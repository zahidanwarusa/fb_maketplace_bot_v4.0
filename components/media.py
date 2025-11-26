"""
Media Component
Handles Google Drive media management routes (upload, list, delete, folders)
"""

from flask import Blueprint, request, jsonify
import os
import logging
import traceback
from werkzeug.utils import secure_filename

# Create blueprint
media_bp = Blueprint('media', __name__)

# Get logger
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'mp4', 'avi', 'mov', 'zip'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def allowed_file(filename):
    """Check if file extension is allowed"""
    try:
        if not filename or '.' not in filename:
            return False
        return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    except Exception as e:
        logger.error(f"Error checking file extension for {filename}: {str(e)}")
        return False


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    try:
        if not isinstance(size_bytes, (int, float)):
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    except Exception as e:
        logger.error(f"Error formatting file size: {str(e)}")
        return "Unknown"


def init_media_routes(app, get_drive_manager):
    """Initialize media management routes with app context"""
    
    @app.route('/upload_to_drive', methods=['POST'])
    def upload_to_drive():
        """Upload file to Google Drive with comprehensive error handling"""
        try:
            if 'file' not in request.files:
                return jsonify({
                    'status': 'error',
                    'message': 'No file provided'
                }), 400
            
            file = request.files['file']
            folder_name = request.form.get('folder_name', '')
            
            if file.filename == '':
                return jsonify({
                    'status': 'error',
                    'message': 'No file selected'
                }), 400
            
            if not allowed_file(file.filename):
                return jsonify({
                    'status': 'error',
                    'message': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
                }), 400
            
            # Secure the filename
            filename = secure_filename(file.filename)
            
            if not filename:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid filename'
                }), 400
            
            # Ensure upload folder exists
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            
            # Save temporarily
            temp_path = os.path.join(UPLOAD_FOLDER, filename)
            
            try:
                file.save(temp_path)
            except Exception as e:
                logger.error(f"Failed to save temp file: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to save file: {str(e)}'
                }), 500
            
            # Check file size
            try:
                file_size = os.path.getsize(temp_path)
                if file_size > MAX_FILE_SIZE:
                    os.remove(temp_path)
                    return jsonify({
                        'status': 'error',
                        'message': f'File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB'
                    }), 400
            except Exception as e:
                logger.error(f"Failed to check file size: {str(e)}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to process file'
                }), 500
            
            # Upload to Google Drive
            try:
                drive_manager = get_drive_manager()
                drive_manager.authenticate()
                drive_manager.ensure_folder_exists()
                
                result = drive_manager.upload_file(
                    file_path=temp_path,
                    subfolder_name=folder_name if folder_name else None
                )
                
                logger.info(f"Successfully uploaded file to Google Drive: {filename}")
                
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file: {str(e)}")
                
                return jsonify({
                    'status': 'success',
                    'message': 'File uploaded successfully',
                    'file': {
                        'id': result['id'],
                        'name': result['name'],
                        'size': result.get('size', 0),
                        'mimeType': result.get('mimeType', ''),
                        'webViewLink': result.get('webViewLink', ''),
                        'webContentLink': result.get('webContentLink', ''),
                        'createdTime': result.get('createdTime', ''),
                        'folder': folder_name if folder_name else 'root'
                    }
                })
                
            except Exception as e:
                logger.error(f"Failed to upload to Google Drive: {str(e)}")
                logger.error(traceback.format_exc())
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                return jsonify({
                    'status': 'error',
                    'message': f'Upload to Google Drive failed: {str(e)}'
                }), 500
            
        except Exception as e:
            logger.error(f"Error in upload_to_drive: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Upload failed: {str(e)}'
            }), 500

    @app.route('/list_drive_files', methods=['GET'])
    def list_drive_files():
        """List all files in Google Drive fbBotMedia folder with error handling"""
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            files = drive_manager.list_files()
            
            # Format file data
            formatted_files = []
            for file in files:
                try:
                    formatted_files.append({
                        'id': file['id'],
                        'name': file['name'],
                        'mimeType': file.get('mimeType', ''),
                        'size': int(file.get('size', 0)),
                        'sizeFormatted': format_file_size(int(file.get('size', 0))),
                        'createdTime': file.get('createdTime', ''),
                        'modifiedTime': file.get('modifiedTime', ''),
                        'webViewLink': file.get('webViewLink', ''),
                        'webContentLink': file.get('webContentLink', ''),
                        'thumbnailLink': file.get('thumbnailLink', '')
                    })
                except Exception as e:
                    logger.error(f"Error formatting file {file.get('id', 'unknown')}: {str(e)}")
                    continue
            
            logger.info(f"Successfully listed {len(formatted_files)} files from Google Drive")
            
            return jsonify({
                'status': 'success',
                'files': formatted_files,
                'total': len(formatted_files)
            })
            
        except Exception as e:
            logger.error(f"Error in list_drive_files: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to list files: {str(e)}'
            }), 500

    @app.route('/delete_drive_file', methods=['POST'])
    def delete_drive_file():
        """Delete a file from Google Drive with error handling"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    'status': 'error',
                    'message': 'No data provided'
                }), 400
                
            file_id = data.get('file_id')
            
            if not file_id:
                return jsonify({
                    'status': 'error',
                    'message': 'No file ID provided'
                }), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            
            success = drive_manager.delete_file(file_id)
            
            if success:
                logger.info(f"Successfully deleted file from Google Drive: {file_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'File deleted successfully'
                })
            else:
                logger.error(f"Failed to delete file from Google Drive: {file_id}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to delete file'
                }), 500
                
        except Exception as e:
            logger.error(f"Error in delete_drive_file: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Delete failed: {str(e)}'
            }), 500

    @app.route('/get_drive_stats', methods=['GET'])
    def get_drive_stats():
        """Get statistics about the Google Drive folder with error handling"""
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            stats = drive_manager.get_folder_stats()
            
            logger.info("Successfully retrieved Google Drive stats")
            
            return jsonify({
                'status': 'success',
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error in get_drive_stats: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get stats: {str(e)}'
            }), 500

    @app.route('/search_drive_files', methods=['GET'])
    def search_drive_files():
        """Search for files in Google Drive with error handling"""
        try:
            query = request.args.get('q', '')
            
            if not query:
                return jsonify({
                    'status': 'error',
                    'message': 'No search query provided'
                }), 400
            
            # Sanitize query
            query = query[:100]
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            files = drive_manager.search_files(query)
            
            # Format file data
            formatted_files = []
            for file in files:
                try:
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
                except Exception as e:
                    logger.error(f"Error formatting file {file.get('id', 'unknown')}: {str(e)}")
                    continue
            
            logger.info(f"Search found {len(formatted_files)} files for query: {query}")
            
            return jsonify({
                'status': 'success',
                'files': formatted_files,
                'total': len(formatted_files)
            })
            
        except Exception as e:
            logger.error(f"Error in search_drive_files: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Search failed: {str(e)}'
            }), 500

    @app.route('/get_drive_structure', methods=['GET'])
    def get_drive_structure():
        """Get complete folder structure from Google Drive"""
        try:
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            structure = drive_manager.get_folder_structure()
            
            # Format the data
            formatted_structure = {
                'root': {
                    'id': structure['root']['id'],
                    'name': structure['root']['name'],
                    'file_count': structure['root']['file_count'],
                    'files': []
                },
                'folders': []
            }
            
            # Format root files
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
            
            # Format folders and their files
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
                    'files': formatted_files,
                    'createdTime': folder.get('createdTime', ''),
                    'modifiedTime': folder.get('modifiedTime', '')
                })
            
            logger.info(f"Retrieved folder structure: {len(formatted_structure['folders'])} folders")
            
            return jsonify({
                'status': 'success',
                'structure': formatted_structure
            })
            
        except Exception as e:
            logger.error(f"Error in get_drive_structure: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get folder structure: {str(e)}'
            }), 500

    @app.route('/create_drive_folder', methods=['POST'])
    def create_drive_folder():
        """Create a new subfolder in Google Drive"""
        try:
            data = request.json
            
            if not data or 'folder_name' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'folder_name is required'
                }), 400
            
            folder_name = data['folder_name']
            
            if not folder_name or not folder_name.strip():
                return jsonify({
                    'status': 'error',
                    'message': 'Folder name cannot be empty'
                }), 400
            
            # Sanitize folder name
            folder_name = folder_name.strip()[:100]
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            drive_manager.ensure_folder_exists()
            
            folder_id = drive_manager.get_or_create_subfolder(folder_name)
            
            logger.info(f"Created/accessed folder: {folder_name} (ID: {folder_id})")
            
            return jsonify({
                'status': 'success',
                'message': f'Folder "{folder_name}" ready',
                'folder_id': folder_id,
                'folder_name': folder_name
            })
            
        except Exception as e:
            logger.error(f"Error in create_drive_folder: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to create folder: {str(e)}'
            }), 500

    @app.route('/get_files_metadata', methods=['POST'])
    def get_files_metadata():
        """Get metadata for multiple files by their IDs"""
        try:
            data = request.json
            
            if not data or 'file_ids' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'file_ids is required'
                }), 400
            
            file_ids = data['file_ids']
            
            if not isinstance(file_ids, list):
                return jsonify({
                    'status': 'error',
                    'message': 'file_ids must be a list'
                }), 400
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            
            files = drive_manager.get_multiple_files_metadata(file_ids)
            
            # Format the data
            formatted_files = []
            for file in files:
                formatted_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file.get('mimeType', ''),
                    'size': int(file.get('size', 0)),
                    'sizeFormatted': format_file_size(int(file.get('size', 0))),
                    'webViewLink': file.get('webViewLink', ''),
                    'thumbnailLink': file.get('thumbnailLink', '')
                })
            
            return jsonify({
                'status': 'success',
                'files': formatted_files
            })
            
        except Exception as e:
            logger.error(f"Error in get_files_metadata: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to get files metadata: {str(e)}'
            }), 500

    @app.route('/delete_drive_folder', methods=['POST'])
    def delete_drive_folder():
        """Delete a folder from Google Drive"""
        try:
            data = request.json
            
            if not data or 'folder_id' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'folder_id is required'
                }), 400
            
            folder_id = data['folder_id']
            
            drive_manager = get_drive_manager()
            drive_manager.authenticate()
            
            success = drive_manager.delete_folder(folder_id)
            
            if success:
                logger.info(f"Deleted folder: {folder_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'Folder deleted successfully'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to delete folder'
                }), 500
            
        except Exception as e:
            logger.error(f"Error in delete_drive_folder: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'status': 'error',
                'message': f'Failed to delete folder: {str(e)}'
            }), 500
