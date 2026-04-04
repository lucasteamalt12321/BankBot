"""Admin commands for python-telegram-bot."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes
from database.database import get_db

logger = structlog.get_logger()


# Wrapper commands - extracted from bot/bot.py
async def admin_adjust_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_adjust_command

    await admin_adjust_command(update, context, admin_system, get_db)


async def admin_addcoins_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_addcoins_command

    await admin_addcoins_command(update, context, admin_system, get_db)


async def admin_removecoins_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_removecoins_command

    await admin_removecoins_command(update, context, admin_system, get_db)


async def admin_merge_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_merge_command

    await admin_merge_command(update, context, admin_system, get_db)


async def admin_transactions_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_transactions_command

    await admin_transactions_command(update, context, admin_system, get_db)


async def admin_balances_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_balances_command

    await admin_balances_command(update, context, admin_system, get_db)


async def admin_users_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_users_command

    await admin_users_command(update, context, admin_system, get_db)


async def admin_rates_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_rates_command

    await admin_rates_command(update, context, admin_system)


async def admin_rate_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_rate_command

    await admin_rate_command(update, context, admin_system)


async def admin_cleanup_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_cleanup_command

    await admin_cleanup_command(update, context, admin_system, get_db)


async def admin_shop_add_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_shop_add_command

    await admin_shop_add_command(update, context, admin_system, get_db)


async def admin_shop_edit_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_shop_edit_command

    await admin_shop_edit_command(update, context, admin_system, get_db)


async def admin_games_stats_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_games_stats_command

    await admin_games_stats_command(update, context, admin_system, get_db)


async def admin_reset_game_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_reset_game_command

    await admin_reset_game_command(update, context, admin_system, get_db)


async def admin_ban_player_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_ban_player_command

    await admin_ban_player_command(update, context, admin_system, get_db)


async def admin_health_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_health_command

    await admin_health_command(update, context, admin_system, get_db)


async def admin_errors_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_errors_command

    await admin_errors_command(update, context, admin_system, get_db)


async def admin_backup_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_backup_command

    await admin_backup_command(update, context, admin_system, get_db)


async def admin_background_status_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_background_status_command

    await admin_background_status_command(update, context, admin_system, get_db)


async def admin_background_health_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_background_health_command

    await admin_background_health_command(update, context, admin_system, get_db)


async def admin_background_restart_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_background_restart_command

    await admin_background_restart_command(update, context, admin_system, get_db)


async def admin_parsing_reload_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_parsing_reload_command

    await admin_parsing_reload_command(update, context, admin_system, get_db)


async def admin_parsing_config_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_parsing_config_command

    await admin_parsing_config_command(update, context, admin_system, get_db)


async def admin_stats_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system
):
    from bot.commands.admin_commands_ptb import admin_stats_command

    await admin_stats_command(update, context, admin_system, get_db)


async def admin_health_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system, monitoring_system
):
    from bot.commands.admin_commands_ptb import admin_health_command

    await admin_health_command(update, context, admin_system, monitoring_system)


async def admin_errors_command_w(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    error_handling_system,
):
    from bot.commands.admin_commands_ptb import admin_errors_command

    await admin_errors_command(update, context, admin_system, error_handling_system)


async def admin_backup_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system, backup_system
):
    from bot.commands.admin_commands_ptb import admin_backup_command

    await admin_backup_command(update, context, admin_system, backup_system)


async def admin_background_status_command_w(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    from bot.commands.admin_commands_ptb import admin_background_status_command

    await admin_background_status_command(
        update, context, admin_system, background_task_manager
    )


async def admin_background_health_command_w(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    from bot.commands.admin_commands_ptb import admin_background_health_command

    await admin_background_health_command(
        update, context, admin_system, background_task_manager
    )


async def admin_background_restart_command_w(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    from bot.commands.admin_commands_ptb import admin_background_restart_command

    await admin_background_restart_command(
        update, context, admin_system, background_task_manager
    )


async def admin_parsing_reload_command_w(
    update: Update, context: ContextTypes.DEFAULT_TYPE, admin_system, message_parser
):
    from bot.commands.admin_commands_ptb import admin_parsing_reload_command

    await admin_parsing_reload_command(update, context, admin_system, message_parser)


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin - панель администратора."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text(
            "🔒 У вас нет прав администратора для выполнения этой команды.\n"
            "Обратитесь к администратору бота для получения доступа."
        )
        logger.warning(
            f"User {user.id} (@{user.username}) attempted to use admin command without permissions"
        )
        return

    users_count = admin_system.get_users_count()

    text = f"""🔧 <b>Админ-панель</b>

👥 <b>Управление пользователями:</b>
/add_points @user [число] - начислить очки
/add_admin @user - добавить администратора
/user_stats @user - детальная статистика пользователя
/admin_users - список всех пользователей
/admin_balances - топ пользователей по балансу
/admin_transactions @user - история транзакций

💰 <b>Управление балансом:</b>
/admin_addcoins @user [число] - добавить монеты
/admin_removecoins @user [число] - снять монеты
/admin_adjust @user [число] - корректировка баланса
/admin_merge @user1 @user2 - объединить аккаунты

📊 <b>Статистика и аналитика:</b>
/parsing_stats [24h|7d|30d] - статистика парсинга
/admin_stats - общая статистика системы
/admin_games_stats - статистика по играм
/admin_rates - коэффициенты конвертации

📢 <b>Коммуникация:</b>
/broadcast <текст> - рассылка всем пользователям

🛒 <b>Управление магазином:</b>
/add_item - добавить товар в магазин
/admin_shop_add - добавить товар (альтернатива)
/admin_shop_edit - редактировать товар

🔧 <b>Системные команды:</b>
/admin_health - здоровье системы
/admin_backup - создать резервную копию
/admin_cleanup - очистка системы
/admin_errors - просмотр ошибок

⚙️ <b>Настройки парсинга:</b>
/admin_parsing_config - конфигурация парсинга
/admin_parsing_reload - перезагрузить правила

🎮 <b>Фоновые задачи:</b>
/admin_background_status - статус задач
/admin_background_health - здоровье задач
/admin_background_restart - перезапуск задач

📈 <b>Информация:</b>
Всего пользователей: {users_count}

💡 <b>Совет:</b> Используйте /user_stats @username для получения детальной информации о любом игроке"""

    await update.message.reply_text(text, parse_mode="HTML")
    logger.info(f"Admin panel accessed by user {user.id}")


async def admin_stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_stats - статистика системы."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    db = get_db()
    try:
        from database.database import User, Transaction
        from sqlalchemy import func
        from datetime import datetime

        total_users = db.query(User).count()
        total_balance = db.query(func.sum(User.balance)).scalar() or 0

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_transactions = (
            db.query(Transaction).filter(Transaction.created_at >= today).count()
        )

        text = f"""
📊 <b>Статистика системы</b>

👤 Пользователи: {total_users}
💰 Общий баланс: {total_balance} монет
📈 Транзакций сегодня: {today_transactions}

💱 <b>Коэффициенты конвертации:</b>
   • Shmalala: 1:1
   • GD Cards: 2:1
   • True Mafia: 15:1
   • Bunker RP: 20:1
"""

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_stats command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_balances_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_balances - топ пользователей по балансу."""
    db = get_db()
    try:
        from database.database import User
        from sqlalchemy import desc

        users = db.query(User).order_by(desc(User.balance)).limit(20).all()

        text = """
🏆 <b>Топ пользователей по балансу</b>

"""
        for i, user_db in enumerate(users, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")

            text += f"{medal} "
            if user_db.username:
                text += f"@{user_db.username}"
            elif user_db.first_name:
                text += f"{user_db.first_name} {user_db.last_name or ''}"
            else:
                text += f"#{user_db.id}"

            text += f" - {user_db.balance} монет\n"

        text += f"\n💡 Всего пользователей: {db.query(User).count()}"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_balances command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_users - список пользователей."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    db = get_db()
    try:
        from database.database import User
        from sqlalchemy import desc

        users = db.query(User).order_by(desc(User.created_at)).limit(20).all()

        text = """
👥 <b>Последние зарегистрированные пользователи</b>

"""
        for user_db in users:
            text += f"👤 #{user_db.id}\n"
            if user_db.username:
                text += f"   @{user_db.username}\n"
            if user_db.first_name:
                text += f"   {user_db.first_name} {user_db.last_name or ''}\n"
            text += f"   Баланс: {user_db.balance} монет\n"
            text += f"   Регистрация: {user_db.created_at.strftime('%d.%m.%Y')}\n\n"

        text += f"💡 Всего пользователей: {db.query(User).count()}"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_users command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_shop_add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_shop_add - добавление товара (заглушка)."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    await update.message.reply_text(
        "🛍️ <b>Добавление товара</b>\n\n"
        "Функция в разработке. Используйте прямой SQL для добавления товаров.",
        parse_mode="HTML",
    )


async def admin_shop_edit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_shop_edit - редактирование товара (заглушка)."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    await update.message.reply_text(
        "✏️ <b>Редактирование товара</b>\n\n"
        "Функция в разработке. Используйте прямой SQL для редактирования товаров.",
        parse_mode="HTML",
    )


