"""Achievements команды для Telegram бота."""

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from bot.bot import BankBot

logger = logging.getLogger(__name__)


async def achievements_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, get_db
) -> None:
    """Команда /achievements - достижения."""
    from bot.services.achievement_service import AchievementSystem

    user = update.effective_user

    db = next(get_db())
    try:
        achievement_system = AchievementSystem(db)
        user_achievements = achievement_system.get_user_achievements(user.id)
        available_achievements = achievement_system.get_available_achievements(user.id)

        text = f"""
[TROPHY] <b>Ваши достижения</b>

[STATS] Общая статистика:
   • Получено достижений: {user_achievements["total_achievements"]}
   • Накоплено очков: {user_achievements["total_points"]}
   • Доступно для получения: {available_achievements["total_available"]}

"""
        if user_achievements["unlocked"]:
            text += "[MEDAL] <b>Последние достижения:</b>\n\n"
            for ach in user_achievements["unlocked"][:3]:
                tier_icon = {
                    "bronze": "[BRONZE]",
                    "silver": "[SILVER]",
                    "gold": "[GOLD]",
                }.get(ach["tier"], "[MEDAL]")

                text += f"{tier_icon} <b>{ach['name']}</b>\n"
                text += f"   {ach['description']}\n"
                text += f"   📅 {ach['unlocked_at']} | 💎 {ach['points']} очков\n\n"

        if available_achievements["available"]:
            text += "[TARGET] <b>Ближайшие к получению:</b>\n\n"
            for ach in available_achievements["available"][:3]:
                progress_bar = "▓" * (ach["progress_percentage"] // 10) + "░" * (
                    10 - (ach["progress_percentage"] // 10)
                )
                text += f"• {ach['name']}\n"
                text += f"   {ach['description']}\n"
                text += f"   📊 {progress_bar} {ach['progress_percentage']}%\n\n"

        text += "[TIP] Продолжайте активность, чтобы открыть новые достижения!"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in achievements command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()
