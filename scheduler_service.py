"""
Scheduler Service
Runs in the background to check for and execute scheduled posts
"""

import os
import sys
import time
import logging
import json
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials")
    raise ValueError("Missing Supabase credentials")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized")
except Exception as e:
    logger.error(f"Failed to initialize Supabase: {str(e)}")
    raise

# Configuration
CHECK_INTERVAL = 60  # Check every 60 seconds
STOP_FILE = 'scheduler_stop_signal.txt'


def get_due_scheduled_posts():
    """Get scheduled posts that are due to run"""
    try:
        # Use local time instead of UTC
        now = datetime.now()
        logger.debug(f"Checking for posts due before: {now.isoformat()} (Local Time)")

        # Get all pending posts where next_run_datetime is in the past or within the next minute
        # Add a small buffer (2 minutes) to account for timing
        check_time = (now + timedelta(minutes=2)).isoformat()

        response = supabase.table('scheduled_posts').select('*').eq('status', 'pending').lte('next_run_datetime', check_time).execute()

        if response.data:
            logger.info(f"Found {len(response.data)} pending post(s)")
            for post in response.data:
                logger.info(f"  Post #{post['id']}: scheduled for {post['next_run_datetime']}")
        else:
            logger.debug("No pending posts found")

        return response.data
    except Exception as e:
        logger.error(f"Error fetching scheduled posts: {str(e)}")
        return []


