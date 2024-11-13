# Import statements remain the same
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pyperclip
import pyautogui

# Keep all existing functions unchanged
def get_file_data(file_name):
    with open(file_name, 'r', encoding='utf-8') as file:
        data = file.read().strip().split('\n')
    return data

def find_element_send_text(driver, ele, text, clear=True):
    while True:
        try:
            input_field = driver.find_element(By.XPATH, ele)
            if clear:
                input_field.clear()
            input_field.send_keys(text)
            break
        except Exception as e:
            print(e)
            time.sleep(0.1)

def specific_clicker(driver, ele, field_name=""):
    while True:
        try:
            element = driver.find_element(By.XPATH, ele)
            webdriver.ActionChains(driver).move_to_element_with_offset(element, 1, 0).click(element).perform()
            break
        except Exception as e:
            time.sleep(0.5)
            print(f"This is not available: {field_name}")
            pass

def specific_clicker2(driver, ele):
    try:
        element = driver.find_element(By.XPATH, ele)
        webdriver.ActionChains(driver).move_to_element_with_offset(element, 1, 0).click(element).perform()
    except Exception as e:
        pass

def generate_multiple_images_path(images_path):
    """
    Generate properly formatted string of image paths.
    """
    if not os.path.exists(images_path):
        print(f"ERROR: Directory does not exist: {images_path}")
        return None
        
    valid_files = []
    for root, dirs, files in os.walk(images_path):
        for file in files:
            # Accept any image file including webp
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heif', '.heic', '.webp')):
                file_path = os.path.join(root, file)
                valid_files.append(os.path.abspath(file_path))
    
    if not valid_files:
        print(f"ERROR: No valid images found in {images_path}")
        return None
        
    print(f"Found {len(valid_files)} valid images:")
    for file in valid_files:
        print(f"  - {file}")
        
    return '\n'.join(valid_files)

def input_file_add_files(driver, selector, files):
    """
    Add files to an input element without unnecessary checks.
    """
    if not files:
        print("No valid files provided for upload")
        return False
        
    try:
        # Wait for input file element to be present
        input_file = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        print("Found file input element")
    except Exception as e:
        print(f'ERROR: Could not find file input element')
        return False

    time.sleep(2)

    try:
        print("Attempting to upload files...")
        input_file.send_keys(files)
        print("Files sent successfully")
        time.sleep(3)  # Wait for upload to complete
        return True
        
    except Exception as e:
        print(f'ERROR: Failed to send files to input')
        return False

def close_chrome():
    import os
    try:
        os.system("taskkill /im chrome.exe /f")
    except Exception as e:
        print(f"Warning: Could not close Chrome: {e}")

## Main script
list_of_profiles = get_file_data("selected_profiles.txt")
df = pd.read_csv('selected_listings.csv')

