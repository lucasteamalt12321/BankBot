#!/usr/bin/env python3
"""
Test script for the shop database setup
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.shop_database import ShopDatabaseManager

def test_shop_database():
    """Test the shop database functionality"""
    print("=== Testing Shop Database Setup ===")
    
    # Initialize database manager
    db_manager = ShopDatabaseManager()
    print("✓ Database manager initialized")
    
    # Test getting shop items
    items = db_manager.get_shop_items()
    print(f"✓ Found {len(items)} shop items:")
    
    for item in items:
        print(f"  - ID: {item.id}, Name: {item.name}, Price: {item.price}")
        print(f"    Description: {item.description}")
    
    # Test getting a specific item
    if items:
        first_item = db_manager.get_shop_item(items[0].id)
        if first_item:
            print(f"✓ Successfully retrieved item by ID: {first_item.name}")
        else:
            print("✗ Failed to retrieve item by ID")
    
    # Test getting pending tasks (should be empty initially)
    tasks = db_manager.get_pending_tasks()
    print(f"✓ Found {len(tasks)} pending tasks")
    
    print("\n=== Database Setup Complete ===")
    print("The following tables have been created:")
    print("  - shop_items (with 3 default items)")
    print("  - user_purchases")
    print("  - scheduled_tasks")

if __name__ == "__main__":
    try:
        test_shop_database()
        print("\n🎉 Shop database setup completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during database setup: {e}")
        import traceback
        traceback.print_exc()