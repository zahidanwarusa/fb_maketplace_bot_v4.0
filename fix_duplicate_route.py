#!/usr/bin/env python3
"""
Automatic Fix Script for Duplicate delete_listing Route
This will remove the OLD delete_listing function and keep the NEW one
"""

import os
import sys
from datetime import datetime

def main():
    print("=" * 70)
    print("🔧 FIXING DUPLICATE delete_listing ROUTE")
    print("=" * 70)
    print()
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ ERROR: app.py not found in current directory")
        print("   Please run this script from your project directory")
        return False
    
    # Read app.py
    print("📖 Reading app.py...")
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"   File size: {len(content)} characters")
    print(f"   Total lines: {content.count(chr(10))}")
    print()
    
    # Find all occurrences of delete_listing route
    import re
    pattern = r"@app\.route\('/delete_listing'"
    matches = list(re.finditer(pattern, content))
    
    if len(matches) == 0:
        print("❌ ERROR: No delete_listing route found!")
        return False
    
    if len(matches) == 1:
        print("⚠️  Only ONE delete_listing route found.")
        print("   The duplicate error might be from a different issue.")
        print()
        print("   Checking if function is defined twice without route decorator...")
        
        func_pattern = r"def delete_listing\("
        func_matches = list(re.finditer(func_pattern, content))
        
        if len(func_matches) > 1:
            print(f"   Found {len(func_matches)} function definitions!")
            print("   This might be the issue.")
        else:
            print("   Only one function definition found.")
            print("   Please check your app.py manually.")
        return False
    
    print(f"✅ Found {len(matches)} delete_listing routes!")
    for i, match in enumerate(matches, 1):
        line_num = content[:match.start()].count('\n') + 1
        print(f"   Route {i} at line {line_num}")
    print()
    
    # Create backup
    backup_name = f'app.py.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"💾 Creating backup: {backup_name}")
    with open(backup_name, 'w', encoding='utf-8') as f:
        f.write(content)
    print("   ✅ Backup created")
    print()
    
    # Find the first delete_listing function
    first_pos = matches[0].start()
    first_line = content[:first_pos].count('\n') + 1
    
    print(f"🔍 Analyzing FIRST delete_listing function (line {first_line})...")
    
    # Find the end of the first function
    # Look for the next @app.route or end of functions
    next_route_match = re.search(r'\n@app\.route', content[first_pos + 1:])
    
    if next_route_match:
        next_route_pos = first_pos + 1 + next_route_match.start()
        # The function ends just before the next route
        # Find the last return statement before next route
        function_section = content[first_pos:next_route_pos]
        
        # Find where the function actually ends (before the next blank line + @app.route)
        # Look backwards from next_route_pos for the end of the function
        search_section = content[first_pos:next_route_pos]
        
        # Find last except/finally block or return statement
        last_except = search_section.rfind('except Exception')
        last_return = search_section.rfind('return jsonify')
        
        if last_except > last_return:
            # Function has exception handling
            end_marker = search_section.find('\n\n', last_except)
            if end_marker != -1:
                function_end = first_pos + end_marker
            else:
                function_end = next_route_pos
        else:
            # Find end after last return
            if last_return != -1:
                end_marker = search_section.find('\n\n', last_return)
                if end_marker != -1:
                    function_end = first_pos + end_marker
                else:
                    function_end = next_route_pos
            else:
                function_end = next_route_pos
    else:
        print("   ⚠️  Could not find next route")
        function_end = len(content)
    
    # Extract what we're removing
    removed_section = content[first_pos:function_end].strip()
    removed_lines = removed_section.count('\n') + 1
    
    print(f"   Function spans approximately {removed_lines} lines")
    print(f"   From character position {first_pos} to {function_end}")
    print()
    
    # Check if it's the old version (hard delete) or new version (soft delete)
    if 'deleted_at' in removed_section:
        print("   ⚠️  WARNING: This appears to be the NEW soft-delete version!")
        print("   We should keep this one and remove the other.")
        print()
        response = input("   Do you want to continue? This will remove the WRONG function! (y/N): ")
        if response.lower() != 'y':
            print("   ❌ Cancelled. Please check your app.py manually.")
            return False
    else:
        print("   ✅ This appears to be the OLD hard-delete version (good to remove)")
    
    print()
    print("🗑️  Removing OLD delete_listing function...")
    
    # Remove the first function
    new_content = content[:first_pos] + content[function_end:]
    
    # Write the fixed content
    print("💾 Writing fixed app.py...")
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Fixed app.py")
    print("=" * 70)
    print()
    print("Changes made:")
    print(f"  • Removed FIRST delete_listing function ({removed_lines} lines)")
    print(f"  • Kept SECOND delete_listing function (new soft-delete version)")
    print(f"  • Backup saved as: {backup_name}")
    print()
    print("Next steps:")
    print("  1. Review the changes if needed")
    print("  2. Run: python app.py")
    print("  3. Test the application")
    print()
    print("If something went wrong:")
    print(f"  • Restore backup: cp {backup_name} app.py")
    print()
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ERROR occurred during fixing:")
        print("=" * 70)
        print(f"{type(e).__name__}: {str(e)}")
        print()
        print("Your app.py has NOT been modified.")
        print("Please fix manually or contact support.")
        sys.exit(1)
