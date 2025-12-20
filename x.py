"""
Auto-Fix Script for Max Groups Bug in Bot.py
This script automatically applies the two necessary changes to fix the max_groups setting.

WHAT THIS SCRIPT DOES:
1. Backs up your original Bot.py to Bot.py.backup
2. Fixes the configuration loading to include max_groups and other settings
3. Updates the select_facebook_groups call to use the loaded max_groups value
4. Saves the fixed version

USAGE:
    python fix_max_groups.py

SAFETY:
    - Creates a backup before making changes
    - Shows a diff of what will be changed
    - Asks for confirmation before applying
"""

import os
import shutil
import re
from datetime import datetime


def create_backup(filename):
    """Create a backup of the original file"""
    backup_name = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filename, backup_name)
    print(f"✓ Backup created: {backup_name}")
    return backup_name


def fix_configuration_loading(content):
    """Fix #1: Update configuration loading to include all settings"""
    
    # Find the old configuration loading code
    old_config_pattern = r'''# Load configuration
delays = DEFAULT_DELAYS\.copy\(\)
if os\.path\.exists\('bot_config\.json'\):
    try:
        with open\('bot_config\.json', 'r'\) as f:
            config = json\.load\(f\)
            delays\.update\(config\.get\('delays', \{\}\)\)
            print\("📋 Loaded custom configuration"\)
    except:
        print\("⚠️ Could not load config, using defaults"\)'''
    
    # New configuration loading code
    new_config_code = '''# Load configuration
delays = DEFAULT_DELAYS.copy()
max_groups = 20  # Default value
headless_mode = False
auto_retry = False
max_retries = 2

if os.path.exists('bot_config.json'):
    try:
        with open('bot_config.json', 'r') as f:
            config = json.load(f)
            
            # Load delays
            delays.update(config.get('delays', {}))
            
            # Load other settings
            max_groups = config.get('max_groups', 20)
            headless_mode = config.get('headless', False)
            auto_retry = config.get('auto_retry', False)
            max_retries = config.get('max_retries', 2)
            
            print("📋 Loaded custom configuration")
            print(f"  ⚙️  Max Groups: {max_groups}")
            print(f"  ⚙️  Auto Retry: {auto_retry}")
            print(f"  ⚙️  Max Retries: {max_retries}")
    except Exception as e:
        print(f"⚠️ Could not load config: {e}")
        print("  Using default settings")'''
    
    # Replace the old code with new code
    if re.search(old_config_pattern, content, re.MULTILINE):
        content = re.sub(old_config_pattern, new_config_code, content, flags=re.MULTILINE)
        print("✓ Fix #1 Applied: Configuration loading updated")
        return content, True
    else:
        print("⚠ Fix #1 Warning: Could not find exact configuration loading pattern")
        print("  Attempting alternative pattern...")
        
        # Try a more flexible pattern
        alt_pattern = r'''(# Load configuration\s+delays = DEFAULT_DELAYS\.copy\(\))(.*?)(print\("⚠️ Could not load config, using defaults"\))'''
        if re.search(alt_pattern, content, re.DOTALL):
            # Find and replace more carefully
            lines = content.split('\n')
            new_lines = []
            in_config_section = False
            config_indent = ''
            
            for i, line in enumerate(lines):
                if '# Load configuration' in line and 'delays = DEFAULT_DELAYS' in lines[i+1] if i+1 < len(lines) else False:
                    # Start of config section
                    in_config_section = True
                    new_lines.append(line)
                    new_lines.extend(new_config_code.split('\n')[1:])  # Skip first line as we already added it
                    continue
                    
                if in_config_section:
                    if 'print("⚠️ Could not load config, using defaults")' in line:
                        # End of config section - skip everything until here
                        in_config_section = False
                    continue
                    
                new_lines.append(line)
            
            content = '\n'.join(new_lines)
            print("✓ Fix #1 Applied: Configuration loading updated (using alternative method)")
            return content, True
        else:
            return content, False


