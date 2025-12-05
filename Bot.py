# Enhanced Facebook Marketplace Bot
# Features: Stop functionality, real-time progress, configurable delays, screenshot saving
# Updated: Google Drive image download support
# Browser: Microsoft Edge (msedgedriver.exe)

import os
import sys
import time
import json
import signal
import re
import shutil
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import pyperclip
import pyautogui

# ============================================================================
# EDGE WEBDRIVER PATH
# ============================================================================
EDGE_DRIVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webdrivers', 'msedgedriver.exe')

# ============================================================================
# CONFIGURATION
# ============================================================================

SCREENSHOT_FOLDER = 'fbmpss'
STATUS_FILE = 'bot_status.json'
STOP_FILE = 'bot_stop_signal.txt'
TEMP_IMAGES_FOLDER = 'temp_bot_images'  # Temporary folder for downloaded Google Drive images

# Default delays (in seconds) - can be overridden by config
DEFAULT_DELAYS = {
    'between_listings': 5,      # Delay between posting different listings
    'between_profiles': 10,     # Delay when switching profiles
    'after_publish': 5,         # Delay after clicking publish
    'page_load': 4,             # Wait for page to load
    'element_wait': 2,          # Wait between element interactions
    'group_selection': 1,       # Delay between selecting groups
}

# ============================================================================
# GLOBAL STATE
# ============================================================================

bot_should_stop = False
current_driver = None


# ============================================================================
# SIGNAL HANDLERS & STOP FUNCTIONALITY
# ============================================================================

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    global bot_should_stop
    print("\n⚠️ Stop signal received! Finishing current operation...")
    bot_should_stop = True
    update_status('stopping', 'Stop signal received, finishing current operation...')


def check_stop_signal():
    """Check if stop signal file exists"""
    global bot_should_stop
    if os.path.exists(STOP_FILE):
        bot_should_stop = True
        try:
            os.remove(STOP_FILE)
        except:
            pass
        return True
    return bot_should_stop


def cleanup_stop_signal():
    """Remove stop signal file if exists"""
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
        except:
            pass


# ============================================================================
# STATUS TRACKING
# ============================================================================

def update_status(status, message, **kwargs):
    """Update bot status to JSON file for real-time tracking"""
    status_data = {
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'updated_at': time.time(),
        **kwargs
    }
    
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not update status file: {e}")
    
    # Also print to console
    print(f"[{status.upper()}] {message}")


def get_progress_info(current_profile_idx, total_profiles, current_listing_idx, total_listings):
    """Calculate overall progress percentage"""
    if total_profiles == 0 or total_listings == 0:
        return 0
    
    listings_per_profile = total_listings
    total_operations = total_profiles * listings_per_profile
    completed_operations = (current_profile_idx * listings_per_profile) + current_listing_idx
    
    return int((completed_operations / total_operations) * 100)


# ============================================================================
# SCREENSHOT MANAGEMENT
# ============================================================================

def ensure_screenshot_folder():
    """Ensure screenshot folder exists"""
    if not os.path.exists(SCREENSHOT_FOLDER):
        os.makedirs(SCREENSHOT_FOLDER)
        print(f"📁 Created screenshot folder: {SCREENSHOT_FOLDER}")


