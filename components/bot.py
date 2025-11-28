"""
Bot Component - Enhanced Version
Handles bot execution with stop functionality, real-time status tracking, and configuration
"""

from flask import Blueprint, request, jsonify
import os
import subprocess
import pandas as pd
import logging
import traceback
import json
import time
import signal
from datetime import datetime
from threading import Thread

# Create blueprint
bot_bp = Blueprint('bot', __name__)

# Get logger
logger = logging.getLogger(__name__)

# Global state for bot process management
bot_process = None
bot_start_time = None

# File paths for bot communication
STATUS_FILE = 'bot_status.json'
STOP_FILE = 'bot_stop_signal.txt'
CONFIG_FILE = 'bot_config.json'
SCREENSHOT_FOLDER = 'fbmpss'

# Default configuration
DEFAULT_CONFIG = {
    'delays': {
        'between_listings': 5,
        'between_profiles': 10,
        'after_publish': 5,
        'page_load': 4,
        'element_wait': 2,
        'group_selection': 1,
    },
    'max_groups': 20,
    'headless': False,
    'auto_retry': False,
    'max_retries': 2
}


def init_bot_routes(app, supabase, max_profile_selection, get_profile_locations_dict=None):
    """Initialize bot execution routes with app context"""
    
    # Ensure screenshot folder exists
    if not os.path.exists(SCREENSHOT_FOLDER):
        os.makedirs(SCREENSHOT_FOLDER)
        logger.info(f"Created screenshot folder: {SCREENSHOT_FOLDER}")
    
    @app.route('/run_bot', methods=['POST'])
    def run_bot():
        """Run the automation bot with selected Edge profiles and listings"""
        global bot_process, bot_start_time
        
        try:
            # Check if bot is already running
            if bot_process is not None and bot_process.poll() is None:
                return jsonify({
                    "status": "error",
                    "message": "Bot is already running. Stop it first or wait for it to finish."
                }), 400
            
            data = request.json
            
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400
            
            selected_profiles = data.get('profiles', [])
            selected_listings = data.get('listings', [])
            
            # Validate profiles and listings are selected
            if not selected_profiles:
                return jsonify({
                    "status": "error",
                    "message": "No profiles selected"
                }), 400
            
            if not selected_listings:
                return jsonify({
                    "status": "error",
                    "message": "No listings selected"
                }), 400
            
            # ENFORCE PROFILE SELECTION LIMIT
            if len(selected_profiles) > max_profile_selection:
                logger.warning(f"Profile selection limit exceeded: {len(selected_profiles)} > {max_profile_selection}")
                return jsonify({
                    "status": "error",
                    "message": f"You can only select up to {max_profile_selection} profiles at a time. Currently selected: {len(selected_profiles)}"
                }), 400
            
            # Validate all profiles have locations
            profiles_without_location = []
            for profile in selected_profiles:
                if not profile.get('location'):
                    profiles_without_location.append(profile.get('profile_name', 'Unknown'))
            
            if profiles_without_location:
                return jsonify({
                    "status": "error",
                    "message": f"The following profiles are missing locations: {', '.join(profiles_without_location)}"
                }), 400
            
            # Clean up any existing stop signal
            if os.path.exists(STOP_FILE):
                try:
                    os.remove(STOP_FILE)
                except:
                    pass
            
            # Save selected profiles to a temporary file
            try:
                with open('selected_profiles.txt', 'w', encoding='utf-8') as f:
                    for profile in selected_profiles:
                        profile_name = profile.get('profile_name', '')
                        profile_path = profile.get('profile_path', '')
                        location = profile.get('location', '')
                        
                        if not profile_path or not location:
                            logger.warning(f"Profile missing required data: {profile_name}")
                            continue
                        
                        f.write(f"{profile_path}|{location}|{profile_name}\n")
            except Exception as e:
                logger.error(f"Failed to write selected_profiles.txt: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to prepare profile data: {str(e)}"
                }), 500
            
            # Fetch listings by IDs from Supabase
            try:
                selected_listings_data = []
                for listing_id in selected_listings:
                    response = supabase.table('listings').select('*').eq('id', listing_id).single().execute()
                    if response.data:
                        item = response.data
                        csv_row = {
                            'Year': item['year'],
                            'Make': item['make'],
                            'Model': item['model'],
                            'Mileage': item['mileage'],
                            'Price': item['price'],
                            'Body Style': item['body_style'],
                            'Exterior Color': item['exterior_color'],
                            'Interior Color': item['interior_color'],
                            'Vehicle Condition': item['vehicle_condition'],
                            'Fuel Type': item['fuel_type'],
                            'Transmission': item['transmission'],
                            'Description': item['description'],
                            'Images Path': item['images_path']
                        }
                        selected_listings_data.append(csv_row)
            except Exception as e:
                logger.error(f"Failed to fetch listings from database: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to fetch listings: {str(e)}"
                }), 500
            
            if not selected_listings_data:
                return jsonify({
                    "status": "error",
                    "message": "No valid listings to process"
                }), 400
            
            # Create temporary CSV for the bot
            try:
                df = pd.DataFrame(selected_listings_data)
                df.to_csv('selected_listings.csv', index=False, encoding='utf-8')
            except Exception as e:
                logger.error(f"Failed to create selected_listings.csv: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to prepare listing data: {str(e)}"
                }), 500
            
            # Initialize status file
            initial_status = {
                'status': 'starting',
                'message': 'Bot is starting...',
                'timestamp': datetime.now().isoformat(),
                'total_profiles': len(selected_profiles),
                'total_listings': len(selected_listings_data),
                'progress': 0
            }
            with open(STATUS_FILE, 'w') as f:
                json.dump(initial_status, f)
            
            # Run the bot script in background
            try:
                logger.info(f"Starting bot with {len(selected_profiles)} Edge profiles and {len(selected_listings_data)} listings")
                
                bot_process = subprocess.Popen(
                    ['python', 'Bot.py'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                
                bot_start_time = datetime.now()
                
                logger.info(f"Bot started with PID: {bot_process.pid}")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Bot started successfully',
                    'pid': bot_process.pid,
                    'total_profiles': len(selected_profiles),
                    'total_listings': len(selected_listings_data)
                })
                
            except Exception as e:
                logger.error(f"Bot execution failed: {str(e)}")
                logger.error(traceback.format_exc())
                
                return jsonify({
                    'status': 'error',
                    'message': f'Bot execution failed: {str(e)}'
                }), 500
            
        except Exception as e:
            logger.error(f"Critical error in run_bot: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Bot execution failed: {str(e)}'
            }), 500

    @app.route('/stop_bot', methods=['POST'])
    def stop_bot():
        """Stop the running bot gracefully"""
        global bot_process
        
        try:
            # Create stop signal file
            with open(STOP_FILE, 'w') as f:
                f.write(datetime.now().isoformat())
            
            logger.info("Stop signal file created")
            
            # Check if process is running
            if bot_process is None:
                return jsonify({
                    'status': 'warning',
                    'message': 'No bot process found, but stop signal created'
                })
            
            if bot_process.poll() is not None:
                return jsonify({
                    'status': 'warning',
                    'message': 'Bot process already finished'
                })
            
            # Give the bot time to stop gracefully
            logger.info(f"Waiting for bot (PID: {bot_process.pid}) to stop gracefully...")
            
            # Wait up to 10 seconds for graceful shutdown
            for i in range(10):
                if bot_process.poll() is not None:
                    logger.info("Bot stopped gracefully")
                    return jsonify({
                        'status': 'success',
                        'message': 'Bot stopped gracefully'
                    })
                time.sleep(1)
            
            # Force kill if still running
            logger.warning("Bot did not stop gracefully, forcing termination...")
            try:
                if os.name == 'nt':
                    # Windows
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(bot_process.pid)], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Unix
                    os.killpg(os.getpgid(bot_process.pid), signal.SIGTERM)
                    
                bot_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error killing process: {e}")
            
            return jsonify({
                'status': 'success',
                'message': 'Bot forcefully terminated'
            })
            
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to stop bot: {str(e)}'
            }), 500

    @app.route('/bot_status', methods=['GET'])
    def get_bot_status():
        """Get current bot status"""
        global bot_process, bot_start_time
        
        try:
            # Check if status file exists
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r') as f:
                        status_data = json.load(f)
                except:
                    status_data = {'status': 'unknown', 'message': 'Could not read status file'}
            else:
                status_data = {'status': 'idle', 'message': 'No bot running'}
            
            # Check process state
            process_running = False
            if bot_process is not None:
                poll_result = bot_process.poll()
                process_running = poll_result is None
                
                if not process_running:
                    # Process finished, get output
                    stdout, stderr = '', ''
                    try:
                        stdout, stderr = bot_process.communicate(timeout=1)
                    except:
                        pass
                    
                    status_data['process_finished'] = True
                    status_data['exit_code'] = poll_result
                    if stderr:
                        status_data['stderr'] = stderr[-1000:]  # Last 1000 chars
            
            status_data['process_running'] = process_running
            
            if bot_start_time and process_running:
                status_data['running_time'] = str(datetime.now() - bot_start_time)
            
            return jsonify({
                'status': 'success',
                **status_data
            })
            
        except Exception as e:
            logger.error(f"Error getting bot status: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get status: {str(e)}'
            }), 500

    @app.route('/bot_config', methods=['GET'])
    def get_bot_config():
        """Get current bot configuration"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
            else:
                config = DEFAULT_CONFIG.copy()
            
            return jsonify({
                'status': 'success',
                'config': config
            })
            
        except Exception as e:
            logger.error(f"Error getting bot config: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get config: {str(e)}'
            }), 500

    @app.route('/bot_config', methods=['POST'])
    def update_bot_config():
        """Update bot configuration"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No configuration data provided'
                }), 400
            
            # Load existing config or use defaults
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
            else:
                config = DEFAULT_CONFIG.copy()
            
            # Update with new values
            if 'delays' in data:
                config['delays'].update(data['delays'])
            if 'max_groups' in data:
                config['max_groups'] = int(data['max_groups'])
            if 'headless' in data:
                config['headless'] = bool(data['headless'])
            if 'auto_retry' in data:
                config['auto_retry'] = bool(data['auto_retry'])
            if 'max_retries' in data:
                config['max_retries'] = int(data['max_retries'])
            
            # Save config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info("Bot configuration updated")
            
            return jsonify({
                'status': 'success',
                'message': 'Configuration updated',
                'config': config
            })
            
        except Exception as e:
            logger.error(f"Error updating bot config: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to update config: {str(e)}'
            }), 500

    @app.route('/bot_logs', methods=['GET'])
    def get_bot_logs():
        """Get bot execution logs"""
        try:
            logs = []
            
            # Read from status file for recent activity
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r') as f:
                        status = json.load(f)
                    logs.append({
                        'timestamp': status.get('timestamp', ''),
                        'message': status.get('message', ''),
                        'status': status.get('status', '')
                    })
                except:
                    pass
            
            # Read from app.log for detailed logs
            if os.path.exists('app.log'):
                try:
                    with open('app.log', 'r', encoding='utf-8') as f:
                        # Get last 100 lines
                        lines = f.readlines()[-100:]
                        for line in lines:
                            if 'bot' in line.lower() or 'Bot' in line:
                                logs.append({'raw': line.strip()})
                except:
                    pass
            
            return jsonify({
                'status': 'success',
                'logs': logs
            })
            
        except Exception as e:
            logger.error(f"Error getting bot logs: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get logs: {str(e)}'
            }), 500

    @app.route('/screenshots', methods=['GET'])
    def get_screenshots():
        """Get list of screenshots from fbmpss folder"""
        try:
            screenshots = []
            
            if os.path.exists(SCREENSHOT_FOLDER):
                for filename in os.listdir(SCREENSHOT_FOLDER):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        filepath = os.path.join(SCREENSHOT_FOLDER, filename)
                        stat = os.stat(filepath)
                        screenshots.append({
                            'filename': filename,
                            'path': filepath,
                            'size': stat.st_size,
                            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'type': 'success' if 'success' in filename.lower() else 
                                    'error' if 'error' in filename.lower() else 'other'
                        })
            
            # Sort by creation time, newest first
            screenshots.sort(key=lambda x: x['created'], reverse=True)
            
            return jsonify({
                'status': 'success',
                'screenshots': screenshots,
                'total': len(screenshots),
                'folder': SCREENSHOT_FOLDER
            })
            
        except Exception as e:
            logger.error(f"Error getting screenshots: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get screenshots: {str(e)}'
            }), 500

    @app.route('/screenshots/<filename>', methods=['GET'])
    def get_screenshot(filename):
        """Get a specific screenshot"""
        from flask import send_file
        try:
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)
            if os.path.exists(filepath):
                return send_file(filepath, mimetype='image/png')
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Screenshot not found'
                }), 404
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/screenshots/clear', methods=['POST'])
    def clear_screenshots():
        """Clear all screenshots from fbmpss folder"""
        try:
            deleted_count = 0
            
            if os.path.exists(SCREENSHOT_FOLDER):
                for filename in os.listdir(SCREENSHOT_FOLDER):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        filepath = os.path.join(SCREENSHOT_FOLDER, filename)
                        try:
                            os.remove(filepath)
                            deleted_count += 1
                        except:
                            pass
            
            logger.info(f"Cleared {deleted_count} screenshots")
            
            return jsonify({
                'status': 'success',
                'message': f'Deleted {deleted_count} screenshots',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Error clearing screenshots: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to clear screenshots: {str(e)}'
            }), 500

    @app.route('/reset_bot_state', methods=['POST'])
    def reset_bot_state():
        """Reset bot state files (useful after crashes)"""
        global bot_process, bot_start_time
        
        try:
            # Clear stop file
            if os.path.exists(STOP_FILE):
                os.remove(STOP_FILE)
            
            # Reset status file
            if os.path.exists(STATUS_FILE):
                os.remove(STATUS_FILE)
            
            # Reset global state
            bot_process = None
            bot_start_time = None
            
            # Clean up temp files
            for temp_file in ['selected_profiles.txt', 'selected_listings.csv']:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            logger.info("Bot state reset")
            
            return jsonify({
                'status': 'success',
                'message': 'Bot state reset successfully'
            })
            
        except Exception as e:
            logger.error(f"Error resetting bot state: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to reset state: {str(e)}'
            }), 500
