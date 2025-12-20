"""
Google Drive Integration Module
Handles downloading images from Google Drive URLs
"""

import os
import re
import shutil
from datetime import datetime

from bot_config import TEMP_IMAGES_FOLDER


# ============================================================================
# GOOGLE DRIVE DETECTION
# ============================================================================

def is_google_drive_url(path):
    """Check if the path is a Google Drive URL"""
    if not path:
        return False
    drive_patterns = [
        'drive.google.com',
        'docs.google.com',
        'googleapis.com'
    ]
    return any(pattern in str(path).lower() for pattern in drive_patterns)


def extract_drive_id(url):
    """Extract Google Drive file/folder ID from URL"""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'/folders/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'^([a-zA-Z0-9_-]{25,})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, str(url))
        if match:
            return match.group(1)
    return None


# ============================================================================
# GOOGLE DRIVE DOWNLOAD
# ============================================================================

def download_drive_images(drive_url, listing_info=""):
    """Download images from Google Drive URL to temp folder"""
    print(f"☁️  Detected Google Drive URL, downloading images...")
    
    # Create unique temp folder for this listing with timestamp to avoid conflicts
    safe_name = "".join(c for c in listing_info if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_folder = os.path.join(TEMP_IMAGES_FOLDER, f"{safe_name}_{timestamp}" if safe_name else f'listing_{timestamp}')
    
    # Create temp folder (using unique name avoids need to delete existing)
    try:
        os.makedirs(temp_folder, exist_ok=True)
    except Exception as e:
        print(f"❌ Could not create temp folder: {e}")
        return None
    
    try:
        # Import the drive manager
        from google_drive_manager import get_drive_manager
        from googleapiclient.http import MediaIoBaseDownload
        
        drive_manager = get_drive_manager()
        drive_manager.authenticate()
        
        file_id = extract_drive_id(drive_url)
        if not file_id:
            print(f"❌ Could not extract file ID from URL: {drive_url}")
            return None
        
        # Check if it's a folder or file
        try:
            file_metadata = drive_manager.service.files().get(
                fileId=file_id, 
                fields='mimeType, name'
            ).execute()
            
            is_folder = file_metadata.get('mimeType') == 'application/vnd.google-apps.folder'
            
            if is_folder:
                # Download all images from folder
                print(f"📁 Downloading images from folder: {file_metadata.get('name', 'Unknown')}")
                
                # Query for image files in the folder
                query = f"'{file_id}' in parents and trashed=false and (mimeType contains 'image/')"
                results = drive_manager.service.files().list(
                    q=query,
                    pageSize=100,
                    fields='files(id, name, mimeType)'
                ).execute()
                
                files = results.get('files', [])
                downloaded = []
                
                for file in files:
                    file_path = os.path.join(temp_folder, file['name'])
                    try:
                        request = drive_manager.service.files().get_media(fileId=file['id'])
                        with open(file_path, 'wb') as f:
                            downloader = MediaIoBaseDownload(f, request)
                            done = False
                            while not done:
                                status, done = downloader.next_chunk()
                        downloaded.append(file_path)
                        print(f"  ✓ {file['name']}")
                    except Exception as e:
                        print(f"  ✗ Failed to download {file['name']}: {e}")
                
            else:
                # Single file - download it
                print(f"📄 Downloading single image: {file_metadata.get('name', 'Unknown')}")
                filename = file_metadata.get('name', f'image_{file_id}.jpg')
                file_path = os.path.join(temp_folder, filename)
                
                try:
                    request = drive_manager.service.files().get_media(fileId=file_id)
                    with open(file_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done:
                            status, done = downloader.next_chunk()
                    print(f"  ✓ {filename}")
                except Exception as e:
                    print(f"  ✗ Failed to download: {e}")
            
            # Check if we got any images
            images = [f for f in os.listdir(temp_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'))]
            if images:
                print(f"✓ Downloaded {len(images)} image(s) to: {temp_folder}")
                return temp_folder
            else:
                print("❌ No images were downloaded")
                return None
                
        except Exception as e:
            print(f"❌ Error accessing Google Drive: {e}")
            return None
            
    except ImportError:
        print("❌ Google Drive manager not available")
        return None
    except Exception as e:
        print(f"❌ Error downloading from Google Drive: {e}")
        return None


# ============================================================================
# CLEANUP
# ============================================================================

def cleanup_temp_images():
    """Clean up temporary images folder with Windows-safe error handling"""
    if not os.path.exists(TEMP_IMAGES_FOLDER):
        return
    
    try:
        # Try to remove the entire folder
        shutil.rmtree(TEMP_IMAGES_FOLDER, ignore_errors=True)
        print(f"🧹 Cleaned up temp images folder")
    except Exception as e:
        # If full cleanup fails, try to clean up individual files
        try:
            for root, dirs, files in os.walk(TEMP_IMAGES_FOLDER, topdown=False):
                for name in files:
                    try:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, 0o777)  # Try to change permissions
                        os.remove(file_path)
                    except:
                        pass  # Skip locked files
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except:
                        pass  # Skip locked dirs
            print(f"🧹 Partially cleaned up temp images folder")
        except Exception as e2:
            print(f"⚠️ Could not fully clean temp folder (files may remain): {e}")
