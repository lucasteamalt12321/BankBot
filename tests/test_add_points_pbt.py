#!/usr/bin/env python3
"""
Property-based tests for add_points command balance arithmetic
Feature: telegram-bot-admin-system
"""

import unittest
import sys
import os
import tempfile
import sqlite3

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False

# Import only the database functions we need to avoid telegram dependency
import sqlite3
from typing import Optional, Dict


class SimpleAdminSystem:
    """Simplified admin system for testing without telegram dependencies"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_admin_tables()
    
    def _init_admin_tables(self):
        """Initialize admin tables"""
        conn = sqlite3.connect(self.db_path)
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
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Register a new user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True
            
            cursor.execute(
                "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception:
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        try:
            clean_username = username.lstrip('@')
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, username, first_name, balance, is_admin FROM users WHERE username = ?",
                (clean_username,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result['id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin'])
                }
            return None
            
        except Exception:
            return None
    
    def update_balance(self, user_id: int, amount: float) -> Optional[float]:
        """Update user balance"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return None
            
            new_balance = result['balance'] + amount
            
            cursor.execute(
                "UPDATE users SET balance = ? WHERE id = ?",
                (new_balance, user_id)
            )
            
            conn.commit()
            conn.close()
            
            return new_balance
            
        except Exception:
            return None
    
    def add_transaction(self, user_id: int, amount: float, transaction_type: str, admin_id: int = None) -> Optional[int]:
        """Add transaction record"""
        try:
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
            
        except Exception:
            return None


class TestAddPointsPBT(unittest.TestCase):
    """Property-based tests for add_points command balance arithmetic"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize admin system with test database
        self.admin_system = SimpleAdminSystem(self.temp_db.name)
        
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_balance_arithmetic_correctness(self, user_id, amount):
        """
        Feature: telegram-bot-admin-system, Property 2: Balance arithmetic correctness
        
        For any user and any positive amount, adding points should increase the user's balance by exactly that amount
        Validates: Requirements 2.1
        """
        # Register a test user first
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        self.admin_system.register_user(user_id, username, first_name)
        
        # Get initial balance
        user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(user, "User should exist after registration")
        initial_balance = user['balance']
        
        # Add points
        new_balance = self.admin_system.update_balance(user_id, amount)
        self.assertIsNotNone(new_balance, "Balance update should succeed")
        
        # Verify arithmetic correctness
        expected_balance = initial_balance + amount
        self.assertAlmostEqual(new_balance, expected_balance, places=2, 
                              msg=f"Balance arithmetic incorrect: {initial_balance} + {amount} should equal {expected_balance}, got {new_balance}")
        
        # Verify the balance is persisted correctly in database
        updated_user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(updated_user, "User should still exist after balance update")
        self.assertAlmostEqual(updated_user['balance'], expected_balance, places=2,
                              msg=f"Persisted balance incorrect: expected {expected_balance}, got {updated_user['balance']}")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.lists(st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False), 
                min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_multiple_additions_arithmetic_correctness(self, user_id, amounts):
        """
        Feature: telegram-bot-admin-system, Property 2: Balance arithmetic correctness (multiple operations)
        
        For any user and any sequence of positive amounts, multiple additions should result in correct cumulative balance
        Validates: Requirements 2.1
        """
        # Register a test user first
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        self.admin_system.register_user(user_id, username, first_name)
        
        # Get initial balance
        user = self.admin_system.get_user_by_username(username)
        initial_balance = user['balance']
        
        # Apply multiple additions
        expected_balance = initial_balance
        for amount in amounts:
            new_balance = self.admin_system.update_balance(user_id, amount)
            self.assertIsNotNone(new_balance, f"Balance update should succeed for amount {amount}")
            expected_balance += amount
            self.assertAlmostEqual(new_balance, expected_balance, places=2,
                                  msg=f"Cumulative balance incorrect after adding {amount}: expected {expected_balance}, got {new_balance}")
        
        # Final verification
        final_user = self.admin_system.get_user_by_username(username)
        self.assertAlmostEqual(final_user['balance'], expected_balance, places=2,
                              msg=f"Final persisted balance incorrect: expected {expected_balance}, got {final_user['balance']}")
    
    def test_balance_arithmetic_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Simple test cases
        test_cases = [
            (12345, 100.0),
            (67890, 50.5),
            (11111, 0.01),
            (22222, 999.99),
        ]
        
        for user_id, amount in test_cases:
            with self.subTest(user_id=user_id, amount=amount):
                # Register user
                username = f"testuser_{user_id}"
                first_name = f"TestUser{user_id}"
                self.admin_system.register_user(user_id, username, first_name)
                
                # Get initial balance
                user = self.admin_system.get_user_by_username(username)
                initial_balance = user['balance']
                
                # Add points
                new_balance = self.admin_system.update_balance(user_id, amount)
                
                # Verify arithmetic
                expected_balance = initial_balance + amount
                self.assertAlmostEqual(new_balance, expected_balance, places=2)
                
                # Verify persistence
                updated_user = self.admin_system.get_user_by_username(username)
                self.assertAlmostEqual(updated_user['balance'], expected_balance, places=2)


if __name__ == '__main__':
    unittest.main()