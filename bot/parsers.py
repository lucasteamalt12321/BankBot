# parsers.py
import re
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class ParsedActivity:
    user_identifier: str
    activity_type: str
    points: int
    game_source: str
    metadata: Dict = None


class EnhancedFishingParser:
    """Улучшенный парсер для рыбалки с детальным извлечением метаданных"""
    
    def __init__(self):
        self.patterns = {
            'fishing': r'Рыбак: ([^\n]+?)\s*\n.*?Монеты: \+(\d+) \(\d+\)💰',
            'experience': r'Опыт: \+(\d+) \(\d+ / \d+\)🔋',
            'catch': r'На крючке: (.+?) \((.+?) кг\)',
            'weather': r'Погода: (.+?)\n',
            'location': r'Место: (.+?)\n',
            'energy': r'Энергии осталось: (\d+) ⚡️',
            'rod': r'Удочка: (.+?) \(ещё (\d+) мин\.\)'
        }
    
    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        """Парсит сообщение рыбалки с детальными метаданными"""
        activities = []
        
        # Проверяем, что это сообщение рыбалки
        if '🎣 [Рыбалка] 🎣' not in message_text and '🎣' not in message_text:
            return activities
        
        # Извлекаем основную информацию
        fishing_match = re.search(self.patterns['fishing'], message_text, re.DOTALL)
        if fishing_match:
            user_identifier = fishing_match.group(1).strip()
            coins = int(fishing_match.group(2))
            
            # Извлекаем дополнительную информацию
            exp_match = re.search(self.patterns['experience'], message_text)
            catch_match = re.search(self.patterns['catch'], message_text)
            weather_match = re.search(self.patterns['weather'], message_text)
            location_match = re.search(self.patterns['location'], message_text)
            energy_match = re.search(self.patterns['energy'], message_text)
            rod_match = re.search(self.patterns['rod'], message_text)
            
            metadata = {
                'raw_message': message_text[:200],
                'experience': int(exp_match.group(1)) if exp_match else 0,
                'catch': catch_match.group(1) if catch_match else 'Unknown',
                'catch_weight': catch_match.group(2) if catch_match else '0',
                'weather': weather_match.group(1) if weather_match else 'Unknown',
                'location': location_match.group(1) if location_match else 'Unknown',
                'energy_left': int(energy_match.group(1)) if energy_match else 0
            }
            
            # Добавляем информацию об удочке, если есть
            if rod_match:
                metadata['rod'] = rod_match.group(1)
                metadata['rod_time_left'] = int(rod_match.group(2))
            
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='fishing',
                points=coins,
                game_source='shmalala',
                metadata=metadata
            )
            activities.append(activity)
        
        return activities


