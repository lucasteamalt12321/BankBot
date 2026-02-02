from sqlalchemy.orm import Session
from database.database import DndSession, DndCharacter, DndDiceRoll, DndQuest, User
from typing import List, Dict, Optional
from datetime import datetime
import random
import structlog

logger = structlog.get_logger()

class DndSystem:
    """Система D&D Мастерской"""

    def __init__(self, db: Session):
        self.db = db

    def create_session(self, master_id: int, name: str, description: str = None, max_players: int = 6) -> DndSession:
        """Создание новой D&D сессии"""

        session = DndSession(
            master_id=master_id,
            name=name,
            description=description,
            max_players=max_players,
            status='planning'
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def join_session(self, session_id: int, player_id: int) -> bool:
        """Присоединение игрока к сессии"""

        session = self.db.query(DndSession).filter(DndSession.id == session_id).first()
        if not session or session.status != 'planning':
            return False

        if session.current_players >= session.max_players:
            return False

        # Проверяем, не участвует ли уже игрок
        existing_character = self.db.query(DndCharacter).filter(
            DndCharacter.session_id == session_id,
            DndCharacter.player_id == player_id
        ).first()

        if existing_character:
            return False

        session.current_players += 1
        self.db.commit()

        return True

    def start_session(self, session_id: int, master_id: int) -> bool:
        """Запуск D&D сессии"""

        session = self.db.query(DndSession).filter(DndSession.id == session_id).first()
        if not session or session.master_id != master_id or session.status != 'planning':
            return False

        session.status = 'active'
        session.started_at = datetime.utcnow()
        self.db.commit()

        return True

    def create_character(self, session_id: int, player_id: int, name: str, character_class: str,
                        background: str = None) -> Optional[DndCharacter]:
        """Создание персонажа"""

        session = self.db.query(DndSession).filter(DndSession.id == session_id).first()
        if not session or session.status not in ['planning', 'active']:
            return None

        # Проверяем, нет ли уже персонажа у игрока в этой сессии
        existing = self.db.query(DndCharacter).filter(
            DndCharacter.session_id == session_id,
            DndCharacter.player_id == player_id
        ).first()

        if existing:
            return None

        # Генерируем базовые характеристики (стандартный массив D&D)
        base_stats = {
            'strength': 15,
            'dexterity': 14,
            'constitution': 13,
            'intelligence': 12,
            'wisdom': 10,
            'charisma': 8
        }

        character = DndCharacter(
            session_id=session_id,
            player_id=player_id,
            name=name,
            character_class=character_class,
            background=background,
            stats=base_stats,
            inventory=[],
            notes=""
        )

        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)

        return character

    def roll_dice(self, player_id: int, session_id: int, dice_type: str, dice_count: int = 1,
                  modifier: int = 0, character_id: int = None, purpose: str = None,
                  is_secret: bool = False) -> Optional[DndDiceRoll]:
        """Бросок кубиков"""

        # Валидация типа кубика
        valid_dice = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
        if dice_type not in valid_dice:
            return None

        # Проверяем, что игрок участвует в сессии
        session = self.db.query(DndSession).filter(DndSession.id == session_id).first()
        if not session or session.status != 'active':
            return None

        # Если указан персонаж, проверяем что он принадлежит игроку
        if character_id:
            character = self.db.query(DndCharacter).filter(
                DndCharacter.id == character_id,
                DndCharacter.player_id == player_id,
                DndCharacter.session_id == session_id
            ).first()
            if not character:
                return None

        # Бросаем кубики
        results = []
        for _ in range(dice_count):
            results.append(random.randint(1, int(dice_type[1:])))

        result = sum(results)
        total = result + modifier

        dice_roll = DndDiceRoll(
            session_id=session_id,
            character_id=character_id,
            player_id=player_id,
            dice_type=dice_type,
            dice_count=dice_count,
            modifier=modifier,
            result=result,
            total=total,
            purpose=purpose,
            is_secret=is_secret
        )

        self.db.add(dice_roll)
        self.db.commit()
        self.db.refresh(dice_roll)

        return dice_roll

    def create_quest(self, character_id: int, title: str, description: str,
                    reward_xp: int = 0, reward_gold: int = 0) -> Optional[DndQuest]:
        """Создание квеста для персонажа"""

        character = self.db.query(DndCharacter).filter(DndCharacter.id == character_id).first()
        if not character:
            return None

        quest = DndQuest(
            character_id=character_id,
            title=title,
            description=description,
            reward_xp=reward_xp,
            reward_gold=reward_gold
        )

        self.db.add(quest)
        self.db.commit()
        self.db.refresh(quest)

        return quest

    def complete_quest(self, quest_id: int, master_id: int) -> bool:
        """Завершение квеста (только мастер)"""

        quest = self.db.query(DndQuest).join(DndCharacter).join(DndSession).filter(
            DndQuest.id == quest_id,
            DndSession.master_id == master_id
        ).first()

        if not quest or quest.status != 'active':
            return False

        quest.status = 'completed'
        quest.completed_at = datetime.utcnow()

        # Начисляем награды персонажу (в будущем можно расширить)
        character = quest.character
        # Здесь можно добавить логику начисления опыта и золота

        self.db.commit()

        return True

    def get_session_info(self, session_id: int) -> Optional[Dict]:
        """Получение информации о сессии"""

        session = self.db.query(DndSession).filter(DndSession.id == session_id).first()
        if not session:
            return None

        characters = self.db.query(DndCharacter).filter(DndCharacter.session_id == session_id).all()

        return {
            "id": session.id,
            "name": session.name,
            "description": session.description,
            "status": session.status,
            "master_id": session.master_id,
            "max_players": session.max_players,
            "current_players": session.current_players,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "characters": [
                {
                    "id": char.id,
                    "name": char.name,
                    "class": char.character_class,
                    "level": char.level,
                    "player_id": char.player_id
                }
                for char in characters
            ]
        }

    def get_character_info(self, character_id: int, player_id: int) -> Optional[Dict]:
        """Получение информации о персонаже"""

        character = self.db.query(DndCharacter).filter(
            DndCharacter.id == character_id,
            DndCharacter.player_id == player_id
        ).first()

        if not character:
            return None

        quests = self.db.query(DndQuest).filter(DndQuest.character_id == character_id).all()

        return {
            "id": character.id,
            "name": character.name,
            "class": character.character_class,
            "level": character.level,
            "background": character.background,
            "stats": character.stats,
            "inventory": character.inventory,
            "notes": character.notes,
            "session_id": character.session_id,
            "quests": [
                {
                    "id": q.id,
                    "title": q.title,
                    "description": q.description,
                    "status": q.status,
                    "reward_xp": q.reward_xp,
                    "reward_gold": q.reward_gold
                }
                for q in quests
            ]
        }

    def get_player_sessions(self, player_id: int) -> List[Dict]:
        """Получение сессий игрока"""

        # Сессии где игрок мастер
        master_sessions = self.db.query(DndSession).filter(DndSession.master_id == player_id).all()

        # Сессии где игрок участник
        player_sessions = self.db.query(DndSession).join(DndCharacter).filter(
            DndCharacter.player_id == player_id
        ).all()

        all_sessions = list(set(master_sessions + player_sessions))

        return [
            {
                "id": s.id,
                "name": s.name,
                "status": s.status,
                "is_master": s.master_id == player_id,
                "created_at": s.created_at
            }
            for s in all_sessions
        ]

    def get_recent_rolls(self, session_id: int, limit: int = 10) -> List[Dict]:
        """Получение последних бросков кубиков в сессии"""

        rolls = self.db.query(DndDiceRoll).filter(
            DndDiceRoll.session_id == session_id,
            DndDiceRoll.is_secret == False
        ).order_by(DndDiceRoll.created_at.desc()).limit(limit).all()

        return [
            {
                "id": r.id,
                "player_id": r.player_id,
                "character_name": r.character.name if r.character else None,
                "dice_type": r.dice_type,
                "dice_count": r.dice_count,
                "modifier": r.modifier,
                "result": r.result,
                "total": r.total,
                "purpose": r.purpose,
                "created_at": r.created_at
            }
            for r in rolls
        ]