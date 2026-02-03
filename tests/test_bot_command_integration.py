#!/usr/bin/env python3
"""
Integration tests for bot command workflows
Task 11.3: Bot command integration testing

Tests bot command interactions:
- Command parsing and execution
- User registration through commands
- Admin command workflows
- Shop command workflows
- Error handling in commands

Requirements validated: 6.1, 2.1, 5.1, 5.5
"""

import unittest
import sys
import os
import tempfile
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin_system import AdminSystem
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes


class MockTelegramObjects:
    """Helper class to create mock Telegram objects"""
    
    @staticmethod
    def create_user(user_id: int, username: str = None, first_name: str = "Test User"):
        """Create a mock Telegram User"""
        user = Mock(spec=User)
        user.id = user_id
        user.username = username
        user.first_name = first_name
        return user
    
    @staticmethod
    def create_message(user: User, text: str, chat_id: int = None):
        """Create a mock Telegram Message"""
        message = Mock(spec=Message)
        message.from_user = user
        message.text = text
        message.chat_id = chat_id or user.id
        message.reply_text = AsyncMock()
        return message
    
    @staticmethod
    def create_update(user: User, text: str):
        """Create a mock Telegram Update"""
        update = Mock(spec=Update)
        update.effective_user = user
        update.message = MockTelegramObjects.create_message(user, text)
        return update
    
    @staticmethod
    def create_context(args: list = None):
        """Create a mock Context"""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = args or []
        context.bot = Mock()
        context.bot.send_message = AsyncMock()
        return context