class EnhancedShmalalaParser:
    """Улучшенный парсер для Shmalala с полной поддержкой крокодила"""

    def __init__(self):
        self.patterns = {
            'battle_win': r'Победил\(а\) (.+?) и забрал\(а\) (\d+) 💰 монетки',
            'battle_participate': r'Участвовал\(а\) (.+?) и получил\(а\) (\d+) 💰 монетки',
            'crocodile_win': r'💵 Приз за победу \+(\d+) монета 💵',
            'fishing': r'Рыбак: ([^\n]+?)\s*\n(?:.*?\n)*?.*?Монеты: \+(\d+) \(\d+\)[💰$]?',
            'trap': r'🦞 \[Ловушка\].*?Монеты: \+(\d+) \(\d+\)💰',
            'crocodile_word': r'^([^\n]+?):\s*\n(.+)$',
            'crocodile_correct_guess': r'(.+?) угадал\(а\) слово!',
            'crocodile_participants': r'Участники?:((?:\n.+?)+)',
            'crocodile_game_start': r'\[Игра Крокодил\] Начался новый раунд!',
            'crocodile_game_end': r'💵 Приз за победу \+(\d+) монета 💵',
            'daily_bonus': r'Ежедневный бонус: \+(\d+) монет',
            'level_up': r'(.+?) достиг\(ла\) уровня (\d+)! Награда: (\d+) монет'
        }
        
        # Состояние игры "Крокодил" для каждого чата
        self.crocodile_games = {}
        # Инициализируем активную игру крокодила
        self.active_crocodile_game = {
            'participants': set(),
            'words_submitted': {},
            'correct_guesses': set(),
            'start_time': None
        }

        # Состояние игры "Крокодил" для каждого чата
        self.crocodile_games = {}

    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        """Парсит сообщение и возвращает список активностей"""
        activities = []

        # Парсим начало игры в крокодила
        if re.search(self.patterns['crocodile_game_start'], message_text):
            self.active_crocodile_game = {
                'participants': set(),
                'words_submitted': {},
                'correct_guesses': set(),
                'start_time': datetime.utcnow()
            }
            logger.info("Crocodile game started")

        # Парсим участников крокодила
        participants_match = re.search(self.patterns['crocodile_participants'], message_text, re.DOTALL)
        if participants_match:
            participants_text = participants_match.group(1)
            participants = [p.strip() for p in participants_text.split('\n') if p.strip()]
            self.active_crocodile_game['participants'].update(participants)
            logger.info(f"Crocodile participants: {participants}")

        # Парсим загаданные слова в крокодиле (улучшенный паттерн)
        crocodile_word_match = re.search(self.patterns['crocodile_word'], message_text)
        if crocodile_word_match and ('[Игра Крокодил]' in message_text or 'Shmalala' not in message_text):
            user_identifier = crocodile_word_match.group(1).strip()
            word = crocodile_word_match.group(2).strip()

            # Сохраняем слово пользователя
            self.active_crocodile_game['words_submitted'][user_identifier] = {
                'word': word,
                'timestamp': datetime.utcnow()
            }

            # Добавляем пользователя в участники
            self.active_crocodile_game['participants'].add(user_identifier)

            # Начисляем за участие (1 банковская монета)
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='crocodile_participate',
                points=1,
                game_source='shmalala',
                metadata={'word': word, 'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим отдельные случаи участия в крокодиле (новый паттерн)
        simple_crocodile_match = re.search(r'^([^\n]+?):\s*\n(.+)\n\n\[Игра Крокодил\]', message_text, re.MULTILINE | re.DOTALL)
        if simple_crocodile_match:
            user_identifier = simple_crocodile_match.group(1).strip()
            word = simple_crocodile_match.group(2).strip()

            # Сохраняем слово пользователя
            self.active_crocodile_game['words_submitted'][user_identifier] = {
                'word': word,
                'timestamp': datetime.utcnow()
            }

            # Добавляем пользователя в участники
            self.active_crocodile_game['participants'].add(user_identifier)

            # Начисляем за участие (1 банковская монета)
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='crocodile_participate',
                points=1,
                game_source='shmalala',
                metadata={'word': word, 'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим правильные отгадывания
        correct_guess_match = re.search(self.patterns['crocodile_correct_guess'], message_text)
        if correct_guess_match:
            user_identifier = correct_guess_match.group(1).strip()
            self.active_crocodile_game['correct_guesses'].add(user_identifier)

            # Начисляем за правильное отгадывание (5 банковских монет)
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='crocodile_correct_guess',
                points=5,
                game_source='shmalala',
                metadata={'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим победу в крокодиле
        crocodile_win_match = re.search(self.patterns['crocodile_win'], message_text)
        if crocodile_win_match and '[Игра Крокодил]' in message_text:
            points = int(crocodile_win_match.group(1))

            # Определяем победителя (последний правильно отгадавший)
            if self.active_crocodile_game['correct_guesses']:
                winner = list(self.active_crocodile_game['correct_guesses'])[-1]

                activity = ParsedActivity(
                    user_identifier=winner,
                    activity_type='crocodile_win',
                    points=points,
                    game_source='shmalala',
                    metadata={'raw_message': message_text[:200], 'win_type': 'final'}
                )
                activities.append(activity)

            # Сбрасываем состояние игры
            self.active_crocodile_game = {
                'participants': set(),
                'words_submitted': {},
                'correct_guesses': set(),
                'start_time': None
            }

        # Парсим бой (существующая логика)
        battle_match = re.search(self.patterns['battle_win'], message_text)
        if battle_match:
            user_identifier = battle_match.group(1).strip()
            points = int(battle_match.group(2))

            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='battle_win',
                points=points,
                game_source='shmalala',
                metadata={'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим рыбалку - используем улучшенный парсер
        enhanced_fishing_parser = EnhancedFishingParser()
        fishing_activities = enhanced_fishing_parser.parse_message(message_text)
        if fishing_activities:
            activities.extend(fishing_activities)
        else:
            # Fallback на старый парсер рыбалки
            fishing_match = re.search(self.patterns['fishing'], message_text, re.DOTALL)
            if fishing_match:
                user_identifier = fishing_match.group(1).strip()
                points = int(fishing_match.group(2))

                activity = ParsedActivity(
                    user_identifier=user_identifier,
                    activity_type='fishing',
                    points=points,
                    game_source='shmalala',
                    metadata={'raw_message': message_text[:200]}
                )
                activities.append(activity)

        # Парсим ловушку (существующая логика)
        trap_match = re.search(self.patterns['trap'], message_text, re.DOTALL)
        if trap_match:
            points = int(trap_match.group(1))

            # Для ловушки определяем пользователя по контексту
            # В реальной реализации нужно анализировать предыдущие сообщения
            if self.active_crocodile_game['participants']:
                user_identifier = list(self.active_crocodile_game['participants'])[-1]
            else:
                user_identifier = 'unknown'

            if user_identifier != 'unknown':
                activity = ParsedActivity(
                    user_identifier=user_identifier,
                    activity_type='trap',
                    points=points,
                    game_source='shmalala',
                    metadata={'raw_message': message_text[:200]}
                )
                activities.append(activity)

        # Парсим ежедневный бонус
        daily_bonus_match = re.search(self.patterns['daily_bonus'], message_text)
        if daily_bonus_match:
            points = int(daily_bonus_match.group(1))
            activity = ParsedActivity(
                user_identifier='unknown',  # Daily bonus doesn't specify user
                activity_type='daily_bonus',
                points=points,
                game_source='shmalala',
                metadata={'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим повышение уровня
        level_up_match = re.search(self.patterns['level_up'], message_text)
        if level_up_match:
            user_identifier = level_up_match.group(1).strip()
            points = int(level_up_match.group(3))
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='level_up',
                points=points,
                game_source='shmalala',
                metadata={'raw_message': message_text[:200], 'level': int(level_up_match.group(2))}
            )
            activities.append(activity)

        return activities


class EnhancedGDCardsParser:
    """Улучшенный парсер для GD Cards с детальными метаданными"""

    def __init__(self):
        self.patterns = {
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
        
        self.rarity_map = {
            'Обычная': 'common',
            'Редкая': 'rare',
            'Эпическая': 'epic',
            'Легендарная': 'legendary'
        }
    
    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        """Парсит сообщение карточной игры с детальными метаданными"""
        activities = []
        
        # Проверяем, что это сообщение карточной игры
        if not any(keyword in message_text for keyword in [
            '🃏 НОВАЯ КАРТА 🃏', '🃏', '🖼 НОВАЯ КАРТА', '🖼', 'НОВАЯ КАРТА', 'Очки:'
        ]):
            return activities
        
        # Извлекаем основную информацию
        player_match = re.search(self.patterns['player'], message_text)
        points_match = re.search(self.patterns['points'], message_text)
        
        if player_match and points_match:
            user_identifier = player_match.group(1).strip()
            points = int(points_match.group(1))
            
            # Извлекаем дополнительную информацию
            card_match = re.search(self.patterns['card_name'], message_text)
            rarity_match = re.search(self.patterns['rarity'], message_text)
            collection_match = re.search(self.patterns['collection'], message_text)
            limit_match = re.search(self.patterns['card_limit'], message_text)
            description_match = re.search(self.patterns['description'], message_text)
            category_match = re.search(self.patterns['category'], message_text)
            owners_match = re.search(self.patterns['card_owners'], message_text)
            
            # Определяем редкость
            rarity = 'common'
            if rarity_match:
                rarity_text = rarity_match.group(1)
                rarity = self.rarity_map.get(rarity_text, 'common')
            
            metadata = {
                'raw_message': message_text[:200],
                'card_name': card_match.group(1) if card_match else 'Unknown',
                'rarity': rarity,
                'collection_current': int(collection_match.group(1)) if collection_match else 0,
                'collection_total': int(collection_match.group(2)) if collection_match else 0,
                'daily_limit_used': int(limit_match.group(1)) if limit_match else 0,
                'daily_limit_total': int(limit_match.group(2)) if limit_match else 0,
                'description': description_match.group(1) if description_match else '',
                'category': category_match.group(1) if category_match else '',
                'card_owners': int(owners_match.group(1)) if owners_match else 0
            }
            
            activity_type = f'card_{rarity}'
            
            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type=activity_type,
                points=points,
                game_source='gdcards',
                metadata=metadata
            )
            activities.append(activity)
        
        return activities


class GDCardsParser:
    """Парсер для GD Cards"""

    def __init__(self):
        self.patterns = {
            'new_card': r'Игрок: ([^\n]+?)\n.*?\n.*?\n.*?Очки: \+(\d+)',
            'card_rarity': r'(?:Редкость: )?(Обычная|Редкая|Эпическая|Легендарная) (?:\(|⚪️|🔴|🟣|🟡).*',
            'new_card_alt': r'Карта: "([^"]+)"\n.*?Очки: \+(\d+)',
            'new_card_player': r'Игрок: (.+?)\n',
            'gd_cards_full': r'Игрок: ([^\n]+?)\n.*?\n.*?\n.*?Карта: "([^"]+)"\n.*?\n.*?\n.*?Очки: \+(\d+)',
            'rarity_pattern': r'Редкость: (Обычная|Редкая|Эпическая|Легендарная)'
        }

    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        activities = []

        # Используем улучшенный парсер сначала
        enhanced_parser = EnhancedGDCardsParser()
        enhanced_activities = enhanced_parser.parse_message(message_text)
        if enhanced_activities:
            return enhanced_activities

        # Fallback на старый парсер
        # Полный паттерн для GD Cards (для корректного парсинга примеров)
        full_match = re.search(self.patterns['gd_cards_full'], message_text, re.DOTALL)
        if full_match:
            user_identifier = full_match.group(1).strip()
            points = int(full_match.group(3))
            
            # Определяем редкость карты
            rarity = 'common'
            rarity_match = re.search(self.patterns['rarity_pattern'], message_text)
            if rarity_match:
                rarity_text = rarity_match.group(1)
                rarity_map = {
                    'Обычная': 'common',
                    'Редкая': 'rare',
                    'Эпическая': 'epic',
                    'Легендарная': 'legendary'
                }
                rarity = rarity_map.get(rarity_text, 'common')

            activity_type = f'card_{rarity}'

            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type=activity_type,
                points=points,
                game_source='gdcards',
                metadata={'raw_message': message_text[:200], 'rarity': rarity, 'card_name': full_match.group(2)}
            )
            activities.append(activity)

        # Альтернативный паттерн для новой карты (для сообщений в формате из примера)
        elif not full_match:
            # Ищем игрока и очки
            player_match = re.search(r'Игрок: ([^\n]+?)\n', message_text)
            points_match = re.search(r'Очки: \+(\d+)', message_text)
            
            if player_match and points_match:
                user_identifier = player_match.group(1).strip()
                points = int(points_match.group(1))
                
                # Определяем редкость карты
                rarity = 'common'
                rarity_match = re.search(self.patterns['rarity_pattern'], message_text)
                if rarity_match:
                    rarity_text = rarity_match.group(1)
                    rarity_map = {
                        'Обычная': 'common',
                        'Редкая': 'rare',
                        'Эпическая': 'epic',
                        'Легендарная': 'legendary'
                    }
                    rarity = rarity_map.get(rarity_text, 'common')

                activity_type = f'card_{rarity}'
                
                # Ищем название карты
                card_match = re.search(r'Карта: "([^"]+)"', message_text)
                card_name = card_match.group(1) if card_match else "Unknown"

                activity = ParsedActivity(
                    user_identifier=user_identifier,
                    activity_type=activity_type,
                    points=points,
                    game_source='gdcards',
                    metadata={'raw_message': message_text[:200], 'rarity': rarity, 'card_name': card_name}
                )
                activities.append(activity)

        return activities


class TrueMafiaParser:
    """Парсер для True Mafia"""

    def __init__(self):
        self.patterns = {
            'game_win': r'Игра окончена!.*?Победил[аи]? (.+?)\n',
            'game_participation': r'Игроки?:((?:\n.+?)+)'
        }

    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        activities = []

        # Парсим победу в мафии
        win_match = re.search(self.patterns['game_win'], message_text, re.DOTALL)
        if win_match:
            user_identifier = win_match.group(1).strip()

            activity = ParsedActivity(
                user_identifier=user_identifier,
                activity_type='game_win',
                points=1,
                game_source='true_mafia',
                metadata={'raw_message': message_text[:200]}
            )
            activities.append(activity)

        # Парсим участие в игре
        participation_match = re.search(self.patterns['game_participation'], message_text, re.DOTALL)
        if participation_match:
            players_text = participation_match.group(1)
            players = [p.strip() for p in players_text.split('\n') if p.strip()]

            for player in players:
                activity = ParsedActivity(
                    user_identifier=player,
                    activity_type='game_participation',
                    points=1,
                    game_source='true_mafia',
                    metadata={'raw_message': message_text[:200]}
                )
                activities.append(activity)

        return activities


class BunkerRPParser:
    """Парсер для Bunker RP"""

    def __init__(self):
        self.patterns = {
            'bunker_survival': r'Прошли в бункер:\n(.+?)(?:\n\n|$)',
            'game_participation': r'Игроки?:((?:\n.+?)+)'
        }

    def parse_message(self, message_text: str) -> List[ParsedActivity]:
        activities = []

        # Парсим выживших в бункере
        survival_match = re.search(self.patterns['bunker_survival'], message_text, re.DOTALL)
        if survival_match:
            players_text = survival_match.group(1)
            players = [p.strip() for p in players_text.split('\n') if p.strip()]

            for player in players:
                activity = ParsedActivity(
                    user_identifier=player,
                    activity_type='bunker_survival',
                    points=1,
                    game_source='bunkerrp',
                    metadata={'raw_message': message_text[:200]}
                )
                activities.append(activity)

        # Парсим участие в игре
        participation_match = re.search(self.patterns['game_participation'], message_text, re.DOTALL)
        if participation_match:
            players_text = participation_match.group(1)
            players = [p.strip() for p in players_text.split('\n') if p.strip()]

            for player in players:
                activity = ParsedActivity(
                    user_identifier=player,
                    activity_type='game_participation',
                    points=1,
                    game_source='bunkerrp',
                    metadata={'raw_message': message_text[:200]}
                )
                activities.append(activity)

        return activities


class UniversalParser:
    """Универсальный парсер для всех игр"""

    def __init__(self):
        self.parsers = {
            'shmalala': EnhancedShmalalaParser(),
            'gdcards': GDCardsParser(),
            'true_mafia': TrueMafiaParser(),
            'bunkerrp': BunkerRPParser()
        }

    def parse_message(self, message_text: str, source_hint: str = None) -> List[ParsedActivity]:
        """Парсит сообщение, пытаясь определить источник автоматически"""
        all_activities = []

        if source_hint and source_hint in self.parsers:
            # Если указан источник, используем только его парсер
            activities = self.parsers[source_hint].parse_message(message_text)
            all_activities.extend(activities)
        else:
            # Автоматическое определение источника по ключевым словам
            # Улучшаем определение Shmalala - добавляем эмодзи и другие возможные ключевые слова
            if any(keyword in message_text for keyword in [
                'Shmalala', 'Рыбалка', 'Крокодил', 'Битва', 'рыбалка', 'крокодил', 'битва',
                'рыбак', 'Рыбак', 'Fish', 'Fishing', '낚시', 'рыбка', 'рыбачок', 'шмалала',
                'Шмалала', 'Shmal', 'шмала', 'Шмала', '🎣', '[Рыбалка]', '[Крокодил]', '[Битва]',
                'Ежедневный бонус', 'уровня', 'достиг'
            ]):
                activities = self.parsers['shmalala'].parse_message(message_text)
                all_activities.extend(activities)
            elif any(keyword in message_text for keyword in [
                'НОВАЯ КАРТА', 'Очки:', 'GDcards', 'Карта:', 'новая карта', 'карта:',
                'GD Cards', 'gd cards', 'gdcards', 'Card', 'card', '🃏', '🖼', 'редкость', 'Редкость:'
            ]):
                activities = self.parsers['gdcards'].parse_message(message_text)
                all_activities.extend(activities)
            elif any(keyword in message_text for keyword in [
                'Мафия', 'Игра окончена', 'true_mafia', 'mafia', 'Мафия', 'игра окончена'
            ]):
                activities = self.parsers['true_mafia'].parse_message(message_text)
                all_activities.extend(activities)
            elif any(keyword in message_text for keyword in [
                'Бункер', 'бункер', 'bunker', 'Bunker', ' bunker rp', 'bunkerrp'
            ]):
                activities = self.parsers['bunkerrp'].parse_message(message_text)
                all_activities.extend(activities)

        return all_activities


# Дополнительные функции для работы с парсером
def parse_from_file(file_path: str) -> List[ParsedActivity]:
    """Парсит сообщения из файла и возвращает список активностей"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        messages = split_messages(content)
        parser = UniversalParser()
        
        all_activities = []
        for message in messages:
            activities = parser.parse_message(message)
            all_activities.extend(activities)
        
        return all_activities
    except Exception as e:
        logger.error(f"Ошибка при парсинге файла {file_path}: {e}")
        return []


def split_messages(text: str) -> List[str]:
    """Разделяет текст на отдельные сообщения по эмодзи"""
    # Разделяем по паттернам начала сообщений
    pattern = r'(🎣 \[Рыбалка\] 🎣|🃏 НОВАЯ КАРТА 🃏)'
    
    # Разделяем текст по паттерну, сохраняя разделители
    parts = re.split(pattern, text)
    
    messages = []
    current_msg = ""
    
    for i, part in enumerate(parts):
        if re.match(pattern, part):
            # Если предыдущее сообщение не пустое, сохраняем его
            if current_msg.strip():
                messages.append(current_msg.strip())
            # Начинаем новое сообщение с заголовка
            current_msg = part
        else:
            # Добавляем содержимое к текущему сообщению
            current_msg += part
    
    # Добавляем последнее сообщение
    if current_msg.strip():
        messages.append(current_msg.strip())
    
    # Фильтруем сообщения - оставляем только те, что содержат нужные паттерны
    filtered_messages = []
    for msg in messages:
        if ('🎣 [Рыбалка] 🎣' in msg or '🃏 НОВАЯ КАРТА 🃏' in msg) and len(msg) > 50:
            filtered_messages.append(msg)
    
    return filtered_messages


def save_results_to_json(activities: List[ParsedActivity], output_file: str):
    """Сохраняет результаты парсинга в JSON файл"""
    try:
        import json
        results = []
        for activity in activities:
            result = {
                'user_identifier': activity.user_identifier,
                'activity_type': activity.activity_type,
                'points': activity.points,
                'game_source': activity.game_source,
                'metadata': activity.metadata
            }
            results.append(result)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Результаты сохранены в файл: {output_file}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в файл {output_file}: {e}")


def get_user_statistics(activities: List[ParsedActivity]) -> Dict:
    """Получает статистику по пользователям"""
    stats = {}
    
    for activity in activities:
        user = activity.user_identifier
        if user not in stats:
            stats[user] = {
                'total_points': 0,
                'activities': {},
                'games': set()
            }
        
        stats[user]['total_points'] += activity.points
        stats[user]['games'].add(activity.game_source)
        
        if activity.activity_type not in stats[user]['activities']:
            stats[user]['activities'][activity.activity_type] = 0
        stats[user]['activities'][activity.activity_type] += 1
    
    # Конвертируем set в list для JSON сериализации
    for user_stats in stats.values():
        user_stats['games'] = list(user_stats['games'])
    
    return stats


def parse_single_message(message_text: str) -> List[ParsedActivity]:
    """Парсит одно сообщение"""
    parser = UniversalParser()
    return parser.parse_message(message_text)