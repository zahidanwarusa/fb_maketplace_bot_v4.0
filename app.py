"""
Facebook Marketplace Automation - Main Application
This is the main entry point that initializes Flask and registers all component routes
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
try:
    load_dotenv()
    logger.info("Environment variables loaded successfully")
except Exception as e:
    logger.error(f"Failed to load environment variables: {str(e)}")
    raise

# ============================================================================
# CONFIGURATION
# ============================================================================

UPLOAD_FOLDER = 'temp_uploads'
MAX_PROFILE_SELECTION = 5  # Maximum number of profiles that can be selected

# Create upload folder if it doesn't exist
try:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        logger.info(f"Created upload folder: {UPLOAD_FOLDER}")
except Exception as e:
    logger.error(f"Failed to create upload folder: {str(e)}")
    raise

# ============================================================================
# INITIALIZE FLASK APP
# ============================================================================

app = Flask(__name__)

# ============================================================================
# INITIALIZE SUPABASE CLIENT
# ============================================================================

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    error_msg = "Missing Supabase credentials. Please check .env file."
    logger.error(error_msg)
    print("=" * 60)
    print("⚠️  WARNING: Supabase credentials not found!")
    print("=" * 60)
    print("Please create a .env file with:")
    print("SUPABASE_URL=your_supabase_url")
    print("SUPABASE_KEY=your_supabase_key")
    print("=" * 60)
    raise ValueError(error_msg)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    raise

# ============================================================================
# IMPORT EXTERNAL MODULES
# ============================================================================

from google_drive_manager import get_drive_manager
from facebook_account_detector import get_facebook_accounts_from_profile

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_profile_locations_dict(supabase_client):
    """Get all profile locations from Supabase as a dictionary with error handling"""
    try:
        response = supabase_client.table('profile_locations').select('*').execute()
        locations = {item['profile_name']: item['location'] for item in response.data}
        logger.info(f"Retrieved {len(locations)} profile locations from Supabase")
        return locations
    except Exception as e:
        logger.error(f"Error fetching profile locations: {str(e)}")
        logger.error(traceback.format_exc())
        return {}


def test_supabase_connection():
    """Test the Supabase connection on startup with comprehensive error handling"""
    try:
        print("\n" + "=" * 60)
        print("Testing Supabase Connection...")
        print("=" * 60)
        
        # Test listings table
        try:
            response = supabase.table('listings').select('id', count='exact').execute()
            listings_count = response.count
            print(f"✓ Connected to Supabase successfully!")
            print(f"✓ Found {listings_count} listings in database")
        except Exception as e:
            logger.error(f"Failed to query listings table: {str(e)}")
            raise
        
        # Test profile_locations table
        try:
            response = supabase.table('profile_locations').select('id', count='exact').execute()
            profiles_count = response.count
            print(f"✓ Found {profiles_count} profile locations in database")
        except Exception as e:
            logger.error(f"Failed to query profile_locations table: {str(e)}")
            raise
        
        # Test upload_history table (optional - won't fail if doesn't exist)
        try:
            response = supabase.table('upload_history').select('id', count='exact').execute()
            uploads_count = response.count
            print(f"✓ Found {uploads_count} upload records in database")
        except Exception as e:
            print(f"ℹ️  Upload history table not found (run schema if you want tracking)")
            logger.warning(f"Upload history table not accessible: {str(e)}")
        
        print("=" * 60 + "\n")
        logger.info("Supabase connection test completed successfully")
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ ERROR: Could not connect to Supabase!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print("\nPlease check:")
        print("1. Your .env file exists with correct credentials")
        print("2. SUPABASE_URL and SUPABASE_KEY are correct")
        print("3. Tables 'listings' and 'profile_locations' exist")
        print("4. You ran the migration script or SQL schema")
        print("=" * 60 + "\n")
        logger.error(f"Supabase connection test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# ============================================================================
# IMPORT AND INITIALIZE COMPONENT ROUTES
# ============================================================================

from components.dashboard import init_dashboard_routes
from components.profiles import init_profiles_routes
from components.listings import init_listings_routes
from components.media import init_media_routes
from components.history import init_history_routes
from components.deleted import init_deleted_routes
from components.schedule import init_schedule_routes
from components.bot import init_bot_routes

# Initialize all component routes
init_dashboard_routes(app, supabase, MAX_PROFILE_SELECTION, get_facebook_accounts_from_profile)
init_profiles_routes(app, supabase)
init_listings_routes(app, supabase)
init_media_routes(app, get_drive_manager)
init_history_routes(app, supabase)
init_deleted_routes(app, supabase)
init_schedule_routes(app, supabase)
init_bot_routes(app, supabase, MAX_PROFILE_SELECTION, get_profile_locations_dict)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"404 error: {error}")
    return jsonify({
        'status': 'error',
        'message': 'Resource not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"500 error: {str(error)}")
    logger.error(traceback.format_exc())
    return jsonify({
        'status': 'error',
        'message': 'Internal server error. Please check server logs.'
    }), 500


@app.errorhandler(Exception)
def handle_exception(error):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(error)}")
    logger.error(traceback.format_exc())
    return jsonify({
        'status': 'error',
        'message': 'An unexpected error occurred. Please check server logs.'
    }), 500

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    try:
        # Test connection before starting
        if test_supabase_connection():
            print("🚀 Starting Flask application...")
            print("🌐 Open http://localhost:5000 in your browser")
            print(f"⚙️  Maximum profile selection: {MAX_PROFILE_SELECTION}")
            print("\n")
            logger.info("Application starting successfully")
            app.run(debug=True, host='0.0.0.0', port=5000)
        else:
            print("⚠️  Application cannot start without Supabase connection.")
            print("Please fix the errors above and try again.")
            logger.error("Application startup failed: Supabase connection test failed")
    except Exception as e:
        print(f"\n✗ Critical error during startup: {str(e)}")
        logger.error(f"Critical startup error: {str(e)}")
        logger.error(traceback.format_exc())
