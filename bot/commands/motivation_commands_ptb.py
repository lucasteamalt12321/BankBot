"""Motivation commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import User, get_db
from core.systems.motivation_system import MotivationSystem


def _day_word(value: int) -> str:
    value_abs = abs(value)
    if value_abs % 100 in {11, 12, 13, 14}:
        return "дней"
    if value_abs % 10 == 1:
        return "день"
    if value_abs % 10 in {2, 3, 4}:
        return "дня"
    return "дней"


def _get_internal_user_id(db, telegram_id: int) -> int | None:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    return user.id if user else None


async def daily_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        internal_user_id = _get_internal_user_id(db, user.id)
        if internal_user_id is None:
            await update.message.reply_text(
                "❌ Пользователь не найден. Сначала используйте /start."
            )
            return

        motivation = MotivationSystem(db)
        result = motivation.claim_daily_bonus(internal_user_id)

        if result["success"]:
            amount = result.get("amount", 0)
            streak = result.get("streak", 0) + 1
            text = (
                "🎁 Ежедневный бонус получен!\n"
                f"💰 Начислено: +{amount} монет\n"
                f"🔥 Серия: {streak} {_day_word(streak)}"
            )
        else:
            stats = motivation.get_user_motivation_stats(internal_user_id)
            streak = stats.get("current_streak", 0)
            text = (
                "⏰ Ежедневный бонус уже получен сегодня.\n"
                f"🔥 Текущая серия: {streak} {_day_word(streak)}\n"
                "Возвращайтесь завтра!"
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        internal_user_id = _get_internal_user_id(db, user.id)
        if internal_user_id is None:
            await update.message.reply_text(
                "❌ Пользователь не найден. Сначала используйте /start."
            )
            return

        motivation = MotivationSystem(db)
        challenges = motivation.get_weekly_challenges(internal_user_id)

        text = f"🎯 Еженедельные задания (неделя {challenges['week']}):\n\n"
        for challenge in challenges["challenges"]:
            progress = challenge.get("progress", 0)
            target = challenge.get("target", 0)
            reward = challenge.get("reward", 0)
            text += (
                f"• {challenge['name']}\n"
                f"  {challenge['description']}\n"
                f"  Прогресс: {progress}/{target}, награда: {reward} монет\n\n"
            )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def motivation_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        internal_user_id = _get_internal_user_id(db, user.id)
        if internal_user_id is None:
            await update.message.reply_text(
                "❌ Пользователь не найден. Сначала используйте /start."
            )
            return

        motivation = MotivationSystem(db)
        stats = motivation.get_user_motivation_stats(internal_user_id)

        streak = stats["current_streak"]
        text = (
            "🔥 Статистика ежедневных бонусов\n\n"
            f"Текущая серия: {streak} {_day_word(streak)}\n"
            f"Бонус сегодня доступен: {'да' if stats['can_claim_today'] else 'нет'}\n"
            f"Следующий бонус: {stats['next_bonus_amount']} монет"
        )
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()
