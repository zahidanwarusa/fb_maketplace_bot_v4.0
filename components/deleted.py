"""
Deleted Listings Component
Handles deleted listings management routes (view, restore, permanent delete)
"""

from flask import Blueprint, request, jsonify
import logging
import traceback

# Create blueprint
deleted_bp = Blueprint('deleted', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_deleted_routes(app, supabase):
    """Initialize deleted listings routes with app context"""
    
    @app.route('/get_deleted_listings', methods=['GET'])
    def get_deleted_listings():
        """Get all soft-deleted listings"""
        try:
            # Fetch deleted listings
            response = supabase.table('listings')\
                .select('*')\
                .not_.is_('deleted_at', 'null')\
                .order('deleted_at', desc=True)\
                .execute()
            
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
            
            return jsonify({
                'status': 'success',
                'deleted_listings': deleted_listings,
                'count': len(deleted_listings)
            })
            
        except Exception as e:
            logger.error(f"Error getting deleted listings: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get deleted listings: {str(e)}'
            }), 500

    @app.route('/restore_listing', methods=['POST'])
    def restore_listing():
        """Restore a soft-deleted listing"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'No listing ID provided'
                }), 400
            
            listing_id = data['id']
            
            # Restore the listing by setting deleted_at to NULL
            response = supabase.table('listings')\
                .update({'deleted_at': None})\
                .eq('id', listing_id)\
                .execute()
            
            if not response.data:
                return jsonify({
                    'status': 'error',
                    'message': 'Listing not found or already restored'
                }), 404
            
            logger.info(f"Successfully restored listing ID: {listing_id}")
            return jsonify({
                'status': 'success',
                'message': 'Listing restored successfully',
                'listing': response.data[0]
            })
            
        except Exception as e:
            logger.error(f"Error restoring listing: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to restore listing: {str(e)}'
            }), 500

    @app.route('/permanently_delete_listing', methods=['POST'])
    def permanently_delete_listing():
        """Permanently delete a listing (cannot be undone)"""
        try:
            data = request.json
            
            if not data or 'id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'No listing ID provided'
                }), 400
            
            listing_id = data['id']
            
            # Permanently delete from database
            response = supabase.table('listings')\
                .delete()\
                .eq('id', listing_id)\
                .execute()
            
            logger.info(f"Permanently deleted listing ID: {listing_id}")
            return jsonify({
                'status': 'success',
                'message': 'Listing permanently deleted'
            })
            
        except Exception as e:
            logger.error(f"Error permanently deleting listing: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to permanently delete listing: {str(e)}'
            }), 500