for single_profile in list_of_profiles:
    path, location_of_profile, user_name = single_profile.strip().split('|')
    profile_name = os.path.basename(path)
    user_data_dir = os.path.dirname(path)
    
    print(f"CHROME PROFILE NAME: {profile_name} ({user_name})")
    print("LOCATION: ", location_of_profile)

    close_chrome()
    time.sleep(5)  # Wait for Chrome to fully close

    options = Options()
    options.add_argument(f"user-data-dir={user_data_dir}")
    options.add_argument(f"profile-directory={profile_name}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')

    service = Service(executable_path=r"C:\WebDrivers\chromedriver.exe")  # Adjust this path
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    print(df)
    for index, single_row in df.iterrows():
        print(f"Processing listing {index + 1}")

        try:
            # Navigate to the Marketplace create vehicle page
            driver.get("https://www.facebook.com/marketplace/create/vehicle")
            time.sleep(4)

            # Vehicle Type
            specific_clicker(driver, "//span[text()='Vehicle type']")
            specific_clicker(driver, f"//span[contains(text(), 'Car/')]")

            # # ADD IMAGES
            # images_path = single_row['Images Path']
            # # Click on Add Photos
            # try:
            #     add_photos_button = WebDriverWait(driver, 10).until(
            #         EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Add photos')]"))
            #     )
            #     add_photos_button.click()
            #     time.sleep(2)  # Short wait for any animations or dialogs to appear
            #     print("Clicked on 'Add Photos' button")
            # except Exception as e:
            #     print(f"Failed to click 'Add Photos' button: {str(e)}")
            
            # pyperclip.copy(images_path)
            # pyautogui.hotkey('ctrl', 'v')
            # pyautogui.press('enter')
            # time.sleep(3)
            # pyautogui.click(x=668, y=319)
            # pyautogui.hotkey('ctrl', 'a')
            # time.sleep(2)
            # pyautogui.press('enter')
            # time.sleep(1)

            # files_list = os.listdir(images_path)
            # full_path_list = [os.path.join(images_path, file) for file in files_list]
            # print(full_path_list)


            # Replace the existing image upload code with:
            try:
                # Generate path string for all images
                images_directory = single_row['Images Path']
                print(f"Looking for images in: {images_directory}")
                image_paths = generate_multiple_images_path(images_directory)
                
                if image_paths:
                    # Upload the images
                    success = input_file_add_files(
                        driver,
                        'input[accept="image/*,image/heif,image/heic"]',
                        image_paths
                    )
                    if not success:
                        print("Failed to upload images, continuing with next listing")
                        continue
                    
                    # Give extra time for upload to complete
                    time.sleep(5)
                else:
                    print("No valid images found, continuing with next listing")
                    continue
                    
            except Exception as e:
                print(f"Unexpected error during image upload: {str(e)}")
                continue
            time.sleep(3)
            # Location
            driver.find_element(By.XPATH, "//span[text()='Location']/../input").send_keys(Keys.CONTROL, "A")
            driver.find_element(By.XPATH, "//span[text()='Location']/../input").send_keys(Keys.DELETE)
            find_element_send_text(driver, "//span[text()='Location']/../input", f'{location_of_profile}')
            specific_clicker(driver, '//ul[@role="listbox"]//li')

            # Year
            year = str(int(single_row['Year']))
            specific_clicker(driver, "//span[text()='Year']")
            time.sleep(1)
            try:
                year_option = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//div[@role='option']//span[text()='{year}']"))
                )
                year_option.click()
            except TimeoutException:
                print(f"Couldn't find year {year} in the dropdown. Trying to input manually.")
                try:
                    year_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//label[text()='Year']/following-sibling::input"))
                    )
                    year_input.clear()
                    year_input.send_keys(year)
                    year_input.send_keys(Keys.RETURN)
                except:
                    print(f"Failed to enter year {year}. Please check the page structure.")
            
            # Make
            make = single_row['Make']
            try:
                driver.find_element(By.XPATH, "//*[text()='Make']/../input")
                find_element_send_text(driver, "//*[text()='Make']/../input", f'{make}')
                time.sleep(1)
            except:
                specific_clicker(driver, "//*[text()='Make']")
                specific_clicker(driver, f"//span[text()='{make}']", f"Make: {make}")

            # Model
            time.sleep(3)
            model = single_row['Model']
            print("Model: ", model)
            try:
                driver.find_element(By.XPATH, "//*[text()='Model']/../div")
                print("Now trying to click")
                specific_clicker(driver, "//*[text()='Model']")
                specific_clicker(driver, f"//span[text()='{model}']", f"Model: {model}")
            except:
                find_element_send_text(driver, "//*[text()='Model']/../input", f'{model}')
                time.sleep(1)

            # Mileage
            mileage = str(int(single_row['Mileage']))
            find_element_send_text(driver, "//*[text()='Mileage']/../input", f'{mileage}')

            # Price
            price = str(int(single_row['Price']))
            find_element_send_text(driver, "//*[text()='Price']/../input", f'{price}')

            # Body Style
            body_style = single_row['Body Style']
            specific_clicker(driver, "//span[text()='Body style']")
            specific_clicker(driver, f"//span[text()='{body_style}']", f"Body Style: {body_style}")

            # Exterior Color
            exterior_color = single_row['Exterior Color']
            specific_clicker(driver, "//span[text()='Exterior color' or text()='Exterior colour']")
            specific_clicker(driver, f"//span[text()='{exterior_color}']", f"Exterior Color: {exterior_color}")

            # Interior Color
            interior_color = single_row['Interior Color']
            specific_clicker(driver, "//span[text()='Interior color' or text()='Interior colour']")
            specific_clicker(driver, f"//span[text()='{interior_color}']", f"Interior Color: {interior_color}")

            # Vehicle Condition
            vehicle_condition = single_row['Vehicle Condition']
            specific_clicker(driver, "//span[text()='Vehicle condition']")
            specific_clicker(driver, f"//span[text()='{vehicle_condition}']", f"Vehicle Condition: {vehicle_condition}")

            # Fuel Type
            fuel_type = single_row['Fuel Type']
            specific_clicker(driver, "//span[text()='Fuel type']")
            specific_clicker(driver, f"//span[text()='{fuel_type}']", f"Fuel Type: {fuel_type}")

            # Transmission
            transmission = single_row['Transmission']
            specific_clicker(driver, "//span[text()='Transmission']")
            specific_clicker(driver, f"//span[text()='{transmission}']", f"Transmission: {transmission}")

            # Clean Title
            specific_clicker(driver, "//span[text()='This vehicle has a clean title.']/../..//label")

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
                
                print("Description entered successfully")
            except Exception as e:
                print(f"Error entering description: {str(e)}")
                
                try:
                    description_textarea = driver.find_element(By.TAG_NAME, "textarea")
                    description_textarea.send_keys(description)
                    print("Description entered using alternative method")
                except Exception as e:
                    print(f"Failed to enter description using alternative method: {str(e)}")
            time.sleep(8)

            # Try to publish
            try:
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@aria-label="Next" and not(@aria-disabled)]'))
                )
                next_button.click()
                print("Clicked 'Next' button")
                time.sleep(2)
            except Exception as e:
                print(f"Error clicking 'Next' button: {str(e)}")

            # Wait for and click the Publish button
            try:
                publish_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@aria-label="Publish"]'))
                )
                publish_button.click()
                print("Clicked 'Publish' button")
                time.sleep(5)
            except Exception as e:
                print(f"Error clicking 'Publish' button: {str(e)}")

            # Wait for the publishing process to complete
            try:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.XPATH, '//*[@aria-label="Publish"]'))
                )
                print("Listing published successfully")
            except TimeoutException:
                print("Publishing process took longer than expected")

            time.sleep(5)  # Short wait before moving to the next listing

        except Exception as e:
            print(f"Error processing listing {index + 1}: {str(e)}")
            driver.save_screenshot(f"error_screenshot_{profile_name}_{index}.png")

        print(f"Completed processing listing {index + 1}")

    driver.quit()
    print(f"Completed all listings for profile: {profile_name}")

print("All profiles and listings completed.")