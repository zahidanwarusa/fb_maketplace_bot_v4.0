"""
Dashboard Component
Handles the main page route and dashboard-related functionality
"""

from flask import Blueprint, render_template, jsonify
import os
import glob
import json
import logging
import traceback

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Get logger
logger = logging.getLogger(__name__)


def get_chrome_profiles(supabase, get_profile_locations_dict, get_facebook_accounts_from_profile):
    """Get all Chrome profiles from the system with Facebook account detection"""
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
            default_profile = os.path.join(user_data_dir, 'Default')
            if os.path.exists(default_profile):
                profile_dirs.append(default_profile)
        except Exception as e:
            logger.error(f"Failed to get profile directories: {str(e)}")
            return profiles

        # Get locations from Supabase
        profile_locations = get_profile_locations_dict(supabase)

        for profile_dir in profile_dirs:
            try:
                if os.path.exists(profile_dir):
                    folder_name = os.path.basename(profile_dir)
                    profile_id = folder_name if folder_name != 'Default' else 'Default'
                    user_name = profile_info.get(profile_id, {}).get('name', 'Unknown')
                    
                    # Get location for this profile from Supabase
                    location = profile_locations.get(folder_name, '')
                    
                    # Detect Facebook accounts for this profile
                    facebook_accounts = []
                    try:
                        facebook_accounts = get_facebook_accounts_from_profile(profile_dir)
                        if facebook_accounts:
                            logger.info(f"Found {len(facebook_accounts)} Facebook account(s) in {folder_name}")
                    except Exception as e:
                        logger.warning(f"Could not detect Facebook accounts for {folder_name}: {str(e)}")
                    
                    profiles.append({
                        'folder_name': folder_name,
                        'user_name': user_name,
                        'path': profile_dir,
                        'location': location,
                        'facebook_accounts': facebook_accounts
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


def get_profile_locations_dict(supabase):
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


def init_dashboard_routes(app, supabase, max_profile_selection, get_facebook_accounts_from_profile_func):
    """Initialize dashboard routes with app context"""
    
    @app.route('/')
    def index():
        """Main page route with error handling"""
        try:
            profiles = get_chrome_profiles(supabase, get_profile_locations_dict, get_facebook_accounts_from_profile_func)
            profile_locations = get_profile_locations_dict(supabase)
            
            try:
                # Fetch listings from Supabase
                response = supabase.table('listings').select('*').is_('deleted_at', 'null').order('id').execute()
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
                            'Images Path': item['images_path'],
                            'selectedDay': item.get('selected_day', ''),
                            'image_ids': item.get('image_ids', []),
                            'image_folder': item.get('image_folder', '')
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
                                 max_profile_selection=max_profile_selection)
                                 
        except Exception as e:
            logger.error(f"Critical error in index route: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": "Failed to load application. Please check server logs."
            }), 500
