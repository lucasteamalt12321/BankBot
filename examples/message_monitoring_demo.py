#!/usr/bin/env python3
"""
Demonstration of Message Monitoring Middleware
Shows how the middleware intercepts and processes external bot messages
"""

import sys
import os
import asyncio
from unittest.mock import Mock
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.message_monitoring_middleware import MessageMonitoringMiddleware


def create_mock_update(message_text: str, bot_username: str = "shmalala_bot", 
                      chat_type: str = "supergroup") -> Update:
    """Create a mock Telegram update for testing"""
    update = Mock(spec=Update)
    
    # Mock message
    message = Mock(spec=Message)
    message.text = message_text
    message.message_id = 123
    message.reply_text = Mock()
    
    # Mock user (external bot)
    user = Mock(spec=User)
    user.id = 98765
    user.is_bot = True
    user.username = bot_username
    
    # Mock chat
    chat = Mock(spec=Chat)
    chat.id = -67890
    chat.type = chat_type
    
    # Wire up the mocks
    update.message = message
    update.effective_user = user
    update.effective_chat = chat
    message.from_user = user
    message.chat = chat
    
    return update


async def demo_shmalala_fishing():
    """Demonstrate processing a Shmalala fishing message"""
    print("🎣 Demo: Shmalala Fishing Message Processing")
    print("=" * 50)
    
    middleware = MessageMonitoringMiddleware()
    
    # Sample Shmalala fishing message
    fishing_message = """🎣 [Рыбалка] 🎣

Рыбак: TestUser
На крючке: Карп (2.5 кг)
Погода: Солнечно
Место: Озеро
Энергии осталось: 85 ⚡️
Удочка: Золотая (ещё 45 мин.)

Монеты: +150 (1500)💰
Опыт: +25 (250 / 500)🔋"""
    
    update = create_mock_update(fishing_message, "shmalala_bot")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    print(f"📨 Processing message from {update.effective_user.username}:")
    print(f"   Message preview: {fishing_message[:100]}...")
    print()
    
    # Check bot identification
    is_game_bot = middleware._is_external_game_bot(update.message)
    print(f"🤖 Is external game bot: {is_game_bot}")
    
    # Check processing criteria
    should_process = middleware._should_process_message(update.message)
    print(f"✅ Should process message: {should_process}")
    
    print()
    print("Note: Full processing requires database connection.")
    print("In real usage, this would:")
    print("  1. Parse the message with MessageParser")
    print("  2. Extract currency amount (150 coins)")
    print("  3. Apply conversion rules")
    print("  4. Update user balance")
    print("  5. Log transaction to database")
    print("  6. Send notification to chat")


async def demo_gdcards_message():
    """Demonstrate processing a GDcards message"""
    print("\n🃏 Demo: GDcards Message Processing")
    print("=" * 50)
    
    middleware = MessageMonitoringMiddleware()
    
    # Sample GDcards message
    gdcards_message = """🃏 НОВАЯ КАРТА 🃏

Игрок: TestUser
─────────────────
Карта: "Огненный дракон"
─────────────────
Редкость: Эпическая (🟣 3.2%)
Коллекция: 45/100 карт
Лимит карт сегодня: 3 из 5

Очки: +75"""
    
    update = create_mock_update(gdcards_message, "gdcards_bot")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    print(f"📨 Processing message from {update.effective_user.username}:")
    print(f"   Message preview: {gdcards_message[:100]}...")
    print()
    
    # Check bot identification
    is_game_bot = middleware._is_external_game_bot(update.message)
    print(f"🤖 Is external game bot: {is_game_bot}")
    
    # Check processing criteria
    should_process = middleware._should_process_message(update.message)
    print(f"✅ Should process message: {should_process}")
    
    print()
    print("Note: Full processing requires database connection.")
    print("In real usage, this would:")
    print("  1. Parse the message with MessageParser")
    print("  2. Extract currency amount (75 points)")
    print("  3. Apply conversion rules")
    print("  4. Update user balance")
    print("  5. Log transaction to database")
    print("  6. Send notification to chat")


async def demo_non_game_message():
    """Demonstrate handling of non-game messages"""
    print("\n💬 Demo: Non-Game Message Handling")
    print("=" * 50)
    
    middleware = MessageMonitoringMiddleware()
    
    # Regular chat message
    regular_message = "Hello everyone! How are you doing today?"
    
    update = create_mock_update(regular_message, "regular_user", "supergroup")
    update.effective_user.is_bot = False  # Regular user, not a bot
    
    print(f"📨 Processing message from regular user:")
    print(f"   Message: {regular_message}")
    print()
    
    # Check bot identification
    is_game_bot = middleware._is_external_game_bot(update.message)
    print(f"🤖 Is external game bot: {is_game_bot}")
    
    # Check processing criteria
    should_process = middleware._should_process_message(update.message)
    print(f"✅ Should process message: {should_process}")
    
    print()
    print("✅ Result: Message correctly ignored (no game content)")


async def demo_middleware_features():
    """Demonstrate middleware features"""
    print("\n⚙️ Demo: Middleware Features")
    print("=" * 50)
    
    middleware = MessageMonitoringMiddleware()
    
    # Show initial stats
    stats = middleware.get_stats()
    print(f"📊 Initial stats: {stats}")
    
    # Test enable/disable
    print(f"🔧 Middleware enabled: {middleware.is_enabled()}")
    
    middleware.disable()
    print(f"🔧 After disable: {middleware.is_enabled()}")
    
    middleware.enable()
    print(f"🔧 After enable: {middleware.is_enabled()}")
    
    # Test cache management
    print(f"💾 Processed messages cache: {len(middleware.processed_messages)}")
    
    # Add some test messages to cache
    for i in range(5):
        middleware.processed_messages.add(f"test_message_{i}")
    
    print(f"💾 After adding test messages: {len(middleware.processed_messages)}")
    
    # Clear cache
    middleware.clear_processed_messages()
    print(f"💾 After clearing cache: {len(middleware.processed_messages)}")


async def main():
    """Run all demonstrations"""
    print("🚀 Message Monitoring Middleware Demonstration")
    print("=" * 60)
    print()
    
    await demo_shmalala_fishing()
    await demo_gdcards_message()
    await demo_non_game_message()
    await demo_middleware_features()
    
    print("\n" + "=" * 60)
    print("✅ Demonstration completed!")
    print()
    print("Integration Points:")
    print("  • Middleware integrates with existing bot.py message handler")
    print("  • Uses MessageParser for actual parsing and database operations")
    print("  • Supports Shmalala, GDcards, and other external game bots")
    print("  • Provides duplicate message detection and error handling")
    print("  • Sends notifications to chat when transactions are processed")


if __name__ == "__main__":
    asyncio.run(main())