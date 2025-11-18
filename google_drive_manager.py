"""
Google Drive Integration Module with Folder Support
Handles file uploads, listing, and deletion operations with subfolder organization
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
    
    def ensure_folder_exists(self, folder_name='fbBotMedia', parent_id=None):
        """Ensure a folder exists in Google Drive"""
        if not self.service:
            self.authenticate()
        
        # Build query
        query_parts = [f"name='{folder_name}'", "mimeType='application/vnd.google-apps.folder'", "trashed=false"]
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        
        query = " and ".join(query_parts)
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            # Folder exists
            folder_id = folders[0]['id']
            print(f"Found existing folder: {folder_name} (ID: {folder_id})")
        else:
            # Create folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            print(f"Created new folder: {folder_name} (ID: {folder_id})")
        
        if folder_name == 'fbBotMedia':
            self.folder_id = folder_id
        
        return folder_id
    
    def get_or_create_subfolder(self, subfolder_name, parent_folder_id=None):
        """Get or create a subfolder within fbBotMedia"""
        if not self.service:
            self.authenticate()
        
        if not parent_folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            parent_folder_id = self.folder_id
        
        return self.ensure_folder_exists(subfolder_name, parent_folder_id)
    
    def list_subfolders(self, parent_folder_id=None):
        """List all subfolders in fbBotMedia"""
        if not self.service:
            self.authenticate()
        
        if not parent_folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            parent_folder_id = self.folder_id
        
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, createdTime, modifiedTime)',
            orderBy='name'
        ).execute()
        
        folders = results.get('files', [])
        return folders
    
    def list_files_in_folder(self, folder_id=None, page_size=100):
        """List all files in a specific folder"""
        if not self.service:
            self.authenticate()
        
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            folder_id = self.folder_id
        
        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        
        results = self.service.files().list(
            q=query,
            pageSize=page_size,
            fields='files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, thumbnailLink)',
            orderBy='createdTime desc'
        ).execute()
        
        files = results.get('files', [])
        return files
    
    def get_folder_structure(self):
        """Get complete folder structure with files"""
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists()
        
        # Get root files
        root_files = self.list_files_in_folder(self.folder_id)
        
        # Get all subfolders
        subfolders = self.list_subfolders(self.folder_id)
        
        # Build structure
        structure = {
            'root': {
                'id': self.folder_id,
                'name': 'fbBotMedia',
                'files': root_files,
                'file_count': len(root_files)
            },
            'folders': []
        }
        
        # Get files for each subfolder
        for folder in subfolders:
            folder_files = self.list_files_in_folder(folder['id'])
            structure['folders'].append({
                'id': folder['id'],
                'name': folder['name'],
                'files': folder_files,
                'file_count': len(folder_files),
                'createdTime': folder.get('createdTime'),
                'modifiedTime': folder.get('modifiedTime')
            })
        
        return structure
    
    def upload_file(self, file_path=None, file_content=None, filename=None, mime_type=None, folder_id=None, subfolder_name=None):
        """
        Upload a file to Google Drive in fbBotMedia folder or subfolder
        
        Args:
            file_path: Path to local file (if uploading from disk)
            file_content: File content as bytes (if uploading from memory)
            filename: Name for the file
            mime_type: MIME type of the file
            folder_id: Specific folder ID to upload to
            subfolder_name: Name of subfolder to create/use (if not using folder_id)
            
        Returns:
            dict: File metadata including id, name, and webViewLink
        """
        if not self.service:
            self.authenticate()
        
        # Determine target folder
        if folder_id:
            target_folder_id = folder_id
        elif subfolder_name:
            target_folder_id = self.get_or_create_subfolder(subfolder_name)
        else:
            if not self.folder_id:
                self.ensure_folder_exists()
            target_folder_id = self.folder_id
        
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
            'parents': [target_folder_id]
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
            fields='id, name, mimeType, size, createdTime, webViewLink, webContentLink, parents'
        ).execute()
        
        # Make file accessible (optional - adjust permissions as needed)
        self.service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        print(f"Uploaded: {filename} (ID: {file['id']}) to folder: {target_folder_id}")
        return file
    
    def upload_multiple_files(self, file_paths, subfolder_name=None):
        """
        Upload multiple files to a subfolder
        
        Args:
            file_paths: List of file paths
            subfolder_name: Name of subfolder to create/use
            
        Returns:
            list: List of uploaded file metadata
        """
        results = []
        
        for file_path in file_paths:
            try:
                result = self.upload_file(
                    file_path=file_path,
                    subfolder_name=subfolder_name
                )
                results.append(result)
            except Exception as e:
                print(f"Failed to upload {file_path}: {str(e)}")
                results.append({
                    'error': str(e),
                    'filename': os.path.basename(file_path)
                })
        
        return results
    
    def list_files(self, folder_name='fbBotMedia', page_size=100):
        """List all files in the fbBotMedia folder (legacy method)"""
        if not self.service:
            self.authenticate()
        
        if not self.folder_id:
            self.ensure_folder_exists(folder_name)
        
        # Get all files recursively
        all_files = []
        
        # Get root files
        root_files = self.list_files_in_folder(self.folder_id)
        all_files.extend(root_files)
        
        # Get subfolder files
        subfolders = self.list_subfolders(self.folder_id)
        for folder in subfolders:
            folder_files = self.list_files_in_folder(folder['id'])
            # Add folder name to file metadata
            for file in folder_files:
                file['folder_name'] = folder['name']
            all_files.extend(folder_files)
        
        return all_files
    
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
    
    def delete_folder(self, folder_id):
        """Delete a folder from Google Drive"""
        if not self.service:
            self.authenticate()
        
        try:
            self.service.files().delete(fileId=folder_id).execute()
            print(f"Deleted folder: {folder_id}")
            return True
        except Exception as e:
            print(f"Error deleting folder {folder_id}: {str(e)}")
            return False
    
    def get_file_metadata(self, file_id):
        """Get metadata for a specific file"""
        if not self.service:
            self.authenticate()
        
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, thumbnailLink, parents'
            ).execute()
            return file
        except Exception as e:
            print(f"Error getting file metadata {file_id}: {str(e)}")
            return None
    
    def get_multiple_files_metadata(self, file_ids):
        """Get metadata for multiple files"""
        results = []
        for file_id in file_ids:
            metadata = self.get_file_metadata(file_id)
            if metadata:
                results.append(metadata)
        return results
    
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
    
    def search_files(self, query_string, folder_id=None):
        """
        Search for files in fbBotMedia folder or subfolder
        
        Args:
            query_string: Search term
            folder_id: Specific folder to search in (optional)
            
        Returns:
            list: Matching files
        """
        if not self.service:
            self.authenticate()
        
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            # Search in all folders
            query = f"name contains '{query_string}' and trashed=false"
        else:
            query = f"'{folder_id}' in parents and name contains '{query_string}' and trashed=false"
        
        results = self.service.files().list(
            q=query,
            pageSize=100,
            fields='files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink, parents)',
            orderBy='createdTime desc'
        ).execute()
        
        return results.get('files', [])
    
    def get_folder_stats(self, folder_id=None):
        """Get statistics about a folder"""
        if not self.service:
            self.authenticate()
        
        if not folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            folder_id = self.folder_id
        
        # Get folder structure
        structure = self.get_folder_structure()
        
        total_files = structure['root']['file_count']
        total_size = 0
        file_types = {}
        
        # Count root files
        for file in structure['root']['files']:
            size = int(file.get('size', 0))
            total_size += size
            
            mime_type = file.get('mimeType', 'unknown')
            file_type = mime_type.split('/')[0] if '/' in mime_type else 'other'
            file_types[file_type] = file_types.get(file_type, 0) + 1
        
        # Count subfolder files
        for folder in structure['folders']:
            total_files += folder['file_count']
            for file in folder['files']:
                size = int(file.get('size', 0))
                total_size += size
                
                mime_type = file.get('mimeType', 'unknown')
                file_type = mime_type.split('/')[0] if '/' in mime_type else 'other'
                file_types[file_type] = file_types.get(file_type, 0) + 1
        
        return {
            'total_files': total_files,
            'total_folders': len(structure['folders']),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types,
            'folders': [{'name': f['name'], 'file_count': f['file_count']} for f in structure['folders']]
        }


# Singleton instance
_drive_manager = None

def get_drive_manager():
    """Get or create the global GoogleDriveManager instance"""
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager
