#!/usr/bin/env python3
"""
Simple shop initialization script
"""

import sqlite3
import json
import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def initialize_shop():
    """Initialize shop with default items using direct SQLite"""
    
    # Use relative path from root
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if shop_categories table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='shop_categories'
        """)
        
        if not cursor.fetchone():
            print("Creating shop_categories table...")
            cursor.execute("""
                CREATE TABLE shop_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100),
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
        
        # Check if shop_items table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='shop_items'
        """)
        
        if not cursor.fetchone():
            print("Creating shop_items table...")
            cursor.execute("""
                CREATE TABLE shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    name VARCHAR(100),
                    description TEXT,
                    price INTEGER,
                    item_type VARCHAR(50),
                    meta_data JSON,
                    purchase_limit INTEGER DEFAULT 0,
                    cooldown_hours INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (category_id) REFERENCES shop_categories(id)
                )
            """)
        
        # Check if items already exist
        cursor.execute("SELECT COUNT(*) FROM shop_items")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"Shop already has {existing_count} items. Skipping initialization.")
            conn.close()
            return True
        
        print("Initializing shop...")
        
        # Insert default category
        cursor.execute("""
            INSERT INTO shop_categories (name, description, sort_order, is_active)
            VALUES (?, ?, ?, ?)
        """, ("Основные услуги", "Основные услуги бота", 1, True))
        
        category_id = cursor.lastrowid
        
        # Insert default items
        items = [
            (
                category_id,
                "Безлимитные стикеры на 24 часа",
                "Получите возможность отправлять неограниченное количество стикеров в течение 24 часов",
                100,
                "sticker",
                json.dumps({"duration_hours": 24, "activation_type": "unlimited_stickers"}),
                0,
                24,
                True
            ),
            (
                category_id,
                "Запрос на админ-права",
                "Отправить запрос владельцу бота на получение прав администратора",
                100,
                "admin_request",
                json.dumps({"activation_type": "admin_request"}),
                1,
                168,
                True
            ),
            (
                category_id,
                "Рассылка сообщения всем пользователям",
                "Отправить ваше сообщение всем пользователям бота с @ упоминанием",
                100,
                "broadcast",
                json.dumps({"activation_type": "broadcast_message"}),
                0,
                24,
                True
            )
        ]
        
        cursor.executemany("""
            INSERT INTO shop_items 
            (category_id, name, description, price, item_type, meta_data, purchase_limit, cooldown_hours, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, items)
        
        conn.commit()
        
        print(f"Successfully initialized shop with {len(items)} items!")
        
        # Display created items
        cursor.execute("SELECT name, price, description FROM shop_items WHERE is_active = 1")
        items = cursor.fetchall()
        
        print("\nCreated shop items:")
        for i, (name, price, description) in enumerate(items, 1):
            print(f"{i}. {name} - {price} монет")
            print(f"   {description}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error initializing shop: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Initializing shop...")
    success = initialize_shop()
    if success:
        print("Shop initialization completed successfully!")
    else:
        print("Shop initialization failed!")