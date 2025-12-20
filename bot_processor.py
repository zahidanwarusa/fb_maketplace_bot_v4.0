"""
Listing Processor Module
Contains the main logic for processing Facebook Marketplace listings
"""

import time
import pyperclip
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

from bot_config import check_stop_signal, update_status
from bot_helpers import (
    save_screenshot, specific_clicker, generate_multiple_images_path,
    input_file_add_files
)
from bot_drive import is_google_drive_url, download_drive_images


# ============================================================================
# FACEBOOK GROUP SELECTION
# ============================================================================

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


# ============================================================================
# MAIN LISTING PROCESSOR
# ============================================================================

def process_single_listing(driver, single_row, location_of_profile, profile_name, listing_index, delays, max_groups):
    """Process a single listing - returns success/failure"""
    
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
            "//*[contains(text(), 'Mileage')]/ancestor::div[1]//input"
        ]
        
        mileage_entered = False
        for i, xpath in enumerate(mileage_xpaths):
            try:
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

        # Price - try multiple XPath patterns
        print(f"  🔍 Looking for Price input...")
        price_xpaths = [
            "//label[text()='Price']/following-sibling::*//input",
            "//input[@aria-label='Price']",
            "//input[@placeholder='Price']",
            "//label[contains(text(), 'Price')]/..//input",
            "//div[contains(@class, 'x1n2onr6')]//input[contains(@aria-label, 'rice')]",
            "//*[contains(text(), 'Price')]/ancestor::div[1]//input"
        ]
        
        price_entered = False
        for i, xpath in enumerate(price_xpaths):
            try:
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
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.35);")
            time.sleep(1)
            
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

        # Body style
        print(f"  🔍 Looking for Body Style dropdown...")
        if not specific_clicker(driver, "//span[text()='Body style']", "Body style dropdown"):
            save_screenshot(driver, 'error_body_style_dropdown', profile_name, listing_info)
        
        time.sleep(1)
        
        try:
            available_styles = driver.find_elements(By.XPATH, "//div[@role='option']//span")
            if available_styles:
                style_list = [s.text for s in available_styles[:10]]
                print(f"  📋 Available body styles: {', '.join(style_list)}")
        except:
            pass
        
        target_style = str(single_row['Body Style'])
        style_selected = False
        
        if specific_clicker(driver, f"//span[text()='{target_style}']", max_wait=3):
            style_selected = True
            print(f"  ✓ Body Style selected: {target_style}")
        else:
            print(f"  ⚠️ Body style '{target_style}' not found in dropdown")
            print(f"  🔄 Attempting to select 'Other'...")
            
            other_xpaths = ["//span[text()='Other']", "//div[@role='option']//span[text()='Other']"]
            
            for xpath in other_xpaths:
                if specific_clicker(driver, xpath, max_wait=2):
                    style_selected = True
                    print(f"  ✓ Selected 'Other' as fallback for body style")
                    break
            
            if not style_selected:
                print(f"  ⚠️ Could not find '{target_style}' or 'Other', continuing anyway...")
                try:
                    driver.find_element(By.TAG_NAME, 'body').click()
                except:
                    pass

        # Exterior color
        print(f"  🔍 Attempting to select Exterior color: {single_row['Exterior Color']}")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        
        exterior_color_xpaths = [
            "//span[text()='Exterior color']",
            "//span[text()='Exterior colour']",
            "//label[contains(text(), 'Exterior')]",
            "//*[contains(text(), 'Exterior color')]"
        ]
        
        exterior_color_clicked = False
        for i, xpath in enumerate(exterior_color_xpaths):
            if specific_clicker(driver, xpath, max_wait=3):
                exterior_color_clicked = True
                print(f"  ✓ Exterior color dropdown opened (method {i+1})")
                break
        
        if exterior_color_clicked:
            time.sleep(1)
            target_color = str(single_row['Exterior Color'])
            color_selected = specific_clicker(driver, f"//span[text()='{target_color}']", max_wait=5)
            
            if color_selected:
                print(f"  ✅ Exterior color selected: {target_color}")
            else:
                print(f"  ⚠️ Exterior color '{target_color}' not found, continuing...")
                save_screenshot(driver, 'warning_exterior_color', profile_name, listing_info)
        else:
            print(f"  ⚠️ Exterior color dropdown not found")
        
        time.sleep(delays.get('element_wait', 2))

        # Interior color
        print(f"  🔍 Attempting to select Interior color: {single_row['Interior Color']}")
        
        interior_color_xpaths = [
            "//span[text()='Interior color']",
            "//span[text()='Interior colour']",
            "//label[contains(text(), 'Interior')]"
        ]
        
        interior_color_clicked = False
        for i, xpath in enumerate(interior_color_xpaths):
            if specific_clicker(driver, xpath, max_wait=3):
                interior_color_clicked = True
                print(f"  ✓ Interior color dropdown opened (method {i+1})")
                break
        
        if interior_color_clicked:
            time.sleep(1)
            target_color = str(single_row['Interior Color'])
            color_selected = specific_clicker(driver, f"//span[text()='{target_color}']", max_wait=5)
            
            if color_selected:
                print(f"  ✅ Interior color selected: {target_color}")
            else:
                print(f"  ⚠️ Interior color '{target_color}' not found, continuing...")
        else:
            print(f"  ⚠️ Interior color dropdown not found")
        
        time.sleep(delays.get('element_wait', 2))

        # Vehicle condition
        print(f"  🔍 Attempting to select Vehicle condition: {single_row['Vehicle Condition']}")
        condition_clicked = specific_clicker(driver, "//span[text()='Vehicle condition']", max_wait=5)
        
        if condition_clicked:
            time.sleep(1)
            target_condition = str(single_row['Vehicle Condition'])
            if specific_clicker(driver, f"//span[text()='{target_condition}']", max_wait=5):
                print(f"  ✅ Condition selected: {target_condition}")
            else:
                print(f"  ⚠️ Condition '{target_condition}' not found, continuing...")
        
        time.sleep(delays.get('element_wait', 2))

        # Fuel type
        print(f"  🔍 Attempting to select Fuel type: {single_row['Fuel Type']}")
        fuel_clicked = specific_clicker(driver, "//span[text()='Fuel type']", max_wait=5)
        
        if fuel_clicked:
            time.sleep(1)
            target_fuel = str(single_row['Fuel Type'])
            if specific_clicker(driver, f"//span[text()='{target_fuel}']", max_wait=5):
                print(f"  ✅ Fuel type selected: {target_fuel}")
            else:
                print(f"  ⚠️ Fuel type '{target_fuel}' not found, continuing...")
        
        time.sleep(delays.get('element_wait', 2))

        # Transmission
        print(f"  🔍 Attempting to select Transmission: {single_row['Transmission']}")
        trans_clicked = specific_clicker(driver, "//span[text()='Transmission']", max_wait=5)
        
        if trans_clicked:
            time.sleep(1)
            target_trans = str(single_row['Transmission'])
            if specific_clicker(driver, f"//span[text()='{target_trans}']", max_wait=5):
                print(f"  ✅ Transmission selected: {target_trans}")
            else:
                print(f"  ⚠️ Transmission '{target_trans}' not found, continuing...")
        
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
            except:
                print(f"  ❌ Failed to enter description")
        
        time.sleep(delays.get('element_wait', 2) * 4)

        if check_stop_signal():
            return False, "Stopped by user"
        
        # Scroll and take screenshot before Next
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        save_screenshot(driver, 'before_next_button', profile_name, listing_info)

        # Click Next
        next_clicked = False
        next_xpaths = [
            '//*[@aria-label="Next" and not(@aria-disabled)]',
            '//div[@aria-label="Next"]',
            '//span[text()="Next"]/..',
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
            except:
                continue
        
        if not next_clicked:
            save_screenshot(driver, 'error_next_button', profile_name, listing_info)
            return False, "Failed to click Next button"
        
        # Verify progression
        time.sleep(3)
        still_on_form = driver.find_elements(By.XPATH, "//span[text()='Year']")
        if still_on_form:
            save_screenshot(driver, 'error_stuck_on_form', profile_name, listing_info)
            return False, "Could not progress past vehicle form"

        # Select Groups
        groups_selected = select_facebook_groups(driver, max_groups=max_groups, delay=delays.get('group_selection', 1))
        print(f"  ✓ Selected {groups_selected} groups for cross-posting")

        if check_stop_signal():
            return False, "Stopped by user"

        # Click Publish
        print(f"  🔍 Looking for Publish button...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        publish_clicked = False
        publish_xpaths = [
            '//*[@aria-label="Publish"]',
            '//div[@aria-label="Publish"]',
            '//span[text()="Publish"]/..',
            '//div[@role="button" and contains(., "Publish")]'
        ]
        
        for i, xpath in enumerate(publish_xpaths):
            try:
                publish_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_button)
                time.sleep(0.5)
                
                try:
                    publish_button.click()
                except:
                    driver.execute_script("arguments[0].click();", publish_button)
                
                print(f"  ✅ Clicked 'Publish' button (method {i+1})")
                publish_clicked = True
                time.sleep(delays.get('after_publish', 5))
                break
            except:
                continue
        
        if not publish_clicked:
            save_screenshot(driver, 'error_publish_button', profile_name, listing_info)
            return False, "Publish button not found"

        # Wait for publishing to complete
        try:
            success = False
            
            try:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.XPATH, '//*[@aria-label="Publish"]'))
                )
                success = True
            except:
                pass
            
            if not success:
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: 'marketplace' in d.current_url.lower() and 'create' not in d.current_url.lower()
                    )
                    success = True
                except:
                    pass
            
            if success:
                print("  ✅ Listing published successfully!")
                save_screenshot(driver, 'success', profile_name, listing_info)
                
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
                save_screenshot(driver, 'timeout_publish', profile_name, listing_info)
                return False, "Publishing verification timeout"
            
        except Exception as e:
            save_screenshot(driver, 'error_publish_verify', profile_name, listing_info)
            return False, f"Publish verification error: {str(e)[:50]}"

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"  ❌ Error processing listing: {error_msg}")
        save_screenshot(driver, 'error_exception', profile_name, listing_info)
        return False, error_msg