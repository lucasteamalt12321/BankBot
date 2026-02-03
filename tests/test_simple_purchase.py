#!/usr/bin/env python3
"""
Simple test to verify purchase handler functionality
"""

import os
import sys
import tempfile
import sqlite3

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.purchase_handler import PurchaseHandler
from core.shop_database import ShopDatabaseManager


def create_test_database(db_path):
    """Create test database with proper schema"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create transactions table (matching existing schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            type TEXT,
            admin_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (admin_id) REFERENCES users (id)
        )
    ''')
    
    # Insert test user
    cursor.execute(
        "INSERT INTO users (telegram_id, username, first_name, balance) VALUES (?, ?, ?, ?)",
        (12345, "testuser", "Test User", 150)
    )
    
    conn.commit()
    conn.close()


def main():
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Initialize database
        create_test_database(temp_db.name)
        
        # Create purchase handler
        db_manager = ShopDatabaseManager(temp_db.name)
        purchase_handler = PurchaseHandler(db_manager)
        
        # Test purchase
        print("Testing purchase with sufficient balance...")
        result = purchase_handler.process_purchase(12345, 1)
        
        print(f"Purchase result: success={result.success}")
        print(f"Message: {result.message}")
        print(f"Error code: {result.error_code}")
        print(f"New balance: {result.new_balance}")
        
        if result.success:
            print("✓ Purchase test passed!")
        else:
            print("✗ Purchase test failed!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        try:
            os.unlink(temp_db.name)
        except:
            pass


if __name__ == "__main__":
    main()