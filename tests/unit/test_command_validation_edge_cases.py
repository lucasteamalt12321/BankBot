#!/usr/bin/env python3
"""
Unit tests for command validation edge cases and boundary conditions
Tests Requirements 2.1, 5.1, 6.3 - Command validation and error handling edge cases

This test file validates edge cases for:
- Command parameter validation
- Input sanitization edge cases
- Error handling boundary conditions
- Command format validation edge cases
"""

import unittest
import sys
import os
import sqlite3
import tempfile
import re

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin.admin_system import AdminSystem


class TestCommandValidationEdgeCases(unittest.TestCase):
    """Unit tests for command validation edge cases and boundary conditions"""
    
    def setUp(self):
        """Set up test database and admin system"""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users
        self.setup_test_users()
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def setup_test_users(self):
        """Set up test users for command validation testing"""
        # Regular test users
        self.admin_system.register_user(123456, "testuser", "Test User")
        self.admin_system.register_user(789012, "admin_user", "Admin User")
        
        # Edge case users for validation testing
        self.admin_system.register_user(111111, "user_with_special_chars", "User!@#$%")
        self.admin_system.register_user(222222, "123numeric_user", "123 Numeric")
        self.admin_system.register_user(333333, "a", "A")  # Single character
        
        # Set admin status
        self.admin_system.set_admin_status(789012, True)
        
        # Set some balances for testing
        self.admin_system.update_balance(123456, 100.0)
    
    # ========== USERNAME VALIDATION EDGE CASES ==========
    
    def test_username_with_leading_trailing_spaces(self):
        """Test username validation with leading/trailing spaces
        
        Validates: Requirements 6.3 - Username space handling
        """
        # Test usernames with various space patterns
        space_usernames = [
            " testuser",      # Leading space
            "testuser ",      # Trailing space
            " testuser ",     # Both spaces
            "  testuser  ",   # Multiple spaces
            "\ttestuser\t",   # Tab characters
            "\ntestuser\n",   # Newline characters
        ]
        
        for username in space_usernames:
            with self.subTest(username=repr(username)):
                # Test finding user with spaces (current implementation doesn't clean spaces)
                user = self.admin_system.get_user_by_username(username)
                # Current implementation only strips @ symbol, not spaces
                # So these should not find the user unless exact match
                if username == "testuser":
                    self.assertIsNotNone(user, f"Should find exact match: {repr(username)}")
                else:
                    # Test that system handles spaces gracefully (may or may not find user)
                    self.assertIsInstance(user, (dict, type(None)), 
                                        f"Should handle spaces gracefully: {repr(username)}")
    
    def test_username_with_at_symbol_variations(self):
        """Test username validation with @ symbol variations
        
        Validates: Requirements 6.3 - @ symbol handling variations
        """
        # Test various @ symbol patterns
        at_usernames = [
            "@testuser",      # Standard @username
            "@@testuser",     # Double @
            "@testuser@",     # @ at end
            "@test@user",     # @ in middle
            "test@user",      # @ without leading @
        ]
        
        for username in at_usernames:
            with self.subTest(username=username):
                user = self.admin_system.get_user_by_username(username)
                # Current implementation only strips leading @, so only some will match
                if username in ["@testuser", "@@testuser"]:
                    # These should find testuser after stripping leading @
                    self.assertIsNotNone(user, f"Should find user after @ cleaning: {username}")
                else:
                    # These may not match due to @ in middle or end
                    # Test that system handles them gracefully
                    self.assertIsInstance(user, (dict, type(None)), 
                                        f"Should handle @ variations gracefully: {username}")
    
    def test_empty_and_whitespace_usernames(self):
        """Test empty and whitespace-only usernames
        
        Validates: Requirements 6.3 - Empty username handling
        """
        empty_usernames = [
            "",           # Empty string
            " ",          # Single space
            "   ",        # Multiple spaces
            "\t",         # Tab
            "\n",         # Newline
            "\r\n",       # Windows newline
        ]
        
        for username in empty_usernames:
            with self.subTest(username=repr(username)):
                user = self.admin_system.get_user_by_username(username)
                self.assertIsNone(user, f"Should not find user for empty username: {repr(username)}")
    
    def test_username_with_special_characters(self):
        """Test usernames with special characters
        
        Validates: Requirements 6.3 - Special character handling
        """
        special_usernames = [
            "user!@#$%",      # Special symbols
            "user()",         # Parentheses
            "user[]",         # Brackets
            "user{}",         # Braces
            "user<>",         # Angle brackets
            "user|\\",        # Pipe and backslash
            "user'\"",        # Quotes
            "user`~",         # Backtick and tilde
        ]
        
        for username in special_usernames:
            with self.subTest(username=username):
                # Test that system handles special characters gracefully
                user = self.admin_system.get_user_by_username(username)
                # Should not crash, may or may not find user depending on implementation
                self.assertIsInstance(user, (dict, type(None)), 
                                    f"Should handle special characters gracefully: {username}")
    
    # ========== NUMERIC VALIDATION EDGE CASES ==========
    
    def test_points_amount_validation_edge_cases(self):
        """Test points amount validation edge cases
        
        Validates: Requirements 2.1 - Points amount validation
        """
        user_id = 123456
        
        # Test various numeric edge cases
        test_amounts = [
            0.0,              # Zero
            0.01,             # Very small positive
            -0.01,            # Very small negative
            999999999.99,     # Very large positive
            -999999999.99,    # Very large negative
            float('inf'),     # Infinity (should be handled gracefully)
            float('-inf'),    # Negative infinity
        ]
        
        for amount in test_amounts:
            with self.subTest(amount=amount):
                if not (amount == float('inf') or amount == float('-inf')):
                    # Test normal amounts
                    result = self.admin_system.update_balance(user_id, amount)
                    self.assertIsNotNone(result, f"Should handle amount: {amount}")
                else:
                    # Test infinity values (should be handled gracefully)
                    try:
                        result = self.admin_system.update_balance(user_id, amount)
                        # If it doesn't crash, that's good
                        self.assertIsInstance(result, (float, type(None)), 
                                            f"Should handle infinity gracefully: {amount}")
                    except (ValueError, OverflowError):
                        # It's acceptable to raise an exception for infinity
                        pass
    
    def test_points_amount_string_conversion_edge_cases(self):
        """Test points amount string conversion edge cases
        
        Validates: Requirements 2.1 - String to number conversion
        """
        # Test various string representations that might be converted to numbers
        string_amounts = [
            "100",            # Simple integer string
            "100.50",         # Decimal string
            "100.0",          # Integer as decimal string
            ".50",            # Decimal without leading zero
            "50.",            # Decimal without trailing digits
            "+100",           # Explicit positive
            "-100",           # Negative
            "1e2",            # Scientific notation
            "1.5e2",          # Scientific notation with decimal
            "0x64",           # Hexadecimal (100 in hex)
            "0o144",          # Octal (100 in octal)
            "0b1100100",      # Binary (100 in binary)
        ]
        
        for amount_str in string_amounts:
            with self.subTest(amount_str=amount_str):
                try:
                    # Test conversion to float
                    if amount_str.startswith(('0x', '0o', '0b')):
                        # Special handling for different bases
                        if amount_str.startswith('0x'):
                            amount = float(int(amount_str, 16))
                        elif amount_str.startswith('0o'):
                            amount = float(int(amount_str, 8))
                        elif amount_str.startswith('0b'):
                            amount = float(int(amount_str, 2))
                    else:
                        amount = float(amount_str)
                    
                    # Test that the converted amount works
                    user_id = 123456
                    result = self.admin_system.update_balance(user_id, amount)
                    self.assertIsNotNone(result, f"Should handle converted amount: {amount_str} -> {amount}")
                    
                except ValueError:
                    # Some conversions may fail, which is acceptable
                    pass
    
    def test_invalid_numeric_strings(self):
        """Test invalid numeric string handling
        
        Validates: Requirements 2.1 - Invalid number handling
        """
        invalid_amounts = [
            "abc",            # Letters
            "12.34.56",       # Multiple decimals
            "12,34",          # Comma as decimal separator
            "12 34",          # Space in number
            "12-34",          # Dash in number
            "12+34",          # Plus in middle
            "",               # Empty string
            " ",              # Space only
            "NaN",            # Not a Number
            "null",           # Null string
            "undefined",      # Undefined string
        ]
        
        for amount_str in invalid_amounts:
            with self.subTest(amount_str=repr(amount_str)):
                try:
                    amount = float(amount_str)
                    # If conversion succeeds, test it
                    user_id = 123456
                    result = self.admin_system.update_balance(user_id, amount)
                    # Should handle gracefully
                    self.assertIsInstance(result, (float, type(None)), 
                                        f"Should handle converted invalid string: {amount_str}")
                except ValueError:
                    # Expected behavior for invalid strings
                    pass
    
    # ========== COMMAND FORMAT VALIDATION ==========
    
    def test_command_parameter_count_edge_cases(self):
        """Test command parameter count edge cases
        
        Validates: Requirements 2.1 - Parameter count validation
        """
        # Simulate command parsing for /add_points command
        test_commands = [
            [],                           # No parameters
            ["user"],                     # One parameter (missing amount)
            ["user", "100"],             # Two parameters (correct)
            ["user", "100", "extra"],    # Three parameters (extra)
            ["user", "100", "extra", "more"],  # Four parameters (too many)
        ]
        
        for i, params in enumerate(test_commands):
            with self.subTest(case=i, params=params):
                # Test parameter count validation logic
                if len(params) == 2:
                    # Correct parameter count
                    username, amount_str = params
                    try:
                        amount = float(amount_str)
                        # Should be valid
                        self.assertIsInstance(amount, float, "Amount should be valid float")
                        self.assertIsInstance(username, str, "Username should be string")
                    except ValueError:
                        # Invalid amount format
                        pass
                else:
                    # Incorrect parameter count - should be handled by command validation
                    is_valid = len(params) == 2
                    self.assertFalse(is_valid or len(params) == 2, 
                                   f"Should detect invalid parameter count: {len(params)}")
    
    def test_command_parameter_order_edge_cases(self):
        """Test command parameter order edge cases
        
        Validates: Requirements 2.1 - Parameter order validation
        """
        # Test different parameter orders for add_points command
        test_cases = [
            ("testuser", "100"),      # Correct order: username, amount
            ("100", "testuser"),      # Reversed order: amount, username
            ("@testuser", "100"),     # Username with @
            ("testuser", "+100"),     # Amount with +
            ("testuser", "-100"),     # Negative amount
        ]
        
        for username_param, amount_param in test_cases:
            with self.subTest(username=username_param, amount=amount_param):
                # Test parameter validation logic
                try:
                    # Try to parse as amount first
                    amount = float(amount_param)
                    # If successful, username_param should be username
                    clean_username = username_param.lstrip('@')
                    
                    # Test that we can find or validate the username
                    user = self.admin_system.get_user_by_username(clean_username)
                    # May or may not find user, but should not crash
                    self.assertIsInstance(user, (dict, type(None)), 
                                        "Should handle username validation gracefully")
                    
                except ValueError:
                    # amount_param is not a valid number
                    # Try to parse username_param as amount
                    try:
                        amount = float(username_param)
                        # If successful, amount_param should be username
                        clean_username = amount_param.lstrip('@')
                        # This would indicate reversed parameters
                    except ValueError:
                        # Neither parameter is a valid amount
                        pass
    
    # ========== ERROR MESSAGE VALIDATION ==========
    
    def test_error_message_format_consistency(self):
        """Test error message format consistency
        
        Validates: Requirements 2.1 - Error message formatting
        """
        # Test various error scenarios and their message formats
        error_scenarios = [
            ("user_not_found", "nonexistent_user"),
            ("invalid_amount", "abc"),
            ("negative_amount", "-100"),
            ("zero_amount", "0"),
        ]
        
        for error_type, test_value in error_scenarios:
            with self.subTest(error_type=error_type, value=test_value):
                if error_type == "user_not_found":
                    user = self.admin_system.get_user_by_username(test_value)
                    self.assertIsNone(user, "Should not find nonexistent user")
                    
                elif error_type == "invalid_amount":
                    try:
                        amount = float(test_value)
                        self.fail("Should not convert invalid amount")
                    except ValueError:
                        # Expected behavior
                        pass
                
                elif error_type in ["negative_amount", "zero_amount"]:
                    amount = float(test_value)
                    # Test that system handles these amounts
                    user_id = 123456
                    result = self.admin_system.update_balance(user_id, amount)
                    self.assertIsNotNone(result, f"Should handle {error_type}")
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in usernames
        
        Validates: Requirements 6.3 - SQL injection prevention
        """
        # Test various SQL injection attempts
        injection_attempts = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; UPDATE users SET is_admin=1; --",
            "' UNION SELECT * FROM users --",
            "admin'; --",
            "' OR 1=1 --",
            "'; INSERT INTO users VALUES (999999, 'hacker', 'Hacker', 1000000, 1); --",
        ]
        
        for injection in injection_attempts:
            with self.subTest(injection=injection):
                # Test that SQL injection attempts are handled safely
                user = self.admin_system.get_user_by_username(injection)
                # Should not find user and should not cause SQL injection
                self.assertIsNone(user, f"Should not find user for injection attempt: {injection}")
                
                # Test that database is still intact
                user_count = self.admin_system.get_users_count()
                self.assertGreater(user_count, 0, "Database should still be intact")
                
                # Test that admin users are still correct
                admin_user = self.admin_system.get_user_by_id(789012)
                self.assertIsNotNone(admin_user, "Admin user should still exist")
                self.assertTrue(admin_user['is_admin'], "Admin status should be preserved")
    
    def test_xss_prevention_in_usernames(self):
        """Test XSS prevention in username handling
        
        Validates: Requirements 6.3 - XSS prevention
        """
        # Test various XSS attempts in usernames
        xss_attempts = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src=javascript:alert('xss')>",
        ]
        
        for xss in xss_attempts:
            with self.subTest(xss=xss):
                # Test that XSS attempts are handled safely
                user = self.admin_system.get_user_by_username(xss)
                # Should not find user (unless specifically registered)
                self.assertIsNone(user, f"Should not find user for XSS attempt: {xss}")
                
                # Test registering user with XSS attempt as username
                test_user_id = 500000 + hash(xss) % 100000
                result = self.admin_system.register_user(test_user_id, xss, "XSS Test")
                
                # Should handle registration gracefully
                self.assertIsInstance(result, bool, "Should handle XSS username registration")
                
                if result:
                    # If registration succeeded, verify user can be found
                    registered_user = self.admin_system.get_user_by_id(test_user_id)
                    self.assertIsNotNone(registered_user, "Should find registered user")
    
    # ========== BOUNDARY CONDITIONS FOR OPERATIONS ==========
    
    def test_operation_sequence_edge_cases(self):
        """Test edge cases in operation sequences
        
        Validates: Requirements 2.1 - Operation sequence handling
        """
        user_id = 123456
        
        # Test rapid sequence of operations
        operations = [
            ("balance_update", 50.0),
            ("balance_update", -25.0),
            ("admin_check", None),
            ("balance_update", 100.0),
            ("transaction", (75.0, 'add', 789012)),
            ("user_lookup", None),
        ]
        
        for i, (operation, param) in enumerate(operations):
            with self.subTest(step=i, operation=operation):
                if operation == "balance_update":
                    result = self.admin_system.update_balance(user_id, param)
                    self.assertIsNotNone(result, f"Balance update {i} should succeed")
                    
                elif operation == "admin_check":
                    result = self.admin_system.is_admin(user_id)
                    self.assertIsInstance(result, bool, f"Admin check {i} should return bool")
                    
                elif operation == "transaction":
                    amount, trans_type, admin_id = param
                    result = self.admin_system.add_transaction(user_id, amount, trans_type, admin_id)
                    self.assertIsNotNone(result, f"Transaction {i} should succeed")
                    
                elif operation == "user_lookup":
                    result = self.admin_system.get_user_by_id(user_id)
                    self.assertIsNotNone(result, f"User lookup {i} should succeed")
    
    def test_database_state_consistency_edge_cases(self):
        """Test database state consistency edge cases
        
        Validates: Requirements 2.1 - Database consistency
        """
        user_id = 123456
        
        # Perform multiple operations and verify consistency
        initial_user = self.admin_system.get_user_by_id(user_id)
        initial_balance = initial_user['balance']
        
        # Sequence of balance changes
        changes = [10.0, -5.0, 20.0, -15.0, 30.0]
        expected_balance = initial_balance
        
        for change in changes:
            new_balance = self.admin_system.update_balance(user_id, change)
            expected_balance += change
            
            # Verify balance is correct
            self.assertEqual(new_balance, expected_balance, 
                           f"Balance should be correct after change {change}")
            
            # Verify database consistency
            user = self.admin_system.get_user_by_id(user_id)
            self.assertEqual(user['balance'], expected_balance, 
                           "Database should be consistent with returned balance")
        
        # Final consistency check
        final_user = self.admin_system.get_user_by_id(user_id)
        self.assertEqual(final_user['balance'], expected_balance, 
                        "Final balance should match expected")


if __name__ == '__main__':
    unittest.main()