async def admin_reset_game_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_reset_game - сброс игры (заглушка)."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    await update.message.reply_text(
        "🔄 <b>Сброс игры</b>\n\nФункция в разработке.",
        parse_mode="HTML",
    )


async def admin_ban_player_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_ban_player - бан игрока (заглушка)."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    await update.message.reply_text(
        "🚫 <b>Бан игрока</b>\n\nФункция в разработке.",
        parse_mode="HTML",
    )


async def admin_adjust_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_adjust - корректировка баланса."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Используйте: /admin_adjust <пользователь> <сумма> <причина>\n"
            'Пример: /admin_adjust @username 100 "Бонус за активность"\n'
            'Пример: /admin_adjust Имя Фамилия -50 "Штраф за нарушение"'
        )
        return

    user_identifier = context.args[0]

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверная сумма")
        return

    reason = " ".join(context.args[2:])

    db = get_db()
    try:
        from database.database import Transaction
        from utils.core.user_manager import UserManager

        user_manager = UserManager(db)
        user_obj = user_manager.identify_user(user_identifier)

        if not user_obj:
            await update.message.reply_text("❌ Пользователь не найден")
            return

        user_obj.balance += amount

        transaction = Transaction(
            user_id=user_obj.id,
            amount=amount,
            transaction_type="admin_adjustment",
            description=reason,
            metadata={"admin_id": user.id, "admin_username": user.username},
        )

        db.add(transaction)
        db.commit()

        text = f"""
✅ <b>Баланс скорректирован</b>

Пользователь: #{user_obj.id}
Изменение: {amount} монет
Новый баланс: {user_obj.balance} монет
Причина: {reason}
ID транзакции: {transaction.id}
            """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_adjust command: {e}")
        db.rollback()
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_addcoins_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_addcoins - добавление монет пользователю."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text(
            "У вас нет прав администратора для использования этой команды"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Неправильное использование: /admin_addcoins <пользователь> <сумма> [причина]\n"
            "Пример: /admin_addcoins @username 100\n"
            'Пример: /admin_addcoins @username 100 "Бонус за активность"'
        )
        return

    user_identifier = context.args[0]

    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом")
        return

    reason = (
        " ".join(context.args[2:])
        if len(context.args) > 2
        else f"Добавлено администратором {user.username or user.first_name}"
    )

    db = get_db()
    try:
        from database.database import Transaction
        from utils.core.user_manager import UserManager

        user_manager = UserManager(db)
        user_obj = user_manager.identify_user(user_identifier)

        if not user_obj:
            await update.message.reply_text("Пользователь не найден")
            return

        user_obj.balance += amount

        transaction = Transaction(
            user_id=user_obj.id,
            amount=amount,
            transaction_type="admin_add_coins",
            description=reason,
            metadata={"admin_id": user.id, "admin_username": user.username},
        )

        db.add(transaction)
        db.commit()

        text = f"""
[COINS] <b>Монеты успешно добавлены</b>

ID пользователя: #{user_obj.id}
Добавлено: {amount} монет
Новый баланс: {user_obj.balance} монет
Причина: {reason}
ID транзакции: {transaction.id}
            """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_addcoins command: {e}")
        db.rollback()
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_removecoins_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_removecoins - удаление монет у пользователя."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text(
            "У вас нет прав администратора для использования этой команды"
        )
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Неправильное использование: /admin_removecoins <пользователь> <сумма> [причина]\n"
            "Пример: /admin_removecoins @username 50\n"
            'Пример: /admin_removecoins @username 50 "Штраф за нарушение"'
        )
        return

    user_identifier = context.args[0]

    try:
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("Сумма должна быть положительным числом")
            return
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом")
        return

    amount = -abs(amount)
    reason = (
        " ".join(context.args[2:])
        if len(context.args) > 2
        else f"Удалено администратором {user.username or user.first_name}"
    )

    db = get_db()
    try:
        from database.database import Transaction
        from utils.core.user_manager import UserManager

        user_manager = UserManager(db)
        user_obj = user_manager.identify_user(user_identifier)

        if not user_obj:
            await update.message.reply_text("Пользователь не найден")
            return

        user_obj.balance += amount

        transaction = Transaction(
            user_id=user_obj.id,
            amount=amount,
            transaction_type="admin_remove_coins",
            description=reason,
            metadata={"admin_id": user.id, "admin_username": user.username},
        )

        db.add(transaction)
        db.commit()

        text = f"""
[COINS] <b>Монеты успешно удалены</b>

ID пользователя: #{user_obj.id}
Удалено: {abs(amount)} монет
Новый баланс: {user_obj.balance} монет
Причина: {reason}
ID транзакции: {transaction.id}
            """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_removecoins command: {e}")
        db.rollback()
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_merge_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_merge - объединение аккаунтов."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Используйте: /admin_merge <основной_пользователь> <дублирующий_пользователь>\n"
            "Пример: /admin_merge @username @old_username\n"
            'Пример: /admin_merge "Имя Фамилия" "Старое Имя"'
        )
        return

    primary_identifier = context.args[0]
    secondary_identifier = context.args[1]

    db = get_db()
    try:
        from utils.core.user_manager import UserManager

        user_manager = UserManager(db)

        primary_user = user_manager.identify_user(primary_identifier)
        secondary_user = user_manager.identify_user(secondary_identifier)

        if not primary_user or not secondary_user:
            await update.message.reply_text("❌ Один из пользователей не найден")
            return

        if primary_user.id == secondary_user.id:
            await update.message.reply_text(
                "❌ Нельзя объединить пользователя с самим собой"
            )
            return

        user_manager.merge_users(primary_user.id, secondary_user.id)

        text = f"""
✅ <b>Аккаунты объединены</b>

Основной аккаунт: #{primary_user.id}
Объединенный аккаунт: #{secondary_user.id}
Баланс объединен
Алиасы перенесены
Транзакции перенесены

💡 Пользователь #{secondary_user.id} удален из системы.
            """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_merge command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_transactions_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_transactions - транзакции пользователя."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: /admin_transactions <пользователь> [лимит]\n"
            "Пример: /admin_transactions @username 20\n"
            'Пример: /admin_transactions "Имя Фамилия"',
            parse_mode="HTML",
        )
        return

    user_identifier = context.args[0].replace("@", "")
    limit = (
        int(context.args[1])
        if len(context.args) > 1 and context.args[1].isdigit()
        else 20
    )

    try:
        admin_user = admin_system.get_user_by_username(user_identifier)
        if admin_user:
            conn = admin_system.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT amount, type, created_at, description 
                FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """,
                (admin_user["id"], limit),
            )

            transactions = cursor.fetchall()
            conn.close()

            text = f"""📊 <b>Транзакции пользователя</b>