def fix_select_facebook_groups_call(content):
    """Fix #2: Update select_facebook_groups call to use variable instead of hardcoded 20"""
    
    # Find the hardcoded max_groups=20
    old_pattern = r'select_facebook_groups\(driver,\s*max_groups=20,'
    new_code = 'select_facebook_groups(driver, max_groups=max_groups,'
    
    if re.search(old_pattern, content):
        content = re.sub(old_pattern, new_code, content)
        print("✓ Fix #2 Applied: select_facebook_groups call updated to use loaded max_groups")
        return content, True
    else:
        print("⚠ Fix #2 Warning: Could not find select_facebook_groups with max_groups=20")
        return content, False


def show_diff_preview(old_content, new_content):
    """Show a preview of what will change"""
    print("\n" + "="*70)
    print("PREVIEW OF CHANGES")
    print("="*70)
    
    old_lines = old_content.split('\n')
    new_lines = new_content.split('\n')
    
    # Find first difference
    for i, (old, new) in enumerate(zip(old_lines, new_lines)):
        if old != new:
            print(f"\nFirst change found around line {i+1}:")
            print("\nOLD CODE (will be removed):")
            print("-" * 70)
            for j in range(max(0, i-2), min(len(old_lines), i+8)):
                prefix = ">>> " if j == i else "    "
                print(f"{prefix}{old_lines[j]}")
            
            print("\nNEW CODE (will be added):")
            print("-" * 70)
            for j in range(max(0, i-2), min(len(new_lines), i+15)):
                prefix = ">>> " if j >= i and j < i + 7 else "    "
                print(f"{prefix}{new_lines[j]}")
            break
    
    print("\n" + "="*70)


def main():
    """Main execution function"""
    bot_file = 'Bot.py'
    
    print("\n" + "="*70)
    print("MAX GROUPS FIX - AUTOMATIC PATCHER")
    print("="*70)
    
    # Check if Bot.py exists
    if not os.path.exists(bot_file):
        print(f"\n❌ ERROR: {bot_file} not found in current directory")
        print(f"   Current directory: {os.getcwd()}")
        print(f"\n   Please run this script from your project root directory")
        print(f"   (the same directory where Bot.py is located)")
        return
    
    print(f"\n✓ Found {bot_file}")
    
    # Read the original file
    with open(bot_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    print(f"✓ File size: {len(original_content)} characters, {len(original_content.splitlines())} lines")
    
    # Create backup
    backup_file = create_backup(bot_file)
    
    # Apply fixes
    print("\nApplying fixes...")
    print("-" * 70)
    
    modified_content = original_content
    
    # Fix #1: Configuration loading
    modified_content, fix1_applied = fix_configuration_loading(modified_content)
    
    # Fix #2: select_facebook_groups call
    modified_content, fix2_applied = fix_select_facebook_groups_call(modified_content)
    
    print("-" * 70)
    
    # Check if any changes were made
    if modified_content == original_content:
        print("\n⚠️  WARNING: No changes were made!")
        print("   This could mean:")
        print("   1. The fixes were already applied")
        print("   2. The code structure is different than expected")
        print("\n   You may need to apply the fixes manually.")
        return
    
    # Show preview
    show_diff_preview(original_content, modified_content)
    
    # Confirm before saving
    print("\n" + "="*70)
    response = input("\nApply these changes to Bot.py? (yes/no): ").strip().lower()
    
    if response == 'yes':
        # Save the modified file
        with open(bot_file, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        print(f"\n✅ SUCCESS! Changes applied to {bot_file}")
        print(f"✓ Backup saved as: {backup_file}")
        print("\nNEXT STEPS:")
        print("1. Restart your Flask application")
        print("2. Open Bot Settings in the dashboard")
        print("3. Set 'Max Groups to Select' to test value (e.g., 5)")
        print("4. Save settings and run the bot")
        print("5. Check logs for: '⚙️  Max Groups: 5'")
        
    else:
        print("\n❌ Changes cancelled. Original file unchanged.")
        print(f"   Backup can be deleted: {backup_file}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. No changes made.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()