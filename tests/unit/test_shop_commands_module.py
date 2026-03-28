"""
Unit tests for shop commands module.

Tests the ShopCommands class moved from bot.py as part of Task 10.2.3.
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from bot.commands.shop_commands import ShopCommands
from utils.admin.admin_system import AdminSystem


class TestShopCommandsModule(unittest.TestCase):
    """Test suite for ShopCommands module"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock AdminSystem
        self.mock_admin_system = Mock(spec=AdminSystem)
        
        # Create ShopCommands instance
        self.shop_commands = ShopCommands(admin_system=self.mock_admin_system)
    
    def test_shop_commands_initialization(self):
        """Test ShopCommands class initialization"""
        self.assertIsNotNone(self.shop_commands)
        self.assertEqual(self.shop_commands.admin_system, self.mock_admin_system)
    
    def test_shop_commands_has_required_methods(self):
        """Test that ShopCommands has all required command methods"""
        required_methods = [
            'shop_command',
            'buy_contact_command',
            'buy_command',
            'buy_1_command',
            'buy_2_command',
            'buy_3_command',
            'buy_4_command',
            'buy_5_command',
            'buy_6_command',
            'buy_7_command',
            'buy_8_command',
            'inventory_command',
            '_handle_purchase_command'
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(self.shop_commands, method_name),
                f"ShopCommands should have {method_name} method"
            )
            method = getattr(self.shop_commands, method_name)
            self.assertTrue(
                callable(method),
                f"{method_name} should be callable"
            )
    
    @patch('bot.commands.shop_commands.auto_registration_middleware')
    @patch('bot.commands.shop_commands.get_db')
    async def test_shop_command_basic(self, mock_get_db, mock_middleware):
        """Test basic shop command execution"""
        # Mock update and context
        mock_update = AsyncMock()
        mock_update.effective_user = Mock(id=12345)
        mock_update.message = AsyncMock()
        mock_context = AsyncMock()
        
        # Mock middleware
        mock_middleware.process_message = AsyncMock()
        
        # Mock database
        mock_db = Mock()
        mock_get_db.return_value = iter([mock_db])
        
        # Mock ShopHandler
        with patch('bot.commands.shop_commands.ShopHandler') as mock_shop_handler:
            mock_handler_instance = Mock()
            mock_handler_instance.display_shop.return_value = "🛒 МАГАЗИН\n\nТовары..."
            mock_shop_handler.return_value = mock_handler_instance
            
            # Execute command
            await self.shop_commands.shop_command(mock_update, mock_context)
            
            # Verify middleware was called
            mock_middleware.process_message.assert_called_once()
            
            # Verify message was sent
            mock_update.message.reply_text.assert_called_once()
    
    @patch('bot.commands.shop_commands.auto_registration_middleware')
    async def test_buy_contact_command_insufficient_balance(self, mock_middleware):
        """Test buy_contact command with insufficient balance"""
        # Mock update and context
        mock_update = AsyncMock()
        mock_update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
        mock_update.message = AsyncMock()
        mock_context = AsyncMock()
        
        # Mock middleware
        mock_middleware.process_message = AsyncMock()
        
        # Mock admin system - user with insufficient balance
        self.mock_admin_system.get_user_by_username.return_value = {
            'id': 1,
            'telegram_id': 12345,
            'username': 'testuser',
            'first_name': 'Test',
            'balance': 5,  # Less than required 10
            'is_admin': False
        }
        
        # Execute command
        await self.shop_commands.buy_contact_command(mock_update, mock_context)
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        self.assertIn("Недостаточно очков", call_args)
    
    @patch('bot.commands.shop_commands.auto_registration_middleware')
    async def test_buy_command_no_args(self, mock_middleware):
        """Test buy command without arguments"""
        # Mock update and context
        mock_update = AsyncMock()
        mock_update.effective_user = Mock(id=12345)
        mock_update.message = AsyncMock()
        mock_context = AsyncMock()
        mock_context.args = []  # No arguments
        
        # Mock middleware
        mock_middleware.process_message = AsyncMock()
        
        # Execute command
        await self.shop_commands.buy_command(mock_update, mock_context)
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        self.assertIn("Укажите номер товара", call_args)
    
    @patch('bot.commands.shop_commands.auto_registration_middleware')
    async def test_buy_command_invalid_number(self, mock_middleware):
        """Test buy command with invalid item number"""
        # Mock update and context
        mock_update = AsyncMock()
        mock_update.effective_user = Mock(id=12345)
        mock_update.message = AsyncMock()
        mock_context = AsyncMock()
        mock_context.args = ["abc"]  # Invalid number
        
        # Mock middleware
        mock_middleware.process_message = AsyncMock()
        
        # Execute command
        await self.shop_commands.buy_command(mock_update, mock_context)
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        self.assertIn("Неверный номер товара", call_args)


def run_tests():
    """Run the test suite"""
    print("\n" + "="*70)
    print("Testing ShopCommands Module (Task 10.2.3)")
    print("="*70 + "\n")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestShopCommandsModule)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ All ShopCommands module tests passed!")
    else:
        print("❌ Some tests failed")
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
