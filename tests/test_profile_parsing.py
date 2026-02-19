#!/usr/bin/env python3
"""
Тест парсинга профиля GDcards
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.parsers.simple_parser import SimpleShmalalaParser

def test_profile_parsing():
    """Тестируем парсинг профиля GDcards"""
    print("[TEST] Тестирование парсинга профиля GDcards...")
    
    # Тестовое сообщение профиля
    test_message = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#731)
Орбы: 10 (#1306)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
    
    print(f"\n[INFO] Тестовое сообщение:")
    print(test_message)
    print("\n" + "="*50 + "\n")
    
    # Создаем парсер
    parser = SimpleShmalalaParser()
    
    # Парсим сообщение
    result = parser.parse_profile_message(test_message)
    
    if result:
        print(f"[SUCCESS] Профиль успешно распознан!")
        print(f"  - Игрок: {result.player_name}")
        print(f"  - Орбы: {result.orbs}")
        print(f"  - Очки: {result.points}")
        print(f"\n[INFO] Сырое сообщение (первые 200 символов):")
        print(f"  {result.raw_message}")
    else:
        print(f"[ERROR] Не удалось распознать профиль!")
        return False
    
    # Проверяем корректность данных
    assert result.player_name == "LucasTeam", f"Ожидалось 'LucasTeam', получено '{result.player_name}'"
    assert result.orbs == 10, f"Ожидалось 10 орбов, получено {result.orbs}"
    assert result.points == 364, f"Ожидалось 364 очка, получено {result.points}"
    
    print(f"\n[SUCCESS] Все проверки пройдены!")
    return True

if __name__ == "__main__":
    try:
        success = test_profile_parsing()
        if success:
            print("\n[RESULT] ✅ Тест успешно пройден!")
            sys.exit(0)
        else:
            print("\n[RESULT] ❌ Тест провален!")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Ошибка при выполнении теста: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
