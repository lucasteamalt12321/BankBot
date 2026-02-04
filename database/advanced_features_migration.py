#!/usr/bin/env python3
"""
Database migration script for Advanced Telegram Bot Features
Creates new tables: parsing_rules, parsed_transactions, purchase_records
Adds new columns to users table: sticker_unlimited, sticker_unlimited_until, total_purchases
"""

import os
import sys
from datetime import datetime
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, Boolean, Text, DECIMAL, ForeignKey
from sqlalchemy.orm import sessionmaker
from database.database import Base
from utils.config import settings


def log_info(message):
    """Simple logging function"""
    print(f"[INFO] {message}")


def log_error(message):
    """Simple error logging function"""
    print(f"[ERROR] {message}")


def create_new_tables(engine):
    """Create the new tables for advanced features"""
    
    # Create parsing_rules table
    parsing_rules_sql = """
    CREATE TABLE IF NOT EXISTS parsing_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_name VARCHAR(50) NOT NULL,
        pattern VARCHAR(200) NOT NULL,
        multiplier DECIMAL(10,4) NOT NULL,
        currency_type VARCHAR(20) NOT NULL,
        is_active BOOLEAN DEFAULT TRUE
    );
    """
    
    # Create parsed_transactions table
    parsed_transactions_sql = """
    CREATE TABLE IF NOT EXISTS parsed_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        source_bot VARCHAR(50) NOT NULL,
        original_amount DECIMAL(10,2) NOT NULL,
        converted_amount DECIMAL(10,2) NOT NULL,
        currency_type VARCHAR(20) NOT NULL,
        parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        message_text TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
    
    # Create purchase_records table
    purchase_records_sql = """
    CREATE TABLE IF NOT EXISTS purchase_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        price_paid DECIMAL(10,2) NOT NULL,
        purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (item_id) REFERENCES shop_items(id)
    );
    """
    
    with engine.connect() as conn:
        log_info("Creating parsing_rules table...")
        conn.execute(text(parsing_rules_sql))
        
        log_info("Creating parsed_transactions table...")
        conn.execute(text(parsed_transactions_sql))
        
        log_info("Creating purchase_records table...")
        conn.execute(text(purchase_records_sql))
        
        conn.commit()
        log_info("New tables created successfully")


def add_user_columns(engine):
    """Add new columns to the users table"""
    
    with engine.connect() as conn:
        # Check existing columns
        cursor = conn.execute(text("PRAGMA table_info(users)"))
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add sticker_unlimited column if it doesn't exist
        if 'sticker_unlimited' not in column_names:
            log_info("Adding sticker_unlimited column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN sticker_unlimited BOOLEAN DEFAULT FALSE"))
        else:
            log_info("sticker_unlimited column already exists")
        
        # Add sticker_unlimited_until column if it doesn't exist
        if 'sticker_unlimited_until' not in column_names:
            log_info("Adding sticker_unlimited_until column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN sticker_unlimited_until TIMESTAMP NULL"))
        else:
            log_info("sticker_unlimited_until column already exists")
        
        # Add total_purchases column if it doesn't exist
        if 'total_purchases' not in column_names:
            log_info("Adding total_purchases column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN total_purchases INTEGER DEFAULT 0"))
        else:
            log_info("total_purchases column already exists")
        
        conn.commit()
        log_info("User table columns updated successfully")


def initialize_default_parsing_rules(engine):
    """Initialize default parsing rules for external bots"""
    
    default_rules = [
        {
            'bot_name': 'Shmalala',
            'pattern': r'Монеты: \+(\d+)',
            'multiplier': Decimal('1.0'),
            'currency_type': 'coins'
        },
        {
            'bot_name': 'GDcards',
            'pattern': r'Очки: \+(\d+)',
            'multiplier': Decimal('1.0'),
            'currency_type': 'points'
        }
    ]
    
    with engine.connect() as conn:
        # Check if rules already exist
        result = conn.execute(text("SELECT COUNT(*) as count FROM parsing_rules"))
        count = result.fetchone()[0]
        
        if count == 0:
            log_info("Initializing default parsing rules...")
            
            for rule in default_rules:
                insert_sql = """
                INSERT INTO parsing_rules (bot_name, pattern, multiplier, currency_type, is_active)
                VALUES (:bot_name, :pattern, :multiplier, :currency_type, TRUE)
                """
                
                conn.execute(text(insert_sql), {
                    'bot_name': rule['bot_name'],
                    'pattern': rule['pattern'],
                    'multiplier': float(rule['multiplier']),
                    'currency_type': rule['currency_type']
                })
            
            conn.commit()
            log_info(f"Initialized {len(default_rules)} default parsing rules")
        else:
            log_info(f"Parsing rules already exist ({count} rules), skipping initialization")


def update_shop_items_for_advanced_features(engine):
    """Update existing shop items to support advanced features"""
    
    with engine.connect() as conn:
        # Check if shop_items table has the required structure
        cursor = conn.execute(text("PRAGMA table_info(shop_items)"))
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Ensure item_type column exists (it should from the existing schema)
        if 'item_type' not in column_names:
            log_info("Adding item_type column to shop_items table...")
            conn.execute(text("ALTER TABLE shop_items ADD COLUMN item_type VARCHAR(50) DEFAULT 'custom'"))
            conn.commit()
        
        # Update existing items with proper types if they don't have them
        update_sql = """
        UPDATE shop_items 
        SET item_type = CASE 
            WHEN name LIKE '%стикер%' OR name LIKE '%Стикер%' THEN 'sticker'
            WHEN name LIKE '%админ%' OR name LIKE '%Админ%' THEN 'admin'
            WHEN name LIKE '%рассылка%' OR name LIKE '%Рассылка%' THEN 'mention_all'
            ELSE 'custom'
        END
        WHERE item_type IS NULL OR item_type = ''
        """
        
        result = conn.execute(text(update_sql))
        updated_rows = result.rowcount
        
        if updated_rows > 0:
            conn.commit()
            log_info(f"Updated {updated_rows} shop items with proper item types")
        else:
            log_info("Shop items already have proper item types")


def verify_migration(engine):
    """Verify that the migration was successful"""
    
    with engine.connect() as conn:
        # Check new tables exist
        tables_to_check = ['parsing_rules', 'parsed_transactions', 'purchase_records']
        
        for table in tables_to_check:
            result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"))
            if result.fetchone():
                log_info(f"✓ Table {table} exists")
            else:
                log_error(f"✗ Table {table} missing")
                return False
        
        # Check new user columns exist
        cursor = conn.execute(text("PRAGMA table_info(users)"))
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required_columns = ['sticker_unlimited', 'sticker_unlimited_until', 'total_purchases']
        for column in required_columns:
            if column in column_names:
                log_info(f"✓ Column users.{column} exists")
            else:
                log_error(f"✗ Column users.{column} missing")
                return False
        
        # Check parsing rules were created
        result = conn.execute(text("SELECT COUNT(*) as count FROM parsing_rules"))
        rule_count = result.fetchone()[0]
        log_info(f"✓ {rule_count} parsing rules initialized")
        
        return True


def run_migration():
    """Run the complete migration"""
    try:
        log_info("Starting advanced features database migration...")
        
        # Create database engine
        engine = create_engine(settings.database_url)
        
        # Create new tables
        create_new_tables(engine)
        
        # Add new columns to users table
        add_user_columns(engine)
        
        # Initialize default parsing rules
        initialize_default_parsing_rules(engine)
        
        # Update shop items for advanced features
        update_shop_items_for_advanced_features(engine)
        
        # Verify migration
        if verify_migration(engine):
            log_info("Advanced features migration completed successfully!")
            return True
        else:
            log_error("Migration verification failed!")
            return False
        
    except Exception as e:
        log_error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=== Advanced Features Database Migration ===")
    try:
        success = run_migration()
        if success:
            print("\n🎉 Migration completed successfully!")
        else:
            print("\n❌ Migration failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        sys.exit(1)