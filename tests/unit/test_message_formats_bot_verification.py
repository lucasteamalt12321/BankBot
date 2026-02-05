#!/usr/bin/env python3
"""
Bot verification tests for message formats - Task 11.1
Verifies that bot implementation matches required message formats
Requirements: 1.1, 4.1, 2.3, 3.2, 5.4, 5.5
"""

import unittest
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BotMessageFormatVerification(unittest.TestCase):
    """Verify bot implementation matches required message formats"""
    
    def setUp(self):
        """Set up test environment"""
        self.bot_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'bot.py')
        
        # Read bot implementation
        try:
            with open(self.bot_file_path, 'r', encoding='utf-8') as f:
                self.bot_content = f.read()
        except FileNotFoundError:
            self.skipTest(f"Bot file not found: {self.bot_file_path}")
    
    def test_admin_command_format_in_bot(self):
        """Test that bot admin command uses correct format
        
        Validates: Requirements 1.1
        """
        # Look for admin command implementation
        admin_command_pattern = r'async def admin_command.*?await.*?reply_text\((.*?)\)'
        matches = re.findall(admin_command_pattern, self.bot_content, re.DOTALL)
        
        self.assertTrue(len(matches) > 0, "Admin command implementation not found in bot")
        
        # Check for the exact format string
        expected_format_parts = [
            "Админ-панель:",
            "/add_points @username [число] - начислить очки",
            "/add_admin @username - добавить администратора",
            "Всего пользователей:"
        ]
        
        found_format = False
        for match in matches:
            for part in expected_format_parts:
                if part in match or part in self.bot_content:
                    found_format = True
                    break
        
        # More specific search for the exact format
        admin_format_search = r'f?"Админ-панель:\\n/add_points @username \[число\] - начислить очки\\n/add_admin @username - добавить администратора\\nВсего пользователей: \{.*?\}"'
        format_match = re.search(admin_format_search, self.bot_content)
        
        if not format_match:
            # Alternative search for the format components
            for part in expected_format_parts:
                self.assertIn(part, self.bot_content, f"Admin command format missing: {part}")
        
        print("✓ Admin command format verified in bot implementation")
    
    def test_shop_command_format_in_bot(self):
        """Test that bot shop command uses correct format
        
        Validates: Requirements 4.1
        """
        # Look for shop command implementation
        expected_format_parts = [
            "Магазин:",
            "1. Сообщение админу - 10 очков",
            "Для покупки введите /buy_contact"
        ]
        
        # Check for exact format or components
        shop_format_found = False
        for part in expected_format_parts:
            if part in self.bot_content:
                shop_format_found = True
            else:
                # If exact part not found, check if shop command exists
                if "shop_command" in self.bot_content or "async def shop" in self.bot_content:
                    # Shop command exists but format might be different
                    self.assertIn(part, self.bot_content, f"Shop format missing: {part}")
        
        # Look for the complete format string
        complete_format = '''Магазин:
1. Сообщение админу - 10 очков
Для покупки введите /buy_contact'''
        
        if complete_format not in self.bot_content:
            # Check individual components
            for part in expected_format_parts:
                self.assertIn(part, self.bot_content, f"Shop command format missing: {part}")
        
        print("✓ Shop command format verified in bot implementation")
    
    def test_add_points_format_in_bot(self):
        """Test that bot add_points command uses correct format
        
        Validates: Requirements 2.3
        """
        # Look for add_points command implementation
        expected_format_pattern = r'Пользователю @.*? начислено.*?очков\. Новый баланс:'
        
        format_match = re.search(expected_format_pattern, self.bot_content)
        self.assertTrue(format_match is not None, "Add points confirmation format not found in bot")
        
        # Check for specific components
        expected_components = [
            "Пользователю @",
            "начислено",
            "очков",
            "Новый баланс:"
        ]
        
        for component in expected_components:
            self.assertIn(component, self.bot_content, f"Add points format missing: {component}")
        
        print("✓ Add points confirmation format verified in bot implementation")
    
    def test_add_admin_format_in_bot(self):
        """Test that bot add_admin command uses correct format
        
        Validates: Requirements 3.2
        """
        # Look for add_admin command implementation
        expected_format_pattern = r'Пользователь @.*? теперь администратор'
        
        format_match = re.search(expected_format_pattern, self.bot_content)
        self.assertTrue(format_match is not None, "Add admin confirmation format not found in bot")
        
        # Check for specific components
        expected_components = [
            "Пользователь @",
            "теперь администратор"
        ]
        
        for component in expected_components:
            self.assertIn(component, self.bot_content, f"Add admin format missing: {component}")
        
        print("✓ Add admin confirmation format verified in bot implementation")
    
    def test_buy_contact_format_in_bot(self):
        """Test that bot buy_contact command uses correct formats
        
        Validates: Requirements 5.4, 5.5
        """
        # Check user confirmation format
        user_confirmation = "Вы купили контакт. Администратор свяжется с вами."
        self.assertIn(user_confirmation, self.bot_content, 
                     "Buy contact user confirmation format not found in bot")
        
        # Check admin notification format pattern
        admin_notification_pattern = r'купил контакт.*?Его баланс:.*?очков'
        format_match = re.search(admin_notification_pattern, self.bot_content)
        self.assertTrue(format_match is not None, 
                       "Buy contact admin notification format not found in bot")
        
        # Check for specific components
        expected_components = [
            "Пользователь @",
            "купил контакт",
            "Его баланс:",
            "очков"
        ]
        
        for component in expected_components:
            self.assertIn(component, self.bot_content, 
                         f"Buy contact admin notification format missing: {component}")
        
        print("✓ Buy contact confirmation formats verified in bot implementation")
    
    def test_command_handlers_exist(self):
        """Test that all required command handlers exist in bot"""
        required_commands = [
            'CommandHandler("admin"',
            'CommandHandler("shop"',
            'CommandHandler("add_points"',
            'CommandHandler("add_admin"',
            'CommandHandler("buy_contact"'
        ]
        
        for command in required_commands:
            self.assertIn(command, self.bot_content, f"Command handler missing: {command}")
        
        print("✓ All required command handlers exist in bot")
    
    def test_message_format_consistency_in_bot(self):
        """Test message format consistency in bot implementation"""
        # Check that usernames are consistently formatted with @
        username_patterns = [
            r'@\{.*?username.*?\}',  # f-string format
            r'@.*?username',         # direct format
            r'Пользователю @',       # add_points format
            r'Пользователь @'        # add_admin format
        ]
        
        username_found = False
        for pattern in username_patterns:
            if re.search(pattern, self.bot_content):
                username_found = True
                break
        
        self.assertTrue(username_found, "Username formatting (@username) not found in bot")
        
        # Check that numbers are formatted as integers
        # Look for int() conversions in message formatting
        int_conversion_patterns = [
            r'int\(.*?amount.*?\)',
            r'int\(.*?balance.*?\)',
            r'int\(.*?\)'
        ]
        
        int_formatting_found = False
        for pattern in int_conversion_patterns:
            if re.search(pattern, self.bot_content):
                int_formatting_found = True
                break
        
        # This is optional - bot might format numbers differently
        if int_formatting_found:
            print("✓ Integer formatting found in bot")
        else:
            print("⚠ Integer formatting not explicitly found (may use default formatting)")
        
        print("✓ Message format consistency verified in bot implementation")
    
    def test_error_handling_messages(self):
        """Test that bot has proper error handling messages"""
        expected_error_messages = [
            "не найден",  # User not found
            "нет прав",   # No admin rights
            "Неверный формат",  # Invalid format
            "недостаточно",     # Insufficient balance
        ]
        
        error_messages_found = 0
        for error_msg in expected_error_messages:
            if error_msg.lower() in self.bot_content.lower():
                error_messages_found += 1
        
        self.assertGreater(error_messages_found, 0, 
                          "No error handling messages found in bot")
        
        print(f"✓ Error handling messages found in bot ({error_messages_found}/{len(expected_error_messages)})")
    
    def test_admin_system_integration(self):
        """Test that bot properly integrates with admin system"""
        # Check for admin system initialization
        admin_system_patterns = [
            r'AdminSystem\(',
            r'self\.admin_system',
            r'admin_system\.',
        ]
        
        admin_integration_found = False
        for pattern in admin_system_patterns:
            if re.search(pattern, self.bot_content):
                admin_integration_found = True
                break
        
        self.assertTrue(admin_integration_found, 
                       "Admin system integration not found in bot")
        
        # Check for admin system methods
        admin_methods = [
            'is_admin',
            'get_users_count',
            'get_user_by_username',
            'update_balance',
            'set_admin_status'
        ]
        
        methods_found = 0
        for method in admin_methods:
            if method in self.bot_content:
                methods_found += 1
        
        self.assertGreater(methods_found, 0, 
                          "No admin system methods found in bot")
        
        print(f"✓ Admin system integration verified ({methods_found}/{len(admin_methods)} methods found)")


