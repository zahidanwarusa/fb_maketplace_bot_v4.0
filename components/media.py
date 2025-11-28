"""
Media Component
Handles Google Drive media management routes
"""

from flask import Blueprint, request, jsonify
import os
import logging
import traceback
from werkzeug.utils import secure_filename

media_bp = Blueprint('media', __name__)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'mp4', 'avi', 'mov', 'zip'}
MAX_FILE_SIZE = 100 * 1024 * 1024


def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def format_file_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def init_media_routes(app, get_drive_manager):
    """Initialize media management routes"""
    
    @app.route('/upload_to_drive', methods=['POST'])
    def upload_to_drive():
        try:
            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': 'No file provided'}), 400
            
            file = request.files['file']
            folder_name = request.form.get('folder_name', '')
            
            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({'status': 'error', 'message': 'Invalid file'}), 400
            
            filename = secure_filename(file.filename)
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            
            temp_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(temp_path)
            
            try:
                drive_manager = get_drive_manager()
                drive_manager.authenticate()
                drive_manager.ensure_folder_exists()
                
                result = drive_manager.upload_file(file_path=temp_path, subfolder_name=folder_name if folder_name else None)
                os.remove(temp_path)
                
                return jsonify({
                    'status': 'success',
                    'message': 'File uploaded',
                    'file': {
                        'id': result['id'],
                        'name': result['name'],
                        'webViewLink': result.get('webViewLink', ''),
                        'folder': folder_name if folder_name else 'root'
                    }
                })
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e
        except Exception as e:
            logger.error(f"Error uploading: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/list_drive_files', methods=['GET'])
    def list_drive_files():
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            files = drive_manager.list_files()
            
            formatted_files = []
            for file in files:
                formatted_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'createdTime': file.get('createdTime', ''),
                    'webViewLink': file.get('webViewLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            return jsonify({'status': 'success', 'files': formatted_files, 'total': len(formatted_files)})
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/delete_drive_file', methods=['POST'])
    def delete_drive_file():
        try:
            data = request.json
            if not data or not data.get('file_id'):
                return jsonify({'status': 'error', 'message': 'No file ID provided'}), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            success = drive_manager.delete_file(data['file_id'])
            
            if success:
                return jsonify({'status': 'success', 'message': 'File deleted'})
            return jsonify({'status': 'error', 'message': 'Failed to delete'}), 500
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/get_drive_stats', methods=['GET'])
    def get_drive_stats():
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            stats = drive_manager.get_folder_stats()
            return jsonify({'status': 'success', 'stats': stats})
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/search_drive_files', methods=['GET'])
    def search_drive_files():
        try:
            query = request.args.get('q', '')
            if not query:
                return jsonify({'status': 'error', 'message': 'No query provided'}), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            files = drive_manager.search_files(query[:100])
            
            formatted_files = []
            for file in files:
                formatted_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'createdTime': file.get('createdTime', ''),
                    'webViewLink': file.get('webViewLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            return jsonify({'status': 'success', 'files': formatted_files, 'total': len(formatted_files)})
        except Exception as e:
            logger.error(f"Error searching: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/get_drive_structure', methods=['GET'])
    def get_drive_structure():
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            structure = drive_manager.get_folder_structure()
            
            formatted_structure = {
                'root': {
                    'id': structure['root']['id'],
                    'name': structure['root']['name'],
                    'file_count': structure['root']['file_count'],
                    'files': []
                },
                'folders': []
            }
            
            for file in structure['root']['files']:
                formatted_structure['root']['files'].append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'createdTime': file.get('createdTime', ''),
                    'webViewLink': file.get('webViewLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            
            for folder in structure['folders']:
                formatted_files = []
                for file in folder['files']:
                    formatted_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mimeType': file.get('mimeType', ''),
                        'size': int(file.get('size', 0)),
                        'sizeFormatted': format_file_size(int(file.get('size', 0))),
                        'createdTime': file.get('createdTime', ''),
                        'webViewLink': file.get('webViewLink', ''),
                        'thumbnailLink': file.get('thumbnailLink', '')
                    })
                formatted_structure['folders'].append({
                    'id': folder['id'],
                    'name': folder['name'],
                    'file_count': folder['file_count'],
                    'files': formatted_files
                })
            
            return jsonify({'status': 'success', 'structure': formatted_structure})
        except Exception as e:
            logger.error(f"Error getting structure: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/create_drive_folder', methods=['POST'])
    def create_drive_folder():
        try:
            data = request.json
            if not data or not data.get('folder_name'):
                return jsonify({'status': 'error', 'message': 'folder_name is required'}), 400
            
            folder_name = data['folder_name'].strip()[:100]
            if not folder_name:
                return jsonify({'status': 'error', 'message': 'Folder name cannot be empty'}), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            drive_manager.ensure_folder_exists()
            folder_id = drive_manager.get_or_create_subfolder(folder_name)
            
            return jsonify({'status': 'success', 'message': f'Folder "{folder_name}" ready', 'folder_id': folder_id, 'folder_name': folder_name})
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/delete_drive_folder', methods=['POST'])
    def delete_drive_folder():
        try:
            data = request.json
            if not data or not data.get('folder_id'):
                return jsonify({'status': 'error', 'message': 'folder_id is required'}), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            success = drive_manager.delete_folder(data['folder_id'])
            
            if success:
                return jsonify({'status': 'success', 'message': 'Folder deleted'})
            return jsonify({'status': 'error', 'message': 'Failed to delete folder'}), 500
        except Exception as e:
            logger.error(f"Error deleting folder: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
