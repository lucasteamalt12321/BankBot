"""Notification commands for python-telegram-bot."""

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database.database import User, get_db
from src.config import settings
from utils.monitoring.notification_system import NotificationSystem


def _get_user_record(db, telegram_user_id: int):
    return db.query(User).filter_by(telegram_id=telegram_user_id).first()


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        notification_system = NotificationSystem(db)
        user_record = _get_user_record(notification_system.db, user.id)

        if not user_record:
            await update.message.reply_text("Сначала зарегистрируйтесь через /start")
            return

        notifications = notification_system.get_user_notifications(user_record.id, limit=20)
        unread_count = notification_system.get_unread_count(user_record.id)

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
        user_record = _get_user_record(notification_system.db, user.id)

        if not user_record:
            await update.message.reply_text("Сначала зарегистрируйтесь через /start")
            return

        cleared_count = notification_system.mark_all_as_read(user_record.id)

        await update.message.reply_text(f"[OK] Ochisceno uvedomleniy: {cleared_count}")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def notify_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current notification transport status and configuration."""
    _ = context
    telegram_realtime_enabled = bool(settings.BOT_TOKEN)
    watch_mode_enabled = False

    lines = [
        "<b>Статус уведомлений</b>",
        "",
        f"• Telegram realtime: <b>{'on' if telegram_realtime_enabled else 'off'}</b>",
        f"• watch mode: <b>{'on' if watch_mode_enabled else 'off временно'}</b>",
        f"• ntfy: <b>{'on' if settings.NTFY_ENABLED and watch_mode_enabled else 'off'}</b>",
        f"• ntfy topic: <code>{settings.NTFY_TOPIC}</code>",
        f"• ntfy base URL: <code>{settings.NTFY_BASE_URL}</code>",
        f"• proxy: <code>{settings.PROXY_URL or 'not set'}</code>",
        f"• adb: <b>{'on' if settings.ADB_NOTIFICATIONS_ENABLED and watch_mode_enabled else 'off'}</b>",
        f"• adb path: <code>{settings.ADB_PATH}</code>",
        f"• adb serial: <code>{settings.ADB_DEVICE_SERIAL or 'default device'}</code>",
        "",
        "Команды диагностики:",
        "/test_notify — проверить Telegram + realtime каналы",
        "/test_adb — отдельно проверить ADB-уведомление",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def test_adb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a diagnostic notification via ADB transport only."""
    _ = context
    db = next(get_db())
    try:
        notification_system = NotificationSystem(db)

        if not settings.ADB_NOTIFICATIONS_ENABLED:
            await update.message.reply_text(
                "ADB-уведомления отключены. Установите ADB_NOTIFICATIONS_ENABLED=true и попробуйте снова."
            )
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        await notification_system._send_to_adb(
            "BankBot ADB Test",
            f"Тестовое ADB-уведомление отправлено в {timestamp}",
            "adb_test",
        )
        await update.message.reply_text(
            "Проверка ADB запущена. Если устройство подключено и авторизовано, уведомление должно появиться на Android-устройстве."
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка ADB-проверки: {str(e)}")
    finally:
        db.close()
