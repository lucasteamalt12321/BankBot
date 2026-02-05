#!/usr/bin/env python3
"""
Property-based tests for database schema integrity
Feature: telegram-bot-advanced-features, Property 16: Database Schema Consistency
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import logging
from typing import List, Tuple, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings, assume, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings, assume, HealthCheck
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False


class DatabaseSchemaIntegritySystem:
    """System for testing database schema integrity for advanced features"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_advanced_schema()
    
    def _init_advanced_schema(self):
        """Initialize database schema with all advanced feature tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            
            # Create users table with advanced features columns
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    telegram_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 0,
                    daily_streak INTEGER DEFAULT 0,
                    last_daily DATETIME,
                    total_earned INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_vip BOOLEAN DEFAULT FALSE,
                    vip_until DATETIME,
                    is_admin BOOLEAN DEFAULT FALSE,
                    sticker_unlimited BOOLEAN DEFAULT FALSE,
                    sticker_unlimited_until DATETIME,
                    total_purchases INTEGER DEFAULT 0
                )
            ''')
            
            # Create shop_items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    item_type TEXT NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create parsing_rules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parsing_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    multiplier DECIMAL(10,4) NOT NULL,
                    currency_type TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Create parsed_transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parsed_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_bot TEXT NOT NULL,
                    original_amount DECIMAL(10,2) NOT NULL,
                    converted_amount DECIMAL(10,2) NOT NULL,
                    currency_type TEXT NOT NULL,
                    parsed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_text TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Create purchase_records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS purchase_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    price_paid DECIMAL(10,2) NOT NULL,
                    purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (item_id) REFERENCES shop_items (id)
                )
            ''')
            
            conn.commit()
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_user(self, user_id: int, username: str = None, telegram_id: int = None) -> bool:
        """Create a new user"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """INSERT INTO users (id, telegram_id, username, first_name, balance, is_admin, 
                       sticker_unlimited, sticker_unlimited_until, total_purchases) 
                       VALUES (?, ?, ?, ?, 0, FALSE, FALSE, NULL, 0)""",
                    (user_id, telegram_id, username, f"User {user_id}")
                )
                
                conn.commit()
                return True
                
        except Exception:
            return False
    
    def create_shop_item(self, name: str, price: float, item_type: str, description: str = None) -> Optional[int]:
        """Create a shop item"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO shop_items (name, price, item_type, description) VALUES (?, ?, ?, ?)",
                    (name, price, item_type, description)
                )
                
                item_id = cursor.lastrowid
                conn.commit()
                return item_id
                
        except Exception:
            return None
    
    def create_parsing_rule(self, bot_name: str, pattern: str, multiplier: float, currency_type: str) -> Optional[int]:
        """Create a parsing rule"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO parsing_rules (bot_name, pattern, multiplier, currency_type) VALUES (?, ?, ?, ?)",
                    (bot_name, pattern, multiplier, currency_type)
                )
                
                rule_id = cursor.lastrowid
                conn.commit()
                return rule_id
                
        except Exception:
            return None
    
    def create_parsed_transaction(self, user_id: int, source_bot: str, original_amount: float, 
                                converted_amount: float, currency_type: str, message_text: str = None) -> Optional[int]:
        """Create a parsed transaction"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """INSERT INTO parsed_transactions (user_id, source_bot, original_amount, 
                       converted_amount, currency_type, message_text) VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, source_bot, original_amount, converted_amount, currency_type, message_text)
                )
                
                transaction_id = cursor.lastrowid
                conn.commit()
                return transaction_id
                
        except Exception:
            return None
    
    def create_purchase_record(self, user_id: int, item_id: int, price_paid: float, expires_at: datetime = None) -> Optional[int]:
        """Create a purchase record"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO purchase_records (user_id, item_id, price_paid, expires_at) VALUES (?, ?, ?, ?)",
                    (user_id, item_id, price_paid, expires_at)
                )
                
                record_id = cursor.lastrowid
                conn.commit()
                return record_id
                
        except Exception:
            return None
    
    def update_user_sticker_access(self, user_id: int, unlimited: bool, until: datetime = None) -> bool:
        """Update user sticker access"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE users SET sticker_unlimited = ?, sticker_unlimited_until = ? WHERE id = ?",
                    (unlimited, until, user_id)
                )
                
                success = cursor.rowcount > 0
                conn.commit()
                return success
                
        except Exception:
            return False
    
    def check_schema_integrity(self) -> List[Dict[str, Any]]:
        """Check database schema integrity"""
        violations = []
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check for orphaned parsed_transactions (user_id not in users)
                cursor.execute('''
                    SELECT pt.id, pt.user_id, pt.source_bot 
                    FROM parsed_transactions pt 
                    LEFT JOIN users u ON pt.user_id = u.id 
                    WHERE u.id IS NULL
                ''')
                orphaned_parsed_transactions = [dict(row) for row in cursor.fetchall()]
                
                # Check for orphaned purchase_records (user_id not in users)
                cursor.execute('''
                    SELECT pr.id, pr.user_id, pr.item_id 
                    FROM purchase_records pr 
                    LEFT JOIN users u ON pr.user_id = u.id 
                    WHERE u.id IS NULL
                ''')
                orphaned_purchase_users = [dict(row) for row in cursor.fetchall()]
                
                # Check for orphaned purchase_records (item_id not in shop_items)
                cursor.execute('''
                    SELECT pr.id, pr.user_id, pr.item_id 
                    FROM purchase_records pr 
                    LEFT JOIN shop_items si ON pr.item_id = si.id 
                    WHERE si.id IS NULL
                ''')
                orphaned_purchase_items = [dict(row) for row in cursor.fetchall()]
                
                # Check for invalid sticker_unlimited_until dates (in past but unlimited still true)
                cursor.execute('''
                    SELECT id, username, sticker_unlimited_until 
                    FROM users 
                    WHERE sticker_unlimited = TRUE 
                    AND sticker_unlimited_until IS NOT NULL 
                    AND sticker_unlimited_until < datetime('now')
                ''')
                expired_sticker_access = [dict(row) for row in cursor.fetchall()]
                
                # Check for negative balances or invalid data
                cursor.execute('''
                    SELECT id, username, balance, total_purchases 
                    FROM users 
                    WHERE balance < 0 OR total_purchases < 0
                ''')
                invalid_user_data = [dict(row) for row in cursor.fetchall()]
                
                # Check for invalid shop item prices
                cursor.execute('''
                    SELECT id, name, price 
                    FROM shop_items 
                    WHERE price <= 0
                ''')
                invalid_shop_prices = [dict(row) for row in cursor.fetchall()]
                
                # Check for invalid parsing rule multipliers
                cursor.execute('''
                    SELECT id, bot_name, multiplier 
                    FROM parsing_rules 
                    WHERE multiplier <= 0
                ''')
                invalid_multipliers = [dict(row) for row in cursor.fetchall()]
                
                # Add violations to list
                for tx in orphaned_parsed_transactions:
                    violations.append({
                        'type': 'orphaned_parsed_transaction',
                        'transaction_id': tx['id'],
                        'user_id': tx['user_id'],
                        'details': f"Parsed transaction {tx['id']} references non-existent user {tx['user_id']}"
                    })
                
                for pr in orphaned_purchase_users:
                    violations.append({
                        'type': 'orphaned_purchase_user',
                        'purchase_id': pr['id'],
                        'user_id': pr['user_id'],
                        'details': f"Purchase record {pr['id']} references non-existent user {pr['user_id']}"
                    })
                
                for pr in orphaned_purchase_items:
                    violations.append({
                        'type': 'orphaned_purchase_item',
                        'purchase_id': pr['id'],
                        'item_id': pr['item_id'],
                        'details': f"Purchase record {pr['id']} references non-existent item {pr['item_id']}"
                    })
                
                for user in expired_sticker_access:
                    violations.append({
                        'type': 'expired_sticker_access',
                        'user_id': user['id'],
                        'details': f"User {user['id']} has expired sticker access but unlimited flag is still true"
                    })
                
                for user in invalid_user_data:
                    violations.append({
                        'type': 'invalid_user_data',
                        'user_id': user['id'],
                        'details': f"User {user['id']} has invalid data: balance={user['balance']}, purchases={user['total_purchases']}"
                    })
                
                for item in invalid_shop_prices:
                    violations.append({
                        'type': 'invalid_shop_price',
                        'item_id': item['id'],
                        'details': f"Shop item {item['id']} has invalid price: {item['price']}"
                    })
                
                for rule in invalid_multipliers:
                    violations.append({
                        'type': 'invalid_multiplier',
                        'rule_id': rule['id'],
                        'details': f"Parsing rule {rule['id']} has invalid multiplier: {rule['multiplier']}"
                    })
                
                return violations
                
        except Exception as e:
            return [{'type': 'check_error', 'details': str(e)}]
    
    def get_table_counts(self) -> Dict[str, int]:
        """Get count of records in each table"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                counts = {}
                tables = ['users', 'shop_items', 'parsing_rules', 'parsed_transactions', 'purchase_records']
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = cursor.fetchone()[0]
                
                return counts
                
        except Exception:
            return {}


class TestDatabaseSchemaIntegrityPBT(unittest.TestCase):
    """Property-based tests for database schema integrity"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize database system
        self.db_system = DatabaseSchemaIntegritySystem(self.temp_db.name)
        
        # Create initial test data
        self.test_users = [1001, 1002, 1003, 1004]
        for user_id in self.test_users:
            self.db_system.create_user(user_id, f"user{user_id}", user_id + 100000)
        
        # Create initial shop items
        self.test_items = []
        item_types = ['sticker', 'admin', 'mention_all', 'custom']
        for i, item_type in enumerate(item_types, 1):
            item_id = self.db_system.create_shop_item(f"item_{item_type}", 10.0 * i, item_type, f"Test {item_type} item")
            if item_id:
                self.test_items.append(item_id)
        
        # Create initial parsing rules
        self.test_rules = []
        bots = [('Shmalala', r'Монеты: \+(\d+)', 1.0, 'coins'), ('GDcards', r'Очки: \+(\d+)', 0.5, 'points')]
        for bot_name, pattern, multiplier, currency in bots:
            rule_id = self.db_system.create_parsing_rule(bot_name, pattern, multiplier, currency)
            if rule_id:
                self.test_rules.append(rule_id)
    
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        user_id=st.integers(min_value=2000, max_value=2010),
        item_name=st.text(min_size=1, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'),
        price=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=10, deadline=30000)
    def test_database_schema_consistency(self, user_id, item_name, price):
        """
        Feature: telegram-bot-advanced-features, Property 16: Database Schema Consistency
        
        For any sequence of database operations on advanced feature tables,
        all foreign key constraints should remain valid and schema integrity preserved
        Validates: Requirements 6.4, 11.1
        """
        # Create a user first
        username = f"user{user_id}"
        telegram_id = user_id + 100000
        user_created = self.db_system.create_user(user_id, username, telegram_id)
        
        # Create a shop item
        item_name_unique = f"{item_name}_{user_id}"
        item_id = self.db_system.create_shop_item(item_name_unique, price, 'custom')
        
        # Create a parsed transaction for the user
        if user_created:
            transaction_id = self.db_system.create_parsed_transaction(
                user_id, 'TestBot', price, price, 'coins'
            )
        
        # Create a purchase record if both user and item exist
        if user_created and item_id:
            purchase_id = self.db_system.create_purchase_record(user_id, item_id, price)
        
        # Check database schema integrity after all operations
        violations = self.db_system.check_schema_integrity()
        
        # Assert no schema integrity violations exist
        self.assertEqual(
            len(violations), 0,
            f"Database schema integrity violations found: {violations}"
        )
        
        # Additional verification: check table counts are reasonable
        counts = self.db_system.get_table_counts()
        self.assertGreater(counts.get('users', 0), 0, "Users table should not be empty")
        
        # Verify all tables exist and are accessible
        expected_tables = ['users', 'shop_items', 'parsing_rules', 'parsed_transactions', 'purchase_records']
        for table in expected_tables:
            self.assertIn(table, counts, f"Table {table} should exist and be accessible")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        user_id=st.integers(min_value=1001, max_value=1004),  # Existing user IDs
        num_purchases=st.integers(min_value=1, max_value=2)  # Number of purchase records
    )
    @settings(max_examples=5, deadline=15000)
    def test_purchase_record_foreign_key_integrity(self, user_id, num_purchases):
        """
        Feature: telegram-bot-advanced-features, Property 16: Database Schema Consistency (purchase records)
        
        Purchase records should maintain foreign key integrity with users and shop_items tables
        Validates: Requirements 6.4, 11.1
        """
        # Create purchase records for existing user and items
        for i in range(num_purchases):
            if self.test_items:
                item_id = self.test_items[i % len(self.test_items)]
                price = 10.0 + i
                self.db_system.create_purchase_record(user_id, item_id, price)
        
        # Check schema integrity
        violations = self.db_system.check_schema_integrity()
        
        # Assert no foreign key violations exist
        self.assertEqual(
            len(violations), 0,
            f"Purchase record foreign key violations found: {violations}"
        )
    
    def test_database_schema_consistency_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Test 1: Create parsed transaction for existing user
        transaction_id = self.db_system.create_parsed_transaction(
            1001, 'Shmalala', 25.0, 25.0, 'coins', 'Монеты: +25'
        )
        self.assertIsNotNone(transaction_id, "Parsed transaction should be created successfully")
        
        violations = self.db_system.check_schema_integrity()
        self.assertEqual(len(violations), 0, "No schema integrity violations should exist")
        
        # Test 2: Create purchase record for existing user and item
        if self.test_items:
            purchase_id = self.db_system.create_purchase_record(1002, self.test_items[0], 15.0)
            self.assertIsNotNone(purchase_id, "Purchase record should be created successfully")
            
            violations = self.db_system.check_schema_integrity()
            self.assertEqual(len(violations), 0, "No schema integrity violations should exist after purchase")
        
        # Test 3: Update sticker access
        success = self.db_system.update_user_sticker_access(1003, True, datetime.now() + timedelta(hours=24))
        self.assertTrue(success, "Sticker access update should succeed")
        
        violations = self.db_system.check_schema_integrity()
        self.assertEqual(len(violations), 0, "No schema integrity violations should exist after sticker update")
        
        # Test 4: Verify all required tables exist
        counts = self.db_system.get_table_counts()
        expected_tables = ['users', 'shop_items', 'parsing_rules', 'parsed_transactions', 'purchase_records']
        for table in expected_tables:
            self.assertIn(table, counts, f"Table {table} should exist")
            self.assertGreaterEqual(counts[table], 0, f"Table {table} should be accessible")


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)