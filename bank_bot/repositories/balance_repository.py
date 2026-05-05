"""Balance repository — manages user balance operations with row-level locking."""

from typing import Optional

from sqlalchemy.orm import Session

from database.database import User

from .base import BaseRepository


class BalanceRepository(BaseRepository[User]):
    """Repository for balance-related operations with locking support."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with SQLAlchemy session.

        Args:
            session: Active SQLAlchemy session.
        """
        super().__init__(session)

    def get(self, id: int) -> Optional[User]:
        """Get user by primary key.

        Args:
            id: User primary key.

        Returns:
            User instance or None.
        """
        return self.session.query(User).filter(User.id == id).first()

    def get_all(self):
        """Get all users.

        Returns:
            List of all User instances.
        """
        return self.session.query(User).all()

    def create(self, entity: User) -> User:
        """Add a new user to the session.

        Args:
            entity: User instance to persist.

        Returns:
            The same User instance (pending flush).
        """
        self.session.add(entity)
        return entity

    def update(self, entity: User) -> User:
        """Merge a detached user instance into the session.

        Args:
            entity: User instance with updated fields.

        Returns:
            Merged User instance.
        """
        self.session.merge(entity)
        return entity

    def delete(self, id: int) -> bool:
        """Delete user by primary key.

        Args:
            id: User primary key.

        Returns:
            True if deleted, False if not found.
        """
        user = self.get(id)
        if user:
            self.session.delete(user)
            return True
        return False

    def get_balance_with_lock(self, user_id: int) -> Optional[User]:
        """Get user with row-level lock for balance update.

        Args:
            user_id: User primary key.

        Returns:
            Locked User row or None.
        """
        return (
            self.session.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )

    def add_balance(self, user_id: int, amount: int) -> Optional[User]:
        """Add amount to user balance atomically (uses row lock).

        Args:
            user_id: User primary key.
            amount: Amount to add (negative to deduct).

        Returns:
            Updated User or None if not found.
        """
        user = self.get_balance_with_lock(user_id)
        if user is None:
            return None
        user.balance += amount
        if amount > 0:
            user.total_earned += amount
        return user
