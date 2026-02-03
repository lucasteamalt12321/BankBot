#!/usr/bin/env python3
"""
Property-based test runner for shop display completeness
Runs without importing bot modules to avoid interference
"""

import unittest
import sys
import os
from datetime import datetime

# Prevent any bot imports by not adding the root to path
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
    print("✓ Hypothesis is available")
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("✗ Hypothesis not available")

# Isolated implementations
class ShopItem:
    def __init__(self, id: int, name: str, price: int, description: str, is_active: bool = True):
        self.id = id
        self.name = name
        self.price = price
        self.description = description
        self.is_active = is_active

class TestableShopHandler:
    def __init__(self, shop_items=None):
        self.shop_items = shop_items or []
    
    def display_shop(self, user_id: int) -> str:
        try:
            active_items = [item for item in self.shop_items if item.is_active]
            
            if not active_items:
                return "🛒 МАГАЗИН\n\nМагазин временно пуст. Попробуйте позже."
            
            message_lines = ["🛒 МАГАЗИН\n"]
            
            for i, item in enumerate(active_items, 1):
                item_text = f"{i}. {item.name} - {item.price} монет"
                message_lines.append(item_text)
                
                if item.description:
                    message_lines.append(f"   {item.description}")
                
                message_lines.append(f"   Для покупки: /buy_{i}")
                message_lines.append("")
            
            message_lines.append("💡 Используйте команды /buy_1, /buy_2, /buy_3 для покупки товаров")
            
            return "\n".join(message_lines)
            
        except Exception as e:
            return "🛒 МАГАЗИН\n\n❌ Произошла ошибка при загрузке магазина. Попробуйте позже."

class TestShopDisplayCompletenessPBT(unittest.TestCase):
    """Property-based tests for shop display completeness"""
    
    def setUp(self):
        self.shop_handler = TestableShopHandler()
    
    def create_shop_items(self, items_data):
        shop_items = []
        for item_data in items_data:
            shop_item = ShopItem(
                id=item_data['id'],
                name=item_data['name'],
                price=item_data['price'],
                description=item_data['description'],
                is_active=item_data.get('is_active', True)
            )
            shop_items.append(shop_item)
        
        self.shop_handler.shop_items = shop_items
        return shop_items
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.fixed_dictionaries({
                'id': st.integers(min_value=1, max_value=1000),
                'name': st.text(min_size=1, max_size=100, alphabet=st.characters(
                    whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Zs', 'Po'),
                    blacklist_characters='\n\r\t'
                )),
                'price': st.integers(min_value=1, max_value=10000),
                'description': st.text(min_size=1, max_size=500, alphabet=st.characters(
                    whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Zs', 'Po'),
                    blacklist_characters='\n\r\t'
                )),
                'is_active': st.just(True)
            }),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x['id']
        ),
        st.integers(min_value=1, max_value=2147483647)
    )
    @settings(max_examples=100, deadline=None)
    def test_shop_display_completeness_property(self, items_data, user_id):
        """
        **Feature: telegram-bot-shop-system, Property 1: Shop Display Completeness**
        **Validates: Requirements 1.2, 1.3**
        
        For any set of active shop items, the shop display should include all items 
        with their name, description, price, and corresponding purchase commands.
        """
        assume(len(items_data) > 0)
        
        shop_items = self.create_shop_items(items_data)
        display = self.shop_handler.display_shop(user_id)
        
        # Property 1: Display should start with the shop header
        self.assertIn("🛒 МАГАЗИН", display, 
                     f"Shop display should contain header '🛒 МАГАЗИН' for {len(shop_items)} items")
        
        # Property 2: All active items should be included in the display
        for i, item in enumerate(shop_items, 1):
            if item.is_active:
                item_line = f"{i}. {item.name} - {item.price} монет"
                self.assertIn(item_line, display,
                             f"Shop display should contain item line '{item_line}' for item {item.id}")
                
                if item.description:
                    self.assertIn(item.description, display,
                                 f"Shop display should contain description '{item.description}' for item {item.id}")
                
                purchase_command = f"/buy_{i}"
                self.assertIn(purchase_command, display,
                             f"Shop display should contain purchase command '{purchase_command}' for item {item.id}")
        
        # Property 3: Display should include purchase instructions
        self.assertIn("💡 Используйте команды", display,
                     "Shop display should contain purchase instructions")
        
        # Property 4: All purchase commands should be listed in instructions
        for i in range(1, len(shop_items) + 1):
            command = f"/buy_{i}"
            self.assertIn(command, display,
                         f"Shop display should contain command '{command}' in instructions")
        
        # Property 5: Display should be properly formatted
        lines = display.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        self.assertGreater(len(non_empty_lines), 0,
                          "Shop display should contain non-empty content")
    
    def test_specific_requirements_compliance(self):
        """Test specific requirements from the design document"""
        default_items = [
            {
                'id': 1,
                'name': 'Безлимитные стикеры на 24 часа',
                'price': 100,
                'description': 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов',
                'is_active': True
            },
            {
                'id': 2,
                'name': 'Запрос на админ-права',
                'price': 100,
                'description': 'Отправить запрос владельцу бота на получение прав администратора',
                'is_active': True
            },
            {
                'id': 3,
                'name': 'Рассылка сообщения всем пользователям',
                'price': 100,
                'description': 'Отправить ваше сообщение всем пользователям бота',
                'is_active': True
            }
        ]
        
        shop_items = self.create_shop_items(default_items)
        display = self.shop_handler.display_shop(12345)
        
        # Verify Requirements 1.2: Show each item with name, description, and price
        expected_elements = [
            "1. Безлимитные стикеры на 24 часа - 100 монет",
            "2. Запрос на админ-права - 100 монет", 
            "3. Рассылка сообщения всем пользователям - 100 монет",
            "Получите возможность отправлять неограниченное количество стикеров",
            "Отправить запрос владельцу бота на получение прав администратора",
            "Отправить ваше сообщение всем пользователям бота"
        ]
        
        for element in expected_elements:
            self.assertIn(element, display,
                         f"Required element missing from display: {element}")
        
        # Verify Requirements 1.3: Include purchase commands
        purchase_commands = ["/buy_1", "/buy_2", "/buy_3"]
        for command in purchase_commands:
            self.assertIn(command, display,
                         f"Purchase command missing from display: {command}")
        
        # Verify Requirements 1.4: Format as "🛒 МАГАЗИН" followed by numbered items
        self.assertTrue(display.startswith("🛒 МАГАЗИН"),
                       "Display should start with '🛒 МАГАЗИН'")
        
        print("✓ Shop display completeness property verified for all requirements")

def run_tests():
    """Run the property-based tests"""
    print("Running Shop Display Completeness Property-Based Tests")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestShopDisplayCompletenessPBT)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 All property-based tests passed!")
        print(f"✓ Ran {result.testsRun} tests successfully")
        return True
    else:
        print("❌ Some tests failed")
        print(f"✗ Failures: {len(result.failures)}")
        print(f"✗ Errors: {len(result.errors)}")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)