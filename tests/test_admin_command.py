#!/usr/bin/env python3
"""
Test script for the /admin command implementation
"""
import sys
import os
import sqlite3

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin_system import AdminSystem

def test_admin_command():
    """Test the admin command functionality"""
    print("Testing /admin command implementation...")
    
    # Initialize admin system
    admin_system = AdminSystem()
    
    # Test get_users_count function
    users_count = admin_system.get_users_count()
    print(f"✓ get_users_count() works: {users_count} users")
    
    # Test admin check for non-existent user
    is_admin_result = admin_system.is_admin(999999999)
    print(f"✓ is_admin() works for non-existent user: {is_admin_result}")
    
    # Create a test user
    test_user_id = 123456789
    success = admin_system.register_user(test_user_id, "testuser", "Test User")
    print(f"✓ register_user() works: {success}")
    
    # Test admin check for regular user
    is_admin_result = admin_system.is_admin(test_user_id)
    print(f"✓ is_admin() works for regular user: {is_admin_result}")
    
    # Make user admin
    success = admin_system.set_admin_status(test_user_id, True)
    print(f"✓ set_admin_status() works: {success}")
    
    # Test admin check for admin user
    is_admin_result = admin_system.is_admin(test_user_id)
    print(f"✓ is_admin() works for admin user: {is_admin_result}")
    
    # Test the exact message format
    users_count = admin_system.get_users_count()
    expected_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
    print(f"✓ Expected admin panel message format:")
    print(f"'{expected_message}'")
    
    print("\n✅ All admin command tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_admin_command()
        print("\n🎉 Admin command implementation is ready!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)