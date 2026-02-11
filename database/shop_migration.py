#!/usr/bin/env python3
"""
Database migration script for Telegram Bot Shop System
Creates new tables: shop_items, user_purchases, scheduled_tasks
"""

import os
import sys
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

# Simple logging instead of structlog to avoid dependencies
def log_info(message):
    print(f"[INFO] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

# Simple settings class
class SimpleSettings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///data/bot.db")

settings = SimpleSettings()


def create_shop_tables(engine):
    """Create the new shop system tables"""
    
    # Create shop_items table
    shop_items_sql = """
    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        price INTEGER NOT NULL DEFAULT 100,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # Create user_purchases table
    user_purchases_sql = """
    CREATE TABLE IF NOT EXISTS user_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NULL,
        data JSON NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (item_id) REFERENCES shop_items(id)
    );
    """
    
    # Create scheduled_tasks table
    scheduled_tasks_sql = """
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message_id INTEGER NULL,
        chat_id INTEGER NOT NULL,
        task_type VARCHAR(50) NOT NULL,
        execute_at TIMESTAMP NOT NULL,
        task_data JSON NULL,
        is_completed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
    
    with engine.connect() as conn:
        log_info("Creating shop_items table...")
        conn.execute(text(shop_items_sql))
        
        log_info("Creating user_purchases table...")
        conn.execute(text(user_purchases_sql))
        
        log_info("Creating scheduled_tasks table...")
        conn.execute(text(scheduled_tasks_sql))
        
        conn.commit()
        log_info("Shop system tables created successfully")


def initialize_default_shop_items(engine):
    """Initialize the three default shop items"""
    
    default_items = [
        {
            'name': 'Безлимитные стикеры на 24 часа',
            'price': 100,
            'description': 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов'
        },
        {
            'name': 'Запрос на админ-права',
            'price': 100,
            'description': 'Отправить запрос владельцу бота на получение прав администратора'
        },
        {
            'name': 'Рассылка сообщения всем пользователям',
            'price': 100,
            'description': 'Отправить ваше сообщение всем пользователям бота'
        }
    ]
    
    with engine.connect() as conn:
        # Check if items already exist
        result = conn.execute(text("SELECT COUNT(*) as count FROM shop_items"))
        count = result.fetchone()[0]
        
        if count == 0:
            log_info("Initializing default shop items...")
            
            for item in default_items:
                insert_sql = """
                INSERT INTO shop_items (name, price, description, is_active, created_at)
                VALUES (:name, :price, :description, TRUE, :created_at)
                """
                
                conn.execute(text(insert_sql), {
                    'name': item['name'],
                    'price': item['price'],
                    'description': item['description'],
                    'created_at': datetime.utcnow()
                })
            
            conn.commit()
            log_info(f"Initialized {len(default_items)} default shop items")
        else:
            log_info(f"Shop items already exist ({count} items), skipping initialization")


def run_migration():
    """Run the complete migration"""
    try:
        log_info("Starting shop system database migration...")
        
        # Create database engine
        engine = create_engine(settings.database_url)
        
        # Create tables
        create_shop_tables(engine)
        
        # Initialize default items
        initialize_default_shop_items(engine)
        
        log_info("Shop system migration completed successfully!")
        return True
        
    except Exception as e:
        log_error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_migration()