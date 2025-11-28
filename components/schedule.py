"""
Schedule Component
Handles scheduled posts management routes
"""

from flask import Blueprint, request, jsonify
import logging
import traceback
from datetime import datetime, timedelta

schedule_bp = Blueprint('schedule', __name__)
logger = logging.getLogger(__name__)


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
            
            scheduled_dt = datetime.fromisoformat(data['scheduled_datetime'].replace('Z', '+00:00'))
            
            schedule_record = {
                'listing_id': int(data['listing_id']),
                'profile_id': int(data.get('profile_id')) if data.get('profile_id') else None,
                'profile_name': str(data['profile_name'])[:100],
                'profile_path': str(data.get('profile_path', ''))[:500],
                'location': str(data.get('location', ''))[:200],
                'scheduled_datetime': scheduled_dt.isoformat(),
                'next_run_datetime': scheduled_dt.isoformat(),
                'status': 'pending',
                'recurrence': data.get('recurrence', 'none'),
                'created_at': datetime.utcnow().isoformat()
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
            
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            if 'status' in data and data['status'] in ['pending', 'completed', 'failed', 'cancelled']:
                update_data['status'] = data['status']
            
            response = supabase.table('scheduled_posts').update(update_data).eq('id', schedule_id).execute()
            
            if not response.data:
                return jsonify({'status': 'error', 'message': 'Scheduled post not found'}), 404
            return jsonify({'status': 'success', 'message': 'Scheduled post updated'})
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
