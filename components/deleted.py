"""
Deleted Listings Component
Handles deleted listings management routes
"""

from flask import Blueprint, request, jsonify
import logging
import traceback

deleted_bp = Blueprint('deleted', __name__)
logger = logging.getLogger(__name__)


def init_deleted_routes(app, supabase):
    """Initialize deleted listings routes"""
    
    @app.route('/get_deleted_listings', methods=['GET'])
    def get_deleted_listings():
        try:
            response = supabase.table('listings').select('*').not_.is_('deleted_at', 'null').order('deleted_at', desc=True).execute()
            deleted_listings = []
            for item in response.data:
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
                    'deleted_at': item['deleted_at']
                }
                deleted_listings.append(listing)
            return jsonify({'status': 'success', 'deleted_listings': deleted_listings, 'count': len(deleted_listings)})
        except Exception as e:
            logger.error(f"Error getting deleted listings: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/restore_listing', methods=['POST'])
    def restore_listing():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'No listing ID provided'}), 400
            
            response = supabase.table('listings').update({'deleted_at': None}).eq('id', data['id']).execute()
            if not response.data:
                return jsonify({'status': 'error', 'message': 'Listing not found'}), 404
            return jsonify({'status': 'success', 'message': 'Listing restored'})
        except Exception as e:
            logger.error(f"Error restoring listing: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/permanently_delete_listing', methods=['POST'])
    def permanently_delete_listing():
        try:
            data = request.json
            if not data or 'id' not in data:
                return jsonify({'status': 'error', 'message': 'No listing ID provided'}), 400
            
            supabase.table('listings').delete().eq('id', data['id']).execute()
            return jsonify({'status': 'success', 'message': 'Listing permanently deleted'})
        except Exception as e:
            logger.error(f"Error permanently deleting listing: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
