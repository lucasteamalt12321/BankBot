#!/usr/bin/env python3
"""
Test script for PurchaseHandler implementation
"""

import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_purchase_handler_import():
    """Test that PurchaseHandler can be imported"""
    try:
        from core.purchase_handler import PurchaseHandler
        print("✅ PurchaseHandler imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import PurchaseHandler: {e}")
        return False

def test_purchase_handler_creation():
    """Test that PurchaseHandler can be created"""
    try:
        from core.purchase_handler import PurchaseHandler
        handler = PurchaseHandler()
        print("✅ PurchaseHandler created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create PurchaseHandler: {e}")
        return False

def test_shop_database_connection():
    """Test that ShopDatabaseManager works"""
    try:
        from core.shop_database import ShopDatabaseManager
        db = ShopDatabaseManager()
        items = db.get_shop_items()
        print(f"✅ Shop database connected, found {len(items)} items")
        for i, item in enumerate(items, 1):
            print(f"   {i}. {item.name} - {item.price} монет")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to shop database: {e}")
        return False

def test_purchase_commands_info():
    """Test getting purchase commands info"""
    try:
        from core.purchase_handler import PurchaseHandler
        handler = PurchaseHandler()
        commands = handler.get_purchase_commands_info()
        print(f"✅ Purchase commands info retrieved: {len(commands)} commands")
        for cmd, info in commands.items():
            print(f"   {cmd}: {info['item_name']} - {info['price']} монет")
        return True
    except Exception as e:
        print(f"❌ Failed to get purchase commands info: {e}")
        return False

def test_purchase_validation():
    """Test purchase validation without actual purchase"""
    try:
        from core.purchase_handler import PurchaseHandler
        handler = PurchaseHandler()
        
        # Test with a non-existent user (should fail gracefully)
        validation = handler.validate_purchase_request(999999, 1)
        print(f"✅ Purchase validation test completed")
        print(f"   Valid: {validation['valid']}")
        print(f"   Message: {validation['message']}")
        return True
    except Exception as e:
        print(f"❌ Failed purchase validation test: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing PurchaseHandler implementation...")
    print("=" * 50)
    
    tests = [
        test_purchase_handler_import,
        test_purchase_handler_creation,
        test_shop_database_connection,
        test_purchase_commands_info,
        test_purchase_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! PurchaseHandler is ready.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")

if __name__ == "__main__":
    main()