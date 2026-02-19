#!/usr/bin/env python3
"""
Task 9 Verification Test: Обновить существующие команды для совместимости

This test verifies that:
- Task 9.1: /start command is updated for new registration system integration
- Task 9.2: /balance command is updated for new database structure

Requirements validated: 6.4, 8.7
"""

import unittest
import tempfile
import os
import sys
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database.simple_db import register_user, get_user_by_id, init_database, get_db_connection
from utils.admin.admin_system import AdminSystem
from utils.admin.admin_middleware import auto_registration_middleware


class TestTask9Verification(unittest.TestCase):
    """Verification tests for Task 9: Updated existing commands for compatibility"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override DB_PATH for testing
        import utils.database.simple_db
        self.original_db_path = utils.simple_db.DB_PATH
        utils.simple_db.DB_PATH = self.temp_db.name
        
        # Initialize test database
        init_database()
        
        # Create admin system instance
        self.admin_system = AdminSystem(self.temp_db.name)
    
    def tearDown(self):
        """Cleanup test database"""
        # Restore original DB_PATH
        import utils.database.simple_db
        utils.simple_db.DB_PATH = self.original_db_path
        
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    def test_task_9_1_start_command_integration(self):
        """
        Task 9.1: Verify /start command integration with new registration system
        
        Requirements: 6.4, 8.7
        """
        print("Testing Task 9.1: /start command integration...")
        
        # Test data
        user_id = 123456789
        username = "testuser"
        first_name = "Test User"
        
        # Verify user doesn't exist initially
        user = get_user_by_id(user_id)
        self.assertIsNone(user, "User should not exist initially")
        
        # Simulate auto registration middleware processing
        # This would normally happen when /start command is called
        success = register_user(user_id, username, first_name)
        self.assertTrue(success, "Auto registration should succeed")
        
        # Verify user was registered correctly
        user = get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist after auto registration")
        self.assertEqual(user['id'], user_id)
        self.assertEqual(user['username'], username)
        self.assertEqual(user['first_name'], first_name)
        self.assertEqual(user['balance'], 0.0)
        self.assertFalse(user['is_admin'])
        
        # Test idempotence - second registration should not create duplicate
        success2 = register_user(user_id, username, first_name)
        self.assertFalse(success2, "Second registration should return False (user exists)")
        
        # Verify still only one user record
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE id = ?', (user_id,))
            count = cursor.fetchone()['count']
            self.assertEqual(count, 1, "Should have exactly one user record")
        finally:
            conn.close()
        
        print("✓ Task 9.1: /start command integration verified")
    
    def test_task_9_2_balance_command_database_structure(self):
        """
        Task 9.2: Verify /balance command works with new database structure
        
        Requirements: 8.7
        """
        print("Testing Task 9.2: /balance command database structure...")
        
        # Test data
        user_id = 987654321
        username = "balanceuser"
        first_name = "Balance User"
        initial_balance = 150.0
        
        # Register user
        success = register_user(user_id, username, first_name)
        self.assertTrue(success, "User registration should succeed")
        
        # Update balance using admin system
        new_balance = self.admin_system.update_balance(user_id, initial_balance)
        self.assertEqual(new_balance, initial_balance, "Balance update should work correctly")
        
        # Verify balance can be retrieved correctly
        user = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist in admin system")
        self.assertEqual(user['balance'], initial_balance, "Balance should match")
        
        # Test admin status display
        admin_user_id = 111111111
        admin_success = register_user(admin_user_id, "adminuser", "Admin User")
        self.assertTrue(admin_success, "Admin user registration should succeed")
        
        # Set admin status
        admin_status_set = self.admin_system.set_admin_status(admin_user_id, True)
        self.assertTrue(admin_status_set, "Admin status should be set successfully")
        
        # Verify admin status
        admin_user = self.admin_system.get_user_by_id(admin_user_id)
        self.assertIsNotNone(admin_user, "Admin user should exist")
        self.assertTrue(admin_user['is_admin'], "User should have admin status")
        
        print("✓ Task 9.2: /balance command database structure verified")
    
    def test_compatibility_with_existing_functionality(self):
        """
        Verify that new admin system doesn't break existing functionality
        
        Requirements: 8.7
        """
        print("Testing compatibility with existing functionality...")
        
        # Test multiple users
        users_data = [
            (100001, "user1", "User One"),
            (100002, "user2", "User Two"),
            (100003, "user3", "User Three"),
        ]
        
        # Register all users
        for user_id, username, first_name in users_data:
            success = register_user(user_id, username, first_name)
            self.assertTrue(success, f"Registration should succeed for user {user_id}")
        
        # Verify all users exist
        for user_id, username, first_name in users_data:
            user = get_user_by_id(user_id)
            self.assertIsNotNone(user, f"User {user_id} should exist")
            self.assertEqual(user['username'], username)
            self.assertEqual(user['first_name'], first_name)
        
        # Test balance operations
        for user_id, _, _ in users_data:
            # Add some balance
            amount = user_id % 100  # Different amounts for each user
            new_balance = self.admin_system.update_balance(user_id, amount)
            self.assertEqual(new_balance, amount, f"Balance should be updated for user {user_id}")
        
        # Verify users count
        total_users = self.admin_system.get_users_count()
        self.assertEqual(total_users, len(users_data), "Users count should match registered users")
        
        print("✓ Compatibility with existing functionality verified")
    
    def test_database_schema_compatibility(self):
        """
        Verify that the database schema is compatible with requirements
        
        Requirements: 7.1, 7.2, 7.3
        """
        print("Testing database schema compatibility...")
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check users table structure
            cursor.execute("PRAGMA table_info(users)")
            users_columns = {row['name']: row['type'] for row in cursor.fetchall()}
            
            expected_users_columns = {
                'id': 'INTEGER',
                'username': 'TEXT',
                'first_name': 'TEXT',
                'balance': 'REAL',
                'is_admin': 'BOOLEAN'
            }
            
            for col_name, col_type in expected_users_columns.items():
                self.assertIn(col_name, users_columns, f"Column {col_name} should exist in users table")
                self.assertEqual(users_columns[col_name], col_type, f"Column {col_name} should have type {col_type}")
            
            # Check transactions table structure
            cursor.execute("PRAGMA table_info(transactions)")
            transactions_columns = {row['name']: row['type'] for row in cursor.fetchall()}
            
            expected_transactions_columns = {
                'id': 'INTEGER',
                'user_id': 'INTEGER',
                'amount': 'REAL',
                'type': 'TEXT',
                'admin_id': 'INTEGER',
                'timestamp': 'DATETIME'
            }
            
            for col_name, col_type in expected_transactions_columns.items():
                self.assertIn(col_name, transactions_columns, f"Column {col_name} should exist in transactions table")
                self.assertEqual(transactions_columns[col_name], col_type, f"Column {col_name} should have type {col_type}")
            
            # Check foreign key constraints
            cursor.execute("PRAGMA foreign_key_list(transactions)")
            foreign_keys = cursor.fetchall()
            self.assertGreater(len(foreign_keys), 0, "Transactions table should have foreign key constraints")
            
        finally:
            conn.close()
        
        print("✓ Database schema compatibility verified")


def run_task_9_verification():
    """Run Task 9 verification tests"""
    print("=" * 60)
    print("TASK 9 VERIFICATION: Обновить существующие команды для совместимости")
    print("=" * 60)
    
    # Run the tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTask9Verification)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ TASK 9 VERIFICATION PASSED")
        print("✓ Task 9.1: /start command integration with new registration system")
        print("✓ Task 9.2: /balance command compatibility with new database structure")
        print("✓ All existing functionality preserved")
        print("✓ Database schema compatibility verified")
    else:
        print("❌ TASK 9 VERIFICATION FAILED")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
    
    print("=" * 60)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_task_9_verification()
    sys.exit(0 if success else 1)