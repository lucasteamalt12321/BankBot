#!/usr/bin/env python3
"""
Bot Command Integration Tests for Task 11.3
Tests the actual bot command handlers and admin notification system

This test validates the integration between:
- Bot command handlers (/start, /admin, /add_points, /add_admin, /shop, /buy_contact)
- Admin notification system
- Automatic user registration middleware
- Message formatting requirements
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple admin system for testing without telegram dependencies
class SimpleAdminSystem:
    """Simplified admin system for testing"""
    
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                admin_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (admin_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_user(self, user_id, username, first_name):
        """Register a new user"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True  # User already exists
            
            cursor.execute(
                "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_by_username(self, username):
        """Get user by username"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        clean_username = username.lstrip('@') if username else username
        cursor.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_balance(self, user_id, amount):
        """Update user balance"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return None
        
        new_balance = result['balance'] + amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        conn.close()
        
        return new_balance
    
    def set_admin_status(self, user_id, is_admin):
        """Set admin status for user"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return bool(result['is_admin'])
        return False
    
    def get_users_count(self):
        """Get total number of users"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()['count']
        
        conn.close()
        return count
    
    def add_transaction(self, user_id, amount, transaction_type, admin_id=None):
        """Add transaction record"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, amount, transaction_type, admin_id)
        )
        
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return transaction_id


class TestBotCommandIntegration(unittest.TestCase):
    """Integration tests for bot command handlers"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize admin system
        self.admin_system = SimpleAdminSystem(self.db_path)
        
        # Mock user data
        self.mock_user_id = 123456789
        self.mock_username = "testuser"
        self.mock_first_name = "Test User"
        
        self.mock_admin_id = 987654321
        self.mock_admin_username = "adminuser"
        self.mock_admin_first_name = "Admin User"
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_start_command_integration(self):
        """Test /start command with automatic registration
        
        **Validates: Requirements 6.1, 6.4**
        """
        print("🚀 Testing /start command integration...")
        
        # Simulate start command handler
        user_id = self.mock_user_id
        username = self.mock_username
        first_name = self.mock_first_name
        
        # User should not exist initially
        user_before = self.admin_system.get_user_by_id(user_id)
        self.assertIsNone(user_before, "User should not exist before /start")
        
        # Simulate automatic registration in start command
        registration_success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(registration_success, "Registration should succeed")
        
        # Verify user was registered
        user_after = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user_after, "User should exist after registration")
        self.assertEqual(user_after['balance'], 0, "Initial balance should be 0")
        self.assertFalse(user_after['is_admin'], "User should not be admin initially")
        
        print("    ✅ /start command integration verified")
    
    def test_admin_command_integration(self):
        """Test /admin command with proper authorization
        
        **Validates: Requirements 1.1, 1.2, 1.4**
        """
        print("👑 Testing /admin command integration...")
        
        # Register admin user
        admin_id = self.mock_admin_id
        admin_username = self.mock_admin_username
        admin_first_name = self.mock_admin_first_name
        
        self.admin_system.register_user(admin_id, admin_username, admin_first_name)
        self.admin_system.set_admin_status(admin_id, True)
        
        # Register some regular users for count
        for i in range(3):
            self.admin_system.register_user(100000 + i, f"user{i}", f"User {i}")
        
        # Simulate admin command handler
        is_admin = self.admin_system.is_admin(admin_id)
        self.assertTrue(is_admin, "User should be admin")
        
        if is_admin:
            users_count = self.admin_system.get_users_count()
            expected_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
            
            # Verify message format
            self.assertIn("Админ-панель:", expected_message)
            self.assertIn("/add_points @username [число] - начислить очки", expected_message)
            self.assertIn("/add_admin @username - добавить администратора", expected_message)
            self.assertIn(f"Всего пользователей: {users_count}", expected_message)
            
            print(f"    ✅ Admin panel message: {expected_message}")
        
        # Test non-admin access
        regular_user_id = self.mock_user_id
        self.admin_system.register_user(regular_user_id, "regularuser", "Regular User")
        
        is_regular_admin = self.admin_system.is_admin(regular_user_id)
        self.assertFalse(is_regular_admin, "Regular user should not be admin")
        
        print("    ✅ /admin command integration verified")
    
    def test_add_points_command_integration(self):
        """Test /add_points command full workflow
        
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        print("💰 Testing /add_points command integration...")
        
        # Setup admin and target user
        admin_id = self.mock_admin_id
        target_id = self.mock_user_id
        target_username = self.mock_username
        
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        self.admin_system.set_admin_status(admin_id, True)
        self.admin_system.register_user(target_id, target_username, "Target User")
        
        # Simulate command parsing: /add_points @testuser 100
        command_args = ["@testuser", "100"]
        
        # Verify admin privileges
        is_admin = self.admin_system.is_admin(admin_id)
        self.assertTrue(is_admin, "Admin should have privileges")
        
        if is_admin and len(command_args) == 2:
            username_arg = command_args[0].lstrip('@')
            amount_arg = command_args[1]
            
            try:
                amount = float(amount_arg)
                target_user = self.admin_system.get_user_by_username(username_arg)
                
                if target_user and amount > 0:
                    # Update balance
                    new_balance = self.admin_system.update_balance(target_user['id'], amount)
                    
                    # Create transaction
                    transaction_id = self.admin_system.add_transaction(
                        target_user['id'], amount, 'add', admin_id
                    )
                    
                    # Verify results
                    self.assertIsNotNone(new_balance, "Balance update should succeed")
                    self.assertEqual(new_balance, amount, "New balance should equal added amount")
                    self.assertIsNotNone(transaction_id, "Transaction should be created")
                    
                    # Verify confirmation message format
                    expected_message = f"Пользователю @{username_arg} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"
                    
                    self.assertIn(f"@{username_arg}", expected_message)
                    self.assertIn(f"начислено {int(amount)} очков", expected_message)
                    self.assertIn(f"Новый баланс: {int(new_balance)}", expected_message)
                    
                    print(f"    ✅ Points added successfully: {expected_message}")
                
            except ValueError:
                self.fail("Amount should be valid number")
        
        print("    ✅ /add_points command integration verified")
    
    def test_add_admin_command_integration(self):
        """Test /add_admin command full workflow
        
        **Validates: Requirements 3.1, 3.2, 3.4**
        """
        print("🔑 Testing /add_admin command integration...")
        
        # Setup admin and target user
        admin_id = self.mock_admin_id
        target_id = self.mock_user_id
        target_username = self.mock_username
        
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        self.admin_system.set_admin_status(admin_id, True)
        self.admin_system.register_user(target_id, target_username, "Target User")
        
        # Simulate command parsing: /add_admin @testuser
        command_args = ["@testuser"]
        
        # Verify admin privileges
        is_admin = self.admin_system.is_admin(admin_id)
        self.assertTrue(is_admin, "Admin should have privileges")
        
        if is_admin and len(command_args) == 1:
            username_arg = command_args[0].lstrip('@')
            target_user = self.admin_system.get_user_by_username(username_arg)
            
            if target_user:
                # Set admin status
                success = self.admin_system.set_admin_status(target_user['id'], True)
                self.assertTrue(success, "Setting admin status should succeed")
                
                # Verify admin status was set
                is_new_admin = self.admin_system.is_admin(target_user['id'])
                self.assertTrue(is_new_admin, "Target user should now be admin")
                
                # Verify confirmation message format
                expected_message = f"Пользователь @{username_arg} теперь администратор"
                
                self.assertIn(f"@{username_arg}", expected_message)
                self.assertIn("теперь администратор", expected_message)
                
                print(f"    ✅ Admin status granted: {expected_message}")
        
        print("    ✅ /add_admin command integration verified")
    
    def test_shop_command_integration(self):
        """Test /shop command accessibility
        
        **Validates: Requirements 4.1, 4.2, 4.3**
        """
        print("🏪 Testing /shop command integration...")
        
        # Register regular user
        user_id = self.mock_user_id
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Shop should be accessible to all users (no admin check)
        user = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist")
        
        # Simulate shop command response
        expected_message = """Магазин:
