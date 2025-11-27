"""
Dashboard Component
Handles the main page route and dashboard-related functionality
"""

from flask import Blueprint, render_template, jsonify
import logging
import traceback

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Get logger
logger = logging.getLogger(__name__)


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


def init_dashboard_routes(app, supabase, max_profile_selection, get_facebook_accounts_from_profile_func=None):
    """Initialize dashboard routes with app context"""
    
    @app.route('/')
    def index():
        """Main page route with error handling"""
        try:
            # Profile locations (legacy support)
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
            
            # Note: Profiles are now loaded via AJAX from /get_profiles endpoint
            # This keeps the initial page load fast
                
            return render_template('index.html', 
                                 profiles=[],  # Empty - loaded via AJAX
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