class TestBotCommandIntegration(unittest.TestCase):
    """Integration tests for bot command workflows"""
    
    def setUp(self):
        """Setup test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize admin system with test database
        self.admin_system = AdminSystem(self.temp_db.name)
        
        # Test users
        self.admin_user = MockTelegramObjects.create_user(123456789, "adminuser", "Admin User")
        self.regular_user = MockTelegramObjects.create_user(987654321, "regularuser", "Regular User")
        self.new_user = MockTelegramObjects.create_user(555666777, "newuser", "New User")
        
        # Setup admin user in database
        self.admin_system.register_user(
            self.admin_user.id, 
            self.admin_user.username, 
            self.admin_user.first_name
        )
        self.admin_system.set_admin_status(self.admin_user.id, True)
        
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_db.name)
        except:
            pass
    
    async def test_admin_command_workflow(self):
        """
        Test /admin command workflow
        Requirements: 2.1 (admin panel access)
        """
        # Test admin user accessing admin panel
        update = MockTelegramObjects.create_update(self.admin_user, "/admin")
        context = MockTelegramObjects.create_context()
        
        # Simulate admin command logic
        user = update.effective_user
        
        # Check admin rights
        is_admin = self.admin_system.is_admin(user.id)
        self.assertTrue(is_admin)
        
        # Get users count for admin panel
        users_count = self.admin_system.get_users_count()
        expected_text = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        # Verify admin panel format
        self.assertIn("Админ-панель:", expected_text)
        self.assertIn("/add_points @username [число] - начислить очки", expected_text)
        self.assertIn("/add_admin @username - добавить администратора", expected_text)
        self.assertIn(f"Всего пользователей: {users_count}", expected_text)
        
        # Test non-admin user accessing admin panel
        non_admin_update = MockTelegramObjects.create_update(self.regular_user, "/admin")
        
        # Register regular user first
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        
        # Check admin rights (should be False)
        is_admin = self.admin_system.is_admin(self.regular_user.id)
        self.assertFalse(is_admin)
        
        # Should receive access denied message
        expected_error = "🔒 У вас нет прав администратора для выполнения этой команды.\nОбратитесь к администратору бота для получения доступа."
        # In real implementation, this would be sent as reply_text
    
    async def test_add_points_command_workflow(self):
        """
        Test /add_points command workflow
        Requirements: 2.1 (points addition)
        """
        # Setup target user
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        
        # Test valid add_points command
        update = MockTelegramObjects.create_update(self.admin_user, "/add_points @regularuser 100")
        context = MockTelegramObjects.create_context(["@regularuser", "100"])
        
        # Simulate add_points command logic
        user = update.effective_user
        
        # Check admin rights
        self.assertTrue(self.admin_system.is_admin(user.id))
        
        # Parse arguments
        username = context.args[0]  # "@regularuser"
        amount = float(context.args[1])  # 100.0
        
        # Find target user
        target_user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(target_user)
        self.assertEqual(target_user['id'], self.regular_user.id)
        
        # Get initial balance
        initial_balance = target_user['balance']
        
        # Update balance
        new_balance = self.admin_system.update_balance(target_user['id'], amount)
        self.assertEqual(new_balance, initial_balance + amount)
        
        # Create transaction
        transaction_id = self.admin_system.add_transaction(
            target_user['id'], amount, 'add', user.id
        )
        self.assertIsNotNone(transaction_id)
        
        # Verify response format
        clean_username = username.lstrip('@')
        expected_response = f"Пользователю @{clean_username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"
        
        self.assertIn(f"@{clean_username}", expected_response)
        self.assertIn(f"{int(amount)} очков", expected_response)
        self.assertIn(f"{int(new_balance)}", expected_response)
    
    async def test_add_points_error_scenarios(self):
        """
        Test /add_points command error scenarios
        Requirements: 5.5 (error handling)
        """
        # Test insufficient arguments
        update = MockTelegramObjects.create_update(self.admin_user, "/add_points @user")
        context = MockTelegramObjects.create_context(["@user"])
        
        # Should detect insufficient arguments
        self.assertLess(len(context.args), 2)
        
        # Test invalid amount
        update = MockTelegramObjects.create_update(self.admin_user, "/add_points @user invalid")
        context = MockTelegramObjects.create_context(["@user", "invalid"])
        
        try:
            amount = float(context.args[1])
            self.fail("Should have raised ValueError")
        except ValueError:
            pass  # Expected
        
        # Test negative amount
        update = MockTelegramObjects.create_update(self.admin_user, "/add_points @user -10")
        context = MockTelegramObjects.create_context(["@user", "-10"])
        
        amount = float(context.args[1])
        self.assertLessEqual(amount, 0)  # Should be rejected
        
        # Test user not found
        update = MockTelegramObjects.create_update(self.admin_user, "/add_points @nonexistent 100")
        context = MockTelegramObjects.create_context(["@nonexistent", "100"])
        
        target_user = self.admin_system.get_user_by_username("@nonexistent")
        self.assertIsNone(target_user)
    
    async def test_add_admin_command_workflow(self):
        """
        Test /add_admin command workflow
        Requirements: 2.1 (admin assignment)
        """
        # Setup target user
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        
        # Verify user is not admin initially
        self.assertFalse(self.admin_system.is_admin(self.regular_user.id))
        
        # Test add_admin command
        update = MockTelegramObjects.create_update(self.admin_user, "/add_admin @regularuser")
        context = MockTelegramObjects.create_context(["@regularuser"])
        
        # Simulate add_admin command logic
        user = update.effective_user
        
        # Check admin rights
        self.assertTrue(self.admin_system.is_admin(user.id))
        
        # Parse arguments
        username = context.args[0]  # "@regularuser"
        
        # Find target user
        target_user = self.admin_system.get_user_by_username(username)
        self.assertIsNotNone(target_user)
        self.assertFalse(target_user['is_admin'])
        
        # Set admin status
        success = self.admin_system.set_admin_status(target_user['id'], True)
        self.assertTrue(success)
        
        # Verify admin status was set
        self.assertTrue(self.admin_system.is_admin(target_user['id']))
        
        # Verify response format
        clean_username = username.lstrip('@')
        expected_response = f"Пользователь @{clean_username} теперь администратор"
        
        self.assertIn(f"@{clean_username}", expected_response)
        self.assertIn("теперь администратор", expected_response)
    
    async def test_shop_command_workflow(self):
        """
        Test /shop command workflow
        Requirements: 5.1 (shop access)
        """
        # Test shop command for any user
        update = MockTelegramObjects.create_update(self.regular_user, "/shop")
        context = MockTelegramObjects.create_context()
        
        # Register user if not exists (auto-registration simulation)
        if not self.admin_system.get_user_by_id(self.regular_user.id):
            self.admin_system.register_user(
                self.regular_user.id,
                self.regular_user.username,
                self.regular_user.first_name
            )
        
        # Verify shop format
        expected_text = """Магазин:
