# Enhanced Upload Tracking Functions
# Replace the existing start_upload_tracking and complete_upload_tracking functions in app.py

def start_upload_tracking(profile_name, profile_folder, listing_data, location, facebook_account_name=None, facebook_account_email=None):
    """
    Helper function to start tracking an upload with Facebook account info
    Call this when the bot starts uploading a listing
    
    Args:
        profile_name: Name of the Chrome profile
        profile_folder: Folder name of the Chrome profile
        listing_data: Dictionary containing listing information
        location: Location for the listing
        facebook_account_name: Name of the Facebook account being used
        facebook_account_email: Email of the Facebook account being used
    
    Returns: upload_id that can be used to update status later
    """
    try:
        vehicle_info = {
            'year': listing_data.get('Year'),
            'make': listing_data.get('Make'),
            'model': listing_data.get('Model'),
            'price': listing_data.get('Price'),
            'mileage': listing_data.get('Mileage'),
            'body_style': listing_data.get('Body Style'),
            'exterior_color': listing_data.get('Exterior Color'),
            'interior_color': listing_data.get('Interior Color'),
            'vehicle_condition': listing_data.get('Vehicle Condition'),
            'fuel_type': listing_data.get('Fuel Type'),
            'transmission': listing_data.get('Transmission'),
            'description': listing_data.get('Description')
        }
        
        upload_record = {
            'profile_name': profile_name,
            'profile_folder': profile_folder,
            'facebook_account_name': facebook_account_name,
            'facebook_account_email': facebook_account_email,
            'listing_id': listing_data.get('id'),
            'vehicle_info': vehicle_info,
            'status': 'in_progress',
            'location': location,
            'upload_datetime': datetime.utcnow().isoformat()
        }
        
        response = supabase.table('upload_history').insert(upload_record).execute()
        
        if response.data:
            return response.data[0]['id']
        return None
        
    except Exception as e:
        print(f"Error starting upload tracking: {e}")
        return None


def complete_upload_tracking(upload_id, success=True, marketplace_url=None, error_message=None):
    """
    Helper function to mark an upload as complete
    Call this when the bot finishes uploading (success or failure)
    
    Args:
        upload_id: ID of the upload record
        success: Whether the upload was successful
        marketplace_url: URL of the posted listing (if successful)
        error_message: Error message (if failed)
    """
    try:
        update_data = {
            'status': 'success' if success else 'failed',
            'completed_datetime': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if marketplace_url:
            update_data['marketplace_url'] = marketplace_url
            
        if error_message:
            update_data['error_message'] = error_message
        
        supabase.table('upload_history')\
            .update(update_data)\
            .eq('id', upload_id)\
            .execute()
        
        return True
        
    except Exception as e:
        print(f"Error completing upload tracking: {e}")
        return False
