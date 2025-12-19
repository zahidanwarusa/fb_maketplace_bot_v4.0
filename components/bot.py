"""
Bot Component - Enhanced Version WITH PROPER ERROR LOGGING AND STATUS UPDATES
Handles bot execution with stop functionality, real-time status tracking, and configuration

FEATURES:
1. Redirects stdout/stderr to log file
2. Sets proper working directory
3. Real-time status tracking
4. File-based statistics tracking (no database changes)
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

# Import stats tracker
from .bot_stats_tracker import (
    init_stats_file, 
    get_stats, 
    reset_stats, 
    record_run_result,
    get_activity_log
)

# Create blueprint
bot_bp = Blueprint('bot', __name__)

# Get logger
logger = logging.getLogger(__name__)

# Global state for bot process management
bot_process = None
bot_start_time = None
bot_log_file = None  # Keep reference to log file

# File paths for bot communication
STATUS_FILE = 'bot_status.json'
STOP_FILE = 'bot_stop_signal.txt'
CONFIG_FILE = 'bot_config.json'
SCREENSHOT_FOLDER = 'fbmpss'
BOT_LOG_FILE = 'bot_execution.log'

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


def init_bot_routes(app, supabase, max_listing_selection, get_profile_locations_dict=None):
    """Initialize bot execution routes with app context"""
    
    # Initialize stats tracking
    init_stats_file()
    
    # Ensure screenshot folder exists
    if not os.path.exists(SCREENSHOT_FOLDER):
        os.makedirs(SCREENSHOT_FOLDER)
        logger.info(f"Created screenshot folder: {SCREENSHOT_FOLDER}")
    
    # Ensure status file exists with idle state
    if not os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'w') as f:
            json.dump({
                'status': 'idle',
                'message': 'Ready to start',
                'timestamp': datetime.now().isoformat(),
                'process_running': False,
                'progress': 0
            }, f)
    
    @app.route('/run_bot', methods=['POST'])
    def run_bot():
        """Run the automation bot with selected Edge profiles and listings"""
        global bot_process, bot_start_time, bot_log_file
        
        try:
            # Check if bot is already running
            if bot_process is not None and bot_process.poll() is None:
                return jsonify({
                    "status": "error",
                    "message": "Bot is already running. Stop it first or wait for it to finish."
                }), 400
            
            # Get request data
            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No data provided"
                }), 400
            
            selected_profiles = data.get('profiles', [])
            selected_listings = data.get('listings', [])
            
            # Validate selections
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
            
            # Check maximum selection limit
            if len(selected_listings) > max_listing_selection:
                return jsonify({
                    "status": "error",
                    "message": f"You can only select up to {max_listing_selection} listings at a time. Currently selected: {len(selected_listings)}"
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
            
            # Initialize status file with starting state
            initial_status = {
                'status': 'starting',
                'message': 'Bot is initializing...',
                'timestamp': datetime.now().isoformat(),
                'process_running': True,
                'total_profiles': len(selected_profiles),
                'total_listings': len(selected_listings_data),
                'current_profile_idx': 0,
                'current_listing_idx': 0,
                'current_profile': '',
                'current_listing': '',
                'progress': 0,
                'results': {
                    'success': 0,
                    'failed': 0,
                    'skipped': 0
                }
            }
            with open(STATUS_FILE, 'w') as f:
                json.dump(initial_status, f, indent=2)
            
            logger.info(f"✅ Initial status file created: {initial_status}")
            
            # Run the bot script in background
            try:
                logger.info(f"Starting bot with {len(selected_profiles)} Edge profiles and {len(selected_listings_data)} listings")
                
                # Close any previous log file
                if bot_log_file is not None:
                    try:
                        bot_log_file.close()
                    except:
                        pass
                
                # Open NEW log file for bot output (this will overwrite previous log)
                bot_log_file = open(BOT_LOG_FILE, 'w', encoding='utf-8', buffering=1)  # Line buffering
                
                # Get current working directory
                current_dir = os.path.dirname(os.path.abspath(__file__))
                bot_dir = os.path.dirname(current_dir)  # Go up one level from components/ to project root
                
                logger.info(f"Bot working directory: {bot_dir}")
                logger.info(f"🔍 Bot output will be logged to: {os.path.abspath(BOT_LOG_FILE)}")
                logger.info(f"👉 CHECK THIS FILE FOR DETAILED ERROR MESSAGES!")
                
                # Write initial header to log file
                bot_log_file.write("=" * 80 + "\n")
                bot_log_file.write(f"BOT EXECUTION LOG - {datetime.now().isoformat()}\n")
                bot_log_file.write(f"Working Directory: {bot_dir}\n")
                bot_log_file.write(f"Profiles: {len(selected_profiles)}\n")
                bot_log_file.write(f"Listings: {len(selected_listings_data)}\n")
                bot_log_file.write("=" * 80 + "\n\n")
                bot_log_file.flush()
                
                # Prepare environment with UTF-8 encoding to handle emojis in Bot.py
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                
                # Launch bot with proper logging
                bot_process = subprocess.Popen(
                    ['python', 'Bot.py'], 
                    stdout=bot_log_file,
                    stderr=bot_log_file,
                    cwd=bot_dir,
                    env=env,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                
                bot_start_time = datetime.now()
                
                logger.info(f"✅ Bot started with PID: {bot_process.pid}")
                logger.info(f"📋 To see what the bot is doing, run: tail -f {BOT_LOG_FILE}")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Bot started successfully',
                    'pid': bot_process.pid,
                    'total_profiles': len(selected_profiles),
                    'total_listings': len(selected_listings_data),
                    'log_file': BOT_LOG_FILE
                })
                
            except Exception as e:
                logger.error(f"Bot execution failed: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Update status to error
                try:
                    with open(STATUS_FILE, 'w') as f:
                        json.dump({
                            'status': 'error',
                            'message': f'Failed to start: {str(e)}',
                            'timestamp': datetime.now().isoformat(),
                            'process_running': False
                        }, f)
                except:
                    pass
                
                # Close log file if it was opened
                if bot_log_file is not None:
                    try:
                        bot_log_file.close()
                        bot_log_file = None
                    except:
                        pass
                
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
        global bot_process, bot_log_file
        
        try:
            # Create stop signal file
            with open(STOP_FILE, 'w') as f:
                f.write(datetime.now().isoformat())
            
            logger.info("Stop signal file created")
            
            # Update status
            try:
                if os.path.exists(STATUS_FILE):
                    with open(STATUS_FILE, 'r') as f:
                        status = json.load(f)
                    status['status'] = 'stopping'
                    status['message'] = 'Stop signal received, finishing current task...'
                    status['timestamp'] = datetime.now().isoformat()
                    with open(STATUS_FILE, 'w') as f:
                        json.dump(status, f, indent=2)
            except:
                pass
            
            # Check if process is running
            if bot_process is None:
                return jsonify({
                    'status': 'warning',
                    'message': 'No bot process found, but stop signal created'
                })
            
            if bot_process.poll() is not None:
                # Process already finished
                if bot_log_file is not None:
                    try:
                        bot_log_file.close()
                        bot_log_file = None
                    except:
                        pass
                
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
                    
                    # Close log file
                    if bot_log_file is not None:
                        try:
                            bot_log_file.close()
                            bot_log_file = None
                        except:
                            pass
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Bot stopped gracefully'
                    })
                time.sleep(1)
            
            # Force kill if still running
            logger.warning("Bot did not stop gracefully, forcing termination...")
            try:
                if os.name == 'nt':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(bot_process.pid)], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(os.getpgid(bot_process.pid), signal.SIGTERM)
                    
                bot_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error killing process: {e}")
            
            # Close log file
            if bot_log_file is not None:
                try:
                    bot_log_file.close()
                    bot_log_file = None
                except:
                    pass
            
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
        """Get current bot status and update stats when finished"""
        global bot_process, bot_start_time
        
        try:
            # Read status file
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r') as f:
                        status_data = json.load(f)
                    
                    logger.debug(f"📊 Read status from file: {status_data}")
                    
                except Exception as e:
                    logger.error(f"Error reading status file: {e}")
                    status_data = {
                        'status': 'error',
                        'message': f'Could not read status file: {str(e)}',
                        'process_running': False
                    }
            else:
                logger.warning("⚠️ Status file does not exist!")
                status_data = {
                    'status': 'idle',
                    'message': 'No bot running',
                    'process_running': False,
                    'progress': 0
                }
            
            # Check actual process state
            process_running = False
            process_just_finished = False
            
            if bot_process is not None:
                poll_result = bot_process.poll()
                process_running = poll_result is None
                
                if not process_running and status_data.get('process_running', False):
                    # Process just finished!
                    process_just_finished = True
                    logger.info(f"🏁 Process finished with exit code: {poll_result}")
                    
                    # ✅ RECORD STATS FROM RESULTS
                    if 'results' in status_data:
                        results = status_data['results']
                        profile = status_data.get('current_profile', 'Unknown')
                        listing = status_data.get('current_listing', 'Unknown')
                        
                        # Calculate duration
                        duration = None
                        if bot_start_time:
                            duration = int((datetime.now() - bot_start_time).total_seconds())
                        
                        # Record each successful listing
                        for _ in range(results.get('success', 0)):
                            record_run_result(profile, listing, True, duration)
                        
                        # Record each failed listing
                        for _ in range(results.get('failed', 0)):
                            record_run_result(profile, listing, False, duration, "Failed")
                        
                        # Record each skipped listing
                        for _ in range(results.get('skipped', 0)):
                            record_run_result(profile, listing, False, duration, "Stopped by user")
                        
                        logger.info(f"✅ Stats recorded: {results}")
                    
                    # Update status
                    if poll_result == 0:
                        status_data['status'] = 'completed'
                        status_data['message'] = 'Bot execution completed successfully'
                    else:
                        status_data['status'] = 'error'
                        status_data['message'] = f'Bot process exited with code {poll_result}'
                    
                    status_data['process_running'] = False
                    status_data['timestamp'] = datetime.now().isoformat()
                    
                    # Save updated status
                    try:
                        with open(STATUS_FILE, 'w') as f:
                            json.dump(status_data, f, indent=2)
                    except:
                        pass
                    
                    status_data['exit_code'] = poll_result
            
            # Override process_running with actual state
            status_data['process_running'] = process_running
            status_data['process_just_finished'] = process_just_finished
            
            # Add runtime if running
            if bot_start_time and process_running:
                status_data['running_time'] = str(datetime.now() - bot_start_time)
            
            # Add log file path
            status_data['log_file'] = os.path.abspath(BOT_LOG_FILE)
            
            # Ensure all required fields exist
            if 'total_profiles' not in status_data:
                status_data['total_profiles'] = 0
            if 'total_listings' not in status_data:
                status_data['total_listings'] = 0
            if 'current_profile_idx' not in status_data:
                status_data['current_profile_idx'] = 0
            if 'current_listing_idx' not in status_data:
                status_data['current_listing_idx'] = 0
            if 'current_profile' not in status_data:
                status_data['current_profile'] = ''
            if 'current_listing' not in status_data:
                status_data['current_listing'] = ''
            if 'progress' not in status_data:
                status_data['progress'] = 0
            if 'results' not in status_data:
                status_data['results'] = {'success': 0, 'failed': 0, 'skipped': 0}
            
            return jsonify({
                'status': 'success',
                **status_data
            })
            
        except Exception as e:
            logger.error(f"Error getting bot status: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get status: {str(e)}',
                'process_running': False
            }), 500

    @app.route('/bot_activity_stats', methods=['GET'])
    def get_bot_activity_stats():
        """Get bot activity statistics from files"""
        try:
            # Get stats from file
            stats = get_stats()
            
            # Get screenshot count
            screenshot_count = 0
            if os.path.exists(SCREENSHOT_FOLDER):
                screenshot_count = len([f for f in os.listdir(SCREENSHOT_FOLDER) 
                                       if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            
            return jsonify({
                'status': 'success',
                'stats': {
                    'total_runs': stats.get('total_runs', 0),
                    'successful': stats.get('successful', 0),
                    'failed': stats.get('failed', 0),
                    'skipped': stats.get('skipped', 0),
                    'screenshots': screenshot_count,
                    'session_start': stats.get('session_start', ''),
                    'last_reset': stats.get('last_reset', '')
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting bot activity stats: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get stats: {str(e)}'
            }), 500
    
    @app.route('/bot_activity_log', methods=['GET'])
    def get_bot_activity_log_route():
        """Get recent activity log entries"""
        try:
            lines = request.args.get('lines', 50, type=int)
            log_content = get_activity_log(lines)
            
            return jsonify({
                'status': 'success',
                'log': log_content
            })
            
        except Exception as e:
            logger.error(f"Error getting activity log: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get log: {str(e)}'
            }), 500
    
    @app.route('/reset_bot_stats', methods=['POST'])
    def reset_bot_stats_route():
        """Reset bot statistics"""
        try:
            stats = reset_stats()
            
            return jsonify({
                'status': 'success',
                'message': 'Statistics reset successfully',
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error resetting stats: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to reset stats: {str(e)}'
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
        """Get bot execution logs from the log file"""
        try:
            logs = []
            
            # Read from bot execution log file
            if os.path.exists(BOT_LOG_FILE):
                try:
                    with open(BOT_LOG_FILE, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logs.append({
                            'type': 'execution_log',
                            'content': content
                        })
                except Exception as e:
                    logs.append({
                        'type': 'error',
                        'message': f'Could not read log file: {str(e)}'
                    })
            
            # Read from status file for recent activity
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, 'r') as f:
                        status = json.load(f)
                    logs.append({
                        'type': 'status',
                        'timestamp': status.get('timestamp', ''),
                        'message': status.get('message', ''),
                        'status': status.get('status', '')
                    })
                except:
                    pass
            
            return jsonify({
                'status': 'success',
                'logs': logs,
                'log_file': os.path.abspath(BOT_LOG_FILE)
            })
            
        except Exception as e:
            logger.error(f"Error getting bot logs: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to get logs: {str(e)}'
            }), 500

    @app.route('/screenshots', methods=['GET'])
    def list_screenshots():
        """List all screenshots in fbmpss folder"""
        try:
            screenshots = []
            
            if os.path.exists(SCREENSHOT_FOLDER):
                for filename in os.listdir(SCREENSHOT_FOLDER):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        filepath = os.path.join(SCREENSHOT_FOLDER, filename)
                        stats = os.stat(filepath)
                        screenshots.append({
                            'filename': filename,
                            'size': stats.st_size,
                            'modified': datetime.fromtimestamp(stats.st_mtime).isoformat()
                        })
            
            screenshots.sort(key=lambda x: x['modified'], reverse=True)
            
            return jsonify({
                'status': 'success',
                'screenshots': screenshots,
                'count': len(screenshots)
            })
            
        except Exception as e:
            logger.error(f"Error listing screenshots: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to list screenshots: {str(e)}'
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
        global bot_process, bot_start_time, bot_log_file
        
        try:
            # Close log file if open
            if bot_log_file is not None:
                try:
                    bot_log_file.close()
                    bot_log_file = None
                except:
                    pass
            
            # Clear stop file
            if os.path.exists(STOP_FILE):
                os.remove(STOP_FILE)
            
            # Reset status file to idle
            with open(STATUS_FILE, 'w') as f:
                json.dump({
                    'status': 'idle',
                    'message': 'Ready to start',
                    'timestamp': datetime.now().isoformat(),
                    'process_running': False,
                    'progress': 0,
                    'total_profiles': 0,
                    'total_listings': 0,
                    'current_profile_idx': 0,
                    'current_listing_idx': 0,
                    'current_profile': '',
                    'current_listing': '',
                    'results': {'success': 0, 'failed': 0, 'skipped': 0}
                }, f, indent=2)
            
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