"""
Edge Driver Test Script
Tests if Edge WebDriver can launch with your profile configuration
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import WebDriverException
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Supabase credentials not found in .env file")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Edge driver path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EDGE_DRIVER_PATH = os.path.join(SCRIPT_DIR, 'webdrivers', 'msedgedriver.exe')

print("=" * 70)
print("🧪 EDGE DRIVER TEST")
print("=" * 70)

# Check if Edge driver exists
print(f"\n📋 Checking Edge WebDriver...")
print(f"   Path: {EDGE_DRIVER_PATH}")
if os.path.exists(EDGE_DRIVER_PATH):
    print(f"   Status: ✓ Found")
else:
    print(f"   Status: ✗ Not found!")
    print(f"\n❌ ERROR: Edge WebDriver not found!")
    print(f"   Please ensure msedgedriver.exe is in the 'webdrivers' folder")
    sys.exit(1)

# Get profiles from database
print(f"\n📊 Fetching profiles from database...")
try:
    response = supabase.table('edge_profiles').select('*').is_('deleted_at', 'null').eq('is_active', True).execute()
    profiles = response.data
    
    if not profiles:
        print(f"   ⚠️  No active profiles found!")
        sys.exit(1)
    
    print(f"   ✓ Found {len(profiles)} active profile(s)")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test each profile
for idx, profile in enumerate(profiles, 1):
    print(f"\n{'=' * 70}")
    print(f"Testing Profile {idx}/{len(profiles)}: {profile['profile_name']}")
    print(f"{'=' * 70}")
    
    profile_path = profile.get('profile_path', '')
    if not profile_path:
        print("❌ Profile path is empty!")
        continue
    
    print(f"Profile Path: {profile_path}")
    
    # Extract profile name and user data dir (exactly how Bot.py does it)
    profile_name = os.path.basename(profile_path)
    user_data_dir = os.path.dirname(profile_path)
    
    print(f"\nExtracted values:")
    print(f"  • profile_name: {profile_name}")
    print(f"  • user_data_dir: {user_data_dir}")
    
    # Verify paths exist
    print(f"\nPath validation:")
    print(f"  • Profile path exists: {'✓' if os.path.exists(profile_path) else '✗'}")
    print(f"  • User Data Dir exists: {'✓' if os.path.exists(user_data_dir) else '✗'}")
    
    if not os.path.exists(profile_path):
        print(f"\n❌ Profile path does not exist! Skipping...")
        continue
    
    if not os.path.exists(user_data_dir):
        print(f"\n❌ User Data directory does not exist! Skipping...")
        continue
    
    # Try to launch Edge
    print(f"\n🚀 Attempting to launch Edge browser...")
    print(f"   (This may take 10-15 seconds...)")
    
    driver = None
    try:
        # Setup options exactly like Bot.py does
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
        
        # Create service
        service = Service(executable_path=EDGE_DRIVER_PATH)
        
        # Launch driver
        driver = webdriver.Edge(service=service, options=options)
        
        print(f"   ✅ SUCCESS! Browser launched successfully!")
        
        # Try to navigate to a page
        print(f"\n📄 Testing navigation...")
        driver.get("https://www.facebook.com")
        time.sleep(3)
        
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        print(f"   ✓ Navigation works!")
        
        print(f"\n✅ All tests passed for this profile!")
        
        # Keep browser open for user to see
        print(f"\n⏸️  Browser will stay open for 10 seconds for you to verify...")
        time.sleep(10)
        
    except WebDriverException as e:
        print(f"\n❌ FAILED to launch browser!")
        print(f"\nError details:")
        print(f"{str(e)}")
        
        # Provide troubleshooting tips
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Make sure ALL Edge browser windows are closed")
        print(f"   2. Verify the profile path is correct in the database")
        print(f"   3. Check if another program is using port 9222")
        print(f"   4. Try restarting your computer")
        print(f"   5. Make sure Edge browser is updated")
        
        if "OneDrive" in profile_path:
            print(f"   6. ⚠️  OneDrive detected in path - this can cause issues!")
            print(f"       Consider using a profile outside OneDrive sync")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    finally:
        if driver:
            try:
                driver.quit()
                print(f"\n🧹 Browser closed")
            except:
                pass
    
    # If multiple profiles, ask before continuing
    if idx < len(profiles):
        input(f"\nPress Enter to test next profile...")

print(f"\n{'=' * 70}")
print("✅ TESTING COMPLETE")
print(f"{'=' * 70}")
