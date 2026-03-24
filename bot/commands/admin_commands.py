# admin_commands.py — Административные команды для python-telegram-bot 20.x
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.dependency_injection import build_services

logger = structlog.get_logger()


async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin — панель администратора."""
    user = update.effective_user

    with build_services() as svc:
        if not svc.admin_service.is_admin(user.id):
            await update.message.reply_text("🔒 У вас нет прав администратора.")
            return

        users_count = svc.admin_service.get_users_count()

        text = (
            f"🔧 <b>Панель администратора</b>\n\n"
            f"👋 Добро пожаловать, {user.first_name}!\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"   • Всего пользователей: {users_count}\n\n"
            f"🛠️ <b>Команды:</b>\n"
            f"   • /add_points @username [число]\n"
            f"   • /add_admin @username\n"
            f"   • /admin_stats — статистика системы"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        logger.info("Admin panel accessed", user_id=user.id)


async def add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add_points — начисление очков пользователю."""
    user = update.effective_user

    with build_services() as svc:
        if not svc.admin_service.is_admin(user.id):
            await update.message.reply_text("🔒 У вас нет прав администратора.")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Неверный формат</b>\n\nИспользование: /add_points @username [количество]",
                parse_mode="HTML",
            )
            return

        username = context.args[0]
        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Количество очков должно быть положительным числом.")
            return

        try:
            target_user = svc.admin_service.get_user_by_username(username)
            if not target_user:
                await update.message.reply_text(f"❌ Пользователь {username} не найден.")
                return

            updated_user = await svc.transaction_service.add_points(
                user_id=target_user.telegram_id,
                amount=amount,
                reason=f"Admin addition by {user.username or user.first_name}",
            )

            await update.message.reply_text(
                f"✅ <b>Очки начислены!</b>\n\n"
                f"👤 Пользователь: @{target_user.username or target_user.telegram_id}\n"
                f"💰 Начислено: {amount} очков\n"
                f"💳 Новый баланс: {updated_user.balance} очков",
                parse_mode="HTML",
            )
            logger.info("Points added", admin_id=user.id, target=target_user.telegram_id, amount=amount)

        except Exception as e:
            logger.error("Error in add_points command", error=str(e))
            await update.message.reply_text("❌ Произошла ошибка при начислении очков.")


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add_admin — назначение администратора."""
    user = update.effective_user

    with build_services() as svc:
        if not svc.admin_service.is_admin(user.id):
            await update.message.reply_text("🔒 У вас нет прав администратора.")
            return

        if not context.args:
            await update.message.reply_text(
                "❌ <b>Неверный формат</b>\n\nИспользование: /add_admin @username",
                parse_mode="HTML",
            )
            return

        username = context.args[0].strip()

        try:
            target_user = svc.admin_service.get_user_by_username(username)
            if not target_user:
                await update.message.reply_text(f"❌ Пользователь {username} не найден.")
                return

            if svc.admin_service.is_admin(target_user.telegram_id):
                await update.message.reply_text(
                    f"ℹ️ Пользователь @{target_user.username or target_user.telegram_id} уже администратор."
                )
                return

            success = svc.admin_service.set_admin_status(target_user.telegram_id, True)
            if not success:
                await update.message.reply_text("❌ Не удалось назначить администратора.")
                return

            await update.message.reply_text(
                f"✅ <b>Администратор назначен!</b>\n\n"
                f"👤 @{target_user.username or target_user.telegram_id}",
                parse_mode="HTML",
            )
            logger.info("Admin granted", admin_id=user.id, target=target_user.telegram_id)

        except Exception as e:
            logger.error("Error in add_admin command", error=str(e))
            await update.message.reply_text("❌ Произошла ошибка при назначении администратора.")
