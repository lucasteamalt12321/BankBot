"""Notification commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from utils.monitoring.notification_system import NotificationSystem


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        notification_system = NotificationSystem(db)
        notifications = notification_system.get_user_notifications(user.id, limit=20)
        unread_count = notification_system.get_unread_count(user.id)

        text = f"[LIST] Uvedomleniya ({unread_count} neproscitano):\n\n"

        if notifications:
            for notification in notifications:
                status = "[NEW]" if not notification["is_read"] else "[OK]"
                created = notification["created_at"].strftime("%d.%m.%Y %H:%M")
                text += f"{status} <b>{notification['title']}</b>\n"
                text += f"   {notification['message'][:50]}...\n"
                text += f"   {created}\n\n"
        else:
            text = "[LIST] Net uvedomleniy"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def notifications_clear_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    db = next(get_db())
    try:
        notification_system = NotificationSystem(db)
        cleared_count = notification_system.mark_all_as_read(user.id)

        await update.message.reply_text(f"[OK] Ochisceno uvedomleniy: {cleared_count}")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()
