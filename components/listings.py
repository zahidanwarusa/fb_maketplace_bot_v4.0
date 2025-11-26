"""
Listings Component
Handles vehicle listing management routes (CRUD operations)
"""

from flask import Blueprint, request, jsonify
import logging
import traceback
from datetime import datetime

# Create blueprint
listings_bp = Blueprint('listings', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_listings_routes(app, supabase):
    """Initialize listing management routes with app context"""
    
    @app.route('/get_listings', methods=['GET'])
    def get_listings():
        """Get all active listings"""
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
            
            return jsonify({
                'status': 'success',
                'listings': listings
            })
        except Exception as e:
            logger.error(f"Error getting listings: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

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
                'images_path': str(listing['Images Path'])[:500],
                'image_ids': listing.get('image_ids', []),
                'image_folder': str(listing.get('image_folder', ''))[:100]
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
                'images_path': str(data['Images Path'])[:500],
                'image_ids': data.get('image_ids', []),
                'image_folder': str(data.get('image_folder', ''))[:100]
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
        """Soft delete a listing (moves to deleted listings)"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400
                
            listing_id = data.get('index')
            
            if listing_id is None:
                return jsonify({
                    "status": "error",
                    "message": "No listing ID provided"
                }), 400
            
            # Validate ID
            try:
                listing_id = int(listing_id)
                if listing_id < 0:
                    return jsonify({
                        "status": "error",
                        "message": "Invalid ID: must be non-negative"
                    }), 400
            except ValueError:
                return jsonify({
                    "status": "error",
                    "message": "Invalid ID format"
                }), 400
            
            # Soft delete by setting deleted_at timestamp
            delete_response = supabase.table('listings')\
                .update({'deleted_at': datetime.utcnow().isoformat()})\
                .eq('id', listing_id)\
                .execute()
            
            if not delete_response.data:
                return jsonify({
                    "status": "error",
                    "message": "Listing not found"
                }), 404
            
            logger.info(f"Soft deleted listing ID: {listing_id}")
            return jsonify({
                "status": "success",
                "message": "Listing moved to deleted listings"
            })
            
        except Exception as e:
            logger.error(f"Error in delete_listing: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": f"Failed to delete listing: {str(e)}"
            }), 500
