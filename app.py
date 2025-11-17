from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os
import glob
import json
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import csv
import io
from werkzeug.utils import secure_filename
from google_drive_manager import get_drive_manager
import traceback
import logging
from facebook_account_detector import get_facebook_accounts_from_profile, get_facebook_login_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
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

# Configuration constants
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'mp4', 'avi', 'mov', 'zip'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_PROFILE_SELECTION = 5  # Maximum number of profiles that can be selected

# Create upload folder if it doesn't exist
try:
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        logger.info(f"Created upload folder: {UPLOAD_FOLDER}")
except Exception as e:
    logger.error(f"Failed to create upload folder: {str(e)}")
    raise

# Initialize Flask app
app = Flask(__name__)

# Initialize Supabase client
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
# HELPER FUNCTIONS
# ============================================================================

def get_chrome_profiles():
    """Get all Chrome profiles from the system with Facebook account information"""
    try:
        user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
        profiles = []
        
        if not os.path.exists(user_data_dir):
            logger.warning(f"Chrome user data directory not found: {user_data_dir}")
            return profiles
        
        # Read the Local State file to get profile names
        try:
            local_state_path = os.path.join(user_data_dir, 'Local State')
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)
                profile_info = local_state.get('profile', {}).get('info_cache', {})
        except Exception as e:
            logger.error(f"Failed to read Chrome profiles: {str(e)}")
            profile_info = {}

        # Get all profile directories
        try:
            profile_dirs = glob.glob(os.path.join(user_data_dir, 'Profile *'))
            profile_dirs.append(os.path.join(user_data_dir, 'Default'))
        except Exception as e:
            logger.error(f"Failed to get profile directories: {str(e)}")
            return profiles

        # Get locations from Supabase
        profile_locations = get_profile_locations_dict()

        for profile_dir in profile_dirs:
            try:
                if os.path.exists(profile_dir):
                    folder_name = os.path.basename(profile_dir)
                    profile_id = folder_name if folder_name != 'Default' else 'Default'
                    user_name = profile_info.get(profile_id, {}).get('name', 'Unknown')
                    
                    # Get location for this profile from Supabase
                    location = profile_locations.get(folder_name, '')
                    
                    # Get Facebook accounts for this profile
                    facebook_accounts = []
                    try:
                        facebook_accounts = get_facebook_accounts_from_profile(profile_dir)
                    except Exception as e:
                        logger.error(f"Error getting Facebook accounts for {folder_name}: {e}")
                    
                    profiles.append({
                        'folder_name': folder_name,
                        'user_name': user_name,
                        'path': profile_dir,
                        'location': location,
                        'facebook_accounts': facebook_accounts,
                        'has_facebook': len(facebook_accounts) > 0
                    })
            except Exception as e:
                logger.error(f"Error processing profile directory {profile_dir}: {str(e)}")
                continue

        logger.info(f"Successfully retrieved {len(profiles)} Chrome profiles")
        return profiles
        
    except Exception as e:
        logger.error(f"Critical error in get_chrome_profiles: {str(e)}")
        logger.error(traceback.format_exc())
        return []


def get_profile_locations_dict():
    """Get all profile locations from Supabase as a dictionary with error handling"""
    try:
        response = supabase.table('profile_locations').select('*').execute()
        locations = {item['profile_name']: item['location'] for item in response.data}
        logger.info(f"Retrieved {len(locations)} profile locations from Supabase")
        return locations
    except Exception as e:
        logger.error(f"Error fetching profile locations: {str(e)}")
        logger.error(traceback.format_exc())
        return {}


def allowed_file(filename):
    """Check if file extension is allowed"""
    try:
        if not filename or '.' not in filename:
            return False
        return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    except Exception as e:
        logger.error(f"Error checking file extension for {filename}: {str(e)}")
        return False


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    try:
        if not isinstance(size_bytes, (int, float)):
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    except Exception as e:
        logger.error(f"Error formatting file size: {str(e)}")
        return "Unknown"


