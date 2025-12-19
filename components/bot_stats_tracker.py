"""
Bot Statistics Tracker
Tracks bot activity stats using simple text files (no database required)
"""

import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Stats file path
STATS_FILE = 'bot_stats.json'
ACTIVITY_LOG_FILE = 'bot_activity_log.txt'

def init_stats_file():
    """Initialize stats file if it doesn't exist"""
    if not os.path.exists(STATS_FILE):
        stats = {
            'total_runs': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'last_reset': datetime.now().isoformat(),
            'session_start': datetime.now().isoformat()
        }
        save_stats(stats)
        logger.info("✅ Initialized stats file")
    
    if not os.path.exists(ACTIVITY_LOG_FILE):
        with open(ACTIVITY_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"Bot Activity Log - Started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
        logger.info("✅ Initialized activity log file")

def load_stats():
    """Load stats from file"""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        else:
            init_stats_file()
            return load_stats()
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
        return {
            'total_runs': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'last_reset': datetime.now().isoformat(),
            'session_start': datetime.now().isoformat()
        }

def save_stats(stats):
    """Save stats to file"""
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info(f"✅ Stats saved: {stats}")
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def log_activity(profile_name, listing_info, status, duration=None, message=None):
    """Log activity to text file"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{timestamp}] "
        log_entry += f"Profile: {profile_name} | "
        log_entry += f"Listing: {listing_info} | "
        log_entry += f"Status: {status.upper()}"
        
        if duration:
            log_entry += f" | Duration: {duration}s"
        
        if message:
            log_entry += f" | Message: {message}"
        
        log_entry += "\n"
        
        with open(ACTIVITY_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"📝 Activity logged: {status} - {listing_info}")
        
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def increment_stat(stat_type):
    """Increment a specific stat counter"""
    stats = load_stats()
    
    if stat_type in ['total_runs', 'successful', 'failed', 'skipped']:
        stats[stat_type] = stats.get(stat_type, 0) + 1
        save_stats(stats)
        logger.info(f"📊 Incremented {stat_type}: {stats[stat_type]}")
    else:
        logger.warning(f"Unknown stat type: {stat_type}")

def record_run_result(profile_name, listing_info, success, duration=None, message=None):
    """Record a single run result and update stats"""
    stats = load_stats()
    
    # Increment counters
    stats['total_runs'] = stats.get('total_runs', 0) + 1
    
    if success:
        stats['successful'] = stats.get('successful', 0) + 1
        status = 'success'
    else:
        if message and 'stopped' in message.lower():
            stats['skipped'] = stats.get('skipped', 0) + 1
            status = 'skipped'
        else:
            stats['failed'] = stats.get('failed', 0) + 1
            status = 'failed'
    
    save_stats(stats)
    log_activity(profile_name, listing_info, status, duration, message)
    
    logger.info(f"✅ Recorded run: {status} - {listing_info}")
    
    return stats

def get_stats():
    """Get current stats"""
    return load_stats()

def reset_stats():
    """Reset all stats to zero"""
    stats = {
        'total_runs': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'last_reset': datetime.now().isoformat(),
        'session_start': datetime.now().isoformat()
    }
    save_stats(stats)
    
    # Add reset marker to log
    with open(ACTIVITY_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'=' * 80}\n")
        f.write(f"STATS RESET - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'=' * 80}\n\n")
    
    logger.info("🔄 Stats reset")
    return stats

def get_activity_log(lines=50):
    """Get recent activity log entries"""
    try:
        if os.path.exists(ACTIVITY_LOG_FILE):
            with open(ACTIVITY_LOG_FILE, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        return "No activity log available"
    except Exception as e:
        logger.error(f"Error reading activity log: {e}")
        return f"Error reading log: {str(e)}"