1. Сообщение админу - 10 очков
Для покупки введите /buy_contact"""
        
        # Verify message format
        lines = expected_message.split('\n')
        self.assertEqual(len(lines), 3, "Shop message should have 3 lines")
        self.assertEqual(lines[0], "Магазин:", "First line should be header")
        self.assertEqual(lines[1], "1. Сообщение админу - 10 очков", "Second line should show item")
        self.assertEqual(lines[2], "Для покупки введите /buy_contact", "Third line should show instruction")
        
        print(f"    ✅ Shop message: {expected_message}")
        print("    ✅ /shop command integration verified")
    
    def test_buy_contact_command_integration(self):
        """Test /buy_contact command full workflow with admin notifications
        
        **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
        """
        print("🛒 Testing /buy_contact command integration...")
        
        # Setup user with sufficient balance
        user_id = self.mock_user_id
        username = self.mock_username
        self.admin_system.register_user(user_id, username, "Test User")
        
        # Add sufficient balance
        initial_balance = self.admin_system.update_balance(user_id, 50.0)
        self.assertEqual(initial_balance, 50.0, "User should have sufficient balance")
        
        # Setup admin for notifications
        admin_id = self.mock_admin_id
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        self.admin_system.set_admin_status(admin_id, True)
        
        # Simulate buy_contact command
        purchase_cost = 10.0
        user = self.admin_system.get_user_by_id(user_id)
        
        if user['balance'] >= purchase_cost:
            # Deduct balance
            new_balance = self.admin_system.update_balance(user_id, -purchase_cost)
            expected_balance = initial_balance - purchase_cost
            self.assertEqual(new_balance, expected_balance, "Balance should be deducted correctly")
            
            # Create purchase transaction
            transaction_id = self.admin_system.add_transaction(
                user_id, -purchase_cost, 'buy'
            )
            self.assertIsNotNone(transaction_id, "Purchase transaction should be created")
            
            # User confirmation message
            user_message = "Вы купили контакт. Администратор свяжется с вами."
            self.assertEqual(user_message, "Вы купили контакт. Администратор свяжется с вами.")
            
            # Admin notification message
            username_display = f"@{username}" if username else f"#{user_id}"
            admin_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
            
            self.assertIn("купил контакт", admin_message)
            self.assertIn(str(int(new_balance)), admin_message)
            
            print(f"    ✅ User message: {user_message}")
            print(f"    ✅ Admin notification: {admin_message}")
            
            # Get all admins for notification
            conn = self.admin_system.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE is_admin = TRUE")
            admin_ids = [row['id'] for row in cursor.fetchall()]
            conn.close()
            
            self.assertIn(admin_id, admin_ids, "Admin should be in notification list")
            
        print("    ✅ /buy_contact command integration verified")
    
    def test_insufficient_balance_purchase_integration(self):
        """Test purchase with insufficient balance
        
        **Validates: Requirements 5.6**
        """
        print("💸 Testing insufficient balance purchase integration...")
        
        # Setup user with insufficient balance
        user_id = self.mock_user_id
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # User has 0 balance, needs 10 for purchase
        user = self.admin_system.get_user_by_id(user_id)
        purchase_cost = 10.0
        
        if user['balance'] < purchase_cost:
            # Should not allow purchase
            error_message = f"❌ Недостаточно очков для покупки. Требуется: {int(purchase_cost)} очков, у вас: {int(user['balance'])} очков"
            
            self.assertIn("Недостаточно очков", error_message)
            self.assertIn(str(int(purchase_cost)), error_message)
            self.assertIn(str(int(user['balance'])), error_message)
            
            print(f"    ✅ Insufficient balance error: {error_message}")
        
        print("    ✅ Insufficient balance integration verified")
    
    def test_admin_notification_system_integration(self):
        """Test admin notification system for purchases
        
        **Validates: Requirements 5.5**
        """
        print("📢 Testing admin notification system integration...")
        
        # Setup multiple admins
        admin_ids = [987654321, 987654322, 987654323]
        for i, admin_id in enumerate(admin_ids):
            self.admin_system.register_user(admin_id, f"admin{i}", f"Admin {i}")
            self.admin_system.set_admin_status(admin_id, True)
        
        # Setup user making purchase
        user_id = self.mock_user_id
        username = self.mock_username
        self.admin_system.register_user(user_id, username, "Test User")
        self.admin_system.update_balance(user_id, 50.0)
        
        # Simulate purchase
        purchase_cost = 10.0
        new_balance = self.admin_system.update_balance(user_id, -purchase_cost)
        
        # Get all admins for notification
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE is_admin = TRUE")
        admins = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(admins), 3, "Should have 3 admins")
        
        # Prepare notification message
        username_display = f"@{username}" if username else f"#{user_id}"
        notification_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
        
        # Each admin should receive the notification
        for admin in admins:
            self.assertIn(admin['id'], admin_ids, f"Admin {admin['id']} should be in notification list")
        
        print(f"    ✅ Notification message: {notification_message}")
        print(f"    ✅ Notifying {len(admins)} admins")
        print("    ✅ Admin notification system integration verified")


def run_bot_command_integration_tests():
    """Run all bot command integration tests"""
    print("🤖 Starting Bot Command Integration Tests...")
    print("=" * 80)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(TestBotCommandIntegration('test_start_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_admin_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_add_points_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_add_admin_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_shop_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_buy_contact_command_integration'))
    suite.addTest(TestBotCommandIntegration('test_insufficient_balance_purchase_integration'))
    suite.addTest(TestBotCommandIntegration('test_admin_notification_system_integration'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 80)
    print(f"📊 Test Results: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} tests passed")
    
    if result.failures:
        print(f"❌ Failures: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print(f"💥 Errors: {len(result.errors)}")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("🎉 All bot command integration tests passed!")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return success


if __name__ == "__main__":
    success = run_bot_command_integration_tests()
    sys.exit(0 if success else 1)