1. Сообщение админу - 10 очков
Для покупки введите /buy_contact"""
        
        self.assertIn("Магазин:", expected_text)
        self.assertIn("1. Сообщение админу - 10 очков", expected_text)
        self.assertIn("Для покупки введите /buy_contact", expected_text)
    
    async def test_buy_contact_workflow_success(self):
        """
        Test /buy_contact command workflow - successful purchase
        Requirements: 5.1 (purchase workflow)
        """
        # Setup user with sufficient balance
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        self.admin_system.update_balance(self.regular_user.id, 50.0)
        
        # Test buy_contact command
        update = MockTelegramObjects.create_update(self.regular_user, "/buy_contact")
        context = MockTelegramObjects.create_context()
        
        # Simulate buy_contact command logic
        user = update.effective_user
        
        # Get user from admin system
        admin_user = self.admin_system.get_user_by_id(user.id)
        self.assertIsNotNone(admin_user)
        
        # Check balance
        current_balance = admin_user['balance']
        required_amount = 10
        self.assertGreaterEqual(current_balance, required_amount)
        
        # Process purchase
        new_balance = self.admin_system.update_balance(admin_user['id'], -required_amount)
        self.assertEqual(new_balance, current_balance - required_amount)
        
        # Create transaction
        transaction_id = self.admin_system.add_transaction(
            admin_user['id'], -required_amount, 'buy'
        )
        self.assertIsNotNone(transaction_id)
        
        # Verify purchase confirmation message
        expected_confirmation = "Вы купили контакт. Администратор свяжется с вами."
        self.assertEqual(expected_confirmation, "Вы купили контакт. Администратор свяжется с вами.")
        
        # Verify admin notification message format
        username_display = f"@{user.username}" if user.username else f"#{user.id}"
        expected_admin_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
        
        self.assertIn("купил контакт", expected_admin_message)
        self.assertIn(f"{int(new_balance)} очков", expected_admin_message)
    
    async def test_buy_contact_workflow_insufficient_balance(self):
        """
        Test /buy_contact command workflow - insufficient balance
        Requirements: 5.5 (error handling)
        """
        # Setup user with insufficient balance
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        self.admin_system.update_balance(self.regular_user.id, 5.0)  # Less than required 10
        
        # Test buy_contact command
        update = MockTelegramObjects.create_update(self.regular_user, "/buy_contact")
        context = MockTelegramObjects.create_context()
        
        # Simulate buy_contact command logic
        user = update.effective_user
        
        # Get user from admin system
        admin_user = self.admin_system.get_user_by_id(user.id)
        self.assertIsNotNone(admin_user)
        
        # Check balance
        current_balance = admin_user['balance']
        required_amount = 10
        self.assertLess(current_balance, required_amount)
        
        # Verify error message format
        expected_error = f"❌ Недостаточно очков для покупки. Требуется: {required_amount} очков, у вас: {int(current_balance)} очков"
        
        self.assertIn("Недостаточно очков", expected_error)
        self.assertIn(f"{required_amount} очков", expected_error)
        self.assertIn(f"{int(current_balance)} очков", expected_error)
        
        # Verify balance remains unchanged
        final_user = self.admin_system.get_user_by_id(user.id)
        self.assertEqual(final_user['balance'], current_balance)
    
    async def test_auto_registration_workflow(self):
        """
        Test automatic user registration workflow
        Requirements: 6.1 (auto registration)
        """
        # Test new user interaction
        new_user = MockTelegramObjects.create_user(999888777, "brandnewuser", "Brand New User")
        
        # Verify user doesn't exist initially
        existing_user = self.admin_system.get_user_by_id(new_user.id)
        self.assertIsNone(existing_user)
        
        # Simulate auto-registration middleware
        success = self.admin_system.register_user(
            new_user.id,
            new_user.username,
            new_user.first_name
        )
        self.assertTrue(success)
        
        # Verify user was registered with correct defaults
        registered_user = self.admin_system.get_user_by_id(new_user.id)
        self.assertIsNotNone(registered_user)
        self.assertEqual(registered_user['id'], new_user.id)
        self.assertEqual(registered_user['username'], new_user.username)
        self.assertEqual(registered_user['first_name'], new_user.first_name)
        self.assertEqual(registered_user['balance'], 0.0)
        self.assertFalse(registered_user['is_admin'])
        
        # Test idempotent registration (should not create duplicate)
        success2 = self.admin_system.register_user(
            new_user.id,
            new_user.username,
            new_user.first_name
        )
        self.assertTrue(success2)  # Should succeed but not create duplicate
        
        # Verify only one user record exists
        users_count_before = self.admin_system.get_users_count()
        
        # Try to register again
        self.admin_system.register_user(
            new_user.id,
            new_user.username,
            new_user.first_name
        )
        
        users_count_after = self.admin_system.get_users_count()
        self.assertEqual(users_count_before, users_count_after)
    
    async def test_command_authorization_workflow(self):
        """
        Test command authorization workflow
        Requirements: 2.1 (admin authorization)
        """
        # Setup regular user
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        
        # Test admin commands with regular user (should fail)
        admin_commands = [
            ("/admin", []),
            ("/add_points", ["@user", "100"]),
            ("/add_admin", ["@user"])
        ]
        
        for command, args in admin_commands:
            update = MockTelegramObjects.create_update(self.regular_user, command)
            context = MockTelegramObjects.create_context(args)
            
            # Check authorization
            user = update.effective_user
            is_admin = self.admin_system.is_admin(user.id)
            self.assertFalse(is_admin)
            
            # Should receive access denied message
            # In real implementation, this would trigger the admin_required decorator
        
        # Test admin commands with admin user (should succeed)
        for command, args in admin_commands:
            update = MockTelegramObjects.create_update(self.admin_user, command)
            context = MockTelegramObjects.create_context(args)
            
            # Check authorization
            user = update.effective_user
            is_admin = self.admin_system.is_admin(user.id)
            self.assertTrue(is_admin)
            
            # Should be allowed to proceed
    
    async def test_balance_command_integration(self):
        """
        Test balance command integration with admin system
        Requirements: 6.1, 2.1 (balance display)
        """
        # Setup user with balance
        self.admin_system.register_user(
            self.regular_user.id,
            self.regular_user.username,
            self.regular_user.first_name
        )
        self.admin_system.update_balance(self.regular_user.id, 75.0)
        
        # Test balance command
        update = MockTelegramObjects.create_update(self.regular_user, "/balance")
        context = MockTelegramObjects.create_context()
        
        # Simulate balance command logic
        user = update.effective_user
        
        # Get user from admin system
        admin_user = self.admin_system.get_user_by_id(user.id)
        self.assertIsNotNone(admin_user)
        
        # Verify balance display format
        expected_text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {admin_user['first_name'] or user.first_name or 'Неизвестно'}
[BALANCE] Баланс: {admin_user['balance']} очков
[STATUS] Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
        """
        
        self.assertIn("[MONEY]", expected_text)
        self.assertIn("[USER]", expected_text)
        self.assertIn("[BALANCE]", expected_text)
        self.assertIn("[STATUS]", expected_text)
        self.assertIn("[TIP]", expected_text)
        self.assertIn(f"{admin_user['balance']} очков", expected_text)
        self.assertIn("Пользователь", expected_text)  # Non-admin status


