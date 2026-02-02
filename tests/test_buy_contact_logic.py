#!/usr/bin/env python3
"""
Simple logic tests for buy_contact functionality without telegram dependencies
Tests the core business logic for Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import unittest
import sys
import os
import sqlite3
import tempfile

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SimpleBuyContactLogic:
    """Simplified version of buy_contact logic for testing"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Initialize test database tables"""
        conn = sqlite3.connect(self.db_path)
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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def register_user(self, user_id, username, first_name, balance=0):
        """Register a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO users (id, username, first_name, balance) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, balance)
        )
        
        conn.commit()
        conn.close()
    
    def get_user_balance(self, user_id):
        """Get user balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def update_balance(self, user_id, amount):
        """Update user balance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        new_balance = result[0] + amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        
        conn.commit()
        conn.close()
        
        return new_balance
    
    def add_transaction(self, user_id, amount, transaction_type):
        """Add transaction record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
            (user_id, amount, transaction_type)
        )
        
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return transaction_id
    
    def get_admins(self):
        """Get all admin user IDs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE is_admin = TRUE")
        admin_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return admin_ids
    
    def set_admin(self, user_id, is_admin=True):
        """Set user admin status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
        
        conn.commit()
        conn.close()
    
    def buy_contact(self, user_id, username):
        """Core buy_contact logic"""
        required_amount = 10
        
        # Check balance
        current_balance = self.get_user_balance(user_id)
        if current_balance is None:
            return {"success": False, "error": "User not found"}
        
        if current_balance < required_amount:
            return {
                "success": False, 
                "error": f"Insufficient balance. Required: {required_amount}, have: {int(current_balance)}"
            }
        
        # Update balance
        new_balance = self.update_balance(user_id, -required_amount)
        if new_balance is None:
            return {"success": False, "error": "Failed to update balance"}
        
        # Create transaction
        transaction_id = self.add_transaction(user_id, -required_amount, 'buy')
        
        # Get admin list for notifications
        admin_ids = self.get_admins()
        
        # Format messages
        user_message = "Вы купили контакт. Администратор свяжется с вами."
        username_display = f"@{username}" if username else f"#{user_id}"
        admin_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
        
        return {
            "success": True,
            "new_balance": new_balance,
            "transaction_id": transaction_id,
            "user_message": user_message,
            "admin_message": admin_message,
            "admin_ids": admin_ids
        }


class TestBuyContactLogic(unittest.TestCase):
    """Test cases for buy_contact core logic"""
    
    def setUp(self):
        """Set up test database"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.logic = SimpleBuyContactLogic(self.db_path)
        
        # Create test users
        self.logic.register_user(123456, "testuser", "Test User", 50)
        self.logic.register_user(789012, "admin_user", "Admin User", 100)
        self.logic.set_admin(789012, True)
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_successful_purchase(self):
        """Test successful purchase with sufficient balance - Requirements 5.1, 5.2, 5.3, 5.4"""
        result = self.logic.buy_contact(123456, "testuser")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["new_balance"], 40)  # 50 - 10
        self.assertIsNotNone(result["transaction_id"])
        self.assertEqual(result["user_message"], "Вы купили контакт. Администратор свяжется с вами.")
    
    def test_insufficient_balance(self):
        """Test insufficient balance error - Requirements 5.6"""
        # Create user with low balance
        self.logic.register_user(111111, "pooruser", "Poor User", 5)
        
        result = self.logic.buy_contact(111111, "pooruser")
        
        self.assertFalse(result["success"])
        self.assertIn("Insufficient balance", result["error"])
        self.assertIn("Required: 10", result["error"])
        self.assertIn("have: 5", result["error"])
    
    def test_admin_notification_format(self):
        """Test admin notification message format - Requirements 5.5"""
        result = self.logic.buy_contact(123456, "testuser")
        
        expected_message = "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        self.assertEqual(result["admin_message"], expected_message)
    
    def test_transaction_logging(self):
        """Test transaction is properly logged - Requirements 5.3"""
        result = self.logic.buy_contact(123456, "testuser")
        
        self.assertTrue(result["success"])
        
        # Verify transaction was created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, amount, type FROM transactions WHERE id = ?",
            (result["transaction_id"],)
        )
        transaction = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction[0], 123456)  # user_id
        self.assertEqual(transaction[1], -10)     # amount
        self.assertEqual(transaction[2], 'buy')   # type
    
    def test_balance_validation(self):
        """Test balance validation logic - Requirements 5.1, 5.2"""
        # Test sufficient balance
        balance_50 = self.logic.get_user_balance(123456)
        self.assertTrue(balance_50 >= 10)
        
        # Test insufficient balance
        self.logic.register_user(222222, "lowuser", "Low User", 3)
        balance_3 = self.logic.get_user_balance(222222)
        self.assertFalse(balance_3 >= 10)
    
    def test_user_confirmation_message(self):
        """Test user confirmation message format - Requirements 5.4"""
        result = self.logic.buy_contact(123456, "testuser")
        
        expected_message = "Вы купили контакт. Администратор свяжется с вами."
        self.assertEqual(result["user_message"], expected_message)
    
    def test_admin_list_retrieval(self):
        """Test admin notification list - Requirements 5.5"""
        result = self.logic.buy_contact(123456, "testuser")
        
        self.assertTrue(result["success"])
        self.assertIn(789012, result["admin_ids"])  # Our test admin
        self.assertEqual(len(result["admin_ids"]), 1)


if __name__ == '__main__':
    unittest.main()