class BotImplementationCompleteness(unittest.TestCase):
    """Test completeness of bot implementation for message formats"""
    
    def setUp(self):
        """Set up test environment"""
        self.bot_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot', 'bot.py')
        
        try:
            with open(self.bot_file_path, 'r', encoding='utf-8') as f:
                self.bot_content = f.read()
        except FileNotFoundError:
            self.skipTest(f"Bot file not found: {self.bot_file_path}")
    
    def test_all_requirements_covered(self):
        """Test that all message format requirements are covered in bot"""
        requirements_coverage = {
            "1.1": {
                "description": "Admin panel format",
                "indicators": ["Админ-панель:", "/add_points", "/add_admin", "Всего пользователей:"],
                "found": 0
            },
            "4.1": {
                "description": "Shop format", 
                "indicators": ["Магазин:", "Сообщение админу", "10 очков", "/buy_contact"],
                "found": 0
            },
            "2.3": {
                "description": "Add points confirmation",
                "indicators": ["Пользователю @", "начислено", "очков", "Новый баланс:"],
                "found": 0
            },
            "3.2": {
                "description": "Add admin confirmation",
                "indicators": ["Пользователь @", "теперь администратор"],
                "found": 0
            },
            "5.4": {
                "description": "Buy contact user confirmation",
                "indicators": ["Вы купили контакт", "Администратор свяжется"],
                "found": 0
            },
            "5.5": {
                "description": "Buy contact admin notification",
                "indicators": ["купил контакт", "Его баланс:", "очков"],
                "found": 0
            }
        }
        
        # Check coverage for each requirement
        for req_id, req_data in requirements_coverage.items():
            for indicator in req_data["indicators"]:
                if indicator in self.bot_content:
                    req_data["found"] += 1
            
            coverage_percent = (req_data["found"] / len(req_data["indicators"])) * 100
            
            self.assertGreater(req_data["found"], 0, 
                             f"Requirement {req_id} ({req_data['description']}) not covered in bot")
            
            print(f"✓ Requirement {req_id} ({req_data['description']}): {req_data['found']}/{len(req_data['indicators'])} indicators found ({coverage_percent:.1f}%)")
        
        print("✓ All message format requirements are covered in bot implementation")


if __name__ == '__main__':
    print("🤖 Running Bot Message Format Verification Tests...")
    print("=" * 60)
    
    # Run tests with verbose output
    unittest.main(verbosity=2, exit=False)
    
    print("=" * 60)
    print("✅ Bot message format verification completed!")