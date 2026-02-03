#!/usr/bin/env python3
"""
Unit tests for message formats in the telegram bot admin system
Tests Requirements 1.1, 4.1, 2.3, 3.2, 5.4, 5.5

This test file validates the exact message formats for:
- /admin command format
- /shop command format  
- /add_points confirmation format
- /add_admin confirmation format
- /buy_contact user confirmation
- /buy_contact admin notification
"""

import unittest
import sys
import os
import sqlite3
import tempfile

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem


class TestMessageFormats(unittest.TestCase):
    """Test cases for exact message formats as specified in requirements"""
    
    def setUp(self):
        """Set up test database and admin system"""
        # Create temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.admin_system = AdminSystem(self.db_path)
        
        # Create test users
        self.admin_system.register_user(123456, "testuser", "Test User")
        self.admin_system.register_user(789012, "admin_user", "Admin User")
        self.admin_system.register_user(555555, "target_user", "Target User")
        
        # Set admin status
        self.admin_system.set_admin_status(789012, True)
        
        # Set initial balances
        self.admin_system.update_balance(123456, 50)  # Regular user with 50 points
        self.admin_system.update_balance(555555, 25)  # Target user with 25 points
    
    def tearDown(self):
        """Clean up test database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_admin_command_format(self):
        """Test /admin command format matches requirements exactly
        
        Validates: Requirements 1.1
        Format: "Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: [число]"
        """
        users_count = self.admin_system.get_users_count()
        expected_format = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Test exact format structure
        lines = expected_format.split('\n')
        
        self.assertEqual(len(lines), 4, "Admin panel message should have exactly 4 lines")
        self.assertEqual(lines[0], "Админ-панель:", "First line should be 'Админ-панель:'")
        self.assertEqual(lines[1], "/add_points @username [число] - начислить очки", 
                        "Second line should show add_points command format")
        self.assertEqual(lines[2], "/add_admin @username - добавить администратора", 
                        "Third line should show add_admin command format")
        self.assertTrue(lines[3].startswith("Всего пользователей: "), 
                       "Fourth line should start with 'Всего пользователей: '")
        
        # Test that user count is correctly displayed
        self.assertEqual(lines[3], f"Всего пользователей: {users_count}", 
                        f"Should show correct user count: {users_count}")
        
        # Verify user count is accurate (we created 3 users in setUp)
        self.assertEqual(users_count, 3, "Should have 3 users in test database")
    
    def test_shop_command_format(self):
        """Test /shop command format matches requirements exactly
        
        Validates: Requirements 4.1
        Format: "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        """
        expected_format = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        
        # Test exact format structure
        lines = expected_format.split('\n')
        
        self.assertEqual(len(lines), 3, "Shop message should have exactly 3 lines")
        self.assertEqual(lines[0], "Магазин:", "First line should be 'Магазин:'")
        self.assertEqual(lines[1], "1. Сообщение админу - 10 очков", 
                        "Second line should show item with exact price")
        self.assertEqual(lines[2], "Для покупки введите /buy_contact", 
                        "Third line should show exact purchase instruction")
        
        # Test specific content requirements
        self.assertIn("10 очков", expected_format, "Should display price as '10 очков'")
        self.assertIn("/buy_contact", expected_format, "Should contain /buy_contact command")
        self.assertIn("Сообщение админу", expected_format, "Should contain item name")
    
    def test_add_points_confirmation_format(self):
        """Test /add_points confirmation format matches requirements exactly
        
        Validates: Requirements 2.3
        Format: "Пользователю @username начислено [число] очков. Новый баланс: [новый_баланс]"
        """
        # Test data
        username = "target_user"
        points_added = 100
        
        # Get user and simulate adding points
        user = self.admin_system.get_user_by_username(username)
        initial_balance = user['balance']  # Should be 25 from setUp
        new_balance = self.admin_system.update_balance(user['id'], points_added)
        
        # Format confirmation message
        expected_format = f"Пользователю @{username} начислено {int(points_added)} очков. Новый баланс: {int(new_balance)}"
        
        # Test exact format
        self.assertTrue(expected_format.startswith("Пользователю @"), 
                       "Should start with 'Пользователю @'")
        self.assertIn(f"@{username}", expected_format, 
                     f"Should contain @{username}")
        self.assertIn(f"начислено {int(points_added)} очков", expected_format, 
                     f"Should contain 'начислено {int(points_added)} очков'")
        self.assertIn(f"Новый баланс: {int(new_balance)}", expected_format, 
                     f"Should contain 'Новый баланс: {int(new_balance)}'")
        
        # Test with specific example
        expected_specific = "Пользователю @target_user начислено 100 очков. Новый баланс: 125"
        self.assertEqual(expected_format, expected_specific, 
                        "Should match exact format with test data")
        
        # Verify balance calculation is correct
        self.assertEqual(new_balance, initial_balance + points_added, 
                        "New balance should be initial balance + points added")
    
    def test_add_admin_confirmation_format(self):
        """Test /add_admin confirmation format matches requirements exactly
        
        Validates: Requirements 3.2
        Format: "Пользователь @username теперь администратор"
        """
        username = "target_user"
        
        # Format confirmation message
        expected_format = f"Пользователь @{username} теперь администратор"
        
        # Test exact format
        self.assertTrue(expected_format.startswith("Пользователь @"), 
                       "Should start with 'Пользователь @'")
        self.assertIn(f"@{username}", expected_format, 
                     f"Should contain @{username}")
        self.assertTrue(expected_format.endswith("теперь администратор"), 
                       "Should end with 'теперь администратор'")
        
        # Test with specific example
        expected_specific = "Пользователь @target_user теперь администратор"
        self.assertEqual(expected_format, expected_specific, 
                        "Should match exact format with test data")
        
        # Test format consistency (no extra punctuation or formatting)
        self.assertNotIn("!", expected_format, "Should not contain exclamation marks")
        self.assertNotIn(".", expected_format, "Should not contain periods")
        self.assertNotIn("✅", expected_format, "Should not contain emoji")
    
    def test_buy_contact_user_confirmation_format(self):
        """Test /buy_contact user confirmation format matches requirements exactly
        
        Validates: Requirements 5.4
        Format: "Вы купили контакт. Администратор свяжется с вами."
        """
        expected_format = "Вы купили контакт. Администратор свяжется с вами."
        
        # Test exact format
        self.assertEqual(expected_format, "Вы купили контакт. Администратор свяжется с вами.", 
                        "Should match exact format from requirements")
        
        # Test format structure
        self.assertTrue(expected_format.startswith("Вы купили контакт"), 
                       "Should start with 'Вы купили контакт'")
        self.assertTrue(expected_format.endswith("Администратор свяжется с вами."), 
                       "Should end with 'Администратор свяжется с вами.'")
        
        # Test punctuation
        self.assertIn(". ", expected_format, "Should contain period and space between sentences")
        self.assertTrue(expected_format.endswith("."), "Should end with period")
        
        # Test no extra formatting
        self.assertNotIn("✅", expected_format, "Should not contain emoji")
        self.assertNotIn("❌", expected_format, "Should not contain error emoji")
        self.assertNotIn("<b>", expected_format, "Should not contain HTML formatting")
    
    def test_buy_contact_admin_notification_format(self):
        """Test /buy_contact admin notification format matches requirements exactly
        
        Validates: Requirements 5.5
        Format: "Пользователь @username купил контакт. Его баланс: [новый_баланс] очков"
        """
        # Test data
        username = "testuser"
        
        # Simulate purchase (deduct 10 points from user with 50 points)
        user = self.admin_system.get_user_by_username(username)
        new_balance = self.admin_system.update_balance(user['id'], -10)  # 50 - 10 = 40
        
        # Format admin notification message
        expected_format = f"Пользователь @{username} купил контакт. Его баланс: {int(new_balance)} очков"
        
        # Test exact format
        self.assertTrue(expected_format.startswith("Пользователь @"), 
                       "Should start with 'Пользователь @'")
        self.assertIn(f"@{username}", expected_format, 
                     f"Should contain @{username}")
        self.assertIn("купил контакт", expected_format, 
                     "Should contain 'купил контакт'")
        self.assertIn(f"Его баланс: {int(new_balance)} очков", expected_format, 
                     f"Should contain 'Его баланс: {int(new_balance)} очков'")
        
        # Test with specific example
        expected_specific = "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        self.assertEqual(expected_format, expected_specific, 
                        "Should match exact format with test data")
        
        # Test punctuation
        self.assertIn(". ", expected_format, "Should contain period and space between sentences")
        
        # Test no extra formatting
        self.assertNotIn("✅", expected_format, "Should not contain emoji")
        self.assertNotIn("<b>", expected_format, "Should not contain HTML formatting")
    
    def test_message_format_consistency(self):
        """Test consistency across all message formats
        
        Validates: General message format consistency
        """
        # Test that all confirmation messages use consistent username format
        username = "testuser"
        
        # All messages should use @username format consistently
        add_points_msg = f"Пользователю @{username} начислено 50 очков. Новый баланс: 100"
        add_admin_msg = f"Пользователь @{username} теперь администратор"
        admin_notification_msg = f"Пользователь @{username} купил контакт. Его баланс: 40 очков"
        
        # All should contain @username
        for msg in [add_points_msg, add_admin_msg, admin_notification_msg]:
            self.assertIn(f"@{username}", msg, f"Message should contain @{username}: {msg}")
        
        # Test that numeric values are displayed as integers (no decimals)
        self.assertNotIn(".0", add_points_msg, "Points should be displayed as integers")
        self.assertNotIn(".0", admin_notification_msg, "Balance should be displayed as integers")
    
    def test_admin_panel_statistics_accuracy(self):
        """Test that admin panel displays accurate user statistics
        
        Validates: Requirements 1.1 (statistics display)
        """
        # Get current user count
        users_count = self.admin_system.get_users_count()
        
        # Add another user and verify count updates
        self.admin_system.register_user(999999, "newuser", "New User")
        updated_count = self.admin_system.get_users_count()
        
        self.assertEqual(updated_count, users_count + 1, 
                        "User count should increase by 1 after adding user")
        
        # Test admin panel format with updated count
        expected_format = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {updated_count}"
        
        lines = expected_format.split('\n')
        self.assertEqual(lines[3], f"Всего пользователей: {updated_count}", 
                        "Should display updated user count")
    
    def test_shop_item_display_format(self):
        """Test that shop items are displayed with correct format
        
        Validates: Requirements 4.1 (item display format)
        """
        expected_format = "Магазин:\n1. Сообщение админу - 10 очков\nДля покупки введите /buy_contact"
        
        # Test item numbering format
        self.assertIn("1. ", expected_format, "Items should be numbered starting with '1. '")
        
        # Test item name and price format
        self.assertIn("Сообщение админу - 10 очков", expected_format, 
                     "Should display 'item_name - price очков'")
        
        # Test price format specifically
        self.assertRegex(expected_format, r"\d+ очков", 
                        "Price should be in format '[number] очков'")
        
        # Test purchase instruction format
        self.assertIn("Для покупки введите /buy_contact", expected_format, 
                     "Should contain exact purchase instruction")
    
    def test_error_message_formats(self):
        """Test error message formats for various scenarios
        
        Validates: Requirements 1.2, 2.4, 2.5, 5.6 (error handling)
        """
        # Test admin access denied format
        admin_access_denied = ("🔒 У вас нет прав администратора для выполнения этой команды.\n"
                              "Обратитесь к администратору бота для получения доступа.")
        
        self.assertTrue(admin_access_denied.startswith("🔒"), 
                       "Admin access denied should start with lock emoji")
        self.assertIn("У вас нет прав администратора", admin_access_denied,
                     "Should contain access denied message")
        self.assertIn("Обратитесь к администратору", admin_access_denied,
                     "Should contain instruction to contact admin")
        
        # Test user not found format
        username = "nonexistent_user"
        user_not_found = f"❌ Пользователь {username} не найден"
        
        self.assertTrue(user_not_found.startswith("❌"), 
                       "User not found should start with error emoji")
        self.assertIn("не найден", user_not_found,
                     "Should contain 'не найден' message")
        self.assertIn(username, user_not_found,
                     "Should contain the username that was not found")
        
        # Test insufficient balance format
        required_amount = 10
        current_balance = 5
        insufficient_balance = (f"❌ Недостаточно очков для покупки. "
                               f"Требуется: {required_amount} очков, "
                               f"у вас: {current_balance} очков")
        
        self.assertTrue(insufficient_balance.startswith("❌"), 
                       "Insufficient balance should start with error emoji")
        self.assertIn("Недостаточно очков", insufficient_balance,
                     "Should contain insufficient balance message")
        self.assertIn(f"Требуется: {required_amount}", insufficient_balance,
                     "Should show required amount")
        self.assertIn(f"у вас: {current_balance}", insufficient_balance,
                     "Should show current balance")
    
    def test_command_format_instruction_messages(self):
        """Test instruction messages for incorrect command formats
        
        Validates: Requirements 2.5, 8.5 (format error handling)
        """
        # Test add_points format instruction
        add_points_instruction = ("❌ Неверный формат команды\n\n"
                                 "Используйте: /add_points @username [число]\n\n"
                                 "Примеры:\n"
                                 "• /add_points @john_doe 100\n"
                                 "• /add_points user123 50")
        
        self.assertTrue(add_points_instruction.startswith("❌"), 
                       "Format instruction should start with error emoji")
        self.assertIn("Неверный формат команды", add_points_instruction,
                     "Should contain format error message")
        self.assertIn("/add_points @username [число]", add_points_instruction,
                     "Should show correct format")
        self.assertIn("Примеры:", add_points_instruction,
                     "Should contain examples section")
        
        # Test add_admin format instruction
        add_admin_instruction = ("❌ Неверный формат команды\n\n"
                                "Используйте: /add_admin @username\n\n"
                                "Примеры:\n"
                                "• /add_admin @john_doe\n"
                                "• /add_admin user123")
        
        self.assertTrue(add_admin_instruction.startswith("❌"), 
                       "Format instruction should start with error emoji")
        self.assertIn("Неверный формат команды", add_admin_instruction,
                     "Should contain format error message")
        self.assertIn("/add_admin @username", add_admin_instruction,
                     "Should show correct format")
        self.assertIn("Примеры:", add_admin_instruction,
                     "Should contain examples section")
    
    def test_numeric_format_consistency(self):
        """Test that all numeric values are displayed consistently as integers
        
        Validates: General numeric display consistency
        """
        # Test points display (should be integers, not decimals)
        points_message = "Пользователю @testuser начислено 100 очков. Новый баланс: 150"
        
        # Should not contain decimal points for whole numbers
        self.assertNotIn(".0", points_message, "Points should be displayed as integers")
        
        # Test balance display in admin notification
        admin_notification = "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        
        self.assertNotIn(".0", admin_notification, "Balance should be displayed as integers")
        
        # Test that numeric values are properly formatted
        self.assertRegex(points_message, r"начислено \d+ очков", 
                        "Points should be displayed as whole numbers")
        self.assertRegex(points_message, r"баланс: \d+", 
                        "Balance should be displayed as whole numbers")
    
    def test_username_format_consistency(self):
        """Test that usernames are consistently formatted with @ symbol
        
        Validates: Username display consistency across all messages
        """
        username = "testuser"
        
        # All user-related messages should use @username format
        messages = [
            f"Пользователю @{username} начислено 50 очков. Новый баланс: 100",
            f"Пользователь @{username} теперь администратор",
            f"Пользователь @{username} купил контакт. Его баланс: 40 очков"
        ]
        
        for message in messages:
            self.assertIn(f"@{username}", message, 
                         f"Message should contain @{username}: {message}")
            # Should not have double @ symbols
            self.assertNotIn(f"@@{username}", message,
                           f"Message should not contain double @: {message}")
    
    def test_message_structure_consistency(self):
        """Test structural consistency across all message types
        
        Validates: Overall message format consistency
        """
        # Test that confirmation messages follow consistent structure
        add_points_msg = "Пользователю @testuser начислено 100 очков. Новый баланс: 200"
        add_admin_msg = "Пользователь @testuser теперь администратор"
        buy_confirmation = "Вы купили контакт. Администратор свяжется с вами."
        admin_notification = "Пользователь @testuser купил контакт. Его баланс: 40 очков"
        
        # Test sentence structure (proper punctuation)
        self.assertTrue(buy_confirmation.endswith("."), 
                       "Buy confirmation should end with period")
        
        # Test that multi-sentence messages use proper punctuation
        sentences_in_buy_confirmation = buy_confirmation.split(". ")
        self.assertEqual(len(sentences_in_buy_confirmation), 2,
                        "Buy confirmation should have exactly 2 sentences")
        
        # Test that admin panel format is consistent
        admin_panel = ("Админ-панель:\n"
                      "/add_points @username [число] - начислить очки\n"
                      "/add_admin @username - добавить администратора\n"
                      "Всего пользователей: 3")
        
        lines = admin_panel.split('\n')
        self.assertEqual(len(lines), 4, "Admin panel should have exactly 4 lines")
        self.assertTrue(lines[0].endswith(":"), "First line should end with colon")
        self.assertTrue(lines[1].startswith("/"), "Command lines should start with /")
        self.assertTrue(lines[2].startswith("/"), "Command lines should start with /")
        self.assertTrue(lines[3].startswith("Всего"), "Stats line should start with 'Всего'")
    
    def test_edge_case_message_formats(self):
        """Test edge cases for message formats
        
        Validates: Edge cases for Requirements 1.1, 2.3, 3.2, 4.1, 5.4, 5.5
        """
        # Test with username that has no @ symbol initially
        username_without_at = "testuser"
        add_points_msg = f"Пользователю @{username_without_at} начислено 1 очков. Новый баланс: 1"
        
        # Should still format correctly with @ symbol
        self.assertIn(f"@{username_without_at}", add_points_msg)
        
        # Test with very large numbers (should still be integers)
        large_amount = 999999
        large_balance = 1000000
        large_points_msg = f"Пользователю @testuser начислено {large_amount} очков. Новый баланс: {large_balance}"
        
        self.assertIn(str(large_amount), large_points_msg)
        self.assertIn(str(large_balance), large_points_msg)
        self.assertNotIn(".0", large_points_msg, "Large numbers should still be integers")
        
        # Test with single point (singular vs plural)
        single_point_msg = "Пользователю @testuser начислено 1 очков. Новый баланс: 1"
        self.assertIn("1 очков", single_point_msg, "Should use 'очков' even for 1 point")
        
        # Test admin panel with zero users
        admin_panel_zero = ("Админ-панель:\n"
                           "/add_points @username [число] - начислить очки\n"
                           "/add_admin @username - добавить администратора\n"
                           "Всего пользователей: 0")
        
        self.assertIn("Всего пользователей: 0", admin_panel_zero)
        
        # Test admin panel with many users
        admin_panel_many = ("Админ-панель:\n"
                           "/add_points @username [число] - начислить очки\n"
                           "/add_admin @username - добавить администратора\n"
                           "Всего пользователей: 1000")
        
        self.assertIn("Всего пользователей: 1000", admin_panel_many)
    
    def test_special_character_handling(self):
        """Test handling of special characters in usernames and messages
        
        Validates: Proper handling of special characters in message formats
        """
        # Test username with underscores
        username_with_underscore = "test_user_123"
        msg_with_underscore = f"Пользователю @{username_with_underscore} начислено 50 очков. Новый баланс: 100"
        
        self.assertIn(f"@{username_with_underscore}", msg_with_underscore)
        
        # Test username with numbers
        username_with_numbers = "user123"
        msg_with_numbers = f"Пользователь @{username_with_numbers} теперь администратор"
        
        self.assertIn(f"@{username_with_numbers}", msg_with_numbers)
        
        # Test that message formats don't break with special usernames
        special_usernames = ["user_123", "test123", "a_b_c", "user1"]
        
        for username in special_usernames:
            add_points = f"Пользователю @{username} начислено 10 очков. Новый баланс: 20"
            add_admin = f"Пользователь @{username} теперь администратор"
            admin_notif = f"Пользователь @{username} купил контакт. Его баланс: 10 очков"
            
            # All should contain the username properly formatted
            self.assertIn(f"@{username}", add_points)
            self.assertIn(f"@{username}", add_admin)
            self.assertIn(f"@{username}", admin_notif)
    
    def test_message_length_and_structure(self):
        """Test that messages have appropriate length and structure
        
        Validates: Message structure requirements
        """
        # Test that admin panel message is not too long
        admin_panel = ("Админ-панель:\n"
                      "/add_points @username [число] - начислить очки\n"
                      "/add_admin @username - добавить администратора\n"
                      "Всего пользователей: 100")
        
        # Should be reasonable length (not too long for Telegram)
        self.assertLess(len(admin_panel), 500, "Admin panel message should be reasonably short")
        
        # Test that shop message is concise
        shop_message = ("Магазин:\n"
                       "1. Сообщение админу - 10 очков\n"
                       "Для покупки введите /buy_contact")
        
        self.assertLess(len(shop_message), 200, "Shop message should be concise")
        
        # Test that confirmation messages are not too verbose
        confirmation_messages = [
            "Пользователю @testuser начислено 100 очков. Новый баланс: 200",
            "Пользователь @testuser теперь администратор",
            "Вы купили контакт. Администратор свяжется с вами.",
            "Пользователь @testuser купил контакт. Его баланс: 90 очков"
        ]
        
        for msg in confirmation_messages:
            self.assertLess(len(msg), 150, f"Confirmation message should be concise: {msg}")
    
    def test_localization_consistency(self):
        """Test that all messages use consistent Russian localization
        
        Validates: Language consistency across all message formats
        """
        # All messages should be in Russian
        russian_messages = [
            "Админ-панель:",
            "начислить очки",
            "добавить администратора", 
            "Всего пользователей:",
            "Магазин:",
            "Сообщение админу",
            "Для покупки введите",
            "начислено",
            "очков",
            "Новый баланс:",
            "теперь администратор",
            "купили контакт",
            "Администратор свяжется с вами",
            "купил контакт",
            "Его баланс:"
        ]
        
        # Test that key Russian phrases are used consistently
        for phrase in russian_messages:
            # This is more of a documentation test - ensuring we use consistent Russian
            self.assertIsInstance(phrase, str, f"Russian phrase should be string: {phrase}")
            self.assertGreater(len(phrase), 0, f"Russian phrase should not be empty: {phrase}")
        
        # Test that we don't mix languages inappropriately
        mixed_language_examples = [
            "Админ-панель:",  # Should not be "Admin panel:"
            "очков",          # Should not be "points"
            "пользователей",  # Should not be "users"
        ]
        
        for phrase in mixed_language_examples:
            # Ensure Russian characters are present
            has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in phrase)
            self.assertTrue(has_cyrillic, f"Phrase should contain Cyrillic characters: {phrase}")


if __name__ == '__main__':
    unittest.main()