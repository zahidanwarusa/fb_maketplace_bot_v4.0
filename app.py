from flask import Flask, render_template, request, jsonify
import pandas as pd
import subprocess
import os
import glob
import json

app = Flask(__name__)

def get_chrome_profiles():
    user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
    profiles = []
    profile_locations = load_profile_locations()
    
    # Read the Local State file to get profile names
    try:
        with open(os.path.join(user_data_dir, 'Local State'), 'r', encoding='utf-8') as f:
            local_state = json.load(f)
            profile_info = local_state.get('profile', {}).get('info_cache', {})
    except:
        profile_info = {}

    # Get all profile directories
    profile_dirs = glob.glob(os.path.join(user_data_dir, 'Profile *'))
    profile_dirs.append(os.path.join(user_data_dir, 'Default'))

    for profile_dir in profile_dirs:
        folder_name = os.path.basename(profile_dir)
        profile_id = folder_name if folder_name != 'Default' else 'Default'
        user_name = profile_info.get(profile_id, {}).get('name', 'Unknown')
        
        # Get location for this profile from profile_locations.json
        location = profile_locations.get(folder_name, '')
        
        profiles.append({
            'folder_name': folder_name,
            'user_name': user_name,
            'path': profile_dir,
            'location': location  # Add location to profile data
        })

    return profiles

def load_profile_locations():
    try:
        with open('profile_locations.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_profile_locations(locations):
    with open('profile_locations.json', 'w') as f:
        json.dump(locations, f, indent=2)

@app.route('/')
def index():
    profiles = get_chrome_profiles()
    profile_locations = load_profile_locations()
    try:
        # Read CSV with error handling
        df = pd.read_csv('listings.csv', encoding='utf-8')
        
        # Ensure all required columns exist
        required_columns = [
            'Year', 'Make', 'Model', 'Mileage', 'Price', 
            'Body Style', 'Exterior Color', 'Interior Color',
            'Vehicle Condition', 'Fuel Type', 'Transmission',
            'Description', 'Images Path'
        ]
        
        # Add any missing columns with empty values
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Convert to records
        listings = df[required_columns].to_dict('records')
        
        # Initialize selectedDay if needed
        for listing in listings:
            if 'selectedDay' not in listing:
                listing['selectedDay'] = ''
                
    except FileNotFoundError:
        listings = []
    except Exception as e:
        print(f"Error reading listings.csv: {str(e)}")
        listings = []
        
    return render_template('index.html', 
                         profiles=profiles, 
                         listings=listings, 
                         profile_locations=profile_locations)

@app.route('/update_profile_location', methods=['POST'])
def update_profile_location():
    try:
        data = request.json
        if not data or 'profile' not in data or 'location' not in data:
            return jsonify({"status": "error", "message": "Invalid data"}), 400
            
        profile_locations = load_profile_locations()
        profile_locations[data['profile']] = data['location']
        save_profile_locations(profile_locations)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/add_listing', methods=['POST'])
def add_listing():
    try:
        listing = request.json
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
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Create a clean listing dictionary with only the required fields
        clean_listing = {field: str(listing.get(field, '')) for field in required_fields}
        
        # Convert numeric fields
        try:
            clean_listing['Year'] = int(float(clean_listing['Year']))
            clean_listing['Mileage'] = int(float(clean_listing['Mileage']))
            clean_listing['Price'] = int(float(clean_listing['Price']))
        except ValueError as e:
            return jsonify({
                "status": "error",
                "message": f"Invalid numeric value: {str(e)}"
            }), 400
        
        # Convert to DataFrame
        df_new = pd.DataFrame([clean_listing])
        
        # If file exists, append; otherwise create new
        if os.path.exists('listings.csv'):
            try:
                df_existing = pd.read_csv('listings.csv', encoding='utf-8')
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Error reading existing listings: {str(e)}"
                }), 500
        else:
            df_combined = df_new
            
        # Save to CSV with proper encoding
        try:
            df_combined.to_csv('listings.csv', index=False, encoding='utf-8')
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error saving listings: {str(e)}"
            }), 500
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }), 500

@app.route('/delete_listing', methods=['POST'])
def delete_listing():
    try:
        index = request.json.get('index')
        if index is None:
            return jsonify({"status": "error", "message": "No index provided"}), 400
            
        df = pd.read_csv('listings.csv', encoding='utf-8')
        if index >= len(df):
            return jsonify({"status": "error", "message": "Invalid index"}), 400
            
        df = df.drop(index)
        df.to_csv('listings.csv', index=False, encoding='utf-8')
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/run_bot', methods=['POST'])
def run_bot():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
        
    try:
        selected_profiles = data.get('profiles', [])
        selected_listings = data.get('listings', [])
        listings_data = data.get('listingsData', [])
        
        if not selected_profiles or not selected_listings:
            return jsonify({
                "status": "error",
                "message": "No profiles or listings selected"
            }), 400
        
        profile_locations = load_profile_locations()
        
        # Save selected profiles to a temporary file with their locations
        with open('selected_profiles.txt', 'w', encoding='utf-8') as f:
            for profile in selected_profiles:
                location = profile.get('location', profile_locations.get(profile['folder_name'], "Default Location"))
                f.write(f"{profile['path']}|{location}|{profile['user_name']}\n")
        
        # Read original CSV and process selected listings
        df = pd.read_csv('listings.csv', encoding='utf-8')
        
        # Create a new DataFrame with only selected listings
        selected_indices = selected_listings
        selected_df = df.iloc[selected_indices].copy()
        
        # Update image paths with selected days from listingsData
        for i, index in enumerate(selected_indices):
            if i < len(listings_data):
                listing_data = listings_data[i]
                if 'selectedDay' in listing_data and listing_data['selectedDay']:
                    original_path = selected_df.iloc[i]['Images Path']
                    day_folder = listing_data['selectedDay']
                    # Create the full path including the day folder
                    new_path = os.path.join(original_path, day_folder)
                    selected_df.iloc[i, selected_df.columns.get_loc('Images Path')] = new_path
        
        # Save to temporary CSV
        selected_df.to_csv('selected_listings.csv', index=False, encoding='utf-8')
        
        # Run the bot script
        process = subprocess.Popen(
            ['python', 'bot.py'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        stdout, stderr = process.communicate()
        
        # Clean up temporary files
        try:
            os.remove('selected_profiles.txt')
            os.remove('selected_listings.csv')
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")
        
        return jsonify({
            'stdout': stdout,
            'stderr': stderr,
            'status': 'success'
        })
        
    except Exception as e:
        error_message = f"Error in run_bot: {str(e)}"
        print(error_message)
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 500

def initialize_files():
    # Create listings.csv if it doesn't exist
    if not os.path.exists('listings.csv'):
        default_columns = [
            'Year', 'Make', 'Model', 'Mileage', 'Price', 
            'Body Style', 'Exterior Color', 'Interior Color',
            'Vehicle Condition', 'Fuel Type', 'Transmission',
            'Description', 'Images Path', 'selectedDay'
        ]
        df = pd.DataFrame(columns=default_columns)
        df.to_csv('listings.csv', index=False, encoding='utf-8')
    
    # Create profile_locations.json if it doesn't exist
    if not os.path.exists('profile_locations.json'):
        with open('profile_locations.json', 'w') as f:
            json.dump({}, f)

if __name__ == '__main__':
    initialize_files()  # Initialize required files
    app.run(debug=True)