#!/usr/bin/env python3
"""
Test for updated /balance command integration with new admin system
"""

import unittest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem
from telegram import Update, User, Message, Chat


class TestBalanceCommandUpdate(unittest.TestCase):
    """Test the updated /balance command with new admin system integration"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test user
        self.test_user_id = 123456789
        self.test_username = "testuser"
        self.test_first_name = "Test User"
        
        # Register test user
        self.admin_system.register_user(
            self.test_user_id, 
            self.test_username, 
            self.test_first_name
        )
        
        # Set initial balance
        self.admin_system.update_balance(self.test_user_id, 100.0)
    
    def tearDown(self):
        """Clean up test environment"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_get_user_by_id_function(self):
        """Test the new get_user_by_id function in AdminSystem"""
        user = self.admin_system.get_user_by_id(self.test_user_id)
        
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], self.test_user_id)
        self.assertEqual(user['username'], self.test_username)
        self.assertEqual(user['first_name'], self.test_first_name)
        self.assertEqual(user['balance'], 100.0)
        self.assertFalse(user['is_admin'])
    
    def test_get_user_by_id_nonexistent(self):
        """Test get_user_by_id with non-existent user"""
        user = self.admin_system.get_user_by_id(999999999)
        self.assertIsNone(user)
    
    def test_balance_display_format(self):
        """Test that balance is displayed correctly from admin system"""
        user = self.admin_system.get_user_by_id(self.test_user_id)
        
        # Verify the balance format matches expected output
        expected_balance = 100.0
        self.assertEqual(user['balance'], expected_balance)
        
        # Test admin status display
        self.assertFalse(user['is_admin'])
        
        # Set user as admin and test
        self.admin_system.set_admin_status(self.test_user_id, True)
        admin_user = self.admin_system.get_user_by_id(self.test_user_id)
        self.assertTrue(admin_user['is_admin'])
    
    def test_balance_update_integration(self):
        """Test that balance updates work correctly"""
        # Add points
        new_balance = self.admin_system.update_balance(self.test_user_id, 50.0)
        self.assertEqual(new_balance, 150.0)
        
        # Verify in database
        user = self.admin_system.get_user_by_id(self.test_user_id)
        self.assertEqual(user['balance'], 150.0)
        
        # Subtract points
        new_balance = self.admin_system.update_balance(self.test_user_id, -25.0)
        self.assertEqual(new_balance, 125.0)
        
        # Verify in database
        user = self.admin_system.get_user_by_id(self.test_user_id)
        self.assertEqual(user['balance'], 125.0)
    
    def test_balance_command_logic_flow(self):
        """Test the logic flow of the updated balance command"""
        # Mock the bot's balance command logic
        
        # 1. User exists in admin system - should use admin system balance
        user = self.admin_system.get_user_by_id(self.test_user_id)
        self.assertIsNotNone(user)
        
        # Simulate balance command response format
        balance_text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {user['first_name'] or 'Неизвестно'}
[BALANCE] Баланс: {user['balance']} очков
[STATUS] Статус: {'Администратор' if user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
        """
        
        # Verify the format contains expected elements
        self.assertIn("Test User", balance_text)
        self.assertIn("100.0 очков", balance_text)
        self.assertIn("Пользователь", balance_text)
        
        # Test admin status display
        self.admin_system.set_admin_status(self.test_user_id, True)
        admin_user = self.admin_system.get_user_by_id(self.test_user_id)
        
        admin_balance_text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {admin_user['first_name'] or 'Неизвестно'}
[BALANCE] Баланс: {admin_user['balance']} очков
[STATUS] Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
        """
        
        self.assertIn("Администратор", admin_balance_text)


if __name__ == '__main__':
    unittest.main()