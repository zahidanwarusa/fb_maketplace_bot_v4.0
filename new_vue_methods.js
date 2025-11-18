// ============================================================================
// CORRECTED VUE METHODS FOR MULTI-IMAGE & FOLDER SUPPORT
// Add these methods to your Vue instance in index.html
// ============================================================================

// STEP 1: Add these properties to your data() section:
/*
data: {
    // ... existing properties ...
    
    // ADD THESE NEW PROPERTIES:
    driveStructure: {
        root: { id: '', name: '', file_count: 0, files: [] },
        folders: []
    },
    showFolderContent: {},
    imagePickerMode: 'single',
    selectedImages: [],
    currentFolder: '',
    imagePreviews: []
}
*/

// STEP 2: Add/Update these methods in your methods section:

const newVueMethods = {
    
    // ========================================================================
    // FOLDER MANAGEMENT METHODS
    // ========================================================================
    
    loadDriveStructure() {
        console.log('Loading Google Drive folder structure...');
        this.loadingMedia = true;
        axios.get('/get_drive_structure')
            .then(response => {
                if (response.data.status === 'success') {
                    this.driveStructure = response.data.structure;
                    console.log(`Loaded structure: ${this.driveStructure.folders.length} folders`);
                    // Initialize showFolderContent for each folder
                    this.driveStructure.folders.forEach(folder => {
                        this.$set(this.showFolderContent, folder.id, false);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading structure:', error);
                this.showToast('error', 'Failed to load folder structure');
            })
            .finally(() => {
                this.loadingMedia = false;
            });
    },
    
    toggleFolder(folderId) {
        this.$set(this.showFolderContent, folderId, !this.showFolderContent[folderId]);
    },
    
    async createFolderPrompt() {
        const folderName = prompt('Enter folder name (e.g., 2024-Honda-Civic):');
        if (!folderName || !folderName.trim()) {
            return;
        }
        
        try {
            const response = await axios.post('/create_drive_folder', {
                folder_name: folderName.trim()
            });
            
            if (response.data.status === 'success') {
                this.showToast('success', `Folder "${folderName}" created!`);
                this.loadDriveStructure();
            }
        } catch (error) {
            console.error('Error creating folder:', error);
            this.showDialog('error', 'Error', 
                error.response?.data?.message || 'Failed to create folder');
        }
    },
    
    async deleteFolder(folder) {
        const confirmed = await this.showDialog('confirm', 'Delete Folder?', 
            `Delete "${folder.name}" and all its files?`, 'Delete');
        if (!confirmed) return;
        
        try {
            const response = await axios.post('/delete_drive_folder', {
                folder_id: folder.id
            });
            
            if (response.data.status === 'success') {
                this.showToast('success', 'Folder deleted');
                this.loadDriveStructure();
            }
        } catch (error) {
            console.error('Error:', error);
            this.showToast('error', 'Failed to delete folder');
        }
    },
    
    // ========================================================================
    // MULTI-IMAGE SELECTION METHODS
    // ========================================================================
    
    openMediaPickerMulti(mode) {
        this.imagePickerMode = 'multi';
        this.pickerMode = mode;
        this.selectedImages = [];
        this.showMediaPicker = true;
        if (this.driveStructure.folders.length === 0) {
            this.loadDriveStructure();
        }
    },
    
    toggleImageSelection(file) {
        const index = this.selectedImages.findIndex(f => f.id === file.id);
        if (index > -1) {
            this.selectedImages.splice(index, 1);
        } else {
            this.selectedImages.push(file);
        }
    },
    
    isImageSelected(file) {
        return this.selectedImages.some(f => f.id === file.id);
    },
    
    confirmMultiImageSelection() {
        if (this.selectedImages.length === 0) {
            this.showToast('warning', 'Please select at least one image');
            return;
        }
        
        const imageIds = this.selectedImages.map(f => f.id);
        
        if (this.pickerMode === 'new') {
            if (!this.newListing.image_ids) {
                this.newListing.image_ids = [];
            }
            this.newListing.image_ids = imageIds;
            this.showToast('success', `Selected ${imageIds.length} image(s)`);
        } else if (this.pickerMode === 'edit') {
            if (!this.editForm.image_ids) {
                this.editForm.image_ids = [];
            }
            this.editForm.image_ids = imageIds;
            this.showToast('success', `Selected ${imageIds.length} image(s)`);
        }
        
        this.closeMediaPicker();
    },
    
    removeImageFromListing(index, mode) {
        if (mode === 'new') {
            if (!this.newListing.image_ids) {
                this.newListing.image_ids = [];
            }
            this.newListing.image_ids.splice(index, 1);
        } else if (mode === 'edit') {
            if (!this.editForm.image_ids) {
                this.editForm.image_ids = [];
            }
            this.editForm.image_ids.splice(index, 1);
        }
    },
    
    async getImagePreviews(imageIds) {
        if (!imageIds || imageIds.length === 0) return [];
        
        try {
            const response = await axios.post('/get_files_metadata', {
                file_ids: imageIds
            });
            
            if (response.data.status === 'success') {
                return response.data.files;
            }
        } catch (error) {
            console.error('Error getting previews:', error);
        }
        return [];
    },
    
    // ========================================================================
    // FILE UPLOAD TO SPECIFIC FOLDER
    // ========================================================================
    
    openFileUploadToFolder(folderName) {
        this.currentFolder = folderName;
        this.openFileUpload('standalone');
    },
    
    // REPLACE your existing uploadFiles() method with this enhanced version:
    uploadFiles() {
        if (this.selectedFiles.length === 0) {
            this.showToast('warning', 'No files selected');
            return;
        }
        
        this.uploading = true;
        this.uploadProgress = 0;
        
        const totalFiles = this.selectedFiles.length;
        let uploadedCount = 0;
        let lastUploadedFile = null;
        
        const uploadNext = (index) => {
            if (index >= this.selectedFiles.length) {
                this.uploading = false;
                this.uploadProgress = 100;
                
                this.showDialog('success', 'Upload Complete', 
                    `Successfully uploaded ${uploadedCount} of ${totalFiles} file(s)!`);
                
                // If uploading from picker or new/edit listing, set the last uploaded file
                if (lastUploadedFile && (this.pickerMode === 'new' || this.pickerMode === 'edit' || this.pickerMode === 'picker')) {
                    const filePath = lastUploadedFile.webViewLink || `https://drive.google.com/uc?id=${lastUploadedFile.id}`;
                    
                    if (this.pickerMode === 'new') {
                        this.newListing['Images Path'] = filePath;
                        this.showToast('success', 'Path set to uploaded file!');
                    } else if (this.pickerMode === 'edit') {
                        this.editForm['Images Path'] = filePath;
                        this.showToast('success', 'Path set to uploaded file!');
                    } else if (this.pickerMode === 'picker') {
                        this.pickerSelected = lastUploadedFile;
                        this.confirmMediaSelection();
                    }
                }
                
                this.closeUploadModal();
                this.loadDriveStructure();  // Changed from loadDriveFiles()
                return;
            }
            
            const file = this.selectedFiles[index];
            const formData = new FormData();
            formData.append('file', file);
            
            // Add folder name if specified
            if (this.currentFolder) {
                formData.append('folder_name', this.currentFolder);
            }
            
            console.log(`Uploading file ${index + 1}/${totalFiles}: ${file.name}${this.currentFolder ? ' to folder: ' + this.currentFolder : ''}`);
            
            // Choose endpoint based on whether folder is specified
            const endpoint = this.currentFolder ? '/upload_to_drive_folder' : '/upload_to_drive';
            
            axios.post(endpoint, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 120000
            })
            .then(response => {
                console.log('Upload response:', response.data);
                if (response.data.status === 'success') {
                    uploadedCount++;
                    lastUploadedFile = response.data.file;
                    this.uploadProgress = Math.round(((index + 1) / totalFiles) * 100);
                    this.showToast('success', `Uploaded: ${file.name}`);
                    uploadNext(index + 1);
                } else {
                    console.error('Upload failed:', response.data);
                    this.showToast('error', `Failed: ${file.name} - ${response.data.message}`);
                    uploadNext(index + 1);
                }
            })
            .catch(error => {
                console.error('Upload error:', error);
                const errorMsg = error.response?.data?.message || error.message || 'Unknown error';
                this.showToast('error', `Failed: ${file.name} - ${errorMsg}`);
                uploadNext(index + 1);
            });
        };
        
        uploadNext(0);
    },
    
    // ========================================================================
    // HELPER METHODS
    // ========================================================================
    
    getFolderFileCount(folder) {
        return folder.file_count || 0;
    },
    
    getImageThumbnail(file) {
        return file.thumbnailLink || file.webViewLink || '';
    },
    
    selectImageFolder(folderName) {
        if (this.pickerMode === 'new') {
            if (!this.newListing.image_folder) {
                this.newListing.image_folder = '';
            }
            this.newListing.image_folder = folderName;
        } else if (this.pickerMode === 'edit') {
            if (!this.editForm.image_folder) {
                this.editForm.image_folder = '';
            }
            this.editForm.image_folder = folderName;
        }
    },
    
    // ========================================================================
    // UPDATE EXISTING METHODS
    // ========================================================================
    
    // UPDATE your existing openMediaPicker to support multi-select:
    openMediaPicker(mode) {
        this.pickerMode = mode;
        this.imagePickerMode = 'single';  // Default to single
        this.pickerSelected = null;
        this.selectedImages = [];
        this.showMediaPicker = true;
        if (this.driveStructure.folders.length === 0) {
            this.loadDriveStructure();
        }
    },
    
    // UPDATE your existing editListing to handle image_ids:
    editListing(index) {
        this.editingListing = index;
        this.editForm = JSON.parse(JSON.stringify(this.listings[index]));
        // Ensure image_ids is an array
        if (!this.editForm.image_ids) {
            this.editForm.image_ids = [];
        }
        if (!this.editForm.image_folder) {
            this.editForm.image_folder = '';
        }
    },
    
    // UPDATE your existing resetForm to include new fields:
    resetForm() {
        this.newListing = {
            Year: '', Make: '', Model: '', Mileage: '', Price: '',
            'Body Style': '', 'Exterior Color': '', 'Interior Color': '',
            'Vehicle Condition': '', 'Fuel Type': '', Transmission: '',
            Description: '', 'Images Path': '', selectedDay: '',
            image_ids: [],        // ADD THIS
            image_folder: ''      // ADD THIS
        };
        this.showToast('info', 'Form reset');
    },
    
    // UPDATE your existing closeMediaPicker to clear current folder:
    closeMediaPicker() {
        this.showMediaPicker = false;
        this.pickerSelected = null;
        this.selectedImages = [];
        this.imagePickerMode = 'single';
        this.currentFolder = '';
        this.mediaSearch = '';
    },
    
    // UPDATE your existing closeUploadModal to clear current folder:
    closeUploadModal() {
        if (!this.uploading) {
            this.showUploadModal = false;
            this.selectedFiles = [];
            this.uploadProgress = 0;
            this.currentFolder = '';
        }
    }
};

// ============================================================================
// INTEGRATION INSTRUCTIONS
// ============================================================================

/*

STEP-BY-STEP INTEGRATION:

1. UPDATE DATA SECTION in your Vue instance:
   Add these properties to your data() object:
   
   driveStructure: {
       root: { id: '', name: '', file_count: 0, files: [] },
       folders: []
   },
   showFolderContent: {},
   imagePickerMode: 'single',
   selectedImages: [],
   currentFolder: '',
   imagePreviews: []

2. UPDATE METHODS SECTION:
   - REPLACE uploadFiles() with the new version above
   - REPLACE openMediaPicker() with the new version above
   - REPLACE editListing() with the new version above
   - REPLACE resetForm() with the new version above
   - REPLACE closeMediaPicker() with the new version above
   - REPLACE closeUploadModal() with the new version above
   - ADD all the new methods (loadDriveStructure, toggleFolder, etc.)

3. UPDATE newListing INITIALIZATION:
   Make sure your newListing in data() includes:
   
   newListing: {
       Year: '', Make: '', Model: '', Mileage: '', Price: '',
       'Body Style': '', 'Exterior Color': '', 'Interior Color': '',
       'Vehicle Condition': '', 'Fuel Type': '', Transmission: '',
       Description: '', 'Images Path': '', selectedDay: '',
       image_ids: [],        // NEW
       image_folder: ''      // NEW
   }

4. UPDATE THE MEDIA TAB HTML (see below for complete HTML update)

*/

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = newVueMethods;
}