"""
Test Scheduler Diagnostic Script
Run this to check if the scheduler can find and process pending posts
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Missing Supabase credentials")
    sys.exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓ Connected to Supabase")
except Exception as e:
    print(f"✗ Failed to connect to Supabase: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("SCHEDULER DIAGNOSTIC TEST")
print("=" * 60)

# Get current time (local)
now = datetime.now()
print(f"\nCurrent Local Time: {now.isoformat()}")
print(f"Checking for posts due before: {(now + timedelta(minutes=2)).isoformat()}")

# Get all scheduled posts
print("\n--- ALL SCHEDULED POSTS ---")
try:
    all_posts = supabase.table('scheduled_posts').select('*').execute()
    if all_posts.data:
        print(f"Total scheduled posts in database: {len(all_posts.data)}")
        for post in all_posts.data:
            print(f"\nPost #{post['id']}:")
            print(f"  Status: {post['status']}")
            print(f"  Listing ID: {post['listing_id']}")
            print(f"  Profile: {post['profile_name']}")
            print(f"  Scheduled: {post['next_run_datetime']}")
            print(f"  Recurrence: {post.get('recurrence', 'none')}")

            # Parse the scheduled time
            try:
                scheduled_time = datetime.fromisoformat(post['next_run_datetime'].replace('Z', '+00:00'))
                if scheduled_time.tzinfo:
                    scheduled_time = scheduled_time.replace(tzinfo=None)
                time_diff = (scheduled_time - now).total_seconds()
                if time_diff < 0:
                    print(f"  ⚠️  OVERDUE by {abs(int(time_diff))} seconds")
                else:
                    print(f"  ⏰ Due in {int(time_diff)} seconds")
            except Exception as e:
                print(f"  ⚠️  Could not parse time: {e}")
    else:
        print("No scheduled posts found in database")
except Exception as e:
    print(f"Error fetching posts: {e}")

# Get pending posts
print("\n--- PENDING POSTS ---")
try:
    pending_posts = supabase.table('scheduled_posts').select('*').eq('status', 'pending').execute()
    if pending_posts.data:
        print(f"Pending posts: {len(pending_posts.data)}")
        for post in pending_posts.data:
            print(f"  Post #{post['id']}: scheduled for {post['next_run_datetime']}")
    else:
        print("No pending posts found")
except Exception as e:
    print(f"Error fetching pending posts: {e}")

# Get due posts (same logic as scheduler)
print("\n--- DUE POSTS (What scheduler would find) ---")
try:
    check_time = (now + timedelta(minutes=2)).isoformat()
    due_posts = supabase.table('scheduled_posts').select('*').eq('status', 'pending').lte('next_run_datetime', check_time).execute()

    if due_posts.data:
        print(f"Posts ready to execute: {len(due_posts.data)}")
        for post in due_posts.data:
            print(f"\n  Post #{post['id']}:")
            print(f"    Listing: {post['listing_id']}")
            print(f"    Profile: {post['profile_name']}")
            print(f"    Profile Path: {post.get('profile_folder') or post.get('profile_path')}")
            print(f"    Location: {post.get('location')}")
            print(f"    Scheduled: {post['next_run_datetime']}")

            # Validate required fields
            errors = []
            if not post.get('profile_folder') and not post.get('profile_path'):
                errors.append("Missing profile_folder/profile_path")
            if not post.get('location'):
                errors.append("Missing location")
            if not post.get('listing_id'):
                errors.append("Missing listing_id")

            if errors:
                print(f"    ⚠️  VALIDATION ERRORS: {', '.join(errors)}")
            else:
                print(f"    ✓ All required fields present")
    else:
        print("No posts due for execution")
        print("This could mean:")
        print("  1. All scheduled posts are in the future")
        print("  2. No posts have 'pending' status")
        print("  3. Timestamps are incorrectly formatted")
except Exception as e:
    print(f"Error checking due posts: {e}")
    import traceback
    traceback.print_exc()

# Check for required files
print("\n--- CHECKING BOT FILES ---")
files_to_check = ['Bot.py', 'bot_config.py', 'bot_helpers.py', 'bot_processor.py']
for file in files_to_check:
    if os.path.exists(file):
        print(f"✓ {file}")
    else:
        print(f"✗ {file} NOT FOUND")

print("\n" + "=" * 60)
print("DIAGNOSTIC TEST COMPLETE")
print("=" * 60)

# Provide recommendations
print("\nRECOMMENDATIONS:")
if not due_posts.data:
    print("• Schedule a post for 1-2 minutes in the future to test")
    print("• Make sure the scheduled time is in the future (use UTC time)")
else:
    print("• Due posts found! Start the scheduler to execute them")
    print("• Run: python scheduler_service.py")
    print("• Or use the 'Start Scheduler' button in the web interface")
