"""
Enhanced Facebook Marketplace Bot - Main Entry Point
Features: Stop functionality, real-time progress, configurable delays, screenshot saving
Updated: Google Drive image download support
Browser: Microsoft Edge (msedgedriver.exe)

IMPORTANT: Make sure your CSV data has matching Make/Model combinations!
Examples of valid combinations:
  - Honda -> Civic, Accord, CR-V
  - Acura -> ILX, TLX, MDX, RDX
  - Toyota -> Camry, Corolla, RAV4
If Model not found for the Make, bot will automatically select "Other"
"""

import os
import sys
import time
import signal
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import WebDriverException

# Import our modular components
import bot_config
from bot_config import (
    EDGE_DRIVER_PATH, SCREENSHOT_FOLDER,
    signal_handler, check_stop_signal, cleanup_stop_signal,
    update_status, get_progress_info, load_bot_config
)
from bot_helpers import (
    ensure_screenshot_folder, get_file_data,
    close_chrome, close_edge
)
from bot_drive import cleanup_temp_images
from bot_processor import process_single_listing


# ============================================================================
# MAIN BOT EXECUTION
# ============================================================================

def run_bot():
    """Main bot execution function"""
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Cleanup any existing stop signal
    cleanup_stop_signal()
    
    # Ensure screenshot folder exists
    ensure_screenshot_folder()
    
    # Load configuration
    config = load_bot_config()
    delays = config['delays']
    max_groups = config['max_groups']
    headless_mode = config['headless_mode']
    auto_retry = config['auto_retry']
    max_retries = config['max_retries']
    
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
    print(f"\n⚙️  SETTINGS:")
    print(f"   Max Groups: {max_groups}")
    if auto_retry:
        print(f"   🔄 Auto-Retry: ENABLED (Max Retries: {max_retries})")
    else:
        print(f"   🔄 Auto-Retry: DISABLED")
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
        
        # Close existing browsers
        close_chrome()  # Disabled - keeps dashboard alive
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
        
        if headless_mode:
            options.add_argument('--headless')
        
        try:
            # Use Edge WebDriver with explicit path
            service = Service(executable_path=EDGE_DRIVER_PATH)
            driver = webdriver.Edge(service=service, options=options)
            bot_config.current_driver = driver
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
            
            # Retry logic
            retry_attempt = 0
            max_attempts = (max_retries + 1) if auto_retry else 1
            success = False
            message = ""
            
            while retry_attempt < max_attempts:
                if check_stop_signal():
                    success = False
                    message = "Stopped by user"
                    break
                
                # Show retry status if this is a retry attempt
                if retry_attempt > 0:
                    print(f"\n🔄 RETRY ATTEMPT {retry_attempt}/{max_retries} for: {listing_info}")
                    update_status('retrying', f'Retry {retry_attempt}/{max_retries}: {listing_info}',
                                  current_profile=user_name,
                                  current_listing=listing_info,
                                  retry_attempt=retry_attempt,
                                  max_retries=max_retries,
                                  progress=progress)
                    
                    # Check if browser is still valid before retrying
                    browser_valid = False
                    try:
                        # Try a simple operation to check if driver is alive
                        driver.current_url
                        browser_valid = True
                    except Exception as e:
                        print(f"  ⚠️ Browser session invalid, restarting browser...")
                        browser_valid = False
                    
                    # Restart browser if needed
                    if not browser_valid:
                        try:
                            driver.quit()
                        except:
                            pass
                        
                        # Wait a moment before restarting
                        time.sleep(2)
                        
                        # Restart browser
                        try:
                            print(f"  🔄 Launching new browser session...")
                            service = Service(executable_path=EDGE_DRIVER_PATH)
                            driver = webdriver.Edge(service=service, options=options)
                            bot_config.current_driver = driver
                            driver.maximize_window()
                            print(f"  ✓ New browser session started")
                            time.sleep(2)
                        except Exception as e:
                            print(f"  ❌ Failed to restart browser: {e}")
                            success = False
                            message = f"Failed to restart browser: {str(e)[:50]}"
                            break  # Can't retry without a browser
                
                try:
                    success, message = process_single_listing(
                        driver, single_row, location_of_profile, 
                        user_name, listing_idx, delays, max_groups
                    )
                except Exception as e:
                    # If process_single_listing fails catastrophically
                    error_str = str(e)
                    print(f"  ❌ Critical error in process_single_listing: {error_str[:100]}")
                    success = False
                    message = f"Critical error: {error_str[:100]}"
                    
                    # Check if this is a browser session error
                    if "invalid session" in error_str.lower() or "no such window" in error_str.lower():
                        print(f"  ⚠️ Browser session lost during processing")
                
                # Check if we succeeded or should retry
                if success:
                    if retry_attempt > 0:
                        print(f"  ✅ SUCCESS on retry attempt {retry_attempt}!")
                    break  # Success - exit retry loop
                else:
                    # Failed - check if we should retry
                    if auto_retry and retry_attempt < max_retries:
                        retry_attempt += 1
                        retry_delay = delays.get('between_listings', 5)
                        print(f"  ⚠️ Attempt failed: {message[:100]}")
                        print(f"  🔄 Will retry in {retry_delay} seconds... ({retry_attempt}/{max_retries})")
                        time.sleep(retry_delay)
                        # Continue to next retry attempt
                    else:
                        # No more retries available
                        if auto_retry and retry_attempt >= max_retries:
                            print(f"  ❌ Failed after {max_retries} retry attempt(s)")
                        break  # Exit retry loop
            
            # Record result (after all retry attempts)
            final_status = 'success' if success else ('skipped' if message == "Stopped by user" else 'failed')
            results['details'].append({
                'profile': user_name,
                'listing': listing_info,
                'status': final_status,
                'message': message,
                'retry_attempts': retry_attempt
            })
            
            if success:
                results['success'] += 1
                if retry_attempt > 0:
                    print(f"  ✅ Listing {listing_idx + 1} completed successfully (after {retry_attempt} retry attempt(s))")
                else:
                    print(f"  ✅ Listing {listing_idx + 1} completed successfully")
            else:
                if message == "Stopped by user":
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                    if auto_retry:
                        print(f"  ❌ Listing {listing_idx + 1} failed after {retry_attempt} retry attempt(s): {message}")
                    else:
                        print(f"  ❌ Listing {listing_idx + 1} failed: {message}")
            
            # Delay between listings
            if listing_idx < len(df) - 1 and not check_stop_signal():
                delay = delays.get('between_listings', 5)
                print(f"  ⏳ Waiting {delay}s before next listing...")
                time.sleep(delay)
        
        # Close browser after profile
        try:
            driver.quit()
            bot_config.current_driver = None
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
    
    # Calculate retry statistics
    retry_stats = {
        'total_retried': 0,
        'succeeded_on_retry': 0,
        'failed_after_retry': 0
    }
    
    if auto_retry:
        for detail in results['details']:
            if detail.get('retry_attempts', 0) > 0:
                retry_stats['total_retried'] += 1
                if detail['status'] == 'success':
                    retry_stats['succeeded_on_retry'] += 1
                else:
                    retry_stats['failed_after_retry'] += 1
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"🏁 BOT EXECUTION COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️ Skipped: {results['skipped']}")
    
    # Show retry statistics if auto-retry was enabled
    if auto_retry and retry_stats['total_retried'] > 0:
        print(f"\n🔄 RETRY STATISTICS:")
        print(f"   Total listings retried: {retry_stats['total_retried']}")
        print(f"   ✅ Succeeded after retry: {retry_stats['succeeded_on_retry']}")
        print(f"   ❌ Failed after retry: {retry_stats['failed_after_retry']}")
    
    print(f"\n📁 Screenshots saved to: {SCREENSHOT_FOLDER}/")
    print(f"{'='*60}\n")
    
    final_status = 'completed' if not bot_config.bot_should_stop else 'stopped'
    update_status(final_status, 'Bot execution finished', 
                  results=results,
                  retry_stats=retry_stats,
                  progress=100 if not bot_config.bot_should_stop else get_progress_info(profile_idx, total_profiles, listing_idx, total_listings))
    
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
        if bot_config.current_driver:
            try:
                bot_config.current_driver.quit()
            except:
                pass
        cleanup_stop_signal()
        cleanup_temp_images()