"""User service for business logic related to user management."""

from typing import Optional, List
from sqlalchemy.orm import Session
from database.database import User, UserAlias
from src.repository.user_repository import UserRepository


class UserService:
    """
    Сервис для управления пользователями.
    
    Содержит бизнес-логику связанную с пользователями, отделенную от Telegram API.
    Использует UserRepository для доступа к данным.
    """

    def __init__(self, user_repo: UserRepository):
        """
        Инициализация сервиса пользователей.

        Args:
            user_repo: Репозиторий для работы с пользователями
        """
        self.user_repo = user_repo

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по Telegram ID.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            User или None если не найден
        """
        return self.user_repo.get_by_telegram_id(telegram_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Получить пользователя по username.

        Args:
            username: Username пользователя

        Returns:
            User или None если не найден
        """
        return self.user_repo.get_by_username(username)

    def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        """
        Получить существующего пользователя или создать нового.

        Args:
            telegram_id: Telegram ID пользователя
            **kwargs: Дополнительные атрибуты для создания

        Returns:
            User (существующий или созданный)
        """
        return self.user_repo.get_or_create(telegram_id, **kwargs)

    def add_alias(
        self,
        user: User,
        alias_type: str,
        alias_value: str,
        game_source: str,
        confidence_score: float = 1.0
    ) -> UserAlias:
        """
        Добавить алиас пользователю.

        Args:
            user: Пользователь
            alias_type: Тип алиаса (username, first_name, game_nickname и т.д.)
            alias_value: Значение алиаса
            game_source: Источник алиаса (название игры)
            confidence_score: Уровень уверенности в сопоставлении

        Returns:
            Созданный UserAlias
        """
        alias = UserAlias(
            user_id=user.id,
            alias_type=alias_type,
            alias_value=alias_value,
            game_source=game_source,
            confidence_score=confidence_score
        )
        self.user_repo.session.add(alias)
        self.user_repo.session.commit()
        self.user_repo.session.refresh(alias)
        return alias

    def find_user_by_alias(
        self,
        alias_value: str,
        alias_type: Optional[str] = None
    ) -> Optional[User]:
        """
        Найти пользователя по алиасу.

        Args:
            alias_value: Значение алиаса
            alias_type: Тип алиаса (опционально)

        Returns:
            User или None если не найден
        """
        query = self.user_repo.session.query(UserAlias).filter(
            UserAlias.alias_value.ilike(f"%{alias_value}%")
        )
        if alias_type:
            query = query.filter(UserAlias.alias_type == alias_type)

        alias = query.first()
        return alias.user if alias else None

    def get_user_aliases(self, user_id: int) -> List[UserAlias]:
        """
        Получить все алиасы пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список алиасов
        """
        return self.user_repo.session.query(UserAlias).filter(
            UserAlias.user_id == user_id
        ).all()

    def search_users_by_name(self, name: str) -> List[User]:
        """
        Найти пользователей по имени (частичное совпадение).

        Args:
            name: Имя для поиска

        Returns:
            Список пользователей
        """
        return self.user_repo.search_by_name(name)

    def update_user_balance(self, user_id: int, new_balance: int) -> Optional[User]:
        """
        Обновить баланс пользователя.

        Args:
            user_id: ID пользователя
            new_balance: Новый баланс

        Returns:
            Обновленный User или None если не найден
        """
        return self.user_repo.update(user_id, balance=new_balance)

    def increase_user_balance(self, user_id: int, amount: int) -> Optional[User]:
        """
        Увеличить баланс пользователя.

        Args:
            user_id: ID пользователя
            amount: Сумма увеличения

        Returns:
            Обновленный User или None если не найден
        """
        user = self.user_repo.get(user_id)
        if user:
            user.balance += amount
            self.user_repo.session.commit()
            self.user_repo.session.refresh(user)
            return user
        return None

    def decrease_user_balance(self, user_id: int, amount: int) -> Optional[User]:
        """
        Уменьшить баланс пользователя.

        Args:
            user_id: ID пользователя
            amount: Сумма уменьшения

        Returns:
            Обновленный User или None если не найден
        """
        user = self.user_repo.get(user_id)
        if user:
            user.balance -= amount
            self.user_repo.session.commit()
            self.user_repo.session.refresh(user)
            return user
        return None
