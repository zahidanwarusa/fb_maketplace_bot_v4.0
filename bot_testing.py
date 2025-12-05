import os
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


class FacebookBot:
    def __init__(self, profile_name="Profile 6"):
        """Initialize the Facebook bot with Edge profile settings"""
        self.profile_name = profile_name
        self.driver = None
        
        # Get the directory where this script is located
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Edge user data path using environment variable
        self.user_data_dir = os.path.join(
            os.environ["LOCALAPPDATA"],
            "Microsoft", "Edge", "User Data"
        )
        
        # Edge driver path - in webdrivers folder
        self.driver_path = os.path.join(self.script_dir, "webdrivers", "msedgedriver.exe")
        
        # Verify driver exists
        if not os.path.exists(self.driver_path):
            raise FileNotFoundError(
                f"Edge driver not found at: {self.driver_path}\n"
                f"Please place msedgedriver.exe in the 'webdrivers' folder"
            )

    def setup_driver(self):
        """Setup Edge WebDriver with the specified profile"""
        try:
            edge_options = Options()
            
            # Set profile paths
            edge_options.add_argument(f"--user-data-dir={self.user_data_dir}")
            edge_options.add_argument(f"--profile-directory={self.profile_name}")
            
            # Additional options
            edge_options.add_argument("--start-maximized")
            edge_options.add_argument("--disable-blink-features=AutomationControlled")
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option("useAutomationExtension", False)
            
            # Create service with driver path
            print(f"Using Edge driver from: {self.driver_path}")
            service = Service(executable_path=self.driver_path)
            self.driver = webdriver.Edge(service=service, options=edge_options)
            
            return True
            
        except WebDriverException as e:
            print(f"Error setting up Edge driver: {e}")
            return False

    def check_facebook_login(self):
        """Check if user is logged into Facebook"""
        try:
            print("Navigating to Facebook...")
            self.driver.get("https://www.facebook.com")
            
            # Wait for page to load
            time.sleep(4)
            
            # Get current URL
            current_url = self.driver.current_url.lower()
            
            # Check if redirected to login page
            if "login" in current_url or "checkpoint" in current_url:
                return False
            
            # Check for login form elements (indicates NOT logged in)
            login_elements = [
                (By.ID, "email"),
                (By.ID, "pass"),
                (By.CSS_SELECTOR, "button[name='login']"),
                (By.CSS_SELECTOR, "[data-testid='royal_login_button']")
            ]
            
            for locator in login_elements:
                try:
                    element = self.driver.find_element(*locator)
                    if element.is_displayed():
                        return False
                except:
                    continue
            
            # Check for logged-in elements
            logged_in_elements = [
                (By.CSS_SELECTOR, "[aria-label='Home']"),
                (By.CSS_SELECTOR, "[aria-label='Your profile']"),
                (By.CSS_SELECTOR, "[role='feed']"),
                (By.CSS_SELECTOR, "[aria-label='Create a post']"),
                (By.CSS_SELECTOR, "[aria-label='Account Controls and Settings']"),
                (By.XPATH, "//span[contains(text(),'Create post')]"),
            ]
            
            for locator in logged_in_elements:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located(locator)
                    )
                    return True
                except TimeoutException:
                    continue
            
            # Final check - if no login form and page loaded, assume logged in
            page_source = self.driver.page_source.lower()
            if "create a post" in page_source or "what's on your mind" in page_source:
                return True
                
            return False
            
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False

    def goto_home_page(self):
        """Navigate to Facebook home page"""
        try:
            self.driver.get("https://www.facebook.com/")
            
            # Wait for feed to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
            )
            
            print("Successfully loaded Facebook home page")
            return True
            
        except Exception as e:
            print(f"Error going to home page: {e}")
            return False

    def goto_marketplace(self):
        """Navigate to Facebook Marketplace"""
        try:
            print("Navigating to Marketplace...")
            self.driver.get("https://www.facebook.com/marketplace/")
            
            # Wait for marketplace to load - look for common marketplace elements
            marketplace_loaded = False
            
            # Try multiple selectors for marketplace
            marketplace_selectors = [
                (By.CSS_SELECTOR, "[role='main']"),
                (By.XPATH, "//span[contains(text(),'Marketplace')]"),
                (By.CSS_SELECTOR, "[aria-label='Marketplace']"),
                (By.XPATH, "//span[contains(text(),'Browse all')]"),
                (By.XPATH, "//span[contains(text(),'Categories')]"),
                (By.XPATH, "//span[contains(text(),'Today')]"),
            ]
            
            for locator in marketplace_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(locator)
                    )
                    marketplace_loaded = True
                    break
                except TimeoutException:
                    continue
            
            # Additional check via URL
            time.sleep(2)
            if "marketplace" in self.driver.current_url.lower():
                marketplace_loaded = True
            
            if marketplace_loaded:
                print("✓ Successfully loaded Facebook Marketplace")
                return True
            else:
                print("Warning: Marketplace may not have loaded correctly")
                return False
            
        except Exception as e:
            print(f"Error navigating to Marketplace: {e}")
            return False

    def click_create_new_listing(self):
        """Click on 'Create new listing' button in Marketplace"""
        try:
            print("Looking for 'Create new listing' button...")
            
            # Various selectors for the create listing button
            create_listing_selectors = [
                # Text-based selectors
                (By.XPATH, "//span[contains(text(),'Create new listing')]"),
                (By.XPATH, "//span[contains(text(),'Create New Listing')]"),
                (By.XPATH, "//span[text()='Create new listing']"),
                (By.XPATH, "//*[contains(text(),'Create new listing')]"),
                # Aria-label selectors
                (By.CSS_SELECTOR, "[aria-label='Create new listing']"),
                (By.CSS_SELECTOR, "[aria-label='Create a listing']"),
                # Link-based selectors
                (By.XPATH, "//a[contains(@href, '/marketplace/create')]"),
                (By.CSS_SELECTOR, "a[href*='/marketplace/create']"),
                # Button with plus icon often used
                (By.XPATH, "//div[contains(@aria-label,'Create')]//span[contains(text(),'listing')]"),
                # Sell button variant
                (By.XPATH, "//span[contains(text(),'Sell')]"),
                (By.CSS_SELECTOR, "[aria-label='Sell']"),
            ]
            
            for locator in create_listing_selectors:
                try:
                    # Wait for element to be clickable
                    element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(locator)
                    )
                    
                    # Scroll element into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.5)
                    
                    # Click the element
                    element.click()
                    print("✓ Clicked on 'Create new listing' button")
                    
                    # Wait for the listing form/options to appear
                    time.sleep(2)
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    continue
            
            # If direct click didn't work, try JavaScript click
            print("Trying alternative click method...")
            for locator in create_listing_selectors:
                try:
                    element = self.driver.find_element(*locator)
                    self.driver.execute_script("arguments[0].click();", element)
                    print("✓ Clicked on 'Create new listing' button (JS click)")
                    time.sleep(2)
                    return True
                except:
                    continue
            
            print("✗ Could not find 'Create new listing' button")
            return False
            
        except Exception as e:
            print(f"Error clicking create new listing: {e}")
            return False

    def click_vehicle_for_sale(self):
        """Click on 'Vehicle for sale' option after create new listing"""
        try:
            print("Looking for 'Vehicle for sale' option...")
            
            # Various selectors for vehicle for sale option
            vehicle_selectors = [
                # Text-based selectors
                (By.XPATH, "//span[contains(text(),'Vehicle for sale')]"),
                (By.XPATH, "//span[contains(text(),'Vehicles')]"),
                (By.XPATH, "//span[text()='Vehicle for sale']"),
                (By.XPATH, "//*[contains(text(),'Vehicle for sale')]"),
                # Aria-label selectors
                (By.CSS_SELECTOR, "[aria-label='Vehicle for sale']"),
                (By.CSS_SELECTOR, "[aria-label='Vehicles']"),
                # Link-based selectors
                (By.XPATH, "//a[contains(@href, 'vehicle')]"),
                # Combination selectors with parent divs
                (By.XPATH, "//div[contains(@role,'button')]//span[contains(text(),'Vehicle')]"),
                (By.XPATH, "//div[@role='button']//span[contains(text(),'Vehicle for sale')]"),
                # Generic item selector in listing creation dialog
                (By.XPATH, "//div[contains(@aria-label,'listing')]//span[contains(text(),'Vehicle')]"),
                # Case insensitive text search
                (By.XPATH, "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'vehicle')]"),
            ]
            
            for locator in vehicle_selectors:
                try:
                    # Wait for element to be clickable
                    element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(locator)
                    )
                    
                    # Scroll element into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.5)
                    
                    # Click the element
                    element.click()
                    print("✓ Clicked on 'Vehicle for sale' option")
                    
                    # Wait for the vehicle listing form to appear
                    time.sleep(3)
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    continue
            
            # If direct click didn't work, try JavaScript click
            print("Trying alternative click method...")
            for locator in vehicle_selectors:
                try:
                    element = self.driver.find_element(*locator)
                    self.driver.execute_script("arguments[0].click();", element)
                    print("✓ Clicked on 'Vehicle for sale' option (JS click)")
                    time.sleep(3)
                    return True
                except:
                    continue
            
            print("✗ Could not find 'Vehicle for sale' option")
            print("Tip: Make sure the listing creation menu is open")
            return False
            
        except Exception as e:
            print(f"Error clicking vehicle for sale: {e}")
            return False

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")

    def list_available_profiles(self):
        """List all available Edge profiles"""
        print(f"\nEdge User Data Directory: {self.user_data_dir}")
        print("\nAvailable profiles:")
        
        if os.path.exists(self.user_data_dir):
            for item in os.listdir(self.user_data_dir):
                item_path = os.path.join(self.user_data_dir, item)
                if os.path.isdir(item_path):
                    if item.startswith("Profile") or item == "Default":
                        print(f"  - {item}")
        else:
            print("  Edge User Data directory not found!")


