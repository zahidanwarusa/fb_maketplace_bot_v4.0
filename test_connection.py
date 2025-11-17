import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

print("Testing Supabase Connection...")
print("=" * 60)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Test 1: Count listings
    response = supabase.table('listings').select('id', count='exact').execute()
    print(f"✅ Listings table: {response.count} records")
    
    # Test 2: Count profile locations
    response = supabase.table('profile_locations').select('id', count='exact').execute()
    print(f"✅ Profile locations table: {response.count} records")
    
    # Test 3: Fetch sample listing
    response = supabase.table('listings').select('*').limit(1).execute()
    if response.data:
        print(f"✅ Sample listing found: {response.data[0]['year']} {response.data[0]['make']} {response.data[0]['model']}")
    
    # Test 4: Try to insert test data
    test_listing = {
        'year': 2020,
        'make': 'TestMake',
        'model': 'TestModel',
        'mileage': 50000,
        'price': 10000,
        'body_style': 'Sedan',
        'exterior_color': 'Blue',
        'interior_color': 'Black',
        'vehicle_condition': 'Good',
        'fuel_type': 'Gasoline',
        'transmission': 'Automatic transmission',
        'description': 'Test listing - will be deleted',
        'images_path': '/test/path'
    }
    
    insert_response = supabase.table('listings').insert(test_listing).execute()
    print(f"✅ Test insert successful! ID: {insert_response.data[0]['id']}")
    
    # Test 5: Delete test data
    test_id = insert_response.data[0]['id']
    supabase.table('listings').delete().eq('id', test_id).execute()
    print(f"✅ Test delete successful!")
    
    print("=" * 60)
    print("✅ All tests passed! Supabase is working perfectly!")
    print("=" * 60)
    
except Exception as e:
    print("=" * 60)
    print(f"❌ Error: {str(e)}")
    print("=" * 60)