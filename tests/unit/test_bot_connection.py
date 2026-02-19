#!/usr/bin/env python3
"""
Простой тест подключения к Telegram Bot API
MOVED from tests/ to tests/unit/ during Phase 4 refactoring
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram import Bot
from src.config import settings
import asyncio

async def test_connection():
    """Тестирование подключения к боту"""
    print(f"Тестирование токена: {settings.bot_token[:20]}...")
    
    try:
        bot = Bot(token=settings.bot_token)
        me = await bot.get_me()
        
        print("✅ Подключение успешно!")
        print(f"   Имя бота: {me.first_name}")
        print(f"   Username: @{me.username}")
        print(f"   ID: {me.id}")
        print(f"   Может присоединяться к группам: {me.can_join_groups}")
        print(f"   Может читать все сообщения: {me.can_read_all_group_messages}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
