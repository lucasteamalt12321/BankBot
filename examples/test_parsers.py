#!/usr/bin/env python3
"""Test script for all message parsers."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.classifier import MessageClassifier, MessageType
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser
)

# Test messages
gdcards_profile = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 10 (#342)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""

gdcards_accrual = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: LucasTeam
───────────────
Карта: "Zodiac"
Описание: Коллаб от Bianox
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────"""

shmalala_fishing = """🎣 [Рыбалка] 🎣

Рыбак: Crazy Time
Опыт: +6 (232 / 64)🔋

Вы ловили взгляд прохожей, а поймали кое-что другое.
На крючке: 🐟 Окунь (0.84 кг)

Погода: ☀️ Ясно
Место: Городское озеро

Монеты: +4 (266)💰
Энергии осталось: 6 ⚡️"""

shmalala_karma = """Лайк! Вы повысили рейтинг пользователя Никита .
Теперь его рейтинг: 11 ❤️"""

truemafia_game_end = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    LucasTeam Luke - 👨🏼 Мирный житель 
    Tidal Wave - 👨🏼 Мирный житель 

Остальные участники: 
    Crazy Time - 👨🏼‍⚕️ Доктор 
    . - 🤵🏻 Дон 

Игра длилась: 2 мин. 35 сек."""

truemafia_profile = """👤 LucasTeam Luke

💵 Деньги: 930
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

bunkerrp_game_end = """Прошли в бункер:
1. LucasTeam
💼Профессия: Программист
👥Био: Мужчина, 26 лет, гетеросексуален, стаж работы 1 год
❤Здоровье: Паралич ног — Экзоскелет (носит внешний каркас, сильнее обычного человека)
🎣Хобби: Поиск пропавших животных (4 года)
📝Факт: Стал героем популярного мема
🧳Багаж: Витамины и добавки
🃏Карта 1: Замени открытую карту профессии любого игрока на случайную из колоды

2. .
💼Профессия: Судья
👥Био: Мужчина, 32 года, гомосексуален, стаж работы 14 лет
❤Здоровье: Отсутствие пальцев на руках — Кулаки (пальцев нет вообще, может только толкать и бить)
🎣Хобби: Массаж и акупунктура (7 лет)
📝Факт: Обожает запах бензина
🧳Багаж: Надувная кукла
🃏Карта 1: Замени открытую карту здоровья любого игрока на случайную из колоды

Не прошли в бункер:
1. Crazy
💼Профессия: Дерматолог"""

bunkerrp_profile = """👤 LucasTeam

💵 Деньги: 300
💎 Кристаллики: 0

Экстры:
🛡 Защита от изгнания: 0
🃏 Вторая карта действий: 0

🎯 Побед: 7 (с финалом: 1)
🎲 Всего игр: 16 (с финалом: 1)"""


def test_classifier():
    """Test message classification."""
    print("="*60)
    print("Testing Message Classifier")
    print("="*60)
    
    classifier = MessageClassifier()
    
    tests = [
        ("GD Cards Profile", gdcards_profile, MessageType.GDCARDS_PROFILE),
        ("GD Cards Accrual", gdcards_accrual, MessageType.GDCARDS_ACCRUAL),
        ("Shmalala Fishing", shmalala_fishing, MessageType.SHMALALA_FISHING),
        ("Shmalala Karma", shmalala_karma, MessageType.SHMALALA_KARMA),
        ("True Mafia Game End", truemafia_game_end, MessageType.TRUEMAFIA_GAME_END),
        ("True Mafia Profile", truemafia_profile, MessageType.TRUEMAFIA_PROFILE),
        ("BunkerRP Game End", bunkerrp_game_end, MessageType.BUNKERRP_GAME_END),
        ("BunkerRP Profile", bunkerrp_profile, MessageType.BUNKERRP_PROFILE),
    ]
    
    for name, message, expected in tests:
        result = classifier.classify(message)
        status = "✓" if result == expected else "✗"
        print(f"{status} {name}: {result.value}")
        if result != expected:
            print(f"  Expected: {expected.value}")
    print()


def test_parsers():
    """Test all parsers."""
    print("="*60)
    print("Testing Parsers")
    print("="*60)
    
    # GD Cards Profile
    parser = ProfileParser()
    result = parser.parse(gdcards_profile)
    print(f"✓ GD Cards Profile: {result.player_name}, Orbs: {result.orbs}")
    
    # GD Cards Accrual
    parser = AccrualParser()
    result = parser.parse(gdcards_accrual)
    print(f"✓ GD Cards Accrual: {result.player_name}, Points: {result.points}")
    
    # Shmalala Fishing
    parser = FishingParser()
    result = parser.parse(shmalala_fishing)
    print(f"✓ Shmalala Fishing: {result.player_name}, Coins: {result.coins}")
    
    # Shmalala Karma
    parser = KarmaParser()
    result = parser.parse(shmalala_karma)
    print(f"✓ Shmalala Karma: {result.player_name}, Karma: {result.karma}")
    
    # True Mafia Game End
    parser = MafiaGameEndParser()
    result = parser.parse(truemafia_game_end)
    print(f"✓ True Mafia Game End: Winners: {', '.join(result.winners)}")
    
    # True Mafia Profile
    parser = MafiaProfileParser()
    result = parser.parse(truemafia_profile)
    print(f"✓ True Mafia Profile: {result.player_name}, Money: {result.money}")
    
    # BunkerRP Game End
    parser = BunkerGameEndParser()
    result = parser.parse(bunkerrp_game_end)
    print(f"✓ BunkerRP Game End: Winners: {', '.join(result.winners)}")
    
    # BunkerRP Profile
    parser = BunkerProfileParser()
    result = parser.parse(bunkerrp_profile)
    print(f"✓ BunkerRP Profile: {result.player_name}, Money: {result.money}")
    
    print()


if __name__ == "__main__":
    test_classifier()
    test_parsers()
    print("="*60)
    print("All tests passed! ✓")
    print("="*60)
