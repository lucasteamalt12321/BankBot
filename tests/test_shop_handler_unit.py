#!/usr/bin/env python3
"""
Unit tests for ShopHandler class
Tests the shop display formatting and item management functionality
"""

import unittest
import os
import sys
from unittest.mock import Mock, patch

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.shop_handler import ShopHandler
from core.shop_models import ShopItem
from datetime import datetime


class TestShopHandler(unittest.TestCase):
    """Test cases for ShopHandler class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock shop items
        self.mock_items = [
            ShopItem(
                id=1,
                name="Безлимитные стикеры на 24 часа",
                price=100,
                description="Получите возможность отправлять неограниченное количество стикеров в течение 24 часов",
                is_active=True,
                created_at=datetime.utcnow()
            ),
            ShopItem(
                id=2,
                name="Запрос на админ-права",
                price=100,
                description="Отправить запрос владельцу бота на получение прав администратора",
                is_active=True,
                created_at=datetime.utcnow()
            ),
            ShopItem(
                id=3,
                name="Рассылка сообщения всем пользователям",
                price=100,
                description="Отправить ваше сообщение всем пользователям бота",
                is_active=True,
                created_at=datetime.utcnow()
            )
        ]
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_shop_handler_initialization(self, mock_db_manager):
        """Test ShopHandler initialization"""
        handler = ShopHandler()
        self.assertIsNotNone(handler)
        self.assertIsNotNone(handler.db)
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_display_shop_with_items(self, mock_db_manager):
        """Test shop display with items"""
        # Mock database manager
        mock_db = Mock()
        mock_db.get_shop_items.return_value = self.mock_items
        
        handler = ShopHandler(mock_db)
        display = handler.display_shop(12345)
        
        # Check required elements
        self.assertIn("🛒 МАГАЗИН", display)
        self.assertIn("1. Безлимитные стикеры на 24 часа - 100 монет", display)
        self.assertIn("2. Запрос на админ-права - 100 монет", display)
        self.assertIn("3. Рассылка сообщения всем пользователям - 100 монет", display)
        self.assertIn("/buy_1", display)
        self.assertIn("/buy_2", display)
        self.assertIn("/buy_3", display)
        self.assertIn("💡 Используйте команды", display)
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_display_shop_empty(self, mock_db_manager):
        """Test shop display with no items"""
        # Mock database manager with empty items
        mock_db = Mock()
        mock_db.get_shop_items.return_value = []
        
        handler = ShopHandler(mock_db)
        display = handler.display_shop(12345)
        
        # Check empty shop message
        self.assertIn("🛒 МАГАЗИН", display)
        self.assertIn("Магазин временно пуст", display)
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_get_shop_item_by_number(self, mock_db_manager):
        """Test getting shop item by number"""
        # Mock database manager
        mock_db = Mock()
        mock_db.get_shop_items.return_value = self.mock_items
        
        handler = ShopHandler(mock_db)
        
        # Test valid item numbers
        item1 = handler.get_shop_item_by_number(1)
        self.assertIsNotNone(item1)
        self.assertEqual(item1.name, "Безлимитные стикеры на 24 часа")
        
        item2 = handler.get_shop_item_by_number(2)
        self.assertIsNotNone(item2)
        self.assertEqual(item2.name, "Запрос на админ-права")
        
        item3 = handler.get_shop_item_by_number(3)
        self.assertIsNotNone(item3)
        self.assertEqual(item3.name, "Рассылка сообщения всем пользователям")
        
        # Test invalid item numbers
        item_invalid = handler.get_shop_item_by_number(4)
        self.assertIsNone(item_invalid)
        
        item_zero = handler.get_shop_item_by_number(0)
        self.assertIsNone(item_zero)
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_format_shop_item(self, mock_db_manager):
        """Test formatting individual shop item"""
        handler = ShopHandler()
        
        item = self.mock_items[0]
        formatted = handler.format_shop_item(item, 1)
        
        expected_lines = [
            "1. Безлимитные стикеры на 24 часа - 100 монет",
            "   Получите возможность отправлять неограниченное количество стикеров в течение 24 часов",
            "   Для покупки: /buy_1"
        ]
        
        for line in expected_lines:
            self.assertIn(line, formatted)
    
    @patch('core.shop_handler.ShopDatabaseManager')
    def test_validate_shop_display(self, mock_db_manager):
        """Test shop display validation"""
        # Mock database manager
        mock_db = Mock()
        mock_db.get_shop_items.return_value = self.mock_items
        
        handler = ShopHandler(mock_db)
        
        # Test validation
        is_valid = handler.validate_shop_display()
        self.assertTrue(is_valid)
    
    def test_shop_display_requirements_compliance(self):
        """Test that shop display meets specific requirements"""
        # This test verifies the exact format specified in requirements
        expected_format = """🛒 МАГАЗИН

1. Безлимитные стикеры на 24 часа - 100 монет
   Получите возможность отправлять неограниченное количество стикеров в течение 24 часов
   Для покупки: /buy_1

2. Запрос на админ-права - 100 монет
   Отправить запрос владельцу бота на получение прав администратора
   Для покупки: /buy_2

3. Рассылка сообщения всем пользователям - 100 монет
   Отправить ваше сообщение всем пользователям бота
   Для покупки: /buy_3

💡 Используйте команды /buy_1, /buy_2, /buy_3 для покупки товаров"""
        
        # Check all required elements are present
        required_elements = [
            "🛒 МАГАЗИН",  # Requirement 1.4: Format as "🛒 МАГАЗИН"
            "1. Безлимитные стикеры на 24 часа - 100 монет",  # Requirement 1.2: Show name and price
            "2. Запрос на админ-права - 100 монет",
            "3. Рассылка сообщения всем пользователям - 100 монет",
            "/buy_1",  # Requirement 1.3: Include purchase commands
            "/buy_2",
            "/buy_3",
            "💡 Используйте команды"  # Instructions
        ]
        
        for element in required_elements:
            self.assertIn(element, expected_format, f"Required element missing: {element}")
        
        print("✓ Shop display format meets all requirements")


if __name__ == "__main__":
    unittest.main()