def start_upload_tracking(profile_name, profile_folder, listing_data, location, facebook_account_name=None, facebook_account_email=None):
    """
    Helper function to start tracking an upload with Facebook account info
    Call this when the bot starts uploading a listing
    
    Returns: upload_id that can be used to update status later
    """
    try:
        if not profile_name or not profile_folder or not listing_data:
            logger.error("Missing required parameters for upload tracking")
            return None
            
        vehicle_info = {
            'year': listing_data.get('Year'),
            'make': listing_data.get('Make'),
            'model': listing_data.get('Model'),
            'price': listing_data.get('Price'),
            'mileage': listing_data.get('Mileage'),
            'body_style': listing_data.get('Body Style'),
            'exterior_color': listing_data.get('Exterior Color'),
            'interior_color': listing_data.get('Interior Color'),
            'vehicle_condition': listing_data.get('Vehicle Condition'),
            'fuel_type': listing_data.get('Fuel Type'),
            'transmission': listing_data.get('Transmission'),
            'description': listing_data.get('Description')
        }
        
        upload_record = {
            'profile_name': profile_name,
            'profile_folder': profile_folder,
            'facebook_account_name': facebook_account_name,
            'facebook_account_email': facebook_account_email,
            'listing_id': listing_data.get('id'),
            'vehicle_info': vehicle_info,
            'status': 'in_progress',
            'location': location,
            'upload_datetime': datetime.utcnow().isoformat()
        }
        
        response = supabase.table('upload_history').insert(upload_record).execute()
        
        if response.data:
            upload_id = response.data[0]['id']
            logger.info(f"Started upload tracking with ID: {upload_id}")
            return upload_id
        
        logger.warning("Upload tracking started but no ID returned")
        return None
        
    except Exception as e:
        logger.error(f"Error starting upload tracking: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def complete_upload_tracking(upload_id, success=True, marketplace_url=None, error_message=None):
    """
    Helper function to mark an upload as complete with error handling
    Call this when the bot finishes uploading (success or failure)
    """
    try:
        if not upload_id:
            logger.error("No upload_id provided for completion tracking")
            return False
            
        update_data = {
            'status': 'success' if success else 'failed',
            'completed_datetime': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if marketplace_url:
            update_data['marketplace_url'] = marketplace_url
            
        if error_message:
            update_data['error_message'] = str(error_message)[:500]  # Limit error message length
        
        supabase.table('upload_history')\
            .update(update_data)\
            .eq('id', upload_id)\
            .execute()
        
        logger.info(f"Completed upload tracking for ID {upload_id}: {'success' if success else 'failed'}")
        return True
        
    except Exception as e:
        logger.error(f"Error completing upload tracking: {str(e)}")
        logger.error(traceback.format_exc())
        return False


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
            print(f"✅ Connected to Supabase successfully!")
            print(f"✅ Found {listings_count} listings in database")
        except Exception as e:
            logger.error(f"Failed to query listings table: {str(e)}")
            raise
        
        # Test profile_locations table
        try:
            response = supabase.table('profile_locations').select('id', count='exact').execute()
            profiles_count = response.count
            print(f"✅ Found {profiles_count} profile locations in database")
        except Exception as e:
            logger.error(f"Failed to query profile_locations table: {str(e)}")
            raise
        
        # Test upload_history table (optional - won't fail if doesn't exist)
        try:
            response = supabase.table('upload_history').select('id', count='exact').execute()
            uploads_count = response.count
            print(f"✅ Found {uploads_count} upload records in database")
        except Exception as e:
            print(f"ℹ️  Upload history table not found (run schema if you want tracking)")
            logger.warning(f"Upload history table not accessible: {str(e)}")
        
        print("=" * 60 + "\n")
        logger.info("Supabase connection test completed successfully")
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR: Could not connect to Supabase!")
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
# MAIN ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main page route with error handling"""
    try:
        profiles = get_chrome_profiles()
        profile_locations = get_profile_locations_dict()
        
        try:
            # Fetch listings from Supabase
            response = supabase.table('listings').select('*').order('id').execute()
            listings = []
            
            for item in response.data:
                try:
                    listing = {
                        'id': item['id'],
                        'Year': item['year'],
                        'Make': item['make'],
                        'Model': item['model'],
                        'Mileage': item['mileage'],
                        'Price': item['price'],
                        'Body Style': item['body_style'],
                        'Exterior Color': item['exterior_color'],
                        'Interior Color': item['interior_color'],
                        'Vehicle Condition': item['vehicle_condition'],
                        'Fuel Type': item['fuel_type'],
                        'Transmission': item['transmission'],
                        'Description': item['description'],
                        'Images Path': item['images_path']
                    }
                    listings.append(listing)
                except Exception as e:
                    logger.error(f"Error processing listing item {item.get('id', 'unknown')}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error reading listings from Supabase: {str(e)}")
            logger.error(traceback.format_exc())
            listings = []
            
        return render_template('index.html', 
                             profiles=profiles, 
                             listings=listings, 
                             profile_locations=profile_locations,
                             max_profile_selection=MAX_PROFILE_SELECTION)
                             
    except Exception as e:
        logger.error(f"Critical error in index route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": "Failed to load application. Please check server logs."
        }), 500


# ============================================================================
# PROFILE MANAGEMENT ROUTES
# ============================================================================

@app.route('/update_profile_location', methods=['POST'])
def update_profile_location():
    """Update or create a profile location with error handling"""
    try:
        data = request.json
        
        if not data or 'profile' not in data or 'location' not in data:
            logger.warning("Invalid data received for profile location update")
            return jsonify({
                "status": "error",
                "message": "Invalid data. Profile and location are required."
            }), 400
        
        profile_name = data['profile']
        location = data['location']
        
        if not profile_name:
            return jsonify({
                "status": "error",
                "message": "Profile name cannot be empty"
            }), 400
        
        # Check if profile exists
        try:
            response = supabase.table('profile_locations').select('*').eq('profile_name', profile_name).execute()
            
            if response.data:
                # Update existing
                supabase.table('profile_locations').update({
                    'location': location
                }).eq('profile_name', profile_name).execute()
                logger.info(f"Updated location for profile: {profile_name}")
            else:
                # Insert new
                supabase.table('profile_locations').insert({
                    'profile_name': profile_name,
                    'location': location
                }).execute()
                logger.info(f"Created new location for profile: {profile_name}")
            
            return jsonify({"status": "success"})
            
        except Exception as e:
            logger.error(f"Database error updating profile location: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"Error in update_profile_location: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Failed to update profile location: {str(e)}"
        }), 500


# ============================================================================
# LISTING MANAGEMENT ROUTES
# ============================================================================

