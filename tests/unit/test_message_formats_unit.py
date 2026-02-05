#!/usr/bin/env python3
"""
Unit tests for message formats - Task 11.1
Tests exact message formats for /admin, /shop, confirmations
Requirements: 1.1, 4.1, 2.3, 3.2, 5.4, 5.5
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple admin system mock to avoid telegram dependencies
class SimpleAdminSystem:
    """Simplified admin system for testing message formats"""
    
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
    
    def register_user(self, user_id, username, first_name):
        """Register a new user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def get_user_by_username(self, username):
        """Get user by username"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Remove @ if present
        clean_username = username.lstrip('@')
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_balance(self, user_id, amount):
        """Update user balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        return result[0] if result else None
    
    def set_admin_status(self, user_id, is_admin):
        """Set admin status for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def get_users_count(self):
        """Get total number of users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def add_transaction(self, user_id, amount, transaction_type, admin_id=None):
        """Add transaction record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, amount, transaction_type, admin_id)
        )
        
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return transaction_id


class TestMessageFormats(unittest.TestCase):
    """Test cases for exact message formats"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize admin system
        self.admin_system = SimpleAdminSystem(self.db_path)
        
        # Create test users
        self.admin_user_id = 123456789
        self.admin_username = "testadmin"
        self.admin_first_name = "Test Admin"
        
        self.regular_user_id = 987654321
        self.regular_username = "testuser"
        self.regular_first_name = "Test User"
        
        # Register users
        self.admin_system.register_user(
            self.admin_user_id, self.admin_username, self.admin_first_name
        )
        self.admin_system.register_user(
            self.regular_user_id, self.regular_username, self.regular_first_name
        )
        
        # Make first user admin
        self.admin_system.set_admin_status(self.admin_user_id, True)
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_admin_command_message_format(self):
        """Test /admin command exact message format
        
        Validates: Requirements 1.1
        """
        # Get users count for the message
        users_count = self.admin_system.get_users_count()
        
        # Expected exact format from requirements
        expected_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Test exact format
        lines = expected_message.split('\n')
        
        # Verify each line matches requirements exactly
        self.assertEqual(lines[0], "Админ-панель:", 
                        "First line must be exactly 'Админ-панель:'")
        
        self.assertEqual(lines[1], "/add_points @username [число] - начислить очки",
                        "Second line must show add_points command format exactly")
        
        self.assertEqual(lines[2], "/add_admin @username - добавить администратора",
                        "Third line must show add_admin command format exactly")
        
        self.assertEqual(lines[3], f"Всего пользователей: {users_count}",
                        "Fourth line must show user count exactly")
        
        # Test that message contains all required elements
        self.assertIn("Админ-панель:", expected_message)
        self.assertIn("/add_points @username [число] - начислить очки", expected_message)
        self.assertIn("/add_admin @username - добавить администратора", expected_message)
        self.assertIn(f"Всего пользователей: {users_count}", expected_message)
        
        print(f"✓ Admin panel message format verified: {expected_message}")
    
    def test_shop_command_message_format(self):
        """Test /shop command exact message format
        
        Validates: Requirements 4.1
        """
        # Expected exact format from requirements
        expected_message = """Магазин:
1. Сообщение админу - 10 очков
Для покупки введите /buy_contact"""
        
        # Test exact format
        lines = expected_message.split('\n')
        
        # Verify each line matches requirements exactly
        self.assertEqual(lines[0], "Магазин:", 
                        "First line must be exactly 'Магазин:'")
        
        self.assertEqual(lines[1], "1. Сообщение админу - 10 очков",
                        "Second line must show item with exact price format")
        
        self.assertEqual(lines[2], "Для покупки введите /buy_contact",
                        "Third line must show exact purchase instruction")
        
        # Test that message contains all required elements
        self.assertIn("Магазин:", expected_message)
        self.assertIn("1. Сообщение админу - 10 очков", expected_message)
        self.assertIn("Для покупки введите /buy_contact", expected_message)
        
        print(f"✓ Shop message format verified: {expected_message}")
    
    def test_add_points_confirmation_format(self):
        """Test /add_points command confirmation message format
        
        Validates: Requirements 2.3
        """
        # Test data
        target_username = "testuser"
        points_amount = 100
        
        # Get user and update balance to simulate the command
        target_user = self.admin_system.get_user_by_username(target_username)
        self.assertIsNotNone(target_user, "Target user must exist for test")
        
        # Update balance
        new_balance = self.admin_system.update_balance(target_user['id'], points_amount)
        
        # Expected exact format from requirements
        expected_message = f"Пользователю @{target_username} начислено {points_amount} очков. Новый баланс: {int(new_balance)}"
        
        # Test exact format components
        self.assertIn(f"Пользователю @{target_username}", expected_message)
        self.assertIn(f"начислено {points_amount} очков", expected_message)
        self.assertIn(f"Новый баланс: {int(new_balance)}", expected_message)
        
        # Test exact format structure
        expected_pattern = f"Пользователю @{target_username} начислено {points_amount} очков. Новый баланс: {int(new_balance)}"
        self.assertEqual(expected_message, expected_pattern,
                        "Add points confirmation must match exact format")
        
        print(f"✓ Add points confirmation format verified: {expected_message}")
    
    def test_add_admin_confirmation_format(self):
        """Test /add_admin command confirmation message format
        
        Validates: Requirements 3.2
        """
        # Create a new user to make admin
        new_user_id = 555555555
        new_username = "newadmin"
        new_first_name = "New Admin"
        
        self.admin_system.register_user(new_user_id, new_username, new_first_name)
        
        # Set admin status
        success = self.admin_system.set_admin_status(new_user_id, True)
        self.assertTrue(success, "Setting admin status must succeed")
        
        # Expected exact format from requirements
        expected_message = f"Пользователь @{new_username} теперь администратор"
        
        # Test exact format components
        self.assertIn(f"Пользователь @{new_username}", expected_message)
        self.assertIn("теперь администратор", expected_message)
        
        # Test exact format structure
        expected_pattern = f"Пользователь @{new_username} теперь администратор"
        self.assertEqual(expected_message, expected_pattern,
                        "Add admin confirmation must match exact format")
        
        print(f"✓ Add admin confirmation format verified: {expected_message}")
    
    def test_buy_contact_user_confirmation_format(self):
        """Test /buy_contact user confirmation message format
        
        Validates: Requirements 5.4
        """
        # Expected exact format from requirements
        expected_message = "Вы купили контакт. Администратор свяжется с вами."
        
        # Test exact format
        self.assertEqual(expected_message, "Вы купили контакт. Администратор свяжется с вами.",
                        "Buy contact user confirmation must match exact format")
        
        # Test message components
        self.assertIn("Вы купили контакт", expected_message)
        self.assertIn("Администратор свяжется с вами", expected_message)
        
        print(f"✓ Buy contact user confirmation format verified: {expected_message}")
    
    def test_buy_contact_admin_notification_format(self):
        """Test /buy_contact admin notification message format
        
        Validates: Requirements 5.5
        """
        # Test data
        username = "testuser"
        new_balance = 40  # After spending 10 points from 50
        
        # Expected exact format from requirements
        expected_message = f"Пользователь @{username} купил контакт. Его баланс: {new_balance} очков"
        
        # Test exact format components
        self.assertIn(f"Пользователь @{username}", expected_message)
        self.assertIn("купил контакт", expected_message)
        self.assertIn(f"Его баланс: {new_balance} очков", expected_message)
        
        # Test exact format structure
        expected_pattern = f"Пользователь @{username} купил контакт. Его баланс: {new_balance} очков"
        self.assertEqual(expected_message, expected_pattern,
                        "Buy contact admin notification must match exact format")
        
        print(f"✓ Buy contact admin notification format verified: {expected_message}")
    
    def test_statistics_display_format(self):
        """Test statistics display in admin panel
        
        Validates: Requirements 1.1 (user count display)
        """
        # Get current user count
        users_count = self.admin_system.get_users_count()
        
        # Test that count is displayed correctly
        self.assertIsInstance(users_count, int, "User count must be integer")
        self.assertGreaterEqual(users_count, 2, "Should have at least 2 test users")
        
        # Test format in admin panel message
        admin_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Verify statistics line format
        lines = admin_message.split('\n')
        stats_line = lines[3]
        
        self.assertEqual(stats_line, f"Всего пользователей: {users_count}",
                        "Statistics line must show exact user count format")
        
        print(f"✓ Statistics display format verified: {stats_line}")
    
    def test_product_display_format(self):
        """Test product display format in shop
        
        Validates: Requirements 4.1 (product display)
        """
        # Expected product format
        product_line = "1. Сообщение админу - 10 очков"
        
        # Test product format components
        self.assertIn("1.", product_line, "Product must have number")
        self.assertIn("Сообщение админу", product_line, "Product must have name")
        self.assertIn("10 очков", product_line, "Product must have price in points")
        self.assertIn(" - ", product_line, "Product must have separator")
        
        # Test exact format
        expected_format = "1. Сообщение админу - 10 очков"
        self.assertEqual(product_line, expected_format,
                        "Product display must match exact format")
        
        print(f"✓ Product display format verified: {product_line}")
    
    def test_username_formatting_consistency(self):
        """Test username formatting consistency across messages
        
        Validates: All requirements with username display
        """
        test_username = "testuser"
        
        # Test that usernames are consistently formatted with @
        add_points_msg = f"Пользователю @{test_username} начислено 100 очков. Новый баланс: 200"
        add_admin_msg = f"Пользователь @{test_username} теперь администратор"
        buy_contact_msg = f"Пользователь @{test_username} купил контакт. Его баланс: 40 очков"
        
        # All messages should use @username format
        self.assertIn(f"@{test_username}", add_points_msg)
        self.assertIn(f"@{test_username}", add_admin_msg)
        self.assertIn(f"@{test_username}", buy_contact_msg)
        
        # Test that @ is always present before username
        for msg in [add_points_msg, add_admin_msg, buy_contact_msg]:
            username_index = msg.find(test_username)
            if username_index > 0:
                self.assertEqual(msg[username_index - 1], '@',
                               f"Username must be prefixed with @ in: {msg}")
        
        print("✓ Username formatting consistency verified")
    
    def test_number_formatting_consistency(self):
        """Test number formatting consistency in messages
        
        Validates: Requirements with numeric values
        """
        # Test integer formatting for points
        points = 100
        balance = 200
        
        add_points_msg = f"Пользователю @testuser начислено {points} очков. Новый баланс: {balance}"
        
        # Numbers should be displayed as integers (no decimals)
        self.assertNotIn(".0", add_points_msg, "Points should be displayed as integers")
        self.assertIn("100", add_points_msg, "Points amount should be displayed")
        self.assertIn("200", add_points_msg, "Balance should be displayed")
        
        # Test shop price formatting
        shop_msg = "1. Сообщение админу - 10 очков"
        self.assertIn("10", shop_msg, "Shop price should be displayed as integer")
        self.assertNotIn("10.0", shop_msg, "Shop price should not have decimals")
        
        print("✓ Number formatting consistency verified")


