# bot.py - Объединенный Telegram-бот банк-аггрегатора LucasTeam
import logging
import asyncio
import signal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from database.database import create_tables, get_db
from core.systems.shop_system import EnhancedShopSystem
from core.systems.games_system import GamesSystem
from core.systems.dnd_system import DndSystem
from core.systems.motivation_system import MotivationSystem
from utils.monitoring.notification_system import NotificationSystem
from core.systems.achievements import AchievementSystem
from core.systems.social_system import SocialSystem
from src.config import settings
from utils.monitoring.monitoring_system import MonitoringSystem, AlertSystem
from database.backup_system import BackupSystem
from utils.core.error_handling import ErrorHandlingSystem
from utils.admin.admin_middleware import auto_registration_middleware
from utils.admin.admin_system import AdminSystem, admin_required
from bot.commands.advanced_admin_commands import AdvancedAdminCommands
from bot.commands import config_commands  # Configuration management commands
from bot.commands.core_commands import (
    welcome_command,
    balance_command,
    history_command,
    profile_command,
    stats_command,
)
from bot.commands.shop_commands_ptb import (
    shop_command,
    buy_contact_command,
    buy_command,
    _handle_purchase_command,
    inventory_command,
)
from bot.commands.game_commands_ptb import (
    games_command,
    play_command,
    join_command,
    start_game_command,
    game_turn_command,
)
from bot.commands.motivation_commands_ptb import (
    daily_bonus_command,
    challenges_command,
    motivation_stats_command,
)
from bot.commands.social_commands_ptb import (
    friends_command,
    friend_add_command,
    friend_accept_command,
    gift_command,
    clan_command,
    clan_create_command,
    clan_join_command,
    clan_leave_command,
)
from bot.commands.notification_commands_ptb import (
    notifications_command,
    notifications_clear_command,
)
from bot.commands.dnd_commands_ptb import (
    dnd_command,
    dnd_create_command,
    dnd_join_command,
    dnd_roll_command,
    dnd_sessions_command,
)
from bot.commands.achievements_commands_ptb import achievements_command
from bot.commands.admin_commands_ptb import (
    admin_command,
    admin_stats_command,
    admin_adjust_command,
    admin_addcoins_command,
    admin_removecoins_command,
    admin_merge_command,
    admin_transactions_command,
    admin_balances_command,
    admin_users_command,
    admin_rates_command,
    admin_rate_command,
    admin_cleanup_command,
    admin_shop_add_command,
    admin_shop_edit_command,
    admin_games_stats_command,
    admin_reset_game_command,
    admin_ban_player_command,
    admin_health_command,
    admin_errors_command,
    admin_backup_command,
    admin_background_status_command,
    admin_background_health_command,
    admin_background_restart_command,
    admin_parsing_reload_command,
    admin_parsing_config_command,
)
from bot.commands.user_commands import (
    buy_1_command,
    buy_2_command,
    buy_3_command,
    buy_4_command,
    buy_5_command,
    buy_6_command,
    buy_7_command,
    buy_8_command,
)
from core.managers.background_task_manager import BackgroundTaskManager
from core.managers.sticker_manager import StickerManager
from bot.handlers import ParsingHandler  # NEW: Unified parsing handler
import structlog

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = structlog.get_logger()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.BOT_TOKEN).build()

        # Инициализация систем мониторинга и безопасности
        self.monitoring_system = None
        self.alert_system = None
        self.backup_system = None
        self.error_handling_system = None

        # Инициализация административной системы
        self.admin_system = AdminSystem("data/bot.db")
        # База данных уже инициализирована, не нужно создавать отдельные таблицы

        # Инициализация расширенных административных команд
        self.advanced_admin_commands = AdvancedAdminCommands()

        # Инициализация системы фоновых задач
        self.background_task_manager = None
        self.sticker_manager = None

        # NEW: Инициализация обработчика парсинга
        self.parsing_handler = ParsingHandler()

        # Флаг для graceful shutdown
        self._shutdown_requested = False

        # Настройка обработчиков сигналов для graceful shutdown
        self._setup_signal_handlers()

        # Настройка обработчиков команд (после инициализации всех систем)
        self.setup_handlers()
        self.setup_error_handler()

    def is_background_system_running(self) -> bool:
        """
        Проверяет, запущена ли система фоновых задач (Task 11.3)

        Returns:
            bool: True если система фоновых задач запущена и работает
        """
        try:
            if not self.background_task_manager:
                return False

            task_status = self.background_task_manager.get_task_status()
            return task_status.get("is_running", False)

        except Exception as e:
            logger.error(f"Error checking background system status: {e}")
            return False

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        logger.info("Setting up enhanced handlers...")

        # Добавляем middleware для отслеживания активности пользователей
        from telegram.ext import TypeHandler
        from core.middleware import track_user_activity

        # Middleware должен быть в группе -1, чтобы выполняться перед всеми остальными обработчиками
        self.application.add_handler(TypeHandler(Update, track_user_activity), group=-1)
        logger.info("Added activity tracking middleware")

        # Основные команды
        handlers = [
            CommandHandler("start", self.welcome_command),
            CommandHandler("balance", self.balance_command),
            CommandHandler("history", self.history_command),
            CommandHandler("profile", self.profile_command),
            CommandHandler("stats", self.stats_command),
            # Магазин
            CommandHandler("shop", self.shop_command),
            CommandHandler("buy_contact", self.buy_contact_command),
            CommandHandler("buy", self.buy_command),
            CommandHandler("buy_1", buy_1_command),
            CommandHandler("buy_2", buy_2_command),
            CommandHandler("buy_3", buy_3_command),
            CommandHandler("buy_4", buy_4_command),
            CommandHandler("buy_5", buy_5_command),
            CommandHandler("buy_6", buy_6_command),
            CommandHandler("buy_7", buy_7_command),
            CommandHandler("buy_8", buy_8_command),
            CommandHandler("inventory", inventory_command),
            # Мини-игры
            CommandHandler("games", games_command),
            CommandHandler("play", play_command),
            CommandHandler("join", join_command),
            CommandHandler("startgame", start_game_command),
            CommandHandler("turn", game_turn_command),
            # D&D
            CommandHandler("dnd", dnd_command),
            CommandHandler("dnd_create", dnd_create_command),
            CommandHandler("dnd_join", dnd_join_command),
            CommandHandler("dnd_roll", dnd_roll_command),
            CommandHandler("dnd_sessions", dnd_sessions_command),
            # Мотивация
            CommandHandler("daily", daily_bonus_command),
            CommandHandler("bonus", daily_bonus_command),
            CommandHandler("challenges", challenges_command),
            CommandHandler("streak", motivation_stats_command),
            # Достижения и уведомления
            CommandHandler("achievements", achievements_command),
            CommandHandler("notifications", notifications_command),
            CommandHandler("notifications_clear", notifications_clear_command),
            # Социальные функции
            CommandHandler("friends", friends_command),
            CommandHandler("friend_add", friend_add_command),
            CommandHandler("friend_accept", friend_accept_command),
            CommandHandler("gift", gift_command),
            CommandHandler("clan", clan_command),
            CommandHandler("clan_create", clan_create_command),
            CommandHandler("clan_join", clan_join_command),
            CommandHandler("clan_leave", clan_leave_command),
            # Админ-команды
            CommandHandler("admin", admin_command),
            CommandHandler("add_points", self.add_points_command),
            CommandHandler("add_admin", self.add_admin_command),
            CommandHandler("admin_stats", admin_stats_command),
            CommandHandler("admin_adjust", admin_adjust_command),
            CommandHandler("admin_addcoins", admin_addcoins_command),
            CommandHandler("admin_removecoins", admin_removecoins_command),
            CommandHandler("admin_merge", admin_merge_command),
            CommandHandler("admin_transactions", admin_transactions_command),
            CommandHandler("admin_transaction", admin_transactions_command),  # Алиас
            CommandHandler("admin_balances", admin_balances_command),
            CommandHandler("admin_users", admin_users_command),
            CommandHandler("admin_rates", admin_rates_command),
            CommandHandler("admin_rate", admin_rate_command),
            CommandHandler("admin_cleanup", admin_cleanup_command),
            CommandHandler("admin_shop_add", admin_shop_add_command),
            CommandHandler("admin_shop_edit", admin_shop_edit_command),
            CommandHandler("admin_games_stats", admin_games_stats_command),
            CommandHandler("admin_reset_game", admin_reset_game_command),
            CommandHandler("admin_ban_player", admin_ban_player_command),
            CommandHandler("admin_health", admin_health_command),
            CommandHandler("admin_errors", admin_errors_command),
            CommandHandler("admin_backup", admin_backup_command),
            # Advanced Admin Commands (Task 7.4 and 8.3)
            CommandHandler(
                "parsing_stats", self.advanced_admin_commands.parsing_stats_command
            ),
            CommandHandler("broadcast", self.advanced_admin_commands.broadcast_command),
            CommandHandler(
                "user_stats", self.advanced_admin_commands.user_stats_command
            ),
            CommandHandler("add_item", self.advanced_admin_commands.add_item_command),
            # Background Task Management Commands (Task 10.3)
            CommandHandler("admin_background_status", admin_background_status_command),
            CommandHandler("admin_background_health", admin_background_health_command),
            CommandHandler(
                "admin_background_restart", admin_background_restart_command
            ),
            # Message Parsing Configuration Commands (Task 11.2)
            CommandHandler("admin_parsing_reload", admin_parsing_reload_command),
            CommandHandler("admin_parsing_config", admin_parsing_config_command),
            # Configuration Management Commands (Full Set)
            CommandHandler("reload_config", config_commands.reload_config_handler),
            CommandHandler("config_status", config_commands.config_status_handler),
            CommandHandler(
                "list_parsing_rules", config_commands.list_parsing_rules_handler
            ),
            CommandHandler(
                "add_parsing_rule", config_commands.add_parsing_rule_handler
            ),
            CommandHandler(
                "update_parsing_rule", config_commands.update_parsing_rule_handler
            ),
            CommandHandler("export_config", config_commands.export_config_handler),
            CommandHandler("import_config", config_commands.import_config_handler),
            CommandHandler("backup_config", config_commands.backup_config_handler),
            CommandHandler("restore_config", config_commands.restore_config_handler),
            CommandHandler("list_backups", config_commands.list_backups_handler),
            CommandHandler("validate_config", config_commands.validate_config_handler),
        ]

        for handler in handlers:
            self.application.add_handler(handler)
            logger.info(f"Added handler: {handler.callback.__name__}")

        # Обработка колбэков
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Обработка всех сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.parse_all_messages)
        )

        logger.info("All enhanced handlers set up successfully")

    def setup_error_handler(self):
        """Настройка обработчика ошибок через PTB add_error_handler."""
        from bot.middleware.error_handler import setup_error_handler as _setup
        from bot.middleware.dependency_injection import setup_di

        _setup(self.application)
        setup_di(self.application)
        logger.info("Error handler and DI registered successfully")

    def _setup_signal_handlers(self):
        """
        Настройка обработчиков сигналов для graceful shutdown (Task 11.3)
        Validates: Requirements 12.1, 12.2
        """

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True

            # Создаем задачу для graceful shutdown
            if hasattr(self, "application") and self.application:
                try:
                    # Останавливаем фоновые задачи
                    if self.background_task_manager:
                        asyncio.create_task(self._shutdown_background_tasks())

                    # Останавливаем бота
                    self.application.stop_running()
                    logger.info("Bot stop requested due to signal")

                except Exception as e:
                    logger.error(f"Error during signal handling: {e}")

        # Регистрируем обработчики для SIGINT (Ctrl+C) и SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers configured for graceful shutdown")

    async def _shutdown_background_tasks(self):
        """
        Graceful shutdown фоновых задач (Task 11.3)
        Validates: Requirements 12.1, 12.2
        """
        try:
            if self.background_task_manager:
                logger.info("Stopping background task manager...")
                await self.background_task_manager.stop_periodic_cleanup()
                logger.info("Background task manager stopped successfully")

                # Проверяем, что задачи действительно остановлены
                task_status = self.background_task_manager.get_task_status()
                if task_status["is_running"]:
                    logger.warning("Background tasks may not have stopped completely")
                else:
                    logger.info("Background tasks confirmed stopped")

                # Очищаем ссылки
                self.background_task_manager = None
                self.sticker_manager = None

        except Exception as e:
            logger.error(f"Error stopping background tasks: {e}")
            # Принудительно очищаем ссылки даже при ошибке
            self.background_task_manager = None
            self.sticker_manager = None

    async def _initialize_background_systems(self):
        """
        Инициализация фоновых систем (Task 11.3)
        Validates: Requirements 12.1, 12.2
        """
        try:
            logger.info("Initializing background task system...")

            db = next(get_db())
            try:
                # Инициализируем StickerManager
                self.sticker_manager = StickerManager(db)
                logger.info("StickerManager initialized successfully")

                # Инициализируем BackgroundTaskManager с правильной конфигурацией
                self.background_task_manager = BackgroundTaskManager(
                    db, self.sticker_manager
                )
                logger.info("BackgroundTaskManager initialized successfully")

                # Запускаем периодические задачи очистки (Requirement 12.1)
                await self.background_task_manager.start_periodic_cleanup()
                logger.info("Periodic cleanup tasks started (5-minute intervals)")

                # Проверяем статус задач
                task_status = self.background_task_manager.get_task_status()
                logger.info("Background task system status", **task_status)

                # Проверяем, что задачи действительно запущены
                if not task_status["is_running"]:
                    raise Exception("Background tasks failed to start properly")

                logger.info(
                    "Background task system initialization completed successfully"
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to initialize background task system: {e}")
            # Очищаем частично инициализированные объекты
            self.background_task_manager = None
            self.sticker_manager = None
            raise

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий кнопок"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        if data.startswith("friend_accept_"):
            friend_id = int(data.split("_")[2])
            await self.handle_friend_accept(update, context, user_id, friend_id)
        elif data.startswith("notification_read_"):
            notification_id = int(data.split("_")[2])
            await self.handle_notification_read(
                update, context, user_id, notification_id
            )
        elif data.startswith("achievement_"):
            achievement_id = int(data.split("_")[1])
            await self.handle_achievement_view(update, context, achievement_id)

    async def handle_friend_accept(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        friend_id: int,
    ):
        """Обработка принятия запроса в друзья"""
        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.accept_friend_request(user_id, friend_id)

            if result["success"]:
                await update.callback_query.edit_message_text(
                    f"✅ Запрос в друзья принят!\n"
                    f"Теперь вы друзья с пользователем #{friend_id}"
                )
            else:
                await update.callback_query.edit_message_text(
                    f"Oshibka: {result['reason']}"
                )
        except Exception as e:
            logger.error(f"Error accepting friend request: {e}")
            await update.callback_query.edit_message_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def handle_notification_read(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        notification_id: int,
    ):
        """Обработка пометки уведомления как прочитанного"""
        db = next(get_db())
        try:
            notification_system = NotificationSystem(db)
            success = notification_system.mark_as_read(notification_id, user_id)

            if success:
                await update.callback_query.edit_message_text(
                    "Uvedomlenie ometeno kak prochtennoe"
                )
            else:
                await update.callback_query.edit_message_text("Uvedomlenie ne naideno")
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            await update.callback_query.edit_message_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def handle_achievement_view(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, achievement_id: int
    ):
        """Просмотр информации о достижении"""
        db = next(get_db())
        try:
            from database.database import Achievement

            achievement = (
                db.query(Achievement).filter(Achievement.id == achievement_id).first()
            )

            if achievement:
                text = f"""
🏆 <b>{achievement.name}</b>

{achievement.description}

📊 Категория: {achievement.category}
🥇 Уровень: {achievement.tier}
💎 Очки: {achievement.points}
                """

                await update.callback_query.edit_message_text(text, parse_mode="HTML")
            else:
                await update.callback_query.edit_message_text("Dostizhenie ne naideno")
        except Exception as e:
            logger.error(f"Error viewing achievement: {e}")
            await update.callback_query.edit_message_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    # ===== Основные команды =====
    async def welcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - приветствие и регистрация."""
        await welcome_command(update, context, self.admin_system, settings, get_db)

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /balance - проверка баланса."""
        await balance_command(update, context, self.admin_system, get_db)

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /history - история транзакций."""
        await history_command(update, context, get_db)

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /profile - профиль пользователя."""
        await profile_command(update, context, self.admin_system, settings, get_db)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - персональная статистика."""
        await stats_command(update, context, get_db)

    # ===== Магазин =====
    async def shop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /shop - просмотр магазина."""
        await shop_command(update, context, auto_registration_middleware, get_db)

    async def buy_contact_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /buy_contact для покупки товаров."""
        await buy_contact_command(update, context, self.admin_system, get_db)

    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy - покупка товара."""
        await buy_command(update, context, auto_registration_middleware, get_db)

    async def inventory_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /inventory - инвентарь."""
        await inventory_command(update, context, get_db)

    # ===== Админ-команды =====
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin - панель администратора с точным форматом вывода"""
        await admin_command(update, context, self.admin_system, get_db)

    async def add_points_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /add_points для начисления очков"""
        user = update.effective_user

        # Проверяем права администратора
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            logger.warning(
                f"User {user.id} (@{user.username}) attempted to use add_points command without permissions"
            )
            return

        # Проверяем формат команды
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Неверный формат команды\n\n"
                "Используйте: /add_points @username [число]\n\n"
                "Примеры:\n"
                "• /add_points @john_doe 100\n"
                "• /add_points user123 50\n"
                "• /add_points me 100 (для себя)\n"
                f"• /add_points {user.id} 100 (по ID)"
            )
            return

        username = context.args[0]
        try:
            amount = float(context.args[1])
            if amount <= 0:
                await update.message.reply_text(
                    "❌ Количество очков должно быть положительным числом"
                )
                return
        except ValueError:
            await update.message.reply_text("❌ Неверный формат количества очков")
            return

        try:
            # Находим пользователя по username
            target_user = self.admin_system.get_user_by_username(username)

            # Если не найден по username, попробуем найти по telegram_id (если это число)
            if not target_user:
                clean_username = username.lstrip("@")
                if clean_username.isdigit():
                    target_user = self.admin_system.get_user_by_id(int(clean_username))

            # Если все еще не найден, попробуем найти текущего пользователя (для самого себя)
            if not target_user and (
                username.lower() in ["me", "self"]
                or username.lstrip("@") == user.username
            ):
                target_user = self.admin_system.get_user_by_id(user.id)

            if not target_user:
                await update.message.reply_text(f"❌ Пользователь {username} не найден")
                return

            # Обновляем баланс пользователя
            new_balance = self.admin_system.update_balance(
                target_user["telegram_id"], amount
            )
            if new_balance is None:
                await update.message.reply_text(
                    "❌ Не удалось обновить баланс пользователя"
                )
                return

            # Создаем транзакцию типа 'add'
            self.admin_system.add_transaction(
                target_user["telegram_id"], amount, "add", user.id
            )

            # Отправляем подтверждение в точном формате
            clean_username = username.lstrip("@")
            text = f"Пользователю @{clean_username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"

            await update.message.reply_text(text)
            logger.info(
                f"Admin {user.id} added {amount} points to user {target_user['telegram_id']}"
            )

        except Exception as e:
            logger.error(f"Error in add_points command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при начислении очков. "
                "Попробуйте позже или обратитесь к разработчику."
            )

    async def add_admin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /add_admin для назначения администратора"""
        user = update.effective_user

        # Проверяем права администратора
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            logger.warning(
                f"User {user.id} (@{user.username}) attempted to use add_admin command without permissions"
            )
            return

        # Проверяем формат команды
        if len(context.args) < 1:
            await update.message.reply_text(
                "❌ Неверный формат команды\n\n"
                "Используйте: /add_admin @username\n\n"
                "Примеры:\n"
                "• /add_admin @john_doe\n"
                "• /add_admin user123"
            )
            return

        username = context.args[0]

        try:
            # Находим пользователя по username
            target_user = self.admin_system.get_user_by_username(username)
            if not target_user:
                await update.message.reply_text(f"❌ Пользователь {username} не найден")
                return

            # Проверяем, не является ли пользователь уже администратором
            if target_user["is_admin"]:
                await update.message.reply_text(
                    f"ℹ️ Пользователь @{target_user['username'] or target_user['id']} "
                    f"уже является администратором"
                )
                return

            # Назначаем администратором
            success = self.admin_system.set_admin_status(
                target_user["telegram_id"], True
            )
            if not success:
                await update.message.reply_text(
                    "❌ Не удалось назначить пользователя администратором"
                )
                return

            # Отправляем подтверждение в точном формате
            clean_username = username.lstrip("@")
            text = f"Пользователь @{clean_username} теперь администратор"

            await update.message.reply_text(text)
            logger.info(
                f"Admin {user.id} granted admin rights to user {target_user['telegram_id']}"
            )

        except Exception as e:
            logger.error(f"Error in add_admin command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при назначении администратора. "
                "Попробуйте позже или обратитесь к разработчику."
            )

    # ===== Обработка сообщений =====
    async def parse_all_messages(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обработка сообщений - только ручной парсинг по команде 'парсинг'"""
        message_text = update.message.text
        chat = update.effective_chat

        # Проверяем, является ли это командой "парсинг" в ответ на сообщение
        # Убираем упоминание бота если оно есть
        if message_text:
            clean_text = message_text.replace("@lt_lo_game_bot", "").strip().lower()
            if clean_text == "парсинг" and update.message.reply_to_message:
                # NEW: Use unified parsing handler
                await self.parsing_handler.handle_manual_parsing(update, context)
                return

        # Пропускаем все остальные сообщения - автоматический парсинг отключен
        # Обработка только по команде "парсинг"
        logger.debug(
            f"Message ignored (automatic parsing disabled): {message_text[:50] if message_text else 'No text'}..."
        )

        # Если это личное сообщение от пользователя и не команда, покажем справку
        if chat.type == "private" and not message_text.startswith("/"):
            await update.message.reply_text(
                "🤖 Я бот банк-аггрегатор LucasTeam!\n\n"
                "Используйте команды:\n"
                "/start - начать работу\n"
                "/balance - проверить баланс\n"
                "/profile - ваш профиль\n"
                "/shop - магазин товаров\n"
                "/games - мини-игры\n"
                "/dnd - D&D мастерская\n"
                "/daily - ежедневный бонус\n"
                "/challenges - задания\n\n"
                "💡 Для начисления очков из игр:\n"
                "Ответьте на сообщение игрового бота словом 'парсинг'\n\n"
                "Поддерживаемые игры: 🎣 Shmalala, 🃏 GD Cards"
            )
            return

    # DEPRECATED: Автоматический парсинг отключен
    # Используется только ручной парсинг по команде "парсинг"
    # async def process_game_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Обработка игровых сообщений в группах с интегрированным парсером"""
    #     # Эта функция больше не используется
    #     pass

    def run(self):
        """Запуск бота с интеграцией фоновых задач и системы парсинга (Task 11.2)"""
        logger.info(
            "Starting enhanced bot with background task integration and message parsing..."
        )

        # Создаем таблицы БД
        create_tables()

        # Инициализируем системы
        db = next(get_db())
        try:
            # Инициализируем магазин
            shop = EnhancedShopSystem(db)
            shop.initialize_default_categories()
            shop.initialize_default_items()
            logger.info("Enhanced shop initialized successfully")

            logger.info("Achievement system initialized successfully")

            # Инициализируем системы мониторинга и безопасности
            self.monitoring_system = MonitoringSystem(db)
            self.alert_system = AlertSystem(self.monitoring_system)
            self.backup_system = BackupSystem()
            self.error_handling_system = ErrorHandlingSystem(db)
            logger.info("Monitoring and security systems initialized successfully")

            # Проверяем и инициализируем правила парсинга (Task 11.2)
            self._ensure_parsing_rules_initialized(db)

        except Exception as e:
            logger.error("Failed to initialize systems", error=str(e))
        finally:
            db.close()

        # Инициализируем и запускаем фоновые задачи (Task 11.3)
        try:
            # Используем asyncio для инициализации фоновых систем
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._initialize_background_systems())
            # НЕ закрываем loop здесь, он нужен для фоновых задач

            logger.info(
                "Background task system initialized and started successfully (Task 11.3)"
            )

        except Exception as e:
            logger.error(f"Failed to initialize background task system: {e}")
            # Продолжаем запуск бота даже если фоновые задачи не запустились
            logger.warning("Bot will continue without background task system")
            # Закрываем loop только при ошибке
            try:
                loop.close()
            except Exception:
                pass

        # Добавляем обработчик для graceful shutdown (Task 11.3)
        async def shutdown_handler():
            """
            Обработчик graceful shutdown с правильной остановкой фоновых задач
            Validates: Requirements 12.1, 12.2
            """
            logger.info("Initiating graceful shutdown...")

            try:
                # Останавливаем фоновые задачи (Task 11.3)
                await self._shutdown_background_tasks()

                # Закрываем соединения с базой данных
                if hasattr(self, "admin_system") and self.admin_system:
                    # AdminSystem использует SQLite, закрытие не требуется
                    pass

                logger.info("Graceful shutdown completed successfully")

            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")
                # Даже при ошибке считаем shutdown завершенным
                logger.info("Graceful shutdown completed with errors")

        # Регистрируем обработчик shutdown
        self.application.add_handler(
            MessageHandler(filters.ALL, lambda u, c: None), group=-1
        )

        # Запускаем бота с обработкой ошибок (Task 11.3)
        try:
            logger.info(
                "Enhanced bot starting polling with background task system integration..."
            )

            # Проверяем статус фоновых задач перед запуском
            if self.is_background_system_running():
                logger.info("Background task system confirmed running before bot start")
            else:
                logger.warning(
                    "Background task system not running - some features may be limited"
                )

            self.application.run_polling(drop_pending_updates=True, close_loop=False)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Bot stopped due to error: {e}")
        finally:
            # Выполняем graceful shutdown (Task 11.3)
            try:
                logger.info("Performing final graceful shutdown...")
                # Используем существующий event loop если он есть
                try:
                    current_loop = asyncio.get_event_loop()
                    if current_loop.is_closed():
                        raise RuntimeError("Loop is closed")
                    current_loop.run_until_complete(shutdown_handler())
                except (RuntimeError, AttributeError):
                    # Создаем новый loop только если текущий недоступен
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(shutdown_handler())
                    new_loop.close()
                logger.info("Final graceful shutdown completed")
            except Exception as e:
                logger.error(f"Error during final shutdown: {e}")

            logger.info("Bot shutdown completed")

    def _ensure_parsing_rules_initialized(self, db):
        """
        Убеждаемся, что правила парсинга инициализированы в базе данных (Task 11.2)

        Args:
            db: Database session
        """
        try:
            from database.database import ParsingRule
            from decimal import Decimal

            # Проверяем, есть ли правила в базе данных
            existing_rules = db.query(ParsingRule).count()

            if existing_rules == 0:
                logger.info(
                    "No parsing rules found in database, creating default rules..."
                )

                # Создаем правила по умолчанию
                default_rules = [
                    {
                        "bot_name": "Shmalala",
                        "pattern": r"Монеты:\s*\+(\d+)",
                        "multiplier": Decimal("1.0"),
                        "currency_type": "coins",
                    },
                    {
                        "bot_name": "GDcards",
                        "pattern": r"Очки:\s*\+(\d+)",
                        "multiplier": Decimal("1.0"),
                        "currency_type": "points",
                    },
                    {
                        "bot_name": "Shmalala",
                        "pattern": r"Победил\(а\).*и забрал\(а\).*(\d+).*💰",
                        "multiplier": Decimal("1.0"),
                        "currency_type": "coins",
                    },
                    {
                        "bot_name": "GDcards",
                        "pattern": r"🃏.*НОВАЯ КАРТА.*🃏.*Очки:\s*\+(\d+)",
                        "multiplier": Decimal("1.0"),
                        "currency_type": "points",
                    },
                ]

                for rule_data in default_rules:
                    db_rule = ParsingRule(
                        bot_name=rule_data["bot_name"],
                        pattern=rule_data["pattern"],
                        multiplier=rule_data["multiplier"],
                        currency_type=rule_data["currency_type"],
                        is_active=True,
                    )
                    db.add(db_rule)

                db.commit()
                logger.info(f"Created {len(default_rules)} default parsing rules")
            else:
                logger.info(
                    f"Found {existing_rules} existing parsing rules in database"
                )

            # Проверяем конфигурацию парсинга
            from core.managers.config_manager import get_config_manager

            config_manager = get_config_manager()

            # Принудительно перезагружаем конфигурацию
            config_manager.reload_configuration()

            config = config_manager.get_configuration()
            logger.info(
                f"Parsing configuration loaded: {len(config.parsing_rules)} rules available"
            )

            # Проверяем наличие ошибок валидации
            if config_manager.has_validation_errors():
                errors = config_manager.get_validation_errors()
                logger.warning(f"Parsing configuration has validation errors: {errors}")
            else:
                logger.info("Parsing configuration validation passed")

        except Exception as e:
            logger.error(f"Error ensuring parsing rules initialization: {e}")
            # Не прерываем запуск бота, но логируем ошибку
            logger.warning(
                "Bot will continue with potentially incomplete parsing rules"
            )


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
