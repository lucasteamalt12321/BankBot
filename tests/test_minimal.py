#!/usr/bin/env python3
"""
Minimal test to check shop display completeness
"""

import sys
import os
import tempfile

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.shop_handler import ShopHandler
    from core.shop_models import ShopItem
    from core.shop_database import ShopDatabaseManager
    print("✓ Imports successful")
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    # Initialize components
    db_manager = ShopDatabaseManager(temp_db.name)
    shop_handler = ShopHandler(db_manager)
    
    print("✓ Components initialized")
    
    # Test shop display with no items
    display = shop_handler.display_shop(12345)
    print("✓ Shop display generated")
    print(f"Display content: {display[:100]}...")
    
    # Check basic requirements
    if "🛒 МАГАЗИН" in display:
        print("✓ Shop header present")
    else:
        print("✗ Shop header missing")
    
    # Clean up
    os.unlink(temp_db.name)
    print("✓ Test completed successfully")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()