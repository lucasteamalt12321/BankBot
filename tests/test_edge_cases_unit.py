#!/usr/bin/env python3
"""
Unit tests for edge cases and boundary conditions in the telegram bot admin system
Tests Requirements 2.1, 5.1, 6.3

This test file validates edge cases and boundary conditions for:
- Zero balances and maximum values
- Special characters in usernames
- Edge cases for transactions
- Boundary conditions for all operations
"""

import unittest
import sys
import os
import sqlite3
import tempfile
import math
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem


class TestEdgeCasesUnit(unittest.TestCase):
    """Unit tests for edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test database and admin system"""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users with various edge case scenarios
        self.setup_test_users()
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def setup_test_users(self):
        """Set up test users for edge case testing"""
        # Regular test users
        self.admin_system.register_user(123456, "testuser", "Test User")
        self.admin_system.register_user(789012, "admin_user", "Admin User")
        
        # Edge case users with special characters
        self.admin_system.register_user(111111, "user_with_underscore", "User With Underscore")
        self.admin_system.register_user(222222, "user123numbers", "User With Numbers")
        self.admin_system.register_user(333333, "a", "Single Char")
        self.admin_system.register_user(444444, "very_long_username_that_might_cause_issues", "Long Username")
        
        # Set admin status
        self.admin_system.set_admin_status(789012, True)
    
    # ========== ZERO BALANCE TESTS ==========
    
    def test_zero_balance_operations(self):
        """Test operations with zero balance
        
        Validates: Requirements 2.1, 5.1 - Zero balance edge cases
        """
        user_id = 123456
        
        # Verify initial zero balance
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], 0.0, "Initial balance should be zero")
        
        # Test adding zero points (edge case)
        new_balance = self.admin_system.update_balance(user_id, 0.0)
        self.assertEqual(new_balance, 0.0, "Adding zero should keep balance at zero")
        
        # Test subtracting from zero balance (should result in negative)
        new_balance = self.admin_system.update_balance(user_id, -10.0)
        self.assertEqual(new_balance, -10.0, "Should allow negative balance")
        
        # Test adding to negative balance
        new_balance = self.admin_system.update_balance(user_id, 5.0)
        self.assertEqual(new_balance, -5.0, "Should correctly add to negative balance")
        
        # Test bringing balance back to zero
        new_balance = self.admin_system.update_balance(user_id, 5.0)
        self.assertEqual(new_balance, 0.0, "Should return to zero balance")
    
    def test_zero_point_transactions(self):
        """Test transactions with zero points
        
        Validates: Requirements 2.1 - Zero point transaction edge cases
        """
        user_id = 123456
        admin_id = 789012
        
        # Test zero point addition transaction
        transaction_id = self.admin_system.add_transaction(user_id, 0.0, 'add', admin_id)
        self.assertIsNotNone(transaction_id, "Should allow zero point transactions")
        
        # Test zero point removal transaction
        transaction_id = self.admin_system.add_transaction(user_id, 0.0, 'remove', admin_id)
        self.assertIsNotNone(transaction_id, "Should allow zero point removal transactions")
        
        # Verify balance remains zero after zero transactions
        user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user['balance'], 0.0, "Balance should remain zero after zero transactions")
    
    # ========== MAXIMUM VALUE TESTS ==========
    
    def test_maximum_balance_values(self):
        """Test operations with maximum balance values
        
        Validates: Requirements 2.1 - Maximum value edge cases
        """
        user_id = 123456
        
        # Test with very large positive balance
        large_amount = 999999999.99
        new_balance = self.admin_system.update_balance(user_id, large_amount)
        self.assertEqual(new_balance, large_amount, "Should handle large positive balances")
        
        # Test adding to large balance
        additional_amount = 0.01
        new_balance = self.admin_system.update_balance(user_id, additional_amount)
        expected_balance = large_amount + additional_amount
        self.assertEqual(new_balance, expected_balance, "Should handle additions to large balances")
        
        # Test with very large negative balance
        user_id_2 = 222222
        large_negative = -999999999.99
        new_balance = self.admin_system.update_balance(user_id_2, large_negative)
        self.assertEqual(new_balance, large_negative, "Should handle large negative balances")
    
    def test_maximum_transaction_values(self):
        """Test transactions with maximum values
        
        Validates: Requirements 2.1 - Maximum transaction value edge cases
        """
        user_id = 123456
        admin_id = 789012
        
        # Test very large positive transaction
        large_amount = 999999999.99
        transaction_id = self.admin_system.add_transaction(user_id, large_amount, 'add', admin_id)
        self.assertIsNotNone(transaction_id, "Should handle large positive transactions")
        
        # Test very large negative transaction
        large_negative = -999999999.99
        transaction_id = self.admin_system.add_transaction(user_id, large_negative, 'remove', admin_id)
        self.assertIsNotNone(transaction_id, "Should handle large negative transactions")
    
    def test_floating_point_precision(self):
        """Test floating point precision edge cases
        
        Validates: Requirements 2.1 - Floating point precision handling
        """
        user_id = 123456
        
        # Test with very small decimal amounts
        small_amount = 0.01
        new_balance = self.admin_system.update_balance(user_id, small_amount)
        self.assertEqual(new_balance, small_amount, "Should handle small decimal amounts")
        
        # Test with many decimal places
        precise_amount = 123.456789
        new_balance = self.admin_system.update_balance(user_id, precise_amount)
        expected_balance = small_amount + precise_amount
        self.assertAlmostEqual(new_balance, expected_balance, places=6, 
                              msg="Should handle precise decimal amounts")
        
        # Test with repeating decimals
        repeating_decimal = 1.0 / 3.0  # 0.333...
        new_balance = self.admin_system.update_balance(user_id, repeating_decimal)
        self.assertIsNotNone(new_balance, "Should handle repeating decimals")
    
    # ========== SPECIAL CHARACTER TESTS ==========
    
    def test_username_with_underscores(self):
        """Test usernames with underscores
        
        Validates: Requirements 6.3 - Special character handling in usernames
        """
        # Test finding user with underscores
        user = self.admin_system.get_user_by_username("user_with_underscore")
        self.assertIsNotNone(user, "Should find user with underscores")
        self.assertEqual(user['username'], "user_with_underscore")
        
        # Test with @ symbol
        user = self.admin_system.get_user_by_username("@user_with_underscore")
        self.assertIsNotNone(user, "Should find user with @ prefix")
        
        # Test operations with underscore username
        new_balance = self.admin_system.update_balance(user['id'], 100.0)
        self.assertEqual(new_balance, 100.0, "Should handle operations with underscore usernames")
    
    def test_username_with_numbers(self):
        """Test usernames with numbers
        
        Validates: Requirements 6.3 - Numeric character handling in usernames
        """
        # Test finding user with numbers
        user = self.admin_system.get_user_by_username("user123numbers")
        self.assertIsNotNone(user, "Should find user with numbers")
        self.assertEqual(user['username'], "user123numbers")
        
        # Test operations with numeric username
        new_balance = self.admin_system.update_balance(user['id'], 50.0)
        self.assertEqual(new_balance, 50.0, "Should handle operations with numeric usernames")
    
    def test_single_character_username(self):
        """Test single character username
        
        Validates: Requirements 6.3 - Minimum length username handling
        """
        # Test finding single character user
        user = self.admin_system.get_user_by_username("a")
        self.assertIsNotNone(user, "Should find single character user")
        self.assertEqual(user['username'], "a")
        
        # Test operations with single character username
        new_balance = self.admin_system.update_balance(user['id'], 25.0)
        self.assertEqual(new_balance, 25.0, "Should handle operations with single character usernames")
    
    def test_very_long_username(self):
        """Test very long username
        
        Validates: Requirements 6.3 - Maximum length username handling
        """
        long_username = "very_long_username_that_might_cause_issues"
        
        # Test finding very long username
        user = self.admin_system.get_user_by_username(long_username)
        self.assertIsNotNone(user, "Should find user with very long username")
        self.assertEqual(user['username'], long_username)
        
        # Test operations with long username
        new_balance = self.admin_system.update_balance(user['id'], 75.0)
        self.assertEqual(new_balance, 75.0, "Should handle operations with long usernames")
    
    def test_username_case_sensitivity(self):
        """Test username case sensitivity
        
        Validates: Requirements 6.3 - Case handling in usernames
        """
        # Register user with mixed case
        self.admin_system.register_user(555555, "MixedCase", "Mixed Case User")
        
        # Test exact case match
        user = self.admin_system.get_user_by_username("MixedCase")
        self.assertIsNotNone(user, "Should find user with exact case")
        
        # Test different case (should not find - case sensitive)
        user_lower = self.admin_system.get_user_by_username("mixedcase")
        user_upper = self.admin_system.get_user_by_username("MIXEDCASE")
        
        # Note: This tests current behavior - may need adjustment based on requirements
        # If case-insensitive search is required, these assertions should be modified
        self.assertIsNone(user_lower, "Username search should be case sensitive")
        self.assertIsNone(user_upper, "Username search should be case sensitive")
    
    def test_username_with_at_symbol_handling(self):
        """Test @ symbol handling in usernames
        
        Validates: Requirements 6.3 - @ symbol handling
        """
        username = "testuser"
        
        # Test with and without @ symbol
        user_without_at = self.admin_system.get_user_by_username(username)
        user_with_at = self.admin_system.get_user_by_username(f"@{username}")
        
        self.assertIsNotNone(user_without_at, "Should find user without @ symbol")
        self.assertIsNotNone(user_with_at, "Should find user with @ symbol")
        self.assertEqual(user_without_at['id'], user_with_at['id'], 
                        "Should find same user with or without @ symbol")
    
    # ========== TRANSACTION EDGE CASES ==========
    
    def test_transaction_type_edge_cases(self):
        """Test transaction types edge cases
        
        Validates: Requirements 2.1 - Transaction type handling
        """
        user_id = 123456
        admin_id = 789012
        
        # Test all valid transaction types
        valid_types = ['add', 'remove', 'buy']
        for transaction_type in valid_types:
            transaction_id = self.admin_system.add_transaction(
                user_id, 10.0, transaction_type, admin_id
            )
            self.assertIsNotNone(transaction_id, 
                               f"Should handle '{transaction_type}' transaction type")
        
        # Test empty transaction type
        transaction_id = self.admin_system.add_transaction(user_id, 10.0, '', admin_id)
        self.assertIsNotNone(transaction_id, "Should handle empty transaction type")
        
        # Test None transaction type
        transaction_id = self.admin_system.add_transaction(user_id, 10.0, None, admin_id)
        self.assertIsNotNone(transaction_id, "Should handle None transaction type")
    
    def test_transaction_without_admin(self):
        """Test transactions without admin ID
        
        Validates: Requirements 2.1 - Transaction without admin edge case
        """
        user_id = 123456
        
        # Test transaction without admin (system transaction)
        transaction_id = self.admin_system.add_transaction(user_id, 50.0, 'add', None)
        self.assertIsNotNone(transaction_id, "Should handle transactions without admin ID")
        
        # Test transaction with admin_id = 0
        transaction_id = self.admin_system.add_transaction(user_id, 25.0, 'add', 0)
        self.assertIsNotNone(transaction_id, "Should handle transactions with admin_id = 0")
    
    def test_concurrent_balance_updates(self):
        """Test concurrent balance update edge cases
        
        Validates: Requirements 2.1 - Concurrent operation handling
        """
        user_id = 123456
        
        # Simulate rapid balance updates
        amounts = [10.0, -5.0, 20.0, -15.0, 30.0]
        expected_balance = 0.0
        
        for amount in amounts:
            new_balance = self.admin_system.update_balance(user_id, amount)
            expected_balance += amount
            self.assertEqual(new_balance, expected_balance, 
                           f"Balance should be correct after adding {amount}")
    
    # ========== BOUNDARY CONDITIONS ==========
    
    def test_user_id_boundary_conditions(self):
        """Test user ID boundary conditions
        
        Validates: Requirements 6.3 - User ID edge cases
        """
        # Test with minimum positive user ID
        min_user_id = 1
        result = self.admin_system.register_user(min_user_id, "min_user", "Min User")
        self.assertTrue(result, "Should handle minimum user ID")
        
        # Test with maximum integer user ID (within reasonable limits)
        max_user_id = 2147483647  # Max 32-bit signed integer
        result = self.admin_system.register_user(max_user_id, "max_user", "Max User")
        self.assertTrue(result, "Should handle large user ID")
        
        # Test operations with boundary user IDs
        user_min = self.admin_system.get_user_by_id(min_user_id)
        user_max = self.admin_system.get_user_by_id(max_user_id)
        
        self.assertIsNotNone(user_min, "Should find user with minimum ID")
        self.assertIsNotNone(user_max, "Should find user with maximum ID")
    
    def test_negative_user_id_handling(self):
        """Test negative user ID handling
        
        Validates: Requirements 6.3 - Negative user ID edge case
        """
        negative_user_id = -123456
        
        # Test registering user with negative ID
        result = self.admin_system.register_user(negative_user_id, "negative_user", "Negative User")
        self.assertTrue(result, "Should handle negative user ID")
        
        # Test operations with negative user ID
        user = self.admin_system.get_user_by_id(negative_user_id)
        self.assertIsNotNone(user, "Should find user with negative ID")
        
        new_balance = self.admin_system.update_balance(negative_user_id, 100.0)
        self.assertEqual(new_balance, 100.0, "Should handle operations with negative user ID")
    
    def test_empty_and_none_values(self):
        """Test empty and None value handling
        
        Validates: Requirements 6.3 - Null value handling
        """
        # Test registering user with None username
        result = self.admin_system.register_user(666666, None, "No Username")
        self.assertTrue(result, "Should handle None username")
        
        # Test registering user with empty username
        result = self.admin_system.register_user(777777, "", "Empty Username")
        self.assertTrue(result, "Should handle empty username")
        
        # Test registering user with None first_name
        result = self.admin_system.register_user(888888, "no_name", None)
        self.assertTrue(result, "Should handle None first_name")
        
        # Test registering user with empty first_name
        result = self.admin_system.register_user(999999, "empty_name", "")
        self.assertTrue(result, "Should handle empty first_name")
    
    def test_database_connection_edge_cases(self):
        """Test database connection edge cases
        
        Validates: Requirements 2.1 - Database connection handling
        """
        # Test operations after multiple connections
        for i in range(10):
            user_count = self.admin_system.get_users_count()
            self.assertGreaterEqual(user_count, 0, "Should handle multiple connection requests")
        
        # Test operations with rapid successive calls
        user_id = 123456
        for i in range(5):
            balance = self.admin_system.update_balance(user_id, 1.0)
            self.assertIsNotNone(balance, "Should handle rapid successive operations")
    
    def test_admin_status_boundary_conditions(self):
        """Test admin status boundary conditions
        
        Validates: Requirements 2.1 - Admin status edge cases
        """
        user_id = 123456
        
        # Test setting admin status multiple times
        for i in range(3):
            result = self.admin_system.set_admin_status(user_id, True)
            self.assertTrue(result, "Should handle repeated admin status setting")
            
            is_admin = self.admin_system.is_admin(user_id)
            self.assertTrue(is_admin, "Admin status should remain True")
        
        # Test toggling admin status
        for i in range(3):
            # Set to False
            result = self.admin_system.set_admin_status(user_id, False)
            self.assertTrue(result, "Should handle admin status removal")
            self.assertFalse(self.admin_system.is_admin(user_id), "Should not be admin")
            
            # Set to True
            result = self.admin_system.set_admin_status(user_id, True)
            self.assertTrue(result, "Should handle admin status granting")
            self.assertTrue(self.admin_system.is_admin(user_id), "Should be admin")
    
    def test_balance_precision_edge_cases(self):
        """Test balance precision edge cases
        
        Validates: Requirements 2.1, 5.1 - Balance precision handling
        """
        user_id = 123456
        
        # Test very small amounts
        tiny_amount = 0.001
        new_balance = self.admin_system.update_balance(user_id, tiny_amount)
        self.assertAlmostEqual(new_balance, tiny_amount, places=3, 
                              msg="Should handle tiny amounts")
        
        # Test amounts that might cause floating point issues
        problematic_amounts = [0.1, 0.2, 0.3]  # These can cause floating point precision issues
        expected_total = tiny_amount
        
        for amount in problematic_amounts:
            new_balance = self.admin_system.update_balance(user_id, amount)
            expected_total += amount
            self.assertAlmostEqual(new_balance, expected_total, places=10,
                                 msg=f"Should handle floating point precision for {amount}")
    
    def test_transaction_timestamp_edge_cases(self):
        """Test transaction timestamp edge cases
        
        Validates: Requirements 2.1 - Transaction timestamp handling
        """
        user_id = 123456
        admin_id = 789012
        
        # Create multiple transactions rapidly
        transaction_ids = []
        for i in range(10):
            transaction_id = self.admin_system.add_transaction(
                user_id, 1.0, 'add', admin_id
            )
            transaction_ids.append(transaction_id)
        
        # All transactions should be created successfully
        for transaction_id in transaction_ids:
            self.assertIsNotNone(transaction_id, "Should create rapid transactions")
        
        # All transaction IDs should be unique
        self.assertEqual(len(transaction_ids), len(set(transaction_ids)), 
                        "All transaction IDs should be unique")
    
    def test_user_count_edge_cases(self):
        """Test user count edge cases
        
        Validates: Requirements 2.1 - User count accuracy
        """
        initial_count = self.admin_system.get_users_count()
        
        # Add users and verify count increases
        new_user_ids = [1000001, 1000002, 1000003]
        for user_id in new_user_ids:
            self.admin_system.register_user(user_id, f"user_{user_id}", f"User {user_id}")
            current_count = self.admin_system.get_users_count()
            self.assertGreater(current_count, initial_count, 
                             "User count should increase after adding users")
        
        final_count = self.admin_system.get_users_count()
        expected_count = initial_count + len(new_user_ids)
        self.assertEqual(final_count, expected_count, 
                        "Final user count should match expected count")
    
    def test_nonexistent_user_operations(self):
        """Test operations on nonexistent users
        
        Validates: Requirements 2.1, 5.1 - Nonexistent user handling
        """
        nonexistent_user_id = 9999999
        
        # Test balance update on nonexistent user
        result = self.admin_system.update_balance(nonexistent_user_id, 100.0)
        self.assertIsNone(result, "Should return None for nonexistent user balance update")
        
        # Test admin status check on nonexistent user
        is_admin = self.admin_system.is_admin(nonexistent_user_id)
        self.assertFalse(is_admin, "Nonexistent user should not be admin")
        
        # Test admin status setting on nonexistent user
        result = self.admin_system.set_admin_status(nonexistent_user_id, True)
        self.assertFalse(result, "Should fail to set admin status for nonexistent user")
        
        # Test getting nonexistent user by ID
        user = self.admin_system.get_user_by_id(nonexistent_user_id)
        self.assertIsNone(user, "Should return None for nonexistent user")
        
        # Test getting nonexistent user by username
        user = self.admin_system.get_user_by_username("nonexistent_user")
        self.assertIsNone(user, "Should return None for nonexistent username")
    
    def test_duplicate_user_registration(self):
        """Test duplicate user registration edge cases
        
        Validates: Requirements 6.3 - Duplicate registration handling
        """
        user_id = 1234567
        username = "duplicate_user"
        first_name = "Duplicate User"
        
        # Register user first time
        result1 = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(result1, "First registration should succeed")
        
        # Register same user again
        result2 = self.admin_system.register_user(user_id, username, first_name)
        self.assertTrue(result2, "Duplicate registration should return True (idempotent)")
        
        # Verify only one user exists
        user = self.admin_system.get_user_by_id(user_id)
        self.assertIsNotNone(user, "User should exist")
        self.assertEqual(user['username'], username, "Username should match")
        
        # Register same user with different username (should not update)
        result3 = self.admin_system.register_user(user_id, "different_username", first_name)
        self.assertTrue(result3, "Registration with different username should succeed")
        
        # Verify original username is preserved
        user_after = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(user_after['username'], username, 
                        "Original username should be preserved")


if __name__ == '__main__':
    unittest.main()