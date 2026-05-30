"""
Geometry Dash API commands for python-telegram-bot.

Commands:
- /gd_user <username> - Get GD player statistics
- /gd_level <level_id> - Get GD level information
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.gd.gd_api import get_user_info, get_level_info, format_user_stats, format_level_info

logger = logging.getLogger(__name__)


async def gd_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /gd_user command.
    
    Usage: /gd_user <username>
    
    Fetches and displays GD player statistics from official servers.
    """
    if not update.message or not context.args:
        await update.message.reply_text(
            "❌ Использование: /gd_user <ник>\n\n"
            "Пример: /gd_user Riot"
        )
        return
    
    username = " ".join(context.args)
    
    # Send "searching" message
    status_msg = await update.message.reply_text(
        f"🔍 Ищу игрока **{username}** в Geometry Dash...",
        parse_mode="Markdown"
    )
    
    try:
        # Fetch user data from GD API
        user_data = await get_user_info(username)
        
        if not user_data:
            await status_msg.edit_text(
                f"❌ Игрок **{username}** не найден в Geometry Dash.\n\n"
                f"Проверьте правильность написания ника.",
                parse_mode="Markdown"
            )
            return
        
        # Format and send user stats
        stats_text = format_user_stats(user_data)
        await status_msg.edit_text(stats_text, parse_mode="Markdown")
        
        logger.info(f"User {update.effective_user.id} fetched GD stats for {username}")
        
    except Exception as e:
        logger.error(f"Error in /gd_user command: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ Произошла ошибка при получении данных из Geometry Dash.\n"
            "Попробуйте позже."
        )


async def gd_level_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /gd_level command.
    
    Usage: /gd_level <level_id>
    
    Fetches and displays GD level information from official servers.
    """
    if not update.message or not context.args:
        await update.message.reply_text(
            "❌ Использование: /gd_level <ID уровня>\n\n"
            "Пример: /gd_level 10565740"
        )
        return
    
    try:
        level_id = int(context.args[0])
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ ID уровня должен быть числом.\n\n"
            "Пример: /gd_level 10565740"
        )
        return
    
    # Send "searching" message
    status_msg = await update.message.reply_text(
        f"🔍 Ищу уровень с ID **{level_id}** в Geometry Dash...",
        parse_mode="Markdown"
    )
    
    try:
        # Fetch level data from GD API
        level_data = await get_level_info(level_id)
        
        if not level_data:
            await status_msg.edit_text(
                f"❌ Уровень с ID **{level_id}** не найден в Geometry Dash.\n\n"
                f"Проверьте правильность ID.",
                parse_mode="Markdown"
            )
            return
        
        # Format and send level info
        level_text = format_level_info(level_data)
        await status_msg.edit_text(level_text, parse_mode="Markdown")
        
        logger.info(f"User {update.effective_user.id} fetched GD level {level_id}")
        
    except Exception as e:
        logger.error(f"Error in /gd_level command: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ Произошла ошибка при получении данных из Geometry Dash.\n"
            "Попробуйте позже."
        )


def register_gd_api_handlers(application) -> None:
    """
    Register GD API command handlers.
    
    Args:
        application: PTB Application instance
    """
    application.add_handler(CommandHandler("gd_user", gd_user_command))
    application.add_handler(CommandHandler("gd_level", gd_level_command))
    
    logger.info("GD API handlers registered: /gd_user, /gd_level")