@app.route('/add_listing', methods=['POST'])
def add_listing():
    """Add a new listing to Supabase with comprehensive error handling"""
    try:
        listing = request.json
        
        if not listing:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        # Ensure the listing has all required fields
        required_fields = [
            'Year', 'Make', 'Model', 'Mileage', 'Price', 
            'Body Style', 'Exterior Color', 'Interior Color',
            'Vehicle Condition', 'Fuel Type', 'Transmission',
            'Description', 'Images Path'
        ]
        
        # Validate required fields
        missing_fields = [field for field in required_fields if not listing.get(field)]
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Convert and validate numeric fields
        try:
            year = int(float(listing['Year']))
            if year < 1900 or year > datetime.now().year + 2:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid year: {year}. Must be between 1900 and {datetime.now().year + 2}"
                }), 400
                
            mileage = int(float(listing['Mileage']))
            if mileage < 0 or mileage > 1000000:
                return jsonify({
                    "status": "error",
                    "message": "Invalid mileage. Must be between 0 and 1,000,000"
                }), 400
                
            price = int(float(listing['Price']))
            if price < 0 or price > 10000000:
                return jsonify({
                    "status": "error",
                    "message": "Invalid price. Must be between 0 and 10,000,000"
                }), 400
                
        except ValueError as e:
            logger.error(f"Invalid numeric value in listing: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Invalid numeric value: {str(e)}"
            }), 400
        
        # Prepare data for Supabase
        listing_data = {
            'year': year,
            'make': str(listing['Make'])[:100],
            'model': str(listing['Model'])[:100],
            'mileage': mileage,
            'price': price,
            'body_style': str(listing['Body Style'])[:50],
            'exterior_color': str(listing['Exterior Color'])[:50],
            'interior_color': str(listing['Interior Color'])[:50],
            'vehicle_condition': str(listing['Vehicle Condition'])[:50],
            'fuel_type': str(listing['Fuel Type'])[:50],
            'transmission': str(listing['Transmission'])[:50],
            'description': str(listing['Description'])[:5000],
            'images_path': str(listing['Images Path'])[:500]
        }
        
        # Insert into Supabase
        response = supabase.table('listings').insert(listing_data).execute()
        
        logger.info(f"Successfully added listing: {year} {listing['Make']} {listing['Model']}")
        return jsonify({"status": "success", "data": response.data})
            
    except Exception as e:
        logger.error(f"Error in add_listing: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Failed to add listing: {str(e)}"
        }), 500


@app.route('/update_listing', methods=['POST'])
def update_listing():
    """Update an existing listing in Supabase with error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
            
        listing_id = data.get('id')
        
        if not listing_id:
            return jsonify({
                "status": "error",
                "message": "No listing ID provided"
            }), 400
        
        # Validate ID is numeric
        try:
            listing_id = int(listing_id)
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid listing ID format"
            }), 400
        
        # Ensure the listing has all required fields
        required_fields = [
            'Year', 'Make', 'Model', 'Mileage', 'Price', 
            'Body Style', 'Exterior Color', 'Interior Color',
            'Vehicle Condition', 'Fuel Type', 'Transmission',
            'Description', 'Images Path'
        ]
        
        # Validate required fields
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Convert and validate numeric fields
        try:
            year = int(float(data['Year']))
            if year < 1900 or year > datetime.now().year + 2:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid year: {year}"
                }), 400
                
            mileage = int(float(data['Mileage']))
            if mileage < 0:
                return jsonify({
                    "status": "error",
                    "message": "Mileage cannot be negative"
                }), 400
                
            price = int(float(data['Price']))
            if price < 0:
                return jsonify({
                    "status": "error",
                    "message": "Price cannot be negative"
                }), 400
                
        except ValueError as e:
            logger.error(f"Invalid numeric value: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Invalid numeric value: {str(e)}"
            }), 400
        
        # Prepare update data for Supabase
        update_data = {
            'year': year,
            'make': str(data['Make'])[:100],
            'model': str(data['Model'])[:100],
            'mileage': mileage,
            'price': price,
            'body_style': str(data['Body Style'])[:50],
            'exterior_color': str(data['Exterior Color'])[:50],
            'interior_color': str(data['Interior Color'])[:50],
            'vehicle_condition': str(data['Vehicle Condition'])[:50],
            'fuel_type': str(data['Fuel Type'])[:50],
            'transmission': str(data['Transmission'])[:50],
            'description': str(data['Description'])[:5000],
            'images_path': str(data['Images Path'])[:500]
        }
        
        # Update in Supabase
        response = supabase.table('listings').update(update_data).eq('id', listing_id).execute()
        
        if not response.data:
            return jsonify({
                "status": "error",
                "message": "Listing not found or update failed"
            }), 404
        
        logger.info(f"Successfully updated listing ID: {listing_id}")
        return jsonify({"status": "success", "data": response.data})
            
    except Exception as e:
        logger.error(f"Error in update_listing: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Failed to update listing: {str(e)}"
        }), 500


@app.route('/delete_listing', methods=['POST'])
def delete_listing():
    """Delete a listing from Supabase with error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
            
        index = data.get('index')
        
        if index is None:
            return jsonify({
                "status": "error",
                "message": "No index provided"
            }), 400
        
        # Validate index
        try:
            index = int(index)
            if index < 0:
                return jsonify({
                    "status": "error",
                    "message": "Invalid index: must be non-negative"
                }), 400
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "Invalid index format"
            }), 400
        
        # Fetch all listings to get the ID at the given index
        response = supabase.table('listings').select('*').order('id').execute()
        
        if not response.data:
            return jsonify({
                "status": "error",
                "message": "No listings found"
            }), 404
        
        if index >= len(response.data):
            return jsonify({
                "status": "error",
                "message": f"Invalid index: {index} (max: {len(response.data) - 1})"
            }), 400
        
        listing_id = response.data[index]['id']
        
        # Delete from Supabase
        delete_response = supabase.table('listings').delete().eq('id', listing_id).execute()
        
        logger.info(f"Successfully deleted listing ID: {listing_id}")
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"Error in delete_listing: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Failed to delete listing: {str(e)}"
        }), 500


