# config.py
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN", "")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///bot.db")
        admin_ids_str = os.getenv("ADMIN_USER_IDS", "2091908459")
        self.admin_user_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
        self.debug = os.getenv("DEBUG", "False").lower() == "true"

# Конфигурация валют (теперь с возможностью динамического изменения)
ADVANCED_CURRENCY_CONFIG = {
    'shmalala': {
        'base_rate': 1.0,
        'currency_name': 'coins',
        'admin_editable': True,
        'event_multipliers': {
            'battle_win': 1.0,
            'crocodile_win': 1.2,
            'crocodile_correct_guess': 1.1,
            'crocodile_participate': 1.0,
            'fishing': 1.0,
            'trap': 1.0
        }
    },
    'gdcards': {
        'base_rate': 2.0,
        'currency_name': 'points',
        'admin_editable': True,
        'rarity_multipliers': {
            'card_common': 1.0,
            'card_rare': 1.5,
            'card_epic': 2.0,
            'card_legendary': 3.0
        }
    },
    'true_mafia': {
        'base_rate': 15.0,
        'currency_name': 'wins',
        'admin_editable': True,
        'event_multipliers': {
            'game_win': 1.0,
            'game_participation': 0.3
        }
    },
    'bunkerrp': {
        'base_rate': 20.0,
        'currency_name': 'survivals',
        'admin_editable': True,
        'event_multipliers': {
            'bunker_survival': 1.0,
            'game_participation': 0.5
        }
    }
}

# Безопасность транзакций
TRANSACTION_SECURITY = {
    'max_single_amount': 1000,
    'max_hourly_transactions': 50,
    'duplicate_window_hours': 1,    # Оставляем 1 час для более гибкой системы
    'suspicious_pattern_detection': True,
    'auto_hold_large_transactions': False
}

# Конфигурация мини-игр
GAMES_CONFIG = {
    'cities': {
        'reward_per_turn': 5,
        'penalty_invalid_city': -2,
        'bonus_chain_5': 25,
        'max_response_time': 30
    },
    'killer_words': {
        'reward_killer_word': 15,
        'penalty_weak_word': -3,
        'bonus_category_completion': 50
    },
    'gd_levels': {
        'reward_per_turn': 5,
        'bonus_completion': 30
    }
}

# Конфигурация D&D
DND_CONFIG = {
    'max_players_per_session': 6,
    'master_reward_per_hour': 100,
    'player_attendance_bonus': 20,
    'max_session_duration': 1000
}

settings = Settings()

def update_currency_rate(game: str, new_rate: float) -> bool:
    """Обновление коэффициента валюты (в памяти)"""
    if game in ADVANCED_CURRENCY_CONFIG:
        ADVANCED_CURRENCY_CONFIG[game]['base_rate'] = new_rate
        return True
    return False

def get_currency_config() -> dict:
    """Получение текущей конфигурации валют"""
    return ADVANCED_CURRENCY_CONFIG.copy()