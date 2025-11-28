"""
Google Drive Integration Module
NOTE: Copy your existing google_drive_manager.py file here
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

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveManager:
    def __init__(self, credentials_file='credentials.json'):
        self.credentials_file = credentials_file
        self.token_file = 'token.pickle'
        self.service = None
        self.folder_id = None
        
    def authenticate(self):
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
        if not self.service:
            self.authenticate()
        if not parent_folder_id:
            if not self.folder_id:
                self.ensure_folder_exists()
            parent_folder_id = self.folder_id
        return self.ensure_folder_exists(subfolder_name, parent_folder_id)
    
    def list_subfolders(self, parent_folder_id=None):
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
        if not self.service:
            self.authenticate()
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except:
            return False
    
    def delete_folder(self, folder_id):
        if not self.service:
            self.authenticate()
        try:
            self.service.files().delete(fileId=folder_id).execute()
            return True
        except:
            return False
    
    def search_files(self, query_string, folder_id=None):
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


_drive_manager = None

def get_drive_manager():
    global _drive_manager
    if _drive_manager is None:
        _drive_manager = GoogleDriveManager()
    return _drive_manager
