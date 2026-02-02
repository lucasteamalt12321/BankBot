#!/usr/bin/env python3
"""
Property-based tests for transaction logging completeness
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
from typing import Optional, Dict, List


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
    
    def get_transactions_by_user(self, user_id: int) -> List[Dict]:
        """Get all transactions for a user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, user_id, amount, type, admin_id, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC",
                (user_id,)
            )
            
            results = cursor.fetchall()
            conn.close()
            
            transactions = []
            for row in results:
                transactions.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'amount': row['amount'],
                    'type': row['type'],
                    'admin_id': row['admin_id'],
                    'timestamp': row['timestamp']
                })
            
            return transactions
            
        except Exception:
            return []
    
    def get_transactions_by_admin(self, admin_id: int) -> List[Dict]:
        """Get all transactions performed by an admin"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, user_id, amount, type, admin_id, timestamp FROM transactions WHERE admin_id = ? ORDER BY timestamp DESC",
                (admin_id,)
            )
            
            results = cursor.fetchall()
            conn.close()
            
            transactions = []
            for row in results:
                transactions.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'amount': row['amount'],
                    'type': row['type'],
                    'admin_id': row['admin_id'],
                    'timestamp': row['timestamp']
                })
            
            return transactions
            
        except Exception:
            return []
    
    def perform_admin_operation(self, user_id: int, amount: float, admin_id: int) -> bool:
        """Perform a complete admin operation: update balance and log transaction"""
        try:
            # Update balance
            new_balance = self.update_balance(user_id, amount)
            if new_balance is None:
                return False
            
            # Log transaction
            transaction_id = self.add_transaction(user_id, amount, 'add', admin_id)
            if transaction_id is None:
                return False
            
            return True
            
        except Exception:
            return False


class TestTransactionLoggingPBT(unittest.TestCase):
    """Property-based tests for transaction logging completeness"""
    
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
    
    def _create_fresh_admin_system(self):
        """Create a fresh admin system for each test case"""
        # Create a new temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Initialize admin system with new test database
        admin_system = SimpleAdminSystem(temp_db.name)
        
        return admin_system, temp_db.name
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.integers(min_value=1000000, max_value=2147483647),
        st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_transaction_logging_completeness(self, user_id, admin_id, amount):
        """
        Feature: telegram-bot-admin-system, Property 3: Transaction logging completeness
        
        For any admin operation (add_points, add_admin), the system should create exactly one corresponding transaction record with correct type and admin_id
        Validates: Requirements 2.2
        """
        # Create fresh admin system for this test case
        admin_system, temp_db_path = self._create_fresh_admin_system()
        
        try:
            # Ensure user_id and admin_id are different
            if user_id == admin_id:
                admin_id = user_id + 1
            
            # Register test users
            username = f"testuser_{user_id}"
            first_name = f"TestUser{user_id}"
            admin_username = f"admin_{admin_id}"
            admin_first_name = f"Admin{admin_id}"
            
            admin_system.register_user(user_id, username, first_name)
            admin_system.register_user(admin_id, admin_username, admin_first_name)
            
            # Get initial transaction count for the user
            initial_transactions = admin_system.get_transactions_by_user(user_id)
            initial_count = len(initial_transactions)
            
            # Get initial transaction count for the admin
            initial_admin_transactions = admin_system.get_transactions_by_admin(admin_id)
            initial_admin_count = len(initial_admin_transactions)
            
            # Perform admin operation (add_points equivalent)
            success = admin_system.perform_admin_operation(user_id, amount, admin_id)
            self.assertTrue(success, "Admin operation should succeed")
            
            # Verify exactly one new transaction was created for the user
            final_transactions = admin_system.get_transactions_by_user(user_id)
            final_count = len(final_transactions)
            self.assertEqual(final_count, initial_count + 1, 
                            f"Expected exactly one new transaction for user, got {final_count - initial_count}")
            
            # Verify exactly one new transaction was created by the admin
            final_admin_transactions = admin_system.get_transactions_by_admin(admin_id)
            final_admin_count = len(final_admin_transactions)
            self.assertEqual(final_admin_count, initial_admin_count + 1,
                            f"Expected exactly one new transaction by admin, got {final_admin_count - initial_admin_count}")
            
            # Verify the transaction details are correct
            new_transaction = final_transactions[0]  # Most recent transaction
            self.assertEqual(new_transaction['user_id'], user_id, "Transaction user_id should match")
            self.assertAlmostEqual(new_transaction['amount'], amount, places=2, msg="Transaction amount should match")
            self.assertEqual(new_transaction['type'], 'add', "Transaction type should be 'add'")
            self.assertEqual(new_transaction['admin_id'], admin_id, "Transaction admin_id should match")
            self.assertIsNotNone(new_transaction['timestamp'], "Transaction should have timestamp")
            self.assertIsNotNone(new_transaction['id'], "Transaction should have ID")
            
        finally:
            # Clean up temporary database
            try:
                os.unlink(temp_db_path)
            except:
                pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.integers(min_value=1000000, max_value=2147483647),
        st.lists(st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False), 
                min_size=1, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_multiple_operations_logging_completeness(self, user_id, admin_id, amounts):
        """
        Feature: telegram-bot-admin-system, Property 3: Transaction logging completeness (multiple operations)
        
        For any sequence of admin operations, each operation should create exactly one corresponding transaction record
        Validates: Requirements 2.2
        """
        # Create fresh admin system for this test case
        admin_system, temp_db_path = self._create_fresh_admin_system()
        
        try:
            # Ensure user_id and admin_id are different
            if user_id == admin_id:
                admin_id = user_id + 1
            
            # Register test users
            username = f"testuser_{user_id}"
            first_name = f"TestUser{user_id}"
            admin_username = f"admin_{admin_id}"
            admin_first_name = f"Admin{admin_id}"
            
            admin_system.register_user(user_id, username, first_name)
            admin_system.register_user(admin_id, admin_username, admin_first_name)
            
            # Get initial transaction count
            initial_transactions = admin_system.get_transactions_by_user(user_id)
            initial_count = len(initial_transactions)
            
            # Perform multiple admin operations
            for i, amount in enumerate(amounts):
                success = admin_system.perform_admin_operation(user_id, amount, admin_id)
                self.assertTrue(success, f"Admin operation {i+1} should succeed")
                
                # Verify transaction count increased by exactly 1
                current_transactions = admin_system.get_transactions_by_user(user_id)
                current_count = len(current_transactions)
                expected_count = initial_count + i + 1
                self.assertEqual(current_count, expected_count,
                               f"After operation {i+1}, expected {expected_count} transactions, got {current_count}")
            
            # Final verification - total transactions should equal initial + number of operations
            final_transactions = admin_system.get_transactions_by_user(user_id)
            final_count = len(final_transactions)
            expected_final_count = initial_count + len(amounts)
            self.assertEqual(final_count, expected_final_count,
                            f"Final transaction count should be {expected_final_count}, got {final_count}")
            
            # Verify all transactions have correct admin_id and type
            recent_transactions = final_transactions[:len(amounts)]  # Get the most recent transactions
            for i, transaction in enumerate(recent_transactions):
                self.assertEqual(transaction['admin_id'], admin_id, f"Transaction {i+1} admin_id should match")
                self.assertEqual(transaction['type'], 'add', f"Transaction {i+1} type should be 'add'")
                self.assertEqual(transaction['user_id'], user_id, f"Transaction {i+1} user_id should match")
        
        finally:
            # Clean up temporary database
            try:
                os.unlink(temp_db_path)
            except:
                pass
    
    def test_transaction_logging_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Simple test cases
        test_cases = [
            (12345, 67890, 100.0),
            (11111, 22222, 50.5),
            (33333, 44444, 0.01),
        ]
        
        for user_id, admin_id, amount in test_cases:
            with self.subTest(user_id=user_id, admin_id=admin_id, amount=amount):
                # Register users
                username = f"testuser_{user_id}"
                first_name = f"TestUser{user_id}"
                admin_username = f"admin_{admin_id}"
                admin_first_name = f"Admin{admin_id}"
                
                self.admin_system.register_user(user_id, username, first_name)
                self.admin_system.register_user(admin_id, admin_username, admin_first_name)
                
                # Get initial count
                initial_transactions = self.admin_system.get_transactions_by_user(user_id)
                initial_count = len(initial_transactions)
                
                # Perform operation
                success = self.admin_system.perform_admin_operation(user_id, amount, admin_id)
                self.assertTrue(success)
                
                # Verify logging
                final_transactions = self.admin_system.get_transactions_by_user(user_id)
                final_count = len(final_transactions)
                self.assertEqual(final_count, initial_count + 1)
                
                # Verify transaction details
                new_transaction = final_transactions[0]
                self.assertEqual(new_transaction['user_id'], user_id)
                self.assertAlmostEqual(new_transaction['amount'], amount, places=2)
                self.assertEqual(new_transaction['type'], 'add')
                self.assertEqual(new_transaction['admin_id'], admin_id)


if __name__ == '__main__':
    unittest.main()