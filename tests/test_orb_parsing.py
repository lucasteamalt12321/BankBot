"""
Test script for orb parsing functionality
Tests both card orbs and chest orb drops
"""

from core.parsers.simple_parser import SimpleShmalalaParser, parse_game_message

# Test 1: Card with orbs
card_message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: LucasTeam
───────────────
Карта: "Zafsa"
Описание: Мобильный игрок с диким чистым скиллом
Категория: Мобильные слееры
───────────────
Редкость: Редкая (5/64) (30.0%) 🔵
Очки: +2
Орбы за дроп: +3
Коллекция: 13/213 карт
───────────────
Эта карта есть у: 1549 игроков
Лимит карт сегодня: 1 из 8"""

# Test 2: Chest orb drop
chest_message = """LucasTeam открыл сундук и получил 70 орб"""

# Test 3: Alternative orb drop format
alt_orb_message = """Nikiktosik получил 50 орбов за достижение"""

print("=" * 60)
print("TEST 1: Card with orbs")
print("=" * 60)
parser = SimpleShmalalaParser()
card_result = parser.parse_card_message(card_message)
if card_result:
    print(f"✅ Card parsed successfully!")
    print(f"   Player: {card_result.player_name}")
    print(f"   Points: {card_result.points}")
    print(f"   Orbs: {card_result.orbs}")
else:
    print("❌ Failed to parse card message")

print("\n" + "=" * 60)
print("TEST 2: Chest orb drop")
print("=" * 60)
orb_drop_result = parser.parse_orb_drop_message(chest_message)
if orb_drop_result:
    print(f"✅ Orb drop parsed successfully!")
    print(f"   Player: {orb_drop_result.player_name}")
    print(f"   Orbs: {orb_drop_result.orbs}")
else:
    print("❌ Failed to parse orb drop message")

print("\n" + "=" * 60)
print("TEST 3: Alternative orb drop format")
print("=" * 60)
alt_orb_result = parser.parse_orb_drop_message(alt_orb_message)
if alt_orb_result:
    print(f"✅ Alternative orb drop parsed successfully!")
    print(f"   Player: {alt_orb_result.player_name}")
    print(f"   Orbs: {alt_orb_result.orbs}")
else:
    print("❌ Failed to parse alternative orb drop message")

print("\n" + "=" * 60)
print("TEST 4: Universal parse_game_message function")
print("=" * 60)

# Test card through universal function
print("\n--- Card message ---")
card_parsed = parse_game_message(card_message)
if card_parsed:
    print(f"✅ Type: {card_parsed['type']}")
    print(f"   User: {card_parsed['user']}")
    print(f"   Amount: {card_parsed['amount']}")
    print(f"   Orbs: {card_parsed['orbs']}")
else:
    print("❌ Failed")

# Test chest through universal function
print("\n--- Chest message ---")
chest_parsed = parse_game_message(chest_message)
if chest_parsed:
    print(f"✅ Type: {chest_parsed['type']}")
    print(f"   User: {chest_parsed['user']}")
    print(f"   Amount: {chest_parsed['amount']}")
    print(f"   Orbs: {chest_parsed['orbs']}")
else:
    print("❌ Failed")

print("\n" + "=" * 60)
print("TEST 5: Coefficient application simulation")
print("=" * 60)

from src.coefficient_provider import CoefficientProvider

coef_provider = CoefficientProvider.from_config('config/coefficients.json')
gd_cards_coef = coef_provider.get_coefficient('GD Cards')

print(f"GD Cards coefficient: {gd_cards_coef}:1")

if card_parsed:
    orbs = card_parsed['orbs']
    bank_change = int(orbs * gd_cards_coef)
    print(f"\nCard with {orbs} orbs:")
    print(f"  → Bank change: +{bank_change} coins")

if chest_parsed:
    orbs = chest_parsed['orbs']
    bank_change = int(orbs * gd_cards_coef)
    print(f"\nChest with {orbs} orbs:")
    print(f"  → Bank change: +{bank_change} coins")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
