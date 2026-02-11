"""
Пример использования интегрированной системы парсинга
Демонстрирует работу с парсером игровых сообщений
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parsers.simple_parser import (
    parse_card_message,
    parse_fishing_message,
    parse_game_message
)


def example_card_parsing():
    """Пример парсинга сообщения о новой карте"""
    message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @username
Карта: Легендарная
Очки: +150
Редкость: Epic"""
    
    result = parse_card_message(message)
    if result:
        print(f"✅ Карта распознана!")
        print(f"   Игрок: {result.player_name}")
        print(f"   Очки: {result.points}")
    else:
        print("❌ Не удалось распознать сообщение о карте")


def example_fishing_parsing():
    """Пример парсинга сообщения о рыбалке"""
    message = """🎣 [Рыбалка] 🎣
Рыбак: @fisher_user
Улов: Золотая рыбка
Монеты: +250 (1500)💰
Опыт: +10"""
    
    result = parse_fishing_message(message)
    if result:
        print(f"✅ Рыбалка распознана!")
        print(f"   Рыбак: {result.fisher_name}")
        print(f"   Монеты: {result.coins}")
    else:
        print("❌ Не удалось распознать сообщение о рыбалке")


def example_universal_parsing():
    """Пример универсального парсинга"""
    messages = [
        """🃏 НОВАЯ КАРТА 🃏
Игрок: @player1
Очки: +100""",
        
        """🎣 [Рыбалка] 🎣
Рыбак: @fisher1
Монеты: +50 (500)💰"""
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\n--- Сообщение {i} ---")
        result = parse_game_message(message)
        if result:
            print(f"✅ Тип: {result['type']}")
            print(f"   Пользователь: {result['user']}")
            print(f"   Количество: {result['amount']}")
        else:
            print("❌ Не удалось распознать сообщение")


def example_bot_integration():
    """Пример интеграции с ботом"""
    from core.database.shop_database import ShopDatabaseManager
    
    db = ShopDatabaseManager()
    
    # Симуляция получения сообщения
    message = """🎣 [Рыбалка] 🎣
Рыбак: @test_user
Монеты: +100 (1000)💰"""
    
    result = parse_game_message(message)
    if result and result['type'] == 'fishing':
        username = result['user'].replace('@', '')
        coins = result['amount']
        
        print(f"\n💰 Начисление монет пользователю {username}: {coins}")
        
        # Здесь можно добавить логику начисления монет в базу данных
        # db.add_user_coins(username, coins)


if __name__ == "__main__":
    print("=" * 50)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ПАРСЕРА")
    print("=" * 50)
    
    print("\n1. Парсинг карт:")
    example_card_parsing()
    
    print("\n2. Парсинг рыбалки:")
    example_fishing_parsing()
    
    print("\n3. Универсальный парсинг:")
    example_universal_parsing()
    
    print("\n4. Интеграция с ботом:")
    example_bot_integration()
    
    print("\n" + "=" * 50)
