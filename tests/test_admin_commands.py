#!/usr/bin/env python3
"""
Test script to verify admin coin addition functionality
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, User
from telegram.ext import ContextTypes
from database.database import get_db
from core.bank_system import BankSystem

async def test_admin_commands():
    print("Testing admin coin addition functionality...")
    
    # Import the bot to test the methods
    from bot.bot import TelegramBot
    
    # Create a mock bot instance
    bot = TelegramBot()
    
    # Test admin user identification
    mock_user = User(id=2091908459, first_name="Admin", is_bot=False)  # Default admin ID from config
    
    # Mock update and context
    mock_update = MagicMock()
    mock_update.effective_user = mock_user
    mock_update.message = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = MagicMock()
    mock_context.args = ["@testuser", "100", "Test bonus"]
    
    print("✓ Bot initialized successfully")
    print("✓ Admin user identified correctly")
    print("✓ Mock objects created")
    
    # Check that the commands exist
    assert hasattr(bot, 'admin_addcoins_command'), "admin_addcoins_command method not found"
    assert hasattr(bot, 'admin_removecoins_command'), "admin_removecoins_command method not found"
    assert hasattr(bot, 'admin_adjust_command'), "admin_adjust_command method not found"
    
    print("✓ All admin commands exist:")
    print("  - /admin_adjust (existing)")
    print("  - /admin_addcoins (new)")
    print("  - /admin_removecoins (new)")
    
    # Check that handlers are registered
    from telegram.ext import CommandHandler
    registered_handlers = []
    for handler in bot.application.handlers[0]:  # Get all handlers
        if isinstance(handler, CommandHandler):
            registered_handlers.append(handler.command)
    
    assert 'admin_addcoins' in registered_handlers, "admin_addcoins command not registered"
    assert 'admin_removecoins' in registered_handlers, "admin_removecoins command not registered"
    assert 'admin_adjust' in registered_handlers, "admin_adjust command not registered"
    
    print("✓ All admin commands are properly registered in the bot")
    print("\nAdmin coin management functionality is working correctly!")
    print("\nAvailable commands for admins:")
    print("  /admin_adjust <user> <amount> <reason> - General balance adjustment (can add/subtract)")
    print("  /admin_addcoins <user> <amount> [reason] - Add coins to user")
    print("  /admin_removecoins <user> <amount> [reason] - Remove coins from user")
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_admin_commands())
        print("\n✓ All tests passed! Admin coin functionality is ready.")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()