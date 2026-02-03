#!/usr/bin/env python3
"""
Property-based tests for automatic user registration system
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

from utils.simple_db import register_user, get_user_by_id, init_database, get_db_connection
from utils.admin_middleware import AutoRegistrationMiddleware


class TestAutoRegistrationPBT(unittest.TestCase):
    """Property-based tests for automatic user registration"""
    
    def setUp(self):
        """Setup test database"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Override DB_PATH for testing
        import utils.simple_db
        self.original_db_path = utils.simple_db.DB_PATH
        utils.simple_db.DB_PATH = self.temp_db.name
        
        # Initialize test database
        init_database()
        
    def tearDown(self):
        """Clean up after tests"""
        # Restore original DB_PATH
        import utils.simple_db
        utils.simple_db.DB_PATH = self.original_db_path
        
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(st.integers(min_value=1, max_value=2147483647))
    @settings(max_examples=100)
    def test_user_registration_idempotence(self, user_id):
        """
        Feature: telegram-bot-admin-system, Property 7: User registration idempotence
        
        For any user, multiple registration attempts should result in exactly one user record in the database
        Validates: Requirements 6.2, 6.4
        """
        # Generate test data
        username = f"testuser_{user_id}"
        first_name = f"TestUser{user_id}"
        
        # First registration
        result1 = register_user(user_id, username, first_name)
        
        # Second registration (should be idempotent)
        result2 = register_user(user_id, username, first_name)
        
        # Third registration (should be idempotent)
        result3 = register_user(user_id, username, first_name)
        
        # Verify idempotence
        self.assertTrue(result1, "First registration should succeed")
        self.assertFalse(result2, "Second registration should return False (user exists)")
        self.assertFalse(result3, "Third registration should return False (user exists)")
        
        # Verify only one user record exists
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE id = ?', (user_id,))
            count = cursor.fetchone()['count']
            self.assertEqual(count, 1, f"Expected exactly 1 user record, found {count}")
            
            # Verify user data is correct
            user = get_user_by_id(user_id)
            self.assertIsNotNone(user, "User should exist in database")
            self.assertEqual(user['id'], user_id)
            self.assertEqual(user['username'], username)
            self.assertEqual(user['first_name'], first_name)
            self.assertEqual(user['balance'], 0.0)
            self.assertFalse(user['is_admin'])
            
        finally:
            conn.close()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        st.integers(min_value=1, max_value=2147483647),
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Zs')))
    )
    @settings(max_examples=100)
    def test_user_registration_data_integrity(self, user_id, username, first_name):
        """
        Feature: telegram-bot-admin-system, Property 7: User registration idempotence (data integrity aspect)
        
        For any valid user data, registration should preserve the data correctly
        Validates: Requirements 6.3, 6.5
        """
        # Clean username (remove @ if present)
        clean_username = username.lstrip('@')
        
        # Check if user already exists (for test isolation)
        existing_user = get_user_by_id(user_id)
        if existing_user:
            # User already exists, verify idempotence by checking data integrity
            self.assertEqual(existing_user['id'], user_id, "User ID should match")
            # For existing users, we can't verify username/first_name match since they might be different
            # This is expected behavior for idempotent registration
            return
        
        # Register user (first time)
        result = register_user(user_id, username, first_name)
        self.assertTrue(result, "Registration should succeed for new user")
        
        # Verify data integrity
        user = get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist after registration")
        self.assertEqual(user['id'], user_id, "User ID should match")
        self.assertEqual(user['username'], clean_username, "Username should be cleaned and stored correctly")
        self.assertEqual(user['first_name'], first_name, "First name should be stored correctly")
        self.assertEqual(user['balance'], 0.0, "Initial balance should be 0")
        self.assertFalse(user['is_admin'], "Initial admin status should be False")
    
    def test_registration_without_hypothesis(self):
        """Fallback test when Hypothesis is not available"""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Simple test cases
        test_cases = [
            (12345, "testuser", "Test User"),
            (67890, "@testuser2", "Test User 2"),
            (11111, "user3", "User Three"),
        ]
        
        for user_id, username, first_name in test_cases:
            with self.subTest(user_id=user_id):
                # Test idempotence
                result1 = register_user(user_id, username, first_name)
                result2 = register_user(user_id, username, first_name)
                
                self.assertTrue(result1, "First registration should succeed")
                self.assertFalse(result2, "Second registration should return False")
                
                # Verify only one record
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) as count FROM users WHERE id = ?', (user_id,))
                    count = cursor.fetchone()['count']
                    self.assertEqual(count, 1, f"Expected exactly 1 user record, found {count}")
                finally:
                    conn.close()


if __name__ == '__main__':
    unittest.main()