# user_manager.py
from sqlalchemy.orm import Session
from database.database import User, UserAlias, get_db
from typing import Optional, List
import re
import difflib
from datetime import datetime


class UserManager:
    """Управление пользователями и их идентификацией"""

    def __init__(self, db: Session):
        self.db = db

    def normalize_username(self, username: str) -> str:
        """Нормализация username"""
        if not username:
            return ""

        # Убираем @ если есть
        username = username.lstrip('@')
        # Приводим к нижнему регистру
        username = username.lower()
        # Убираем лишние пробелы
        username = username.strip()
        # Убираем специальные символы для более гибкого сопоставления
        username = re.sub(r'[^a-z0-9_]', '', username)

        return username

    def normalize_name(self, name: str) -> str:
        """Нормализация имени"""
        if not name:
            return ""

        # Убираем лишние пробелы и приводим к нижнему регистру
        name = re.sub(r'\s+', ' ', name.strip().lower())
        
        # Убираем специальные символы и оставляем только буквы и пробелы
        name = re.sub(r'[^a-zа-яё\s]', '', name)
        
        # Убираем лишние пробелы снова после очистки
        name = re.sub(r'\s+', ' ', name.strip())

        return name

    def find_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Поиск пользователя по Telegram ID"""
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()

    def find_user_by_username(self, username: str) -> Optional[User]:
        """Поиск пользователя по username с нормализацией"""
        normalized = self.normalize_username(username)
        if not normalized:
            return None

        # Прямой поиск по username
        user = self.db.query(User).filter(User.username.ilike(f"%{normalized}%")).first()
        if user:
            return user

        # Поиск по алиасам
        alias = self.db.query(UserAlias).filter(
            UserAlias.alias_type == 'username',
            UserAlias.alias_value.ilike(f"%{normalized}%")
        ).first()

        if alias:
            return alias.user

        return None

    def find_user_by_name(self, name: str) -> Optional[User]:
        """Поиск пользователя по имени (fuzzy matching)"""
        normalized_name = self.normalize_name(name)
        if not normalized_name:
            return None

        # Ищем точное совпадение по first_name + last_name
        if ' ' in normalized_name:
            parts = normalized_name.split(' ', 1)
            first_name, last_name = parts[0], parts[1]

            user = self.db.query(User).filter(
                User.first_name.ilike(f"%{first_name}%"),
                User.last_name.ilike(f"%{last_name}%")
            ).first()

            if user:
                return user

        # Ищем по first_name
        user = self.db.query(User).filter(
            User.first_name.ilike(f"%{normalized_name}%")
        ).first()

        if user:
            return user

        # Fuzzy matching по алиасам
        aliases = self.db.query(UserAlias).filter(
            UserAlias.alias_type.in_(['first_name', 'first_last', 'game_nickname'])
        ).all()

        best_match = None
        best_score = 0

        for alias in aliases:
            alias_normalized = self.normalize_name(alias.alias_value)
            
            # Основная проверка по коэффициенту схожести
            score = difflib.SequenceMatcher(
                None, normalized_name, alias_normalized
            ).ratio()
            
            # Также проверяем с помощью индекса Жаккара (для имен без пробелов)
            jac_score = self.jaccard_similarity(set(normalized_name.split()), set(alias_normalized.split()))
            
            # Проверяем также с помощью SequenceMatcher с разными вариантами
            # Например, проверим, если имя и фамилия перепутаны местами
            reversed_name = ' '.join(normalized_name.split()[::-1]) if ' ' in normalized_name else normalized_name
            reversed_score = difflib.SequenceMatcher(None, reversed_name, alias_normalized).ratio()
            
            # Берем максимальный из трех показателей схожести
            max_score = max(score, jac_score, reversed_score)
            
            # Повышаем уверенность в сопоставлении для коротких имен
            if len(normalized_name) <= 3 and max_score > 0.5:  # Понижаем порог для коротких имен
                adjusted_score = max_score
            else:
                adjusted_score = max_score
            
            if adjusted_score > best_score and adjusted_score > 0.6:  # Снижаем порог до 60% для большей гибкости
                best_score = adjusted_score
                best_match = alias.user

        return best_match
    
    def jaccard_similarity(self, set1, set2):
        """Вычисление коэффициента Жаккара для оценки схожести двух множеств"""
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union != 0 else 0

    def identify_user(self, identifier: str, telegram_id: int = None) -> User:
        """
        Основной метод идентификации пользователя
        Алгоритм:
        1. Поиск по Telegram User ID (при наличии)
        2. Поиск по username (@nickname) с нормализацией
        3. Поиск по имени и фамилии с fuzzy matching
        4. Создание новой записи с автоматическим связыванием алиасов
        """

        # 1. Поиск по Telegram ID
        if telegram_id:
            user = self.find_user_by_telegram_id(telegram_id)
            if user:
                # Обновляем алиасы при наличии
                if identifier.startswith('@') or not ' ' in identifier:
                    self.add_alias(user, 'username', identifier, 'auto_detection')
                elif identifier:
                    self.add_alias(user, 'game_nickname', identifier, 'auto_detection')
                return user

        # 2. Поиск по username (с учетом различных вариантов)
        username_variants = [identifier]
        if identifier.startswith('@'):
            # Проверяем без @
            username_variants.append(identifier[1:])
        
        user = None
        for variant in username_variants:
            user = self.find_user_by_username(variant)
            if user:
                # Добавляем алиас если его нет
                self.add_alias(user, 'username', variant, 'auto_detection')
                return user

        # 3. Поиск по имени с fuzzy matching
        user = self.find_user_by_name(identifier)
        if user:
            # Добавляем алиас если его нет
            self.add_alias(user, 'game_nickname', identifier, 'auto_detection')
            return user

        # 4. Попробуем дополнительные стратегии поиска
        # Проверим, может быть это имя, но в немного другом формате
        if telegram_id:
            # Если у нас есть telegram_id, создаем пользователя с ним
            return self.create_user_from_identifier(identifier, telegram_id)
        else:
            # Если нет telegram_id, попробуем найти по алиасам более агрессивно
            user = self.aggressive_alias_search(identifier)
            if user:
                # Добавляем алиас если его нет
                self.add_alias(user, 'game_nickname', identifier, 'auto_detection')
                return user

        # 5. Создание нового пользователя
        return self.create_user_from_identifier(identifier, telegram_id)

    def create_user_from_identifier(self, identifier: str, telegram_id: int = None) -> User:
        """Создание нового пользователя из идентификатора"""

        # Определяем тип идентификатора
        if identifier.startswith('@'):
            username = self.normalize_username(identifier)
            user = User(
                telegram_id=telegram_id,
                username=username,
                balance=0
            )
        elif ' ' in identifier:
            # Предполагаем, что это имя и фамилия
            parts = identifier.split(' ', 1)
            user = User(
                telegram_id=telegram_id,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else None,
                balance=0
            )
        else:
            # Предполагаем, что это игровой никнейм
            user = User(
                telegram_id=telegram_id,
                first_name=identifier,
                balance=0
            )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # Добавляем алиас
        self.add_alias(user, 'game_nickname', identifier, 'initial_creation')

        return user

    def add_alias(self, user: User, alias_type: str, alias_value: str, game_source: str, confidence: float = 1.0):
        """Добавление алиаса пользователю"""

        # Проверяем, нет ли уже такого алиаса
        existing = self.db.query(UserAlias).filter(
            UserAlias.user_id == user.id,
            UserAlias.alias_type == alias_type,
            UserAlias.alias_value == alias_value
        ).first()

        if not existing:
            alias = UserAlias(
                user_id=user.id,
                alias_type=alias_type,
                alias_value=alias_value,
                game_source=game_source,
                confidence_score=confidence
            )
            self.db.add(alias)
            self.db.commit()

    def merge_users(self, primary_user_id: int, secondary_user_id: int):
        """Объединение двух пользователей (для админов)"""

        primary_user = self.db.query(User).filter(User.id == primary_user_id).first()
        secondary_user = self.db.query(User).filter(User.id == secondary_user_id).first()

        if not primary_user or not secondary_user:
            raise ValueError("Один из пользователей не найден")

        # Переносим баланс
        primary_user.balance += secondary_user.balance

        # Переносим алиасы
        for alias in secondary_user.aliases:
            alias.user_id = primary_user.id

        # Переносим транзакции
        for transaction in secondary_user.transactions:
            transaction.user_id = primary_user.id

        # Переносим покупки
        for purchase in secondary_user.purchases:
            purchase.user_id = primary_user.id

        # Обновляем время последней активности
        primary_user.last_activity = datetime.utcnow()

        # Удаляем вторичного пользователя
        self.db.delete(secondary_user)
        self.db.commit()

        # Логируем объединение
        from database.database import Transaction
        transaction = Transaction(
            user_id=primary_user.id,
            amount=0,
            transaction_type='system',
            source_game='admin',
            description=f"Объединение аккаунтов с пользователем {secondary_user_id}",
            meta_data={'merged_user_id': secondary_user_id}
        )
        self.db.add(transaction)
        self.db.commit()

    def aggressive_alias_search(self, identifier: str) -> Optional[User]:
        """Агрессивный поиск по алиасам с использованием различных стратегий"""
        normalized_identifier = self.normalize_name(identifier)
        
        # Поиск по подстроке в алиасах
        substring_matches = self.db.query(UserAlias).filter(
            UserAlias.alias_value.ilike(f'%{normalized_identifier}%')
        ).all()
        
        if substring_matches:
            # Возвращаем первого подходящего пользователя
            return substring_matches[0].user
        
        # Поиск с использованием более гибких правил
        all_aliases = self.db.query(UserAlias).all()
        best_match = None
        best_score = 0
        
        for alias in all_aliases:
            alias_normalized = self.normalize_name(alias.alias_value)
            
            # Проверяем схожесть с различными стратегиями
            scores = []
            
            # Стандартная проверка
            standard_score = difflib.SequenceMatcher(
                None, normalized_identifier, alias_normalized
            ).ratio()
            scores.append(standard_score)
            
            # Проверка с игнорированием пробелов
            no_space_score = difflib.SequenceMatcher(
                None, normalized_identifier.replace(' ', ''),
                alias_normalized.replace(' ', '')
            ).ratio()
            scores.append(no_space_score)
            
            # Проверка с реверсом
            reversed_score = difflib.SequenceMatcher(
                None, ' '.join(normalized_identifier.split()[::-1]), alias_normalized
            ).ratio()
            scores.append(reversed_score)
            
            max_score = max(scores)
            
            if max_score > best_score and max_score > 0.5:  # Пониженный порог для агрессивного поиска
                best_score = max_score
                best_match = alias.user
                
        return best_match