👤 Пользователь: {admin_user["first_name"]} (@{admin_user["username"] or admin_user["telegram_id"]})
💳 Баланс: {int(admin_user["balance"])} очков
📋 Показано: {len(transactions)} транзакций

"""
            if not transactions:
                text += "📭 Транзакций не найдено"
            else:
                for t in transactions:
                    amount_text = (
                        f"+{t['amount']}" if t["amount"] > 0 else str(t["amount"])
                    )
                    emoji = "⬆️" if t["amount"] > 0 else "⬇️" if t["amount"] < 0 else "➡️"

                    text += f"{emoji} {amount_text} очков\n"
                    text += f"   Тип: {t['type']}\n"
                    text += f"   Описание: {t['description'] or 'Нет описания'}\n"
                    text += f"   Дата: {t['created_at']}\n\n"

            await update.message.reply_text(text, parse_mode="HTML")
            return

        db = get_db()
        try:
            from database.database import Transaction
            from utils.core.user_manager import UserManager
            from sqlalchemy import desc

            user_manager = UserManager(db)
            user_obj = user_manager.identify_user(user_identifier)
            if not user_obj:
                await update.message.reply_text("❌ Пользователь не найден")
                return

            transactions = (
                db.query(Transaction)
                .filter(Transaction.user_id == user_obj.id)
                .order_by(desc(Transaction.created_at))
                .limit(limit)
                .all()
            )

            text = f"""📊 <b>Транзакции пользователя</b>

👤 Пользователь: #{user_obj.id}
💳 Баланс: {user_obj.balance} монет
📋 Показано: {len(transactions)} транзакций

