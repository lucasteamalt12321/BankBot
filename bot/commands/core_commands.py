"""Core user commands: welcome, balance, history, profile, stats."""

import structlog
import html
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()


WELCOME_TEXT = """
[BANK] Добро пожаловать в Мета-Игровую Платформу LucasTeam!

[HELLO] Привет, {name}!

[SYSTEM] <b>Статус регистрации:</b>
{registration_status}
{admin_status}
Ваш Telegram ID: {user_id}

Я автоматически отслеживаю вашу активность в играх и начисляю банковские монеты.

[COMMANDS] <b>🔧 Основные команды:</b>
/start - запустить бота
/ping - проверить задержку
/balance - проверить баланс
/history - история транзакций  
/profile - ваш профиль
/stats - персональная статистика

[SHOP] <b>🛒 Магазин:</b>
/shop - просмотр товаров
/buy &lt;номер&gt; - купить товар
/buy_1, /buy_2, /buy_3 - быстрая покупка
/buy_contact - связь с админом (10 очков)
/inventory - ваши покупки

[ACHIEVEMENTS] <b>🏆 Достижения:</b>
/achievements - ваши достижения
/notifications - уведомления
/notifications_clear - очистить все

[ADMIN] <b>👨‍💼 Админ-команды:</b>
/admin - панель администратора
/add_points &lt;@user&gt; &lt;сумма&gt; - начислить очки
/add_admin &lt;@user&gt; - назначить админа
/admin_stats - статистика системы
/admin_users - список пользователей
/admin_balances - топ по балансу
/admin_transactions &lt;@user&gt; - транзакции
/admin_addcoins, /admin_removecoins - управление балансом
/admin_health - здоровье системы

[ADVANCED] <b>🔧 Расширенные админ-команды:</b>
/parsing_stats - статистика парсинга
/user_stats &lt;@user&gt; - детальная статистика
/broadcast &lt;текст&gt; - рассылка всем
/add_item - добавить товар в магазин

[CONFIG] <b>⚙️ Конфигурация системы:</b>
/reload_config - перезагрузить конфигурацию
/config_status - статус конфигурации
/list_parsing_rules - правила парсинга
/add_parsing_rule - добавить правило
/update_parsing_rule - обновить правило
/export_config - экспорт конфигурации
/import_config - импорт конфигурации
/backup_config - создать бэкап
/restore_config - восстановить бэкап
/list_backups - список бэкапов
/validate_config - валидация конфигурации

[GAMES_SUPPORTED] <b>Поддерживаемые игры:</b>
• Shmalala (курс 1:1)
• GD Cards (курс 2:1)  
• True Mafia (курс 15:1)
• Bunker RP (курс 20:1)

[PLAY] Просто играйте, а я буду автоматически начислять вам монеты за активность!

[TIP] <b>💡 Совет:</b> Начните с /shop для покупок!
"""


async def welcome_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    settings,
    db_get_db,
):
    """Команда /start - приветствие и регистрация."""
    user = update.effective_user

    registration_status = "❌ Ошибка регистрации"
    admin_status = "❌ Не администратор"

    try:
        admin_user = admin_system.get_user_by_id(user.id)
        if not admin_user:
            success = admin_system.register_user(user.id, user.username, user.first_name)
            if success:
                logger.info(f"Force-registered user {user.id} in admin system")
                registration_status = "✅ Пользователь зарегистрирован"

                if user.id == settings.ADMIN_TELEGRAM_ID:
                    admin_success = admin_system.set_admin_status(user.id, True)
                    if admin_success:
                        logger.info(f"Set admin status for user {user.id}")
                        admin_status = "✅ Права администратора установлены"
                    else:
                        admin_status = "❌ Ошибка установки прав администратора"

                admin_user = admin_system.get_user_by_id(user.id)
            else:
                logger.error(f"Failed to register user {user.id} in admin system")
                registration_status = "❌ Ошибка регистрации"
        else:
            registration_status = "✅ Пользователь уже зарегистрирован"
            if admin_user["is_admin"]:
                admin_status = "✅ Права администратора активны"
            else:
                admin_status = "❌ Нет прав администратора"
                if user.id == settings.ADMIN_TELEGRAM_ID:
                    admin_success = admin_system.set_admin_status(user.id, True)
                    if admin_success:
                        admin_status = "✅ Права администратора установлены"

    except Exception as e:
        logger.error(f"Error in admin system registration: {e}")
        registration_status = f"❌ Ошибка: {str(e)}"

    welcome_text = WELCOME_TEXT.format(
        name=html.escape(user.first_name or "Пользователь"),
        registration_status=html.escape(registration_status),
        admin_status=html.escape(admin_status),
        user_id=user.id,
    )

    await update.message.reply_text(welcome_text, parse_mode="HTML")

    db = next(db_get_db())
    try:
        from utils.core.user_manager import UserManager
        from utils.monitoring.notification_system import NotificationSystem

        user_manager = UserManager(db)
        identified_user = user_manager.identify_user(
            user.username or user.first_name,
            user.id,
        )

        if (
            identified_user.created_at
            and (datetime.utcnow() - identified_user.created_at).total_seconds() < 60
        ):
            notification_system = NotificationSystem(db, bot=context.bot)
            await notification_system.send_system_notification(
                identified_user.id,
                "🎉 Добро пожаловать!",
                "Вы успешно зарегистрированы в системе. Начните зарабатывать монеты!",
            )

        logger.info(
            f"User processed in main system: {identified_user.id} (Telegram ID: {user.id})",
        )
    except Exception as e:
        logger.error(f"Error processing user in main system: {e}")
    finally:
        db.close()