def main():
    # Initialize bot with profile name
    bot = FacebookBot(profile_name="Profile 6")
    
    # Show available profiles
    bot.list_available_profiles()
    
    print("\n" + "="*50)
    print("IMPORTANT: Close all Edge browser windows first!")
    print("="*50 + "\n")
    
    input("Press Enter to continue...")
    
    try:
        # Setup the browser
        print("\nStarting Edge browser...")
        if not bot.setup_driver():
            print("Failed to setup Edge driver. Exiting.")
            return
        
        # Check login status
        print("\nChecking Facebook login status...")
        is_logged_in = bot.check_facebook_login()
        
        if is_logged_in:
            print("\n" + "="*50)
            print("✓ SUCCESS: Facebook account is LOGGED IN")
            print("="*50)
            
            # Navigate to Marketplace
            print("\nNavigating to Marketplace...")
            if bot.goto_marketplace():
                # Click on Create new listing
                time.sleep(2)  # Give page time to fully load
                if bot.click_create_new_listing():
                    # Click on Vehicle for sale
                    time.sleep(2)  # Wait for menu to appear
                    bot.click_vehicle_for_sale()
            
            print("\nBrowser will remain open. Press Enter to close...")
            input()
            
        else:
            print("\n" + "="*50)
            print("✗ Facebook account is NOT LOGGED IN")
            print("="*50)
            print("\nYou can log in manually now.")
            print("Press Enter when done to close the browser...")
            input()
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        
    finally:
        bot.close()


if __name__ == "__main__":
    main()