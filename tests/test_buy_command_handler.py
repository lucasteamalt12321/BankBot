"""
Unit tests for the /buy command handler integration with ShopManager
Tests the command parsing, ShopManager integration, and response formatting
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.advanced_models import PurchaseResult
from database.database import User, ShopItem


class TestBuyCommandHandler:
    """Test cases for the /buy command handler"""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update object"""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        return update
    
    @pytest.fixture
    def mock_context_with_args(self):
        """Create a mock context with command arguments"""
        context = Mock()
        context.args = ["1"]  # /buy 1
        return context
    
    @pytest.fixture
    def mock_context_no_args(self):
        """Create a mock context without arguments"""
        context = Mock()
        context.args = []
        return context
    
    @pytest.fixture
    def mock_context_invalid_args(self):
        """Create a mock context with invalid arguments"""
        context = Mock()
        context.args = ["invalid"]
        return context
    
    @pytest.fixture
    def mock_successful_purchase_result(self):
        """Create a successful purchase result"""
        return PurchaseResult(
            success=True,
            message="Покупка успешна! Безлимитные стикеры активированы на 24 часа",
            purchase_id=123,
            new_balance=Decimal('950')
        )
    
    @pytest.fixture
    def mock_failed_purchase_result(self):
        """Create a failed purchase result"""
        return PurchaseResult(
            success=False,
            message="Недостаточно средств. Нужно 100, у вас 50",
            error_code="INSUFFICIENT_BALANCE"
        )
    
    @pytest.fixture
    def mock_shop_item(self):
        """Create a mock shop item"""
        item = Mock()
        item.name = "Безлимитные стикеры"
        item.price = 100
        return item
    
    def test_buy_command_no_arguments(self, mock_update, mock_context_no_args):
        """Test /buy command without arguments shows usage message"""
        from bot.bot import TelegramBot
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_command(mock_update, mock_context_no_args))
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "❌ Укажите номер товара!" in call_args
        assert "Использование: /buy <номер_товара>" in call_args
        assert "/shop" in call_args
    
    def test_buy_command_invalid_arguments(self, mock_update, mock_context_invalid_args):
        """Test /buy command with invalid arguments shows error message"""
        from bot.bot import TelegramBot
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_command(mock_update, mock_context_invalid_args))
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "❌ Неверный номер товара!" in call_args
        assert "Номер товара должен быть числом" in call_args
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_command_successful_purchase(self, mock_shop_manager_class, mock_middleware, 
                                           mock_get_db, mock_update, mock_context_with_args, 
                                           mock_successful_purchase_result, mock_shop_item):
        """Test successful purchase through /buy command"""
        from bot.bot import TelegramBot
        
        # Setup mocks
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(return_value=mock_successful_purchase_result)
        mock_shop_manager.get_shop_items.return_value = [mock_shop_item]
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_command(mock_update, mock_context_with_args))
        
        # Verify ShopManager was called correctly
        mock_shop_manager.process_purchase.assert_called_once_with(12345, 1)
        
        # Verify success message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "✅" in call_args
        assert "Покупка успешна!" in call_args
        assert "950 монет" in call_args
        assert "ID покупки: 123" in call_args
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_command_failed_purchase(self, mock_shop_manager_class, mock_middleware, 
                                       mock_get_db, mock_update, mock_context_with_args, 
                                       mock_failed_purchase_result):
        """Test failed purchase through /buy command"""
        from bot.bot import TelegramBot
        
        # Setup mocks
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(return_value=mock_failed_purchase_result)
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_command(mock_update, mock_context_with_args))
        
        # Verify error message was sent with helpful suggestion
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "❌" in call_args
        assert "Недостаточно средств" in call_args
        assert "💡 Заработайте больше монет" in call_args
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_command_exception_handling(self, mock_shop_manager_class, mock_middleware, 
                                          mock_get_db, mock_update, mock_context_with_args):
        """Test exception handling in /buy command"""
        from bot.bot import TelegramBot
        
        # Setup mocks to raise exception
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(side_effect=Exception("Database error"))
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_command(mock_update, mock_context_with_args))
        
        # Verify error message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "❌ Произошла ошибка при обработке покупки" in call_args
        assert "администратору" in call_args


class TestBuyNumberCommandHandler:
    """Test cases for the /buy_1, /buy_2, /buy_3 command handlers"""
    
    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update object"""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        return update
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock context"""
        return Mock()
    
    @pytest.fixture
    def mock_successful_purchase_result(self):
        """Create a successful purchase result"""
        return PurchaseResult(
            success=True,
            message="Покупка успешна! Безлимитные стикеры активированы на 24 часа",
            purchase_id=456,
            new_balance=Decimal('850')
        )
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_1_command_successful(self, mock_shop_manager_class, mock_middleware, 
                                    mock_get_db, mock_update, mock_context, 
                                    mock_successful_purchase_result):
        """Test successful /buy_1 command"""
        from bot.bot import TelegramBot
        
        # Setup mocks
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(return_value=mock_successful_purchase_result)
        mock_shop_manager.get_shop_items.return_value = [Mock(name="Test Item", price=100)]
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_1_command(mock_update, mock_context))
        
        # Verify ShopManager was called with item number 1
        mock_shop_manager.process_purchase.assert_called_once_with(12345, 1)
        
        # Verify success message was sent
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "✅" in call_args
        assert "Покупка успешна!" in call_args
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_2_command_successful(self, mock_shop_manager_class, mock_middleware, 
                                    mock_get_db, mock_update, mock_context, 
                                    mock_successful_purchase_result):
        """Test successful /buy_2 command"""
        from bot.bot import TelegramBot
        
        # Setup mocks
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(return_value=mock_successful_purchase_result)
        mock_shop_manager.get_shop_items.return_value = [Mock(name="Test Item", price=100)]
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_2_command(mock_update, mock_context))
        
        # Verify ShopManager was called with item number 2
        mock_shop_manager.process_purchase.assert_called_once_with(12345, 2)
    
    @patch('bot.bot.get_db')
    @patch('bot.bot.auto_registration_middleware')
    @patch('core.shop_manager.ShopManager')
    def test_buy_3_command_successful(self, mock_shop_manager_class, mock_middleware, 
                                    mock_get_db, mock_update, mock_context, 
                                    mock_successful_purchase_result):
        """Test successful /buy_3 command"""
        from bot.bot import TelegramBot
        
        # Setup mocks
        mock_middleware.process_message = AsyncMock()
        mock_db = Mock()
        mock_get_db.return_value.__next__.return_value = mock_db
        
        mock_shop_manager = Mock()
        mock_shop_manager.process_purchase = AsyncMock(return_value=mock_successful_purchase_result)
        mock_shop_manager.get_shop_items.return_value = [Mock(name="Test Item", price=100)]
        mock_shop_manager_class.return_value = mock_shop_manager
        
        bot = TelegramBot()
        
        # Run the command
        asyncio.run(bot.buy_3_command(mock_update, mock_context))
        
        # Verify ShopManager was called with item number 3
        mock_shop_manager.process_purchase.assert_called_once_with(12345, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])