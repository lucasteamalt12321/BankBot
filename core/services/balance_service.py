"""Balance service — business logic for balance accrual and deduction."""

from typing import Optional

from sqlalchemy.orm import Session

from core.repositories.balance_repository import BalanceRepository
from core.repositories.transaction_repository import TransactionRepository
from database.database import User


class BalanceService:
    """Service for balance operations: accrual, deduction, and transaction logging.

    All balance changes are atomic (row-level lock via BalanceRepository).
    Business logic is separated from Telegram API calls.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with SQLAlchemy session.

        Args:
            session: Active SQLAlchemy session.
        """
        self._balance_repo = BalanceRepository(session)
        self._tx_repo = TransactionRepository(session)
        self._session = session

    def accrue(
        self,
        user_id: int,
        amount: int,
        description: str,
        source_game: Optional[str] = None,
    ) -> Optional[User]:
        """Add points to user balance and log the transaction.

        Args:
            user_id: User primary key.
            amount: Positive amount to add.
            description: Human-readable reason.
            source_game: Optional game source identifier.

        Returns:
            Updated User or None if user not found.

        Raises:
            ValueError: If amount is not positive.
        """
        if amount <= 0:
            raise ValueError(f"Accrual amount must be positive, got {amount}")
        user = self._balance_repo.add_balance(user_id, amount)
        if user is None:
            return None
        self._tx_repo.log_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type="accrual",
            description=description,
            source_game=source_game,
        )
        return user

    def deduct(
        self,
        user_id: int,
        amount: int,
        description: str,
        source_game: Optional[str] = None,
    ) -> Optional[User]:
        """Deduct points from user balance and log the transaction.

        Args:
            user_id: User primary key.
            amount: Positive amount to deduct.
            description: Human-readable reason.
            source_game: Optional game source identifier.

        Returns:
            Updated User or None if user not found.

        Raises:
            ValueError: If amount is not positive or balance insufficient.
        """
        if amount <= 0:
            raise ValueError(f"Deduction amount must be positive, got {amount}")
        user = self._balance_repo.get_balance_with_lock(user_id)
        if user is None:
            return None
        if user.balance < amount:
            raise ValueError(
                f"Insufficient balance: user {user_id} has {user.balance}, "
                f"needs {amount}"
            )
        user.balance -= amount
        self._tx_repo.log_transaction(
            user_id=user_id,
            amount=-amount,
            transaction_type="deduction",
            description=description,
            source_game=source_game,
        )
        return user

    def get_balance(self, user_id: int) -> Optional[int]:
        """Get current balance for a user.

        Args:
            user_id: User primary key.

        Returns:
            Current balance or None if user not found.
        """
        user = self._balance_repo.get(user_id)
        return user.balance if user else None
