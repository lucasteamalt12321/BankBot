"""Unit of Work pattern for atomic database transactions."""

from __future__ import annotations
import functools
import structlog
from contextlib import contextmanager
from typing import Generator, Optional, Callable, Any, TYPE_CHECKING
from sqlalchemy.orm import Session
from database.database import SessionLocal

if TYPE_CHECKING:
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

    def __init__(self, session_factory=None, session: Optional[Session] = None):
        """
        Args:
            session_factory: Фабрика сессий SQLAlchemy (по умолчанию SessionLocal)
            session: Готовая сессия (если передана, session_factory игнорируется)
        """
        self._session_factory = session_factory or SessionLocal
        self._provided_session = session
        self._session: Optional[Session] = session
        self._users: Optional[UserRepository] = None
        self._rolled_back = False

    def __enter__(self) -> "UnitOfWork":
        if self._provided_session is None:
            self._session = self._session_factory()
        from core.repositories.user_repository import UserRepository as _UserRepository
        self._users = _UserRepository(self._session)
        self._rolled_back = False
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
            # Commit changes regardless of whether session was provided or created
            if not self._rolled_back:
                try:
                    self.session.commit()
                except Exception:
                    self.rollback()
                    raise
            if self._provided_session is None:
                self._close()
        return False  # не подавляем исключение

    @property
    def session(self) -> Session:
        """Get the current session or raise an error if not available."""
        if self._session is None:
            raise RuntimeError("No active session. Use UnitOfWork in a context manager.")
        return self._session

    @property
    def users(self) -> "UserRepository":
        """Get the user repository or raise an error if not available."""
        if self._users is None:
            raise RuntimeError("No active user repository. Use UnitOfWork in a context manager.")
        return self._users

    def commit(self):
        """Зафиксировать все изменения текущей транзакции."""
        if self._rolled_back:
            raise RuntimeError("Cannot commit after rollback")
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
            self._rolled_back = True
            logger.debug("UnitOfWork rolled back")

    def flush(self):
        """Сбросить изменения в БД без коммита."""
        self.session.flush()

    def _close(self):
        if self._session is not None:
            self._session.close()
            self._session = None


@contextmanager
def transaction(session_factory=None, session: Optional[Session] = None) -> Generator[Session, None, None]:
    """
    Контекстный менеджер для атомарной транзакции.

    Если передана session — использует её напрямую.
    Иначе создаёт новую сессию через session_factory.

    Example:
        >>> with transaction() as session:
        ...     session.add(user)
    """
    if session is not None:
        # Используем переданную сессию
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
    else:
        factory = session_factory or SessionLocal
        sess = factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()


@contextmanager
def nested_transaction(session: Session) -> Generator[Session, None, None]:
    """
    Контекстный менеджер для вложенной транзакции (savepoint).

    Args:
        session: Активная SQLAlchemy сессия

    Example:
        >>> with transaction(session=session):
        ...     with nested_transaction(session):
        ...         session.add(user)
    """
    savepoint = session.begin_nested()
    try:
        yield session
        savepoint.commit()
    except Exception:
        savepoint.rollback()
        raise


def atomic(func: Callable) -> Callable:
    """
    Декоратор для оборачивания функции в транзакцию.

    Если функция принимает аргумент `session` — использует его.
    Иначе создаёт новую сессию.

    Example:
        >>> @atomic
        ... def create_user(session, telegram_id, username):
        ...     user = User(telegram_id=telegram_id, username=username)
        ...     session.add(user)
        ...     return user
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = kwargs.get('session')
        if session is not None:
            # Используем переданную сессию без управления транзакцией
            return func(*args, **kwargs)
        else:
            # Создаём новую сессию и управляем транзакцией
            sess = SessionLocal()
            try:
                kwargs['session'] = sess
                result = func(*args, **kwargs)
                sess.commit()
                return result
            except Exception:
                sess.rollback()
                raise
            finally:
                sess.close()
    return wrapper


class TransactionManager:
    """
    Менеджер транзакций с поддержкой вложенных транзакций через savepoints.

    Example:
        >>> tm = TransactionManager(session=session)
        >>> with tm:
        ...     user.balance = 100
    """

    def __init__(self, session_factory=None, session: Optional[Session] = None):
        """
        Args:
            session_factory: Фабрика сессий
            session: Готовая сессия
        """
        self._session_factory = session_factory or SessionLocal
        self._provided_session = session
        self._session: Optional[Session] = session
        self._savepoint = None

    def __enter__(self) -> "TransactionManager":
        if self._provided_session is None:
            self._session = self._session_factory()
        else:
            # Вложенная транзакция через savepoint
            try:
                self._savepoint = self._session.begin_nested()
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            if self._savepoint:
                self._savepoint.rollback()
            elif self._session:
                self._session.rollback()
        else:
            if self._savepoint:
                self._savepoint.commit()
            elif self._provided_session is None and self._session:
                self._session.commit()
                self._session.close()
        return False

    def begin(self):
        """Явно начать транзакцию."""
        if self._session is None:
            self._session = self._session_factory()

    def commit(self):
        """Зафиксировать транзакцию."""
        if self._session:
            self._session.commit()

    def rollback(self):
        """Откатить транзакцию."""
        if self._session:
            self._session.rollback()
