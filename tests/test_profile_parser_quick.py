"""Быстрый тест парсера профилей"""
import sys
sys.path.insert(0, '.')

from core.parsers.simple_parser import SimpleShmalalaParser

# Ваше сообщение профиля
profile_text = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#731)
Орбы: 10 (#1309)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""

print("Тестирование парсера профилей...")
print("=" * 50)

parser = SimpleShmalalaParser()
result = parser.parse_profile_message(profile_text)

if result:
    print("✅ Профиль успешно распознан!")
    print(f"Игрок: {result.player_name}")
    print(f"Орбы: {result.orbs}")
    print(f"Очки: {result.points}")
    print("\n✅ ТЕСТ ПРОЙДЕН")
else:
    print("❌ Профиль не распознан")
    print("\nДебаг информация:")
    print(f"Текст содержит 'ПРОФИЛЬ': {'ПРОФИЛЬ' in profile_text}")
    
    # Проверяем построчно
    lines = profile_text.splitlines()
    for i, line in enumerate(lines):
        print(f"Строка {i}: '{line}'")
        if "ПРОФИЛЬ" in line:
            print(f"  -> Найдена строка с ПРОФИЛЬ")
            parts = line.split("ПРОФИЛЬ")
            print(f"  -> После split: {parts}")
        if "Ник:" in line:
            print(f"  -> Найдена строка с Ник")
        if "Орбы:" in line:
            print(f"  -> Найдена строка с орбами")
        if "Очки:" in line:
            print(f"  -> Найдена строка с очками")
    
    print("\n❌ ТЕСТ НЕ ПРОЙДЕН")
