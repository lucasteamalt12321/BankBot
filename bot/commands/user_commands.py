"""User commands for python-telegram-bot 20.x."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.dependency_injection import build_services

logger = structlog.get_logger()


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile — профиль пользователя."""
    with build_services() as svc:
        user = svc.user_service.get_user_by_telegram_id(update.effective_user.id)

        if not user:
            await update.message.reply_text("👤 Пользователь не найден. Используйте /start.")
            return

        text = (
            f"👤 <b>Профиль пользователя</b>\n\n"
            f"🆔 <b>ID:</b> {user.id}\n"
            f"👤 <b>Имя:</b> {user.first_name or 'Не указано'}\n"
            f"📝 <b>Username:</b> @{user.username or 'Не указан'}\n"
            f"📅 <b>Регистрация:</b> {user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'Неизвестно'}\n\n"
            f"💰 <b>Финансы:</b>\n"
            f"   • Баланс: {user.balance} очков\n"
            f"   • Заработано: {user.total_earned} очков\n"
            f"   • Покупок: {user.total_purchases}\n\n"
            f"🏆 <b>Статус:</b>\n"
            f"   • Дневная серия: {user.daily_streak} дней\n"
            f"   • VIP: {'✅' if user.is_vip else '❌'}"
        )
        await update.message.reply_text(text, parse_mode="HTML")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /balance — баланс пользователя."""
    with build_services() as svc:
        user = svc.user_service.get_user_by_telegram_id(update.effective_user.id)

        if not user:
            await update.message.reply_text("💰 Пользователь не найден. Используйте /start.")
            return

        await update.message.reply_text(f"💰 Ваш баланс: <b>{user.balance}</b> очков", parse_mode="HTML")
