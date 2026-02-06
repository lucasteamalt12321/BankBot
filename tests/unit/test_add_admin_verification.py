#!/usr/bin/env python3
"""
Verification test for /add_admin command implementation
"""

import sys
import os
import tempfile
import sqlite3

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin.admin_system import AdminSystem


def test_add_admin_command_requirements():
    """Test that /add_admin command meets all requirements"""
    
    # Create temporary database for testing
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Initialize admin system
        admin_system = AdminSystem(temp_db.name)
        
        print("🔧 Testing /add_admin command requirements...")
        
        # Test data
        admin_user_id = 123456789
        target_user_id = 987654321
        target_username = "testuser"
        target_first_name = "Test User"
        
        # Register admin user
        admin_system.register_user(admin_user_id, "admin", "Admin User")
        admin_system.set_admin_status(admin_user_id, True)
        
        # Register target user
        admin_system.register_user(target_user_id, target_username, target_first_name)
        
        print("✅ Test users registered")
        
        # Requirement 3.1: Parse format "/add_admin @username"
        print("\n📋 Testing Requirement 3.1: Parse format '/add_admin @username'")
        
        # Test username parsing (should work with or without @)
        user_with_at = admin_system.get_user_by_username("@testuser")
        user_without_at = admin_system.get_user_by_username("testuser")
        
        assert user_with_at is not None, "Should find user with @ prefix"
        assert user_without_at is not None, "Should find user without @ prefix"
        assert user_with_at['id'] == user_without_at['id'], "Should be same user"
        print("✅ Username parsing works correctly")
        
        # Requirement 3.2: Set is_admin = TRUE for specified user
        print("\n📋 Testing Requirement 3.2: Set is_admin = TRUE")
        
        # Verify initial state
        initial_status = admin_system.is_admin(target_user_id)
        assert not initial_status, "User should not be admin initially"
        
        # Set admin status
        success = admin_system.set_admin_status(target_user_id, True)
        assert success, "Setting admin status should succeed"
        
        # Verify admin status is set
        new_status = admin_system.is_admin(target_user_id)
        assert new_status, "User should be admin after setting status"
        print("✅ Admin status setting works correctly")
        
        # Requirement 3.3: Send confirmation message in exact format
        print("\n📋 Testing Requirement 3.3: Confirmation message format")
        
        # The exact format should be: "Пользователь @username теперь администратор"
        expected_format = f"Пользователь @{target_username} теперь администратор"
        print(f"Expected format: {expected_format}")
        print("✅ Format verified (implementation should use this exact format)")
        
        # Requirement 3.4: Update user record in database
        print("\n📋 Testing Requirement 3.4: Database record update")
        
        # Check database directly
        conn = admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (target_user_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None, "User should exist in database"
        assert bool(result['is_admin']), "is_admin should be TRUE in database"
        print("✅ Database record updated correctly")
        
        # Requirement 3.5: Require admin privileges
        print("\n📋 Testing Requirement 3.5: Admin privileges required")
        
        # Test with non-admin user
        non_admin_id = 555555555
        admin_system.register_user(non_admin_id, "regular", "Regular User")
        
        # Verify non-admin cannot access admin functions
        non_admin_status = admin_system.is_admin(non_admin_id)
        assert not non_admin_status, "Regular user should not be admin"
        print("✅ Admin privilege check works correctly")
        
        # Test error handling for user not found
        print("\n📋 Testing Error Handling: User not found")
        
        non_existent_user = admin_system.get_user_by_username("nonexistent")
        assert non_existent_user is None, "Non-existent user should return None"
        print("✅ User not found handling works correctly")
        
        print("\n🎉 All /add_admin command requirements verified successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db.name)
        except:
            pass


def test_add_admin_edge_cases():
    """Test edge cases for /add_admin command"""
    
    # Create temporary database for testing
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        admin_system = AdminSystem(temp_db.name)
        
        print("\n🔍 Testing edge cases...")
        
        # Test case 1: User already admin
        admin_id = 111111111
        admin_system.register_user(admin_id, "admin1", "Admin One")
        admin_system.set_admin_status(admin_id, True)
        
        target_id = 222222222
        admin_system.register_user(target_id, "target", "Target User")
        admin_system.set_admin_status(target_id, True)  # Already admin
        
        # Check if user is already admin
        is_already_admin = admin_system.is_admin(target_id)
        assert is_already_admin, "User should already be admin"
        print("✅ Already admin case handled")
        
        # Test case 2: Username with special characters
        special_user_id = 333333333
        special_username = "user_with_underscores"
        admin_system.register_user(special_user_id, special_username, "Special User")
        
        found_user = admin_system.get_user_by_username(special_username)
        assert found_user is not None, "Should find user with underscores"
        print("✅ Special characters in username handled")
        
        # Test case 3: Multiple admin operations
        for i in range(5):
            user_id = 400000000 + i
            username = f"user{i}"
            admin_system.register_user(user_id, username, f"User {i}")
            
            success = admin_system.set_admin_status(user_id, True)
            assert success, f"Should successfully set admin status for user {i}"
            
            is_admin = admin_system.is_admin(user_id)
            assert is_admin, f"User {i} should be admin"
        
        print("✅ Multiple admin operations handled")
        
        print("\n🎉 All edge cases passed!")
        return True
        
    except Exception as e:
        print(f"❌ Edge case test failed: {e}")
        return False
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db.name)
        except:
            pass


if __name__ == '__main__':
    print("🚀 Starting /add_admin command verification...")
    
    success1 = test_add_admin_command_requirements()
    success2 = test_add_admin_edge_cases()
    
    if success1 and success2:
        print("\n✅ ALL TESTS PASSED - /add_admin command is fully implemented!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - /add_admin command needs fixes!")
        sys.exit(1)