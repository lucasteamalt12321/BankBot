# parser_config.py
"""
Конфигурация парсеров для различных игр
"""

SHMALALA_CONFIG = {
    'patterns': {
        'battle_win': [
            r'Победил\(а\) (.+?) и забрал\(а\) (\d+) 💰 монетки',
            r'(.+?) победил\(а\) в дуэли и получил\(а\) (\d+) монет',
            r'(.+?) выиграл\(а\) битву и заработал\(а\) (\d+) 💰'
        ],
        'battle_participate': [
            r'Участвовал\(а\) (.+?) и получил\(а\) (\d+) 💰 монетки',
            r'(.+?) участвовал\(а\) в битве и получил\(а\) (\d+) монет'
        ],
        'crocodile_win': [
            r'💵 Приз за победу \+(\d+) монета 💵',
            r'Победа в крокодиле! Награда: (\d+) монет'
        ],
        'crocodile_word': [
            r'^(.+?):\s*\n(.+)$',
            r'(.+?) загадал\(а\) слово: (.+)'
        ],
        'fishing': [
            r'Рыбак: (.+?)\n.*?Монеты: \+(\d+) \(\d+\)💰',
            r'(.+?) поймал\(а\) рыбу на (\d+) монет'
        ],
        'trap': [
            r'🦞 \[Ловушка\].*?Монеты: \+(\d+) \(\d+\)💰',
            r'Ловушка сработала! (.+?) получает (\d+) монет'
        ],
        'daily_bonus': [
            r'Ежедневный бонус: \+(\d+) монет',
            r'Бонус за вход: (\d+) 💰'
        ],
        'level_up': [
            r'(.+?) достиг\(ла\) уровня (\d+)! Награда: (\d+) монет',
            r'Поздравляем! (.+?) получил\(а\) (\d+) монет за уровень'
        ]
    },
    'multipliers': {
        'battle_win': 1.0,
        'battle_participate': 0.5,
        'crocodile_win': 1.2,
        'crocodile_participate': 0.3,
        'fishing': 0.8,
        'trap': 0.7,
        'daily_bonus': 1.0,
        'level_up': 1.5
    }
}

GD_CARDS_CONFIG = {
    'patterns': {
        'new_card': [
            r'Игрок: (.+?)\n.*?Очки: \+(\d+)',
            r'НОВАЯ КАРТА!\nИгрок: (.+?)\n.*?Очки: \+(\d+)',
            r'(.+?) получил\(а\) новую карту! Очки: \+(\d+)'
        ],
        'card_upgrade': [
            r'(.+?) улучшил\(а\) карту! Очки: \+(\d+)',
            r'Улучшение карты: (.+?) получает \+(\d+) очков'
        ],
        'collection_bonus': [
            r'(.+?) собрал\(а\) коллекцию! Бонус: (\d+) очков',
            r'Коллекция завершена! (.+?) награжден\(а\) (\d+) очками'
        ]
    },
    'rarity_multipliers': {
        'common': 1.0,
        'rare': 1.5,
        'epic': 2.0,
        'legendary': 3.0,
        'mythical': 5.0
    }
}

TRUE_MAFIA_CONFIG = {
    'patterns': {
        'game_win': [
            r'Игра окончена!.*?Победил[аи]? (.+?)\n',
            r'Победитель: (.+?)\n.*?Игра завершена',
            r'(.+?) побеждает в мафии!'
        ],
        'best_player': [
            r'Лучший игрок: (.+?) награждается (\d+) очками',
            r'(.+?) признан\(а\) лучшим игроком! Награда: (\d+)'
        ],
        'role_bonus': [
            r'(.+?) как (.+?) получает бонус (\d+) очков',
            r'Бонус за роль: (.+?) \+(\d+)'
        ]
    },
    'role_bonuses': {
        'mafia': 20,
        'don': 25,
        'sheriff': 15,
        'civilian': 10,
        'doctor': 15
    }
}

BUNKERRP_CONFIG = {
    'patterns': {
        'bunker_survival': [
            r'Прошли в бункер:\n(.+?)(?:\n\n|$)',
            r'Выжили в бункере:\n(.+?)(?:\n\n|$)',
            r'Список выживших:\n(.+?)(?:\n\n|$)'
        ],
        'role_action': [
            r'(.+?) как (.+?) выполняет действие и получает (\d+) очков',
            r'Действие выполнено! (.+?) получает (\d+) очков'
        ],
        'game_completion': [
            r'Игра завершена! Выжившие: (.+?)\n.*?Награда: (\d+)',
            r'Результаты игры: (.+?) получают по (\d+) очков'
        ]
    }
}

# Настройки парсинга
PARSER_SETTINGS = {
    'enable_cache': True,
    'cache_duration_minutes': 30,
    'max_username_length': 50,
    'min_points_threshold': 1,
    'max_points_threshold': 10000,
    'confidence_threshold': 0.6,
    'enable_fuzzy_matching': True,
    'fuzzy_threshold': 0.8,
    'log_parsing_errors': True,
    'save_unparsed_messages': False,
    'validation_rules': {
        'check_duplicates': True,
        'duplicate_window_minutes': 5,
        'validate_points_range': True,
        'sanitize_usernames': True
    }
}
