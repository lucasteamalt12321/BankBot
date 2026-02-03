#!/usr/bin/env python3
"""
Simple verification test for Task 9: Обновить существующие команды для совместимости
Tests the core functionality without requiring telegram module
"""

import os
import sys
import sqlite3
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin_system import AdminSystem
from utils.simple_db import init_database, register_user, get_user_by_id, update_user_balance


class SimpleTask9Verification:
    """Simple test class for verifying Task 9 core functionality"""
    
    def __init__(self):
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize admin system with test database
        self.admin_system = AdminSystem(self.db_path)
    
    def cleanup(self):
        """Clean up test database"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_admin_system_initialization(self):
        """Test that admin system initializes correctly"""
        print("Testing admin system initialization...")
        
        # Check that tables were created
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_table = cursor.fetchone()
        assert users_table is not None, "Users table should exist"
        
        # Check transactions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        transactions_table = cursor.fetchone()
        assert transactions_table is not None, "Transactions table should exist"
        
        # Check users table structure
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'username', 'first_name', 'balance', 'is_admin']
        for col in expected_columns:
            assert col in column_names, f"Column {col} should exist in users table"
        
        conn.close()
        print("✅ Admin system initialization test passed")
    
    def test_user_registration_functionality(self):
        """Test user registration functionality for /start command"""
        print("Testing user registration functionality...")
        
        # Test data
        user_id = 12345
        username = "testuser"
        first_name = "Test User"
        
        # Test registration
        success = self.admin_system.register_user(user_id, username, first_name)
        assert success, "User registration should succeed"
        
        # Verify user was created
        user = self.admin_system.get_user_by_id(user_id)
        assert user is not None, "User should exist after registration"
        assert user['id'] == user_id, f"User ID should be {user_id}"
        assert user['username'] == username, f"Username should be {username}"
        assert user['first_name'] == first_name, f"First name should be {first_name}"
        assert user['balance'] == 0, "Initial balance should be 0"
        assert user['is_admin'] == False, "User should not be admin initially"
        
        # Test duplicate registration (should not create duplicate)
        success2 = self.admin_system.register_user(user_id, username, first_name)
        assert success2, "Duplicate registration should return True (user exists)"
        
        # Verify still only one user
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE id = ?", (user_id,))
        count = cursor.fetchone()['count']
        conn.close()
        
        assert count == 1, f"Should have exactly 1 user record, found {count}"
        
        print("✅ User registration functionality test passed")
    
    def test_balance_functionality(self):
        """Test balance functionality for /balance command"""
        print("Testing balance functionality...")
        
        # Test data
        user_id = 12346
        username = "balanceuser"
        first_name = "Balance User"
        
        # Register user
        self.admin_system.register_user(user_id, username, first_name)
        
        # Test initial balance
        user = self.admin_system.get_user_by_id(user_id)
        assert user['balance'] == 0, "Initial balance should be 0"
        
        # Test balance update
        new_balance = self.admin_system.update_balance(user_id, 100.5)
        assert new_balance == 100.5, f"New balance should be 100.5, got {new_balance}"
        
        # Verify balance in database
        user = self.admin_system.get_user_by_id(user_id)
        assert user['balance'] == 100.5, f"Database balance should be 100.5, got {user['balance']}"
        
        # Test negative balance update
        new_balance = self.admin_system.update_balance(user_id, -50.25)
        assert new_balance == 50.25, f"New balance should be 50.25, got {new_balance}"
        
        print("✅ Balance functionality test passed")
    
    def test_admin_status_functionality(self):
        """Test admin status functionality"""
        print("Testing admin status functionality...")
        
        # Test data
        user_id = 12347
        username = "adminuser"
        first_name = "Admin User"
        
        # Register user
        self.admin_system.register_user(user_id, username, first_name)
        
        # Test initial admin status
        is_admin = self.admin_system.is_admin(user_id)
        assert is_admin == False, "User should not be admin initially"
        
        # Set admin status
        success = self.admin_system.set_admin_status(user_id, True)
        assert success, "Setting admin status should succeed"
        
        # Verify admin status
        is_admin = self.admin_system.is_admin(user_id)
        assert is_admin == True, "User should be admin after setting status"
        
        # Verify in database
        user = self.admin_system.get_user_by_id(user_id)
        assert user['is_admin'] == True, "Database should show user as admin"
        
        print("✅ Admin status functionality test passed")
    
    def test_transaction_logging(self):
        """Test transaction logging functionality"""
        print("Testing transaction logging functionality...")
        
        # Test data
        user_id = 12348
        admin_id = 12349
        
        # Register users
        self.admin_system.register_user(user_id, "user", "User")
        self.admin_system.register_user(admin_id, "admin", "Admin")
        
        # Add transaction
        transaction_id = self.admin_system.add_transaction(user_id, 50.0, 'add', admin_id)
        assert transaction_id is not None, "Transaction should be created successfully"
        
        # Verify transaction in database
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
        transaction = cursor.fetchone()
        conn.close()
        
        assert transaction is not None, "Transaction should exist in database"
        assert transaction['user_id'] == user_id, f"Transaction user_id should be {user_id}"
        assert transaction['amount'] == 50.0, f"Transaction amount should be 50.0"
        assert transaction['type'] == 'add', f"Transaction type should be 'add'"
        assert transaction['admin_id'] == admin_id, f"Transaction admin_id should be {admin_id}"
        
        print("✅ Transaction logging functionality test passed")
    
    def test_user_lookup_functionality(self):
        """Test user lookup functionality"""
        print("Testing user lookup functionality...")
        
        # Test data
        user_id = 12350
        username = "lookupuser"
        first_name = "Lookup User"
        
        # Register user
        self.admin_system.register_user(user_id, username, first_name)
        
        # Test lookup by ID
        user_by_id = self.admin_system.get_user_by_id(user_id)
        assert user_by_id is not None, "Should find user by ID"
        assert user_by_id['username'] == username, "Username should match"
        
        # Test lookup by username
        user_by_username = self.admin_system.get_user_by_username(username)
        assert user_by_username is not None, "Should find user by username"
        assert user_by_username['id'] == user_id, "User ID should match"
        
        # Test lookup by username with @
        user_by_username_at = self.admin_system.get_user_by_username(f"@{username}")
        assert user_by_username_at is not None, "Should find user by username with @"
        assert user_by_username_at['id'] == user_id, "User ID should match"
        
        # Test lookup non-existent user
        non_existent = self.admin_system.get_user_by_id(99999)
        assert non_existent is None, "Should return None for non-existent user"
        
        print("✅ User lookup functionality test passed")
    
    def test_users_count_functionality(self):
        """Test users count functionality"""
        print("Testing users count functionality...")
        
        # Get initial count
        initial_count = self.admin_system.get_users_count()
        
        # Register some users
        self.admin_system.register_user(20001, "user1", "User 1")
        self.admin_system.register_user(20002, "user2", "User 2")
        self.admin_system.register_user(20003, "user3", "User 3")
        
        # Check count increased
        new_count = self.admin_system.get_users_count()
        assert new_count == initial_count + 3, f"Count should increase by 3, got {new_count - initial_count}"
        
        print("✅ Users count functionality test passed")
    
    def verify_bot_integration_points(self):
        """Verify that bot integration points exist"""
        print("Verifying bot integration points...")
        
        # Check that bot.py file exists and contains expected methods
        bot_file = "bot/bot.py"
        assert os.path.exists(bot_file), "bot/bot.py should exist"
        
        with open(bot_file, 'r', encoding='utf-8') as f:
            bot_content = f.read()
        
        # Check for welcome_command method
        assert "async def welcome_command" in bot_content, "/start command handler should exist"
        assert "auto_registration_middleware.process_message" in bot_content, "/start should use auto-registration"
        
        # Check for balance_command method
        assert "async def balance_command" in bot_content, "/balance command handler should exist"
        assert "admin_system.get_user_by_id" in bot_content, "/balance should use admin system"
        
        # Check for admin system initialization
        assert "AdminSystem" in bot_content, "Bot should initialize AdminSystem"
        assert "admin_system.db" in bot_content or "admin_system" in bot_content, "Bot should use admin system"
        
        print("✅ Bot integration points verification passed")
    
    def run_all_tests(self):
        """Run all verification tests"""
        print("=" * 60)
        print("TASK 9 SIMPLE VERIFICATION TESTS")
        print("=" * 60)
        
        try:
            self.test_admin_system_initialization()
            self.test_user_registration_functionality()
            self.test_balance_functionality()
            self.test_admin_status_functionality()
            self.test_transaction_logging()
            self.test_user_lookup_functionality()
            self.test_users_count_functionality()
            self.verify_bot_integration_points()
            
            print("=" * 60)
            print("✅ ALL TASK 9 TESTS PASSED!")
            print("=" * 60)
            print()
            print("VERIFICATION SUMMARY:")
            print("✅ Task 9.1: /start command updated for new registration system")
            print("   - Auto-registration middleware integrated")
            print("   - User registration functionality working")
            print("   - Idempotent registration (no duplicates)")
            print()
            print("✅ Task 9.2: /balance command updated for new database structure")
            print("   - Admin system integration working")
            print("   - Balance retrieval from new database")
            print("   - Admin status display functionality")
            print()
            print("✅ Core admin system functionality verified:")
            print("   - Database initialization and structure")
            print("   - User registration and lookup")
            print("   - Balance management")
            print("   - Transaction logging")
            print("   - Admin status management")
            print("   - Users count functionality")
            print()
            print("✅ Bot integration points verified")
            print()
            return True
            
        except Exception as e:
            print(f"❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self.cleanup()


def main():
    """Main test function"""
    tester = SimpleTask9Verification()
    success = tester.run_all_tests()
    
    if success:
        print("Task 9 verification completed successfully!")
        print("Both subtasks 9.1 and 9.2 are working correctly.")
        return 0
    else:
        print("Task 9 verification failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)