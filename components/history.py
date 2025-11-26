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

# Create blueprint
history_bp = Blueprint('history', __name__)

# Get logger
logger = logging.getLogger(__name__)


def init_history_routes(app, supabase):
    """Initialize upload history routes with app context"""
    
    @app.route('/track_upload', methods=['POST'])
    def track_upload():
        """Record an upload attempt to the database with error handling"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
            
            # Validate required fields
            required_fields = ['profile_name', 'listing_id', 'vehicle_info']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400
            
            # Prepare upload record
            upload_record = {
                'profile_name': str(data.get('profile_name'))[:100],
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
            
            # Insert into Supabase
            response = supabase.table('upload_history').insert(upload_record).execute()
            
            upload_id = response.data[0]['id'] if response.data else None
            logger.info(f"Successfully tracked upload with ID: {upload_id}")
            
            return jsonify({
                'status': 'success',
                'message': 'Upload tracked successfully',
                'upload_id': upload_id
            })
            
        except Exception as e:
            logger.error(f"Error in track_upload: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to track upload: {str(e)}'
            }), 500

    @app.route('/update_upload_status', methods=['POST'])
    def update_upload_status():
        """Update the status of an existing upload record with error handling"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
                
            upload_id = data.get('upload_id')
            
            if not upload_id:
                return jsonify({
                    'status': 'error',
                    'message': 'upload_id is required'
                }), 400
            
            # Validate upload_id
            try:
                upload_id = int(upload_id)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid upload_id format'
                }), 400
            
            # Prepare update data
            update_data = {
                'status': data.get('status', 'pending'),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if data.get('error_message'):
                update_data['error_message'] = str(data.get('error_message'))[:500]
                
            if data.get('marketplace_url'):
                update_data['marketplace_url'] = str(data.get('marketplace_url'))[:500]
            
            # Update in Supabase
            response = supabase.table('upload_history')\
                .update(update_data)\
                .eq('id', upload_id)\
                .execute()
            
            if not response.data:
                return jsonify({
                    'status': 'error',
                    'message': 'Upload record not found'
                }), 404
            
            logger.info(f"Successfully updated upload status for ID: {upload_id}")
            return jsonify({
                'status': 'success',
                'message': 'Upload status updated successfully'
            })
            
        except Exception as e:
            logger.error(f"Error in update_upload_status: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to update upload status: {str(e)}'
            }), 500

    @app.route('/upload_history', methods=['GET'])
    def get_upload_history():
        """Retrieve upload history with optional filters and error handling"""
        try:
            # Get and validate query parameters
            try:
                page = int(request.args.get('page', 1))
                if page < 1:
                    page = 1
            except ValueError:
                page = 1
                
            try:
                page_size = int(request.args.get('page_size', 20))
                if page_size < 1 or page_size > 100:
                    page_size = 20
            except ValueError:
                page_size = 20
                
            profile_filter = request.args.get('profile', '')
            status_filter = request.args.get('status', '')
            date_from = request.args.get('dateFrom', '')
            date_to = request.args.get('dateTo', '')
            
            # Build query
            query = supabase.table('upload_history').select('*', count='exact')
            
            # Apply filters
            if profile_filter:
                query = query.eq('profile_name', profile_filter)
                
            if status_filter:
                query = query.eq('status', status_filter)
                
            if date_from:
                try:
                    date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                    query = query.gte('upload_datetime', date_from_dt.isoformat())
                except ValueError:
                    logger.warning(f"Invalid date_from format: {date_from}")
                
            if date_to:
                try:
                    date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                    query = query.lt('upload_datetime', date_to_dt.isoformat())
                except ValueError:
                    logger.warning(f"Invalid date_to format: {date_to}")
            
            # Apply pagination
            start = (page - 1) * page_size
            end = start + page_size - 1
            
            # Execute query with ordering
            response = query.order('upload_datetime', desc=True)\
                .range(start, end)\
                .execute()
            
            # Get statistics
            stats_query = supabase.table('upload_history').select('status', count='exact')
            
            # Apply same filters to stats
            if profile_filter:
                stats_query = stats_query.eq('profile_name', profile_filter)
            if date_from:
                try:
                    stats_query = stats_query.gte('upload_datetime', date_from_dt.isoformat())
                except:
                    pass
            if date_to:
                try:
                    stats_query = stats_query.lt('upload_datetime', date_to_dt.isoformat())
                except:
                    pass
            
            stats_response = stats_query.execute()
            
            # Calculate statistics
            stats = {
                'success': 0,
                'failed': 0,
                'pending': 0,
                'in_progress': 0,
                'total': 0
            }
            
            if stats_response.data:
                for record in stats_response.data:
                    status = record.get('status', '')
                    if status in stats:
                        stats[status] = stats.get(status, 0) + 1
                    stats['total'] += 1
            
            logger.info(f"Retrieved {len(response.data)} upload history records")
            
            return jsonify({
                'status': 'success',
                'uploads': response.data,
                'total': response.count,
                'page': page,
                'page_size': page_size,
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error in get_upload_history: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to retrieve upload history: {str(e)}'
            }), 500

    @app.route('/export_history', methods=['GET'])
    def export_history():
        """Export upload history to CSV with error handling"""
        try:
            # Get filters
            profile_filter = request.args.get('profile', '')
            status_filter = request.args.get('status', '')
            date_from = request.args.get('dateFrom', '')
            date_to = request.args.get('dateTo', '')
            
            # Build query (similar to get_upload_history but without pagination)
            query = supabase.table('upload_history').select('*')
            
            if profile_filter:
                query = query.eq('profile_name', profile_filter)
            if status_filter:
                query = query.eq('status', status_filter)
            if date_from:
                try:
                    date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                    query = query.gte('upload_datetime', date_from_dt.isoformat())
                except ValueError:
                    pass
            if date_to:
                try:
                    date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                    query = query.lt('upload_datetime', date_to_dt.isoformat())
                except ValueError:
                    pass
            
            response = query.order('upload_datetime', desc=True).execute()
            
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow([
                'Upload ID',
                'Date & Time',
                'Profile Name',
                'Profile Folder',
                'Vehicle Year',
                'Vehicle Make',
                'Vehicle Model',
                'Price',
                'Mileage',
                'Location',
                'Status',
                'Error Message',
                'Marketplace URL',
                'Attempt Number'
            ])
            
            # Write data
            for upload in response.data:
                try:
                    vehicle_info = upload.get('vehicle_info', {})
                    writer.writerow([
                        upload.get('id', ''),
                        upload.get('upload_datetime', ''),
                        upload.get('profile_name', ''),
                        upload.get('profile_folder', ''),
                        vehicle_info.get('year', ''),
                        vehicle_info.get('make', ''),
                        vehicle_info.get('model', ''),
                        vehicle_info.get('price', ''),
                        vehicle_info.get('mileage', ''),
                        upload.get('location', ''),
                        upload.get('status', ''),
                        upload.get('error_message', ''),
                        upload.get('marketplace_url', ''),
                        upload.get('attempt_number', 1)
                    ])
                except Exception as e:
                    logger.error(f"Error writing row for upload {upload.get('id')}: {str(e)}")
                    continue
            
            # Prepare file for download
            output.seek(0)
            
            logger.info(f"Exported {len(response.data)} upload history records")
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'upload_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )
            
        except Exception as e:
            logger.error(f"Error in export_history: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to export history: {str(e)}'
            }), 500

    @app.route('/upload_stats', methods=['GET'])
    def get_upload_stats():
        """Get overall upload statistics with error handling"""
        try:
            # Get and validate days parameter
            try:
                days = int(request.args.get('days', 30))
                if days < 1 or days > 365:
                    days = 30
            except ValueError:
                days = 30
            
            # Calculate date threshold
            date_threshold = datetime.utcnow() - timedelta(days=days)
            
            # Get stats for the period
            response = supabase.table('upload_history')\
                .select('status, profile_name', count='exact')\
                .gte('upload_datetime', date_threshold.isoformat())\
                .execute()
            
            # Calculate statistics
            stats = {
                'total_uploads': response.count,
                'by_status': {
                    'success': 0,
                    'failed': 0,
                    'pending': 0,
                    'in_progress': 0
                },
                'by_profile': {},
                'success_rate': 0
            }
            
            for record in response.data:
                status = record.get('status', '')
                profile = record.get('profile_name', 'Unknown')
                
                if status in stats['by_status']:
                    stats['by_status'][status] += 1
                    
                if profile not in stats['by_profile']:
                    stats['by_profile'][profile] = 0
                stats['by_profile'][profile] += 1
            
            # Calculate success rate
            if stats['total_uploads'] > 0:
                stats['success_rate'] = round(
                    (stats['by_status']['success'] / stats['total_uploads']) * 100, 2
                )
            
            logger.info(f"Retrieved upload stats for last {days} days")
            
            return jsonify({
                'status': 'success',
                'stats': stats,
                'period_days': days
            })
            
        except Exception as e:
            logger.error(f"Error in get_upload_stats: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get upload stats: {str(e)}'
            }), 500
