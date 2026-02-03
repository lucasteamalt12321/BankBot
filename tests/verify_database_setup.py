#!/usr/bin/env python3
"""
Verification script for the shop database setup
This script checks if all required tables and data are properly set up
"""

import sqlite3
import os
import json
from datetime import datetime


def verify_database_setup():
    """Verify that the database is properly set up for the shop system"""
    
    db_path = "bot.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} does not exist")
        return False
    
    print(f"✓ Database file {db_path} exists")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check required tables
        required_tables = {
            'shop_items': ['id', 'name', 'price', 'description'],
            'user_purchases': ['id', 'user_id', 'item_id', 'purchased_at', 'expires_at'],
            'scheduled_tasks': ['id', 'user_id', 'chat_id', 'task_type', 'execute_at']
        }
        
        print("\n=== Checking Tables ===")
        for table_name, required_columns in required_tables.items():
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if cursor.fetchone():
                print(f"✓ Table {table_name} exists")
                
                # Check columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]
                
                missing_columns = []
                for col in required_columns:
                    if col not in columns:
                        missing_columns.append(col)
                
                if missing_columns:
                    print(f"  ⚠️  Missing columns: {missing_columns}")
                else:
                    print(f"  ✓ All required columns present")
                
                # Check record count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  Records: {count}")
                
            else:
                print(f"❌ Table {table_name} does not exist")
        
        # Check shop items specifically
        print("\n=== Checking Shop Items ===")
        cursor.execute("SELECT id, name, price, description FROM shop_items WHERE is_active = 1 ORDER BY id")
        items = cursor.fetchall()
        
        required_items = [
            'Безлимитные стикеры на 24 часа',
            'Запрос на админ-права',
            'Рассылка сообщения всем пользователям'
        ]
        
        if items:
            print(f"Found {len(items)} active shop items:")
            item_names = []
            for item in items:
                print(f"  - ID {item['id']}: {item['name']} ({item['price']} coins)")
                item_names.append(item['name'])
            
            # Check if all required items are present
            missing_items = []
            for required_item in required_items:
                if required_item not in item_names:
                    missing_items.append(required_item)
            
            if missing_items:
                print(f"\n⚠️  Missing required items:")
                for item in missing_items:
                    print(f"    - {item}")
            else:
                print(f"\n✓ All required shop items are present")
        else:
            print("❌ No shop items found")
        
        # Check if users table exists (required for foreign keys)
        print("\n=== Checking Dependencies ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            print("✓ Users table exists (required for foreign keys)")
        else:
            print("❌ Users table does not exist")
        
        conn.close()
        
        print("\n=== Summary ===")
        print("Database schema is set up for the Telegram Bot Shop System")
        print("Required tables: shop_items, user_purchases, scheduled_tasks")
        print("Required items: 3 shop items with 100 coin price each")
        
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False


def create_minimal_setup():
    """Create minimal database setup if tables don't exist"""
    
    print("\n=== Creating Minimal Setup ===")
    
    try:
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        
        # Create shop_items table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name VARCHAR(100),
            description TEXT,
            price INTEGER,
            item_type VARCHAR(50),
            meta_data JSON,
            purchase_limit INTEGER DEFAULT 0,
            cooldown_hours INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )
        """)
        
        # Create user_purchases table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            purchase_price INTEGER,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            meta_data JSON
        )
        """)
        
        # Create scheduled_tasks table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_id INTEGER,
            chat_id INTEGER NOT NULL,
            task_type VARCHAR(50) NOT NULL,
            execute_at TIMESTAMP NOT NULL,
            task_data JSON,
            is_completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Insert default shop items if they don't exist
        default_items = [
            (1, 'Безлимитные стикеры на 24 часа', 100, 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов', 'sticker_unlimited'),
            (2, 'Запрос на админ-права', 100, 'Отправить запрос владельцу бота на получение прав администратора', 'admin_request'),
            (3, 'Рассылка сообщения всем пользователям', 100, 'Отправить ваше сообщение всем пользователям бота', 'broadcast_message')
        ]
        
        for item_id, name, price, description, item_type in default_items:
            cursor.execute("SELECT id FROM shop_items WHERE id = ?", (item_id,))
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO shop_items (id, name, price, description, item_type, is_active, meta_data)
                VALUES (?, ?, ?, ?, ?, TRUE, ?)
                """, (item_id, name, price, description, item_type, json.dumps({'shop_system_item': True})))
        
        conn.commit()
        conn.close()
        
        print("✓ Minimal database setup completed")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create minimal setup: {e}")
        return False


if __name__ == "__main__":
    print("=== Database Setup Verification ===")
    
    # First try to verify existing setup
    if not verify_database_setup():
        # If verification fails, try to create minimal setup
        if create_minimal_setup():
            # Verify again after setup
            verify_database_setup()
    
    print("\n🎉 Database verification completed!")