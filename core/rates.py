"""
Канонические курсы конвертации игровых валют (единственный источник правды).

Оба стека парсинга читают курсы отсюда:
- api/index.py (Vercel webhook) — словарь как fallback к таблице `conversion_rates`
- bank_bot/services/parsing_service.py (PTB bot) — fallback вместо 1.0
- bot/handlers/parsing_handler.py (legacy-фолбэк) — конвертация по канону

Значения = «задуманные» курсы из api-словаря (gdcards 2.5 и т.д.).

Ключи совпадают с `conversion_rates.bot_name` из миграции 005
(gusya_cards/gdcards/shmalala) + дополнительные боты.
"""

from __future__ import annotations

# Единственный источник правды курсов. Ключи = bot_name в conversion_rates.
BOT_CONVERSION_RATES: dict[str, float] = {
    "gdcards": 2.5,
    "gusya_cards": 5.0,
    "shmalala": 2.5,
    "shmalala_karma": 0.5,
    "bunkerrp": 50.0,
    "chaometer": 1.0,
}

DEFAULT_CONVERSION_RATE = 1.0

# Маппинг resource_type для ботов, читаемых банк_бот-стеком
# (parsing_service читает курсы по паре (bot_name, resource_type)).
PARSING_RESOURCE_TYPES: dict[str, str] = {
    "gusya_cards": "coins",
    "gdcards": "orbs",
    "shmalala": "money",
    "shmalala_karma": "karma",
}


def get_conversion_rate(bot_name: str) -> float:
    """Канонический курс для бота (фолбэк DEFAULT_CONVERSION_RATE)."""
    return BOT_CONVERSION_RATES.get(bot_name, DEFAULT_CONVERSION_RATE)