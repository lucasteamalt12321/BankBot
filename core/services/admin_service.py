"""Admin service for business logic related to admin management."""

from typing import Optional, Union
from sqlalchemy.orm import Session
from database.database import User
from src.repository.user_repository import UserRepository


class AdminService:
    """
    Сервис для управления администраторами.
    
    Содержит бизнес-логику связанную с административными функциями.
    """

    def __init__(self, user_repo_or_session: Union[UserRepository, Session]):
        """
        Инициализация сервиса администраторов.

        Args:
            user_repo_or_session: Репозиторий для работы с пользователями или Session
        """
        if isinstance(user_repo_or_session, UserRepository):
            self.user_repo = user_repo_or_session
        else:
            # Создаем UserRepository из Session
            self.user_repo = UserRepository(user_repo_or_session)

    def is_admin(self, user_id: int) -> bool:
        """
        Проверка прав администратора пользователя.

        Args:
            user_id: Telegram ID пользователя

        Returns:
            True если пользователь администратор, False иначе
        """
        user = self.user_repo.get_by_telegram_id(user_id)
        return user.is_admin if user else False

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Поиск пользователя по username.

        Args:
            username: Username пользователя (с @ или без)

        Returns:
            User или None если не найден
        """
        clean_username = username.lstrip('@')
        user = self.user_repo.get_by_username(clean_username)

        if not user:
            # Попробуем найти по first_name
            users = self.user_repo.search_by_name(clean_username)
            if users:
                user = users[0]

        return user

    def update_balance(self, user_id: int, amount: float) -> Optional[User]:
        """
        Обновление баланса пользователя.

        Args:
            user_id: ID пользователя
            amount: Сумма для добавления (может быть отрицательной)

        Returns:
            Обновленный User или None при ошибке
        """
        user = self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return None

        user.balance = int(user.balance + amount)
        self.user_repo.session.commit()
        self.user_repo.session.refresh(user)

        return user

    def set_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """
        Установка статуса администратора для пользователя.

        Args:
            user_id: ID пользователя
            is_admin: Статус администратора

        Returns:
            True если статус обновлен успешно
        """
        user = self.user_repo.get_by_telegram_id(user_id)
        if not user:
            return False

        user.is_admin = is_admin
        self.user_repo.session.commit()
        self.user_repo.session.refresh(user)

        return True

    def get_users_count(self) -> int:
        """
        Получение общего количества пользователей.

        Returns:
            Количество пользователей
        """
        return self.user_repo.session.query(User).count()
