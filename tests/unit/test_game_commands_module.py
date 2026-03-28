"""
Unit tests for game commands module.

Tests the GameCommands class to ensure game-related commands are properly
moved from bot.py to the dedicated module.

Task 10.2.4: Переместить game команды
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, User, Message
from telegram.ext import ContextTypes

from bot.commands.game_commands import GameCommands


@pytest.fixture
def game_commands():
    """Create GameCommands instance for testing."""
    return GameCommands()


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 12345
    update.effective_user.first_name = "TestUser"
    update.effective_user.username = "testuser"
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context


@pytest.mark.asyncio
async def test_games_command_displays_info(game_commands, mock_update, mock_context):
    """Test that /games command displays game information."""
    await game_commands.games_command(mock_update, mock_context)
    
    # Verify reply_text was called
    mock_update.message.reply_text.assert_called_once()
    
    # Verify the message contains game information
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "[GAME]" in message_text
    assert "Мини-игры" in message_text
    assert "Города" in message_text
    assert "/play" in message_text


@pytest.mark.asyncio
async def test_dnd_command_displays_info(game_commands, mock_update, mock_context):
    """Test that /dnd command displays D&D information."""
    await game_commands.dnd_command(mock_update, mock_context)
    
    # Verify reply_text was called
    mock_update.message.reply_text.assert_called_once()
    
    # Verify the message contains D&D information
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "[DICE]" in message_text
    assert "D&D Мастерская" in message_text
    assert "/dnd_create" in message_text
    assert "/dnd_roll" in message_text


@pytest.mark.asyncio
async def test_play_command_requires_game_type(game_commands, mock_update, mock_context):
    """Test that /play command requires a game type argument."""
    # No arguments provided
    mock_context.args = []
    
    await game_commands.play_command(mock_update, mock_context)
    
    # Verify error message was sent
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "Ukazhite tip igry" in message_text or "tip igry" in message_text


@pytest.mark.asyncio
async def test_play_command_validates_game_type(game_commands, mock_update, mock_context):
    """Test that /play command validates game type."""
    # Invalid game type
    mock_context.args = ["invalid_game"]
    
    await game_commands.play_command(mock_update, mock_context)
    
    # Verify error message was sent
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "Neizvestnyy tip igry" in message_text or "tip igry" in message_text


@pytest.mark.asyncio
async def test_join_command_requires_session_id(game_commands, mock_update, mock_context):
    """Test that /join command requires a session ID."""
    # No arguments provided
    mock_context.args = []
    
    await game_commands.join_command(mock_update, mock_context)
    
    # Verify error message was sent
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "Ispolzuyte" in message_text or "join" in message_text


@pytest.mark.asyncio
async def test_dnd_create_command_requires_name(game_commands, mock_update, mock_context):
    """Test that /dnd_create command requires a session name."""
    # No arguments provided
    mock_context.args = []
    
    await game_commands.dnd_create_command(mock_update, mock_context)
    
    # Verify error message was sent
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "Используйте" in message_text or "dnd_create" in message_text


@pytest.mark.asyncio
async def test_dnd_roll_command_requires_dice_input(game_commands, mock_update, mock_context):
    """Test that /dnd_roll command requires dice input."""
    # No arguments provided
    mock_context.args = []
    
    await game_commands.dnd_roll_command(mock_update, mock_context)
    
    # Verify error message was sent
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args
    message_text = call_args[0][0]
    
    assert "Используйте" in message_text or "dnd_roll" in message_text


def test_game_commands_initialization():
    """Test that GameCommands can be initialized."""
    game_commands = GameCommands()
    assert game_commands is not None
    assert hasattr(game_commands, 'games_command')
    assert hasattr(game_commands, 'play_command')
    assert hasattr(game_commands, 'dnd_command')
    assert hasattr(game_commands, 'dnd_create_command')
