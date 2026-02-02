from sqlalchemy.orm import Session
from database.database import GameSession, GamePlayer, User, Transaction
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import random
import structlog

logger = structlog.get_logger()

class CitiesGame:
    """Игра 'Города'"""

    def __init__(self):
        # Списки городов по сложности (упрощенные для демонстрации)
        self.cities = {
            'easy': [
                'Москва', 'Санкт-Петербург', 'Екатеринбург', 'Новосибирск', 'Казань',
                'Нижний Новгород', 'Челябинск', 'Омск', 'Самара', 'Ростов-на-Дону'
            ],
            'medium': [
                'Волгоград', 'Уфа', 'Красноярск', 'Пермь', 'Воронеж', 'Вологда',
                'Ярославль', 'Ижевск', 'Ульяновск', 'Хабаровск'
            ],
            'hard': [
                'Благовещенск', 'Чита', 'Южно-Сахалинск', 'Петропавловск-Камчатский',
                'Магадан', 'Анадырь', 'Нарьян-Мар', 'Салехард', 'Воркута'
            ]
        }

    def is_valid_city(self, city: str, difficulty: str = 'easy') -> bool:
        """Проверка существования города"""
        all_cities = []
        for level in ['easy', 'medium', 'hard']:
            if difficulty == 'hard' or level == difficulty:
                all_cities.extend(self.cities[level])
        return city.strip().title() in [c.title() for c in all_cities]

    def get_city_by_first_letter(self, letter: str, used_cities: List[str], difficulty: str = 'easy') -> Optional[str]:
        """Получить город на заданную букву"""
        available_cities = []
        for level in ['easy', 'medium', 'hard']:
            if difficulty == 'hard' or level == difficulty:
                available_cities.extend(self.cities[level])

        # Исключаем использованные города
        available_cities = [c for c in available_cities if c not in used_cities]

        # Фильтруем по первой букве
        matching_cities = [c for c in available_cities if c.upper().startswith(letter.upper())]

        return random.choice(matching_cities) if matching_cities else None

class KillerWordsGame:
    """Игра 'Слова, которые могут убить'"""

    def __init__(self):
        self.categories = {
            'оружие': ['нож', 'пистолет', 'автомат', 'яд', 'бомба', 'топор'],
            'яды': ['мышьяк', 'цианид', 'стрихнин', 'полоний', 'рицин'],
            'стихии': ['огонь', 'вода', 'земля', 'воздух', 'молния', 'лед'],
            'животные': ['змея', 'тигр', 'лев', 'медведь', 'волк', 'акула']
        }

        self.letter_combinations = ['уби', 'смер', 'конц', 'гибе', 'смерт', 'убий']

    def is_killer_word(self, word: str) -> Tuple[bool, str]:
        """Проверка, является ли слово 'убийственным'"""
        word_lower = word.lower().strip()

        # Проверка по категориям
        for category, words in self.categories.items():
            if word_lower in [w.lower() for w in words]:
                return True, f"killer_category_{category}"

        # Проверка по комбинациям букв
        for combo in self.letter_combinations:
            if combo in word_lower:
                return True, "killer_letters"

        return False, ""

class GDLevelsGame:
    """Игра 'Уровни GD' - города, но с названиями уровней Geometry Dash"""

    def __init__(self):
        # Названия уровней GD (упрощенные)
        self.levels = [
            'Stereo Madness', 'Back on Track', 'Polargeist', 'Dry Out', 'Base after Base',
            'Cant Let Go', 'Jumper', 'Time Machine', 'Cycles', 'xStep',
            'Clutterfunk', 'Theory of Everything', 'Electroman AD', 'Clubstep', 'Electrodynamix',
            'Hexagon Force', 'Blast Processing', 'Toe II', 'Geometrical Dominator', 'Deadlocked'
        ]

    def is_valid_level(self, level: str) -> bool:
        """Проверка существования уровня"""
        return level.strip() in self.levels

    def get_level_by_first_letter(self, letter: str, used_levels: List[str]) -> Optional[str]:
        """Получить уровень на заданную букву"""
        available_levels = [l for l in self.levels if l not in used_levels]
        matching_levels = [l for l in available_levels if l.upper().startswith(letter.upper())]

        return random.choice(matching_levels) if matching_levels else None