# ============================================================================
# UPLOAD TRACKING ROUTES
# ============================================================================

@app.route('/track_upload', methods=['POST'])
def track_upload():
    """Record an upload attempt to the database with error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['profile_name', 'listing_id', 'vehicle_info']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Prepare upload record
        upload_record = {
            'profile_name': str(data.get('profile_name'))[:100],
            'profile_folder': str(data.get('profile_folder', ''))[:100],
            'facebook_account_name': str(data.get('facebook_account_name', ''))[:100] if data.get('facebook_account_name') else None,
            'facebook_account_email': str(data.get('facebook_account_email', ''))[:200] if data.get('facebook_account_email') else None,
            'listing_id': data.get('listing_id'),
            'vehicle_info': data.get('vehicle_info'),
            'status': data.get('status', 'pending'),
            'error_message': str(data.get('error_message', ''))[:500] if data.get('error_message') else None,
            'location': str(data.get('location', ''))[:200],
            'marketplace_url': str(data.get('marketplace_url', ''))[:500] if data.get('marketplace_url') else None,
            'attempt_number': int(data.get('attempt_number', 1)),
            'upload_datetime': datetime.utcnow().isoformat()
        }
        
        # Insert into Supabase
        response = supabase.table('upload_history').insert(upload_record).execute()
        
        upload_id = response.data[0]['id'] if response.data else None
        logger.info(f"Successfully tracked upload with ID: {upload_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Upload tracked successfully',
            'upload_id': upload_id
        })
        
    except Exception as e:
        logger.error(f"Error in track_upload: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to track upload: {str(e)}'
        }), 500


@app.route('/update_upload_status', methods=['POST'])
def update_upload_status():
    """Update the status of an existing upload record with error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        upload_id = data.get('upload_id')
        
        if not upload_id:
            return jsonify({
                'status': 'error',
                'message': 'upload_id is required'
            }), 400
        
        # Validate upload_id
        try:
            upload_id = int(upload_id)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid upload_id format'
            }), 400
        
        # Prepare update data
        update_data = {
            'status': data.get('status', 'pending'),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if data.get('error_message'):
            update_data['error_message'] = str(data.get('error_message'))[:500]
            
        if data.get('marketplace_url'):
            update_data['marketplace_url'] = str(data.get('marketplace_url'))[:500]
        
        # Update in Supabase
        response = supabase.table('upload_history')\
            .update(update_data)\
            .eq('id', upload_id)\
            .execute()
        
        if not response.data:
            return jsonify({
                'status': 'error',
                'message': 'Upload record not found'
            }), 404
        
        logger.info(f"Successfully updated upload status for ID: {upload_id}")
        return jsonify({
            'status': 'success',
            'message': 'Upload status updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in update_upload_status: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to update upload status: {str(e)}'
        }), 500


@app.route('/upload_history', methods=['GET'])
def get_upload_history():
    """Retrieve upload history with optional filters and error handling"""
    try:
        # Get and validate query parameters
        try:
            page = int(request.args.get('page', 1))
            if page < 1:
                page = 1
        except ValueError:
            page = 1
            
        try:
            page_size = int(request.args.get('page_size', 20))
            if page_size < 1 or page_size > 100:
                page_size = 20
        except ValueError:
            page_size = 20
            
        profile_filter = request.args.get('profile', '')
        status_filter = request.args.get('status', '')
        date_from = request.args.get('dateFrom', '')
        date_to = request.args.get('dateTo', '')
        
        # Build query
        query = supabase.table('upload_history').select('*', count='exact')
        
        # Apply filters
        if profile_filter:
            query = query.eq('profile_name', profile_filter)
            
        if status_filter:
            query = query.eq('status', status_filter)
            
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.gte('upload_datetime', date_from_dt.isoformat())
            except ValueError:
                logger.warning(f"Invalid date_from format: {date_from}")
            
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.lt('upload_datetime', date_to_dt.isoformat())
            except ValueError:
                logger.warning(f"Invalid date_to format: {date_to}")
        
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        # Execute query with ordering
        response = query.order('upload_datetime', desc=True)\
            .range(start, end)\
            .execute()
        
        # Get statistics
        stats_query = supabase.table('upload_history').select('status', count='exact')
        
        # Apply same filters to stats
        if profile_filter:
            stats_query = stats_query.eq('profile_name', profile_filter)
        if date_from:
            try:
                stats_query = stats_query.gte('upload_datetime', date_from_dt.isoformat())
            except:
                pass
        if date_to:
            try:
                stats_query = stats_query.lt('upload_datetime', date_to_dt.isoformat())
            except:
                pass
        
        stats_response = stats_query.execute()
        
        # Calculate statistics
        stats = {
            'success': 0,
            'failed': 0,
            'pending': 0,
            'in_progress': 0,
            'total': 0
        }
        
        if stats_response.data:
            for record in stats_response.data:
                status = record.get('status', '')
                if status in stats:
                    stats[status] = stats.get(status, 0) + 1
                stats['total'] += 1
        
        logger.info(f"Retrieved {len(response.data)} upload history records")
        
        return jsonify({
            'status': 'success',
            'uploads': response.data,
            'total': response.count,
            'page': page,
            'page_size': page_size,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in get_upload_history: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve upload history: {str(e)}'
        }), 500


@app.route('/export_history', methods=['GET'])
def export_history():
    """Export upload history to CSV with error handling"""
    try:
        # Get filters
        profile_filter = request.args.get('profile', '')
        status_filter = request.args.get('status', '')
        date_from = request.args.get('dateFrom', '')
        date_to = request.args.get('dateTo', '')
        
        # Build query (similar to get_upload_history but without pagination)
        query = supabase.table('upload_history').select('*')
        
        if profile_filter:
            query = query.eq('profile_name', profile_filter)
        if status_filter:
            query = query.eq('status', status_filter)
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.gte('upload_datetime', date_from_dt.isoformat())
            except ValueError:
                pass
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.lt('upload_datetime', date_to_dt.isoformat())
            except ValueError:
                pass
        
        response = query.order('upload_datetime', desc=True).execute()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Upload ID',
            'Date & Time',
            'Profile Name',
            'Profile Folder',
            'Facebook Account Name',
            'Facebook Account Email',
            'Vehicle Year',
            'Vehicle Make',
            'Vehicle Model',
            'Price',
            'Mileage',
            'Location',
            'Status',
            'Error Message',
            'Marketplace URL',
            'Attempt Number'
        ])
        
        # Write data
        for upload in response.data:
            try:
                vehicle_info = upload.get('vehicle_info', {})
                writer.writerow([
                    upload.get('id', ''),
                    upload.get('upload_datetime', ''),
                    upload.get('profile_name', ''),
                    upload.get('profile_folder', ''),
                    upload.get('facebook_account_name', ''),
                    upload.get('facebook_account_email', ''),
                    vehicle_info.get('year', ''),
                    vehicle_info.get('make', ''),
                    vehicle_info.get('model', ''),
                    vehicle_info.get('price', ''),
                    vehicle_info.get('mileage', ''),
                    upload.get('location', ''),
                    upload.get('status', ''),
                    upload.get('error_message', ''),
                    upload.get('marketplace_url', ''),
                    upload.get('attempt_number', 1)
                ])
            except Exception as e:
                logger.error(f"Error writing row for upload {upload.get('id')}: {str(e)}")
                continue
        
        # Prepare file for download
        output.seek(0)
        
        logger.info(f"Exported {len(response.data)} upload history records")
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'upload_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        logger.error(f"Error in export_history: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to export history: {str(e)}'
        }), 500


