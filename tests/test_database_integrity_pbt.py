#!/usr/bin/env python3
"""
Property-based tests for database integrity preservation
Feature: telegram-bot-admin-system
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import logging
from typing import List, Tuple, Optional, Dict, Any

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings, assume
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False


class DatabaseIntegritySystem:
    """Simplified system for testing database integrity without telegram dependencies"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Initialize database tables with foreign key constraints"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
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
        """Get database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Register a new user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True  # User already exists
            
            cursor.execute(
                "INSERT INTO users (id, username, first_name, balance, is_admin) VALUES (?, ?, ?, 0, FALSE)",
                (user_id, username, first_name)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            return False
    
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
    
    def set_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """Set admin status for user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (is_admin, user_id)
            )
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
            
        except Exception:
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (this should fail if there are dependent transactions)"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return success
            
        except Exception:
            # Foreign key constraint violation expected
            return False
    
    def check_foreign_key_integrity(self) -> List[Dict[str, Any]]:
        """Check for foreign key constraint violations"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check for orphaned transactions (user_id not in users)
            cursor.execute('''
                SELECT t.id, t.user_id, t.type, t.amount 
                FROM transactions t 
                LEFT JOIN users u ON t.user_id = u.id 
                WHERE u.id IS NULL
            ''')
            orphaned_user_transactions = [dict(row) for row in cursor.fetchall()]
            
            # Check for orphaned transactions (admin_id not in users, but admin_id is not null)
            cursor.execute('''
                SELECT t.id, t.admin_id, t.type, t.amount 
                FROM transactions t 
                LEFT JOIN users u ON t.admin_id = u.id 
                WHERE t.admin_id IS NOT NULL AND u.id IS NULL
            ''')
            orphaned_admin_transactions = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            violations = []
            for tx in orphaned_user_transactions:
                violations.append({
                    'type': 'orphaned_user_transaction',
                    'transaction_id': tx['id'],
                    'user_id': tx['user_id'],
                    'details': f"Transaction {tx['id']} references non-existent user {tx['user_id']}"
                })
            
            for tx in orphaned_admin_transactions:
                violations.append({
                    'type': 'orphaned_admin_transaction',
                    'transaction_id': tx['id'],
                    'admin_id': tx['admin_id'],
                    'details': f"Transaction {tx['id']} references non-existent admin {tx['admin_id']}"
                })
            
            return violations
            
        except Exception as e:
            return [{'type': 'check_error', 'details': str(e)}]
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, username, first_name, balance, is_admin FROM users")
            users = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return users
            
        except Exception:
            return []
    
    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """Get all transactions"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, user_id, amount, type, admin_id FROM transactions")
            transactions = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return transactions
            
        except Exception:
            return []