def execute_scheduled_post(post):
    """Execute a single scheduled post"""
    try:
        logger.info(f"Executing scheduled post ID: {post['id']}")

        # Note: We don't update status to 'running' because the database constraint
        # only allows: pending, completed, failed, cancelled
        # The post will go directly from pending -> completed or pending -> failed

        # Get listing data
        listing_response = supabase.table('listings').select('*').eq('id', post['listing_id']).single().execute()

        if not listing_response.data:
            raise ValueError(f"Listing {post['listing_id']} not found")

        listing = listing_response.data

        # Prepare profile data
        profile_path = post.get('profile_folder') or post.get('profile_path', '')
        profile_name = post.get('profile_name', '')
        location = post.get('location', '')

        if not profile_path or not location:
            raise ValueError("Missing profile path or location")

        # Create temporary files for bot execution
        with open('selected_profiles.txt', 'w', encoding='utf-8') as f:
            f.write(f"{profile_path}|{location}|{profile_name}\n")

        # Prepare listing data
        listing_data = [{
            'Year': listing['year'],
            'Make': listing['make'],
            'Model': listing['model'],
            'Mileage': listing['mileage'],
            'Price': listing['price'],
            'Body Style': listing['body_style'],
            'Exterior Color': listing['exterior_color'],
            'Interior Color': listing['interior_color'],
            'Vehicle Condition': listing['vehicle_condition'],
            'Fuel Type': listing['fuel_type'],
            'Transmission': listing['transmission'],
            'Description': listing['description'],
            'Images Path': listing['images_path']
        }]

        # Create temporary CSV
        df = pd.DataFrame(listing_data)
        df.to_csv('selected_listings.csv', index=False, encoding='utf-8')

        # Execute bot
        logger.info(f"Starting bot for scheduled post {post['id']}")

        # Initialize status file
        with open('bot_status.json', 'w') as f:
            json.dump({
                'status': 'starting',
                'message': f"Executing scheduled post #{post['id']}",
                'timestamp': datetime.now().isoformat(),
                'process_running': True,
                'scheduled_post_id': post['id']
            }, f)

        # Run bot
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        bot_process = subprocess.Popen(
            ['python', 'Bot.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            universal_newlines=True
        )

        # Wait for bot to complete
        stdout, stderr = bot_process.communicate(timeout=600)  # 10 minute timeout

        if bot_process.returncode == 0:
            logger.info(f"Scheduled post {post['id']} completed successfully")

            # Update scheduled post status
            update_data = {
                'status': 'completed',
                'updated_at': datetime.now().isoformat()
            }

            # Handle recurrence
            recurrence = post.get('recurrence', 'none')
            if recurrence == 'daily':
                next_run = datetime.fromisoformat(post['next_run_datetime'].replace('Z', '+00:00')) + timedelta(days=1)
                update_data['next_run_datetime'] = next_run.isoformat()
                update_data['status'] = 'pending'
            elif recurrence == 'weekly':
                next_run = datetime.fromisoformat(post['next_run_datetime'].replace('Z', '+00:00')) + timedelta(weeks=1)
                update_data['next_run_datetime'] = next_run.isoformat()
                update_data['status'] = 'pending'
            elif recurrence == 'monthly':
                next_run = datetime.fromisoformat(post['next_run_datetime'].replace('Z', '+00:00')) + timedelta(days=30)
                update_data['next_run_datetime'] = next_run.isoformat()
                update_data['status'] = 'pending'

            supabase.table('scheduled_posts').update(update_data).eq('id', post['id']).execute()

            # Record in history
            try:
                history_record = {
                    'listing_id': post['listing_id'],
                    'profile_id': post.get('profile_id'),
                    'profile_name': profile_name,
                    'status': 'completed',
                    'timestamp': datetime.now().isoformat(),
                    'scheduled_post_id': post['id']
                }
                supabase.table('listing_history').insert(history_record).execute()
            except Exception as e:
                logger.warning(f"Failed to record history: {str(e)}")

            return True
        else:
            logger.error(f"Scheduled post {post['id']} failed with return code {bot_process.returncode}")
            logger.error(f"STDERR: {stderr}")

            # Update status to failed
            supabase.table('scheduled_posts').update({
                'status': 'failed',
                'error_message': stderr[:500] if stderr else 'Unknown error',
                'updated_at': datetime.now().isoformat()
            }).eq('id', post['id']).execute()

            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Scheduled post {post['id']} timed out")
        supabase.table('scheduled_posts').update({
            'status': 'failed',
            'error_message': 'Execution timeout',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', post['id']).execute()
        return False

    except Exception as e:
        logger.error(f"Error executing scheduled post {post['id']}: {str(e)}")

        # Update status to failed
        try:
            supabase.table('scheduled_posts').update({
                'status': 'failed',
                'error_message': str(e)[:500],
                'updated_at': datetime.now().isoformat()
            }).eq('id', post['id']).execute()
        except:
            pass

        return False


def run_scheduler():
    """Main scheduler loop"""
    logger.info("=" * 60)
    logger.info("Scheduler Service Started")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
    logger.info(f"To stop, create file: {STOP_FILE}")
    logger.info(f"Current Local Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Remove stop file if it exists
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
            logger.info("Removed existing stop signal file")
        except Exception as e:
            logger.warning(f"Could not remove stop file: {e}")

    iteration = 0
    while True:
        try:
            iteration += 1

            # Check for stop signal
            if os.path.exists(STOP_FILE):
                logger.info("Stop signal detected. Shutting down scheduler...")
                break

            # Log every 10 iterations (every 10 minutes)
            if iteration % 10 == 1:
                logger.info(f"Scheduler is running... (Iteration {iteration}, Time: {datetime.now().isoformat()})")

            # Get due scheduled posts
            due_posts = get_due_scheduled_posts()

            if due_posts:
                logger.info(f"Found {len(due_posts)} scheduled post(s) to execute")

                for post in due_posts:
                    # Check for stop signal before each execution
                    if os.path.exists(STOP_FILE):
                        logger.info("Stop signal detected. Shutting down scheduler...")
                        return

                    success = execute_scheduled_post(post)
                    if success:
                        logger.info(f"Successfully executed scheduled post #{post['id']}")
                    else:
                        logger.error(f"Failed to execute scheduled post #{post['id']}")

                    # Wait a bit between posts to avoid overwhelming the system
                    time.sleep(5)

            # Wait before next check
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}")
            logger.exception("Full traceback:")
            time.sleep(CHECK_INTERVAL)

    logger.info("Scheduler service stopped")


if __name__ == '__main__':
    try:
        run_scheduler()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        sys.exit(1)
