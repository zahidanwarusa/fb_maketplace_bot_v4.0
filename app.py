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
        profiles.append({
            'folder_name': folder_name,
            'user_name': user_name,
            'path': profile_dir
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
        df = pd.read_csv('listings.csv')
        listings = df.to_dict('records')
    except FileNotFoundError:
        listings = []
    return render_template('index.html', 
                           profiles=profiles, 
                           listings=listings, 
                           profile_locations=profile_locations)

@app.route('/update_profile_location', methods=['POST'])
def update_profile_location():
    data = request.json
    profile_locations = load_profile_locations()
    profile_locations[data['profile']] = data['location']
    save_profile_locations(profile_locations)
    return jsonify({"status": "success"})

@app.route('/add_listing', methods=['POST'])
def add_listing():
    listing = request.json
    df = pd.DataFrame([listing])
    df.to_csv('listings.csv', mode='a', header=not os.path.exists('listings.csv'), index=False)
    return jsonify({"status": "success"})

@app.route('/delete_listing', methods=['POST'])
def delete_listing():
    index = request.json['index']
    try:
        df = pd.read_csv('listings.csv')
        df = df.drop(index)
        df.to_csv('listings.csv', index=False)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/run_bot', methods=['POST'])
def run_bot():
    selected_profiles = request.json['profiles']
    selected_listings = request.json['listings']
    profile_locations = load_profile_locations()
    
    # Save selected profiles to a temporary file with their locations
    with open('selected_profiles.txt', 'w') as f:
        for profile in selected_profiles:
            location = profile_locations.get(profile['folder_name'], "Default Location")
            f.write(f"{profile['path']}|{location}|{profile['user_name']}\n")
    
    # Save selected listings to a temporary CSV file
    df = pd.read_csv('listings.csv')
    selected_df = df.iloc[selected_listings]
    selected_df.to_csv('selected_listings.csv', index=False)
    
    # Run the existing bot script
    process = subprocess.Popen(['python', 'bot.py'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               universal_newlines=True)
    
    stdout, stderr = process.communicate()
    
    # Clean up temporary files
    os.remove('selected_profiles.txt')
    os.remove('selected_listings.csv')
    
    return jsonify({'stdout': stdout, 'stderr': stderr})

if __name__ == '__main__':
    app.run(debug=True)