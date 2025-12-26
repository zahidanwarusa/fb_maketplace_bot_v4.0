"""
Schedule Component
Handles scheduled posts management routes
"""

from flask import Blueprint, request, jsonify
import logging
import traceback
import subprocess
import os
import signal
from datetime import datetime, timedelta

schedule_bp = Blueprint('schedule', __name__)
logger = logging.getLogger(__name__)

# Global state for scheduler process
scheduler_process = None
SCHEDULER_STOP_FILE = 'scheduler_stop_signal.txt'


def init_schedule_routes(app, supabase):
    """Initialize schedule management routes"""
    
    @app.route('/get_scheduled_posts', methods=['GET'])
    def get_scheduled_posts():
        try:
            response = supabase.table('scheduled_posts').select('*').order('scheduled_datetime', desc=False).execute()
            
            scheduled_posts = []
            for post in response.data:
                try:
                    listing_response = supabase.table('listings').select('*').eq('id', post['listing_id']).execute()
                    listing = listing_response.data[0] if listing_response.data else {}
                    
                    enhanced_post = {
                        **post,
                        'vehicle_info': {
                            'year': listing.get('year'),
                            'make': listing.get('make'),
                            'model': listing.get('model'),
                            'price': listing.get('price'),
                            'mileage': listing.get('mileage')
                        }
                    }
                    scheduled_posts.append(enhanced_post)
                except:
                    scheduled_posts.append(post)
            
            return jsonify({'status': 'success', 'scheduled_posts': scheduled_posts, 'total': len(scheduled_posts)})
        except Exception as e:
            logger.error(f"Error getting scheduled posts: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/get_schedule_stats', methods=['GET'])
    def get_schedule_stats():
        try:
            response = supabase.table('scheduled_posts').select('status', count='exact').execute()
            
            stats = {'pending': 0, 'completed': 0, 'failed': 0, 'cancelled': 0, 'total': len(response.data), 'upcoming_7_days': 0}
            
            for record in response.data:
                status = record.get('status', 'pending')
                if status in stats:
                    stats[status] += 1
            
            return jsonify({'status': 'success', 'stats': stats})
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/schedule_post', methods=['POST'])
    def schedule_post():
        try:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400

            if not data.get('listing_id') or not data.get('profile_name') or not data.get('scheduled_datetime'):
                return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

            # Parse the datetime string as local time (no timezone conversion)
            scheduled_datetime_str = data['scheduled_datetime']
            # Handle both formats: "YYYY-MM-DD HH:MM:SS" and ISO format
            if 'T' in scheduled_datetime_str:
                scheduled_datetime_str = scheduled_datetime_str.replace('T', ' ')
            if 'Z' in scheduled_datetime_str:
                scheduled_datetime_str = scheduled_datetime_str.replace('Z', '')

            # Parse as naive datetime (local time, no timezone)
            try:
                scheduled_dt = datetime.strptime(scheduled_datetime_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                scheduled_dt = datetime.strptime(scheduled_datetime_str.split('.')[0], '%Y-%m-%d %H:%M')

            schedule_record = {
                'listing_id': int(data['listing_id']),
                'profile_id': int(data.get('profile_id')) if data.get('profile_id') else None,
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data.get('profile_path', ''))[:500],
                'profile_folder': str(data.get('profile_path', ''))[:500],
                'location': str(data.get('location', ''))[:200],
                'scheduled_datetime': scheduled_dt.isoformat(),
                'next_run_datetime': scheduled_dt.isoformat(),
                'status': 'pending',
                'recurrence': data.get('recurrence', 'none'),
                'created_at': datetime.now().isoformat()
            }
            
            response = supabase.table('scheduled_posts').insert(schedule_record).execute()
            
            if response.data:
                return jsonify({'status': 'success', 'message': 'Post scheduled', 'schedule_id': response.data[0]['id']})
            return jsonify({'status': 'error', 'message': 'Failed to create schedule'}), 500
        except Exception as e:
            logger.error(f"Error scheduling post: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/update_scheduled_post', methods=['POST'])
    def update_scheduled_post():
        try:
            data = request.json
            schedule_id = data.get('schedule_id')

            if not schedule_id:
                return jsonify({'status': 'error', 'message': 'schedule_id is required'}), 400

            update_data = {'updated_at': datetime.now().isoformat()}
            if 'status' in data and data['status'] in ['pending', 'completed', 'failed', 'cancelled']:
                update_data['status'] = data['status']

            response = supabase.table('scheduled_posts').update(update_data).eq('id', schedule_id).execute()

            if not response.data:
                return jsonify({'status': 'error', 'message': 'Scheduled post not found'}), 404
            return jsonify({'status': 'success', 'message': 'Scheduled post updated'})
        except Exception as e:
            logger.error(f"Error updating scheduled post: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/update_scheduled_post_full', methods=['POST'])
    def update_scheduled_post_full():
        try:
            data = request.json
            schedule_id = data.get('schedule_id')

            if not schedule_id:
                return jsonify({'status': 'error', 'message': 'schedule_id is required'}), 400

            if not data.get('listing_id') or not data.get('profile_name') or not data.get('scheduled_datetime'):
                return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

            # Parse the datetime string as local time (no timezone conversion)
            scheduled_datetime_str = data['scheduled_datetime']
            # Handle both formats: "YYYY-MM-DD HH:MM:SS" and ISO format
            if 'T' in scheduled_datetime_str:
                scheduled_datetime_str = scheduled_datetime_str.replace('T', ' ')
            if 'Z' in scheduled_datetime_str:
                scheduled_datetime_str = scheduled_datetime_str.replace('Z', '')

            # Parse as naive datetime (local time, no timezone)
            try:
                scheduled_dt = datetime.strptime(scheduled_datetime_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                scheduled_dt = datetime.strptime(scheduled_datetime_str.split('.')[0], '%Y-%m-%d %H:%M')

            update_data = {
                'listing_id': int(data['listing_id']),
                'profile_id': int(data.get('profile_id')) if data.get('profile_id') else None,
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data.get('profile_path', ''))[:500],
                'profile_folder': str(data.get('profile_path', ''))[:500],
                'location': str(data.get('location', ''))[:200],
                'scheduled_datetime': scheduled_dt.isoformat(),
                'next_run_datetime': scheduled_dt.isoformat(),
                'recurrence': data.get('recurrence', 'none'),
                'updated_at': datetime.now().isoformat()
            }

            response = supabase.table('scheduled_posts').update(update_data).eq('id', schedule_id).execute()

            if not response.data:
                return jsonify({'status': 'error', 'message': 'Scheduled post not found'}), 404
            return jsonify({'status': 'success', 'message': 'Scheduled post updated successfully'})
        except Exception as e:
            logger.error(f"Error updating scheduled post: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/delete_scheduled_post', methods=['POST'])
    def delete_scheduled_post():
        try:
            data = request.json
            schedule_id = data.get('schedule_id')

            if not schedule_id:
                return jsonify({'status': 'error', 'message': 'schedule_id is required'}), 400

            supabase.table('scheduled_posts').delete().eq('id', schedule_id).execute()
            return jsonify({'status': 'success', 'message': 'Scheduled post deleted'})
        except Exception as e:
            logger.error(f"Error deleting scheduled post: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/start_scheduler', methods=['POST'])
    def start_scheduler():
        """Start the scheduler service"""
        global scheduler_process

        try:
            # Check if scheduler is already running
            if scheduler_process is not None and scheduler_process.poll() is None:
                return jsonify({
                    'status': 'warning',
                    'message': 'Scheduler is already running'
                }), 400

            # Remove stop signal if it exists
            if os.path.exists(SCHEDULER_STOP_FILE):
                try:
                    os.remove(SCHEDULER_STOP_FILE)
                except:
                    pass

            # Start scheduler process
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            scheduler_process = subprocess.Popen(
                ['python', 'scheduler_service.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            logger.info(f"Scheduler started with PID: {scheduler_process.pid}")

            return jsonify({
                'status': 'success',
                'message': 'Scheduler service started',
                'pid': scheduler_process.pid
            })

        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to start scheduler: {str(e)}'
            }), 500

    @app.route('/stop_scheduler', methods=['POST'])
    def stop_scheduler():
        """Stop the scheduler service"""
        global scheduler_process

        try:
            # Create stop signal file
            with open(SCHEDULER_STOP_FILE, 'w') as f:
                f.write(datetime.now().isoformat())

            logger.info("Scheduler stop signal created")

            # Check if process is running
            if scheduler_process is None or scheduler_process.poll() is not None:
                return jsonify({
                    'status': 'warning',
                    'message': 'Scheduler is not running'
                })

            # Wait for graceful shutdown
            import time
            for i in range(10):
                if scheduler_process.poll() is not None:
                    logger.info("Scheduler stopped gracefully")
                    return jsonify({
                        'status': 'success',
                        'message': 'Scheduler stopped'
                    })
                time.sleep(1)

            # Force kill if still running
            logger.warning("Forcing scheduler termination...")
            try:
                if os.name == 'nt':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(scheduler_process.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(os.getpgid(scheduler_process.pid), signal.SIGTERM)

                scheduler_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error killing scheduler: {e}")

            return jsonify({
                'status': 'success',
                'message': 'Scheduler forcefully stopped'
            })

        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to stop scheduler: {str(e)}'
            }), 500

    @app.route('/scheduler_status', methods=['GET'])
    def get_scheduler_status():
        """Get scheduler service status"""
        global scheduler_process

        try:
            is_running = scheduler_process is not None and scheduler_process.poll() is None

            # Check for pending scheduled posts
            now = datetime.now()
            pending_response = supabase.table('scheduled_posts').select('*', count='exact').eq('status', 'pending').execute()

            # Get next scheduled post
            next_post = None
            if pending_response.data:
                next_response = supabase.table('scheduled_posts').select('*').eq('status', 'pending').order('next_run_datetime').limit(1).execute()
                if next_response.data:
                    next_post = next_response.data[0]

            return jsonify({
                'status': 'success',
                'scheduler_running': is_running,
                'pending_count': pending_response.count or 0,
                'next_post': next_post,
                'pid': scheduler_process.pid if is_running else None
            })

        except Exception as e:
            logger.error(f"Error getting scheduler status: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get status: {str(e)}'
            }), 500
