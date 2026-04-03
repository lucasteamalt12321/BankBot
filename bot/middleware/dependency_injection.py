"""
Dependency Injection для python-telegram-bot 20.x.

PTB не имеет middleware в aiogram-стиле. DI реализован через:
- ServiceContainer — создаёт сервисы per-request из сессии БД
- get_services() — хелпер для получения сервисов внутри handler
- setup_di() — регистрирует post_init хук в Application

Использование в handler:
    async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        services = get_services(context)
        user = services.user_service.get_user_by_telegram_id(update.effective_user.id)
"""

from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

import structlog
from sqlalchemy.orm import Session
from telegram.ext import ContextTypes

from database.database import SessionLocal
from src.repository.user_repository import UserRepository
from core.services.user_service import UserService
from core.services.admin_service import AdminService
from core.services.shop_service import ShopService
from core.services.transaction_service import TransactionService

logger = structlog.get_logger()

_DI_KEY = "services_factory"


@dataclass
class Services:
    """Контейнер сервисов для одного запроса."""

    session: Session
    user_repo: UserRepository
    user_service: UserService
    admin_service: AdminService
    shop_service: ShopService
    transaction_service: TransactionService

    def close(self) -> None:
        """Закрывает сессию БД."""
        self.session.close()


@contextmanager
def build_services() -> Generator[Services, None, None]:
    """
    Контекстный менеджер: создаёт сервисы и закрывает сессию после использования.

    Example:
        with build_services() as svc:
            user = svc.user_service.get_user_by_telegram_id(123)
    """
    session: Session = SessionLocal()
    try:
        user_repo = UserRepository(session)
        services = Services(
            session=session,
            user_repo=user_repo,
            user_service=UserService(user_repo),
            admin_service=AdminService(user_repo),
            shop_service=ShopService(user_repo),
            transaction_service=TransactionService(user_repo),
        )
        yield services
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_services(context: ContextTypes.DEFAULT_TYPE) -> Services:
    """
    Возвращает Services из context.bot_data (per-request фабрика).

    Если сервисы ещё не созданы для этого запроса — создаёт новые.
    Сессия закрывается вручную или через close_services().

    Args:
        context: PTB контекст

    Returns:
        Services с открытой сессией БД
    """
    if _DI_KEY not in context.chat_data:
        session: Session = SessionLocal()
        user_repo = UserRepository(session)
        context.chat_data[_DI_KEY] = Services(
            session=session,
            user_repo=user_repo,
            user_service=UserService(user_repo),
            admin_service=AdminService(user_repo),
            shop_service=ShopService(user_repo),
            transaction_service=TransactionService(user_repo),
        )
    return context.chat_data[_DI_KEY]


def close_services(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Закрывает сессию и удаляет сервисы из context."""
    svc = context.chat_data.pop(_DI_KEY, None)
    if svc:
        svc.close()


def setup_di(application) -> None:
    """
    Регистрирует хуки DI в PTB Application.

    Добавляет TypeHandler для автоматического закрытия сессий
    после каждого обработанного обновления.

    Args:
        application: PTB Application instance
    """
    from telegram import Update
    from telegram.ext import TypeHandler

    async def _cleanup_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        close_services(context)

    # Группа 999 — выполняется после всех handlers
    application.add_handler(TypeHandler(Update, _cleanup_session), group=999)
    logger.info("DI session cleanup handler registered")
