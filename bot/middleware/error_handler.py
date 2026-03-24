"""
Middleware для обработки ошибок в Telegram-боте.

Этот модуль предоставляет глобальный обработчик ошибок, который:
- Отправляет пользователю дружественное сообщение об ошибке
- Логирует полный стектрейс критических ошибок
- Уведомляет администраторов о критических ошибках
"""

import structlog
import traceback
from typing import Any, Dict, Optional

from aiogram import Bot, BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from src.config import settings

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware для глобальной обработки ошибок в Telegram-боте.
    
    При возникновении ошибки:
    1. Логирует полный стектрейс
    2. Отправляет пользователю понятное сообщение
    3. Уведомляет администраторов о критических ошибках
    """
    
    async def __call__(
        self,
        callback: callable,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработчик ошибок для всех событий.
        
        Args:
            callback: Следующий обработчик в цепочке
            event: Telegram событие (сообщение, колбэк и т.д.)
            data: Данные, переданные в обработчик
            
        Returns:
            Результат выполнения следующего обработчика
        """
        try:
            return await callback(event, data)
        except Exception as e:
            await self._handle_error(e, event, data)
            # Возвращаем None, чтобы остановить цепочку обработки
            return None
    
    async def _handle_error(
        self,
        error: Exception,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> None:
        """
        Обрабатывает ошибку: логирует, уведомляет пользователя и администраторов.
        
        Args:
            error: Возникшее исключение
            event: Telegram событие
            data: Данные обработчика
        """
        # Логируем полный стектрейс
        logger.exception(f"Ошибка при обработке события: {error}")
        
        # Получаем объект бота из данных
        bot = data.get("bot")
        if not bot:
            logger.warning("Не удалось получить объект бота из данных")
            return
        
        # Определяем тип события и отправляем уведомление пользователю
        await self._notify_user(bot, error, event)
        
        # Уведомляем администраторов
        await self._notify_admins(bot, error, event, data)
    
    async def _notify_user(
        self,
        bot: Bot,
        error: Exception,
        event: TelegramObject
    ) -> None:
        """
        Отправляет пользователю дружественное сообщение об ошибке.
        
        Args:
            bot: Объект бота
            error: Возникшее исключение
            event: Telegram событие
        """
        # Определяем chat_id в зависимости от типа события
        chat_id = None
        
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else None
        
        if chat_id:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "❌ Произошла ошибка при обработке вашего запроса.\n"
                        "Мы уже уведомлены и работаем над исправлением.\n"
                        "Пожалуйста, попробуйте позже."
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю: {e}")
    
    async def _notify_admins(
        self,
        bot: Bot,
        error: Exception,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> None:
        """
        Уведомляет администраторов о критической ошибке.
        
        Args:
            bot: Объект бота
            error: Возникшее исключение
            event: Telegram событие
            data: Данные обработчика
        """
        if not settings.ADMIN_TELEGRAM_ID:
            logger.warning("ADMIN_TELEGRAM_ID не настроен, пропускаем уведомление администраторов")
            return
        
        # Формируем сообщение об ошибке
        error_type = type(error).__name__
        error_message = str(error)
        
        # Получаем информацию о пользователе
        user_info = "Неизвестный пользователь"
        if isinstance(event, Message):
            if event.from_user:
                user_info = (
                    f"@{event.from_user.username or 'no_username'} "
                    f"({event.from_user.id})"
                )
        elif isinstance(event, CallbackQuery):
            if event.from_user:
                user_info = (
                    f"@{event.from_user.username or 'no_username'} "
                    f"({event.from_user.id})"
                )
        
        # Получаем текст сообщения (если есть)
        message_text = "Нет текста сообщения"
        if isinstance(event, Message):
            message_text = event.text or event.caption or "Нет текста"
        elif isinstance(event, CallbackQuery):
            message_text = event.data or "Нет данных"
        
        # Формируем полное сообщение
        full_message = (
            f"⚠️ <b>КРИТИЧЕСКАЯ ОШИБКА</b> ⚠️\n\n"
            f"<b>Тип ошибки:</b> <code>{error_type}</code>\n"
            f"<b>Сообщение:</b> <code>{error_message}</code>\n\n"
            f"<b>Пользователь:</b> {user_info}\n"
            f"<b>Сообщение:</b> <code>{message_text[:100]}...</code>\n\n"
            f"<pre>{self._format_traceback(error)}</pre>"
        )
        
        try:
            # Отправляем уведомление администратору
            await bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_ID,
                text=full_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление администратору: {e}")
    
    def _format_traceback(self, error: Exception) -> str:
        """
        Форматирует стектрейс для отправки в Telegram.
        
        Args:
            error: Возникшее исключение
            
        Returns:
            Отформатированный стектрейс
        """
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_lines)
        
        # Ограничиваем длину для Telegram (4096 символов)
        if len(tb_text) > 4000:
            tb_text = tb_text[:4000] + "\n... (стектрейс обрезан)"
        
        return tb_text


# Алиас для удобства
error_handler = ErrorHandlerMiddleware()
