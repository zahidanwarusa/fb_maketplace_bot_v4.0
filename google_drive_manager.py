"""
Google Drive Integration Module
Handles file uploads, listing, and deletion operations
"""

import os
import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import pickle
from datetime import datetime
import mimetypes

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveManager:
    def __init__(self, credentials_file='credentials.json'):
        self.credentials_file = credentials_file
        self.token_file = 'token.pickle'
        self.service = None
        self.folder_id = None
        
    def authenticate(self):
        """Authenticate and create Google Drive service"""
        creds = None
        
        # Check if token.pickle exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Please download credentials.json from Google Cloud Console"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        return True
    
    def ensure_folder_exists(self, folder_name='fbBotMedia'):
        """Ensure the fbBotMedia folder exists in Google Drive"""
        if not self.service:
            self.authenticate()
        
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            # Folder exists
            self.folder_id = folders[0]['id']
            print(f"Found existing folder: {folder_name} (ID: {self.folder_id})")
        else:
            # Create folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            self.folder_id = folder.get('id')
            print(f"Created new folder: {folder_name} (ID: {self.folder_id})")
        
        return self.folder_id
    
    def upload_file(self, file_path=None, file_content=None, filename=None, mime_type=None):
        """
        Upload a file to Google Drive in fbBotMedia folder
        
        Args:
            file_path: Path to local file (if uploading from disk)
            file_content: File content as bytes (if uploading from memory)
            filename: Name for the file
            mime_type: MIME type of the file
            
        Returns:
            dict: File metadata including id, name, and webViewLink
        """
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists()
        
        # Determine filename and mime type
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
        
        # Prepare file metadata
        file_metadata = {
            'name': filename,
            'parents': [self.folder_id]
        }
        
        # Upload file
        if file_path:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        else:
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, mimeType, size, createdTime, webViewLink, webContentLink'
        ).execute()
        
        # Make file accessible (optional - adjust permissions as needed)
        self.service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        print(f"Uploaded: {filename} (ID: {file['id']})")
        return file
    
    def list_files(self, folder_name='fbBotMedia', page_size=100):
        """List all files in the fbBotMedia folder"""
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists(folder_name)
        
        query = f"'{self.folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            pageSize=page_size,
            fields='files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, thumbnailLink)',
            orderBy='createdTime desc'
        ).execute()
        
        files = results.get('files', [])
        return files
    
    def delete_file(self, file_id):
        """Delete a file from Google Drive"""
        if not self.service:
            self.authenticate()
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            print(f"Deleted file: {file_id}")
            return True
        except Exception as e:
            print(f"Error deleting file {file_id}: {str(e)}")
            return False
    
    def get_file_metadata(self, file_id):
        """Get metadata for a specific file"""
        if not self.service:
            self.authenticate()
        
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, thumbnailLink'
            ).execute()
            return file
        except Exception as e:
            print(f"Error getting file metadata {file_id}: {str(e)}")
            return None
    
    def create_folder_path(self, folder_path):
        """
        Create a nested folder path in Google Drive
        
        Args:
            folder_path: String like "fbBotMedia/2024/January"
            
        Returns:
            str: ID of the deepest folder
        """
        if not self.service:
            self.authenticate()
        
        folders = folder_path.split('/')
        current_parent = 'root'
        
        for folder_name in folders:
            # Check if folder exists
            query = f"name='{folder_name}' and '{current_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            existing_folders = results.get('files', [])
            
            if existing_folders:
                current_parent = existing_folders[0]['id']
            else:
                # Create folder
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent]
                }
                folder = self.service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                current_parent = folder.get('id')
        
        return current_parent
    
    def get_shareable_link(self, file_id):
        """Get a shareable link for a file"""
        if not self.service:
            self.authenticate()
        
        try:
            # Make sure file is shared with anyone
            self.service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            # Get file metadata with link
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink, webContentLink'
            ).execute()
            
            return file.get('webViewLink') or file.get('webContentLink')
        except Exception as e:
            print(f"Error getting shareable link for {file_id}: {str(e)}")
            return None
    
    def search_files(self, query_string):
        """
        Search for files in fbBotMedia folder
        
        Args:
            query_string: Search term
            
        Returns:
            list: Matching files
        """
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists()
        
        query = f"'{self.folder_id}' in parents and name contains '{query_string}' and trashed=false"
        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields='files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink)',
            orderBy='createdTime desc'
        ).execute()
        
        return results.get('files', [])
    
    def get_folder_stats(self):
        """Get statistics about the fbBotMedia folder"""
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists()
        
        files = self.list_files()
        
        total_size = 0
        file_types = {}
        
        for file in files:
            # Count size
            size = int(file.get('size', 0))
            total_size += size
            
            # Count by type
            mime_type = file.get('mimeType', 'unknown')
            file_type = mime_type.split('/')[0] if '/' in mime_type else 'other'
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        return {
            'total_files': len(files),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types
        }


# Singleton instance
_drive_manager = None

def get_drive_manager():
    """Get or create the global GoogleDriveManager instance"""
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager
