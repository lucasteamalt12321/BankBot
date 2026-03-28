"""Централизованная обработка ошибок для aiogram (BaseMiddleware).

Перехватывает все необработанные исключения в Handler-ах,
логирует с полным stack trace, уведомляет администратора
(с дедупликацией) и отправляет пользователю нейтральное сообщение.

Требования: BB-5
"""

from __future__ import annotations

import logging
import time
import traceback
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)

# Дедупликация: хранит timestamp последней отправки уведомления по типу исключения
_last_admin_notify: dict[str, float] = defaultdict(float)
ADMIN_NOTIFY_COOLDOWN = 60.0  # секунд


def _should_notify_admin(exc_key: str) -> bool:
    """Проверяет, прошло ли достаточно времени для повторного уведомления.

    Args:
        exc_key: Уникальный ключ типа исключения (имя класса).

    Returns:
        True если уведомление нужно отправить.
    """
    now = time.monotonic()
    if now - _last_admin_notify[exc_key] >= ADMIN_NOTIFY_COOLDOWN:
        _last_admin_notify[exc_key] = now
        return True
    return False


def _get_chat_id(event: TelegramObject) -> int | None:
    """Извлекает chat_id из события aiogram.

    Args:
        event: Telegram-событие (Message, CallbackQuery и др.).

    Returns:
        chat_id или None если не удалось извлечь.
    """
    if isinstance(event, Message):
        return event.chat.id
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.chat.id
    return None


def _get_user_info(event: TelegramObject) -> str:
    """Формирует строку с информацией о пользователе.

    Args:
        event: Telegram-событие.

    Returns:
        Строка вида '@username (id)' или 'неизвестен'.
    """
    user = None
    if isinstance(event, Message):
        user = event.from_user
    elif isinstance(event, CallbackQuery):
        user = event.from_user

    if user:
        username = f"@{user.username}" if user.username else f"id={user.id}"
        return f"{username} ({user.id})"
    return "неизвестен"


class ErrorHandlingMiddleware(BaseMiddleware):
    """aiogram middleware для централизованной обработки ошибок.

    Перехватывает все необработанные исключения в Handler-ах,
    логирует с полным stack trace, уведомляет администратора
    (дедупликация: не чаще раза в 60 сек для одного типа исключения)
    и отправляет пользователю нейтральное сообщение.

    Attributes:
        admin_chat_id: Telegram ID чата администратора для уведомлений.
    """

    def __init__(self, admin_chat_id: int | None = None) -> None:
        """Инициализирует middleware.

        Args:
            admin_chat_id: Telegram ID чата администратора.
                           Если None — уведомления администратору не отправляются.
        """
        super().__init__()
        self.admin_chat_id = admin_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Выполняет handler с перехватом исключений.

        Args:
            handler: Следующий handler в цепочке.
            event: Telegram-событие.
            data: Контекстные данные aiogram.

        Returns:
            Результат handler или None при ошибке.
        """
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.exception(
                "Необработанное исключение в handler: %s — %s",
                type(exc).__name__,
                exc,
            )

            bot = data.get("bot")
            if bot is None:
                logger.warning("bot не найден в data, уведомления не отправлены")
                return None

            # Уведомляем пользователя нейтральным сообщением
            chat_id = _get_chat_id(event)
            if chat_id is not None:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="❌ Произошла ошибка. Попробуйте позже.",
                    )
                except Exception as send_err:
                    logger.error("Не удалось отправить сообщение пользователю: %s", send_err)

            # Уведомляем администратора с дедупликацией
            if self.admin_chat_id and _should_notify_admin(type(exc).__name__):
                await self._notify_admin(bot, exc, event)

            return None

    async def _notify_admin(
        self,
        bot: Any,
        exc: Exception,
        event: TelegramObject,
    ) -> None:
        """Отправляет уведомление об ошибке администратору.

        Args:
            bot: aiogram Bot instance.
            exc: Перехваченное исключение.
            event: Telegram-событие, в котором произошла ошибка.
        """
        exc_type = type(exc).__name__
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if len(tb) > 3500:
            tb = tb[:3500] + "\n... (обрезано)"

        user_info = _get_user_info(event)

        text = (
            f"⚠️ <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
            f"<b>Тип:</b> <code>{exc_type}</code>\n"
            f"<b>Сообщение:</b> <code>{str(exc)[:200]}</code>\n"
            f"<b>Пользователь:</b> {user_info}\n\n"
            f"<pre>{tb}</pre>"
        )

        try:
            await bot.send_message(
                chat_id=self.admin_chat_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception as notify_err:
            logger.error("Не удалось уведомить администратора: %s", notify_err)
