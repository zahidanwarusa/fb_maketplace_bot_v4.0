"""
Apply enhanced schema for upload history tracking and scheduling
Run this script to update your Supabase database
"""

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

def apply_schema():
    """Apply the enhanced schema to Supabase"""
    print("=" * 60)
    print("Applying Enhanced Schema for Upload Tracking & Scheduling")
    print("=" * 60)
    print()
    
    print("NOTE: You need to run the SQL file manually in Supabase SQL Editor")
    print("Location: /home/claude/enhanced_schema.sql")
    print()
    print("Steps to apply:")
    print("1. Go to your Supabase dashboard")
    print("2. Navigate to SQL Editor")
    print("3. Copy and paste the contents of enhanced_schema.sql")
    print("4. Click 'Run' to execute the SQL")
    print()
    print("After applying the schema, verify by checking:")
    print("- upload_history table has new columns (facebook_account_name, facebook_account_email)")
    print("- scheduled_posts table exists")
    print("- Views are created (upload_history_detailed, scheduled_posts_detailed)")
    print()
    
    # Test if we can access the tables
    try:
        print("Testing database connection...")
        
        # Test upload_history
        response = supabase.table('upload_history').select('id', count='exact').limit(1).execute()
        print(f"✅ upload_history table accessible ({response.count} records)")
        
        # Test scheduled_posts (might not exist yet)
        try:
            response = supabase.table('scheduled_posts').select('id', count='exact').limit(1).execute()
            print(f"✅ scheduled_posts table accessible ({response.count} records)")
        except:
            print("⚠️  scheduled_posts table not found - please apply the schema")
        
        print()
        print("=" * 60)
        print("Schema check complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error accessing database: {str(e)}")
        print()
        print("Please make sure:")
        print("1. Your Supabase credentials are correct")
        print("2. The schema has been applied via SQL Editor")

if __name__ == '__main__':
    apply_schema()
