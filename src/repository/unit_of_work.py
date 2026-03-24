"""Unit of Work pattern for atomic database transactions."""

from __future__ import annotations
from typing import Optional
import structlog
from sqlalchemy.orm import Session
from database.database import SessionLocal
from src.repository.user_repository import UserRepository

logger = structlog.get_logger()


class UnitOfWork:
    """
    Unit of Work pattern — управляет транзакцией как единым атомарным блоком.

    Гарантирует, что все операции в рамках одного контекста либо
    фиксируются вместе, либо откатываются при ошибке.

    Example:
        >>> async with UnitOfWork() as uow:
        ...     user = uow.users.get_by_telegram_id(123)
        ...     user.balance += 100
        ...     await uow.commit()
    """

    def __init__(self, session_factory=None):
        """
        Args:
            session_factory: Фабрика сессий SQLAlchemy (по умолчанию SessionLocal)
        """
        self._session_factory = session_factory or SessionLocal
        self.session: Optional[Session] = None
        self.users: Optional[UserRepository] = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.users = UserRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
            logger.warning(
                "UnitOfWork rolled back due to exception",
                exc_type=exc_type.__name__ if exc_type else None,
                exc_val=str(exc_val),
            )
        self._close()
        return False  # не подавляем исключение

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
        if self.session:
            self.session.rollback()
            logger.debug("UnitOfWork rolled back")

    def _close(self):
        if self.session:
            self.session.close()
            self.session = None
