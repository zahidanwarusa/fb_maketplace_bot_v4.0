"""
Profiles Component
Handles Chrome profile management routes including locations and notifications
"""

from flask import Blueprint, request, jsonify
import os
import logging
import traceback
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime

# Create blueprint
profiles_bp = Blueprint('profiles', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_profiles_routes(app, supabase):
    """Initialize profile management routes with app context"""
    
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

    @app.route('/check_notifications/<profile_folder>', methods=['GET'])
    def check_notifications(profile_folder):
        """Check Facebook notifications for a specific profile"""
        try:
            logger.info(f"Checking notifications for profile: {profile_folder}")
            
            # Get profile path
            user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
            profile_path = os.path.join(user_data_dir, profile_folder)
            
            if not os.path.exists(profile_path):
                return jsonify({
                    'status': 'error',
                    'message': 'Profile not found'
                }), 404
            
            # Setup Chrome options
            options = Options()
            options.add_argument(f"user-data-dir={user_data_dir}")
            options.add_argument(f"profile-directory={profile_folder}")
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument('--disable-notifications')
            
            driver = None
            notifications = []
            notification_count = 0
            
            try:
                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(30)
                
                logger.info("Navigating to Facebook notifications...")
                driver.get("https://www.facebook.com/notifications")
                time.sleep(5)
                
                # Check if logged in
                if "login" in driver.current_url.lower():
                    logger.warning(f"Profile {profile_folder} is not logged into Facebook")
                    return jsonify({
                        'status': 'error',
                        'message': 'Not logged into Facebook',
                        'notification_count': 0,
                        'notifications': []
                    })
                
                # Get notification count
                try:
                    notification_badge = driver.find_element(By.CSS_SELECTOR, 
                        '[aria-label*="Notifications"] span[data-visualcompletion="css-img"]')
                    notification_count_text = notification_badge.text.strip()
                    
                    if notification_count_text.endswith('+'):
                        notification_count = int(notification_count_text[:-1])
                    elif notification_count_text.isdigit():
                        notification_count = int(notification_count_text)
                    else:
                        notification_count = 0
                        
                    logger.info(f"Found {notification_count} notifications")
                except Exception as e:
                    logger.warning(f"Could not find notification badge: {str(e)}")
                    notification_count = 0
                
                # Get notification items
                try:
                    notification_items = driver.find_elements(By.CSS_SELECTOR, '[role="article"]')[:10]
                    
                    for item in notification_items:
                        try:
                            text_element = item.find_element(By.CSS_SELECTOR, '[dir="auto"]')
                            notification_text = text_element.text.strip()
                            is_unread = "background-color" in item.get_attribute("style")
                            
                            try:
                                time_element = item.find_element(By.CSS_SELECTOR, 'span[class*="x1"] span:last-child')
                                time_text = time_element.text.strip()
                            except:
                                time_text = "Unknown time"
                            
                            notifications.append({
                                'text': notification_text[:200],
                                'is_unread': is_unread,
                                'time': time_text
                            })
                        except Exception as e:
                            logger.warning(f"Error parsing notification item: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Could not extract notification details: {str(e)}")
                
                # Store in database
                notification_record = {
                    'profile_folder': profile_folder,
                    'notification_count': notification_count,
                    'last_checked': datetime.utcnow().isoformat(),
                    'notifications': notifications
                }
                
                try:
                    supabase.table('profile_notifications').upsert(
                        notification_record, 
                        on_conflict='profile_folder'
                    ).execute()
                except Exception as e:
                    logger.warning(f"Could not store notifications in database: {str(e)}")
                
                return jsonify({
                    'status': 'success',
                    'notification_count': notification_count,
                    'notifications': notifications[:5],
                    'last_checked': notification_record['last_checked']
                })
                
            finally:
                if driver:
                    driver.quit()
                    
        except Exception as e:
            logger.error(f"Error checking notifications: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to check notifications: {str(e)}'
            }), 500

    @app.route('/get_profile_notifications/<profile_folder>', methods=['GET'])
    def get_profile_notifications(profile_folder):
        """Get cached notification data for a profile"""
        try:
            response = supabase.table('profile_notifications')\
                .select('*')\
                .eq('profile_folder', profile_folder)\
                .execute()
            
            if response.data:
                return jsonify({
                    'status': 'success',
                    'data': response.data[0]
                })
            else:
                return jsonify({
                    'status': 'success',
                    'data': {
                        'notification_count': 0,
                        'last_checked': None,
                        'notifications': []
                    }
                })
                
        except Exception as e:
            logger.error(f"Error getting profile notifications: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/get_all_notifications', methods=['GET'])
    def get_all_notifications():
        """Get notification status for all profiles"""
        try:
            response = supabase.table('profile_notifications')\
                .select('*')\
                .order('last_checked', desc=True)\
                .execute()
            
            return jsonify({
                'status': 'success',
                'notifications': response.data
            })
            
        except Exception as e:
            logger.error(f"Error getting all notifications: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
