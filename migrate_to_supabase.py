"""
Migration script to transfer data from CSV/JSON files to Supabase
Run this once after setting up your Supabase database with the schema
"""

import pandas as pd
import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY in your .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def migrate_listings():
    """Migrate listings from CSV to Supabase"""
    print("Starting listings migration...")
    
    try:
        # Read CSV file
        if not os.path.exists('listings.csv'):
            print("No listings.csv file found. Skipping listings migration.")
            return
        
        df = pd.read_csv('listings.csv', encoding='utf-8')
        
        if df.empty:
            print("No listings to migrate.")
            return
        
        # Convert DataFrame to list of dictionaries
        listings_data = []
        for _, row in df.iterrows():
            listing = {
                'year': int(row['Year']) if pd.notna(row['Year']) else None,
                'make': str(row['Make']) if pd.notna(row['Make']) else '',
                'model': str(row['Model']) if pd.notna(row['Model']) else '',
                'mileage': int(row['Mileage']) if pd.notna(row['Mileage']) else 0,
                'price': int(row['Price']) if pd.notna(row['Price']) else 0,
                'body_style': str(row['Body Style']) if pd.notna(row['Body Style']) else '',
                'exterior_color': str(row['Exterior Color']) if pd.notna(row['Exterior Color']) else '',
                'interior_color': str(row['Interior Color']) if pd.notna(row['Interior Color']) else '',
                'vehicle_condition': str(row['Vehicle Condition']) if pd.notna(row['Vehicle Condition']) else '',
                'fuel_type': str(row['Fuel Type']) if pd.notna(row['Fuel Type']) else '',
                'transmission': str(row['Transmission']) if pd.notna(row['Transmission']) else '',
                'description': str(row['Description']) if pd.notna(row['Description']) else '',
                'images_path': str(row['Images Path']) if pd.notna(row['Images Path']) else '',
                'selected_day': str(row['selectedDay']) if 'selectedDay' in row and pd.notna(row['selectedDay']) else None
            }
            listings_data.append(listing)
        
        # Insert into Supabase
        response = supabase.table('listings').insert(listings_data).execute()
        
        print(f"✓ Successfully migrated {len(listings_data)} listings to Supabase")
        
    except Exception as e:
        print(f"✗ Error migrating listings: {str(e)}")
        raise

def migrate_profile_locations():
    """Migrate profile locations from JSON to Supabase"""
    print("Starting profile locations migration...")
    
    try:
        # Read JSON file
        if not os.path.exists('profile_locations.json'):
            print("No profile_locations.json file found. Skipping profile locations migration.")
            return
        
        with open('profile_locations.json', 'r') as f:
            profile_locations = json.load(f)
        
        if not profile_locations:
            print("No profile locations to migrate.")
            return
        
        # Convert to list of dictionaries
        locations_data = [
            {
                'profile_name': profile_name,
                'location': location
            }
            for profile_name, location in profile_locations.items()
        ]
        
        # Insert into Supabase
        response = supabase.table('profile_locations').insert(locations_data).execute()
        
        print(f"✓ Successfully migrated {len(locations_data)} profile locations to Supabase")
        
    except Exception as e:
        print(f"✗ Error migrating profile locations: {str(e)}")
        raise

def verify_migration():
    """Verify the migration was successful"""
    print("\nVerifying migration...")
    
    try:
        # Check listings count
        listings_response = supabase.table('listings').select('id', count='exact').execute()
        listings_count = listings_response.count
        print(f"✓ Listings in database: {listings_count}")
        
        # Check profile locations count
        locations_response = supabase.table('profile_locations').select('id', count='exact').execute()
        locations_count = locations_response.count
        print(f"✓ Profile locations in database: {locations_count}")
        
        print("\n✓ Migration verification complete!")
        
    except Exception as e:
        print(f"✗ Error during verification: {str(e)}")
        raise

def main():
    print("=" * 60)
    print("Facebook Marketplace Automation - Data Migration")
    print("=" * 60)
    print()
    
    try:
        # Migrate data
        migrate_listings()
        migrate_profile_locations()
        
        # Verify migration
        verify_migration()
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Verify your data in Supabase dashboard")
        print("2. Update your app.py to use the new Supabase integration")
        print("3. Optional: Backup and remove listings.csv and profile_locations.json")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("Migration failed!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print("\nPlease fix the error and try again.")

if __name__ == '__main__':
    main()
