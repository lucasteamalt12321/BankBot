"""
Unit tests for system commands module.

Tests the SystemCommands class to ensure system commands work correctly.
Created as part of Task 10.2.5 - Переместить system команды
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from bot.commands.system_commands import SystemCommands
from utils.admin.admin_system import AdminSystem


@pytest.fixture
def mock_admin_system():
    """Create a mock AdminSystem"""
    admin_system = Mock(spec=AdminSystem)
    admin_system.is_admin = Mock(return_value=False)
    admin_system.get_user_by_id = Mock(return_value=None)
    return admin_system


@pytest.fixture
def system_commands(mock_admin_system):
    """Create SystemCommands instance with mocked dependencies"""
    return SystemCommands(admin_system=mock_admin_system)


@pytest.fixture
def mock_update():
    """Create a mock Update object"""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object"""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context


class TestSystemCommands:
    """Test suite for SystemCommands class"""

    @pytest.mark.asyncio
    async def test_help_command(self, system_commands, mock_update, mock_context):
        """Test /help command displays help text"""
        await system_commands.help_command(mock_update, mock_context)

        # Verify reply_text was called
        mock_update.message.reply_text.assert_called_once()

        # Verify the help text contains expected sections
        call_args = mock_update.message.reply_text.call_args
        help_text = call_args[0][0]

        assert "Справка по командам" in help_text
        assert "/start" in help_text
        assert "/help" in help_text
        assert "/profile" in help_text
        assert "/shop" in help_text
        assert "/games" in help_text
        assert "parse_mode" in call_args[1]
        assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_beta_command(self, system_commands, mock_update, mock_context):
        """Test /beta command displays beta features"""
        await system_commands.beta_command(mock_update, mock_context)

        # Verify reply_text was called
        mock_update.message.reply_text.assert_called_once()

        # Verify the beta text contains expected sections
        call_args = mock_update.message.reply_text.call_args
        beta_text = call_args[0][0]

        assert "Бета-функции" in beta_text
        assert "/market" in beta_text
        assert "/quests" in beta_text
        assert "/leaderboard" in beta_text
        assert "parse_mode" in call_args[1]
        assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_about_command(self, system_commands, mock_update, mock_context):
        """Test /about command displays bot information"""
        await system_commands.about_command(mock_update, mock_context)

        # Verify reply_text was called
        mock_update.message.reply_text.assert_called_once()

        # Verify the about text contains expected information
        call_args = mock_update.message.reply_text.call_args
        about_text = call_args[0][0]

        assert "LucasTeam Bank" in about_text
        assert "Shmalala" in about_text
        assert "GD Cards" in about_text
        assert "True Mafia" in about_text
        assert "Bunker RP" in about_text
        assert "parse_mode" in call_args[1]
        assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_help_command_logs_access(self, system_commands, mock_update, mock_context):
        """Test that help command logs user access"""
        with patch('bot.commands.system_commands.logger') as mock_logger:
            await system_commands.help_command(mock_update, mock_context)

            # Verify logging was called
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "Help command accessed" in log_message
            assert str(mock_update.effective_user.id) in log_message

    @pytest.mark.asyncio
    async def test_beta_command_logs_access(self, system_commands, mock_update, mock_context):
        """Test that beta command logs user access"""
        with patch('bot.commands.system_commands.logger') as mock_logger:
            await system_commands.beta_command(mock_update, mock_context)

            # Verify logging was called
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "Beta command accessed" in log_message
            assert str(mock_update.effective_user.id) in log_message

    @pytest.mark.asyncio
    async def test_about_command_logs_access(self, system_commands, mock_update, mock_context):
        """Test that about command logs user access"""
        with patch('bot.commands.system_commands.logger') as mock_logger:
            await system_commands.about_command(mock_update, mock_context)

            # Verify logging was called
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "About command accessed" in log_message
            assert str(mock_update.effective_user.id) in log_message


class TestSystemCommandsIntegration:
    """Integration tests for SystemCommands"""

    @pytest.mark.asyncio
    async def test_all_commands_use_html_parse_mode(self, system_commands, mock_update, mock_context):
        """Test that all commands use HTML parse mode for formatting"""
        commands = [
            system_commands.help_command,
            system_commands.beta_command,
            system_commands.about_command,
        ]

        for command in commands:
            mock_update.message.reply_text.reset_mock()
            await command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert "parse_mode" in call_args[1]
            assert call_args[1]["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_commands_handle_user_without_username(self, system_commands, mock_context):
        """Test that commands work even if user has no username"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 12345
        update.effective_user.username = None  # No username
        update.effective_user.first_name = "Test"
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()

        # All commands should work without errors
        await system_commands.help_command(update, mock_context)
        assert update.message.reply_text.called

        update.message.reply_text.reset_mock()
        await system_commands.beta_command(update, mock_context)
        assert update.message.reply_text.called

        update.message.reply_text.reset_mock()
        await system_commands.about_command(update, mock_context)
        assert update.message.reply_text.called

