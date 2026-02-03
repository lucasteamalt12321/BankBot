#!/usr/bin/env python3
"""
Simple test for PurchaseHandler
"""

import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing PurchaseHandler import...")
    from core.purchase_handler import PurchaseHandler
    print("✅ Import successful")
    
    print("Testing PurchaseHandler creation...")
    handler = PurchaseHandler()
    print("✅ Creation successful")
    
    print("Testing shop items retrieval...")
    from core.shop_database import ShopDatabaseManager
    db = ShopDatabaseManager()
    items = db.get_shop_items()
    print(f"✅ Found {len(items)} shop items")
    
    for i, item in enumerate(items, 1):
        print(f"   {i}. {item.name} - {item.price} монет")
    
    print("Testing purchase commands info...")
    commands = handler.get_purchase_commands_info()
    print(f"✅ Found {len(commands)} purchase commands")
    
    for cmd, info in commands.items():
        print(f"   {cmd}: {info['item_name']}")
    
    print("\n🎉 All basic tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()