# bot.py - Объединенный Telegram-бот банк-аггрегатора LucasTeam
import logging
import asyncio
import os
import signal
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

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
from database.database import User, get_db, engine
from database.schema import ensure_schema_up_to_date
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
from bot.commands.ai_commands import (
    ai_command,
    ai_help_command,
    ai_update_knowledge_command,
    handle_ai_feedback_reply,
)
from bot.commands.feedback_commands import feedback_command, feedback_list_command
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
from bot.commands.notification_commands_ptb import notifications_command, notifications_clear_command
from bot.commands.achievements_commands_ptb import achievements_command
from bot.commands.admin_commands_ptb import (
    admin_command as admin_command_handler,
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
    admin_health_command,
    admin_errors_command,
    admin_backup_command,
    admin_parsing_reload_command,
    admin_parsing_config_command,
)
from bot.template_coder import TemplateCoderDialog
from bot.trivia.commands import trivia_command, trivia_callback_handler
from bot.short_mode import long_all_command, long_command, short_all_command, short_command
from core.managers.background_task_manager import BackgroundTaskManager
from core.managers.sticker_manager import StickerManager
from bot.handlers import ParsingHandler  # NEW: Unified parsing handler
import structlog


POLLING_RETRY_DELAY_SECONDS = 5
TELEGRAM_DEFAULT_BASE_URL = "https://api.telegram.org/bot/"
STICKER_LIMIT_PER_HOUR = 5
STICKER_LIMIT_WINDOW_SECONDS = 60 * 60
HF_WEBHOOK_DISABLED_COMMANDS = {
    "shop",
    "buy_contact",
    "buy",
    "buy_1",
    "buy_2",
    "buy_3",
    "buy_4",
    "buy_5",
    "buy_6",
    "buy_7",
    "buy_8",
    "inventory",
    "games",
    "play",
    "join",
    "startgame",
    "turn",
    "dnd",
    "dnd_create",
    "dnd_join",
    "dnd_roll",
    "dnd_sessions",
    "notify_status",
    "test_adb",
    "admin_shop_add",
    "admin_shop_edit",
    "admin_games_stats",
    "admin_reset_game",
    "admin_ban_player",
    "admin_background_status",
    "admin_background_health",
    "admin_background_restart",
    "add_item",
}

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


def _mask_proxy_url(proxy_url: str) -> str:
    """Mask proxy credentials before logging."""
    parsed = urlparse(proxy_url)
    if not parsed.password:
        return proxy_url

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    username = parsed.username or ""
    netloc = f"{username}:***@{host}"
    return parsed._replace(netloc=netloc).geturl()


def is_hf_webhook_runtime() -> bool:
    """Return true for the reduced Hugging Face webhook production runtime."""
    return os.environ.get("WEBHOOK_MODE") == "1" or bool(os.environ.get("SPACE_ID"))


def get_db_session():
    """Return one SQLAlchemy session for legacy command handlers that expect get_db()."""
    return next(get_db())


