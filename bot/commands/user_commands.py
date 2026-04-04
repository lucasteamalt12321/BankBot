"""User commands for python-telegram-bot 20.x."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.dependency_injection import build_services
from bot.commands.shop_commands_ptb import _handle_purchase_command
from utils.admin.admin_middleware import auto_registration_middleware
from database.database import get_db

logger = structlog.get_logger()


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile — профиль пользователя."""
    with build_services() as svc:
        user = svc.user_service.get_user_by_telegram_id(update.effective_user.id)

        if not user:
            await update.message.reply_text(
                "👤 Пользователь не найден. Используйте /start."
            )
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
            await update.message.reply_text(
                "💰 Пользователь не найден. Используйте /start."
            )
            return

        await update.message.reply_text(
            f"💰 Ваш баланс: <b>{user.balance}</b> очков", parse_mode="HTML"
        )


# Buy commands - extracted from bot/bot.py
async def buy_1_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 1, auto_registration_middleware, get_db
    )


async def buy_2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 2, auto_registration_middleware, get_db
    )


async def buy_3_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 3, auto_registration_middleware, get_db
    )


async def buy_4_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 4, auto_registration_middleware, get_db
    )


async def buy_5_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 5, auto_registration_middleware, get_db
    )


async def buy_6_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 6, auto_registration_middleware, get_db
    )


async def buy_7_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 7, auto_registration_middleware, get_db
    )


async def buy_8_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_purchase_command(
        update, context, 8, auto_registration_middleware, get_db
    )