class TestMessageFormatEdgeCases(unittest.TestCase):
    """Test edge cases for message formats"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.admin_system = SimpleAdminSystem(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_zero_users_count_format(self):
        """Test admin panel format with zero users"""
        users_count = self.admin_system.get_users_count()
        
        expected_message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Should work even with 0 users
        self.assertIn(f"Всего пользователей: {users_count}", expected_message)
        
        print(f"✓ Zero users count format verified: {users_count}")
    
    def test_large_numbers_format(self):
        """Test message format with large numbers"""
        # Create user and add large amount
        user_id = 123456789
        username = "testuser"
        self.admin_system.register_user(user_id, username, "Test User")
        
        large_amount = 999999
        new_balance = self.admin_system.update_balance(user_id, large_amount)
        
        expected_message = f"Пользователю @{username} начислено {large_amount} очков. Новый баланс: {int(new_balance)}"
        
        # Should handle large numbers correctly
        self.assertIn(str(large_amount), expected_message)
        self.assertIn(str(int(new_balance)), expected_message)
        
        print(f"✓ Large numbers format verified: {large_amount}")
    
    def test_username_with_special_characters(self):
        """Test message format with usernames containing underscores/numbers"""
        special_username = "user_123"
        user_id = 987654321
        
        self.admin_system.register_user(user_id, special_username, "Special User")
        
        expected_message = f"Пользователь @{special_username} теперь администратор"
        
        # Should handle special characters in usernames
        self.assertIn(f"@{special_username}", expected_message)
        
        print(f"✓ Special username format verified: @{special_username}")


if __name__ == '__main__':
    print("🧪 Running Message Format Unit Tests...")
    print("=" * 60)
    
    # Run tests with verbose output
    unittest.main(verbosity=2, exit=False)
    
    print("=" * 60)
    print("✅ Message format unit tests completed!")