class TelegramBot:
    def __init__(self):
        builder = self._create_application_builder()
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
        self._last_sticker_warning_sent = {}

        # NEW: Инициализация обработчика парсинга
        # Vercel serverless has a read-only filesystem; parsing's legacy
        # SQLiteRepository opens data/bot.db during construction.  Keep parsing
        # disabled there until the parser repository is fully PostgreSQL-backed.
        if os.environ.get("VERCEL"):
            self.parsing_handler = None
            logger.info("Parsing handler disabled for Vercel serverless runtime")
        else:
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

    def _create_application_builder(self):
        """Create PTB ApplicationBuilder with HF-safe network settings."""
        token = settings.BOT_TOKEN.strip()
        builder = Application.builder().token(token)

        if os.environ.get("SPACE_ID"):
            # Hugging Face needs longer timeouts for Telegram API
            builder.read_timeout(120)
            builder.connect_timeout(60)
            builder.write_timeout(60)
            builder.pool_timeout(60)
            builder.get_updates_read_timeout(120)
            builder.get_updates_connect_timeout(60)
            builder.get_updates_write_timeout(60)
            builder.get_updates_pool_timeout(60)
        else:
            builder.read_timeout(75)
            builder.connect_timeout(30)
            builder.write_timeout(45)
            builder.pool_timeout(30)
            builder.get_updates_read_timeout(90)
            builder.get_updates_connect_timeout(30)
            builder.get_updates_write_timeout(45)
            builder.get_updates_pool_timeout(30)

        base_url = os.environ.get("TELEGRAM_BASE_URL") or getattr(
            settings,
            "TELEGRAM_BASE_URL",
            TELEGRAM_DEFAULT_BASE_URL,
        )
        base_url = base_url.strip()
        if not base_url.endswith("/"):
            base_url = f"{base_url}/"

        if os.environ.get("SPACE_ID"):
            logger.info(
                "Configuring Telegram client for Hugging Face",
                base_url=base_url,
                proxy_configured=bool(settings.PROXY_URL),
            )

        if base_url != TELEGRAM_DEFAULT_BASE_URL:
            builder.base_url(base_url)
            logger.info("Using custom Telegram base_url", base_url=base_url)

        proxy = settings.PROXY_URL
        if proxy:
            builder.proxy_url(proxy)
            builder.get_updates_proxy_url(proxy)
            logger.info("Using Telegram proxy", proxy=_mask_proxy_url(proxy))

        return builder

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

        hf_webhook_runtime = is_hf_webhook_runtime()

        # Основные команды
        handlers = [
            CommandHandler("start", self.welcome_command),
            CommandHandler("ping", ping_command),
            CommandHandler("test_notify", test_notify_command),
            CommandHandler("balance", self.balance_command),
            CommandHandler("history", self.history_command),
            CommandHandler("profile", self.profile_command),
            CommandHandler("user", self.profile_command),
            CommandHandler("stats", self.stats_command),
            CommandHandler("ai", ai_command),
            CommandHandler("ask", ai_command),
            CommandHandler("ai_help", ai_help_command),
            CommandHandler(
                "ai_update_knowledge",
                lambda update, context: ai_update_knowledge_command(
                    update,
                    context,
                    self.admin_system,
                ),
            ),
            CommandHandler("feedback", feedback_command),
            CommandHandler("suggest", feedback_command),
            CommandHandler("complaint", feedback_command),
            CommandHandler(
                "feedback_list",
                lambda update, context: feedback_list_command(
                    update,
                    context,
                    settings.ADMIN_TELEGRAM_ID,
                ),
            ),
            # Мотивация
            CommandHandler("daily", daily_bonus_command),
            CommandHandler("bonus", daily_bonus_command),
            CommandHandler("challenges", challenges_command),
            CommandHandler("streak", motivation_stats_command),
            # Достижения и уведомления
            CommandHandler(
                "achievements",
                lambda update, context: achievements_command(update, context, get_db),
            ),
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
            CommandHandler("admin", self.admin_command),
            CommandHandler("add_points", self.add_points_command),
            CommandHandler("add_coins", self.add_points_command),
            CommandHandler("add_admin", self.add_admin_command),
            CommandHandler(
                "admin_stats",
                lambda update, context: admin_stats_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_adjust",
                lambda update, context: admin_adjust_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_addcoins",
                lambda update, context: admin_addcoins_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_removecoins",
                lambda update, context: admin_removecoins_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_merge",
                lambda update, context: admin_merge_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_transactions",
                lambda update, context: admin_transactions_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_transaction",
                lambda update, context: admin_transactions_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_balances",
                lambda update, context: admin_balances_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_users",
                lambda update, context: admin_users_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_rates",
                lambda update, context: admin_rates_command(update, context, self.admin_system),
            ),
            CommandHandler(
                "admin_rate",
                lambda update, context: admin_rate_command(update, context, self.admin_system),
            ),
            CommandHandler(
                "admin_cleanup",
                lambda update, context: admin_cleanup_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_health",
                lambda update, context: admin_health_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_errors",
                lambda update, context: admin_errors_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_backup",
                lambda update, context: admin_backup_command(update, context, self.admin_system, get_db_session),
            ),
            # Advanced Admin Commands (Task 7.4 and 8.3)
            CommandHandler(
                "parsing_stats", self.advanced_admin_commands.parsing_stats_command
            ),
            CommandHandler("broadcast", self.advanced_admin_commands.broadcast_command),
            CommandHandler(
                "user_stats", self.advanced_admin_commands.user_stats_command
            ),
            # Message Parsing Configuration Commands (Task 11.2)
            CommandHandler(
                "admin_parsing_reload",
                lambda update, context: admin_parsing_reload_command(update, context, self.admin_system, get_db_session),
            ),
            CommandHandler(
                "admin_parsing_config",
                lambda update, context: admin_parsing_config_command(update, context, self.admin_system, get_db_session),
            ),
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
            # Краткий режим обычных меню, не режим часов и не кодер.
            CommandHandler("short", short_command),
            CommandHandler("short_all", short_all_command),
            CommandHandler("long", long_command),
            CommandHandler("long_all", long_all_command),
            CommandHandler("reset", self.template_coder_dialog.reset_command),
            CommandHandler("done", self.template_coder_dialog.done_command),
            CommandHandler("help", self.template_coder_dialog.help_command),
            # Викторина по канону
            CommandHandler("trivia", trivia_command),
        ]

        if hf_webhook_runtime:
            for command in sorted(HF_WEBHOOK_DISABLED_COMMANDS):
                handlers.append(CommandHandler(command, self.disabled_in_hf_webhook_command))
            logger.info(
                "HF webhook runtime: disabled shop/games/dnd/watch-realtime/background handlers",
                disabled_commands=sorted(HF_WEBHOOK_DISABLED_COMMANDS),
            )
        else:
            from bot.commands.admin_commands_ptb import (
                admin_background_health_command,
                admin_background_restart_command,
                admin_background_status_command,
                admin_ban_player_command,
                admin_games_stats_command,
                admin_reset_game_command,
                admin_shop_add_command,
                admin_shop_edit_command,
            )
            from bot.commands.dnd_commands_ptb import (
                dnd_command,
                dnd_create_command,
                dnd_join_command,
                dnd_roll_command,
                dnd_sessions_command,
            )
            from bot.commands.game_commands_ptb import (
                game_turn_command,
                games_command,
                join_command,
                play_command,
                start_game_command,
            )
            from bot.commands.shop_commands_ptb import inventory_command
            from bot.commands.notification_commands_ptb import (
                notify_status_command,
                test_adb_command,
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

            handlers.extend(
                [
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
                    # Realtime/watch diagnostics
                    CommandHandler("notify_status", notify_status_command),
                    CommandHandler("test_adb", test_adb_command),
                    # Shop/game/background admin commands
                    CommandHandler("admin_shop_add", admin_shop_add_command),
                    CommandHandler("admin_shop_edit", admin_shop_edit_command),
                    CommandHandler("admin_games_stats", admin_games_stats_command),
                    CommandHandler("admin_reset_game", admin_reset_game_command),
                    CommandHandler("admin_ban_player", admin_ban_player_command),
                    CommandHandler("add_item", self.advanced_admin_commands.add_item_command),
                    CommandHandler("admin_background_status", admin_background_status_command),
                    CommandHandler("admin_background_health", admin_background_health_command),
                    CommandHandler("admin_background_restart", admin_background_restart_command),
                ]
            )

        for handler in handlers:
            self.application.add_handler(handler)
            logger.info(f"Added handler: {handler.callback.__name__}")

        # Обработка колбэков
        self.application.add_handler(CallbackQueryHandler(trivia_callback_handler, pattern="^trivia:"))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Явный fallback для команд с упоминанием бота (/start@bot_username)
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self.handle_mentioned_commands)
        )

        # Обработка всех сообщений
        self.application.add_handler(
            MessageHandler(filters.Sticker.ALL, self.moderate_sticker_message), group=-3
        )
        self.application.add_handler(
            MessageHandler(filters.ALL, self.log_all_updates), group=-2
        )
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.parse_all_messages)
        )

        logger.info("All enhanced handlers set up successfully")

    async def moderate_sticker_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Удалять стикеры сверх лимита 5 стикеров в час на пользователя в чате."""
        from sqlalchemy import text

        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat

        if not message or not user or not chat or not message.sticker:
            return

        now = datetime.utcnow()
        window_start = now - timedelta(seconds=STICKER_LIMIT_WINDOW_SECONDS)

        try:
            with engine.begin() as conn:
                unlimited_until = conn.execute(
                    text(
                        """
                        SELECT sticker_unlimited_until
                        FROM users
                        WHERE telegram_id = :telegram_id
                          AND sticker_unlimited = TRUE
                          AND sticker_unlimited_until > :now
                        """
                    ),
                    {"telegram_id": user.id, "now": now},
                ).scalar_one_or_none()
                if unlimited_until is not None:
                    logger.debug(
                        "Sticker moderation skipped: unlimited access active",
                        chat_id=chat.id,
                        user_id=user.id,
                        expires_at=str(unlimited_until),
                    )
                    return

                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sticker_usage_events (
                            id SERIAL PRIMARY KEY,
                            chat_id BIGINT NOT NULL,
                            user_id BIGINT NOT NULL,
                            message_id BIGINT NOT NULL,
                            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS idx_sticker_usage_chat_user_created
                        ON sticker_usage_events (chat_id, user_id, created_at)
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        DELETE FROM sticker_usage_events
                        WHERE created_at < :cleanup_before
                        """
                    ),
                    {"cleanup_before": now - timedelta(hours=2)},
                )
                recent_count = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM sticker_usage_events
                        WHERE chat_id = :chat_id
                          AND user_id = :user_id
                          AND created_at >= :window_start
                        """
                    ),
                    {
                        "chat_id": chat.id,
                        "user_id": user.id,
                        "window_start": window_start,
                    },
                ).scalar_one()

                if recent_count < STICKER_LIMIT_PER_HOUR:
                    conn.execute(
                        text(
                            """
                            INSERT INTO sticker_usage_events
                                (chat_id, user_id, message_id, created_at)
                            VALUES
                                (:chat_id, :user_id, :message_id, :created_at)
                            """
                        ),
                        {
                            "chat_id": chat.id,
                            "user_id": user.id,
                            "message_id": message.message_id,
                            "created_at": now,
                        },
                    )
                    return
        except Exception as e:
            logger.warning(
                "Sticker rate-limit DB check failed",
                chat_id=chat.id,
                user_id=user.id,
                message_id=message.message_id,
                error=str(e),
            )
            return

        try:
            await context.bot.delete_message(
                chat_id=chat.id,
                message_id=message.message_id,
            )
            logger.info(
                "Deleted sticker over hourly limit",
                chat_id=chat.id,
                user_id=user.id,
                message_id=message.message_id,
                limit=STICKER_LIMIT_PER_HOUR,
            )
            
            # Send warning at most once per 60 seconds per user in chat
            now_mono = time.monotonic()
            last_warning_time = self._last_sticker_warning_sent.get((chat.id, user.id), 0)
            if now_mono - last_warning_time >= 60:
                self._last_sticker_warning_sent[(chat.id, user.id)] = now_mono
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=(
                            f"⚠️ @{user.username or user.first_name}, <b>превышен лимит стикеров!</b>\n\n"
                            f"Вы можете отправлять не более {STICKER_LIMIT_PER_HOUR} стикеров в час.\n"
                            "🛒 Купите <b>Безлимит стикеров на 24 часа</b> в магазине (/shop), чтобы снять это ограничение!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as msg_err:
                    logger.warning("Failed to send sticker warning message", error=str(msg_err))
        except Exception as e:
            logger.warning(
                "Failed to delete sticker over hourly limit",
                chat_id=chat.id,
                user_id=user.id,
                message_id=message.message_id,
                error=str(e),
            )

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO sticker_usage_events
                            (chat_id, user_id, message_id, created_at)
                        VALUES
                            (:chat_id, :user_id, :message_id, :created_at)
                        """
                    ),
                    {
                        "chat_id": chat.id,
                        "user_id": user.id,
                        "message_id": message.message_id,
                        "created_at": now,
                    },
                )
        except Exception as e:
            logger.warning(
                "Failed to record deleted sticker usage",
                chat_id=chat.id,
                user_id=user.id,
                message_id=message.message_id,
                error=str(e),
            )

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
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            logger.info("Signal handlers configured for graceful shutdown")
        except ValueError:
            # Webhook runtime runs in a daemon thread where signals are unavailable
            logger.info("Signal handlers skipped: not in main thread (webhook mode)")

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
        self.template_coder_dialog.reset_state(context)
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

    async def disabled_in_hf_webhook_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Reply for commands intentionally disabled in HF webhook production."""
        await update.message.reply_text(
            "Эта команда отключена в стабильном HF webhook-режиме. "
            "Доступны: /start, /user, /profile, /balance, /history, /stats, "
            "/short, /long, /feedback и безопасный reply-парсинг словом «парсинг»."
        )

    # ===== Магазин =====
    async def shop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /shop - просмотр магазина."""
        from bot.commands.shop_commands_ptb import shop_command

        await shop_command(update, context, auto_registration_middleware, get_db)

    async def buy_contact_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /buy_contact для покупки товаров."""
        from bot.commands.shop_commands_ptb import buy_contact_command

        await buy_contact_command(update, context, self.admin_system, get_db)

    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy - покупка товара."""
        from bot.commands.shop_commands_ptb import buy_command

        await buy_command(update, context, auto_registration_middleware, get_db)

    async def inventory_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /inventory - инвентарь."""
        from bot.commands.shop_commands_ptb import inventory_command

        await inventory_command(update, context, get_db)

    # ===== Админ-команды =====
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin - панель администратора с точным форматом вывода"""
        await admin_command_handler(update, context, self.admin_system, get_db)

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
                "Используйте: /add_points @username [число] [комментарий]\n\n"
                "Примеры:\n"
                "• /add_points @john_doe 100\n"
                "• /add_points @john_doe 100 бонус за помощь\n"
                "• /add_points user123 50\n"
                "• /add_points me 100 (для себя)\n"
                f"• /add_points {user.id} 100 (по ID)"
            )
            return

        username = context.args[0]
        comment = " ".join(context.args[2:]).strip()
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
                target_user["telegram_id"],
                amount,
                "add",
                user.id,
                comment or None,
            )

            # Отправляем подтверждение в точном формате
            clean_username = username.lstrip("@")
            text = f"Пользователю @{clean_username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"
            if comment:
                text += f"\nКомментарий: {comment}"

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
            if clean_text == "парсинг":
                if self.parsing_handler is None:
                    await self.handle_serverless_manual_parsing(update, context)
                    return
                # NEW: Use unified parsing handler
                await self.parsing_handler.handle_manual_parsing(update, context)
                return

        # Пропускаем все остальные сообщения
        # Обработка только по команде "парсинг"
        logger.debug(
            f"Message ignored (ordinary text message): {message_text[:50] if message_text else 'No text'}..."
        )

        if await self.template_coder_dialog.handle_text(update, context):
            return

        # Если это личное сообщение от пользователя и не команда, покажем справку
        if chat.type == "private" and not message_text.startswith("/"):
            await update.message.reply_text(
                "🤖 Я бот банк-аггрегатор LucasTeam!\n\n"
                "Используйте команды:\n"
                "/start - начать работу\n"
                "/balance - проверить баланс\n"
                "/profile - ваш профиль\n"
                "/history - история транзакций\n"
                "/stats - статистика\n\n"
                "💡 Для начисления очков из игр:\n"
                "Ответьте на сообщение игрового бота словом 'парсинг'\n\n"
                "Поддерживаемые игры: 🎣 Shmalala, 🃏 GD Cards"
            )
            return

    async def handle_serverless_manual_parsing(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Serverless-safe reply parsing using PostgreSQL-backed ParsingService."""

        from bank_bot.services.parsing_service import ParsingService
        from database.database import SessionLocal

        message = update.effective_message
        user = update.effective_user

        if not message or not user:
            return

        replied_message = message.reply_to_message
        message_text = ""
        if replied_message:
            message_text = replied_message.text or replied_message.caption or ""

        if not message_text:
            await message.reply_text(
                "❌ Я не вижу сообщение, на которое вы ответили.\n\n"
                "Ответьте словом «Парсинг» именно на сообщение GDcards/Shmalala."
            )
            return

        db = SessionLocal()
        try:
            db_user = (
                db.query(User)
                .filter(User.telegram_id == user.id)
                .first()
            )
            if db_user is None:
                db_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    balance=0,
                    total_earned=0,
                    last_activity=datetime.utcnow(),
                )
                db.add(db_user)
                db.flush()
            else:
                db_user.username = user.username
                db_user.first_name = user.first_name
                db_user.last_name = user.last_name
                db_user.last_activity = datetime.utcnow()

            parsing_service = ParsingService(db)
            is_profile = parsing_service.detect_bot(message_text) is None
            if is_profile:
                success, response, details = parsing_service.parse_profile_and_accrue(
                    user_id=db_user.id,
                    text=message_text,
                )
            else:
                success, response, details = parsing_service.parse_and_accrue(
                    user_id=db_user.id,
                    text=message_text,
                )

            if success:
                db.commit()
                logger.info(
                    "Serverless parsing success",
                    telegram_id=user.id,
                    user_id=db_user.id,
                    details=details,
                )
                await message.reply_text(response)
                return

            db.rollback()
            logger.warning(
                "Serverless parsing failed",
                telegram_id=user.id,
                response=response,
                text_preview=message_text[:200],
            )
            await message.reply_text(f"❌ {response}")
        except Exception as e:
            db.rollback()
            logger.error("Serverless parsing error", error=str(e), exc_info=True)
            await message.reply_text("❌ Ошибка при обработке данных парсинга")
        finally:
            db.close()

    async def handle_mentioned_commands(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle commands addressed via /command@bot_username syntax."""
        message_text = update.effective_message.text if update.effective_message else None
        bot_username = settings.BOT_USERNAME or getattr(context.bot, "username", "")
        mentioned_command = _extract_bot_mentioned_command(
            message_text,
            bot_username,
        )

        if mentioned_command.lstrip("/") in HF_WEBHOOK_DISABLED_COMMANDS and is_hf_webhook_runtime():
            await self.disabled_in_hf_webhook_command(update, context)
        elif mentioned_command == "/start":
            await self.welcome_command(update, context)
        elif mentioned_command == "/coder":
            await self.template_coder_dialog.start_command(update, context)
        elif mentioned_command in ("/ai", "/ask"):
            await ai_command(update, context)
        elif mentioned_command == "/ai_help":
            await ai_help_command(update, context)
        elif mentioned_command == "/ai_update_knowledge":
            await ai_update_knowledge_command(update, context, self.admin_system)
        elif mentioned_command in ("/feedback", "/suggest", "/complaint"):
            await feedback_command(update, context)
        elif mentioned_command == "/feedback_list":
            await feedback_list_command(update, context, settings.ADMIN_TELEGRAM_ID)
        elif mentioned_command == "/admin":
            await self.admin_command(update, context)
        elif mentioned_command == "/short":
            await short_command(update, context)
        elif mentioned_command == "/short_all":
            await short_all_command(update, context)
        elif mentioned_command == "/long":
            await long_command(update, context)
        elif mentioned_command == "/long_all":
            await long_all_command(update, context)
        elif mentioned_command in ("/profile", "/user"):
            await self.profile_command(update, context)
        elif mentioned_command == "/balance":
            await self.balance_command(update, context)
        elif mentioned_command == "/history":
            await self.history_command(update, context)
        elif mentioned_command == "/stats":
            await self.stats_command(update, context)
        elif mentioned_command == "/help":
            await self.template_coder_dialog.help_command(update, context)
        elif mentioned_command == "/reset":
            await self.template_coder_dialog.reset_command(update, context)
        elif mentioned_command == "/done":
            await self.template_coder_dialog.done_command(update, context)
        elif mentioned_command == "/trivia":
            await trivia_command(update, context)

    # DEPRECATED: Автоматический парсинг отключен
    # Используется только ручной парсинг по команде "парсинг"
    # async def process_game_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Обработка игровых сообщений в группах с интегрированным парсером"""
    #     # Эта функция больше не используется
    #     pass

    async def log_all_updates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Логирование абсолютно всех входящих обновлений для отладки групп"""
        if update.message and await handle_ai_feedback_reply(update, context):
            return

        chat = update.effective_chat
        user = update.effective_user
        
        chat_id = chat.id if chat else "unknown"
        chat_type = chat.type if chat else "unknown"
        user_id = user.id if user else "unknown"
        
        text = "No text/Other update"
        if update.message and update.message.text:
            text = update.message.text
        elif update.callback_query:
            text = f"Callback: {update.callback_query.data}"
            
        logger.info(f"DEBUG: Update from {chat_type} ({chat_id}), User {user_id}: {text[:50]}")

    def initialize_runtime_systems(
        self,
        *,
        start_background_tasks: bool = True,
        initialize_shop: bool = True,
    ):
        """Initialize one-shot runtime systems before polling or webhook processing."""
        logger.info(
            "Initializing bot runtime systems",
            start_background_tasks=start_background_tasks,
            initialize_shop=initialize_shop,
        )

        # Инициализируем системы
        db = next(get_db())
        try:
            # Инициализируем магазин
            if initialize_shop:
                from core.systems.shop_system import EnhancedShopSystem

                shop = EnhancedShopSystem(db)
                shop.initialize_default_categories()
                shop.initialize_default_items()
                logger.info("Enhanced shop initialized successfully")
            else:
                logger.info("Enhanced shop initialization skipped for webhook runtime")

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
        if not start_background_tasks:
            logger.info("Background task system disabled for webhook runtime")
            return

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

    async def initialize_for_webhook(self, webhook_url: str, webhook_secret: str) -> None:
        """Prepare PTB Application for custom Flask webhook processing."""
        self.initialize_runtime_systems(
            start_background_tasks=False,
            initialize_shop=False,
        )
        # Retry initialization for HF network reliability
        for attempt in range(1, 4):
            try:
                await self.application.initialize()
                await self.application.start()
                break
            except TimedOut:
                logger.warning(f"Webhook init timed out (attempt {attempt}/3), retrying...")
                if attempt == 3:
                    raise
                await asyncio.sleep(5)
        await self.application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
            secret_token=webhook_secret,
        )
        webhook_info = await self.application.bot.get_webhook_info()
        logger.info(
            "Telegram webhook configured",
            webhook_url=webhook_url,
            pending_update_count=webhook_info.pending_update_count,
            last_error_message=webhook_info.last_error_message,
            allowed_updates=webhook_info.allowed_updates,
        )

    async def shutdown_for_webhook(self) -> None:
        """Stop custom webhook PTB Application cleanly."""
        await self._shutdown_background_tasks()
        await self.application.stop()
        await self.application.shutdown()

    def run(self):
        """Запуск бота с интеграцией фоновых задач и системы парсинга (Task 11.2)"""
        logger.info(
            "Starting enhanced bot with background task integration and message parsing..."
        )

        self.initialize_runtime_systems(
            start_background_tasks=True,
            initialize_shop=True,
        )

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
                    logger.info("Starting run_polling with HF-safe timeouts...")
                    logger.info(f"Bot token configured: {settings.BOT_TOKEN[:15]}...")

                    logger.info("Starting polling loop...")

                    # Запускаем polling
                    polling_kwargs = {
                        "drop_pending_updates": False,
                        "close_loop": False,
                        "allowed_updates": Update.ALL_TYPES,
                        "timeout": 60,
                        "read_timeout": 75,
                        "write_timeout": 45,
                        "connect_timeout": 30,
                        "pool_timeout": 30,
                    }

                    self.application.run_polling(**polling_kwargs)
                    logger.info("Polling started successfully!")
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
