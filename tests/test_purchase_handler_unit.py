"""
Unit tests for PurchaseHandler class
Tests balance validation, deduction logic, and purchase processing
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.purchase_handler import PurchaseHandler
from core.shop_models import PurchaseResult, ShopItem, User


class TestPurchaseHandler(unittest.TestCase):
    """Test cases for PurchaseHandler"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock database manager
        self.mock_db = Mock()
        self.handler = PurchaseHandler(self.mock_db)
        
        # Sample test data
        self.test_user = User(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            balance=200,
            is_admin=False
        )
        
        self.test_items = [
            ShopItem(id=1, name="Безлимитные стикеры на 24 часа", price=100, description="Test item 1"),
            ShopItem(id=2, name="Запрос на админ-права", price=100, description="Test item 2"),
            ShopItem(id=3, name="Рассылка сообщения всем пользователям", price=100, description="Test item 3")
        ]
    
    def test_validate_balance_sufficient(self):
        """Test balance validation with sufficient balance"""
        result = self.handler.validate_balance(self.test_user, 100)
        self.assertTrue(result)
    
    def test_validate_balance_insufficient(self):
        """Test balance validation with insufficient balance"""
        result = self.handler.validate_balance(self.test_user, 300)
        self.assertFalse(result)
    
    def test_validate_balance_exact(self):
        """Test balance validation with exact balance"""
        result = self.handler.validate_balance(self.test_user, 200)
        self.assertTrue(result)
    
    def test_deduct_balance_success(self):
        """Test successful balance deduction"""
        self.mock_db.update_user_balance.return_value = None
        
        result = self.handler.deduct_balance(self.test_user, 100)
        self.assertEqual(result, 100)  # 200 - 100 = 100
        self.mock_db.update_user_balance.assert_called_once_with(1, 100)
    
    def test_deduct_balance_insufficient(self):
        """Test balance deduction with insufficient funds"""
        result = self.handler.deduct_balance(self.test_user, 300)
        self.assertIsNone(result)
    
    def test_get_purchase_commands_info(self):
        """Test getting purchase commands information"""
        self.mock_db.get_shop_items.return_value = self.test_items
        
        commands = self.handler.get_purchase_commands_info()
        
        expected_commands = ["/buy_1", "/buy_2", "/buy_3"]
        self.assertEqual(len(commands), 3)
        
        for cmd in expected_commands:
            self.assertIn(cmd, commands)
        
        # Check first command details
        self.assertEqual(commands["/buy_1"]["item_name"], "Безлимитные стикеры на 24 часа")
        self.assertEqual(commands["/buy_1"]["price"], 100)
    
    def test_process_buy_command_valid(self):
        """Test processing valid buy command"""
        self.mock_db.get_user_by_telegram_id.return_value = self.test_user
        self.mock_db.get_shop_items.return_value = self.test_items
        self.mock_db.update_user_balance.return_value = None
        self.mock_db.create_purchase.return_value = 123
        self.mock_db.add_transaction.return_value = None
        
        result = self.handler.process_buy_command(12345, "/buy_1")
        
        self.assertTrue(result.success)
        self.assertEqual(result.new_balance, 100)
        self.assertEqual(result.purchase_id, 123)
    
    def test_process_buy_command_invalid_format(self):
        """Test processing invalid buy command format"""
        result = self.handler.process_buy_command(12345, "/invalid")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_command")
    
    def test_process_buy_command_invalid_number(self):
        """Test processing buy command with invalid item number"""
        result = self.handler.process_buy_command(12345, "/buy_abc")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_item_number")
    
    def test_validate_purchase_request_success(self):
        """Test successful purchase request validation"""
        self.mock_db.get_user_by_telegram_id.return_value = self.test_user
        self.mock_db.get_shop_items.return_value = self.test_items
        
        validation = self.handler.validate_purchase_request(12345, 1)
        
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["user"], self.test_user)
        self.assertEqual(validation["item"], self.test_items[0])
    
    def test_validate_purchase_request_user_not_found(self):
        """Test purchase request validation with user not found"""
        self.mock_db.get_user_by_telegram_id.return_value = None
        
        validation = self.handler.validate_purchase_request(12345, 1)
        
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["error"], "user_not_found")
    
    def test_validate_purchase_request_item_not_found(self):
        """Test purchase request validation with item not found"""
        self.mock_db.get_user_by_telegram_id.return_value = self.test_user
        self.mock_db.get_shop_items.return_value = self.test_items
        
        validation = self.handler.validate_purchase_request(12345, 5)  # Invalid item number
        
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["error"], "item_not_found")
    
    def test_validate_purchase_request_insufficient_balance(self):
        """Test purchase request validation with insufficient balance"""
        poor_user = User(
            id=2,
            telegram_id=54321,
            username="pooruser",
            first_name="Poor",
            balance=50,  # Less than required 100
            is_admin=False
        )
        
        self.mock_db.get_user_by_telegram_id.return_value = poor_user
        self.mock_db.get_shop_items.return_value = self.test_items
        
        validation = self.handler.validate_purchase_request(54321, 1)
        
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["error"], "insufficient_balance")
        self.assertEqual(validation["current_balance"], 50)
        self.assertEqual(validation["required"], 100)


if __name__ == '__main__':
    unittest.main()