class TestDatabaseIntegrityPBT(unittest.TestCase):
    """Property-based tests for database integrity preservation"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize database system
        self.db_system = DatabaseIntegritySystem(self.temp_db.name)
        
        # Create some initial users for testing
        self.test_users = [
            {'id': 1001, 'username': 'testuser1', 'first_name': 'Test User 1'},
            {'id': 1002, 'username': 'testuser2', 'first_name': 'Test User 2'},
            {'id': 1003, 'username': 'admin1', 'first_name': 'Admin User 1'},
        ]
        
        for user in self.test_users:
            self.db_system.register_user(user['id'], user['username'], user['first_name'])
        
        # Make one user an admin
        self.db_system.set_admin_status(1003, True)
    
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.lists(
            st.one_of(
                # Register user operation
                st.tuples(
                    st.just('register_user'),
                    st.integers(min_value=2000, max_value=2010),  # Smaller range
                    st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
                    st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')))
                ),
                # Update balance operation
                st.tuples(
                    st.just('update_balance'),
                    st.sampled_from([1001, 1002, 1003]),  # Existing users
                    st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False)
                ),
                # Add transaction operation
                st.tuples(
                    st.just('add_transaction'),
                    st.sampled_from([1001, 1002, 1003]),  # Existing users
                    st.floats(min_value=1.0, max_value=25.0, allow_nan=False, allow_infinity=False),
                    st.sampled_from(['add', 'remove', 'buy']),
                    st.one_of(st.none(), st.sampled_from([1003]))  # Admin ID (only 1003 is admin)
                ),
                # Set admin status operation
                st.tuples(
                    st.just('set_admin_status'),
                    st.sampled_from([1001, 1002, 1003]),  # Existing users
                    st.booleans()
                )
            ),
            min_size=1,
            max_size=10  # Reduced from 20
        )
    )
    @settings(max_examples=50, deadline=10000)
    def test_database_integrity_preservation(self, operations):
        """
        Feature: telegram-bot-admin-system, Property 9: Database integrity preservation
        
        For any sequence of operations, foreign key constraints should remain valid 
        and no orphaned records should exist
        Validates: Requirements 7.3, 8.6
        """
        # Execute the sequence of operations
        for operation in operations:
            op_type = operation[0]
            
            try:
                if op_type == 'register_user':
                    _, user_id, username, first_name = operation
                    self.db_system.register_user(user_id, username, first_name)
                
                elif op_type == 'update_balance':
                    _, user_id, amount = operation
                    self.db_system.update_balance(user_id, amount)
                
                elif op_type == 'add_transaction':
                    _, user_id, amount, tx_type, admin_id = operation
                    self.db_system.add_transaction(user_id, amount, tx_type, admin_id)
                
                elif op_type == 'set_admin_status':
                    _, user_id, is_admin = operation
                    self.db_system.set_admin_status(user_id, is_admin)
                
            except Exception:
                # Operations may fail, but should not leave database in inconsistent state
                pass
        
        # Check database integrity after all operations
        violations = self.db_system.check_foreign_key_integrity()
        
        # Assert no foreign key violations exist
        self.assertEqual(
            len(violations), 0,
            f"Database integrity violations found: {violations}"
        )
        
        # Additional checks: verify that all transactions reference existing users
        all_users = self.db_system.get_all_users()
        all_transactions = self.db_system.get_all_transactions()
        
        user_ids = {user['id'] for user in all_users}
        
        for transaction in all_transactions:
            # Check user_id exists
            self.assertIn(
                transaction['user_id'], user_ids,
                f"Transaction {transaction['id']} references non-existent user {transaction['user_id']}"
            )
            
            # Check admin_id exists (if not null)
            if transaction['admin_id'] is not None:
                self.assertIn(
                    transaction['admin_id'], user_ids,
                    f"Transaction {transaction['id']} references non-existent admin {transaction['admin_id']}"
                )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1001, max_value=1003),  # Existing user IDs
        st.integers(min_value=1, max_value=10)  # Number of transactions to create
    )
    @settings(max_examples=50, deadline=10000)
    def test_user_deletion_prevents_orphaned_transactions(self, user_id, num_transactions):
        """
        Feature: telegram-bot-admin-system, Property 9: Database integrity preservation (deletion aspect)
        
        Attempting to delete a user with existing transactions should fail,
        preventing orphaned transaction records
        Validates: Requirements 7.3, 8.6
        """
        # Create some transactions for the user
        for i in range(num_transactions):
            self.db_system.add_transaction(user_id, 10.0, 'add', 1003)
        
        # Attempt to delete the user (should fail due to foreign key constraint)
        deletion_result = self.db_system.delete_user(user_id)
        
        # Deletion should fail to preserve integrity
        self.assertFalse(
            deletion_result,
            f"User deletion should fail when transactions exist, but succeeded for user {user_id}"
        )
        
        # Verify user still exists
        all_users = self.db_system.get_all_users()
        user_ids = {user['id'] for user in all_users}
        self.assertIn(
            user_id, user_ids,
            f"User {user_id} should still exist after failed deletion attempt"
        )
        
        # Verify no orphaned transactions exist
        violations = self.db_system.check_foreign_key_integrity()
        self.assertEqual(
            len(violations), 0,
            f"Database integrity violations found after deletion attempt: {violations}"
        )
    
    def test_database_integrity_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Simple test cases for database integrity
        
        # Test 1: Add transaction for existing user
        result = self.db_system.add_transaction(1001, 25.0, 'add', 1003)
        self.assertIsNotNone(result, "Transaction should be created successfully")
        
        violations = self.db_system.check_foreign_key_integrity()
        self.assertEqual(len(violations), 0, "No integrity violations should exist")
        
        # Test 2: Attempt to add transaction for non-existent user (should fail)
        result = self.db_system.add_transaction(9999, 25.0, 'add', 1003)
        self.assertIsNone(result, "Transaction creation should fail for non-existent user")
        
        violations = self.db_system.check_foreign_key_integrity()
        self.assertEqual(len(violations), 0, "No integrity violations should exist after failed operation")
        
        # Test 3: Attempt to delete user with transactions (should fail)
        self.db_system.add_transaction(1002, 15.0, 'buy', None)
        deletion_result = self.db_system.delete_user(1002)
        self.assertFalse(deletion_result, "User deletion should fail when transactions exist")
        
        violations = self.db_system.check_foreign_key_integrity()
        self.assertEqual(len(violations), 0, "No integrity violations should exist after failed deletion")


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run tests
    unittest.main(verbosity=2)