@app.route('/upload_stats', methods=['GET'])
def get_upload_stats():
    """Get overall upload statistics with error handling"""
    try:
        # Get and validate days parameter
        try:
            days = int(request.args.get('days', 30))
            if days < 1 or days > 365:
                days = 30
        except ValueError:
            days = 30
        
        # Calculate date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Get stats for the period
        response = supabase.table('upload_history')\
            .select('status, profile_name', count='exact')\
            .gte('upload_datetime', date_threshold.isoformat())\
            .execute()
        
        # Calculate statistics
        stats = {
            'total_uploads': response.count,
            'by_status': {
                'success': 0,
                'failed': 0,
                'pending': 0,
                'in_progress': 0
            },
            'by_profile': {},
            'success_rate': 0
        }
        
        for record in response.data:
            status = record.get('status', '')
            profile = record.get('profile_name', 'Unknown')
            
            if status in stats['by_status']:
                stats['by_status'][status] += 1
                
            if profile not in stats['by_profile']:
                stats['by_profile'][profile] = 0
            stats['by_profile'][profile] += 1
        
        # Calculate success rate
        if stats['total_uploads'] > 0:
            stats['success_rate'] = round(
                (stats['by_status']['success'] / stats['total_uploads']) * 100, 2
            )
        
        logger.info(f"Retrieved upload stats for last {days} days")
        
        return jsonify({
            'status': 'success',
            'stats': stats,
            'period_days': days
        })
        
    except Exception as e:
        logger.error(f"Error in get_upload_stats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to get upload stats: {str(e)}'
        }), 500


# ============================================================================
# SCHEDULING ROUTES
# ============================================================================

