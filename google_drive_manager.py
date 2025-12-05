"""
Google Drive Integration Module
Handles uploading, downloading, and managing files in Google Drive
"""

import os
import io
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
import pickle
from datetime import datetime
import mimetypes

SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveManager:
    def __init__(self, credentials_file='credentials.json'):
        self.credentials_file = credentials_file
        self.token_file = 'token.pickle'
        self.service = None
        self.folder_id = None
        
    def authenticate(self):
        """Authenticate with Google Drive API"""
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        return True
    
    def ensure_folder_exists(self, folder_name='fbBotMedia', parent_id=None):
        """Ensure a folder exists, create if it doesn't"""
        if not self.service:
            self.authenticate()
        
        query_parts = [f"name='{folder_name}'", "mimeType='application/vnd.google-apps.folder'", "trashed=false"]
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        
        query = " and ".join(query_parts)
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = results.get('files', [])
        
        if folders:
            folder_id = folders[0]['id']
        else:
            file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_id:
                file_metadata['parents'] = [parent_id]
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
        
        if folder_name == 'fbBotMedia':
            self.folder_id = folder_id
        return folder_id
    
    def get_or_create_subfolder(self, subfolder_name, parent_folder_id=None):
        """Get or create a subfolder"""
        if not self.service:
            self.authenticate()
        if not parent_folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            parent_folder_id = self.folder_id
        return self.ensure_folder_exists(subfolder_name, parent_folder_id)
    
    def list_subfolders(self, parent_folder_id=None):
        """List subfolders in a folder"""
        if not self.service:
            self.authenticate()
        if not parent_folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            parent_folder_id = self.folder_id
        
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name, createdTime, modifiedTime)', orderBy='name').execute()
        return results.get('files', [])
    
    def list_files_in_folder(self, folder_id=None, page_size=100):
        """List files in a folder"""
        if not self.service:
            self.authenticate()
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            folder_id = self.folder_id
        
        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, pageSize=page_size, fields='files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, thumbnailLink)', orderBy='createdTime desc').execute()
        return results.get('files', [])
    
    def get_folder_structure(self):
        """Get complete folder structure"""
        if not self.service:
            self.authenticate()
        if not self.folder_id:
            self.ensure_folder_exists()
        
        root_files = self.list_files_in_folder(self.folder_id)
        subfolders = self.list_subfolders(self.folder_id)
        
        structure = {'root': {'id': self.folder_id, 'name': 'fbBotMedia', 'files': root_files, 'file_count': len(root_files)}, 'folders': []}
        
        for folder in subfolders:
            folder_files = self.list_files_in_folder(folder['id'])
            structure['folders'].append({'id': folder['id'], 'name': folder['name'], 'files': folder_files, 'file_count': len(folder_files)})
        
        return structure
    
    def upload_file(self, file_path=None, file_content=None, filename=None, mime_type=None, folder_id=None, subfolder_name=None):
        """Upload a file to Google Drive"""
        if not self.service:
            self.authenticate()
        
        if folder_id:
            target_folder_id = folder_id
        elif subfolder_name:
            target_folder_id = self.get_or_create_subfolder(subfolder_name)
        else:
            if not self.folder_id:
                self.ensure_folder_exists()
            target_folder_id = self.folder_id
        
        if file_path:
            if not filename:
                filename = os.path.basename(file_path)
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = 'application/octet-stream'
        elif not filename:
            filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        file_metadata = {'name': filename, 'parents': [target_folder_id]}
        
        if file_path:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        else:
            media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=True)
        
        file = self.service.files().create(body=file_metadata, media_body=media, fields='id, name, mimeType, size, createdTime, webViewLink, webContentLink, parents').execute()
        
        self.service.permissions().create(fileId=file['id'], body={'type': 'anyone', 'role': 'reader'}).execute()
        return file
    
    def list_files(self, folder_name='fbBotMedia', page_size=100):
        """List all files including subfolders"""
        if not self.service:
            self.authenticate()
        if not self.folder_id:
            self.ensure_folder_exists(folder_name)
        
        all_files = []
        root_files = self.list_files_in_folder(self.folder_id)
        all_files.extend(root_files)
        
        subfolders = self.list_subfolders(self.folder_id)
        for folder in subfolders:
            folder_files = self.list_files_in_folder(folder['id'])
            for file in folder_files:
                file['folder_name'] = folder['name']
            all_files.extend(folder_files)
        
        return all_files
    
    def delete_file(self, file_id):
        """Delete a file"""
        if not self.service:
            self.authenticate()
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except:
            return False
    
    def delete_folder(self, folder_id):
        """Delete a folder"""
        if not self.service:
            self.authenticate()
        try:
            self.service.files().delete(fileId=folder_id).execute()
            return True
        except:
            return False
    
    def search_files(self, query_string, folder_id=None):
        """Search for files by name"""
        if not self.service:
            self.authenticate()
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            query = f"name contains '{query_string}' and trashed=false"
        else:
            query = f"'{folder_id}' in parents and name contains '{query_string}' and trashed=false"
        
        results = self.service.files().list(q=query, pageSize=100, fields='files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink, parents)', orderBy='createdTime desc').execute()
        return results.get('files', [])
    
    def get_folder_stats(self, folder_id=None):
        """Get folder statistics"""
        if not self.service:
            self.authenticate()
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            folder_id = self.folder_id
        
        structure = self.get_folder_structure()
        total_files = structure['root']['file_count']
        total_size = 0
        file_types = {}
        
        for file in structure['root']['files']:
            size = int(file.get('size', 0))
            total_size += size
            mime_type = file.get('mimeType', 'unknown')
            file_type = mime_type.split('/')[0] if '/' in mime_type else 'other'
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        for folder in structure['folders']:
            total_files += folder['file_count']
            for file in folder['files']:
                size = int(file.get('size', 0))
                total_size += size
                mime_type = file.get('mimeType', 'unknown')
                file_type = mime_type.split('/')[0] if '/' in mime_type else 'other'
                file_types[file_type] = file_types.get(file_type, 0) + 1
        
        return {'total_files': total_files, 'total_folders': len(structure['folders']), 'total_size': total_size, 'total_size_mb': round(total_size / (1024 * 1024), 2), 'file_types': file_types}

    # ============================================================================
    # DOWNLOAD METHODS - For Bot.py Google Drive image support
    # ============================================================================
    
    def download_file(self, file_id, destination_path):
        """Download a file from Google Drive by file ID"""
        if not self.service:
            self.authenticate()
        
        try:
            # Get file metadata first
            file_metadata = self.service.files().get(fileId=file_id, fields='name, mimeType').execute()
            
            # Download the file
            request = self.service.files().get_media(fileId=file_id)
            
            with open(destination_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return True, file_metadata.get('name', 'unknown')
        except Exception as e:
            print(f"Error downloading file {file_id}: {e}")
            return False, str(e)

    def download_folder_contents(self, folder_id, destination_folder):
        """Download all images from a Google Drive folder to a local folder"""
        if not self.service:
            self.authenticate()
        
        # Create destination folder if it doesn't exist
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        
        # List all image files in the folder
        query = f"'{folder_id}' in parents and trashed=false and (mimeType contains 'image/')"
        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields='files(id, name, mimeType)'
        ).execute()
        
        files = results.get('files', [])
        downloaded = []
        
        for file in files:
            file_path = os.path.join(destination_folder, file['name'])
            success, _ = self.download_file(file['id'], file_path)
            if success:
                downloaded.append(file_path)
                print(f"  ✓ Downloaded: {file['name']}")
            else:
                print(f"  ✗ Failed: {file['name']}")
        
        return downloaded

    def extract_file_id_from_url(self, url):
        """Extract Google Drive file ID from various URL formats"""
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID/
            r'id=([a-zA-Z0-9_-]+)',        # ?id=FILE_ID
            r'/folders/([a-zA-Z0-9_-]+)',  # /folders/FOLDER_ID
            r'^([a-zA-Z0-9_-]{25,})$'      # Just the ID itself
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def is_folder(self, file_id):
        """Check if a Google Drive ID is a folder"""
        if not self.service:
            self.authenticate()
        
        try:
            file_metadata = self.service.files().get(fileId=file_id, fields='mimeType').execute()
            return file_metadata.get('mimeType') == 'application/vnd.google-apps.folder'
        except:
            return False

    def download_from_url(self, drive_url, destination_folder):
        """Download images from a Google Drive URL (file or folder) to local folder"""
        file_id = self.extract_file_id_from_url(drive_url)
        
        if not file_id:
            print(f"❌ Could not extract file ID from URL: {drive_url}")
            return []
        
        # Create destination folder
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        
        # Check if it's a folder or a single file
        if self.is_folder(file_id):
            print(f"📁 Downloading folder contents...")
            return self.download_folder_contents(file_id, destination_folder)
        else:
            # Single file
            print(f"📄 Downloading single file...")
            try:
                file_metadata = self.service.files().get(fileId=file_id, fields='name').execute()
                filename = file_metadata.get('name', f'image_{file_id}.jpg')
                file_path = os.path.join(destination_folder, filename)
                success, _ = self.download_file(file_id, file_path)
                if success:
                    print(f"  ✓ Downloaded: {filename}")
                    return [file_path]
            except Exception as e:
                print(f"❌ Error downloading: {e}")
        
        return []

    def get_file_metadata(self, file_id):
        """Get metadata for a file"""
        if not self.service:
            self.authenticate()
        
        try:
            return self.service.files().get(
                fileId=file_id, 
                fields='id, name, mimeType, size, createdTime, webViewLink, webContentLink'
            ).execute()
        except Exception as e:
            print(f"Error getting file metadata: {e}")
            return None


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_drive_manager = None

def get_drive_manager():
    """Get singleton instance of GoogleDriveManager"""
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager