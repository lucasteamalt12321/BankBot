#!/usr/bin/env python3
"""
Quick test of the parser with user's message
"""

import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parsers.simple_parser import parse_shmalala_message

# User's exact message
test_message = """🎣 [Рыбалка] 🎣
Рыбак: LucasTeam Luke
Опыт: +1 (380 / 782)🔋
Вы хрустнули чипсами, и от этого звука проснулась вся рыба в округе.
На крючке: 👢 Одинокий сапог Капитана Очевидности (0.24 кг)
Погода: 🌨 Снежная буря
Место: Городское озеро
Монеты: +5 (3680)💰
Энергии осталось: 2 ⚡️"""

print("Testing parser with user's message...")
result = parse_shmalala_message(test_message)

if result:
    print("✅ SUCCESS!")
    print(f"Fisher: '{result.fisher_name}'")
    print(f"Coins: {result.coins}")
else:
    print("❌ FAILED!")
    print("Message not recognized")

print("\nDone!")