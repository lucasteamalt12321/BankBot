#!/usr/bin/env python3
"""
Initialize shop with default items
This script creates the basic shop categories and items needed for the bot to function
"""

import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db, ShopCategory, ShopItem
import structlog

logger = structlog.get_logger()


def initialize_shop():
    """Initialize shop with default categories and items"""
    
    try:
        db = next(get_db())
        
        # Check if shop items already exist
        existing_items = db.query(ShopItem).count()
        if existing_items > 0:
            print(f"Shop already has {existing_items} items. Skipping initialization.")
            return
        
        print("Initializing shop categories and items...")
        
        # Create default category
        category = ShopCategory(
            name="Основные услуги",
            description="Основные услуги бота",
            sort_order=1,
            is_active=True
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        
        # Create default shop items
        default_items = [
            {
                "category_id": category.id,
                "name": "Безлимитные стикеры на 24 часа",
                "description": "Получите возможность отправлять неограниченное количество стикеров в течение 24 часов",
                "price": 100,
                "item_type": "sticker",
                "meta_data": {"duration_hours": 24, "activation_type": "unlimited_stickers"},
                "cooldown_hours": 24,
                "is_active": True
            },
            {
                "category_id": category.id,
                "name": "Запрос на админ-права",
                "description": "Отправить запрос владельцу бота на получение прав администратора",
                "price": 100,
                "item_type": "admin_request",
                "meta_data": {"activation_type": "admin_request"},
                "purchase_limit": 1,
                "cooldown_hours": 168,  # 1 week
                "is_active": True
            },
            {
                "category_id": category.id,
                "name": "Рассылка сообщения всем пользователям",
                "description": "Отправить ваше сообщение всем пользователям бота",
                "price": 100,
                "item_type": "broadcast",
                "meta_data": {"activation_type": "broadcast_message"},
                "cooldown_hours": 24,
                "is_active": True
            }
        ]
        
        for item_data in default_items:
            item = ShopItem(**item_data)
            db.add(item)
        
        db.commit()
        
        print(f"Successfully initialized shop with {len(default_items)} items!")
        
        # Display created items
        items = db.query(ShopItem).filter(ShopItem.is_active == True).all()
        print("\nCreated shop items:")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item.name} - {item.price} монет")
            print(f"   {item.description}")
        
    except Exception as e:
        logger.error(f"Error initializing shop: {e}")
        print(f"Error initializing shop: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("Initializing shop...")
    success = initialize_shop()
    if success:
        print("Shop initialization completed successfully!")
    else:
        print("Shop initialization failed!")
        sys.exit(1)