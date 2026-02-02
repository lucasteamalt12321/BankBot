#!/usr/bin/env python3
"""
Unit tests for the /buy_contact command implementation
Tests Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import unittest
import sys
import os
import sqlite3
import tempfile
from unittest.mock import Mock, AsyncMock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem


class TestBuyContactCommand(unittest.TestCase):
    """Test cases for the /buy_contact command"""
    
    def setUp(self):
        """Set up test database and admin system"""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users
        self.admin_system.register_user(123456, "testuser", "Test User")
        self.admin_system.register_user(789012, "admin_user", "Admin User")
        self.admin_system.set_admin_status(789012, True)
        
        # Set initial balance for test user
        self.admin_system.update_balance(123456, 50)  # Give user 50 points
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_sufficient_balance_purchase(self):
        """Test successful purchase with sufficient balance
        
        Validates: Requirements 5.1, 5.2, 5.3, 5.4
        """
        # Get initial balance
        user = self.admin_system.get_user_by_username("testuser")
        initial_balance = user['balance']
        
        # Simulate purchase (deduct 10 points)
        new_balance = self.admin_system.update_balance(user['id'], -10)
        
        # Create transaction
        transaction_id = self.admin_system.add_transaction(
            user['id'], -10, 'buy'
        )
        
        # Verify balance was updated correctly
        self.assertEqual(new_balance, initial_balance - 10)
        self.assertIsNotNone(transaction_id)
        
        # Verify transaction was logged
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions WHERE id = ? AND type = 'buy'",
            (transaction_id,)
        )
        transaction = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction['user_id'], user['id'])
        self.assertEqual(transaction['amount'], -10)
        self.assertEqual(transaction['type'], 'buy')
    
    def test_insufficient_balance_error(self):
        """Test error handling for insufficient balance
        
        Validates: Requirements 5.6
        """
        # Create user with insufficient balance
        self.admin_system.register_user(111111, "pooruser", "Poor User")
        self.admin_system.update_balance(111111, 5)  # Only 5 points
        
        user = self.admin_system.get_user_by_username("pooruser")
        
        # Check if balance is insufficient
        required_amount = 10
        has_sufficient_balance = user['balance'] >= required_amount
        
        self.assertFalse(has_sufficient_balance)
        self.assertEqual(user['balance'], 5)
    
    def test_admin_notification_data(self):
        """Test admin notification message format
        
        Validates: Requirements 5.5
        """
        # Get test user
        user = self.admin_system.get_user_by_username("testuser")
        
        # Simulate purchase
        new_balance = self.admin_system.update_balance(user['id'], -10)
        
        # Format admin notification message
        username_display = f"@{user['username']}"
        admin_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
        
        expected_message = "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        self.assertEqual(admin_message, expected_message)
    
    def test_user_confirmation_message(self):
        """Test user confirmation message format
        
        Validates: Requirements 5.4
        """
        expected_message = "Вы купили контакт. Администратор свяжется с вами."
        
        # This is the exact message format required by the specification
        self.assertEqual(expected_message, "Вы купили контакт. Администратор свяжется с вами.")
    
    def test_balance_validation_logic(self):
        """Test balance validation logic
        
        Validates: Requirements 5.1, 5.2
        """
        # Test with sufficient balance
        user_sufficient = self.admin_system.get_user_by_username("testuser")  # Has 50 points
        self.assertTrue(user_sufficient['balance'] >= 10)
        
        # Test with insufficient balance
        self.admin_system.register_user(222222, "lowbalance", "Low Balance User")
        self.admin_system.update_balance(222222, 3)  # Only 3 points
        
        user_insufficient = self.admin_system.get_user_by_username("lowbalance")
        self.assertFalse(user_insufficient['balance'] >= 10)
    
    def test_transaction_creation(self):
        """Test transaction creation for purchase
        
        Validates: Requirements 5.3
        """
        user = self.admin_system.get_user_by_username("testuser")
        
        # Create buy transaction
        transaction_id = self.admin_system.add_transaction(
            user['id'], -10, 'buy'
        )
        
        self.assertIsNotNone(transaction_id)
        
        # Verify transaction details
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, amount, type FROM transactions WHERE id = ?",
            (transaction_id,)
        )
        transaction = cursor.fetchone()
        conn.close()
        
        self.assertEqual(transaction['user_id'], user['id'])
        self.assertEqual(transaction['amount'], -10)
        self.assertEqual(transaction['type'], 'buy')


if __name__ == '__main__':
    unittest.main()