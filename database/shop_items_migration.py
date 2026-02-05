#!/usr/bin/env python3
"""
Migration script to initialize the 3 default shop items for the Telegram Bot Shop System
"""

import os
import sys
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.database import Base, ShopItem, ShopCategory
from utils.core.config import settings


def initialize_shop_items():
    """Initialize the three default shop items"""
    
    # Create database engine and session
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if we already have the specific items we need
        existing_items = db.query(ShopItem).filter(
            ShopItem.name.in_([
                'Безлимитные стикеры на 24 часа',
                'Запрос на админ-права', 
                'Рассылка сообщения всем пользователям'
            ])
        ).all()
        
        existing_names = [item.name for item in existing_items]
        
        # Create a default category if none exists
        default_category = db.query(ShopCategory).first()
        if not default_category:
            default_category = ShopCategory(
                name="Основные услуги",
                description="Основные услуги бота",
                sort_order=1,
                is_active=True
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
        
        # Define the three required items
        required_items = [
            {
                'name': 'Безлимитные стикеры на 24 часа',
                'price': 100,
                'description': 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов',
                'item_type': 'sticker_unlimited'
            },
            {
                'name': 'Запрос на админ-права',
                'price': 100,
                'description': 'Отправить запрос владельцу бота на получение прав администратора',
                'item_type': 'admin_request'
            },
            {
                'name': 'Рассылка сообщения всем пользователям',
                'price': 100,
                'description': 'Отправить ваше сообщение всем пользователям бота',
                'item_type': 'broadcast_message'
            }
        ]
        
        # Add missing items
        added_count = 0
        for item_data in required_items:
            if item_data['name'] not in existing_names:
                new_item = ShopItem(
                    category_id=default_category.id,
                    name=item_data['name'],
                    price=item_data['price'],
                    description=item_data['description'],
                    item_type=item_data['item_type'],
                    meta_data={'shop_system_item': True},
                    is_active=True
                )
                db.add(new_item)
                added_count += 1
        
        if added_count > 0:
            db.commit()
            print(f"✓ Added {added_count} new shop items")
        else:
            print("✓ All required shop items already exist")
        
        # Display current shop items
        all_items = db.query(ShopItem).filter(ShopItem.is_active == True).all()
        print(f"\nCurrent active shop items ({len(all_items)}):")
        for item in all_items:
            print(f"  - ID {item.id}: {item.name} ({item.price} coins)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Shop Items Migration ===")
    try:
        initialize_shop_items()
        print("\n🎉 Shop items migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)