"""
            for t in transactions:
                amount_text = f"+{t.amount}" if t.amount > 0 else str(t.amount)
                emoji = "⬆️" if t.amount > 0 else "⬇️" if t.amount < 0 else "➡️"

                text += f"{emoji} {amount_text} монет\n"
                text += f"   ID: {t.id}\n"
                text += f"   Тип: {t.transaction_type}\n"
                text += f"   Описание: {t.description[:50]}{'...' if len(t.description) > 50 else ''}\n"
                text += f"   Дата: {t.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

            await update.message.reply_text(text, parse_mode="HTML")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_transactions command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def admin_rates_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_rates - коэффициенты конвертации."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    from src.config import get_currency_config

    currency_config = get_currency_config()

    text = "💰 <b>Текущие коэффициенты конвертации:</b>\n\n"
    for game, config in currency_config.items():
        text += f"🎮 <b>{game}</b>: {config['base_rate']}x\n"
        if "event_multipliers" in config:
            for event, multiplier in config["event_multipliers"].items():
                text += f"   ├ {event}: {multiplier}x\n"
        if "rarity_multipliers" in config:
            for rarity, multiplier in config["rarity_multipliers"].items():
                text += f"   ├ {rarity}: {multiplier}x\n"
        text += "\n"

    text += "💡 Используйте /admin_rate <игра> <коэффициент> для изменения"

    await update.message.reply_text(text, parse_mode="HTML")


async def admin_rate_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
):
    """Команда /admin_rate - изменение коэффициента."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Используйте: /admin_rate <игра> <новый_коэффициент>\n"
            "Пример: /admin_rate shmalala 1.5\n"
            "Доступные игры: shmalala, gdcards, true_mafia, bunkerrp"
        )
        return

    game, new_rate = context.args[0], context.args[1]

    try:
        new_rate = float(new_rate)
        if new_rate <= 0:
            await update.message.reply_text(
                "❌ Коэффициент должен быть положительным числом"
            )
            return

        from src.config import update_currency_rate

        success = update_currency_rate(game, new_rate)

        if success:
            await update.message.reply_text(
                f"✅ Коэффициент для {game} изменен на {new_rate}x\n"
                f"💡 Изменение применено в памяти. Для постоянного сохранения требуется перезапуск."
            )
        else:
            await update.message.reply_text(
                f"❌ Игра '{game}' не найдена\n"
                f"Доступные игры: shmalala, gdcards, true_mafia, bunkerrp"
            )

    except ValueError:
        await update.message.reply_text("❌ Неверный формат коэффициента")


