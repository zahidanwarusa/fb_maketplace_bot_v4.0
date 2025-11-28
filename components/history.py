"""
History Component
Handles upload history and tracking routes
"""

from flask import Blueprint, request, jsonify, send_file
import logging
import traceback
from datetime import datetime, timedelta
import csv
import io

history_bp = Blueprint('history', __name__)
logger = logging.getLogger(__name__)


def init_history_routes(app, supabase):
    """Initialize upload history routes"""
    
    @app.route('/track_upload', methods=['POST'])
    def track_upload():
        try:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400
            
            upload_record = {
                'profile_name': str(data.get('profile_name', ''))[:100],
                'profile_folder': str(data.get('profile_folder', ''))[:100],
                'listing_id': data.get('listing_id'),
                'vehicle_info': data.get('vehicle_info'),
                'status': data.get('status', 'pending'),
                'error_message': str(data.get('error_message', ''))[:500] if data.get('error_message') else None,
                'location': str(data.get('location', ''))[:200],
                'marketplace_url': str(data.get('marketplace_url', ''))[:500] if data.get('marketplace_url') else None,
                'attempt_number': int(data.get('attempt_number', 1)),
                'upload_datetime': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('upload_history').insert(upload_record).execute()
            upload_id = response.data[0]['id'] if response.data else None
            return jsonify({'status': 'success', 'message': 'Upload tracked', 'upload_id': upload_id})
        except Exception as e:
            logger.error(f"Error tracking upload: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/update_upload_status', methods=['POST'])
    def update_upload_status():
        try:
            data = request.json
            if not data or not data.get('upload_id'):
                return jsonify({'status': 'error', 'message': 'upload_id is required'}), 400
            
            update_data = {'status': data.get('status', 'pending'), 'updated_at': datetime.utcnow().isoformat()}
            if data.get('error_message'):
                update_data['error_message'] = str(data.get('error_message'))[:500]
            if data.get('marketplace_url'):
                update_data['marketplace_url'] = str(data.get('marketplace_url'))[:500]
            
            response = supabase.table('upload_history').update(update_data).eq('id', data['upload_id']).execute()
            if not response.data:
                return jsonify({'status': 'error', 'message': 'Upload record not found'}), 404
            return jsonify({'status': 'success', 'message': 'Status updated'})
        except Exception as e:
            logger.error(f"Error updating status: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/upload_history', methods=['GET'])
    def get_upload_history():
        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            
            query = supabase.table('upload_history').select('*', count='exact')
            
            profile_filter = request.args.get('profile', '')
            status_filter = request.args.get('status', '')
            
            if profile_filter:
                query = query.eq('profile_name', profile_filter)
            if status_filter:
                query = query.eq('status', status_filter)
            
            start = (page - 1) * page_size
            end = start + page_size - 1
            
            response = query.order('upload_datetime', desc=True).range(start, end).execute()
            
            stats = {'success': 0, 'failed': 0, 'pending': 0, 'in_progress': 0, 'total': response.count or 0}
            
            return jsonify({
                'status': 'success',
                'uploads': response.data,
                'total': response.count,
                'page': page,
                'page_size': page_size,
                'stats': stats
            })
        except Exception as e:
            logger.error(f"Error getting history: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/export_history', methods=['GET'])
    def export_history():
        try:
            response = supabase.table('upload_history').select('*').order('upload_datetime', desc=True).execute()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Upload ID', 'Date & Time', 'Profile Name', 'Vehicle Year', 'Vehicle Make', 'Vehicle Model', 'Price', 'Status', 'Error Message'])
            
            for upload in response.data:
                vehicle_info = upload.get('vehicle_info', {})
                writer.writerow([
                    upload.get('id', ''),
                    upload.get('upload_datetime', ''),
                    upload.get('profile_name', ''),
                    vehicle_info.get('year', ''),
                    vehicle_info.get('make', ''),
                    vehicle_info.get('model', ''),
                    vehicle_info.get('price', ''),
                    upload.get('status', ''),
                    upload.get('error_message', '')
                ])
            
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'upload_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
        except Exception as e:
            logger.error(f"Error exporting history: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/upload_stats', methods=['GET'])
    def get_upload_stats():
        try:
            days = int(request.args.get('days', 30))
            date_threshold = datetime.utcnow() - timedelta(days=days)
            
            response = supabase.table('upload_history').select('status', count='exact').gte('upload_datetime', date_threshold.isoformat()).execute()
            
            stats = {'total_uploads': response.count, 'by_status': {'success': 0, 'failed': 0, 'pending': 0, 'in_progress': 0}, 'success_rate': 0}
            
            for record in response.data:
                status = record.get('status', '')
                if status in stats['by_status']:
                    stats['by_status'][status] += 1
            
            if stats['total_uploads'] > 0:
                stats['success_rate'] = round((stats['by_status']['success'] / stats['total_uploads']) * 100, 2)
            
            return jsonify({'status': 'success', 'stats': stats, 'period_days': days})
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
