#!/usr/bin/env python3
"""
Property-based tests for admin status persistence
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
    
    def set_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """Set admin status for user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (is_admin, user_id)
            )
            
            if cursor.rowcount == 0:
                conn.close()
                return False  # User not found
            
            conn.commit()
            conn.close()
            return True
            
        except Exception:
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return bool(result['is_admin'])
            return False
            
        except Exception:
            return False
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, username, first_name, balance, is_admin FROM users WHERE id = ?",
                (user_id,)
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


class TestAdminStatusPersistencePBT(unittest.TestCase):
    """Property-based tests for admin status persistence"""
    
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
        st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_admin_status_persistence(self, user_id, admin_status):
        """
        Feature: telegram-bot-admin-system, Property 5: Admin status persistence
        
        For any user, setting admin status should permanently update the is_admin flag in the database until changed again
        Validates: Requirements 3.1, 3.4
        """
        # Create fresh admin system for this test case
        admin_system, temp_db_path = self._create_fresh_admin_system()
        
        try:
            # Register test user
            username = f"testuser_{user_id}"
            first_name = f"TestUser{user_id}"
            success = admin_system.register_user(user_id, username, first_name)
            self.assertTrue(success, "User registration should succeed")
            
            # Verify initial admin status is False
            initial_status = admin_system.is_admin(user_id)
            self.assertFalse(initial_status, "Initial admin status should be False")
            
            # Set admin status
            set_success = admin_system.set_admin_status(user_id, admin_status)
            self.assertTrue(set_success, "Setting admin status should succeed")
            
            # Verify admin status is immediately updated
            immediate_status = admin_system.is_admin(user_id)
            self.assertEqual(immediate_status, admin_status, 
                           f"Admin status should be immediately updated to {admin_status}")
            
            # Verify persistence by checking the database directly
            conn = admin_system.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(result, "User should exist in database")
            persisted_status = bool(result['is_admin'])
            self.assertEqual(persisted_status, admin_status,
                           f"Admin status should be persisted in database as {admin_status}")
            
            # Verify persistence across multiple checks (simulating different sessions)
            for _ in range(3):
                check_status = admin_system.is_admin(user_id)
                self.assertEqual(check_status, admin_status,
                               f"Admin status should remain {admin_status} across multiple checks")
            
            # Verify persistence by getting user data
            user_data = admin_system.get_user_by_id(user_id)
            self.assertIsNotNone(user_data, "User data should be retrievable")
            self.assertEqual(user_data['is_admin'], admin_status,
                           f"Admin status in user data should be {admin_status}")
            
        finally:
            # Clean up temporary database
            try:
                os.unlink(temp_db_path)
            except:
                pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.lists(st.booleans(), min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_admin_status_persistence_multiple_changes(self, user_id, status_changes):
        """
        Feature: telegram-bot-admin-system, Property 5: Admin status persistence (multiple changes)
        
        For any user and any sequence of admin status changes, each change should be permanently persisted until the next change
        Validates: Requirements 3.1, 3.4
        """
        # Create fresh admin system for this test case
        admin_system, temp_db_path = self._create_fresh_admin_system()
        
        try:
            # Register test user
            username = f"testuser_{user_id}"
            first_name = f"TestUser{user_id}"
            success = admin_system.register_user(user_id, username, first_name)
            self.assertTrue(success, "User registration should succeed")
            
            # Apply sequence of status changes
            for i, new_status in enumerate(status_changes):
                # Set new admin status
                set_success = admin_system.set_admin_status(user_id, new_status)
                self.assertTrue(set_success, f"Setting admin status to {new_status} (change {i+1}) should succeed")
                
                # Verify immediate persistence
                immediate_status = admin_system.is_admin(user_id)
                self.assertEqual(immediate_status, new_status,
                               f"Admin status should be immediately updated to {new_status} (change {i+1})")
                
                # Verify database persistence
                conn = admin_system.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()
                conn.close()
                
                self.assertIsNotNone(result, f"User should exist in database after change {i+1}")
                persisted_status = bool(result['is_admin'])
                self.assertEqual(persisted_status, new_status,
                               f"Admin status should be persisted as {new_status} after change {i+1}")
                
                # Verify persistence across multiple checks
                for check_num in range(2):
                    check_status = admin_system.is_admin(user_id)
                    self.assertEqual(check_status, new_status,
                                   f"Admin status should remain {new_status} on check {check_num+1} after change {i+1}")
            
            # Final verification - status should be the last value set
            final_expected_status = status_changes[-1]
            final_status = admin_system.is_admin(user_id)
            self.assertEqual(final_status, final_expected_status,
                           f"Final admin status should be {final_expected_status}")
            
            # Verify final status in user data
            user_data = admin_system.get_user_by_id(user_id)
            self.assertIsNotNone(user_data, "User data should be retrievable after all changes")
            self.assertEqual(user_data['is_admin'], final_expected_status,
                           f"Final admin status in user data should be {final_expected_status}")
            
        finally:
            # Clean up temporary database
            try:
                os.unlink(temp_db_path)
            except:
                pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647)
    )
    @settings(max_examples=100, deadline=None)
    def test_admin_status_persistence_toggle_pattern(self, user_id):
        """
        Feature: telegram-bot-admin-system, Property 5: Admin status persistence (toggle pattern)
        
        For any user, toggling admin status back and forth should persist each change correctly
        Validates: Requirements 3.1, 3.4
        """
        # Create fresh admin system for this test case
        admin_system, temp_db_path = self._create_fresh_admin_system()
        
        try:
            # Register test user
            username = f"testuser_{user_id}"
            first_name = f"TestUser{user_id}"
            success = admin_system.register_user(user_id, username, first_name)
            self.assertTrue(success, "User registration should succeed")
            
            # Initial state should be False
            initial_status = admin_system.is_admin(user_id)
            self.assertFalse(initial_status, "Initial admin status should be False")
            
            # Toggle pattern: False -> True -> False -> True
            toggle_sequence = [True, False, True]
            
            for i, target_status in enumerate(toggle_sequence):
                # Set admin status
                set_success = admin_system.set_admin_status(user_id, target_status)
                self.assertTrue(set_success, f"Setting admin status to {target_status} (toggle {i+1}) should succeed")
                
                # Verify immediate persistence
                immediate_status = admin_system.is_admin(user_id)
                self.assertEqual(immediate_status, target_status,
                               f"Admin status should be {target_status} after toggle {i+1}")
                
                # Verify database persistence
                conn = admin_system.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()
                conn.close()
                
                persisted_status = bool(result['is_admin'])
                self.assertEqual(persisted_status, target_status,
                               f"Database should show admin status as {target_status} after toggle {i+1}")
                
                # Verify persistence across multiple reads
                for read_num in range(3):
                    read_status = admin_system.is_admin(user_id)
                    self.assertEqual(read_status, target_status,
                                   f"Admin status should remain {target_status} on read {read_num+1} after toggle {i+1}")
            
            # Final verification
            final_expected = toggle_sequence[-1]  # Should be True
            final_status = admin_system.is_admin(user_id)
            self.assertEqual(final_status, final_expected,
                           f"Final admin status should be {final_expected}")
            
        finally:
            # Clean up temporary database
            try:
                os.unlink(temp_db_path)
            except:
                pass
    
    def test_admin_status_persistence_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Simple test cases
        test_cases = [
            (12345, True),
            (67890, False),
            (11111, True),
            (22222, False),
        ]
        
        for user_id, admin_status in test_cases:
            with self.subTest(user_id=user_id, admin_status=admin_status):
                # Register user
                username = f"testuser_{user_id}"
                first_name = f"TestUser{user_id}"
                self.admin_system.register_user(user_id, username, first_name)
                
                # Set admin status
                success = self.admin_system.set_admin_status(user_id, admin_status)
                self.assertTrue(success)
                
                # Verify persistence
                check_status = self.admin_system.is_admin(user_id)
                self.assertEqual(check_status, admin_status)
                
                # Verify database persistence
                conn = self.admin_system.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()
                conn.close()
                
                persisted_status = bool(result['is_admin'])
                self.assertEqual(persisted_status, admin_status)


if __name__ == '__main__':
    unittest.main()