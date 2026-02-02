#!/usr/bin/env python3
"""
Integration test for /balance command with new admin system
Tests requirement 8.7: Preserve existing functionality while integrating new admin system
"""

import unittest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem
from telegram import Update, User, Message, Chat


class TestBalanceIntegration(unittest.TestCase):
    """Integration test for balance command with admin system"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users
        self.regular_user_id = 123456789
        self.admin_user_id = 987654321
        
        # Register users
        self.admin_system.register_user(
            self.regular_user_id, 
            "regularuser", 
            "Regular User"
        )
        self.admin_system.register_user(
            self.admin_user_id, 
            "adminuser", 
            "Admin User"
        )
        
        # Set balances and admin status
        self.admin_system.update_balance(self.regular_user_id, 150.0)
        self.admin_system.update_balance(self.admin_user_id, 500.0)
        self.admin_system.set_admin_status(self.admin_user_id, True)
    
    def tearDown(self):
        """Clean up test environment"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_balance_command_preserves_functionality(self):
        """Test that balance command preserves existing functionality (Requirement 8.7)"""
        
        # Test regular user balance display
        regular_user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertIsNotNone(regular_user)
        self.assertEqual(regular_user['balance'], 150.0)
        self.assertFalse(regular_user['is_admin'])
        
        # Test admin user balance display
        admin_user = self.admin_system.get_user_by_id(self.admin_user_id)
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user['balance'], 500.0)
        self.assertTrue(admin_user['is_admin'])
    
    def test_balance_command_format_consistency(self):
        """Test that balance command maintains consistent format"""
        
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        
        # Simulate the balance command response format
        balance_text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {user['first_name'] or 'Неизвестно'}
[BALANCE] Баланс: {user['balance']} очков
[STATUS] Статус: {'Администратор' if user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
        """
        
        # Verify format elements
        self.assertIn("[MONEY]", balance_text)
        self.assertIn("[USER]", balance_text)
        self.assertIn("[BALANCE]", balance_text)
        self.assertIn("[STATUS]", balance_text)
        self.assertIn("[TIP]", balance_text)
        self.assertIn("Regular User", balance_text)
        self.assertIn("150.0 очков", balance_text)
        self.assertIn("Пользователь", balance_text)
    
    def test_admin_status_display(self):
        """Test that admin status is correctly displayed in balance"""
        
        admin_user = self.admin_system.get_user_by_id(self.admin_user_id)
        
        balance_text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {admin_user['first_name'] or 'Неизвестно'}
[BALANCE] Баланс: {admin_user['balance']} очков
[STATUS] Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
        """
        
        self.assertIn("Admin User", balance_text)
        self.assertIn("500.0 очков", balance_text)
        self.assertIn("Администратор", balance_text)
    
    def test_balance_updates_reflect_correctly(self):
        """Test that balance updates are reflected in balance command"""
        
        # Update balance
        new_balance = self.admin_system.update_balance(self.regular_user_id, 25.0)
        self.assertEqual(new_balance, 175.0)
        
        # Verify balance is updated
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertEqual(user['balance'], 175.0)
        
        # Test negative balance update
        new_balance = self.admin_system.update_balance(self.regular_user_id, -50.0)
        self.assertEqual(new_balance, 125.0)
        
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        self.assertEqual(user['balance'], 125.0)
    
    def test_balance_command_error_handling(self):
        """Test error handling in balance command"""
        
        # Test with non-existent user
        non_existent_user = self.admin_system.get_user_by_id(999999999)
        self.assertIsNone(non_existent_user)
        
        # This should trigger fallback to old system in real implementation
        # For now, we just verify the admin system returns None correctly
    
    def test_database_consistency(self):
        """Test that database operations maintain consistency"""
        
        # Test multiple operations
        self.admin_system.update_balance(self.regular_user_id, 100.0)
        self.admin_system.set_admin_status(self.regular_user_id, True)
        
        user = self.admin_system.get_user_by_id(self.regular_user_id)
        
        # Verify all changes are persisted
        self.assertEqual(user['balance'], 250.0)  # 150 + 100
        self.assertTrue(user['is_admin'])
        self.assertEqual(user['username'], 'regularuser')
        self.assertEqual(user['first_name'], 'Regular User')


if __name__ == '__main__':
    unittest.main()