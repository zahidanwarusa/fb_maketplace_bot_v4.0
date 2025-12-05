# Enhanced Facebook Marketplace Bot
# Features: Stop functionality, real-time progress, configurable delays, screenshot saving
# Updated: Google Drive image download support
# Browser: Microsoft Edge (msedgedriver.exe)
#
# IMPORTANT: Make sure your CSV data has matching Make/Model combinations!
# Examples of valid combinations:
#   - Honda -> Civic, Accord, CR-V
#   - Acura -> ILX, TLX, MDX, RDX
#   - Toyota -> Camry, Corolla, RAV4
# If Model not found for the Make, bot will automatically select "Other"

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
    
    # Create unique temp folder for this listing with timestamp to avoid conflicts
    safe_name = "".join(c for c in listing_info if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_folder = os.path.join(TEMP_IMAGES_FOLDER, f"{safe_name}_{timestamp}" if safe_name else f'listing_{timestamp}')
    
    # Create temp folder (using unique name avoids need to delete existing)
    try:
        os.makedirs(temp_folder, exist_ok=True)
    except Exception as e:
        print(f"❌ Could not create temp folder: {e}")
        return None
    
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
    """Clean up temporary images folder with Windows-safe error handling"""
    if not os.path.exists(TEMP_IMAGES_FOLDER):
        return
    
    try:
        # Try to remove the entire folder
        shutil.rmtree(TEMP_IMAGES_FOLDER, ignore_errors=True)
        print(f"🧹 Cleaned up temp images folder")
    except Exception as e:
        # If full cleanup fails, try to clean up individual files
        try:
            for root, dirs, files in os.walk(TEMP_IMAGES_FOLDER, topdown=False):
                for name in files:
                    try:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, 0o777)  # Try to change permissions
                        os.remove(file_path)
                    except:
                        pass  # Skip locked files
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except:
                        pass  # Skip locked dirs
            print(f"🧹 Partially cleaned up temp images folder")
        except Exception as e2:
            print(f"⚠️ Could not fully clean temp folder (files may remain): {e}")


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
    """Click element with retry, timeout, and automatic scrolling"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if check_stop_signal():
            return False
        try:
            element = driver.find_element(By.XPATH, ele)
            # Scroll element into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            time.sleep(0.5)  # Wait for scroll to complete
            # Try to click
            webdriver.ActionChains(driver).move_to_element_with_offset(element, 1, 0).click(element).perform()
            return True
        except Exception as e:
            time.sleep(0.5)
            if field_name and (time.time() - start_time) % 5 < 1:  # Print every 5 seconds
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
    """Select Facebook groups for cross-posting with improved detection"""
    if check_stop_signal():
        return 0
        
    print("📋 Selecting Facebook groups to cross-post...")
    try:
        time.sleep(5)
        
        # Try multiple selectors for checkboxes
        checkbox_selectors = [
            "//div[@role='checkbox' and @aria-checked='false']",
            "//input[@type='checkbox' and not(@checked)]/..",
            "//div[contains(@class, 'checkbox') and @aria-checked='false']",
            "//div[@role='checkbox']"
        ]
        
        group_checkboxes = []
        for selector in checkbox_selectors:
            try:
                checkboxes = driver.find_elements(By.XPATH, selector)
                if checkboxes:
                    group_checkboxes = checkboxes
                    print(f"  ✓ Found {len(checkboxes)} potential groups to select")
                    break
            except:
                continue
        
        if not group_checkboxes:
            print("  ⚠️ No group checkboxes found - may already be on final page or groups unavailable")
            return 0
        
        groups_selected = 0
        for checkbox in group_checkboxes[:max_groups]:  # Limit to max_groups
            if check_stop_signal():
                print("⚠️ Stop signal - finishing group selection")
                break
                
            try:
                # Check if already checked
                is_checked = checkbox.get_attribute('aria-checked')
                if is_checked == 'true':
                    continue
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                time.sleep(0.5)
                
                # Try multiple click methods
                try:
                    checkbox.click()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", checkbox)
                    except:
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
    """Close all Chrome instances - DISABLED to keep dashboard alive"""
    # Commented out to preserve Chrome dashboard
    # try:
    #     if sys.platform == 'win32':
    #         os.system("taskkill /im chrome.exe /f 2>nul")
    #     else:
    #         os.system("pkill -f chrome 2>/dev/null")
    # except Exception as e:
    #     print(f"Warning: Could not close Chrome: {e}")
    pass  # Do nothing - keep Chrome alive for dashboard


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
    
    # Display all listing data from Supabase
    print(f"\n📊 LISTING DATA FROM SUPABASE:")
    print(f"  Year: {single_row.get('Year', 'N/A')}")
    print(f"  Make: {single_row.get('Make', 'N/A')}")
    print(f"  Model: {single_row.get('Model', 'N/A')}")
    print(f"  Mileage: {single_row.get('Mileage', 'N/A')}")
    print(f"  Price: {single_row.get('Price', 'N/A')}")
    print(f"  Body Style: {single_row.get('Body Style', 'N/A')}")
    print(f"  Exterior Color: {single_row.get('Exterior Color', 'N/A')}")
    print(f"  Interior Color: {single_row.get('Interior Color', 'N/A')}")
    print(f"  Condition: {single_row.get('Vehicle Condition', 'N/A')}")
    print(f"  Fuel Type: {single_row.get('Fuel Type', 'N/A')}")
    print(f"  Transmission: {single_row.get('Transmission', 'N/A')}")
    print(f"  Images Path: {single_row.get('Images Path', 'N/A')[:50]}...")
    print(f"{'='*60}\n")
    
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
        
        # Wait for page to update after vehicle type selection
        time.sleep(delays.get('element_wait', 2))

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
                
                # Wait longer for images to process
                print("  ⏳ Waiting for images to process...")
                time.sleep(8)
            else:
                return False, "No valid images found"
                
        except Exception as e:
            save_screenshot(driver, 'error_image_exception', profile_name, listing_info)
            return False, f"Image upload error: {str(e)}"
        
        if check_stop_signal():
            return False, "Stopped by user"
        
        time.sleep(delays.get('element_wait', 2))
        
        # Scroll page to ensure all fields are visible
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
        except:
            pass
        
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
        print(f"  🔍 Attempting to select Year: {single_row['Year']}")
        if not specific_clicker(driver, "//span[text()='Year']"):
            save_screenshot(driver, 'error_year_dropdown', profile_name, listing_info)
            return False, "Failed to open Year dropdown"
        
        time.sleep(1)
        year_selected = specific_clicker(driver, f"//span[text()='{single_row['Year']}']", max_wait=10)
        
        if not year_selected:
            save_screenshot(driver, 'error_year_select', profile_name, listing_info)
            return False, f"Year '{single_row['Year']}' not found in dropdown"
        
        print(f"  ✅ Year selected: {single_row['Year']}")
        time.sleep(delays.get('element_wait', 2))

        # Make
        print(f"  🔍 Attempting to select Make: {single_row['Make']}")
        if not specific_clicker(driver, "//span[text()='Make']", "Make dropdown"):
            save_screenshot(driver, 'error_make_dropdown', profile_name, listing_info)
            return False, "Failed to open Make dropdown"
        
        time.sleep(1)
        
        # Show available makes for debugging
        try:
            available_makes = driver.find_elements(By.XPATH, "//div[@role='option']//span")
            if available_makes:
                makes_list = [m.text for m in available_makes[:15] if m.text]
                print(f"  📋 Available makes: {', '.join(makes_list)}")
        except:
            pass
        
        make_selected = specific_clicker(driver, f"//span[text()='{single_row['Make']}']", max_wait=10)
        
        if not make_selected:
            save_screenshot(driver, 'error_make_not_found', profile_name, listing_info)
            return False, f"❌ Make '{single_row['Make']}' not found in dropdown. Check your Supabase data."
        
        print(f"  ✅ Make confirmed: {single_row['Make']}")
        time.sleep(delays.get('element_wait', 2))
        
        # Wait for Model field to appear based on Make selection
        print(f"  ⏳ Waiting for Model field to appear...")
        time.sleep(3)

        # Model - TEXT INPUT FIELD (not dropdown)
        print(f"  🔍 Looking for Model input field...")
        
        # Model is a text input, not a dropdown!
        model_xpaths = [
            "//label[text()='Model']/following-sibling::*//input",
            "//input[@aria-label='Model']",
            "//input[@placeholder='Model']",
            "//label[contains(text(), 'Model')]/..//input",
            "//*[contains(text(), 'Model')]/ancestor::div[1]//input",
            "//input[contains(@placeholder, 'model')]"
        ]
        
        model_entered = False
        target_model = str(single_row['Model'])
        
        for i, xpath in enumerate(model_xpaths):
            try:
                model_input = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", model_input)
                time.sleep(0.5)
                model_input.clear()
                model_input.send_keys(target_model)
                model_entered = True
                print(f"  ✅ Model entered: {target_model} (method {i+1})")
                break
            except:
                continue
        
        if not model_entered:
            print(f"  ⚠️ Could not enter model with any method")
            save_screenshot(driver, 'error_model_input', profile_name, listing_info)
            return False, f"Failed to enter Model: {target_model}"
        
        time.sleep(delays.get('element_wait', 2))

        # Mileage - try multiple XPath patterns
        print(f"  🔍 Looking for Mileage input...")
        mileage_xpaths = [
            "//label[text()='Mileage']/following-sibling::*//input",
            "//input[@aria-label='Mileage']",
            "//input[@placeholder='Mileage']",
            "//label[contains(text(), 'Mileage')]/..//input",
            "//div[contains(@class, 'x1n2onr6')]//input[contains(@aria-label, 'ileage')]",
            # Generic - find input near "Mileage" text
            "//*[contains(text(), 'Mileage')]/ancestor::div[1]//input"
        ]
        
        mileage_entered = False
        for i, xpath in enumerate(mileage_xpaths):
            try:
                # Try to find and enter
                input_elem = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_elem)
                time.sleep(0.5)
                input_elem.clear()
                input_elem.send_keys(str(single_row['Mileage']))
                mileage_entered = True
                print(f"  ✓ Mileage entered: {single_row['Mileage']} (method {i+1})")
                break
            except:
                continue
        
        if not mileage_entered:
            print(f"  ⚠️ Could not enter mileage with any method")
            save_screenshot(driver, 'error_mileage', profile_name, listing_info)
            # Try to find ANY input field that might be mileage
            try:
                all_inputs = driver.find_elements(By.TAG_NAME, 'input')
                print(f"  🔍 Found {len(all_inputs)} input fields on page, taking screenshot for debugging")
            except:
                pass

        # Price - try multiple XPath patterns
        print(f"  🔍 Looking for Price input...")
        price_xpaths = [
            "//label[text()='Price']/following-sibling::*//input",
            "//input[@aria-label='Price']",
            "//input[@placeholder='Price']",
            "//label[contains(text(), 'Price')]/..//input",
            "//div[contains(@class, 'x1n2onr6')]//input[contains(@aria-label, 'rice')]",
            # Generic - find input near "Price" text
            "//*[contains(text(), 'Price')]/ancestor::div[1]//input"
        ]
        
        price_entered = False
        for i, xpath in enumerate(price_xpaths):
            try:
                # Try to find and enter
                input_elem = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_elem)
                time.sleep(0.5)
                input_elem.clear()
                input_elem.send_keys(str(single_row['Price']))
                price_entered = True
                print(f"  ✓ Price entered: ${single_row['Price']} (method {i+1})")
                break
            except:
                continue
        
        if not price_entered:
            print(f"  ⚠️ Could not enter price with any method")
            save_screenshot(driver, 'error_price', profile_name, listing_info)
            return False, "Failed to enter Price - form may be incomplete"
        
        # Detect available form fields for debugging
        print(f"\n  🔍 Detecting available appearance/detail fields...")
        try:
            # Scroll through the page to see all fields
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.35);")
            time.sleep(1)
            
            # Look for common field labels
            field_keywords = ['style', 'color', 'colour', 'condition', 'fuel', 'transmission', 'exterior', 'interior']
            all_text_elements = driver.find_elements(By.XPATH, "//span | //label")
            detected_fields = []
            
            for elem in all_text_elements[:50]:
                try:
                    text = elem.text.strip()
                    if text and len(text) < 40 and any(keyword in text.lower() for keyword in field_keywords):
                        if text not in detected_fields:
                            detected_fields.append(text)
                except:
                    continue
            
            if detected_fields:
                print(f"  📋 Available fields detected: {', '.join(detected_fields[:10])}")
            else:
                print(f"  ⚠️ Could not detect field labels - page structure may be different")
        except Exception as e:
            print(f"  ⚠️ Field detection failed: {str(e)[:50]}")
        print()

        if check_stop_signal():
            return False, "Stopped by user"
        
        # Scroll down to ensure "Vehicle appearance" section is visible
        print(f"  🔍 Scrolling to Vehicle appearance section...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
        time.sleep(1)

        # Body style - with better debugging and fallback
        print(f"  🔍 Looking for Body Style dropdown...")
        if not specific_clicker(driver, "//span[text()='Body style']", "Body style dropdown"):
            save_screenshot(driver, 'error_body_style_dropdown', profile_name, listing_info)
        
        # Wait for dropdown to populate
        time.sleep(1)
        
        # Try to see what body styles are available
        try:
            available_styles = driver.find_elements(By.XPATH, "//div[@role='option']//span")
            if available_styles:
                style_list = [s.text for s in available_styles[:10]]  # First 10
                print(f"  📋 Available body styles: {', '.join(style_list)}")
        except:
            pass
        
        # Try to select the body style
        target_style = str(single_row['Body Style'])
        style_selected = False
        
        # Try exact match first
        if specific_clicker(driver, f"//span[text()='{target_style}']", max_wait=3):
            style_selected = True
            print(f"  ✓ Body Style selected: {target_style}")
        else:
            # Body style not found, try "Other"
            print(f"  ⚠️ Body style '{target_style}' not found in dropdown")
            print(f"  🔄 Attempting to select 'Other'...")
            
            other_xpaths = [
                "//span[text()='Other']",
                "//div[@role='option']//span[text()='Other']"
            ]
            
            for xpath in other_xpaths:
                if specific_clicker(driver, xpath, max_wait=2):
                    style_selected = True
                    print(f"  ✓ Selected 'Other' as fallback for body style")
                    break
            
            if not style_selected:
                print(f"  ⚠️ Could not find '{target_style}' or 'Other', continuing anyway...")
                # Close dropdown
                try:
                    driver.find_element(By.TAG_NAME, 'body').click()
                except:
                    pass

        # Exterior color - with multiple XPath patterns
        print(f"  🔍 Attempting to select Exterior color: {single_row['Exterior Color']}")
        
        # Scroll down to make sure color fields are visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        
        exterior_color_xpaths = [
            "//span[text()='Exterior color']",
            "//span[text()='Exterior colour']",
            "//label[contains(text(), 'Exterior')]",
            "//*[contains(text(), 'Exterior color')]",
            "//*[contains(text(), 'Exterior colour')]",
            # Position-based as fallback
            "//div[contains(@class, 'x1n2onr6') and position()=15]",
            # By placeholder or aria-label
            "//*[@placeholder='Exterior color']",
            "//*[@aria-label='Exterior color']",
            "//*[@placeholder='Exterior colour']",
            "//*[@aria-label='Exterior colour']"
        ]
        
        exterior_color_clicked = False
        for i, xpath in enumerate(exterior_color_xpaths):
            if specific_clicker(driver, xpath, max_wait=3):
                exterior_color_clicked = True
                print(f"  ✓ Exterior color dropdown opened (method {i+1})")
                break
        
        if exterior_color_clicked:
            time.sleep(1)
            
            # Show available colors
            try:
                available_colors = driver.find_elements(By.XPATH, "//div[@role='option']//span")
                if available_colors:
                    colors_list = [c.text for c in available_colors[:15] if c.text]
                    print(f"  📋 Available exterior colors: {', '.join(colors_list)}")
            except:
                pass
            
            # Try to select the color
            target_color = str(single_row['Exterior Color'])
            color_selected = specific_clicker(driver, f"//span[text()='{target_color}']", max_wait=5)
            
            if color_selected:
                print(f"  ✅ Exterior color selected: {target_color}")
            else:
                print(f"  ⚠️ Exterior color '{target_color}' not found, trying alternatives...")
                # Try common variations
                color_variations = [
                    target_color.capitalize(),
                    target_color.upper(),
                    target_color.lower()
                ]
                for variation in color_variations:
                    if specific_clicker(driver, f"//span[text()='{variation}']", max_wait=2):
                        print(f"  ✓ Selected exterior color: {variation}")
                        color_selected = True
                        break
                
                if not color_selected:
                    print(f"  ⚠️ Could not select exterior color, continuing...")
                    save_screenshot(driver, 'warning_exterior_color', profile_name, listing_info)
        else:
            print(f"  ⚠️ Exterior color dropdown not found with any method")
            print(f"  💡 This field may be optional or not present")
            save_screenshot(driver, 'warning_no_exterior_color_field', profile_name, listing_info)
        
        time.sleep(delays.get('element_wait', 2))

        # Interior color - with multiple XPath patterns
        print(f"  🔍 Attempting to select Interior color: {single_row['Interior Color']}")
        
        interior_color_xpaths = [
            "//span[text()='Interior color']",
            "//span[text()='Interior colour']",
            "//label[contains(text(), 'Interior')]",
            "//*[contains(text(), 'Interior color')]",
            "//*[contains(text(), 'Interior colour')]",
            # Position-based as fallback
            "//div[contains(@class, 'x1n2onr6') and position()=16]",
            # By placeholder or aria-label
            "//*[@placeholder='Interior color']",
            "//*[@aria-label='Interior color']",
            "//*[@placeholder='Interior colour']",
            "//*[@aria-label='Interior colour']"
        ]
        
        interior_color_clicked = False
        for i, xpath in enumerate(interior_color_xpaths):
            if specific_clicker(driver, xpath, max_wait=3):
                interior_color_clicked = True
                print(f"  ✓ Interior color dropdown opened (method {i+1})")
                break
        
        if interior_color_clicked:
            time.sleep(1)
            
            # Show available colors
            try:
                available_colors = driver.find_elements(By.XPATH, "//div[@role='option']//span")
                if available_colors:
                    colors_list = [c.text for c in available_colors[:15] if c.text]
                    print(f"  📋 Available interior colors: {', '.join(colors_list)}")
            except:
                pass
            
            # Try to select the color
            target_color = str(single_row['Interior Color'])
            color_selected = specific_clicker(driver, f"//span[text()='{target_color}']", max_wait=5)
            
            if color_selected:
                print(f"  ✅ Interior color selected: {target_color}")
            else:
                print(f"  ⚠️ Interior color '{target_color}' not found, trying alternatives...")
                # Try common variations
                color_variations = [
                    target_color.capitalize(),
                    target_color.upper(),
                    target_color.lower()
                ]
                for variation in color_variations:
                    if specific_clicker(driver, f"//span[text()='{variation}']", max_wait=2):
                        print(f"  ✓ Selected interior color: {variation}")
                        color_selected = True
                        break
                
                if not color_selected:
                    print(f"  ⚠️ Could not select interior color, continuing...")
                    save_screenshot(driver, 'warning_interior_color', profile_name, listing_info)
        else:
            print(f"  ⚠️ Interior color dropdown not found with any method")
            print(f"  💡 This field may be optional or not present")
            save_screenshot(driver, 'warning_no_interior_color_field', profile_name, listing_info)
        
        time.sleep(delays.get('element_wait', 2))

        # Vehicle condition - with validation
        print(f"  🔍 Attempting to select Vehicle condition: {single_row['Vehicle Condition']}")
        
        condition_clicked = specific_clicker(driver, "//span[text()='Vehicle condition']", "Vehicle condition dropdown", max_wait=5)
        
        if condition_clicked:
            time.sleep(1)
            target_condition = str(single_row['Vehicle Condition'])
            
            if specific_clicker(driver, f"//span[text()='{target_condition}']", max_wait=5):
                print(f"  ✅ Condition selected: {target_condition}")
            else:
                print(f"  ⚠️ Condition '{target_condition}' not found, continuing...")
        else:
            print(f"  ⚠️ Vehicle condition dropdown not found")
        
        time.sleep(delays.get('element_wait', 2))

        # Fuel type - with validation
        print(f"  🔍 Attempting to select Fuel type: {single_row['Fuel Type']}")
        
        fuel_clicked = specific_clicker(driver, "//span[text()='Fuel type']", "Fuel type dropdown", max_wait=5)
        
        if fuel_clicked:
            time.sleep(1)
            target_fuel = str(single_row['Fuel Type'])
            
            if specific_clicker(driver, f"//span[text()='{target_fuel}']", max_wait=5):
                print(f"  ✅ Fuel type selected: {target_fuel}")
            else:
                # Try variations (e.g., "Gasoline" vs "Petrol")
                fuel_variations = {
                    'Gasoline': ['Petrol', 'Gas'],
                    'Petrol': ['Gasoline', 'Gas'],
                    'Diesel': ['Diesel fuel'],
                    'Electric': ['EV', 'Battery electric'],
                    'Hybrid': ['Hybrid electric']
                }
                
                found = False
                if target_fuel in fuel_variations:
                    for variation in fuel_variations[target_fuel]:
                        if specific_clicker(driver, f"//span[text()='{variation}']", max_wait=2):
                            print(f"  ✓ Fuel type selected (as {variation}): {target_fuel}")
                            found = True
                            break
                
                if not found:
                    print(f"  ⚠️ Fuel type '{target_fuel}' not found, continuing...")
        else:
            print(f"  ⚠️ Fuel type dropdown not found")
        
        time.sleep(delays.get('element_wait', 2))

        # Transmission - with validation
        print(f"  🔍 Attempting to select Transmission: {single_row['Transmission']}")
        
        trans_clicked = specific_clicker(driver, "//span[text()='Transmission']", "Transmission dropdown", max_wait=5)
        
        if trans_clicked:
            time.sleep(1)
            target_trans = str(single_row['Transmission'])
            
            if specific_clicker(driver, f"//span[text()='{target_trans}']", max_wait=5):
                print(f"  ✅ Transmission selected: {target_trans}")
            else:
                # Try variations
                trans_variations = {
                    'Automatic transmission': ['Automatic', 'Auto'],
                    'Manual transmission': ['Manual'],
                    'Automatic': ['Automatic transmission'],
                    'Manual': ['Manual transmission']
                }
                
                found = False
                if target_trans in trans_variations:
                    for variation in trans_variations[target_trans]:
                        if specific_clicker(driver, f"//span[text()='{variation}']", max_wait=2):
                            print(f"  ✓ Transmission selected (as {variation}): {target_trans}")
                            found = True
                            break
                
                if not found:
                    print(f"  ⚠️ Transmission '{target_trans}' not found, continuing...")
        else:
            print(f"  ⚠️ Transmission dropdown not found")
        
        time.sleep(delays.get('element_wait', 2))

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
        
        # Scroll to bottom before clicking Next to ensure all fields are visible
        print(f"  🔍 Scrolling to ensure all fields are visible...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Take a screenshot before clicking Next for debugging
        save_screenshot(driver, 'before_next_button', profile_name, listing_info)
        
        # Check for any error messages or required field warnings
        try:
            error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'required') or contains(text(), 'Required') or contains(text(), 'must') or contains(text(), 'select')]")
            if error_elements:
                error_messages = [elem.text for elem in error_elements[:5] if elem.text]
                if error_messages:
                    print(f"  ⚠️ Potential validation messages found:")
                    for msg in error_messages:
                        print(f"     - {msg[:100]}")
        except:
            pass

        # Click Next - try multiple approaches
        next_clicked = False
        next_xpaths = [
            '//*[@aria-label="Next" and not(@aria-disabled)]',
            '//div[@aria-label="Next"]',
            '//span[text()="Next"]/..',
            '//div[contains(@class, "x1i10hfl") and contains(text(), "Next")]',
            '//div[@role="button" and contains(., "Next")]'
        ]
        
        for xpath in next_xpaths:
            try:
                next_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                next_button.click()
                print("  ✓ Clicked 'Next' button")
                next_clicked = True
                time.sleep(2)
                break
            except Exception as e:
                continue
        
        if not next_clicked:
            save_screenshot(driver, 'error_next_button_not_clickable', profile_name, listing_info)
            print(f"  ❌ Could not click 'Next' button with any method")
            print(f"  💡 This usually means required fields are missing")
            print(f"  💡 Check: Year, Make, Model (Model is often the issue)")
            return False, "Failed to click Next button - likely missing required fields"
        
        # Verify we progressed to the next page
        time.sleep(3)
        try:
            # Check if we're on the group selection page
            # Look for group-related elements or absence of vehicle form elements
            still_on_form = driver.find_elements(By.XPATH, "//span[text()='Year']")
            if still_on_form:
                save_screenshot(driver, 'error_stuck_on_form_page', profile_name, listing_info)
                print(f"  ❌ Still on form page after clicking Next!")
                print(f"  💡 Facebook prevented progression - likely missing required field")
                
                # Try to identify which fields might be the issue
                print(f"\n  🔍 Checking for potential issues:")
                
                # Check if colors have "Please select" text
                try:
                    color_placeholders = driver.find_elements(By.XPATH, "//*[contains(text(), 'Please select') or contains(text(), 'select the')]")
                    if color_placeholders:
                        for placeholder in color_placeholders[:5]:
                            text = placeholder.text
                            if text:
                                print(f"     ⚠️ Unfilled field: {text[:80]}")
                except:
                    pass
                
                # Check for validation errors
                try:
                    validation_errors = driver.find_elements(By.XPATH, "//*[@role='alert'] | //*[contains(@class, 'error')]")
                    if validation_errors:
                        for error in validation_errors[:3]:
                            text = error.text
                            if text:
                                print(f"     ❌ Validation error: {text[:80]}")
                except:
                    pass
                
                print(f"\n  💡 Common causes:")
                print(f"     - Exterior/Interior colors not selected (if required)")
                print(f"     - Model field might not have registered")
                print(f"     - Some other required field missing")
                print(f"  📸 Check 'before_next_button' screenshot for details")
                
                return False, "Could not progress past vehicle form - check screenshots for missing fields"
            else:
                print(f"  ✅ Successfully progressed to group selection page")
        except:
            pass

        # Select Groups
        groups_selected = select_facebook_groups(driver, max_groups=20, delay=delays.get('group_selection', 1))
        print(f"  ✓ Selected {groups_selected} groups for cross-posting")

        if check_stop_signal():
            return False, "Stopped by user"

        # Click Publish - try multiple approaches
        print(f"  🔍 Looking for Publish button...")
        
        # First, scroll to bottom to ensure button is visible
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        except:
            pass
        
        publish_clicked = False
        publish_xpaths = [
            '//*[@aria-label="Publish"]',
            '//div[@aria-label="Publish"]',
            '//span[text()="Publish"]/..',
            '//div[contains(@class, "x1i10hfl") and contains(text(), "Publish")]',
            '//div[@role="button" and contains(., "Publish")]',
            # Additional patterns
            '//div[@role="button"]//span[text()="Publish"]/..',
            '//div[text()="Publish"]',
            '//*[text()="Publish" and @role="button"]',
            # Case insensitive
            '//*[contains(translate(@aria-label, "PUBLISH", "publish"), "publish")]'
        ]
        
        # Try to see what buttons are available
        try:
            all_buttons = driver.find_elements(By.XPATH, '//div[@role="button"]')
            button_labels = []
            for btn in all_buttons[:10]:
                label = btn.get_attribute('aria-label') or btn.text
                if label:
                    button_labels.append(label[:40])
            if button_labels:
                print(f"  📋 Available buttons: {', '.join(button_labels)}")
        except:
            pass
        
        # Also check if we're still on the preview/form page
        try:
            # Look for indicators that we're still on the form
            preview_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Preview') or contains(text(), 'preview')]")
            if preview_elements:
                print(f"  ℹ️ Still on Preview page - looking for Publish button...")
        except:
            pass
        
        for i, xpath in enumerate(publish_xpaths):
            try:
                publish_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                # Scroll into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_button)
                time.sleep(0.5)
                
                # Try multiple click methods
                try:
                    publish_button.click()
                except:
                    try:
                        driver.execute_script("arguments[0].click();", publish_button)
                    except:
                        webdriver.ActionChains(driver).move_to_element(publish_button).click().perform()
                
                print(f"  ✅ Clicked 'Publish' button (method {i+1})")
                publish_clicked = True
                time.sleep(delays.get('after_publish', 5))
                break
            except Exception as e:
                continue
        
        if not publish_clicked:
            # Try one more time after scrolling to very bottom
            print(f"  🔄 Scrolling to absolute bottom and retrying...")
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight + 1000);")
                time.sleep(2)
                
                for xpath in ['//*[@aria-label="Publish"]', '//div[@role="button" and contains(., "Publish")]', '//span[text()="Publish"]/..']:
                    try:
                        btn = driver.find_element(By.XPATH, xpath)
                        driver.execute_script("arguments[0].click();", btn)
                        print(f"  ✅ Clicked 'Publish' after extra scrolling")
                        publish_clicked = True
                        time.sleep(delays.get('after_publish', 5))
                        break
                    except:
                        continue
            except:
                pass
        
        if not publish_clicked:
            save_screenshot(driver, 'error_publish_button_not_found', profile_name, listing_info)
            print(f"  ❌ Could not find or click 'Publish' button")
            print(f"  💡 Possible reasons:")
            print(f"     - Required fields missing (check Model selection)")
            print(f"     - Page did not progress to final step")
            print(f"     - Facebook UI changed")
            print(f"  📸 Check screenshots for current page state")
            return False, "Publish button not found - likely missing required fields"

        # Wait for publishing to complete - check multiple success indicators
        try:
            # Wait for publish button to disappear OR success message to appear
            success = False
            
            # Check if Publish button disappeared
            try:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.XPATH, '//*[@aria-label="Publish"]'))
                )
                success = True
            except:
                pass
            
            # Check for success message or marketplace URL
            if not success:
                try:
                    # Look for success indicators
                    WebDriverWait(driver, 10).until(
                        lambda d: 'marketplace' in d.current_url.lower() and 'create' not in d.current_url.lower()
                    )
                    success = True
                except:
                    pass
            
            if success:
                print("  ✅ Listing published successfully!")
                save_screenshot(driver, 'success', profile_name, listing_info)
                
                # Validation summary
                print(f"\n{'='*60}")
                print(f"✅ LISTING POSTED SUCCESSFULLY")
                print(f"{'='*60}")
                print(f"  Title: {single_row.get('Year')} {single_row.get('Make')} {single_row.get('Model')}")
                print(f"  Price: ${single_row.get('Price')}")
                print(f"  Mileage: {single_row.get('Mileage')} miles")
                print(f"  Location: {location_of_profile}")
                print(f"{'='*60}\n")
                
                return True, "Success"
            else:
                print("  ⚠️ Publishing status unclear")
                save_screenshot(driver, 'timeout_publish', profile_name, listing_info)
                return False, "Publishing verification timeout"
            
        except Exception as e:
            print(f"  ⚠️ Error verifying publish: {str(e)[:50]}")
            save_screenshot(driver, 'error_publish_verify', profile_name, listing_info)
            return False, f"Publish verification error: {str(e)[:50]}"

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
    print(f"\n⚠️  IMPORTANT: Verify your Supabase data!")
    print(f"   - Make/Model combinations must match Facebook options")
    print(f"   - Example: 'Civic' is a Honda model, not Acura")
    print(f"   - Body styles must match available options")
    print(f"   - Bot will select 'Other' if exact match not found")
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
        
        # Close existing browser - Chrome is now disabled to keep dashboard alive
        close_chrome()  # This function now does nothing (pass)
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