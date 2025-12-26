"""
Facebook Marketplace Automation - Main Application
Enhanced with Stop functionality, Progress tracking, and Screenshot management
"""

from flask import Flask, jsonify
import os
import sys
import logging
import traceback
from supabase import create_client, Client
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
MAX_LISTING_SELECTION = 5  # Changed from MAX_PROFILE_SELECTION - now limits listings instead of profiles

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize Flask app
app = Flask(__name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials")
    print("=" * 60)
    print("WARNING: Supabase credentials not found!")
    print("Please create a .env file with:")
    print("SUPABASE_URL=your_supabase_url")
    print("SUPABASE_KEY=your_supabase_key")
    print("=" * 60)
    raise ValueError("Missing Supabase credentials")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Supabase: {str(e)}")
    raise

# Import external modules
from google_drive_manager import get_drive_manager
from facebook_account_detector import get_facebook_accounts_from_profile

# Helper functions
def get_profile_locations_dict(supabase_client):
    try:
        response = supabase_client.table('profile_locations').select('*').execute()
        return {item['profile_name']: item['location'] for item in response.data}
    except Exception as e:
        logger.error(f"Error fetching profile locations: {str(e)}")
        return {}


def test_supabase_connection():
    try:
        print("\n" + "=" * 60)
        print("Testing Supabase Connection...")
        print("=" * 60)
        
        response = supabase.table('listings').select('id', count='exact').execute()
        print(f"✓ Connected to Supabase!")
        print(f"✓ Found {response.count} listings")
        
        response = supabase.table('profile_locations').select('id', count='exact').execute()
        print(f"✓ Found {response.count} profile locations")
        
        print("=" * 60 + "\n")
        return True
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ Could not connect to Supabase!")
        print(f"Error: {str(e)}")
        print("=" * 60 + "\n")
        return False


# Import and initialize component routes
from components.dashboard import init_dashboard_routes
from components.profiles import init_profiles_routes
from components.listings import init_listings_routes
from components.media import init_media_routes
from components.history import init_history_routes
from components.deleted import init_deleted_routes
from components.schedule import init_schedule_routes
from components.bot import init_bot_routes

# Initialize all component routes
init_dashboard_routes(app, supabase, MAX_LISTING_SELECTION, get_facebook_accounts_from_profile)
init_profiles_routes(app, supabase)
init_listings_routes(app, supabase)
init_media_routes(app, get_drive_manager)
init_history_routes(app, supabase)
init_deleted_routes(app, supabase)
init_schedule_routes(app, supabase)
init_bot_routes(app, supabase, MAX_LISTING_SELECTION, get_profile_locations_dict)


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {str(error)}")
    return jsonify({'status': 'error', 'message': 'An unexpected error occurred'}), 500


if __name__ == '__main__':
    try:
        if test_supabase_connection():
            print("🚀 Starting Flask application...")
            print("🌐 Open http://localhost:5001 in your browser")
            print(f"⚙️  Maximum listing selection: {MAX_LISTING_SELECTION}")
            print("\n")
            app.run(debug=True, host='0.0.0.0', port=5001)
        else:
            print("⚠️  Application cannot start without Supabase connection.")
    except Exception as e:
        print(f"\n✗ Critical error during startup: {str(e)}")
        logger.error(f"Critical startup error: {str(e)}")