@app.route('/schedule_post', methods=['POST'])
def schedule_post():
    """Schedule a post for future automatic upload"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['listing_id', 'profile_folder', 'profile_name', 'scheduled_datetime']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Parse scheduled datetime
        scheduled_dt = datetime.fromisoformat(data['scheduled_datetime'].replace('Z', '+00:00'))
        
        # Check if the scheduled time is in the future
        if scheduled_dt <= datetime.utcnow():
            return jsonify({
                'status': 'error',
                'message': 'Scheduled time must be in the future'
            }), 400
        
        # Calculate next run datetime based on recurrence
        recurrence = data.get('recurrence', 'none')
        next_run = scheduled_dt
        
        # Prepare schedule record
        schedule_record = {
            'listing_id': data['listing_id'],
            'profile_folder': data['profile_folder'],
            'profile_name': data['profile_name'],
            'facebook_account_name': data.get('facebook_account_name'),
            'facebook_account_email': data.get('facebook_account_email'),
            'scheduled_datetime': scheduled_dt.isoformat(),
            'next_run_datetime': next_run.isoformat(),
            'status': 'pending',
            'recurrence': recurrence
        }
        
        # Insert into Supabase
        response = supabase.table('scheduled_posts').insert(schedule_record).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Post scheduled successfully',
            'schedule_id': response.data[0]['id'] if response.data else None
        })
        
    except Exception as e:
        logger.error(f"Error in schedule_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/get_scheduled_posts', methods=['GET'])
def get_scheduled_posts():
    """Get all scheduled posts with optional filters"""
    try:
        # Build query
        query = supabase.table('scheduled_posts').select('*')
        
        # Apply filters
        status_filter = request.args.get('status')
        if status_filter:
            query = query.eq('status', status_filter)
        
        profile_filter = request.args.get('profile')
        if profile_filter:
            query = query.eq('profile_name', profile_filter)
        
        listing_id_filter = request.args.get('listing_id')
        if listing_id_filter:
            query = query.eq('listing_id', int(listing_id_filter))
        
        upcoming = request.args.get('upcoming', 'false').lower() == 'true'
        if upcoming:
            query = query.gte('next_run_datetime', datetime.utcnow().isoformat())
        
        # Execute query
        response = query.order('scheduled_datetime', desc=False).execute()
        
        # Enhance data with listing details
        scheduled_posts = []
        for post in response.data:
            # Get listing details
            listing_response = supabase.table('listings').select('*').eq('id', post['listing_id']).execute()
            listing = listing_response.data[0] if listing_response.data else {}
            
            enhanced_post = {
                **post,
                'vehicle_info': {
                    'year': listing.get('year'),
                    'make': listing.get('make'),
                    'model': listing.get('model'),
                    'price': listing.get('price'),
                    'mileage': listing.get('mileage')
                }
            }
            scheduled_posts.append(enhanced_post)
        
        return jsonify({
            'status': 'success',
            'scheduled_posts': scheduled_posts,
            'total': len(scheduled_posts)
        })
        
    except Exception as e:
        logger.error(f"Error in get_scheduled_posts: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/update_scheduled_post', methods=['POST'])
def update_scheduled_post():
    """Update a scheduled post"""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        
        if not schedule_id:
            return jsonify({
                'status': 'error',
                'message': 'schedule_id is required'
            }), 400
        
        # Prepare update data
        update_data = {}
        
        if 'scheduled_datetime' in data:
            scheduled_dt = datetime.fromisoformat(data['scheduled_datetime'].replace('Z', '+00:00'))
            update_data['scheduled_datetime'] = scheduled_dt.isoformat()
            update_data['next_run_datetime'] = scheduled_dt.isoformat()
        
        if 'status' in data:
            update_data['status'] = data['status']
        
        if 'recurrence' in data:
            update_data['recurrence'] = data['recurrence']
        
        if not update_data:
            return jsonify({
                'status': 'error',
                'message': 'No fields to update'
            }), 400
        
        # Update in Supabase
        response = supabase.table('scheduled_posts')\
            .update(update_data)\
            .eq('id', schedule_id)\
            .execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Scheduled post updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in update_scheduled_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/delete_scheduled_post', methods=['POST'])
def delete_scheduled_post():
    """Delete a scheduled post"""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        
        if not schedule_id:
            return jsonify({
                'status': 'error',
                'message': 'schedule_id is required'
            }), 400
        
        # Delete from Supabase
        supabase.table('scheduled_posts')\
            .delete()\
            .eq('id', schedule_id)\
            .execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Scheduled post deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in delete_scheduled_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/process_scheduled_posts', methods=['POST'])
def process_scheduled_posts():
    """Process scheduled posts that are due"""
    try:
        current_time = datetime.utcnow()
        
        # Get all pending scheduled posts that are due
        response = supabase.table('scheduled_posts')\
            .select('*')\
            .eq('status', 'pending')\
            .lte('next_run_datetime', current_time.isoformat())\
            .execute()
        
        due_posts = response.data
        processed_count = 0
        
        for post in due_posts:
            try:
                # Get listing details
                listing_response = supabase.table('listings')\
                    .select('*')\
                    .eq('id', post['listing_id'])\
                    .execute()
                
                if not listing_response.data:
                    # Mark as failed if listing doesn't exist
                    supabase.table('scheduled_posts')\
                        .update({
                            'status': 'failed',
                            'error_message': 'Listing not found'
                        })\
                        .eq('id', post['id'])\
                        .execute()
                    continue
                
                # TODO: Trigger bot to post this listing
                # For now, we'll just mark it for manual processing
                
                # Update schedule based on recurrence
                if post['recurrence'] == 'daily':
                    next_run = current_time + timedelta(days=1)
                    supabase.table('scheduled_posts')\
                        .update({
                            'last_run_datetime': current_time.isoformat(),
                            'next_run_datetime': next_run.isoformat()
                        })\
                        .eq('id', post['id'])\
                        .execute()
                elif post['recurrence'] == 'weekly':
                    next_run = current_time + timedelta(weeks=1)
                    supabase.table('scheduled_posts')\
                        .update({
                            'last_run_datetime': current_time.isoformat(),
                            'next_run_datetime': next_run.isoformat()
                        })\
                        .eq('id', post['id'])\
                        .execute()
                elif post['recurrence'] == 'monthly':
                    next_run = current_time + timedelta(days=30)
                    supabase.table('scheduled_posts')\
                        .update({
                            'last_run_datetime': current_time.isoformat(),
                            'next_run_datetime': next_run.isoformat()
                        })\
                        .eq('id', post['id'])\
                        .execute()
                else:
                    # One-time schedule, mark as completed
                    supabase.table('scheduled_posts')\
                        .update({
                            'status': 'completed',
                            'last_run_datetime': current_time.isoformat()
                        })\
                        .eq('id', post['id'])\
                        .execute()
                
                processed_count += 1
                
            except Exception as e:
                # Mark this post as failed
                supabase.table('scheduled_posts')\
                    .update({
                        'status': 'failed',
                        'error_message': str(e)
                    })\
                    .eq('id', post['id'])\
                    .execute()
        
        return jsonify({
            'status': 'success',
            'message': f'Processed {processed_count} scheduled posts',
            'processed_count': processed_count
        })
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_posts: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/get_schedule_stats', methods=['GET'])
def get_schedule_stats():
    """Get statistics about scheduled posts"""
    try:
        # Get counts by status
        response = supabase.table('scheduled_posts')\
            .select('status', count='exact')\
            .execute()
        
        stats = {
            'pending': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'total': len(response.data)
        }
        
        for record in response.data:
            status = record.get('status', 'pending')
            if status in stats:
                stats[status] += 1
        
        # Get upcoming posts (next 7 days)
        upcoming_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        upcoming_response = supabase.table('scheduled_posts')\
            .select('id', count='exact')\
            .eq('status', 'pending')\
            .lte('next_run_datetime', upcoming_date)\
            .gte('next_run_datetime', datetime.utcnow().isoformat())\
            .execute()
        
        stats['upcoming_7_days'] = upcoming_response.count
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in get_schedule_stats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ============================================================================
# GOOGLE DRIVE MEDIA MANAGEMENT ROUTES
# ============================================================================

@app.route('/upload_to_drive', methods=['POST'])
def upload_to_drive():
    """Upload file to Google Drive with comprehensive error handling"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        
        if not filename:
            return jsonify({
                'status': 'error',
                'message': 'Invalid filename'
            }), 400
        
        # Save temporarily
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        
        try:
            file.save(temp_path)
        except Exception as e:
            logger.error(f"Failed to save temp file: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to save file: {str(e)}'
            }), 500
        
        # Check file size
        try:
            file_size = os.path.getsize(temp_path)
            if file_size > MAX_FILE_SIZE:
                os.remove(temp_path)
                return jsonify({
                    'status': 'error',
                    'message': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'
                }), 400
        except Exception as e:
            logger.error(f"Failed to check file size: {str(e)}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({
                'status': 'error',
                'message': 'Failed to process file'
            }), 500
        
        # Upload to Google Drive
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            drive_manager.ensure_folder_exists()
            
            result = drive_manager.upload_file(file_path=temp_path)
            
            logger.info(f"Successfully uploaded file to Google Drive: {filename}")
            
            # Clean up temp file
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp file: {str(e)}")
            
            return jsonify({
                'status': 'success',
                'message': 'File uploaded successfully',
                'file': {
                    'id': result['id'],
                    'name': result['name'],
                    'size': result.get('size', 0),
                    'mimeType': result.get('mimeType', ''),
                    'webViewLink': result.get('webViewLink', ''),
                    'webContentLink': result.get('webContentLink', ''),
                    'createdTime': result.get('createdTime', '')
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {str(e)}")
            logger.error(traceback.format_exc())
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            return jsonify({
                'status': 'error',
                'message': f'Upload to Google Drive failed: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Error in upload_to_drive: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500


@app.route('/list_drive_files', methods=['GET'])
def list_drive_files():
    """List all files in Google Drive fbBotMedia folder with error handling"""
    try:
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        files = drive_manager.list_files()
        
        # Format file data
        formatted_files = []
        for file in files:
            try:
                formatted_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'createdTime': file.get('createdTime', ''),
                    'modifiedTime': file.get('modifiedTime', ''),
                    'webViewLink': file.get('webViewLink', ''),
                    'webContentLink': file.get('webContentLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            except Exception as e:
                logger.error(f"Error formatting file {file.get('id', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully listed {len(formatted_files)} files from Google Drive")
        
        return jsonify({
            'status': 'success',
            'files': formatted_files,
            'total': len(formatted_files)
        })
        
    except Exception as e:
        logger.error(f"Error in list_drive_files: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to list files: {str(e)}'
        }), 500


@app.route('/delete_drive_file', methods=['POST'])
def delete_drive_file():
    """Delete a file from Google Drive with error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        file_id = data.get('file_id')
        
        if not file_id:
            return jsonify({
                'status': 'error',
                'message': 'No file ID provided'
            }), 400
        
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        
        success = drive_manager.delete_file(file_id)
        
        if success:
            logger.info(f"Successfully deleted file from Google Drive: {file_id}")
            return jsonify({
                'status': 'success',
                'message': 'File deleted successfully'
            })
        else:
            logger.error(f"Failed to delete file from Google Drive: {file_id}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to delete file'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in delete_drive_file: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Delete failed: {str(e)}'
        }), 500


@app.route('/get_drive_stats', methods=['GET'])
def get_drive_stats():
    """Get statistics about the Google Drive folder with error handling"""
    try:
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        stats = drive_manager.get_folder_stats()
        
        logger.info("Successfully retrieved Google Drive stats")
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in get_drive_stats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to get stats: {str(e)}'
        }), 500


@app.route('/search_drive_files', methods=['GET'])
def search_drive_files():
    """Search for files in Google Drive with error handling"""
    try:
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({
                'status': 'error',
                'message': 'No search query provided'
            }), 400
        
        # Sanitize query
        query = query[:100]  # Limit query length
        
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        files = drive_manager.search_files(query)
        
        # Format file data
        formatted_files = []
        for file in files:
            try:
                formatted_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'createdTime': file.get('createdTime', ''),
                    'webViewLink': file.get('webViewLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            except Exception as e:
                logger.error(f"Error formatting file {file.get('id', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Search found {len(formatted_files)} files for query: {query}")
        
        return jsonify({
            'status': 'success',
            'files': formatted_files,
            'total': len(formatted_files)
        })
        
    except Exception as e:
        logger.error(f"Error in search_drive_files: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Search failed: {str(e)}'
        }), 500


# ============================================================================
# BOT EXECUTION ROUTE
# ============================================================================

@app.route('/run_bot', methods=['POST'])
def run_bot():
    """Run the automation bot with selected profiles and listings with comprehensive error handling"""
    try:
        data = request.json
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        selected_profiles = data.get('profiles', [])
        selected_listings = data.get('listings', [])
        listings_data = data.get('listingsData', [])
        
        # Validate profiles and listings are selected
        if not selected_profiles:
            return jsonify({
                "status": "error",
                "message": "No profiles selected"
            }), 400
        
        if not selected_listings:
            return jsonify({
                "status": "error",
                "message": "No listings selected"
            }), 400
        
        # ENFORCE PROFILE SELECTION LIMIT
        if len(selected_profiles) > MAX_PROFILE_SELECTION:
            logger.warning(f"Profile selection limit exceeded: {len(selected_profiles)} > {MAX_PROFILE_SELECTION}")
            return jsonify({
                "status": "error",
                "message": f"You can only select up to {MAX_PROFILE_SELECTION} profiles at a time. Currently selected: {len(selected_profiles)}"
            }), 400
        
        # Get profile locations from Supabase
        profile_locations = get_profile_locations_dict()
        
        # Validate all profiles have locations
        profiles_without_location = []
        for profile in selected_profiles:
            folder_name = profile.get('folder_name', '')
            if not profile_locations.get(folder_name):
                profiles_without_location.append(profile.get('user_name', folder_name))
        
        if profiles_without_location:
            return jsonify({
                "status": "error",
                "message": f"The following profiles are missing locations: {', '.join(profiles_without_location)}"
            }), 400
        
        # Save selected profiles to a temporary file with their locations
        try:
            with open('selected_profiles.txt', 'w', encoding='utf-8') as f:
                for profile in selected_profiles:
                    folder_name = profile.get('folder_name', '')
                    path = profile.get('path', '')
                    user_name = profile.get('user_name', '')
                    location = profile.get('location', profile_locations.get(folder_name, ""))
                    
                    if not path or not location:
                        logger.warning(f"Profile missing required data: {user_name}")
                        continue
                    
                    f.write(f"{path}|{location}|{user_name}\n")
        except Exception as e:
            logger.error(f"Failed to write selected_profiles.txt: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Failed to prepare profile data: {str(e)}"
            }), 500
        
        # Fetch all listings from Supabase
        try:
            response = supabase.table('listings').select('*').order('id').execute()
            all_listings = response.data
        except Exception as e:
            logger.error(f"Failed to fetch listings from database: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Failed to fetch listings: {str(e)}"
            }), 500
        
        # Prepare selected listings data for CSV
        selected_listings_data = []
        for i, index in enumerate(selected_listings):
            try:
                if index < 0 or index >= len(all_listings):
                    logger.warning(f"Invalid listing index: {index}")
                    continue
                
                listing = all_listings[index]
                
                # Create CSV row
                csv_row = {
                    'Year': listing['year'],
                    'Make': listing['make'],
                    'Model': listing['model'],
                    'Mileage': listing['mileage'],
                    'Price': listing['price'],
                    'Body Style': listing['body_style'],
                    'Exterior Color': listing['exterior_color'],
                    'Interior Color': listing['interior_color'],
                    'Vehicle Condition': listing['vehicle_condition'],
                    'Fuel Type': listing['fuel_type'],
                    'Transmission': listing['transmission'],
                    'Description': listing['description'],
                    'Images Path': listing['images_path']
                }
                selected_listings_data.append(csv_row)
            except Exception as e:
                logger.error(f"Error processing listing at index {index}: {str(e)}")
                continue
        
        if not selected_listings_data:
            return jsonify({
                "status": "error",
                "message": "No valid listings to process"
            }), 400
        
        # Create temporary CSV for the bot
        try:
            df = pd.DataFrame(selected_listings_data)
            df.to_csv('selected_listings.csv', index=False, encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to create selected_listings.csv: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Failed to prepare listing data: {str(e)}"
            }), 500
        
        # Run the bot script
        try:
            logger.info(f"Starting bot with {len(selected_profiles)} profiles and {len(selected_listings_data)} listings")
            
            process = subprocess.Popen(
                ['python', 'Bot.py'], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            logger.info("Bot execution completed")
            
            # Clean up temporary files
            try:
                if os.path.exists('selected_profiles.txt'):
                    os.remove('selected_profiles.txt')
                if os.path.exists('selected_listings.csv'):
                    os.remove('selected_listings.csv')
            except Exception as e:
                logger.warning(f"Failed to clean up temporary files: {str(e)}")
            
            return jsonify({
                'stdout': stdout,
                'stderr': stderr,
                'status': 'success'
            })
            
        except Exception as e:
            logger.error(f"Bot execution failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Try to clean up temporary files
            try:
                if os.path.exists('selected_profiles.txt'):
                    os.remove('selected_profiles.txt')
                if os.path.exists('selected_listings.csv'):
                    os.remove('selected_listings.csv')
            except:
                pass
            
            return jsonify({
                'status': 'error',
                'message': f'Bot execution failed: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Critical error in run_bot: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Bot execution failed: {str(e)}'
        }), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"404 error: {request.url}")
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
            print(f"ℹ️  Maximum profile selection: {MAX_PROFILE_SELECTION}")
            print("\n")
            logger.info("Application starting successfully")
            app.run(debug=True)
        else:
            print("⚠️  Application cannot start without Supabase connection.")
            print("Please fix the errors above and try again.")
            logger.error("Application startup failed: Supabase connection test failed")
    except Exception as e:
        print(f"\n❌ Critical error during startup: {str(e)}")
        logger.error(f"Critical startup error: {str(e)}")
        logger.error(traceback.format_exc())