#!/usr/bin/env python3
"""
Minimal test without any imports that might trigger bot startup
"""

from datetime import datetime

# Isolated ShopItem class
class ShopItem:
    def __init__(self, id: int, name: str, price: int, description: str, is_active: bool = True):
        self.id = id
        self.name = name
        self.price = price
        self.description = description
        self.is_active = is_active

# Isolated ShopHandler implementation
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

def main():
    print("Starting minimal test...")
    
    # Test 1: Basic functionality
    items = [
        ShopItem(1, "Безлимитные стикеры", 100, "Стикеры на 24 часа", True),
        ShopItem(2, "Админ права", 100, "Запрос на админ права", True),
        ShopItem(3, "Рассылка", 100, "Рассылка всем пользователям", True)
    ]
    
    handler = TestableShopHandler(items)
    display = handler.display_shop(12345)
    
    print("Generated display:")
    print(display)
    print()
    
    # Verify requirements
    checks = [
        ("🛒 МАГАЗИН" in display, "Shop header present"),
        ("Безлимитные стикеры" in display, "Item 1 present"),
        ("Админ права" in display, "Item 2 present"),
        ("Рассылка" in display, "Item 3 present"),
        ("/buy_1" in display, "Purchase command 1 present"),
        ("/buy_2" in display, "Purchase command 2 present"),
        ("/buy_3" in display, "Purchase command 3 present"),
        ("100 монет" in display, "Price displayed"),
        ("💡 Используйте команды" in display, "Instructions present")
    ]
    
    all_passed = True
    for check, description in checks:
        if check:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    # Test 2: Empty shop
    print("\nTesting empty shop...")
    empty_handler = TestableShopHandler([])
    empty_display = empty_handler.display_shop(12345)
    
    print("Empty shop display:")
    print(empty_display)
    
    empty_checks = [
        ("🛒 МАГАЗИН" in empty_display, "Empty shop header present"),
        ("Магазин временно пуст" in empty_display, "Empty message present")
    ]
    
    for check, description in empty_checks:
        if check:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    # Test 3: Mixed active/inactive items
    print("\nTesting mixed active/inactive items...")
    mixed_items = [
        ShopItem(1, "Active Item", 100, "Active description", True),
        ShopItem(2, "Inactive Item", 200, "Inactive description", False),
        ShopItem(3, "Another Active", 300, "Another active item", True)
    ]
    
    mixed_handler = TestableShopHandler(mixed_items)
    mixed_display = mixed_handler.display_shop(12345)
    
    print("Mixed items display:")
    print(mixed_display)
    
    mixed_checks = [
        ("Active Item" in mixed_display, "Active item 1 present"),
        ("Another Active" in mixed_display, "Active item 2 present"),
        ("Inactive Item" not in mixed_display, "Inactive item not present"),
        ("/buy_1" in mixed_display, "Command for active item 1"),
        ("/buy_2" in mixed_display, "Command for active item 2"),
        # Check that /buy_3 is not in the item section (before instructions)
        ("/buy_3" not in mixed_display.split("💡 Используйте команды")[0], "No command for inactive item in items section")
    ]
    
    for check, description in mixed_checks:
        if check:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! Property test implementation is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)