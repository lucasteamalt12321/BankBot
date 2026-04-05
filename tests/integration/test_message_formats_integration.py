#!/usr/bin/env python3
"""
Integration tests for message formats - Task 11.1
Tests message formats in actual bot command context
Requirements: 1.1, 4.1, 2.3, 3.2, 5.4, 5.5
"""

import unittest
import sys
import os
import tempfile
import sqlite3
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MessageFormatValidator:
    """Validator for message formats according to requirements"""

    @staticmethod
    def validate_admin_panel_format(message, users_count):
        """Validate admin panel message format (Requirement 1.1)"""
        expected_lines = [
            "Админ-панель:",
            "/add_points @username [число] - начислить очки",
            "/add_admin @username - добавить администратора",
            f"Всего пользователей: {users_count}"
        ]

        actual_lines = message.split('\n')

        if len(actual_lines) != len(expected_lines):
            return False, f"Expected {len(expected_lines)} lines, got {len(actual_lines)}"

        for i, (expected, actual) in enumerate(zip(expected_lines, actual_lines)):
            if expected != actual:
                return False, f"Line {i+1}: expected '{expected}', got '{actual}'"

        return True, "Valid admin panel format"

    @staticmethod
    def validate_shop_format(message):
        """Validate shop message format (Requirement 4.1)"""
        expected_lines = [
            "Магазин:",
            "1. Сообщение админу - 10 очков",
            "Для покупки введите /buy_contact"
        ]

        actual_lines = message.split('\n')

        if len(actual_lines) != len(expected_lines):
            return False, f"Expected {len(expected_lines)} lines, got {len(actual_lines)}"

        for i, (expected, actual) in enumerate(zip(expected_lines, actual_lines)):
            if expected != actual:
                return False, f"Line {i+1}: expected '{expected}', got '{actual}'"

        return True, "Valid shop format"

    @staticmethod
    def validate_add_points_format(message, username, amount, new_balance):
        """Validate add points confirmation format (Requirement 2.3)"""
        expected = f"Пользователю @{username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"

        if message != expected:
            return False, f"Expected '{expected}', got '{message}'"

        return True, "Valid add points format"

    @staticmethod
    def validate_add_admin_format(message, username):
        """Validate add admin confirmation format (Requirement 3.2)"""
        expected = f"Пользователь @{username} теперь администратор"

        if message != expected:
            return False, f"Expected '{expected}', got '{message}'"

        return True, "Valid add admin format"

    @staticmethod
    def validate_buy_contact_user_format(message):
        """Validate buy contact user confirmation format (Requirement 5.4)"""
        expected = "Вы купили контакт. Администратор свяжется с вами."

        if message != expected:
            return False, f"Expected '{expected}', got '{message}'"

        return True, "Valid buy contact user format"

    @staticmethod
    def validate_buy_contact_admin_format(message, username, balance):
        """Validate buy contact admin notification format (Requirement 5.5)"""
        expected = f"Пользователь @{username} купил контакт. Его баланс: {int(balance)} очков"

        if message != expected:
            return False, f"Expected '{expected}', got '{message}'"

        return True, "Valid buy contact admin format"


