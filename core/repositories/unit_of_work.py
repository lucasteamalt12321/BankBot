"""Unit of Work pattern for atomic balance transactions."""

from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

import structlog
from sqlalchemy.orm import Session

from core.repositories.balance_repository import BalanceRepository
from core.repositories.transaction_repository import TransactionRepository
from database.database import SessionLocal

logger = structlog.get_logger()


class UnitOfWork:
    """Context manager that wraps balance operations in a single DB transaction.

    Usage:
        with UnitOfWork() as uow:
            user = uow.balances.add_balance(user_id, amount)
            uow.transactions.log_transaction(user_id, amount, "accrual", "Game reward")
            uow.commit()

    On exception, the transaction is automatically rolled back.
    """

    def __init__(self, session_factory=None) -> None:
        """Initialize UnitOfWork.

        Args:
            session_factory: Callable that returns a new Session.
                             Defaults to SessionLocal.
        """
        self._session_factory = session_factory or SessionLocal
        self.session: Optional[Session] = None
        self.balances: Optional[BalanceRepository] = None
        self.transactions: Optional[TransactionRepository] = None

    def __enter__(self) -> "UnitOfWork":
        """Open session and initialize repositories.

        Returns:
            Self reference for use in with-statement.
        """
        self.session = self._session_factory()
        self.balances = BalanceRepository(self.session)
        self.transactions = TransactionRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Rollback on exception, always close session.

        Args:
            exc_type: Exception type, if any.
            exc_val: Exception value, if any.
            exc_tb: Exception traceback, if any.
        """
        if exc_type is not None:
            self.rollback()
            logger.warning(
                "UnitOfWork rolled back due to exception",
                exc_type=exc_type.__name__,
                exc_val=str(exc_val),
            )
        if self.session:
            self.session.close()

    def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            RuntimeError: If session is not open.
            Exception: Re-raises any DB error after rolling back.
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork session is not open")
        try:
            self.session.commit()
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        """Roll back the current transaction."""
        if self.session is not None:
            self.session.rollback()
