"""Unit of Work pattern for atomic database transactions."""

from __future__ import annotations
import structlog
from sqlalchemy.orm import Session
from database.database import SessionLocal
from core.repositories.user_repository import UserRepository

logger = structlog.get_logger()


class UnitOfWork:
    """
    Unit of Work pattern — управляет транзакцией как единым атомарным блоком.

    Гарантирует, что все операции в рамках одного контекста либо
    фиксируются вместе, либо откатываются при ошибке.

    Example:
        >>> with UnitOfWork() as uow:
        ...     user = uow.users.get_by_telegram_id(123)
        ...     user.balance += 100
        ...     uow.commit()
    """

    def __init__(self, session_factory=None):
        """
        Args:
            session_factory: Фабрика сессий SQLAlchemy (по умолчанию SessionLocal)
        """
        self._session_factory = session_factory or SessionLocal
        self._session: Session | None = None
        self._users: UserRepository | None = None

    def __enter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        self._users = UserRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
            logger.warning(
                "UnitOfWork rolled back due to exception",
                exc_type=exc_type.__name__ if exc_type else None,
                exc_val=str(exc_val),
            )
        else:
            # Only close if no exception occurred
            self._close()
        return False  # не подавляем исключение

    @property
    def session(self) -> Session:
        """Get the current session or raise an error if not available."""
        if self._session is None:
            raise RuntimeError("No active session. Use UnitOfWork in a context manager.")
        return self._session

    @property
    def users(self) -> UserRepository:
        """Get the user repository or raise an error if not available."""
        if self._users is None:
            raise RuntimeError("No active user repository. Use UnitOfWork in a context manager.")
        return self._users

    def commit(self):
        """Зафиксировать все изменения текущей транзакции."""
        try:
            self.session.commit()
            logger.debug("UnitOfWork committed")
        except Exception:
            self.rollback()
            raise

    def rollback(self):
        """Откатить все изменения текущей транзакции."""
        if self._session is not None:
            self._session.rollback()
            logger.debug("UnitOfWork rolled back")

    def _close(self):
        if self._session is not None:
            self._session.close()
            self._session = None