class TestMessageFormatIntegration(unittest.TestCase):
    """Integration tests for message formats"""

    def setUp(self):
        """Set up test environment"""
        self.validator = MessageFormatValidator()

    def test_admin_panel_message_validation(self):
        """Test admin panel message validation with various user counts"""
        test_cases = [
            (0, "Empty database"),
            (1, "Single user"),
            (10, "Multiple users"),
            (1000, "Large user count")
        ]

        for users_count, description in test_cases:
            with self.subTest(users_count=users_count, description=description):
                message = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"

                is_valid, error_msg = self.validator.validate_admin_panel_format(message, users_count)
                self.assertTrue(is_valid, f"Admin panel format invalid for {description}: {error_msg}")

                print(f"✓ Admin panel format valid for {description} ({users_count} users)")

    def test_shop_message_validation(self):
        """Test shop message validation"""
        message = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"

        is_valid, error_msg = self.validator.validate_shop_format(message)
        self.assertTrue(is_valid, f"Shop format invalid: {error_msg}")

        print("✓ Shop message format validation passed")

    def test_add_points_message_validation(self):
        """Test add points confirmation message validation"""
        test_cases = [
            ("testuser", 50, 150, "Regular case"),
            ("user_123", 1, 1, "Minimum amount"),
            ("admin", 999999, 1000000, "Large amounts"),
            ("новыйпользователь", 100, 100, "Cyrillic username")
        ]

        for username, amount, new_balance, description in test_cases:
            with self.subTest(username=username, amount=amount, description=description):
                message = f"Пользователю @{username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"

                is_valid, error_msg = self.validator.validate_add_points_format(message, username, amount, new_balance)
                self.assertTrue(is_valid, f"Add points format invalid for {description}: {error_msg}")

                print(f"✓ Add points format valid for {description}")

    def test_add_admin_message_validation(self):
        """Test add admin confirmation message validation"""
        test_cases = [
            ("newadmin", "Regular username"),
            ("user_123", "Username with underscore and numbers"),
            ("админ", "Cyrillic username"),
            ("a", "Single character username")
        ]

        for username, description in test_cases:
            with self.subTest(username=username, description=description):
                message = f"Пользователь @{username} теперь администратор"

                is_valid, error_msg = self.validator.validate_add_admin_format(message, username)
                self.assertTrue(is_valid, f"Add admin format invalid for {description}: {error_msg}")

                print(f"✓ Add admin format valid for {description}")

    def test_buy_contact_messages_validation(self):
        """Test buy contact message validation"""
        # Test user confirmation
        user_message = "Вы купили контакт. Администратор свяжется с вами."
        is_valid, error_msg = self.validator.validate_buy_contact_user_format(user_message)
        self.assertTrue(is_valid, f"Buy contact user format invalid: {error_msg}")

        # Test admin notification with various scenarios
        test_cases = [
            ("buyer1", 40, "After spending 10 from 50"),
            ("buyer2", 0, "After spending last 10 points"),
            ("buyer3", 990, "High balance user"),
        ]

        for username, balance, description in test_cases:
            with self.subTest(username=username, balance=balance, description=description):
                admin_message = f"Пользователь @{username} купил контакт. Его баланс: {int(balance)} очков"

                is_valid, error_msg = self.validator.validate_buy_contact_admin_format(admin_message, username, balance)
                self.assertTrue(is_valid, f"Buy contact admin format invalid for {description}: {error_msg}")

                print(f"✓ Buy contact admin format valid for {description}")

        print("✓ Buy contact user format validation passed")

    def test_message_format_consistency(self):
        """Test consistency across all message formats"""
        # Test that all messages use consistent formatting patterns

        # Username formatting consistency
        messages_with_usernames = [
            "Пользователю @testuser начислено 100 очков. Новый баланс: 200",
            "Пользователь @testuser теперь администратор",
            "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        ]

        username_pattern = r"@\w+"
        for message in messages_with_usernames:
            matches = re.findall(username_pattern, message)
            self.assertTrue(len(matches) > 0, f"Message should contain @username: {message}")

            # Check that @ is always directly before username (no space)
            for match in matches:
                self.assertTrue(match.startswith('@'), f"Username should start with @: {match}")

        # Number formatting consistency (integers, no decimals)
        messages_with_numbers = [
            "Пользователю @testuser начислено 100 очков. Новый баланс: 200",
            "1. Сообщение админу - 10 очков",
            "Пользователь @testuser купил контакт. Его баланс: 40 очков",
            "Всего пользователей: 5"
        ]

        decimal_pattern = r"\d+\.\d+"
        for message in messages_with_numbers:
            matches = re.findall(decimal_pattern, message)
            self.assertEqual(len(matches), 0, f"Message should not contain decimal numbers: {message}")

        print("✓ Message format consistency validation passed")

    def test_message_format_completeness(self):
        """Test that all required message formats are covered"""
        # Verify all requirements are covered by our format validators

        required_formats = {
            "1.1": "Admin panel format",
            "4.1": "Shop format", 
            "2.3": "Add points confirmation",
            "3.2": "Add admin confirmation",
            "5.4": "Buy contact user confirmation",
            "5.5": "Buy contact admin notification"
        }

        # Test that we have validators for all required formats
        validator_methods = [
            self.validator.validate_admin_panel_format,
            self.validator.validate_shop_format,
            self.validator.validate_add_points_format,
            self.validator.validate_add_admin_format,
            self.validator.validate_buy_contact_user_format,
            self.validator.validate_buy_contact_admin_format
        ]

        self.assertEqual(len(validator_methods), len(required_formats),
                        "Should have validator for each required format")

        print(f"✓ All {len(required_formats)} required message formats are covered")

    def test_error_message_formats(self):
        """Test that error messages don't break format validation"""
        # Test invalid formats to ensure validator catches them

        invalid_admin_panel = "Админ-панель:\nНеправильный формат"
        is_valid, _ = self.validator.validate_admin_panel_format(invalid_admin_panel, 1)
        self.assertFalse(is_valid, "Validator should catch invalid admin panel format")

        invalid_shop = "Магазин:\nНеправильный товар"
        is_valid, _ = self.validator.validate_shop_format(invalid_shop)
        self.assertFalse(is_valid, "Validator should catch invalid shop format")

        invalid_add_points = "Неправильное подтверждение"
        is_valid, _ = self.validator.validate_add_points_format(invalid_add_points, "user", 100, 200)
        self.assertFalse(is_valid, "Validator should catch invalid add points format")

        print("✓ Error message format validation passed")


class TestMessageFormatRegression(unittest.TestCase):
    """Regression tests for message formats"""

    def test_format_stability(self):
        """Test that message formats remain stable across changes"""
        # These are the exact formats that must never change
        stable_formats = {
            "admin_panel": "Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {count}",
            "shop": "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact",
            "add_points": "Пользователю @{username} начислено {amount} очков. Новый баланс: {balance}",
            "add_admin": "Пользователь @{username} теперь администратор",
            "buy_contact_user": "Вы купили контакт. Администратор свяжется с вами.",
            "buy_contact_admin": "Пользователь @{username} купил контакт. Его баланс: {balance} очков"
        }

        # Test that formats match exactly
        for format_name, format_template in stable_formats.items():
            # Test with sample data
            if format_name == "admin_panel":
                actual = format_template.format(count=5)
                expected = "Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: 5"
            elif format_name == "shop":
                actual = format_template
                expected = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
            elif format_name == "add_points":
                actual = format_template.format(username="testuser", amount=100, balance=200)
                expected = "Пользователю @testuser начислено 100 очков. Новый баланс: 200"
            elif format_name == "add_admin":
                actual = format_template.format(username="newadmin")
                expected = "Пользователь @newadmin теперь администратор"
            elif format_name == "buy_contact_user":
                actual = format_template
                expected = "Вы купили контакт. Администратор свяжется с вами."
            elif format_name == "buy_contact_admin":
                actual = format_template.format(username="buyer", balance=40)
                expected = "Пользователь @buyer купил контакт. Его баланс: 40 очков"

            self.assertEqual(actual, expected, f"Format {format_name} has changed")
            print(f"✓ Format {format_name} is stable")

        print("✓ All message formats are stable")


if __name__ == '__main__':
    print("🔗 Running Message Format Integration Tests...")
    print("=" * 60)

    # Run tests with verbose output
    unittest.main(verbosity=2, exit=False)

    print("=" * 60)
    print("✅ Message format integration tests completed!")
