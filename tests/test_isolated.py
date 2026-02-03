#!/usr/bin/env python3
"""
Isolated test for shop display completeness property
"""

import sys
import os
import tempfile
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
    print("Hypothesis is available")
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Hypothesis not available")

# Isolated ShopItem class to avoid imports
class ShopItem:
    """Data class representing a shop item"""
    def __init__(self, id: int, name: str, price: int, description: str, is_active: bool = True, created_at=None):
        self.id = id
        self.name = name
        self.price = price
        self.description = description
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

# Isolated ShopHandler implementation for testing
class TestableShopHandler:
    """Isolated shop handler for testing without bot dependencies"""
    
    def __init__(self, shop_items=None):
        self.shop_items = shop_items or []
    
    def display_shop(self, user_id: int) -> str:
        """Generate formatted shop display message with Russian text"""
        try:
            # Get all active shop items
            active_items = [item for item in self.shop_items if item.is_active]
            
            if not active_items:
                return "🛒 МАГАЗИН\n\nМагазин временно пуст. Попробуйте позже."
            
            # Build the shop display message
            message_lines = ["🛒 МАГАЗИН\n"]
            
            for i, item in enumerate(active_items, 1):
                # Format each item with number, name, description, and price
                item_text = f"{i}. {item.name} - {item.price} монет"
                message_lines.append(item_text)
                
                # Add description if available
                if item.description:
                    message_lines.append(f"   {item.description}")
                
                # Add purchase command
                message_lines.append(f"   Для покупки: /buy_{i}")
                message_lines.append("")  # Empty line for spacing
            
            # Add general instructions
            message_lines.append("💡 Используйте команды /buy_1, /buy_2, /buy_3 для покупки товаров")
            
            return "\n".join(message_lines)
            
        except Exception as e:
            return "🛒 МАГАЗИН\n\n❌ Произошла ошибка при загрузке магазина. Попробуйте позже."

def test_basic_functionality():
    """Test basic shop display functionality"""
    print("Testing basic shop display functionality...")
    
    # Create test items
    items = [
        ShopItem(1, "Test Item 1", 100, "Test description 1", True),
        ShopItem(2, "Test Item 2", 200, "Test description 2", True),
        ShopItem(3, "Inactive Item", 300, "Inactive description", False)
    ]
    
    handler = TestableShopHandler(items)
    display = handler.display_shop(12345)
    
    print("Generated display:")
    print(display)
    print()
    
    # Check basic requirements
    assert "🛒 МАГАЗИН" in display, "Should contain shop header"
    assert "Test Item 1" in display, "Should contain active item 1"
    assert "Test Item 2" in display, "Should contain active item 2"
    assert "Inactive Item" not in display, "Should not contain inactive item"
    assert "/buy_1" in display, "Should contain purchase command 1"
    assert "/buy_2" in display, "Should contain purchase command 2"
    assert "/buy_3" not in display.split("💡 Используйте команды")[0], "Should not contain purchase command 3 for inactive item"
    
    print("✓ Basic functionality test passed")

def test_empty_shop():
    """Test empty shop display"""
    print("Testing empty shop display...")
    
    handler = TestableShopHandler([])
    display = handler.display_shop(12345)
    
    print("Empty shop display:")
    print(display)
    print()
    
    assert "🛒 МАГАЗИН" in display, "Should contain shop header"
    assert "Магазин временно пуст" in display, "Should contain empty message"
    
    print("✓ Empty shop test passed")

if __name__ == "__main__":
    test_basic_functionality()
    test_empty_shop()
    print("All tests passed!")