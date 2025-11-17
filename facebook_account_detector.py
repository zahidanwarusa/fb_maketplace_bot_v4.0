"""
Facebook Account Detector
Extracts Facebook account information from Chrome profiles
"""

import os
import json
import sqlite3
import shutil
from pathlib import Path


def get_facebook_accounts_from_profile(profile_path):
    """
    Extract Facebook account information from a Chrome profile
    
    Args:
        profile_path: Path to the Chrome profile directory
        
    Returns:
        list: List of Facebook accounts found in the profile
    """
    facebook_accounts = []
    
    try:
        # Path to Chrome cookies database
        cookies_path = os.path.join(profile_path, 'Network', 'Cookies')
        
        if not os.path.exists(cookies_path):
            # Try old location
            cookies_path = os.path.join(profile_path, 'Cookies')
            
        if not os.path.exists(cookies_path):
            print(f"Cookies file not found for profile: {profile_path}")
            return facebook_accounts
        
        # Create a temporary copy of the cookies file (Chrome locks it)
        temp_cookies = cookies_path + '.tmp'
        try:
            shutil.copy2(cookies_path, temp_cookies)
        except Exception as e:
            print(f"Could not copy cookies file: {e}")
            return facebook_accounts
        
        try:
            # Connect to the cookies database
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            # Query for Facebook cookies
            # We look for 'c_user' cookie which contains the Facebook user ID
            query = """
                SELECT name, value, host_key 
                FROM cookies 
                WHERE host_key LIKE '%facebook.com%' 
                AND name IN ('c_user', 'xs')
                ORDER BY creation_utc DESC
            """
            
            cursor.execute(query)
            cookies = cursor.fetchall()
            
            # Extract user IDs from c_user cookie
            user_ids = set()
            for cookie_name, cookie_value, host in cookies:
                if cookie_name == 'c_user':
                    user_ids.add(cookie_value)
            
            # For each user ID found, try to get more information
            for user_id in user_ids:
                account_info = {
                    'id': user_id,
                    'name': f'Facebook User {user_id}',
                    'email': None,
                    'selected': True  # Default to selected
                }
                
                # Try to get profile name from Preferences file
                prefs_path = os.path.join(profile_path, 'Preferences')
                if os.path.exists(prefs_path):
                    try:
                        with open(prefs_path, 'r', encoding='utf-8') as f:
                            prefs = json.load(f)
                            
                        # Check for Facebook-related data in preferences
                        # This is a best-effort attempt as Chrome doesn't store FB names directly
                        account_info['name'] = f'Facebook Account (ID: {user_id})'
                        
                    except Exception as e:
                        print(f"Could not read preferences: {e}")
                
                facebook_accounts.append(account_info)
            
            conn.close()
            
        finally:
            # Clean up temporary file
            try:
                os.remove(temp_cookies)
            except:
                pass
                
    except Exception as e:
        print(f"Error extracting Facebook accounts from {profile_path}: {e}")
    
    return facebook_accounts


def get_facebook_login_status(profile_path):
    """
    Quick check if Facebook is logged in for a profile
    
    Args:
        profile_path: Path to the Chrome profile directory
        
    Returns:
        bool: True if Facebook session appears to be active
    """
    try:
        cookies_path = os.path.join(profile_path, 'Network', 'Cookies')
        if not os.path.exists(cookies_path):
            cookies_path = os.path.join(profile_path, 'Cookies')
            
        if not os.path.exists(cookies_path):
            return False
        
        # Create temporary copy
        temp_cookies = cookies_path + '.tmp'
        try:
            shutil.copy2(cookies_path, temp_cookies)
        except:
            return False
        
        try:
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            # Check for c_user cookie (indicates logged in)
            cursor.execute("""
                SELECT COUNT(*) FROM cookies 
                WHERE host_key LIKE '%facebook.com%' 
                AND name = 'c_user'
            """)
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        finally:
            try:
                os.remove(temp_cookies)
            except:
                pass
                
    except Exception as e:
        print(f"Error checking Facebook login status: {e}")
        return False


def get_all_profiles_with_facebook_accounts():
    """
    Get all Chrome profiles with their Facebook accounts
    
    Returns:
        dict: Dictionary mapping profile names to Facebook accounts
    """
    user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
    profiles_with_accounts = {}
    
    try:
        # Get all profile directories
        profile_dirs = []
        profile_dirs.extend(Path(user_data_dir).glob('Profile *'))
        default_profile = Path(user_data_dir) / 'Default'
        if default_profile.exists():
            profile_dirs.append(default_profile)
        
        for profile_dir in profile_dirs:
            profile_name = profile_dir.name
            facebook_accounts = get_facebook_accounts_from_profile(str(profile_dir))
            
            if facebook_accounts:
                profiles_with_accounts[profile_name] = facebook_accounts
                
    except Exception as e:
        print(f"Error getting profiles with Facebook accounts: {e}")
    
    return profiles_with_accounts


# Example usage
if __name__ == '__main__':
    print("Detecting Facebook accounts in Chrome profiles...")
    print("=" * 60)
    
    profiles = get_all_profiles_with_facebook_accounts()
    
    if profiles:
        for profile_name, accounts in profiles.items():
            print(f"\n{profile_name}:")
            for account in accounts:
                print(f"  - {account['name']} (ID: {account['id']})")
    else:
        print("No Facebook accounts found in any profile")
