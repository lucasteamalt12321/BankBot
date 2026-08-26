"""
Unit tests for shop commands module (function-based API).

Tests the shop command functions moved out of the monolith bot.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

import bot.commands.shop_commands as shop_commands


@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.effective_user = Mock(id=12345, username="testuser", first_name="Test")
    update.message = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.args = []
    return context


def test_shop_commands_has_required_functions():
    """Test that shop module exposes all required command functions."""
    required_methods = [
        'shop_command',
        'buy_contact_command',
        'buy_command',
        'inventory_command',
        '_handle_purchase',
    ]
    for method_name in required_methods:
        assert hasattr(shop_commands, method_name), f"shop module should have {method_name}"
        assert callable(getattr(shop_commands, method_name))


@patch('bot.commands.shop_commands.ShopHandler')
@patch('bot.commands.shop_commands.auto_registration_middleware')
@patch('bot.commands.shop_commands.get_db')
async def test_shop_command_basic(mock_get_db, mock_middleware, mock_shop_handler, mock_update, mock_context):
    """Test basic shop command execution"""
    mock_middleware.process_message = AsyncMock()

    mock_db = Mock()
    mock_get_db.return_value = iter([mock_db])

    mock_handler_instance = Mock()
    mock_handler_instance.display_shop.return_value = "🛒 МАГАЗИН\n\nТовары..."
    mock_shop_handler.return_value = mock_handler_instance

    await shop_commands.shop_command(mock_update, mock_context)

    mock_middleware.process_message.assert_called_once()
    mock_update.message.reply_text.assert_called_once()


@patch('bot.commands.shop_commands.build_services')
async def test_buy_contact_command_insufficient_balance(mock_build_services, mock_update, mock_context):
    """Test buy_contact command with insufficient balance"""
    mock_svc = Mock()
    mock_svc.admin_service.get_user_by_username.return_value = {
        'id': 1,
        'telegram_id': 12345,
        'username': 'testuser',
        'first_name': 'Test',
        'balance': 5,  # Less than required 10
        'is_admin': False,
    }
    mock_svc.admin_service.register_user.return_value = True
    mock_svc.admin_service.update_balance.return_value = 5
    mock_svc.admin_service.add_transaction.return_value = None
    mock_build_services.return_value.__enter__.return_value = mock_svc

    await shop_commands.buy_contact_command(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Недостаточно очков" in call_args


@patch('bot.commands.shop_commands.auto_registration_middleware')
async def test_buy_command_no_args(mock_middleware, mock_update, mock_context):
    """Test buy command without arguments"""
    mock_middleware.process_message = AsyncMock()
    mock_context.args = []

    await shop_commands.buy_command(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Укажите номер товара" in call_args


@patch('bot.commands.shop_commands.auto_registration_middleware')
async def test_buy_command_invalid_number(mock_middleware, mock_update, mock_context):
    """Test buy command with invalid item number"""
    mock_middleware.process_message = AsyncMock()
    mock_context.args = ["abc"]

    await shop_commands.buy_command(mock_update, mock_context)

    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Неверный номер товара" in call_args


if __name__ == '__main__':
    import pytest as _pytest
    _pytest.main([__file__, '-v'])
