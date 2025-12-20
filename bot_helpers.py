"""
Bot Helper Functions Module
Contains utility functions for screenshots, clicking elements, and file operations
"""

import os
import sys
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

from bot_config import SCREENSHOT_FOLDER, check_stop_signal


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
# FILE OPERATIONS
# ============================================================================

def get_file_data(file_name):
    """Read file and return lines"""
    with open(file_name, 'r', encoding='utf-8') as file:
        data = file.read().strip().split('\n')
    return data


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


# ============================================================================
# SELENIUM HELPER FUNCTIONS
# ============================================================================

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


# ============================================================================
# BROWSER CONTROL
# ============================================================================

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
