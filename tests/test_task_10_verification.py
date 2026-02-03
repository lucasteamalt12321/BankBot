#!/usr/bin/env python3
"""
Verification script for Task 10 - Complex Property Tests
Tests both error handling consistency and database integrity
"""

import sys
import os
import tempfile
import sqlite3
import logging

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the test systems
from tests.test_error_handling_consistency_pbt import SimpleAdminSystem, ErrorHandlingSimulator
from tests.test_database_integrity_pbt import DatabaseIntegritySystem

def test_error_handling_consistency():
    """Test Property 8: Error handling consistency"""
    print("🧪 Testing Property 8: Error handling consistency...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Initialize admin system
        admin_system = SimpleAdminSystem(temp_db.name)
        error_simulator = ErrorHandlingSimulator(admin_system)
        
        # Create test users
        admin_user_id = 999999999
        regular_user_id = 888888888
        
        admin_system.register_user(admin_user_id, "testadmin", "Test Admin")
        admin_system.set_admin_status(admin_user_id, True)
        admin_system.register_user(regular_user_id, "testuser", "Test User")
        admin_system.update_balance(regular_user_id, 100.0)
        
        # Test cases for error handling consistency
        test_cases = [
            # (description, test_function, expected_result)
            ("Non-admin user tries to add points", 
             lambda: error_simulator.simulate_add_points_command(regular_user_id, "testuser", 100),
             False),
            ("Admin adds points with invalid amount", 
             lambda: error_simulator.simulate_add_points_command(admin_user_id, "testuser", "invalid"),
             False),
            ("Admin adds points to non-existent user", 
             lambda: error_simulator.simulate_add_points_command(admin_user_id, "nonexistent", 100),
             False),
            ("Non-admin user tries to add admin", 
             lambda: error_simulator.simulate_add_admin_command(regular_user_id, "testuser"),
             False),
            ("Admin adds admin for non-existent user", 
             lambda: error_simulator.simulate_add_admin_command(admin_user_id, "nonexistent"),
             False),
            ("User with insufficient balance tries to buy", 
             lambda: error_simulator.simulate_buy_contact_command(regular_user_id),
             True),  # Should succeed as user has 100 points
            ("Non-existent user tries to buy", 
             lambda: error_simulator.simulate_buy_contact_command(999999),
             False),
        ]
        
        passed = 0
        failed = 0
        
        for description, test_func, expected_success in test_cases:
            try:
                success, message = test_func()
                
                # Check that we get a proper response
                if not isinstance(message, str) or len(message) == 0:
                    print(f"  ❌ {description}: Invalid message format")
                    failed += 1
                    continue
                
                # Check expected success/failure
                if success == expected_success:
                    print(f"  ✅ {description}: {message[:50]}...")
                    passed += 1
                else:
                    print(f"  ❌ {description}: Expected {'success' if expected_success else 'failure'}, got {'success' if success else 'failure'}")
                    failed += 1
                    
            except Exception as e:
                print(f"  ❌ {description}: Exception occurred: {e}")
                failed += 1
        
        print(f"  📊 Error handling tests: {passed} passed, {failed} failed")
        return failed == 0
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db.name)
        except:
            pass

def test_database_integrity():
    """Test Property 9: Database integrity preservation"""
    print("🧪 Testing Property 9: Database integrity preservation...")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Initialize database system
        db_system = DatabaseIntegritySystem(temp_db.name)
        
        # Create test users
        test_users = [
            {'id': 1001, 'username': 'testuser1', 'first_name': 'Test User 1'},
            {'id': 1002, 'username': 'testuser2', 'first_name': 'Test User 2'},
            {'id': 1003, 'username': 'admin1', 'first_name': 'Admin User 1'},
        ]
        
        for user in test_users:
            db_system.register_user(user['id'], user['username'], user['first_name'])
        
        # Make one user an admin
        db_system.set_admin_status(1003, True)
        
        # Test operations that should maintain integrity
        operations = [
            ("Register duplicate user", lambda: db_system.register_user(1001, "testuser1", "Test User 1")),
            ("Update balance for existing user", lambda: db_system.update_balance(1001, 25.0)),
            ("Add transaction for existing user", lambda: db_system.add_transaction(1001, 10.0, 'add', 1003)),
            ("Set admin status", lambda: db_system.set_admin_status(1002, True)),
            ("Add transaction with null admin", lambda: db_system.add_transaction(1002, 5.0, 'buy', None)),
        ]
        
        passed = 0
        failed = 0
        
        for description, operation in operations:
            try:
                result = operation()
                
                # Check integrity after each operation
                violations = db_system.check_foreign_key_integrity()
                
                if len(violations) == 0:
                    print(f"  ✅ {description}: No integrity violations")
                    passed += 1
                else:
                    print(f"  ❌ {description}: Integrity violations found: {violations}")
                    failed += 1
                    
            except Exception as e:
                print(f"  ❌ {description}: Exception occurred: {e}")
                failed += 1
        
        # Test that deletion with dependent records fails
        try:
            # Add a transaction for user 1001
            db_system.add_transaction(1001, 15.0, 'add', 1003)
            
            # Try to delete user 1001 (should fail due to foreign key constraint)
            deletion_result = db_system.delete_user(1001)
            
            if not deletion_result:
                print("  ✅ User deletion correctly prevented when transactions exist")
                passed += 1
            else:
                print("  ❌ User deletion should have failed but succeeded")
                failed += 1
                
            # Verify no integrity violations after failed deletion
            violations = db_system.check_foreign_key_integrity()
            if len(violations) == 0:
                print("  ✅ No integrity violations after failed deletion")
                passed += 1
            else:
                print(f"  ❌ Integrity violations after failed deletion: {violations}")
                failed += 1
                
        except Exception as e:
            print(f"  ❌ Deletion test failed with exception: {e}")
            failed += 1
        
        print(f"  📊 Database integrity tests: {passed} passed, {failed} failed")
        return failed == 0
        
    finally:
        # Clean up
        try:
            os.unlink(temp_db.name)
        except:
            pass

def main():
    """Main verification function"""
    print("🚀 Starting Task 10 verification...")
    print("=" * 60)
    
    # Test both properties
    error_handling_ok = test_error_handling_consistency()
    print()
    database_integrity_ok = test_database_integrity()
    
    print()
    print("=" * 60)
    
    if error_handling_ok and database_integrity_ok:
        print("✅ Task 10 verification PASSED")
        print("Both Property 8 (Error handling consistency) and Property 9 (Database integrity) are working correctly!")
        return True
    else:
        print("❌ Task 10 verification FAILED")
        if not error_handling_ok:
            print("  - Property 8 (Error handling consistency) has issues")
        if not database_integrity_ok:
            print("  - Property 9 (Database integrity preservation) has issues")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)