"""
Profiles Component
Handles Edge profile management routes
"""

from flask import Blueprint, request, jsonify
import os
import logging
import traceback
from datetime import datetime

profiles_bp = Blueprint('profiles', __name__)
logger = logging.getLogger(__name__)


def init_profiles_routes(app, supabase):
    """Initialize profile management routes"""
    
    @app.route('/get_profiles', methods=['GET'])
    def get_profiles():
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
            return jsonify({'status': 'success', 'profiles': profiles, 'count': len(profiles)})
        except Exception as e:
            logger.error(f"Error getting profiles: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/add_profile', methods=['POST'])
    def add_profile():
        try:
            data = request.json
            if not data or not data.get('profile_name') or not data.get('profile_path'):
                return jsonify({'status': 'error', 'message': 'Profile name and path are required'}), 400
            
            existing = supabase.table('edge_profiles').select('id').eq('profile_name', data['profile_name']).is_('deleted_at', 'null').execute()
            if existing.data:
                return jsonify({'status': 'error', 'message': 'A profile with this name already exists'}), 400
            
            profile_data = {
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data['profile_path'])[:500],
                'location': str(data.get('location', ''))[:200],
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('edge_profiles').insert(profile_data).execute()
            if response.data:
                return jsonify({'status': 'success', 'message': 'Profile added successfully', 'profile': response.data[0]})
            return jsonify({'status': 'error', 'message': 'Failed to add profile'}), 500
        except Exception as e:
            logger.error(f"Error adding profile: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/update_profile', methods=['POST'])
    def update_profile():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
            
            update_data = {
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data['profile_path'])[:500],
                'location': str(data.get('location', ''))[:200],
                'updated_at': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('edge_profiles').update(update_data).eq('id', data['id']).execute()
            if response.data:
                return jsonify({'status': 'success', 'message': 'Profile updated', 'profile': response.data[0]})
            return jsonify({'status': 'error', 'message': 'Profile not found'}), 404
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/delete_profile', methods=['POST'])
    def delete_profile():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
            
            response = supabase.table('edge_profiles').update({'deleted_at': datetime.utcnow().isoformat()}).eq('id', data['id']).execute()
            if response.data:
                return jsonify({'status': 'success', 'message': 'Profile deleted'})
            return jsonify({'status': 'error', 'message': 'Profile not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting profile: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/update_profile_location', methods=['POST'])
    def update_profile_location():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
            
            response = supabase.table('edge_profiles').update({
                'location': str(data.get('location', ''))[:200],
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', data['id']).execute()
            
            if response.data:
                return jsonify({'status': 'success', 'message': 'Location updated'})
            return jsonify({'status': 'error', 'message': 'Profile not found'}), 404
        except Exception as e:
            logger.error(f"Error updating location: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/toggle_profile_active', methods=['POST'])
    def toggle_profile_active():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
            
            response = supabase.table('edge_profiles').update({
                'is_active': data.get('is_active', True),
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', data['id']).execute()
            
            if response.data:
                return jsonify({'status': 'success', 'message': 'Profile status updated'})
            return jsonify({'status': 'error', 'message': 'Profile not found'}), 404
        except Exception as e:
            logger.error(f"Error toggling profile: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/validate_profile_path', methods=['POST'])
    def validate_profile_path():
        try:
            data = request.json
            if not data or 'path' not in data:
                return jsonify({'status': 'error', 'message': 'Path is required'}), 400
            
            path = data['path']
            exists = os.path.exists(path)
            is_directory = os.path.isdir(path) if exists else False
            
            return jsonify({'status': 'success', 'exists': exists, 'is_directory': is_directory, 'path': path})
        except Exception as e:
            logger.error(f"Error validating path: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
