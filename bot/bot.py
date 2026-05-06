# bot.py - Объединенный Telegram-бот банк-аггрегатора LucasTeam
import logging
import asyncio
import signal
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from database.database import get_db
from database.schema import ensure_schema_up_to_date
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
    ping_command,
    test_notify_command,
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
    notify_status_command,
    notifications_command,
    notifications_clear_command,
    test_adb_command,
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
from bot.template_coder import TemplateCoderDialog
from core.managers.background_task_manager import BackgroundTaskManager
from core.managers.sticker_manager import StickerManager
from bot.handlers import ParsingHandler  # NEW: Unified parsing handler
import structlog


POLLING_RETRY_DELAY_SECONDS = 5

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = structlog.get_logger()


def _normalize_bot_command(message_text: str | None) -> str:
    """Normalize command text by stripping bot mention and arguments."""
    if not message_text:
        return ""

    command = message_text.strip().split(maxsplit=1)[0]
    return command.split("@", maxsplit=1)[0].lower()


def _extract_bot_mentioned_command(message_text: str | None, bot_username: str | None) -> str:
    """Extract command addressed to this bot via /command@username syntax."""
    if not message_text or not bot_username:
        return ""

    command = message_text.strip().split(maxsplit=1)[0]
    if "@" not in command:
        return ""

    base_command, mentioned_username = command.split("@", maxsplit=1)
    if mentioned_username.lower() != bot_username.lstrip("@").lower():
        return ""

    return base_command.lower()


class TelegramBot:
    def __init__(self):
        builder = Application.builder().token(settings.BOT_TOKEN)
        
        # Настройка прокси и таймаутов
        proxy = settings.PROXY_URL
        # Не используем локальный прокси на Hugging Face (определяем по USER=bot в Docker или отсутствию порта 1080)
        if proxy and not (os.environ.get("SPACE_ID") and "127.0.0.1" in proxy):
            builder.proxy_url(proxy)
            builder.get_updates_proxy_url(proxy)
            logger.info(f"Using proxy: {proxy}")
        
        # Увеличиваем таймауты для облачного хостинга
        builder.read_timeout(60)
        builder.connect_timeout(60)
        builder.write_timeout(60)
        builder.pool_timeout(60)
        
        self.application = builder.build()

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

        # M01: диалоговый кодер текстовых шаблонов
        self.template_coder_dialog = TemplateCoderDialog()

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
            CommandHandler("ping", ping_command),
            CommandHandler("test_notify", test_notify_command),
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
            CommandHandler("notify_status", notify_status_command),
            CommandHandler("test_adb", test_adb_command),
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
            # Диалоговый кодер шаблонов
            CommandHandler("coder", self.template_coder_dialog.start_command),
            CommandHandler("reset", self.template_coder_dialog.reset_command),
            CommandHandler("help", self.template_coder_dialog.help_command),
        ]

        for handler in handlers:
            self.application.add_handler(handler)
            logger.info(f"Added handler: {handler.callback.__name__}")

        # Обработка колбэков
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Явный fallback для команд с упоминанием бота (/start@bot_username)
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self.handle_mentioned_commands)
        )

        # Обработка всех сообщений
        self.application.add_handler(
            MessageHandler(filters.ALL, self.log_all_updates), group=-2
        )
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.parse_all_messages)
        )

        logger.info("All enhanced handlers set up successfully")

    async def log_all_updates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Логирование абсолютно всех входящих обновлений для отладки групп"""
        chat = update.effective_chat
        user = update.effective_user
        
        chat_id = chat.id if chat else "unknown"
        chat_type = chat.type if chat else "unknown"
        user_id = user.id if user else "unknown"
        
        text = "No text"
        if update.message and update.message.text:
            text = update.message.text
        elif update.callback_query:
            text = f"Callback: {update.callback_query.data}"
            
        logger.info(f"DEBUG: Update from {chat_type} ({chat_id}), User {user_id}: {text[:50]}")

    def run(self):
        """Запуск бота с интеграцией фоновых задач и системы парсинга (Task 11.2)"""
        logger.info(
            "Starting enhanced bot with background task integration and message parsing..."
        )

        # Приводим схему БД к актуальному состоянию перед инициализацией систем.
        ensure_schema_up_to_date()

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

            while not self._shutdown_requested:
                try:
                    logger.info("Starting run_polling with 60s timeout...")
                    self.application.run_polling(
                        drop_pending_updates=True,
                        close_loop=False,
                        read_timeout=60,
                        connect_timeout=60,
                        allowed_updates=Update.ALL_TYPES
                    )
                    break
                except (TimedOut, NetworkError) as e:
                    logger.warning(
                        "Polling interrupted by network error, retrying...",
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay_seconds=POLLING_RETRY_DELAY_SECONDS,
                    )
                    if self._shutdown_requested:
                        break
                    time.sleep(POLLING_RETRY_DELAY_SECONDS)
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