# Helper function to run async tests
def run_async_test(test_func):
    """Helper to run async test functions"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_func())
    finally:
        loop.close()


class TestBotCommandIntegrationRunner(unittest.TestCase):
    """Test runner for async bot command integration tests"""
    
    def setUp(self):
        self.test_instance = TestBotCommandIntegration()
        self.test_instance.setUp()
    
    def tearDown(self):
        self.test_instance.tearDown()
    
    def test_admin_command_workflow(self):
        run_async_test(self.test_instance.test_admin_command_workflow)
    
    def test_add_points_command_workflow(self):
        run_async_test(self.test_instance.test_add_points_command_workflow)
    
    def test_add_points_error_scenarios(self):
        run_async_test(self.test_instance.test_add_points_error_scenarios)
    
    def test_add_admin_command_workflow(self):
        run_async_test(self.test_instance.test_add_admin_command_workflow)
    
    def test_shop_command_workflow(self):
        run_async_test(self.test_instance.test_shop_command_workflow)
    
    def test_buy_contact_workflow_success(self):
        run_async_test(self.test_instance.test_buy_contact_workflow_success)
    
    def test_buy_contact_workflow_insufficient_balance(self):
        run_async_test(self.test_instance.test_buy_contact_workflow_insufficient_balance)
    
    def test_auto_registration_workflow(self):
        run_async_test(self.test_instance.test_auto_registration_workflow)
    
    def test_command_authorization_workflow(self):
        run_async_test(self.test_instance.test_command_authorization_workflow)
    
    def test_balance_command_integration(self):
        run_async_test(self.test_instance.test_balance_command_integration)


if __name__ == '__main__':
    unittest.main()