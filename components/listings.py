"""
Listings Component
Handles vehicle listing management routes
"""

from flask import Blueprint, request, jsonify
import logging
import traceback
from datetime import datetime

listings_bp = Blueprint('listings', __name__)
logger = logging.getLogger(__name__)


def init_listings_routes(app, supabase):
    """Initialize listing management routes"""
    
    @app.route('/get_listings', methods=['GET'])
    def get_listings():
        try:
            response = supabase.table('listings').select('*').is_('deleted_at', 'null').order('id').execute()
            listings = []
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
                    'selectedDay': item.get('selected_day', ''),
                    'image_ids': item.get('image_ids', []),
                    'image_folder': item.get('image_folder', '')
                }
                listings.append(listing)
            return jsonify({'status': 'success', 'listings': listings})
        except Exception as e:
            logger.error(f"Error getting listings: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/add_listing', methods=['POST'])
    def add_listing():
        try:
            listing = request.json
            if not listing:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            
            listing_data = {
                'year': int(float(listing['Year'])),
                'make': str(listing['Make'])[:100],
                'model': str(listing['Model'])[:100],
                'mileage': int(float(listing['Mileage'])),
                'price': int(float(listing['Price'])),
                'body_style': str(listing['Body Style'])[:50],
                'exterior_color': str(listing['Exterior Color'])[:50],
                'interior_color': str(listing['Interior Color'])[:50],
                'vehicle_condition': str(listing['Vehicle Condition'])[:50],
                'fuel_type': str(listing['Fuel Type'])[:50],
                'transmission': str(listing['Transmission'])[:50],
                'description': str(listing['Description'])[:5000],
                'images_path': str(listing['Images Path'])[:500],
                'image_ids': listing.get('image_ids', []),
                'image_folder': str(listing.get('image_folder', ''))[:100]
            }
            
            response = supabase.table('listings').insert(listing_data).execute()
            return jsonify({"status": "success", "data": response.data})
        except Exception as e:
            logger.error(f"Error adding listing: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/update_listing', methods=['POST'])
    def update_listing():
        try:
            data = request.json
            if not data or not data.get('id'):
                return jsonify({"status": "error", "message": "No listing ID provided"}), 400
            
            update_data = {
                'year': int(float(data['Year'])),
                'make': str(data['Make'])[:100],
                'model': str(data['Model'])[:100],
                'mileage': int(float(data['Mileage'])),
                'price': int(float(data['Price'])),
                'body_style': str(data['Body Style'])[:50],
                'exterior_color': str(data['Exterior Color'])[:50],
                'interior_color': str(data['Interior Color'])[:50],
                'vehicle_condition': str(data['Vehicle Condition'])[:50],
                'fuel_type': str(data['Fuel Type'])[:50],
                'transmission': str(data['Transmission'])[:50],
                'description': str(data['Description'])[:5000],
                'images_path': str(data['Images Path'])[:500],
                'image_ids': data.get('image_ids', []),
                'image_folder': str(data.get('image_folder', ''))[:100]
            }
            
            response = supabase.table('listings').update(update_data).eq('id', data['id']).execute()
            if not response.data:
                return jsonify({"status": "error", "message": "Listing not found"}), 404
            return jsonify({"status": "success", "data": response.data})
        except Exception as e:
            logger.error(f"Error updating listing: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/delete_listing', methods=['POST'])
    def delete_listing():
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400
            
            listing_id = data.get('index')
            if listing_id is None:
                return jsonify({"status": "error", "message": "No listing ID provided"}), 400
            
            delete_response = supabase.table('listings').update({'deleted_at': datetime.utcnow().isoformat()}).eq('id', listing_id).execute()
            if not delete_response.data:
                return jsonify({"status": "error", "message": "Listing not found"}), 404
            
            return jsonify({"status": "success", "message": "Listing moved to deleted listings"})
        except Exception as e:
            logger.error(f"Error deleting listing: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
