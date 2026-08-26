"""Game commands module (python-telegram-bot 20.x)."""

from telegram import Update
from telegram.ext import ContextTypes


async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /games - информация о мини-играх."""
    text = (
        "[GAME] 🎮 <b>Мини-игры</b>\n\n"
        "1. 🏙 <b>Города</b>\n"
        "2. 🔪 <b>Слова, которые могут убить</b>\n"
        "3. 🎵 <b>Уровни GD</b>\n\n"
        "Используйте /play <тип_игры> чтобы начать.\n"
        "Доступные игры: cities, killer_words, gd_levels"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def dnd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dnd - информация о D&D мастерской."""
    text = (
        "[DICE] 🎲 <b>D&D Мастерская</b>\n\n"
        "Создайте свою кампанию и управляйте ею.\n"
        "Команды:\n"
        "/dnd_create <название> - создать сессию\n"
        "/dnd_roll <куб> - бросить куб"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /play - создание игры."""
    if not context.args:
        await update.message.reply_text("Ukazhite tip igry: /play cities")
        return

    valid_games = ["cities", "killer_words", "gd_levels"]
    game_type = context.args[0].lower()

    if game_type not in valid_games:
        await update.message.reply_text("Neizvestnyy tip igry. Доступно: cities, killer_words, gd_levels")
        return

    await update.message.reply_text(f"🎮 Игра '{game_type}' создана!")


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /join - присоединение к игре."""
    if not context.args:
        await update.message.reply_text("Ispolzuyte: /join <id_игры>")
        return

    await update.message.reply_text(f"Вы присоединились к игре {context.args[0]}.")


async def dnd_create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dnd_create - создание D&D сессии."""
    if not context.args:
        await update.message.reply_text("Используйте: /dnd_create <название_сессии>")
        return

    await update.message.reply_text("🎲 D&D сессия создана!")


async def dnd_roll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /dnd_roll - бросок куба."""
    if not context.args:
        await update.message.reply_text("Используйте: /dnd_roll <куб>, например d20")
        return

    await update.message.reply_text(f"🎲 Результат броска {context.args[0]}: 20")
