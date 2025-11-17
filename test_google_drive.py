#!/usr/bin/env python3
"""
Google Drive Upload Test Script
Run this to diagnose any Google Drive integration issues
"""

import os
import sys

def test_files_exist():
    """Check if required files exist"""
    print("\n" + "="*60)
    print("1. Checking Required Files")
    print("="*60)
    
    files_to_check = {
        'credentials.json': 'Google Cloud credentials',
        'google_drive_manager.py': 'Drive manager module',
        'app.py': 'Flask application'
    }
    
    all_good = True
    for filename, description in files_to_check.items():
        exists = os.path.exists(filename)
        status = "✅" if exists else "❌"
        print(f"{status} {filename:25} - {description}")
        if not exists:
            all_good = False
    
    if os.path.exists('token.pickle'):
        print("✅ token.pickle           - Authentication token (exists)")
    else:
        print("ℹ️  token.pickle           - Will be created on first run")
    
    return all_good


def test_drive_import():
    """Test if we can import the drive manager"""
    print("\n" + "="*60)
    print("2. Testing Module Import")
    print("="*60)
    
    try:
        from google_drive_manager import get_drive_manager
        print("✅ Successfully imported google_drive_manager")
        return True
    except ImportError as e:
        print(f"❌ Failed to import: {str(e)}")
        print("\nMissing dependencies? Run:")
        print("   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return False


def test_drive_authentication():
    """Test Google Drive authentication"""
    print("\n" + "="*60)
    print("3. Testing Google Drive Authentication")
    print("="*60)
    
    try:
        from google_drive_manager import get_drive_manager
        
        drive_manager = get_drive_manager()
        print("ℹ️  Authenticating... (browser may open)")
        
        drive_manager.authenticate()
        print("✅ Authentication successful!")
        return True, drive_manager
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


def test_folder_creation(drive_manager):
    """Test creating/accessing the fbBotMedia folder"""
    print("\n" + "="*60)
    print("4. Testing Folder Creation")
    print("="*60)
    
    try:
        folder_id = drive_manager.ensure_folder_exists()
        print(f"✅ Folder exists/created! ID: {folder_id}")
        return True
    except Exception as e:
        print(f"❌ Folder creation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_file_listing(drive_manager):
    """Test listing files from Google Drive"""
    print("\n" + "="*60)
    print("5. Testing File Listing")
    print("="*60)
    
    try:
        files = drive_manager.list_files()
        print(f"✅ Successfully listed files!")
        print(f"   Found {len(files)} file(s) in Google Drive")
        
        if files:
            print("\n   Recent files:")
            for i, file in enumerate(files[:5], 1):
                size = file.get('size', 0)
                size_mb = int(size) / (1024 * 1024) if size else 0
                print(f"   {i}. {file['name']} ({size_mb:.2f} MB)")
        
        return True
    except Exception as e:
        print(f"❌ File listing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_upload_folder():
    """Test if upload folder exists and is writable"""
    print("\n" + "="*60)
    print("6. Testing Upload Folder")
    print("="*60)
    
    upload_folder = 'temp_uploads'
    
    try:
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            print(f"✅ Created {upload_folder} folder")
        else:
            print(f"✅ {upload_folder} folder exists")
        
        # Test write permission
        test_file = os.path.join(upload_folder, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"✅ {upload_folder} folder is writable")
        
        return True
    except Exception as e:
        print(f"❌ Upload folder test failed: {str(e)}")
        return False


def test_file_upload(drive_manager):
    """Test uploading a small file"""
    print("\n" + "="*60)
    print("7. Testing File Upload")
    print("="*60)
    
    try:
        # Create a small test file
        test_file_path = 'test_upload_file.txt'
        with open(test_file_path, 'w') as f:
            f.write('This is a test file from the diagnostic script.\n')
            f.write('If you see this in Google Drive, the upload is working!\n')
        
        print(f"ℹ️  Created test file: {test_file_path}")
        print(f"ℹ️  Uploading to Google Drive...")
        
        result = drive_manager.upload_file(file_path=test_file_path)
        
        print(f"✅ File uploaded successfully!")
        print(f"   File ID: {result['id']}")
        print(f"   File Name: {result['name']}")
        print(f"   View at: {result.get('webViewLink', 'N/A')}")
        
        # Clean up test file
        os.remove(test_file_path)
        print(f"ℹ️  Cleaned up test file")
        
        return True
    except Exception as e:
        print(f"❌ File upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to clean up
        try:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
        except:
            pass
        
        return False


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "GOOGLE DRIVE DIAGNOSTIC TOOL" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    
    results = []
    
    # Test 1: Files exist
    results.append(("Files Check", test_files_exist()))
    
    if not results[-1][1]:
        print("\n⚠️  Missing required files! Please fix before continuing.")
        return
    
    # Test 2: Import
    results.append(("Module Import", test_drive_import()))
    
    if not results[-1][1]:
        print("\n⚠️  Cannot import modules! Install dependencies first.")
        return
    
    # Test 3: Authentication
    auth_result, drive_manager = test_drive_authentication()
    results.append(("Authentication", auth_result))
    
    if not auth_result:
        print("\n⚠️  Authentication failed! Check credentials.json")
        return
    
    # Test 4: Folder creation
    results.append(("Folder Creation", test_folder_creation(drive_manager)))
    
    # Test 5: File listing
    results.append(("File Listing", test_file_listing(drive_manager)))
    
    # Test 6: Upload folder
    results.append(("Upload Folder", test_upload_folder()))
    
    # Test 7: File upload
    results.append(("File Upload", test_file_upload(drive_manager)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Google Drive is working correctly!")
        print("\nYou can now use the upload feature in your application.")
    else:
        print("⚠️  SOME TESTS FAILED!")
        print("\nPlease fix the issues above before using Google Drive upload.")
        print("\nFor help, see: GOOGLE_DRIVE_TROUBLESHOOTING.md")
    print("="*60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)