class GamesSystem:
    """Система мини-игр"""

    def __init__(self, db: Session):
        self.db = db
        self.cities_game = CitiesGame()
        self.killer_words_game = KillerWordsGame()
        self.gd_levels_game = GDLevelsGame()

    def create_game_session(self, game_type: str, creator_id: int) -> GameSession:
        """Создание новой игровой сессии"""

        session = GameSession(
            game_type=game_type,
            status='waiting'
        )

        self.db.add(session)
        self.db.flush()  # Получаем ID сессии

        # Добавляем создателя как первого игрока
        player = GamePlayer(
            session_id=session.id,
            user_id=creator_id
        )

        self.db.add(player)
        self.db.commit()
        self.db.refresh(session)

        return session

    def join_game_session(self, session_id: int, user_id: int) -> bool:
        """Присоединение к игровой сессии"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or session.status != 'waiting':
            return False

        # Проверяем, не участвует ли уже пользователь
        existing_player = self.db.query(GamePlayer).filter(
            GamePlayer.session_id == session_id,
            GamePlayer.user_id == user_id
        ).first()

        if existing_player:
            return False

        # Проверяем лимит игроков
        player_count = self.db.query(GamePlayer).filter(GamePlayer.session_id == session_id).count()
        if player_count >= 6:  # Максимум 6 игроков
            return False

        player = GamePlayer(
            session_id=session_id,
            user_id=user_id
        )

        self.db.add(player)
        self.db.commit()

        return True

    def start_game_session(self, session_id: int, starter_id: int) -> bool:
        """Запуск игровой сессии"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or session.status != 'waiting':
            return False

        # Проверяем, что стартер является участником
        player = self.db.query(GamePlayer).filter(
            GamePlayer.session_id == session_id,
            GamePlayer.user_id == starter_id
        ).first()

        if not player:
            return False

        # Получаем всех игроков
        players = self.db.query(GamePlayer).filter(GamePlayer.session_id == session_id).all()
        if len(players) < 2:
            return False

        # Запускаем игру
        session.status = 'active'
        session.current_player_id = players[0].user_id  # Первый игрок начинает
        session.updated_at = datetime.utcnow()

        self.db.commit()

        return True

    def process_cities_turn(self, session_id: int, user_id: int, city: str) -> Dict:
        """Обработка хода в игре 'Города'"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or session.status != 'active' or session.current_player_id != user_id:
            return {"success": False, "reason": "Не ваш ход или игра не активна"}

        city = city.strip().title()
        used_cities = session.used_cities or []

        # Проверяем, не использовался ли город
        if city in used_cities:
            return {"success": False, "reason": "Этот город уже был использован"}

        # Проверяем правило: город должен начинаться на последнюю букву предыдущего города
        if session.last_city:
            last_letter = session.last_city[-1].lower()
            if not city.lower().startswith(last_letter):
                return {"success": False, "reason": f"Город должен начинаться на букву '{last_letter.upper()}'"}

        # Проверяем существование города
        if not self.cities_game.is_valid_city(city):
            return {"success": False, "reason": "Такого города не существует"}

        # Начисляем награду
        reward = 5  # базовая награда
        self._award_points(user_id, reward, f"Города: {city}")

        # Обновляем состояние игры
        used_cities.append(city)
        session.last_city = city
        session.used_cities = used_cities
        session.updated_at = datetime.utcnow()

        # Переходим к следующему игроку
        next_player_id = self._get_next_player(session_id, user_id)
        session.current_player_id = next_player_id

        self.db.commit()

        return {
            "success": True,
            "city": city,
            "reward": reward,
            "next_player_id": next_player_id
        }

    def process_killer_words_turn(self, session_id: int, user_id: int, word: str) -> Dict:
        """Обработка хода в игре 'Слова, которые могут убить'"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or session.status != 'active' or session.current_player_id != user_id:
            return {"success": False, "reason": "Не ваш ход или игра не активна"}

        word = word.strip().lower()

        # Проверяем, является ли слово "убийственным"
        is_killer, killer_type = self.killer_words_game.is_killer_word(word)

        if is_killer:
            # Начисляем бонус за убийственное слово
            reward = 15
            self._award_points(user_id, reward, f"Убийственное слово: {word}")

            # Обновляем статистику игры
            game_data = session.game_data or {}
            game_data['killer_words'] = game_data.get('killer_words', 0) + 1
            session.game_data = game_data

        else:
            # Штраф за слабое слово
            penalty = -3
            self._award_points(user_id, penalty, f"Слабое слово: {word}")

        session.updated_at = datetime.utcnow()

        # Переходим к следующему игроку
        next_player_id = self._get_next_player(session_id, user_id)
        session.current_player_id = next_player_id

        self.db.commit()

        return {
            "success": True,
            "word": word,
            "is_killer": is_killer,
            "killer_type": killer_type,
            "reward": reward if is_killer else penalty,
            "next_player_id": next_player_id
        }

    def process_gd_levels_turn(self, session_id: int, user_id: int, level: str) -> Dict:
        """Обработка хода в игре 'Уровни GD'"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or session.status != 'active' or session.current_player_id != user_id:
            return {"success": False, "reason": "Не ваш ход или игра не активна"}

        level = level.strip()
        used_levels = session.used_cities or []  # используем то же поле для уровней

        # Проверяем, не использовался ли уровень
        if level in used_levels:
            return {"success": False, "reason": "Этот уровень уже был использован"}

        # Проверяем правило: уровень должен начинаться на последнюю букву предыдущего уровня
        if session.last_city:
            last_letter = session.last_city[-1].lower()
            if not level.lower().startswith(last_letter):
                return {"success": False, "reason": f"Уровень должен начинаться на букву '{last_letter.upper()}'"}

        # Проверяем существование уровня
        if not self.gd_levels_game.is_valid_level(level):
            return {"success": False, "reason": "Такого уровня GD не существует"}

        # Начисляем награду
        reward = 5  # базовая награда
        self._award_points(user_id, reward, f"GD Уровни: {level}")

        # Обновляем состояние игры
        used_levels.append(level)
        session.last_city = level  # используем для последней буквы
        session.used_cities = used_levels
        session.updated_at = datetime.utcnow()

        # Переходим к следующему игроку
        next_player_id = self._get_next_player(session_id, user_id)
        session.current_player_id = next_player_id

        self.db.commit()

        return {
            "success": True,
            "level": level,
            "reward": reward,
            "next_player_id": next_player_id
        }

    def _award_points(self, user_id: int, amount: int, description: str):
        """Начисление очков пользователю"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.balance += amount

            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                transaction_type='game_reward',
                source_game='mini_games',
                description=description
            )

            self.db.add(transaction)

    def _get_next_player(self, session_id: int, current_user_id: int) -> int:
        """Получение следующего игрока"""

        players = self.db.query(GamePlayer).filter(
            GamePlayer.session_id == session_id,
            GamePlayer.is_active == True
        ).order_by(GamePlayer.joined_at).all()

        player_ids = [p.user_id for p in players]
        current_index = player_ids.index(current_user_id)

        next_index = (current_index + 1) % len(player_ids)
        return player_ids[next_index]

    def get_game_session_info(self, session_id: int) -> Optional[Dict]:
        """Получение информации об игровой сессии"""

        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return None

        players = self.db.query(GamePlayer).filter(GamePlayer.session_id == session_id).all()

        return {
            "id": session.id,
            "game_type": session.game_type,
            "status": session.status,
            "current_player_id": session.current_player_id,
            "last_city": session.last_city,
            "players": [
                {
                    "user_id": p.user_id,
                    "score": p.score,
                    "is_active": p.is_active
                }
                for p in players
            ],
            "created_at": session.created_at,
            "updated_at": session.updated_at
        }

    def get_active_sessions(self, game_type: str = None) -> List[Dict]:
        """Получение активных сессий"""

        query = self.db.query(GameSession).filter(GameSession.status.in_(['waiting', 'active']))

        if game_type:
            query = query.filter(GameSession.game_type == game_type)

        sessions = query.order_by(GameSession.created_at.desc()).limit(10).all()

        return [
            {
                "id": s.id,
                "game_type": s.game_type,
                "status": s.status,
                "players_count": self.db.query(GamePlayer).filter(GamePlayer.session_id == s.id).count(),
                "created_at": s.created_at
            }
            for s in sessions
        ]