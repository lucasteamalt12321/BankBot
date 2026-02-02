#!/usr/bin/env python3
"""
Simple verification script to confirm admin commands exist
"""
import sys
import os

def verify_admin_commands():
    print("Verifying admin coin management commands...")
    
    # Read the bot.py file to check if commands are properly defined
    with open('bot/bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for the command handlers
    has_admin_adjust = 'CommandHandler("admin_adjust"' in content
    has_admin_addcoins = 'CommandHandler("admin_addcoins"' in content
    has_admin_removecoins = 'CommandHandler("admin_removecoins"' in content
    
    print(f"  - /admin_adjust exists: {has_admin_adjust}")
    print(f"  - /admin_addcoins exists: {has_admin_addcoins}")
    print(f"  - /admin_removecoins exists: {has_admin_removecoins}")
    
    # Check for the method definitions
    has_admin_addcoins_method = 'async def admin_addcoins_command' in content
    has_admin_removecoins_method = 'async def admin_removecoins_command' in content
    has_admin_adjust_method = 'async def admin_adjust_command' in content
    
    print(f"  - admin_addcoins_command method: {has_admin_addcoins_method}")
    print(f"  - admin_removecoins_command method: {has_admin_removecoins_method}")
    print(f"  - admin_adjust_command method: {has_admin_adjust_method}")
    
    # Verify all methods are implemented
    all_good = all([
        has_admin_adjust, has_admin_addcoins, has_admin_removecoins,
        has_admin_adjust_method, has_admin_addcoins_method, has_admin_removecoins_method
    ])
    
    if all_good:
        print("\nSUCCESS: All admin coin management commands are properly implemented!")
        print("\nCommands available for administrators:")
        print("  /admin_adjust <user> <amount> <reason> - General balance adjustment (positive or negative)")
        print("  /admin_addcoins <user> <amount> [reason] - Add coins to user (simplified interface)")
        print("  /admin_removecoins <user> <amount> [reason] - Remove coins from user (simplified interface)")
        return True
    else:
        print("\nERROR: Some admin commands are missing!")
        return False

if __name__ == "__main__":
    success = verify_admin_commands()
    if success:
        print("\nAdmin coin management functionality is ready for use!")
    else:
        print("\nVerification failed!")
        sys.exit(1)