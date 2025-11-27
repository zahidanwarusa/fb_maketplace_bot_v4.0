"""
Profiles Component
Handles Edge profile management routes (CRUD operations for profiles stored in database)
"""

from flask import Blueprint, request, jsonify
import os
import logging
import traceback
from datetime import datetime

# Create blueprint
profiles_bp = Blueprint('profiles', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_profiles_routes(app, supabase):
    """Initialize profile management routes with app context"""
    
    @app.route('/get_profiles', methods=['GET'])
    def get_profiles():
        """Get all Edge profiles from database"""
        try:
            response = supabase.table('edge_profiles').select('*').is_('deleted_at', 'null').order('created_at', desc=True).execute()
            
            profiles = []
            for item in response.data:
                profile = {
                    'id': item['id'],
                    'profile_name': item['profile_name'],
                    'profile_path': item['profile_path'],
                    'location': item.get('location', ''),
                    'is_active': item.get('is_active', True),
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at')
                }
                profiles.append(profile)
            
            logger.info(f"Retrieved {len(profiles)} Edge profiles from database")
            return jsonify({
                'status': 'success',
                'profiles': profiles,
                'count': len(profiles)
            })
            
        except Exception as e:
            logger.error(f"Error getting profiles: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get profiles: {str(e)}'
            }), 500

    @app.route('/add_profile', methods=['POST'])
    def add_profile():
        """Add a new Edge profile to the database"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
            
            # Validate required fields
            if not data.get('profile_name') or not data.get('profile_path'):
                return jsonify({
                    'status': 'error',
                    'message': 'Profile name and path are required'
                }), 400
            
            # Check if profile name already exists
            existing = supabase.table('edge_profiles').select('id').eq('profile_name', data['profile_name']).is_('deleted_at', 'null').execute()
            if existing.data:
                return jsonify({
                    'status': 'error',
                    'message': 'A profile with this name already exists'
                }), 400
            
            # Prepare profile data
            profile_data = {
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data['profile_path'])[:500],
                'location': str(data.get('location', ''))[:200],
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Insert into database
            response = supabase.table('edge_profiles').insert(profile_data).execute()
            
            if response.data:
                logger.info(f"Successfully added profile: {data['profile_name']}")
                return jsonify({
                    'status': 'success',
                    'message': 'Profile added successfully',
                    'profile': response.data[0]
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to add profile'
                }), 500
                
        except Exception as e:
            logger.error(f"Error adding profile: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to add profile: {str(e)}'
            }), 500

    @app.route('/update_profile', methods=['POST'])
    def update_profile():
        """Update an existing Edge profile"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile ID is required'
                }), 400
            
            profile_id = data['id']
            
            # Validate required fields
            if not data.get('profile_name') or not data.get('profile_path'):
                return jsonify({
                    'status': 'error',
                    'message': 'Profile name and path are required'
                }), 400
            
            # Check if another profile with same name exists
            existing = supabase.table('edge_profiles').select('id').eq('profile_name', data['profile_name']).neq('id', profile_id).is_('deleted_at', 'null').execute()
            if existing.data:
                return jsonify({
                    'status': 'error',
                    'message': 'Another profile with this name already exists'
                }), 400
            
            # Prepare update data
            update_data = {
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data['profile_path'])[:500],
                'location': str(data.get('location', ''))[:200],
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Update in database
            response = supabase.table('edge_profiles').update(update_data).eq('id', profile_id).execute()
            
            if response.data:
                logger.info(f"Successfully updated profile ID: {profile_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Profile updated successfully',
                    'profile': response.data[0]
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile not found'
                }), 404
                
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to update profile: {str(e)}'
            }), 500

    @app.route('/delete_profile', methods=['POST'])
    def delete_profile():
        """Soft delete an Edge profile"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile ID is required'
                }), 400
            
            profile_id = data['id']
            
            # Soft delete by setting deleted_at
            response = supabase.table('edge_profiles').update({
                'deleted_at': datetime.utcnow().isoformat()
            }).eq('id', profile_id).execute()
            
            if response.data:
                logger.info(f"Successfully deleted profile ID: {profile_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Profile deleted successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile not found'
                }), 404
                
        except Exception as e:
            logger.error(f"Error deleting profile: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to delete profile: {str(e)}'
            }), 500

    @app.route('/update_profile_location', methods=['POST'])
    def update_profile_location():
        """Update location for a profile"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile ID is required'
                }), 400
            
            profile_id = data['id']
            location = data.get('location', '')
            
            # Update location
            response = supabase.table('edge_profiles').update({
                'location': str(location)[:200],
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', profile_id).execute()
            
            if response.data:
                logger.info(f"Updated location for profile ID: {profile_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Location updated successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile not found'
                }), 404
                
        except Exception as e:
            logger.error(f"Error updating profile location: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to update location: {str(e)}'
            }), 500

    @app.route('/toggle_profile_active', methods=['POST'])
    def toggle_profile_active():
        """Toggle profile active status"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile ID is required'
                }), 400
            
            profile_id = data['id']
            is_active = data.get('is_active', True)
            
            response = supabase.table('edge_profiles').update({
                'is_active': is_active,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', profile_id).execute()
            
            if response.data:
                status_text = 'activated' if is_active else 'deactivated'
                logger.info(f"Profile ID {profile_id} {status_text}")
                return jsonify({
                    'status': 'success',
                    'message': f'Profile {status_text} successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Profile not found'
                }), 404
                
        except Exception as e:
            logger.error(f"Error toggling profile status: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to toggle profile status: {str(e)}'
            }), 500

    @app.route('/validate_profile_path', methods=['POST'])
    def validate_profile_path():
        """Validate if a profile path exists on the system"""
        try:
            data = request.json
            
            if not data or 'path' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Path is required'
                }), 400
            
            path = data['path']
            exists = os.path.exists(path)
            is_directory = os.path.isdir(path) if exists else False
            
            return jsonify({
                'status': 'success',
                'exists': exists,
                'is_directory': is_directory,
                'path': path
            })
            
        except Exception as e:
            logger.error(f"Error validating path: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to validate path: {str(e)}'
            }), 500