async def test_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /test_notify - тест всплывающего уведомления."""
    from utils.monitoring.notification_system import NotificationSystem
    from database.database import get_db, User
    
    user = update.effective_user
    db = next(get_db())
    try:
        user_db = db.query(User).filter(User.telegram_id == user.id).first()
        if not user_db:
            await update.message.reply_text("Сначала зарегистрируйтесь через /start")
            return
            
        await update.message.reply_text("🔔 Отправляю тестовое уведомление через 3 секунды...\nЗаблокируйте экран или выйдите из чата!")
        
        # Ждем немного, чтобы пользователь успел закрыть чат
        import asyncio
        await asyncio.sleep(3)
        
        notification_system = NotificationSystem(db, bot=context.bot)
        await notification_system.send_system_notification(
            user_db.id,
            "🔔 ТЕСТ УВЕДОМЛЕНИЯ",
            "Это тестовое системное уведомление. Если вы видите его на часах — всё работает!"
        )
    finally:
        db.close()


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ping - проверка работоспособности бота."""
    start_time = datetime.utcnow()
    message = await update.message.reply_text("🏓 Понг...")
    end_time = datetime.utcnow()
    latency = (end_time - start_time).total_seconds() * 1000
    await message.edit_text(f"🏓 Понг! (Задержка: {latency:.2f} мс)")


async def balance_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    db_get_db,
):
    """Команда /balance - проверка баланса."""
    from utils.admin.admin_middleware import auto_registration_middleware

    await auto_registration_middleware.process_message(update, context)
    user = update.effective_user

    try:
        admin_user = admin_system.get_user_by_id(user.id)

        if admin_user:
            text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {html.escape(admin_user['first_name'] or user.first_name or 'Неизвестно')}
[BALANCE] Баланс: {admin_user['balance']} очков
[STATUS] Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
            """
            await update.message.reply_text(text, parse_mode="HTML")
            return

        db = next(db_get_db())
        try:
            from database.database import User

            user_db = db.query(User).filter(User.telegram_id == user.id).first()

            if user_db:
                text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {html.escape(user_db.first_name or '')} {html.escape(user_db.last_name or '')}
[BALANCE] Баланс: {user_db.balance} банковских монет
[TIME] Последняя активность: {user_db.last_activity.strftime('%d.%m.%Y %H:%M') if user_db.last_activity else 'Нет данных'}

[TIP] Используйте /history для просмотра транзакций
                """
                await update.message.reply_text(text, parse_mode="HTML")
            else:
                await update.message.reply_text(
                    "❌ Пользователь не найден. Используйте /start для регистрации.",
                )
        finally:
            db.close()

    except Exception as e:
        logger.error(
            "Error in balance command",
            error=str(e),
            user_id=user.id,
            username=user.username,
        )
        await update.message.reply_text(
            "❌ Произошла ошибка при получении баланса. Попробуйте позже.",
        )


