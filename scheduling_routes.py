# ============================================================================
# SCHEDULING ROUTES
# Add these routes to your app.py file (add before if __name__ == '__main__':)
# ============================================================================

@app.route('/schedule_post', methods=['POST'])
def schedule_post():
    """Schedule a post for future automatic upload"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['listing_id', 'profile_folder', 'profile_name', 'scheduled_datetime']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Parse scheduled datetime
        try:
            scheduled_dt = datetime.fromisoformat(data['scheduled_datetime'].replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': f'Invalid datetime format: {str(e)}'
            }), 400
        
        # Check if the scheduled time is in the future
        if scheduled_dt <= datetime.utcnow():
            return jsonify({
                'status': 'error',
                'message': 'Scheduled time must be in the future'
            }), 400
        
        # Calculate next run datetime based on recurrence
        recurrence = data.get('recurrence', 'none')
        next_run = scheduled_dt
        
        # Prepare schedule record
        schedule_record = {
            'listing_id': int(data['listing_id']),
            'profile_folder': str(data['profile_folder'])[:100],
            'profile_name': str(data['profile_name'])[:100],
            'facebook_account_name': data.get('facebook_account_name'),
            'facebook_account_email': data.get('facebook_account_email'),
            'scheduled_datetime': scheduled_dt.isoformat(),
            'next_run_datetime': next_run.isoformat(),
            'status': 'pending',
            'recurrence': recurrence
        }
        
        # Insert into Supabase
        response = supabase.table('scheduled_posts').insert(schedule_record).execute()
        
        logger.info(f"Scheduled post created for listing {data['listing_id']}")
        
        return jsonify({
            'status': 'success',
            'message': 'Post scheduled successfully',
            'schedule_id': response.data[0]['id'] if response.data else None
        })
        
    except Exception as e:
        logger.error(f"Error in schedule_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to schedule post: {str(e)}'
        }), 500


@app.route('/get_scheduled_posts', methods=['GET'])
def get_scheduled_posts():
    """Get all scheduled posts with optional filters"""
    try:
        # Build query
        query = supabase.table('scheduled_posts').select('*')
        
        # Apply filters
        status_filter = request.args.get('status')
        if status_filter:
            query = query.eq('status', status_filter)
        
        profile_filter = request.args.get('profile')
        if profile_filter:
            query = query.eq('profile_folder', profile_filter)
        
        listing_id_filter = request.args.get('listing_id')
        if listing_id_filter:
            try:
                query = query.eq('listing_id', int(listing_id_filter))
            except ValueError:
                pass
        
        upcoming = request.args.get('upcoming', 'false').lower() == 'true'
        if upcoming:
            query = query.gte('next_run_datetime', datetime.utcnow().isoformat())
            query = query.eq('status', 'pending')
        
        # Execute query
        response = query.order('scheduled_datetime', desc=False).execute()
        
        # Enhance data with listing details
        scheduled_posts = []
        for post in response.data:
            try:
                # Get listing details
                listing_response = supabase.table('listings').select('*').eq('id', post['listing_id']).execute()
                listing = listing_response.data[0] if listing_response.data else {}
                
                enhanced_post = {
                    **post,
                    'vehicle_info': {
                        'year': listing.get('year'),
                        'make': listing.get('make'),
                        'model': listing.get('model'),
                        'price': listing.get('price'),
                        'mileage': listing.get('mileage'),
                        'description': listing.get('description', '')[:100]
                    }
                }
                scheduled_posts.append(enhanced_post)
            except Exception as e:
                logger.error(f"Error enhancing scheduled post {post.get('id')}: {str(e)}")
                scheduled_posts.append(post)
        
        logger.info(f"Retrieved {len(scheduled_posts)} scheduled posts")
        
        return jsonify({
            'status': 'success',
            'scheduled_posts': scheduled_posts,
            'total': len(scheduled_posts)
        })
        
    except Exception as e:
        logger.error(f"Error in get_scheduled_posts: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to get scheduled posts: {str(e)}'
        }), 500


@app.route('/update_scheduled_post', methods=['POST'])
def update_scheduled_post():
    """Update a scheduled post"""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        
        if not schedule_id:
            return jsonify({
                'status': 'error',
                'message': 'schedule_id is required'
            }), 400
        
        try:
            schedule_id = int(schedule_id)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid schedule_id format'
            }), 400
        
        # Prepare update data
        update_data = {}
        
        if 'scheduled_datetime' in data:
            try:
                scheduled_dt = datetime.fromisoformat(data['scheduled_datetime'].replace('Z', '+00:00'))
                update_data['scheduled_datetime'] = scheduled_dt.isoformat()
                update_data['next_run_datetime'] = scheduled_dt.isoformat()
            except ValueError as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid datetime format: {str(e)}'
                }), 400
        
        if 'status' in data:
            if data['status'] in ['pending', 'completed', 'failed', 'cancelled']:
                update_data['status'] = data['status']
        
        if 'recurrence' in data:
            if data['recurrence'] in ['none', 'daily', 'weekly', 'monthly']:
                update_data['recurrence'] = data['recurrence']
        
        if not update_data:
            return jsonify({
                'status': 'error',
                'message': 'No valid fields to update'
            }), 400
        
        # Update in Supabase
        response = supabase.table('scheduled_posts')\
            .update(update_data)\
            .eq('id', schedule_id)\
            .execute()
        
        if not response.data:
            return jsonify({
                'status': 'error',
                'message': 'Scheduled post not found'
            }), 404
        
        logger.info(f"Updated scheduled post {schedule_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Scheduled post updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in update_scheduled_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to update scheduled post: {str(e)}'
        }), 500


@app.route('/delete_scheduled_post', methods=['POST'])
def delete_scheduled_post():
    """Delete a scheduled post"""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        
        if not schedule_id:
            return jsonify({
                'status': 'error',
                'message': 'schedule_id is required'
            }), 400
        
        try:
            schedule_id = int(schedule_id)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid schedule_id format'
            }), 400
        
        # Delete from Supabase
        supabase.table('scheduled_posts')\
            .delete()\
            .eq('id', schedule_id)\
            .execute()
        
        logger.info(f"Deleted scheduled post {schedule_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Scheduled post deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in delete_scheduled_post: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete scheduled post: {str(e)}'
        }), 500


@app.route('/get_schedule_stats', methods=['GET'])
def get_schedule_stats():
    """Get statistics about scheduled posts"""
    try:
        # Get all scheduled posts
        response = supabase.table('scheduled_posts')\
            .select('status, scheduled_datetime, next_run_datetime')\
            .execute()
        
        stats = {
            'pending': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'total': len(response.data)
        }
        
        for record in response.data:
            status = record.get('status', 'pending')
            if status in stats:
                stats[status] += 1
        
        # Get upcoming posts (next 7 days)
        upcoming_date = (datetime.utcnow() + timedelta(days=7)).isoformat()
        current_time = datetime.utcnow().isoformat()
        
        upcoming_response = supabase.table('scheduled_posts')\
            .select('id', count='exact')\
            .eq('status', 'pending')\
            .lte('next_run_datetime', upcoming_date)\
            .gte('next_run_datetime', current_time)\
            .execute()
        
        stats['upcoming_7_days'] = upcoming_response.count if upcoming_response.count else 0
        
        logger.info("Retrieved schedule statistics")
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in get_schedule_stats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to get schedule stats: {str(e)}'
        }), 500