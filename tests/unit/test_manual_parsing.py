#!/usr/bin/env python3
"""
Тесты для функции ручного парсинга сообщений
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.parsers.simple_parser import parse_game_message

class TestManualParsing:
    """Тесты для ручного парсинга игровых сообщений"""
    
    def test_fishing_message_parsing(self):
        """Тест парсинга сообщения о рыбалке"""
        message = """
🎣 [Рыбалка] 🎣

Рыбак: TestUser
Монеты: +75 (225)💰
        """
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'fishing'
        assert result['user'] == 'TestUser'
        assert result['amount'] == 75
    
    def test_card_message_parsing(self):
        """Тест парсинга сообщения о новой карте"""
        message = """
🃏 НОВАЯ КАРТА 🃏

Игрок: TestPlayer
Очки: +150
        """
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'card'
        assert result['user'] == 'TestPlayer'
        assert result['amount'] == 150
    
    def test_invalid_message(self):
        """Тест парсинга невалидного сообщения"""
        message = "Просто обычное сообщение без игровой информации"
        
        result = parse_game_message(message)
        
        assert result is None
    
    def test_fishing_with_username(self):
        """Тест парсинга рыбалки с @username"""
        message = """
🎣 [Рыбалка] 🎣

Рыбак: @username123
Монеты: +50 (150)💰
        """
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'fishing'
        assert 'username123' in result['user']
        assert result['amount'] == 50
    
    def test_card_with_large_points(self):
        """Тест парсинга карты с большим количеством очков"""
        message = """
🃏 НОВАЯ КАРТА 🃏

Игрок: ProPlayer
Очки: +999
        """
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'card'
        assert result['user'] == 'ProPlayer'
        assert result['amount'] == 999
    
    def test_empty_message(self):
        """Тест парсинга пустого сообщения"""
        message = ""
        
        result = parse_game_message(message)
        
        assert result is None
    
    def test_partial_fishing_message(self):
        """Тест парсинга неполного сообщения о рыбалке"""
        message = """
🎣 [Рыбалка] 🎣

Рыбак: TestUser
        """
        
        result = parse_game_message(message)
        
        # Должно вернуть None, так как нет информации о монетах
        assert result is None
    
    def test_partial_card_message(self):
        """Тест парсинга неполного сообщения о карте"""
        message = """
🃏 НОВАЯ КАРТА 🃏

Игрок: TestPlayer
        """
        
        result = parse_game_message(message)
        
        # Должно вернуть None, так как нет информации об очках
        assert result is None


def run_manual_tests():
    """Запуск тестов вручную без pytest"""
    print("=== Тесты ручного парсинга ===\n")
    
    test = TestManualParsing()
    tests = [
        ("Парсинг рыбалки", test.test_fishing_message_parsing),
        ("Парсинг карты", test.test_card_message_parsing),
        ("Невалидное сообщение", test.test_invalid_message),
        ("Рыбалка с @username", test.test_fishing_with_username),
        ("Карта с большими очками", test.test_card_with_large_points),
        ("Пустое сообщение", test.test_empty_message),
        ("Неполное сообщение рыбалки", test.test_partial_fishing_message),
        ("Неполное сообщение карты", test.test_partial_card_message),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {name}: Ошибка - {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Всего тестов: {passed + failed}")
    print(f"Успешно: {passed}")
    print(f"Провалено: {failed}")
    print(f"{'='*50}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_manual_tests()
    sys.exit(0 if success else 1)
