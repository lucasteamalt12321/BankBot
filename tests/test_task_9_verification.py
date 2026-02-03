#!/usr/bin/env python3
"""
Verification test for Task 9: Обновить существующие команды для совместимости
Tests both subtasks:
- 9.1 Обновить команду /start для новой системы регистрации
- 9.2 Обновить команду /balance для новой структуры БД
"""

import os
import sys
import sqlite3
import asyncio
import tempfile
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin_system import AdminSystem
from utils.admin_middleware import auto_registration_middleware
from bot.bot import TelegramBot


class TestTask9Verification:
    """Test class for verifying Task 9 functionality"""
    
    def __init__(self):
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize admin system with test database
        self.admin_system = AdminSystem(self.db_path)
        
        # Create bot instance for testing
        self.bot = TelegramBot()
        self.bot.admin_system = self.admin_system
    
    def cleanup(self):
        """Clean up test database"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def create_mock_update(self, user_id: int, username: str = None, first_name: str = "Test User", text: str = "/start"):
        """Create a mock Telegram update for testing"""
        user = User(
            id=user_id,
            is_bot=False,
            first_name=first_name,
            username=username
        )
        
        chat = Chat(id=user_id, type="private")
        
        message = Mock(spec=Message)
        message.from_user = user
        message.chat = chat
        message.text = text
        message.reply_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.effective_user = user
        update.message = message
        
        return update
    
    def create_mock_context(self):
        """Create a mock context for testing"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context
    
    async def test_start_command_registration(self):
        """Test that /start command properly registers users in admin system"""
        print("Testing /start command with new registration system...")
        
        # Test data
        user_id = 12345
        username = "testuser"
        first_name = "Test User"
        
        # Verify user doesn't exist initially
        user = self.admin_system.get_user_by_id(user_id)
        assert user is None, "User should not exist initially"
        
        # Create mock update and context
        update = self.create_mock_update(user_id, username, first_name, "/start")
        context = self.create_mock_context()
        
        # Call the welcome command
        await self.bot.welcome_command(update, context)
        
        # Verify user was registered in admin system
        user = self.admin_system.get_user_by_id(user_id)
        assert user is not None, "User should be registered after /start command"
        assert user['id'] == user_id, f"User ID should be {user_id}"
        assert user['username'] == username, f"Username should be {username}"
        assert user['first_name'] == first_name, f"First name should be {first_name}"
        assert user['balance'] == 0, "Initial balance should be 0"
        assert user['is_admin'] == False, "User should not be admin initially"
        
        # Verify welcome message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        
        # Check that welcome message contains expected content
        assert "Добро пожаловать" in message_text, "Welcome message should contain greeting"
        assert "/balance" in message_text, "Welcome message should mention /balance command"
        assert "/shop" in message_text, "Welcome message should mention /shop command"
        
        print("✅ /start command registration test passed")
    
    async def test_start_command_idempotence(self):
        """Test that /start command doesn't create duplicate users"""
        print("Testing /start command idempotence...")
        
        # Test data
        user_id = 12346
        username = "testuser2"
        first_name = "Test User 2"
        
        # Register user first time
        update = self.create_mock_update(user_id, username, first_name, "/start")
        context = self.create_mock_context()
        await self.bot.welcome_command(update, context)
        
        # Get initial user data
        user1 = self.admin_system.get_user_by_id(user_id)
        assert user1 is not None, "User should exist after first registration"
        
        # Call /start again
        update2 = self.create_mock_update(user_id, username, first_name, "/start")
        context2 = self.create_mock_context()
        await self.bot.welcome_command(update2, context2)
        
        # Verify user data is the same (no duplicate)
        user2 = self.admin_system.get_user_by_id(user_id)
        assert user2 is not None, "User should still exist"
        assert user1['id'] == user2['id'], "User ID should be the same"
        assert user1['username'] == user2['username'], "Username should be the same"
        assert user1['balance'] == user2['balance'], "Balance should be the same"
        
        # Verify only one user exists in database
        conn = self.admin_system.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE id = ?", (user_id,))
        count = cursor.fetchone()['count']
        conn.close()
        
        assert count == 1, f"Should have exactly 1 user record, found {count}"
        
        print("✅ /start command idempotence test passed")
    
    async def test_balance_command_admin_system(self):
        """Test that /balance command works with new admin system"""
        print("Testing /balance command with admin system...")
        
        # Test data
        user_id = 12347
        username = "testuser3"
        first_name = "Test User 3"
        initial_balance = 150.5
        
        # Register user and set balance
        self.admin_system.register_user(user_id, username, first_name)
        self.admin_system.update_balance(user_id, initial_balance)
        
        # Create mock update and context
        update = self.create_mock_update(user_id, username, first_name, "/balance")
        context = self.create_mock_context()
        
        # Call balance command
        await self.bot.balance_command(update, context)
        
        # Verify balance message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        
        # Check that balance message contains expected content
        assert "Ваш баланс" in message_text, "Balance message should contain balance header"
        assert str(int(initial_balance)) in message_text, "Balance message should contain correct balance"
        assert first_name in message_text, "Balance message should contain user name"
        assert "очков" in message_text, "Balance message should mention points"
        
        print("✅ /balance command admin system test passed")
    
    async def test_balance_command_auto_registration(self):
        """Test that /balance command auto-registers users"""
        print("Testing /balance command auto-registration...")
        
        # Test data
        user_id = 12348
        username = "testuser4"
        first_name = "Test User 4"
        
        # Verify user doesn't exist initially
        user = self.admin_system.get_user_by_id(user_id)
        assert user is None, "User should not exist initially"
        
        # Create mock update and context
        update = self.create_mock_update(user_id, username, first_name, "/balance")
        context = self.create_mock_context()
        
        # Call balance command
        await self.bot.balance_command(update, context)
        
        # Verify user was auto-registered
        user = self.admin_system.get_user_by_id(user_id)
        assert user is not None, "User should be auto-registered"
        assert user['id'] == user_id, f"User ID should be {user_id}"
        assert user['username'] == username, f"Username should be {username}"
        assert user['first_name'] == first_name, f"First name should be {first_name}"
        assert user['balance'] == 0, "Initial balance should be 0"
        
        # Verify balance message was sent
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        
        # Check that balance message shows 0 balance for new user
        assert "0 очков" in message_text, "New user should have 0 balance"
        
        print("✅ /balance command auto-registration test passed")
    
    async def test_balance_command_admin_status(self):
        """Test that /balance command shows admin status correctly"""
        print("Testing /balance command admin status display...")
        
        # Test data
        user_id = 12349
        username = "adminuser"
        first_name = "Admin User"
        
        # Register user and make admin
        self.admin_system.register_user(user_id, username, first_name)
        self.admin_system.set_admin_status(user_id, True)
        self.admin_system.update_balance(user_id, 100)
        
        # Create mock update and context
        update = self.create_mock_update(user_id, username, first_name, "/balance")
        context = self.create_mock_context()
        
        # Call balance command
        await self.bot.balance_command(update, context)
        
        # Verify balance message shows admin status
        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        message_text = call_args[0][0]
        
        assert "Администратор" in message_text, "Admin user should show admin status"
        assert "100 очков" in message_text, "Should show correct balance"
        
        print("✅ /balance command admin status test passed")
    
    async def test_middleware_auto_registration(self):
        """Test that auto-registration middleware works correctly"""
        print("Testing auto-registration middleware...")
        
        # Test data
        user_id = 12350
        username = "middlewareuser"
        first_name = "Middleware User"
        
        # Verify user doesn't exist initially
        user = self.admin_system.get_user_by_id(user_id)
        assert user is None, "User should not exist initially"
        
        # Create mock update and context
        update = self.create_mock_update(user_id, username, first_name, "/any_command")
        context = self.create_mock_context()
        
        # Process through middleware
        await auto_registration_middleware.process_message(update, context)
        
        # Verify user was registered
        user = self.admin_system.get_user_by_id(user_id)
        assert user is not None, "User should be registered by middleware"
        assert user['id'] == user_id, f"User ID should be {user_id}"
        assert user['username'] == username, f"Username should be {username}"
        assert user['first_name'] == first_name, f"First name should be {first_name}"
        
        print("✅ Auto-registration middleware test passed")
    
    async def run_all_tests(self):
        """Run all verification tests"""
        print("=" * 60)
        print("TASK 9 VERIFICATION TESTS")
        print("=" * 60)
        
        try:
            await self.test_start_command_registration()
            await self.test_start_command_idempotence()
            await self.test_balance_command_admin_system()
            await self.test_balance_command_auto_registration()
            await self.test_balance_command_admin_status()
            await self.test_middleware_auto_registration()
            
            print("=" * 60)
            print("✅ ALL TASK 9 TESTS PASSED!")
            print("=" * 60)
            print()
            print("VERIFICATION SUMMARY:")
            print("✅ Task 9.1: /start command updated for new registration system")
            print("✅ Task 9.2: /balance command updated for new database structure")
            print("✅ Auto-registration middleware working correctly")
            print("✅ Admin system integration functional")
            print("✅ Database compatibility maintained")
            print()
            return True
            
        except Exception as e:
            print(f"❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self.cleanup()


async def main():
    """Main test function"""
    tester = TestTask9Verification()
    success = await tester.run_all_tests()
    
    if success:
        print("Task 9 verification completed successfully!")
        return 0
    else:
        print("Task 9 verification failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)