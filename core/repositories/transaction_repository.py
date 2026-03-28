"""Transaction repository — parameterized queries for transaction history."""

from typing import List, Optional

from sqlalchemy.orm import Session

from database.database import Transaction

from .base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for transaction records. All queries are parameterized."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with SQLAlchemy session.

        Args:
            session: Active SQLAlchemy session.
        """
        super().__init__(session)

    def get(self, id: int) -> Optional[Transaction]:
        """Get transaction by primary key.

        Args:
            id: Transaction primary key.

        Returns:
            Transaction instance or None.
        """
        return self.session.query(Transaction).filter(Transaction.id == id).first()

    def get_all(self) -> List[Transaction]:
        """Get all transactions.

        Returns:
            List of all Transaction instances.
        """
        return self.session.query(Transaction).all()

    def create(self, entity: Transaction) -> Transaction:
        """Add a new transaction to the session.

        Args:
            entity: Transaction instance to persist.

        Returns:
            The same Transaction instance (pending flush).
        """
        self.session.add(entity)
        return entity

    def update(self, entity: Transaction) -> Transaction:
        """Merge a detached transaction instance into the session.

        Args:
            entity: Transaction instance with updated fields.

        Returns:
            Merged Transaction instance.
        """
        self.session.merge(entity)
        return entity

    def delete(self, id: int) -> bool:
        """Delete transaction by primary key.

        Args:
            id: Transaction primary key.

        Returns:
            True if deleted, False if not found.
        """
        tx = self.get(id)
        if tx:
            self.session.delete(tx)
            return True
        return False

    def get_by_user(self, user_id: int, limit: int = 20) -> List[Transaction]:
        """Get recent transactions for a user (parameterized).

        Args:
            user_id: User primary key.
            limit: Max number of records to return.

        Returns:
            List of Transaction ordered by id desc.
        """
        return (
            self.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.id.desc())
            .limit(limit)
            .all()
        )

    def log_transaction(
        self,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: str,
        source_game: Optional[str] = None,
    ) -> Transaction:
        """Create and persist a transaction record.

        Args:
            user_id: User primary key.
            amount: Transaction amount.
            transaction_type: Type label (e.g. 'accrual', 'purchase').
            description: Human-readable description.
            source_game: Optional game source identifier.

        Returns:
            Persisted Transaction instance.
        """
        tx = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            source_game=source_game,
        )
        self.session.add(tx)
        return tx
