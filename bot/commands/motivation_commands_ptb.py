"""Motivation commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from core.systems.motivation_system import MotivationSystem


async def daily_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        motivation = MotivationSystem(db)
        result = motivation.claim_daily_bonus(user.id)

        if result["success"]:
            text = f"[FREE] Bonus poluchen! +{result['coins_earned']} monet"
        else:
            text = f"[CLOCK] Bonus uzhe poluchen segodnya! Streak: {result.get('streak', 0)} dney"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        motivation = MotivationSystem(db)
        challenges = motivation.get_weekly_challenges(user.id)

        text = f"Ezhenedelnye zadaniya (Nedelya {challenges['week']}):\n\n"
        for challenge in challenges["challenges"]:
            status = "[YES]" if challenge["completed"] else "[NO]"
            text += f"{status} {challenge['name']}\n"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def motivation_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        motivation = MotivationSystem(db)
        stats = motivation.get_user_motivation_stats(user.id)

        text = f"Streak: {stats['current_streak']} dney\n"
        text += f"Max streak: {stats['max_streak']} dney\n"
        text += f"Total bonuses: {stats['total_daily_bonuses']}"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()
