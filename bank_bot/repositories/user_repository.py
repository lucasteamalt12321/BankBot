"""User repository implementation with balance locking."""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.database import User, BotBalance
from .base import BaseRepository

class UserRepository(BaseRepository[User]):
    """Repository for user-related operations with balance management."""

    def __init__(self, session: Session):
        super().__init__(session)
        self.model = User

    def get(self, id: int) -> Optional[User]:
        """Get user by ID (internal database ID)."""
        return self.session.query(self.model).filter(self.model.id == id).first()

    def get_all(self) -> List[User]:
        """Get all users."""
        return self.session.query(self.model).all()

    def create(self, entity: User) -> User:
        """Create new user."""
        self.session.add(entity)
        return entity

    def update(self, entity: User) -> User:
        """Update existing user."""
        self.session.merge(entity)
        return entity

    def delete(self, id: int) -> bool:
        """Delete user by ID."""
        user = self.get(id)
        if user:
            self.session.delete(user)
            return True
        return False

    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return self.session.query(self.model).filter(
            self.model.telegram_id == telegram_id
        ).first()

    def get_or_create_by_name(self, username: str) -> User:
        """Get existing user or create new one by username."""
        user = self.session.query(self.model).filter(
            self.model.username == username
        ).first()

        if not user:
            user = User(username=username, balance=0)
            self.session.add(user)
            self.session.flush()  # Get the ID without committing

        return user

    def update_balance_with_lock(self, user_id: int, amount: int) -> Optional[User]:
        """
        Update user balance with row-level locking to prevent race conditions.
        
        Args:
            user_id: User ID
            amount: Amount to add to balance (can be negative)
            
        Returns:
            Updated user or None if user not found
        """
        # Use SELECT FOR UPDATE to lock the row
        user = self.session.query(self.model).filter(
            self.model.id == user_id
        ).with_for_update().first()

        if user:
            user.balance += amount
            user.total_earned += max(0, amount)  # Only count positive amounts
            return user

        return None

    def get_bot_balance(self, user_id: int, game: str) -> Optional[BotBalance]:
        """Get bot balance for user and game."""
        return self.session.query(BotBalance).filter(
            BotBalance.user_id == user_id,
            BotBalance.game == game
        ).first()

    def create_or_update_bot_balance(
        self, 
        user_id: int, 
        game: str, 
        last_balance: float = 0.0,
        current_bot_balance: float = 0.0
    ) -> BotBalance:
        """
        Create or update bot balance record.
        
        Args:
            user_id: User ID
            game: Game name
            last_balance: Last known balance from profile
            current_bot_balance: Current accumulated bot balance
            
        Returns:
            BotBalance instance
        """
        bot_balance = self.get_bot_balance(user_id, game)

        if bot_balance:
            bot_balance.last_balance = last_balance
            bot_balance.current_bot_balance = current_bot_balance
            bot_balance.last_updated = func.now()
        else:
            bot_balance = BotBalance(
                user_id=user_id,
                game=game,
                last_balance=last_balance,
                current_bot_balance=current_bot_balance
            )
            self.session.add(bot_balance)

        return bot_balance
