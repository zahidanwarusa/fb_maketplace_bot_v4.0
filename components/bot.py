"""
Bot Component
Handles bot execution routes
"""

from flask import Blueprint, request, jsonify
import os
import subprocess
import pandas as pd
import logging
import traceback

# Create blueprint
bot_bp = Blueprint('bot', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_bot_routes(app, supabase, max_profile_selection, get_profile_locations_dict):
    """Initialize bot execution routes with app context"""
    
    @app.route('/run_bot', methods=['POST'])
    def run_bot():
        """Run the automation bot with selected profiles and listings"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400
            
            selected_profiles = data.get('profiles', [])
            selected_listings = data.get('listings', [])
            
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
            if len(selected_profiles) > max_profile_selection:
                logger.warning(f"Profile selection limit exceeded: {len(selected_profiles)} > {max_profile_selection}")
                return jsonify({
                    "status": "error",
                    "message": f"You can only select up to {max_profile_selection} profiles at a time. Currently selected: {len(selected_profiles)}"
                }), 400
            
            # Get profile locations from Supabase
            profile_locations = get_profile_locations_dict(supabase)
            
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
            
            # Fetch listings by IDs from Supabase
            try:
                selected_listings_data = []
                for listing_id in selected_listings:
                    response = supabase.table('listings').select('*').eq('id', listing_id).single().execute()
                    if response.data:
                        item = response.data
                        csv_row = {
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
                        selected_listings_data.append(csv_row)
            except Exception as e:
                logger.error(f"Failed to fetch listings from database: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to fetch listings: {str(e)}"
                }), 500
            
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
