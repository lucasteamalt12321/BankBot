#!/usr/bin/env python3
"""
Quick test to verify the parsing functionality
"""

import sys
import os
import re

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_patterns():
    """Test individual patterns manually"""
    
    # Sample message without emojis to avoid encoding issues
    sample_message = '''NOVAYA KARTA
-----------------
Igrok: TidalWaveT
-----------------
Karta: "Void Wave"
Opisanie: Luchshiy proekt
Kategoriya: Demony
-----------------
Redkost: Epicheskaya (1/55) (17.0%)
Ochki: +3
Kollekciya: 2/213 kart
-----------------
Eta karta yest u: 994 igrokov
Limit kart segodnya: 1 iz 8'''
    
    print("Testing individual patterns...")
    print("=" * 50)
    
    # Patterns from EnhancedGDCardsParser adapted for transliterated text
    patterns = {
        'player': r'Igrok: ([^\n─]+?)(?:\n|─)',
        'card_name': r'Karta: "([^"]+)"',
        'points': r'Ochki: \+(\d+)',
        'rarity': r'Redkost: (Obichnaya|Rezkaya|Epicheskaya|Legendarnaya)',
        'collection': r'Kollekciya: (\d+)/(\d+) kart',
        'card_limit': r'Limit kart segodnya: (\d+) iz (\d+)',
        'description': r'Opisanie: ([^\n]+)',
        'category': r'Kategoriya: ([^\n]+)',
        'card_owners': r'Eta karta yest u: (\d+) igrokov'
    }
    
    for name, pattern in patterns.items():
        match = re.search(pattern, sample_message)
        if match:
            print(f"Pattern '{name}': MATCH - {match.groups() if match.groups() else match.group()}")
        else:
            print(f"Pattern '{name}': NO MATCH")
    
    # Now test with actual Russian patterns on original text
    original_sample = '''🖼 🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TidalWaveT
───────────────
Карта: "Void Wave"
Описание: Один из лучших проектов Cherry Team. Мегаколлаб, выполненный в глоу-стиле длиной в 4 минуты. Верифицирован Dorami.
Категория: Демоны
───────────────
Редкость: Эпическая (1/55) (17.0%) 🟣
Очки: +3
Коллекция: 2/213 карт
───────────────
Эта карта есть у: 994 игроков
Лимит карт сегодня: 1 из 8'''

    print("\nTesting with original Russian patterns...")
    print("=" * 50)
    
    original_patterns = {
        'player': r'Игрок: ([^\n─]+?)(?:\n|─)',
        'card_name': r'Карта: "([^"]+)"',
        'points': r'Очки: \+(\d+)',
        'rarity': r'Редкость: (Обычная|Редкая|Эпическая|Легендарная)',
        'collection': r'Коллекция: (\d+)/(\d+) карт',
        'card_limit': r'Лимит карт сегодня: (\d+) из (\d+)',
        'description': r'Описание: ([^\n]+)',
        'category': r'Категория: ([^\n]+)',
        'card_owners': r'Эта карта есть у: (\d+) игроков'
    }
    
    for name, pattern in original_patterns.items():
        match = re.search(pattern, original_sample)
        if match:
            print(f"Original Pattern '{name}': MATCH")
        else:
            print(f"Original Pattern '{name}': NO MATCH")
    
    # Check for keywords that trigger the parser
    keywords = [
        'НОВАЯ КАРТА', 'Очки:', 'GDcards', 'Карта:', 'новая карта', 'карта:',
        'GD Cards', 'gd cards', 'gdcards', 'Card', 'card', 'Карта', 'Редкость:'
    ]
    
    print("\nChecking keyword triggers:")
    for keyword in keywords:
        found = keyword in original_sample
        print(f"Keyword '{keyword}': {'FOUND' if found else 'NOT FOUND'}")


def test_parsing_directly():
    """Test the actual parser classes"""
    
    from bot.parsers import EnhancedGDCardsParser, GDCardsParser
    
    original_sample = '''🖼 🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TidalWaveT
───────────────
Карта: "Void Wave"
Описание: Один из лучших проектов Cherry Team. Мегаколлаб, выполненный в глоу-стиле длиной в 4 минуты. Верифицирован Dorami.
Категория: Демоны
───────────────
Редкость: Эпическая (1/55) (17.0%) 🟣
Очки: +3
Коллекция: 2/213 карт
───────────────
Эта карта есть у: 994 игроков
Лимит карт сегодня: 1 из 8'''

    print("\nTesting actual parser classes...")
    print("=" * 50)
    
    # Try EnhancedGDCardsParser
    enhanced_parser = EnhancedGDCardsParser()
    try:
        enhanced_activities = enhanced_parser.parse_message(original_sample)
        print(f"EnhancedGDCardsParser found {len(enhanced_activities)} activities")
        for i, activity in enumerate(enhanced_activities):
            print(f"  Activity {i+1}: {activity.activity_type} for {activity.user_identifier} - {activity.points} points")
    except Exception as e:
        print(f"EnhancedGDCardsParser error: {e}")
    
    # Try GDCardsParser
    basic_parser = GDCardsParser()
    try:
        basic_activities = basic_parser.parse_message(original_sample)
        print(f"GDCardsParser found {len(basic_activities)} activities")
        for i, activity in enumerate(basic_activities):
            print(f"  Activity {i+1}: {activity.activity_type} for {activity.user_identifier} - {activity.points} points")
    except Exception as e:
        print(f"GDCardsParser error: {e}")

if __name__ == "__main__":
    print("Quick GDcards Parser Test")
    print("=" * 50)
    
    test_patterns()
    test_parsing_directly()
    
    print("Quick test completed!")