async def admin_cleanup_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_cleanup - очистка системы."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    db = get_db()
    try:
        from shop.enhanced_shop import EnhancedShopSystem

        shop = EnhancedShopSystem(db)
        expired_count = shop.check_expired_items()

        from database.database import UserNotification
        from datetime import datetime, timedelta

        month_ago = datetime.utcnow() - timedelta(days=30)
        old_notifications = (
            db.query(UserNotification)
            .filter(UserNotification.created_at < month_ago)
            .delete()
        )
        db.commit()

        db.commit()

        await update.message.reply_text(
            f"🧹 <b>Очистка системы завершена</b>\n\n"
            f"📦 Деактивировано просроченных товаров: {expired_count}\n"
            f"🗑️ Удалено старых уведомлений: {old_notifications}\n"
            f"✅ Система оптимизирована",
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Error in admin_cleanup command: {e}")
        await update.message.reply_text(f"❌ Ошибка при очистке: {str(e)}")
    finally:
        db.close()


async def admin_games_stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_games_stats - статистика игр."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    db = get_db()
    try:
        from database.database import GameSession

        total_games = db.query(GameSession).count()
        active_games = (
            db.query(GameSession).filter(GameSession.status == "active").count()
        )
        waiting_games = (
            db.query(GameSession).filter(GameSession.status == "waiting").count()
        )

        await update.message.reply_text(
            f"🎮 <b>Статистика мини-игр</b>\n\n"
            f"Всего игр: {total_games}\n"
            f"Активных: {active_games}\n"
            f"Ожидающих начала: {waiting_games}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error in admin_games_stats command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def admin_health_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    monitoring_system,
):
    """Команда /admin_health - здоровье системы."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if monitoring_system:
        health_data = monitoring_system.get_system_health()
        metrics = monitoring_system.get_all_metrics()

        text = f"""
⚙️ <b>Состояние системы</b>

💻 <b>Процессор:</b>
   • Загрузка: {health_data["cpu"]["percent"]}%
   • Ядер: {health_data["cpu"]["count"]}

🧠 <b>Память:</b>
   • Всего: {health_data["memory"]["total"] // (1024**3)} GB
   • Использовано: {health_data["memory"]["used"] // (1024**3)} GB ({health_data["memory"]["percent"]}%)
   • Свободно: {health_data["memory"]["available"] // (1024**3)} GB

💾 <b>Диск:</b>
   • Всего: {health_data["disk"]["total"] // (1024**3)} GB
   • Использовано: {health_data["disk"]["used"] // (1024**3)} GB ({health_data["disk"]["percent"]}%)
   • Свободно: {health_data["disk"]["free"] // (1024**3)} GB

📊 <b>Бизнес-метрики:</b>
   • Всего пользователей: {metrics["business_metrics"]["total_users"]}
   • Активных сегодня: {metrics["business_metrics"]["active_users_today"]}
   • Транзакций сегодня: {metrics["business_metrics"]["today_transactions"]}

📈 <b>Производительность:</b>
   • Проверка: {metrics["performance_metrics"]["total_check_time"]:.2f}s
   • Проблемы: {len(metrics["performance_metrics"]["performance_issues"])}
        """
    else:
        import psutil
        import os

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        text = f"""
⚙️ <b>Состояние системы</b>

💻 <b>Процессор:</b>
   • Загрузка: {cpu_percent}%
   • Ядер: {psutil.cpu_count()}

🧠 <b>Память:</b>
   • Всего: {memory.total // (1024**3)} GB
   • Использовано: {memory.used // (1024**3)} GB ({memory.percent}%)
   • Свободно: {memory.available // (1024**3)} GB

💾 <b>Диск:</b>
   • Всего: {disk.total // (1024**3)} GB
   • Использовано: {disk.used // (1024**3)} GB ({disk.percent}%)
   • Свободно: {disk.free // (1024**3)} GB

📊 <b>Бот:</b>
   • PID: {os.getpid()}
   • Время работы: {psutil.Process(os.getpid()).create_time()}
        """

    await update.message.reply_text(text, parse_mode="HTML")


async def admin_errors_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    error_handling_system,
):
    """Команда /admin_errors - просмотр ошибок."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if error_handling_system:
        errors = error_handling_system.get_recent_errors(10)
        stats = error_handling_system.get_error_statistics()

        text = f"""
🚨 <b>Последние ошибки</b>

📊 <b>Статистика ошибок:</b>
   • Всего ошибок: {stats["total_errors"]}
   • Сегодня: {stats["errors_today"]}
   • На этой неделе: {stats["errors_this_week"]}
   • Самая частая: {stats["most_common_error"]["type"]} ({stats["most_common_error"]["count"]} раз)

📝 <b>Последние ошибки:</b>
"""
        for error in errors[-5:]:
            text += f"• {error['error_type']}: {error['message'][:50]}...\n"
            text += f"  📅 {error['timestamp'].strftime('%d.%m.%Y %H:%M')}\n\n"

        text += "💡 Используйте /admin_cleanup для очистки старых ошибок"
    else:
        text = (
            "🚨 <b>Просмотр ошибок</b>\n\n"
            "Функция в разработке. Ошибки логируются в файлы логов."
        )

    await update.message.reply_text(text, parse_mode="HTML")


async def admin_backup_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    backup_system,
):
    """Команда /admin_backup - резервное копирование."""
    user = update.effective_user

    if not admin_system.is_admin(user.id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if backup_system:
        result = backup_system.create_backup()
        if result["success"]:
            await update.message.reply_text(
                f"✅ <b>Резервная копия создана</b>\n\n"
                f"Файл: {result['backup_file']}\n"
                f"Размер: {result['size']} байт\n"
                f"Время: {result['timestamp']}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Ошибка создания резервной копии</b>\n\n{result['message']}",
                parse_mode="HTML",
            )
    else:
        await update.message.reply_text(
            "💾 <b>Резервное копирование</b>\n\n"
            "Функция в разработке. Резервные копии создаются автоматически.",
            parse_mode="HTML",
        )


async def admin_background_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    """Команда /admin_background_status - статус фоновых задач."""
    user = update.effective_user

    try:
        if not background_task_manager:
            await update.message.reply_text(
                "❌ Система фоновых задач не инициализирована"
            )
            return

        task_status = background_task_manager.get_task_status()
        health_status = await background_task_manager.monitor_parsing_health()

        text = f"""
🔧 <b>Статус фоновых задач</b>

📊 <b>Основной статус:</b>
   • Запущены: {"✅ Да" if task_status["is_running"] else "❌ Нет"}
   • Интервал очистки: {task_status["cleanup_interval_seconds"]} сек
   • Интервал мониторинга: {task_status["monitoring_interval_seconds"]} сек

🏃 <b>Активные задачи:</b>
   • Очистка: {"✅ Активна" if task_status["cleanup_task_running"] else "❌ Неактивна"}
   • Мониторинг: {"✅ Активен" if task_status["monitoring_task_running"] else "❌ Неактивен"}

🏥 <b>Здоровье системы:</b>
   • Общее состояние: {"✅ Здорова" if health_status.is_healthy else "❌ Проблемы"}
   • База данных: {"✅ Подключена" if health_status.database_connected else "❌ Отключена"}
   • Парсинг активен: {"✅ Да" if health_status.parsing_active else "❌ Нет"}
   • Последняя проверка: {health_status.last_check.strftime("%d.%m.%Y %H:%M:%S")}

⚠️ <b>Ошибки:</b>
{chr(10).join([f"   • {error}" for error in health_status.errors]) if health_status.errors else "   • Ошибок нет"}

🕐 <b>Последняя проверка статуса:</b>
   {task_status["last_status_check"]}
        """

        await update.message.reply_text(text, parse_mode="HTML")
        logger.info(f"Background status requested by admin {user.id}")

    except Exception as e:
        logger.error(f"Error in admin_background_status command: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при получении статуса фоновых задач: {str(e)}"
        )


async def admin_background_health_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    """Команда /admin_background_health - проверка здоровья фоновых задач."""
    user = update.effective_user

    try:
        if not background_task_manager:
            await update.message.reply_text(
                "❌ Система фоновых задач не инициализирована"
            )
            return

        health_status = await background_task_manager.monitor_parsing_health()
        cleanup_result = await background_task_manager.cleanup_expired_access()

        text = f"""
🏥 <b>Проверка здоровья фоновых задач</b>

📊 <b>Результат проверки:</b>
   • Статус: {"✅ Система здорова" if health_status.is_healthy else "❌ Обнаружены проблемы"}
   • База данных: {"✅ Подключена" if health_status.database_connected else "❌ Отключена"}
   • Фоновые задачи: {"✅ Работают" if health_status.background_tasks_running else "❌ Остановлены"}
   • Парсинг: {"✅ Активен" if health_status.parsing_active else "❌ Неактивен"}

🧹 <b>Результат тестовой очистки:</b>
   • Очищено пользователей: {cleanup_result.cleaned_users}
   • Очищено файлов: {cleanup_result.cleaned_files}
   • Ошибок: {len(cleanup_result.errors)}
   • Сообщение: {cleanup_result.completion_message}

⚠️ <b>Обнаруженные ошибки:</b>
{chr(10).join([f"   • {error}" for error in health_status.errors + cleanup_result.errors]) if (health_status.errors or cleanup_result.errors) else "   • Ошибок не обнаружено"}

🕐 <b>Время проверки:</b>
   {health_status.last_check.strftime("%d.%m.%Y %H:%M:%S")}

💡 <b>Рекомендации:</b>
   • Если есть ошибки, используйте /admin_background_restart для перезапуска
   • Регулярно проверяйте статус с помощью /admin_background_status
        """

        await update.message.reply_text(text, parse_mode="HTML")
        logger.info(f"Background health check requested by admin {user.id}")

    except Exception as e:
        logger.error(f"Error in admin_background_health command: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при проверке здоровья фоновых задач: {str(e)}"
        )


async def admin_background_restart_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    background_task_manager,
):
    """Команда /admin_background_restart - перезапуск фоновых задач."""
    user = update.effective_user

    try:
        if not background_task_manager:
            await update.message.reply_text(
                "❌ Система фоновых задач не инициализирована"
            )
            return

        await update.message.reply_text("🔄 Перезапуск фоновых задач...")

        import asyncio

        await background_task_manager.stop_periodic_cleanup()
        logger.info(f"Background tasks stopped by admin {user.id}")

        await asyncio.sleep(2)

        await background_task_manager.start_periodic_cleanup()
        logger.info(f"Background tasks restarted by admin {user.id}")

        task_status = background_task_manager.get_task_status()
        health_status = await background_task_manager.monitor_parsing_health()

        from datetime import datetime

        text = f"""
✅ <b>Фоновые задачи перезапущены</b>

📊 <b>Новый статус:</b>
   • Запущены: {"✅ Да" if task_status["is_running"] else "❌ Нет"}
   • Очистка активна: {"✅ Да" if task_status["cleanup_task_running"] else "❌ Нет"}
   • Мониторинг активен: {"✅ Да" if task_status["monitoring_task_running"] else "❌ Нет"}
   • Система здорова: {"✅ Да" if health_status.is_healthy else "❌ Нет"}

🕐 <b>Время перезапуска:</b>
   {datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")}

💡 <b>Следующие шаги:</b>
   • Проверьте статус через несколько минут: /admin_background_status
   • Мониторьте логи на предмет ошибок
        """

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in admin_background_restart command: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при перезапуске фоновых задач: {str(e)}"
        )


async def admin_parsing_reload_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    message_parser,
):
    """Команда /admin_parsing_reload - перезагрузка правил парсинга."""
    user = update.effective_user

    try:
        await update.message.reply_text("🔄 Перезагружаю правила парсинга...")

        from core.managers.config_manager import get_config_manager

        config_manager = get_config_manager()

        success = config_manager.reload_configuration()

        if success:
            if message_parser:
                message_parser.load_parsing_rules()

            config = config_manager.get_configuration()
            from datetime import datetime

            text = f"""
✅ <b>Правила парсинга перезагружены</b>

📊 <b>Статистика:</b>
   • Загружено правил: {len(config.parsing_rules)}
   • Активных правил: {len([r for r in config.parsing_rules if r.is_active])}
   • Ошибок валидации: {len(config_manager.get_validation_errors())}

🎮 <b>Поддерживаемые боты:</b>
{chr(10).join([f"   • {rule.bot_name} ({rule.currency_type}, x{rule.multiplier})" for rule in config.parsing_rules if rule.is_active])}

⚠️ <b>Ошибки валидации:</b>
{chr(10).join([f"   • {error}" for error in config_manager.get_validation_errors()]) if config_manager.get_validation_errors() else "   • Ошибок нет"}

🕐 <b>Время перезагрузки:</b>
   {datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S")}
            """

            await update.message.reply_text(text, parse_mode="HTML")
            logger.info(f"Parsing rules reloaded by admin {user.id}")

        else:
            errors = config_manager.get_validation_errors()
            error_text = f"""
❌ <b>Ошибка перезагрузки правил парсинга</b>

⚠️ <b>Обнаруженные ошибки:</b>
{chr(10).join([f"   • {error}" for error in errors]) if errors else "   • Неизвестная ошибка"}

💡 <b>Рекомендации:</b>
   • Проверьте правила парсинга в базе данных
   • Используйте /admin_parsing_config для просмотра конфигурации
   • Обратитесь к логам для подробной информации
            """

            await update.message.reply_text(error_text, parse_mode="HTML")
            logger.warning(f"Parsing rules reload failed for admin {user.id}")

    except Exception as e:
        logger.error(f"Error in admin_parsing_reload command: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при перезагрузке правил парсинга: {str(e)}"
        )


async def admin_parsing_config_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /admin_parsing_config - просмотр конфигурации парсинга."""
    user = update.effective_user

    try:
        from core.managers.config_manager import get_config_manager

        config_manager = get_config_manager()

        config = config_manager.get_configuration()
        health_status = config_manager.get_health_status()

        db = get_db()
        try:
            from database.database import ParsedTransaction, ParsingRule
            from sqlalchemy import func
            from datetime import timedelta

            yesterday = __import__("datetime").datetime.utcnow() - timedelta(days=1)

            recent_transactions = (
                db.query(func.count(ParsedTransaction.id))
                .filter(ParsedTransaction.parsed_at >= yesterday)
                .scalar()
                or 0
            )

            total_rules = db.query(func.count(ParsingRule.id)).scalar() or 0
            active_rules = (
                db.query(func.count(ParsingRule.id))
                .filter(ParsingRule.is_active)
                .scalar()
                or 0
            )

        finally:
            db.close()

        text = f"""
⚙️ <b>Конфигурация системы парсинга</b>

🏥 <b>Состояние системы:</b>
   • Общее здоровье: {"✅ Здорова" if health_status.is_healthy else "❌ Проблемы"}
   • База данных: {"✅ Подключена" if health_status.database_connected else "❌ Отключена"}
   • Парсинг активен: {"✅ Да" if health_status.parsing_active else "❌ Нет"}

📊 <b>Статистика правил:</b>
   • Всего правил в БД: {total_rules}
   • Активных правил: {active_rules}
   • Загружено в память: {len(config.parsing_rules)}

📈 <b>Статистика активности:</b>
   • Транзакций за 24ч: {recent_transactions}
   • Последняя проверка: {health_status.last_check.strftime("%d.%m.%Y %H:%M:%S")}

🎮 <b>Активные правила парсинга:</b>
{chr(10).join([f"   • {rule.bot_name}: {rule.pattern[:50]}{'...' if len(rule.pattern) > 50 else ''}" for rule in config.parsing_rules if rule.is_active]) if config.parsing_rules else "   • Нет активных правил"}

⚙️ <b>Настройки системы:</b>
   • Интервал очистки стикеров: {config.sticker_cleanup_interval}с
   • Задержка автоудаления: {config.sticker_auto_delete_delay}с
   • Размер пакета рассылки: {config.broadcast_batch_size}
   • Максимум попыток парсинга: {config.max_parsing_retries}

⚠️ <b>Ошибки:</b>
{chr(10).join([f"   • {error}" for error in health_status.errors]) if health_status.errors else "   • Ошибок нет"}

💡 <b>Команды управления:</b>
   • /admin_parsing_reload - перезагрузить правила
   • /parsing_stats - статистика парсинга
        """

        await update.message.reply_text(text, parse_mode="HTML")
        logger.info(f"Parsing configuration viewed by admin {user.id}")

    except Exception as e:
        logger.error(f"Error in admin_parsing_config command: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при получении конфигурации парсинга: {str(e)}"
        )
