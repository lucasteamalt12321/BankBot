"""User repository for specialized user data access operations."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from src.repository.base import BaseRepository
from database.database import User


class UserRepository(BaseRepository[User]):
    """
    Repository for User model with specialized query methods.

    Extends BaseRepository to provide user-specific data access operations
    such as finding users by Telegram ID, username, or creating users
    with get-or-create pattern.

    Example:
        >>> from database.database import SessionLocal
        >>> session = SessionLocal()
        >>> user_repo = UserRepository(session)
        >>> user = user_repo.get_by_telegram_id(123456789)
    """

    def __init__(self, session: Session):
        """
        Инициализация репозитория пользователей.

        Args:
            session: SQLAlchemy сессия
        """
        super().__init__(User, session)

    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get a user by their Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User instance if found, None otherwise
        """
        return self.get_by(telegram_id=telegram_id)

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by their username.

        Args:
            username: Username to search for

        Returns:
            User instance if found, None otherwise
        """
        return self.get_by(username=username)

    def get_or_create(self, telegram_id: int, **kwargs) -> User:
        """
        Get an existing user by Telegram ID or create a new one.

        Args:
            telegram_id: Telegram user ID (required)
            **kwargs: Additional fields for user creation

        Returns:
            Existing or newly created User instance
        """
        user = self.get_by_telegram_id(telegram_id)
        if not user:
            user = self.create(telegram_id=telegram_id, **kwargs)
        return user

    def search_by_name(self, name: str) -> List[User]:
        """
        Find users by name (partial match on first_name or username).

        Args:
            name: Name to search for

        Returns:
            List of matching users
        """
        return self.session.query(User).filter(
            User.first_name.contains(name) | User.username.contains(name)
        ).all()

    def get_all_admins(self) -> List[User]:
        """
        Get all users with admin privileges.

        Returns:
            List of User instances with is_admin=True
        """
        return self.get_all_by(is_admin=True)

    def get_all_vips(self) -> List[User]:
        """
        Get all users with active VIP status.

        Returns:
            List of User instances with is_vip=True
        """
        return self.get_all_by(is_vip=True)

    def get_users_with_balance_above(self, min_balance: int) -> List[User]:
        """
        Get all users with balance >= specified amount.

        Args:
            min_balance: Minimum balance threshold

        Returns:
            List of matching User instances
        """
        return self.session.query(User).filter(
            User.balance >= min_balance
        ).all()

    def get_active_users_since(self, since_datetime: datetime) -> List[User]:
        """
        Get all users who were active since the specified datetime.

        Args:
            since_datetime: Datetime threshold for last activity

        Returns:
            List of matching User instances
        """
        return self.session.query(User).filter(
            User.last_activity >= since_datetime
        ).all()

    def get_users_with_expired_vip(self, current_time: datetime) -> List[User]:
        """
        Get all users with expired VIP status.

        Args:
            current_time: Current datetime to compare against vip_until

        Returns:
            List of User instances with is_vip=True and vip_until <= current_time
        """
        return self.session.query(User).filter(
            User.is_vip,
            User.vip_until <= current_time
        ).all()

    def get_users_with_expired_stickers(self, current_time: datetime) -> List[User]:
        """
        Get all users with expired unlimited sticker access.

        Args:
            current_time: Current datetime to compare against sticker_unlimited_until

        Returns:
            List of matching User instances
        """
        return self.session.query(User).filter(
            User.sticker_unlimited,
            User.sticker_unlimited_until <= current_time
        ).all()

    def get_top_users_by_balance(self, limit: int = 10) -> List[User]:
        """
        Get top users ordered by balance (highest first).

        Args:
            limit: Maximum number of users to return

        Returns:
            List of User instances ordered by balance descending
        """
        return self.session.query(User).order_by(
            User.balance.desc()
        ).limit(limit).all()

    def get_top_users_by_earnings(self, limit: int = 10) -> List[User]:
        """
        Get top users ordered by total earnings (highest first).

        Args:
            limit: Maximum number of users to return

        Returns:
            List of User instances ordered by total_earned descending
        """
        return self.session.query(User).order_by(
            User.total_earned.desc()
        ).limit(limit).all()

    def count_total_users(self) -> int:
        """Get total count of all users."""
        return self.count()

    def count_admins(self) -> int:
        """Get count of admin users."""
        return self.count(is_admin=True)

    def count_vips(self) -> int:
        """Get count of VIP users."""
        return self.count(is_vip=True)

    def bulk_update_balance(self, user_ids: list, amount: int) -> int:
        """
        Update balance for multiple users at once.

        Args:
            user_ids: List of user IDs to update
            amount: Amount to add to each user's balance (can be negative)

        Returns:
            Number of users updated
        """
        count = self.session.query(User).filter(
            User.id.in_(user_ids)
        ).update(
            {User.balance: User.balance + amount},
            synchronize_session=False
        )
        self.session.commit()
        return count