def save_screenshot(driver, prefix, profile_name="", listing_info=""):
    """Save screenshot to fbmpss folder with descriptive name"""
    ensure_screenshot_folder()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Clean up names for filename
    clean_profile = "".join(c for c in profile_name if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    clean_listing = "".join(c for c in listing_info if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    
    filename = f"{prefix}_{clean_profile}_{clean_listing}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_FOLDER, filename)
    
    try:
        driver.save_screenshot(filepath)
        print(f"📸 Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"⚠️ Failed to save screenshot: {e}")
        return None


# ============================================================================
# GOOGLE DRIVE IMAGE DOWNLOAD FUNCTIONS
# ============================================================================

def is_google_drive_url(path):
    """Check if the path is a Google Drive URL"""
    if not path:
        return False
    drive_patterns = [
        'drive.google.com',
        'docs.google.com',
        'googleapis.com'
    ]
    return any(pattern in str(path).lower() for pattern in drive_patterns)


def extract_drive_id(url):
    """Extract Google Drive file/folder ID from URL"""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'/folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'^([a-zA-Z0-9_-]{25,})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, str(url))
        if match:
            return match.group(1)
    return None


def download_drive_images(drive_url, listing_info=""):
    """Download images from Google Drive URL to temp folder"""
    print(f"☁️  Detected Google Drive URL, downloading images...")
    
    # Create unique temp folder for this listing
    safe_name = "".join(c for c in listing_info if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    temp_folder = os.path.join(TEMP_IMAGES_FOLDER, safe_name or 'listing')
    
    # Clean up existing temp folder for this listing
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
    os.makedirs(temp_folder)
    
    try:
        # Import the drive manager
        from google_drive_manager import get_drive_manager
        from googleapiclient.http import MediaIoBaseDownload
        
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        
        file_id = extract_drive_id(drive_url)
        if not file_id:
            print(f"❌ Could not extract file ID from URL: {drive_url}")
            return None
        
        # Check if it's a folder or file
        try:
            file_metadata = drive_manager.service.files().get(
                fileId=file_id, 
                fields='mimeType, name'
            ).execute()
            
            is_folder = file_metadata.get('mimeType') == 'application/vnd.google-apps.folder'
            
            if is_folder:
                # Download all images from folder
                print(f"📁 Downloading images from folder: {file_metadata.get('name', 'Unknown')}")
                
                # Query for image files in the folder
                query = f"'{file_id}' in parents and trashed=false and (mimeType contains 'image/')"
                results = drive_manager.service.files().list(
                    q=query,
                    pageSize=100,
                    fields='files(id, name, mimeType)'
                ).execute()
                
                files = results.get('files', [])
                downloaded = []
                
                for file in files:
                    file_path = os.path.join(temp_folder, file['name'])
                    try:
                        request = drive_manager.service.files().get_media(fileId=file['id'])
                        with open(file_path, 'wb') as f:
                            downloader = MediaIoBaseDownload(f, request)
                            done = False
                            while not done:
                                status, done = downloader.next_chunk()
                        downloaded.append(file_path)
                        print(f"  ✓ {file['name']}")
                    except Exception as e:
                        print(f"  ✗ Failed to download {file['name']}: {e}")
                
            else:
                # Single file - download it
                print(f"📄 Downloading single image: {file_metadata.get('name', 'Unknown')}")
                filename = file_metadata.get('name', f'image_{file_id}.jpg')
                file_path = os.path.join(temp_folder, filename)
                
                try:
                    request = drive_manager.service.files().get_media(fileId=file_id)
                    with open(file_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                    print(f"  ✓ {filename}")
                except Exception as e:
                    print(f"  ✗ Failed to download: {e}")
            
            # Check if we got any images
            images = [f for f in os.listdir(temp_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'))]
            if images:
                print(f"✓ Downloaded {len(images)} image(s) to: {temp_folder}")
                return temp_folder
            else:
                print("❌ No images were downloaded")
                return None
                
        except Exception as e:
            print(f"❌ Error accessing Google Drive: {e}")
            return None
            
    except ImportError:
        print("❌ Google Drive manager not available")
        return None
    except Exception as e:
        print(f"❌ Error downloading from Google Drive: {e}")
        return None


def cleanup_temp_images():
    """Clean up temporary images folder"""
    if os.path.exists(TEMP_IMAGES_FOLDER):
        try:
            shutil.rmtree(TEMP_IMAGES_FOLDER)
            print(f"🧹 Cleaned up temp images folder")
        except Exception as e:
            print(f"⚠️ Could not clean temp folder: {e}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_file_data(file_name):
    """Read file and return lines"""
    with open(file_name, 'r', encoding='utf-8') as file:
        data = file.read().strip().split('\n')
    return data


def find_element_send_text(driver, ele, text, clear=True):
    """Find element and send text with retry"""
    max_attempts = 10
    for attempt in range(max_attempts):
        if check_stop_signal():
            return False
        try:
            input_field = driver.find_element(By.XPATH, ele)
            if clear:
                input_field.clear()
            input_field.send_keys(text)
            return True
        except Exception as e:
            if attempt == max_attempts - 1:
                print(f"Failed to send text after {max_attempts} attempts: {e}")
                return False
            time.sleep(0.1)
    return False


def specific_clicker(driver, ele, field_name="", max_wait=30):
    """Click element with retry and timeout"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if check_stop_signal():
            return False
        try:
            element = driver.find_element(By.XPATH, ele)
            webdriver.ActionChains(driver).move_to_element_with_offset(element, 1, 0).click(element).perform()
            return True
        except Exception as e:
            time.sleep(0.5)
            if field_name:
                print(f"Waiting for: {field_name}")
    print(f"⚠️ Timeout waiting for element: {field_name or ele}")
    return False


def specific_clicker2(driver, ele):
    """Try to click element without blocking"""
    try:
        element = driver.find_element(By.XPATH, ele)
        webdriver.ActionChains(driver).move_to_element_with_offset(element, 1, 0).click(element).perform()
        return True
    except:
        return False


def select_facebook_groups(driver, max_groups=20, delay=1):
    """Select Facebook groups for cross-posting"""
    if check_stop_signal():
        return 0
        
    print("📋 Selecting Facebook groups to cross-post...")
    try:
        time.sleep(5)
        
        group_checkboxes = driver.find_elements(By.XPATH, "//div[@role='checkbox' and @aria-checked='false']")
        
        groups_selected = 0
        for checkbox in group_checkboxes:
            if check_stop_signal():
                print("⚠️ Stop signal - finishing group selection")
                break
                
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(0.5)
                webdriver.ActionChains(driver).move_to_element(checkbox).click(checkbox).perform()
                groups_selected += 1
                print(f"  ✓ Selected group {groups_selected}")
                
                if groups_selected >= max_groups:
                    print(f"  ✓ Maximum groups ({max_groups}) selected")
                    break
                    
                time.sleep(delay)
                
            except Exception as e:
                print(f"  ⚠️ Failed to select a group: {str(e)[:50]}")
                continue
                
        print(f"✅ Successfully selected {groups_selected} groups")
        return groups_selected
        
    except Exception as e:
        print(f"❌ Error selecting Facebook groups: {str(e)}")
        return 0


def generate_multiple_images_path(images_path):
    """Generate sorted image paths for upload"""
    if not os.path.exists(images_path):
        print(f"❌ ERROR: Directory does not exist: {images_path}")
        return None
        
    def sort_key(filename):
        name = filename.lower()
        if name[0].isdigit():
            numeric_part = ''.join(c for c in name if c.isdigit())
            return (0, numeric_part.zfill(2), name)
        elif name[0].isalpha():
            return (1, name[0], name)
        return (2, name, name)
    
    valid_files = []
    for root, dirs, files in os.walk(images_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heif', '.heic', '.webp')):
                file_path = os.path.join(root, file)
                valid_files.append((file, os.path.abspath(file_path)))
    
    if not valid_files:
        print(f"❌ ERROR: No valid images found in {images_path}")
        return None
    
    sorted_files = sorted(valid_files, key=lambda x: sort_key(x[0]))
    
    print(f"\n📷 Found {len(sorted_files)} valid images (in upload order):")
    for i, (filename, filepath) in enumerate(sorted_files, 1):
        marker = " ← Feature image" if i == 1 else ""
        print(f"  {i}. {filename}{marker}")
    print()
    
    return '\n'.join(file[1] for file in sorted_files)


def input_file_add_files(driver, selector, files):
    """Add files to input element"""
    if not files:
        print("❌ No valid files provided for upload")
        return False
        
    try:
        input_file = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        print("✓ Found file input element")
    except Exception as e:
        print(f'❌ ERROR: Could not find file input element')
        return False

    time.sleep(2)

    try:
        print("📤 Uploading images in specified order...")
        input_file.send_keys(files)
        print("✓ Files sent successfully")
        time.sleep(3)
        return True
        
    except Exception as e:
        print(f'❌ ERROR: Failed to send files to input')
        return False


def close_chrome():
    """Close all Chrome instances"""
    try:
        if sys.platform == 'win32':
            os.system("taskkill /im chrome.exe /f 2>nul")
        else:
            os.system("pkill -f chrome 2>/dev/null")
    except Exception as e:
        print(f"Warning: Could not close Chrome: {e}")


def close_edge():
    """Close all Edge instances"""
    try:
        if sys.platform == 'win32':
            os.system("taskkill /im msedge.exe /f 2>nul")
        else:
            os.system("pkill -f msedge 2>/dev/null")
    except Exception as e:
        print(f"Warning: Could not close Edge: {e}")


# ============================================================================
# MAIN BOT LOGIC
# ============================================================================

def process_single_listing(driver, single_row, location_of_profile, profile_name, listing_index, delays):
    """Process a single listing - returns success/failure"""
    global bot_should_stop
    
    if check_stop_signal():
        return False, "Stopped by user"
    
    listing_info = f"{single_row.get('Year', '')} {single_row.get('Make', '')} {single_row.get('Model', '')}"
    print(f"\n{'='*60}")
    print(f"📝 Processing: {listing_info}")
    print(f"{'='*60}")
    
    update_status('processing', f'Processing: {listing_info}', 
                  current_listing=listing_info,
                  profile=profile_name)
    
    try:
        # Navigate to Marketplace create vehicle page
        driver.get("https://www.facebook.com/marketplace/create/vehicle")
        time.sleep(delays.get('page_load', 4))
        
        if check_stop_signal():
            return False, "Stopped by user"

        # Vehicle Type
        if not specific_clicker(driver, "//span[text()='Vehicle type']"):
            save_screenshot(driver, 'error_vehicle_type', profile_name, listing_info)
            return False, "Failed to click Vehicle type"
        if not specific_clicker(driver, f"//span[contains(text(), 'Car/')]"):
            save_screenshot(driver, 'error_vehicle_type_select', profile_name, listing_info)
            return False, "Failed to select Car type"

        # Upload Images - WITH GOOGLE DRIVE SUPPORT
        try:
            images_directory = single_row['Images Path']
            print(f"📁 Processing images from: {images_directory}")
            
            # Check if it's a Google Drive URL and download images
            if is_google_drive_url(images_directory):
                local_folder = download_drive_images(images_directory, listing_info)
                if local_folder:
                    images_directory = local_folder
                else:
                    return False, "Failed to download images from Google Drive"
            
            image_paths = generate_multiple_images_path(images_directory)
            
            if image_paths:
                success = input_file_add_files(
                    driver,
                    'input[accept="image/*,image/heif,image/heic"]',
                    image_paths
                )
                if not success:
                    save_screenshot(driver, 'error_image_upload', profile_name, listing_info)
                    return False, "Failed to upload images"
                
                time.sleep(5)
            else:
                return False, "No valid images found"
                
        except Exception as e:
            save_screenshot(driver, 'error_image_exception', profile_name, listing_info)
            return False, f"Image upload error: {str(e)}"
        
        if check_stop_signal():
            return False, "Stopped by user"
        
        time.sleep(delays.get('element_wait', 2))
        
        # Location
        try:
            loc_input = driver.find_element(By.XPATH, "//span[text()='Location']/../input")
            loc_input.send_keys(Keys.CONTROL + "a")
            loc_input.send_keys(Keys.DELETE)
            loc_input.send_keys(location_of_profile)
            time.sleep(2)
            loc_input.send_keys(Keys.ARROW_DOWN)
            loc_input.send_keys(Keys.ENTER)
            print(f"  ✓ Location set: {location_of_profile}")
        except Exception as e:
            print(f"  ⚠️ Error setting location: {str(e)[:50]}")

        if check_stop_signal():
            return False, "Stopped by user"

        # Year
        if not specific_clicker(driver, "//span[text()='Year']"):
            save_screenshot(driver, 'error_year', profile_name, listing_info)
        if not specific_clicker(driver, f"//span[text()='{single_row['Year']}']"):
            save_screenshot(driver, 'error_year_select', profile_name, listing_info)
        print(f"  ✓ Year: {single_row['Year']}")

        # Make
        if not specific_clicker(driver, "//span[text()='Make']"):
            save_screenshot(driver, 'error_make', profile_name, listing_info)
        if not specific_clicker(driver, f"//span[text()='{single_row['Make']}']"):
            save_screenshot(driver, 'error_make_select', profile_name, listing_info)
        print(f"  ✓ Make: {single_row['Make']}")

        # Model
        if not specific_clicker(driver, "//span[text()='Model']"):
            save_screenshot(driver, 'error_model', profile_name, listing_info)
        if not specific_clicker(driver, f"//span[text()='{single_row['Model']}']"):
            save_screenshot(driver, 'error_model_select', profile_name, listing_info)
        print(f"  ✓ Model: {single_row['Model']}")

        # Mileage
        find_element_send_text(driver, "//label[text()='Mileage']/following-sibling::*//input", str(single_row['Mileage']))
        print(f"  ✓ Mileage: {single_row['Mileage']}")

        # Price
        find_element_send_text(driver, "//label[text()='Price']/following-sibling::*//input", str(single_row['Price']))
        print(f"  ✓ Price: {single_row['Price']}")

        if check_stop_signal():
            return False, "Stopped by user"

        # Body style
        if not specific_clicker(driver, "//span[text()='Body style']"):
            save_screenshot(driver, 'error_body_style', profile_name, listing_info)
        if not specific_clicker(driver, f"//span[text()='{single_row['Body Style']}']"):
            save_screenshot(driver, 'error_body_style_select', profile_name, listing_info)
        print(f"  ✓ Body Style: {single_row['Body Style']}")

        # Exterior color
        specific_clicker2(driver, "//span[text()='Exterior color']")
        specific_clicker2(driver, f"//span[text()='{single_row['Exterior Color']}']")
        print(f"  ✓ Exterior Color: {single_row['Exterior Color']}")

        # Interior color
        specific_clicker2(driver, "//span[text()='Interior color']")
        specific_clicker2(driver, f"//span[text()='{single_row['Interior Color']}']")
        print(f"  ✓ Interior Color: {single_row['Interior Color']}")

        # Vehicle condition
        specific_clicker2(driver, "//span[text()='Vehicle condition']")
        specific_clicker2(driver, f"//span[text()='{single_row['Vehicle Condition']}']")
        print(f"  ✓ Condition: {single_row['Vehicle Condition']}")

        # Fuel type
        specific_clicker2(driver, "//span[text()='Fuel type']")
        specific_clicker2(driver, f"//span[text()='{single_row['Fuel Type']}']")
        print(f"  ✓ Fuel Type: {single_row['Fuel Type']}")

        # Transmission
        specific_clicker2(driver, "//span[text()='Transmission']")
        specific_clicker2(driver, f"//span[text()='{single_row['Transmission']}']")
        print(f"  ✓ Transmission: {single_row['Transmission']}")

        if check_stop_signal():
            return False, "Stopped by user"

        # Description
        description = single_row['Description']
        pyperclip.copy(description)

        try:
            description_textarea = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//textarea[@id and @dir='ltr']"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", description_textarea)
            description_textarea.click()
            description_textarea.send_keys(Keys.CONTROL, 'v')
            print("  ✓ Description entered successfully")
        except Exception as e:
            print(f"  ⚠️ Error entering description: {str(e)[:50]}")
            try:
                description_textarea = driver.find_element(By.TAG_NAME, "textarea")
                description_textarea.send_keys(description)
                print("  ✓ Description entered using alternative method")
            except Exception as e:
                print(f"  ❌ Failed to enter description: {str(e)[:50]}")
        
        time.sleep(delays.get('element_wait', 2) * 4)

        if check_stop_signal():
            return False, "Stopped by user"

        # Click Next
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@aria-label="Next" and not(@aria-disabled)]'))
            )
            next_button.click()
            print("  ✓ Clicked 'Next' button")
            time.sleep(2)
        except Exception as e:
            save_screenshot(driver, 'error_next_button', profile_name, listing_info)
            print(f"  ⚠️ Error clicking 'Next' button: {str(e)[:50]}")

        # Select Groups
        groups_selected = select_facebook_groups(driver, max_groups=20, delay=delays.get('group_selection', 1))
        print(f"  ✓ Selected {groups_selected} groups for cross-posting")

        if check_stop_signal():
            return False, "Stopped by user"

        # Click Publish
        try:
            publish_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@aria-label="Publish"]'))
            )
            publish_button.click()
            print("  ✓ Clicked 'Publish' button")
            time.sleep(delays.get('after_publish', 5))
        except Exception as e:
            save_screenshot(driver, 'error_publish_button', profile_name, listing_info)
            print(f"  ⚠️ Error clicking 'Publish' button: {str(e)[:50]}")

        # Wait for publishing to complete
        try:
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.XPATH, '//*[@aria-label="Publish"]'))
            )
            print("  ✅ Listing published successfully!")
            
            # Save success screenshot
            save_screenshot(driver, 'success', profile_name, listing_info)
            
        except TimeoutException:
            print("  ⚠️ Publishing process took longer than expected")
            save_screenshot(driver, 'timeout_publish', profile_name, listing_info)

        return True, "Success"

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"  ❌ Error processing listing: {error_msg}")
        save_screenshot(driver, 'error_exception', profile_name, listing_info)
        return False, error_msg


def run_bot():
    """Main bot execution function"""
    global bot_should_stop, current_driver
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Cleanup any existing stop signal
    cleanup_stop_signal()
    
    # Ensure screenshot folder exists
    ensure_screenshot_folder()
    
    # Load configuration
    delays = DEFAULT_DELAYS.copy()
    if os.path.exists('bot_config.json'):
        try:
            with open('bot_config.json', 'r') as f:
                config = json.load(f)
                delays.update(config.get('delays', {}))
                print("📋 Loaded custom configuration")
        except:
            print("⚠️ Could not load config, using defaults")
    
    # Load profiles and listings
    try:
        list_of_profiles = get_file_data("selected_profiles.txt")
        df = pd.read_csv('selected_listings.csv')
    except FileNotFoundError as e:
        update_status('error', f'Required file not found: {e}')
        return
    except Exception as e:
        update_status('error', f'Error loading data: {e}')
        return
    
    total_profiles = len(list_of_profiles)
    total_listings = len(df)
    
    print(f"\n{'='*60}")
    print(f"🚀 FB MARKETPLACE BOT - STARTING")
    print(f"{'='*60}")
    print(f"📊 Profiles: {total_profiles}")
    print(f"📋 Listings: {total_listings}")
    print(f"📁 Screenshots: {SCREENSHOT_FOLDER}/")
    print(f"{'='*60}\n")
    
    update_status('running', 'Bot started', 
                  total_profiles=total_profiles,
                  total_listings=total_listings,
                  progress=0)
    
    results = {
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }
    
    for profile_idx, single_profile in enumerate(list_of_profiles):
        if check_stop_signal():
            print("\n⚠️ Bot stopped by user")
            update_status('stopped', 'Bot stopped by user', results=results)
            break
        
        try:
            path, location_of_profile, user_name = single_profile.strip().split('|')
        except ValueError:
            print(f"⚠️ Invalid profile format: {single_profile}")
            continue
            
        profile_name = os.path.basename(path)
        user_data_dir = os.path.dirname(path)
        
        print(f"\n{'='*60}")
        print(f"👤 PROFILE {profile_idx + 1}/{total_profiles}: {user_name}")
        print(f"📍 Location: {location_of_profile}")
        print(f"{'='*60}")
        
        update_status('running', f'Switching to profile: {user_name}',
                      current_profile=user_name,
                      current_profile_idx=profile_idx + 1,
                      total_profiles=total_profiles,
                      progress=get_progress_info(profile_idx, total_profiles, 0, total_listings))
        
        # Close existing browser
        close_chrome()
        close_edge()
        time.sleep(delays.get('between_profiles', 10) // 2)
        
        if check_stop_signal():
            break
        
        # Setup Edge browser options
        options = Options()
        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument(f"profile-directory={profile_name}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--no-first-run')
        options.add_argument('--no-default-browser-check')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        try:
            # Use Edge WebDriver with explicit path
            service = Service(executable_path=EDGE_DRIVER_PATH)
            driver = webdriver.Edge(service=service, options=options)
            current_driver = driver
            driver.maximize_window()
            print("✓ Edge browser launched successfully")
        except WebDriverException as e:
            print(f"❌ Failed to launch browser: {e}")
            results['details'].append({
                'profile': user_name,
                'status': 'error',
                'message': f'Browser launch failed: {str(e)[:50]}'
            })
            continue
        
        # Process each listing
        for listing_idx, single_row in df.iterrows():
            if check_stop_signal():
                print("\n⚠️ Bot stopped by user")
                break
            
            progress = get_progress_info(profile_idx, total_profiles, listing_idx, total_listings)
            listing_info = f"{single_row.get('Year', '')} {single_row.get('Make', '')} {single_row.get('Model', '')}"
            
            update_status('running', f'Processing listing {listing_idx + 1}/{total_listings}',
                          current_profile=user_name,
                          current_listing=listing_info,
                          current_listing_idx=listing_idx + 1,
                          total_listings=total_listings,
                          progress=progress)
            
            success, message = process_single_listing(
                driver, single_row, location_of_profile, 
                user_name, listing_idx, delays
            )
            
            results['details'].append({
                'profile': user_name,
                'listing': listing_info,
                'status': 'success' if success else 'failed',
                'message': message
            })
            
            if success:
                results['success'] += 1
                print(f"  ✅ Listing {listing_idx + 1} completed successfully")
            else:
                if message == "Stopped by user":
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                print(f"  ❌ Listing {listing_idx + 1} failed: {message}")
            
            # Delay between listings
            if listing_idx < len(df) - 1 and not check_stop_signal():
                delay = delays.get('between_listings', 5)
                print(f"  ⏳ Waiting {delay}s before next listing...")
                time.sleep(delay)
        
        # Close browser after profile
        try:
            driver.quit()
            current_driver = None
            print(f"✓ Browser closed for profile: {user_name}")
        except:
            pass
        
        # Delay between profiles
        if profile_idx < len(list_of_profiles) - 1 and not check_stop_signal():
            delay = delays.get('between_profiles', 10)
            print(f"⏳ Waiting {delay}s before next profile...")
            time.sleep(delay)
    
    # Clean up temp images folder
    cleanup_temp_images()
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"🏁 BOT EXECUTION COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️ Skipped: {results['skipped']}")
    print(f"📁 Screenshots saved to: {SCREENSHOT_FOLDER}/")
    print(f"{'='*60}\n")
    
    final_status = 'completed' if not bot_should_stop else 'stopped'
    update_status(final_status, 'Bot execution finished', 
                  results=results,
                  progress=100 if not bot_should_stop else get_progress_info(profile_idx, total_profiles, listing_idx, total_listings))
    
    return results


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n⚠️ Bot interrupted by user")
        update_status('stopped', 'Bot interrupted by user')
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        update_status('error', f'Critical error: {str(e)}')
    finally:
        # Cleanup
        if current_driver:
            try:
                current_driver.quit()
            except:
                pass
        cleanup_stop_signal()
        cleanup_temp_images()