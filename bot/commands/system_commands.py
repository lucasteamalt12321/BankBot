"""System commands module (python-telegram-bot 20.x)."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    await update.message.reply_text("🤖 Добро пожаловать в LucasTeam Bank Bot!")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - справка по командам."""
    user = update.effective_user
    text = (
        "📋 <b>Справка по командам</b>\n\n"
        "/start - начать работу\n"
        "/help - эта справка\n"
        "/profile - ваш профиль\n"
        "/shop - магазин товаров\n"
        "/games - мини-игры"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    logger.info(f"Help command accessed by user {user.id}")


async def beta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /beta - бета-функции."""
    user = update.effective_user
    text = (
        "🧪 <b>Бета-функции</b>\n\n"
        "Экспериментальные команды:\n"
        "/market - рыночные котировки\n"
        "/quests - квесты\n"
        "/leaderboard - таблица лидеров"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    logger.info(f"Beta command accessed by user {user.id}")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /about - информация о боте."""
    user = update.effective_user
    text = (
        "ℹ️ <b>О боте</b>\n\n"
        "LucasTeam Bank — бот лояльности.\n"
        "Проекты: Shmalala, GD Cards, True Mafia, Bunker RP."
    )
    await update.message.reply_text(text, parse_mode="HTML")
    logger.info(f"About command accessed by user {user.id}")
