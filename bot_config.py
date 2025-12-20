"""
Bot Configuration Module
Contains all configuration constants, global state, and status tracking
"""

import os
import json
import signal
import time
from datetime import datetime

# ============================================================================
# PATHS AND CONSTANTS
# ============================================================================

EDGE_DRIVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webdrivers', 'msedgedriver.exe')
SCREENSHOT_FOLDER = 'fbmpss'
STATUS_FILE = 'bot_status.json'
STOP_FILE = 'bot_stop_signal.txt'
TEMP_IMAGES_FOLDER = 'temp_bot_images'

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
# CONFIGURATION LOADING
# ============================================================================

def load_bot_config():
    """Load bot configuration from file"""
    delays = DEFAULT_DELAYS.copy()
    max_groups = 20  # Default value
    headless_mode = False
    auto_retry = False
    max_retries = 2

    if os.path.exists('bot_config.json'):
        try:
            with open('bot_config.json', 'r') as f:
                config = json.load(f)
                
                # Load delays
                delays.update(config.get('delays', {}))
                
                # Load other settings
                max_groups = config.get('max_groups', 20)
                headless_mode = config.get('headless', False)
                auto_retry = config.get('auto_retry', False)
                max_retries = config.get('max_retries', 2)
                
                print("📋 Loaded custom configuration")
                print(f"  ⚙️  Max Groups: {max_groups}")
                print(f"  ⚙️  Auto Retry: {auto_retry}")
                print(f"  ⚙️  Max Retries: {max_retries}")
        except Exception as e:
            print(f"⚠️ Could not load config: {e}")
            print("  Using default settings")
    
    return {
        'delays': delays,
        'max_groups': max_groups,
        'headless_mode': headless_mode,
        'auto_retry': auto_retry,
        'max_retries': max_retries
    }
