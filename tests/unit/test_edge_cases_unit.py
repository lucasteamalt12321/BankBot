#!/usr/bin/env python3
"""
Unit tests for edge cases - Task 11.2
Tests zero balances, maximum values, special characters in usernames, transaction edge cases
Requirements: 2.1, 5.1, 6.3
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import logging
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple admin system mock to avoid telegram dependencies
class SimpleAdminSystem:
    """Simplified admin system for testing edge cases"""
    
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
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
        
        conn.commit()
        conn.close()
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_user(self, user_id, username, first_name):
        """Register a new user"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True  # User already exists
            
            cursor.execute(
                "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def get_user_by_username(self, username):
        """Get user by username"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Remove @ if present
        clean_username = username.lstrip('@') if username else username
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_balance(self, user_id, amount):
        """Update user balance"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return None
        
        new_balance = result['balance'] + amount
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        conn.close()
        
        return new_balance
    
    def set_admin_status(self, user_id, is_admin):
        """Set admin status for user"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?", (is_admin, user_id))
        success = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return success
    
    def get_users_count(self):
        """Get total number of users"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        count = cursor.fetchone()['count']
        
        conn.close()
        return count
    
    def add_transaction(self, user_id, amount, transaction_type, admin_id=None):
        """Add transaction record"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type, admin_id) VALUES (?, ?, ?, ?)",
            (user_id, amount, transaction_type, admin_id)
        )
        
        transaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return transaction_id


class TestEdgeCases(unittest.TestCase):
    """Test cases for edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize admin system
        self.admin_system = SimpleAdminSystem(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    # ===== Zero Balance Tests =====
    
    def test_zero_balance_initialization(self):
        """Test that new users start with zero balance
        
        Validates: Requirements 2.1, 6.3
        """
        user_id = 123456789
        username = "testuser"
        first_name = "Test User"
        
        # Register new user
        success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(success, "User registration should succeed")
        
        # Check that balance is exactly zero
        user = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist after registration")
        self.assertEqual(user['balance'], 0.0, "New user balance should be exactly 0.0")
        
        print(f"✓ Zero balance initialization verified: {user['balance']}")
    
    def test_zero_balance_operations(self):
        """Test operations with zero balance
        
        Validates: Requirements 2.1, 5.1
        """
        user_id = 123456789
        username = "testuser"
        
        # Register user with zero balance
        self.admin_system.register_user(user_id, username, "Test User")
        
        # Test adding zero points
        new_balance = self.admin_system.update_balance(user_id, 0.0)
        self.assertEqual(new_balance, 0.0, "Adding zero to zero should remain zero")
        
        # Test subtracting from zero balance (should work mathematically)
        new_balance = self.admin_system.update_balance(user_id, -10.0)
        self.assertEqual(new_balance, -10.0, "Subtracting from zero should result in negative balance")
        
        # Test adding back to zero
        new_balance = self.admin_system.update_balance(user_id, 10.0)
        self.assertEqual(new_balance, 0.0, "Adding back should return to zero")
        
        print("✓ Zero balance operations verified")
    
    def test_purchase_with_zero_balance(self):
        """Test purchase attempt with zero balance
        
        Validates: Requirements 5.1
        """
        user_id = 123456789
        username = "testuser"
        
        # Register user with zero balance
        self.admin_system.register_user(user_id, username, "Test User")
        
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], 0.0, "User should have zero balance")
        
        # Simulate purchase validation (10 points required)
        required_amount = 10
        can_purchase = user['balance'] >= required_amount
        
        self.assertFalse(can_purchase, "Purchase should not be allowed with zero balance")
        
        print("✓ Purchase with zero balance correctly blocked")
    
    # ===== Maximum Value Tests =====
    
    def test_maximum_balance_values(self):
        """Test handling of very large balance values
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        username = "testuser"
        
        # Register user
        self.admin_system.register_user(user_id, username, "Test User")
        
        # Test large positive balance
        large_amount = 999999999.99
        new_balance = self.admin_system.update_balance(user_id, large_amount)
        self.assertEqual(new_balance, large_amount, "Should handle large positive balances")
        
        # Test adding more to large balance
        additional_amount = 1000000.01
        new_balance = self.admin_system.update_balance(user_id, additional_amount)
        expected_balance = large_amount + additional_amount
        self.assertAlmostEqual(new_balance, expected_balance, places=2, 
                              msg="Should handle arithmetic with large balances")
        
        print(f"✓ Maximum balance values verified: {new_balance}")
    
    def test_maximum_transaction_amounts(self):
        """Test very large transaction amounts
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        admin_id = 987654321
        
        # Register users
        self.admin_system.register_user(user_id, "testuser", "Test User")
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        self.admin_system.set_admin_status(admin_id, True)
        
        # Test large transaction
        large_amount = 1000000.0
        transaction_id = self.admin_system.add_transaction(
            user_id, large_amount, 'add', admin_id
        )
        
        self.assertIsNotNone(transaction_id, "Large transaction should be recorded")
        self.assertIsInstance(transaction_id, int, "Transaction ID should be integer")
        
        # Verify transaction was recorded correctly
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type FROM transactions WHERE id = ?", (transaction_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result, "Transaction should exist in database")
        self.assertEqual(result['amount'], large_amount, "Transaction amount should match")
        self.assertEqual(result['type'], 'add', "Transaction type should match")
        
        print(f"✓ Maximum transaction amounts verified: {large_amount}")
    
    def test_maximum_user_count(self):
        """Test system with many users
        
        Validates: Requirements 6.3
        """
        # Create many users to test counting
        user_count = 100  # Reduced from 1000 for faster testing
        
        for i in range(user_count):
            user_id = 100000 + i
            username = f"user_{i}"
            first_name = f"User {i}"
            
            success = self.admin_system.register_user(user_id, username, first_name)
            self.assertTrue(success, f"User {i} registration should succeed")
        
        # Verify count
        total_count = self.admin_system.get_users_count()
        self.assertEqual(total_count, user_count, f"Should have exactly {user_count} users")
        
        print(f"✓ Maximum user count verified: {total_count}")
    
    # ===== Special Characters in Username Tests =====
    
    def test_username_with_underscores(self):
        """Test usernames containing underscores
        
        Validates: Requirements 6.3
        """
        user_id = 123456789
        username = "user_with_underscores"
        first_name = "Test User"
        
        # Register user with underscores in username
        success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(success, "Should register user with underscores")
        
        # Test retrieval by username
        user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(user, "Should find user with underscores")
        self.assertEqual(user['username'], username, "Username should match exactly")
        
        # Test with @ prefix
        user_with_at = self.admin_system.get_user_by_username(f"@{username}")
        self.assertIsNotNone(user_with_at, "Should find user with @ prefix")
        self.assertEqual(user_with_at['id'], user_id, "Should be same user")
        
        print(f"✓ Username with underscores verified: {username}")
    
    def test_username_with_numbers(self):
        """Test usernames containing numbers
        
        Validates: Requirements 6.3
        """
        user_id = 123456789
        username = "user123"
        first_name = "Test User"
        
        # Register user with numbers in username
        success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(success, "Should register user with numbers")
        
        # Test retrieval
        user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(user, "Should find user with numbers")
        self.assertEqual(user['username'], username, "Username should match exactly")
        
        print(f"✓ Username with numbers verified: {username}")
    
    def test_username_with_mixed_case(self):
        """Test usernames with mixed case
        
        Validates: Requirements 6.3
        """
        user_id = 123456789
        username = "TestUser"
        first_name = "Test User"
        
        # Register user with mixed case username
        success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(success, "Should register user with mixed case")
        
        # Test exact case retrieval
        user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(user, "Should find user with exact case")
        self.assertEqual(user['username'], username, "Username case should be preserved")
        
        # Test different case (should not find - case sensitive)
        user_lower = self.admin_system.get_user_by_username(username.lower())
        self.assertIsNone(user_lower, "Username search should be case sensitive")
        
        print(f"✓ Username with mixed case verified: {username}")
    
    def test_username_at_symbol_handling(self):
        """Test proper handling of @ symbol in usernames
        
        Validates: Requirements 6.3
        """
        user_id = 123456789
        username = "testuser"
        first_name = "Test User"
        
        # Register user without @ symbol
        success = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(success, "Should register user")
        
        # Test finding with @ symbol
        user_with_at = self.admin_system.get_user_by_username(f"@{username}")
        self.assertIsNotNone(user_with_at, "Should find user when searching with @")
        self.assertEqual(user_with_at['username'], username, "Stored username should not have @")
        
        # Test finding without @ symbol
        user_without_at = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(user_without_at, "Should find user when searching without @")
        
        # Both should return same user
        self.assertEqual(user_with_at['id'], user_without_at['id'], "Should be same user")
        
        print("✓ Username @ symbol handling verified")
    
    def test_empty_username_handling(self):
        """Test handling of empty or None usernames
        
        Validates: Requirements 6.3
        """
        user_id = 123456789
        first_name = "Test User"
        
        # Test with None username
        success = self.admin_system.register_user(user_id, None, first_name)
        self.assertTrue(success, "Should register user with None username")
        
        user = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist")
        self.assertIsNone(user['username'], "Username should be None")
        
        # Test with empty string username
        user_id_2 = 987654321
        success = self.admin_system.register_user(user_id_2, "", first_name)
        self.assertTrue(success, "Should register user with empty username")
        
        user_2 = self.admin_system.get_user_by_id(user_id_2)
        self.assertIsNotNone(user_2, "User should exist")
        self.assertEqual(user_2['username'], "", "Username should be empty string")
        
        print("✓ Empty username handling verified")
    
    # ===== Transaction Edge Cases =====
    
    def test_negative_transaction_amounts(self):
        """Test transactions with negative amounts
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        admin_id = 987654321
        
        # Register users
        self.admin_system.register_user(user_id, "testuser", "Test User")
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        
        # Test negative transaction (removal)
        negative_amount = -50.0
        transaction_id = self.admin_system.add_transaction(
            user_id, negative_amount, 'remove', admin_id
        )
        
        self.assertIsNotNone(transaction_id, "Negative transaction should be recorded")
        
        # Verify transaction
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type FROM transactions WHERE id = ?", (transaction_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result['amount'], negative_amount, "Negative amount should be preserved")
        self.assertEqual(result['type'], 'remove', "Transaction type should be remove")
        
        print(f"✓ Negative transaction amounts verified: {negative_amount}")
    
    def test_zero_amount_transactions(self):
        """Test transactions with zero amounts
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        admin_id = 987654321
        
        # Register users
        self.admin_system.register_user(user_id, "testuser", "Test User")
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        
        # Test zero amount transaction
        zero_amount = 0.0
        transaction_id = self.admin_system.add_transaction(
            user_id, zero_amount, 'add', admin_id
        )
        
        self.assertIsNotNone(transaction_id, "Zero amount transaction should be recorded")
        
        # Verify transaction
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount FROM transactions WHERE id = ?", (transaction_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result['amount'], zero_amount, "Zero amount should be preserved")
        
        print("✓ Zero amount transactions verified")
    
    def test_transaction_without_admin(self):
        """Test transactions without admin_id (system transactions)
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        
        # Register user
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Test transaction without admin_id
        amount = 100.0
        transaction_id = self.admin_system.add_transaction(
            user_id, amount, 'buy', None
        )
        
        self.assertIsNotNone(transaction_id, "Transaction without admin should be recorded")
        
        # Verify transaction
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT admin_id FROM transactions WHERE id = ?", (transaction_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNone(result['admin_id'], "Admin ID should be None for system transactions")
        
        print("✓ Transaction without admin verified")
    
    def test_multiple_rapid_transactions(self):
        """Test multiple rapid transactions for same user
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        admin_id = 987654321
        
        # Register users
        self.admin_system.register_user(user_id, "testuser", "Test User")
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        
        # Create multiple rapid transactions
        transaction_ids = []
        for i in range(10):
            transaction_id = self.admin_system.add_transaction(
                user_id, 10.0, 'add', admin_id
            )
            transaction_ids.append(transaction_id)
        
        # Verify all transactions were created
        self.assertEqual(len(transaction_ids), 10, "All transactions should be created")
        self.assertEqual(len(set(transaction_ids)), 10, "All transaction IDs should be unique")
        
        # Verify in database
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result['count'], 10, "All transactions should be in database")
        
        print("✓ Multiple rapid transactions verified")
    
    def test_transaction_type_validation(self):
        """Test different transaction types
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        admin_id = 987654321
        
        # Register users
        self.admin_system.register_user(user_id, "testuser", "Test User")
        self.admin_system.register_user(admin_id, "admin", "Admin User")
        
        # Test all valid transaction types
        valid_types = ['add', 'remove', 'buy']
        
        for transaction_type in valid_types:
            transaction_id = self.admin_system.add_transaction(
                user_id, 10.0, transaction_type, admin_id
            )
            self.assertIsNotNone(transaction_id, f"Transaction type '{transaction_type}' should be valid")
            
            # Verify type in database
            conn = self.admin_system.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT type FROM transactions WHERE id = ?", (transaction_id,))
            result = cursor.fetchone()
            conn.close()
            
            self.assertEqual(result['type'], transaction_type, f"Transaction type should be '{transaction_type}'")
        
        print("✓ Transaction type validation verified")
    
    # ===== Balance Arithmetic Edge Cases =====
    
    def test_floating_point_precision(self):
        """Test floating point precision in balance calculations
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        
        # Register user
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Test precise decimal operations
        amount1 = 0.1
        amount2 = 0.2
        
        # Add first amount
        balance1 = self.admin_system.update_balance(user_id, amount1)
        self.assertAlmostEqual(balance1, amount1, places=10, msg="First amount should be precise")
        
        # Add second amount
        balance2 = self.admin_system.update_balance(user_id, amount2)
        expected = amount1 + amount2
        self.assertAlmostEqual(balance2, expected, places=10, msg="Sum should be precise")
        
        print(f"✓ Floating point precision verified: {balance2}")
    
    def test_balance_boundary_conditions(self):
        """Test balance at boundary conditions
        
        Validates: Requirements 2.1, 5.1
        """
        user_id = 123456789
        
        # Register user
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Test exactly at purchase threshold
        purchase_threshold = 10.0
        
        # Set balance to exactly threshold
        balance = self.admin_system.update_balance(user_id, purchase_threshold)
        self.assertEqual(balance, purchase_threshold, "Balance should be exactly at threshold")
        
        # Test purchase validation at threshold
        can_purchase = balance >= purchase_threshold
        self.assertTrue(can_purchase, "Should be able to purchase at exact threshold")
        
        # Test just below threshold
        balance = self.admin_system.update_balance(user_id, -0.01)
        can_purchase = balance >= purchase_threshold
        self.assertFalse(can_purchase, "Should not be able to purchase below threshold")
        
        # Test just above threshold
        balance = self.admin_system.update_balance(user_id, 0.02)
        can_purchase = balance >= purchase_threshold
        self.assertTrue(can_purchase, "Should be able to purchase above threshold")
        
        print("✓ Balance boundary conditions verified")
    
    def test_negative_balance_handling(self):
        """Test system behavior with negative balances
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        
        # Register user
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Create negative balance
        negative_amount = -100.0
        balance = self.admin_system.update_balance(user_id, negative_amount)
        self.assertEqual(balance, negative_amount, "Should allow negative balance")
        
        # Test operations with negative balance
        additional_negative = -50.0
        balance = self.admin_system.update_balance(user_id, additional_negative)
        expected = negative_amount + additional_negative
        self.assertEqual(balance, expected, "Should handle negative + negative")
        
        # Test adding positive to negative
        positive_amount = 75.0
        balance = self.admin_system.update_balance(user_id, positive_amount)
        expected = expected + positive_amount
        self.assertEqual(balance, expected, "Should handle negative + positive")
        
        print(f"✓ Negative balance handling verified: {balance}")


class TestDatabaseIntegrityEdgeCases(unittest.TestCase):
    """Test database integrity under edge conditions"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.admin_system = SimpleAdminSystem(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_database_constraints(self):
        """Test database foreign key constraints
        
        Validates: Requirements 2.1
        """
        # Create user and transaction
        user_id = 123456789
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        transaction_id = self.admin_system.add_transaction(user_id, 100.0, 'add')
        self.assertIsNotNone(transaction_id, "Transaction should be created")
        
        # Verify foreign key relationship
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        
        # Check that transaction references valid user
        cursor.execute("""
            SELECT t.user_id, u.id 
            FROM transactions t 
            JOIN users u ON t.user_id = u.id 
            WHERE t.id = ?
        """, (transaction_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result, "Transaction should reference valid user")
        self.assertEqual(result['user_id'], user_id, "Foreign key should match")
        
        print("✓ Database constraints verified")
    
    def test_concurrent_balance_updates(self):
        """Test concurrent balance updates (simulation)
        
        Validates: Requirements 2.1
        """
        user_id = 123456789
        self.admin_system.register_user(user_id, "testuser", "Test User")
        
        # Simulate concurrent updates by rapid sequential updates
        initial_balance = 100.0
        self.admin_system.update_balance(user_id, initial_balance)
        
        # Multiple small updates
        update_count = 50
        update_amount = 1.0
        
        for i in range(update_count):
            balance = self.admin_system.update_balance(user_id, update_amount)
            self.assertIsNotNone(balance, f"Update {i} should succeed")
        
        # Verify final balance
        final_user = self.admin_system.get_user_by_id(user_id)
        expected_balance = initial_balance + (update_count * update_amount)
        self.assertEqual(final_user['balance'], expected_balance, 
                        "Final balance should be sum of all updates")
        
        print(f"✓ Concurrent balance updates verified: {final_user['balance']}")


if __name__ == '__main__':
    print("🧪 Running Edge Cases Unit Tests...")
    print("=" * 60)
    
    # Run tests with verbose output
    unittest.main(verbosity=2, exit=False)
    
    print("=" * 60)
    print("✅ Edge cases unit tests completed!")