async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_get_db,
):
    """Команда /history - история транзакций."""
    user = update.effective_user
    limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10

    db = next(db_get_db())
    try:
        from database.database import User, Transaction
        from sqlalchemy import desc

        user_db = db.query(User).filter(User.telegram_id == user.id).first()
        if not user_db:
            await update.message.reply_text(
                "📭 Пользователь не найден. Используйте /start для регистрации.",
            )
            return

        transactions = (
            db.query(Transaction)
            .filter(Transaction.user_id == user_db.id)
            .order_by(desc(Transaction.created_at))
            .limit(limit)
            .all()
        )

        if not transactions:
            await update.message.reply_text("📭 У вас пока нет транзакций")
            return

        text = f"""
[STATS] <b>История транзакций</b>

[USER] Пользователь: {html.escape(user_db.first_name or '')} {html.escape(user_db.last_name or '')}
[BALANCE] Текущий баланс: {user_db.balance} монет
[LIST] Показано последних: {len(transactions)} транзакций

"""
        for t in transactions:
            amount_text = f"+{t.amount}" if t.amount > 0 else str(t.amount)
            arrow = "UP" if t.amount > 0 else "DOWN" if t.amount < 0 else "EQUAL"

            text += f"[{arrow}] {amount_text} монет\n"
            text += f"   Тип: {html.escape(t.transaction_type)}\n"
            text += f"   Описание: {html.escape(t.description[:50])}...\n"
            text += f"   Дата: {t.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in history command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def profile_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    settings,
    db_get_db,
):
    """Команда /profile - профиль пользователя."""
    from utils.admin.admin_middleware import auto_registration_middleware

    user = update.effective_user
    logger.info(f"Profile command called by user {user.id} (@{user.username})")

    try:
        await auto_registration_middleware.process_message(update, context)
        logger.info(f"Auto-registration middleware processed for user {user.id}")
    except Exception as e:
        logger.error(f"Error in auto-registration middleware: {e}")

    admin_user = None
    try:
        admin_user = admin_system.get_user_by_id(user.id)
        if not admin_user:
            success = admin_system.register_user(user.id, user.username, user.first_name)
            if success:
                logger.info(f"Force-registered user {user.id} in profile command")

                if user.id == settings.ADMIN_TELEGRAM_ID:
                    admin_system.set_admin_status(user.id, True)
                    logger.info(f"Set admin status for user {user.id}")

                admin_user = admin_system.get_user_by_id(user.id)

                if not admin_user:
                    admin_user = {
                        "id": None,
                        "telegram_id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "balance": 0,
                        "is_admin": user.id == settings.ADMIN_TELEGRAM_ID,
                    }
                    logger.warning(f"Created temporary user object for {user.id}")
            else:
                admin_user = {
                    "id": None,
                    "telegram_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "balance": 0,
                    "is_admin": False,
                }
                logger.warning(
                    f"Registration failed, created fallback user object for {user.id}",
                )
    except Exception as e:
        logger.error(f"Error in admin system registration: {e}")
        admin_user = {
            "id": None,
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "balance": 0,
            "is_admin": False,
        }
        logger.warning(
            f"Created fallback user object for {user.id} due to error: {e}",
        )

    try:
        if not admin_user:
            await update.message.reply_text(
                "❌ Критическая ошибка: пользователь не найден после регистрации",
            )
            return

        conn = admin_system.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user.id,))
        user_row = cursor.fetchone()
        internal_id = user_row["id"] if user_row else None

        total_transactions = 0
        total_deposits = 0
        if internal_id:
            cursor.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE user_id = ?",
                (internal_id,),
            )
            result = cursor.fetchone()
            total_transactions = result["count"] if result else 0

            cursor.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE user_id = ? AND amount > 0",
                (internal_id,),
            )
            result = cursor.fetchone()
            total_deposits = result["count"] if result else 0

        conn.close()

        text = f"""
[USER] <b>Ваш профиль</b>

[INFO] <b>Основная информация:</b>
   • ID: {user.id}
   • Имя: {html.escape(admin_user['first_name'] or 'Не указано')}
   • Username: @{html.escape(admin_user['username'] or 'Не указан')}
   • Баланс: {int(admin_user['balance'])} очков

[STATS] <b>Статистика:</b>
   • Всего транзакций: {total_transactions}
   • Пополнений: {total_deposits}
   • Покупок: 0
   • Друзей: 0
   • Отправлено подарков: 0

[SOCIAL] <b>Социальный статус:</b>
   • В клане: NO 
   • Роль в клане: Не состоит
   • Входящих запросов: 0

[ADMIN] <b>Права доступа:</b>
   • Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIPS] <b>Советы:</b>
   • Используйте /daily для получения ежедневного бонуса
   • Играйте в игры для увеличения баланса
   • Приглашайте друзей для получения бонусов
        """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(
            "Error in profile command",
            error=str(e),
            user_id=user.id,
            username=user.username,
        )
        await update.message.reply_text(
            f"❌ Произошла ошибка при получении профиля: {str(e)}",
        )


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_get_db,
):
    """Команда /stats - персональная статистика."""
    user = update.effective_user

    db = next(db_get_db())
    try:
        from database.database import User, Transaction, UserPurchase
        from sqlalchemy import func

        user_db = db.query(User).filter(User.telegram_id == user.id).first()
        if not user_db:
            await update.message.reply_text("❌ Пользователь не найден")
            return

        total_earned = (
            db.query(func.sum(Transaction.amount))
            .filter(Transaction.user_id == user_db.id, Transaction.amount > 0)
            .scalar()
            or 0
        )

        total_spent = abs(
            db.query(func.sum(Transaction.amount))
            .filter(Transaction.user_id == user_db.id, Transaction.amount < 0)
            .scalar()
            or 0
        )

        total_purchases = db.query(UserPurchase).filter(
            UserPurchase.user_id == user_db.id,
        ).count()

        week_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_transactions = db.query(Transaction).filter(
            Transaction.user_id == user_db.id,
            Transaction.created_at >= week_ago,
        ).count()

        text = f"""
[CHART] <b>Ваша статистика</b>

[MONEY] <b>Финансы:</b>
   • Всего заработано: {total_earned} монет
   • Всего потрачено: {total_spent} монет
   • Текущий баланс: {user_db.balance} монет
   • Покупок совершено: {total_purchases}

[STATS] <b>Активность:</b>
   • Транзакций за неделю: {week_transactions}
   • Дней в системе: {(datetime.utcnow() - user_db.created_at).days}
   • Последняя активность: {user_db.last_activity.strftime('%d.%m.%Y %H:%M') if user_db.last_activity else 'Нет данных'}

[TARGET] <b>Рекомендации:</b>
   • Заходите ежедневно для получения бонусов
   • Участвуйте в играх для увеличения баланса
   • Используйте /achievements для отслеживания прогресса
        """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()
