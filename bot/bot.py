# bot.py - Объединенный Telegram-бот банк-аггрегатора LucasTeam
import logging
import asyncio
import signal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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
from core.managers.background_task_manager import BackgroundTaskManager
from core.managers.sticker_manager import StickerManager
from bot.handlers import ParsingHandler  # NEW: Unified parsing handler
import structlog

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
            return task_status.get('is_running', False)
            
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
        self.application.add_handler(
            TypeHandler(Update, track_user_activity),
            group=-1
        )
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
            CommandHandler("buy_1", self.buy_1_command),
            CommandHandler("buy_2", self.buy_2_command),
            CommandHandler("buy_3", self.buy_3_command),
            CommandHandler("buy_4", self.buy_4_command),
            CommandHandler("buy_5", self.buy_5_command),
            CommandHandler("buy_6", self.buy_6_command),
            CommandHandler("buy_7", self.buy_7_command),
            CommandHandler("buy_8", self.buy_8_command),
            CommandHandler("inventory", self.inventory_command),

            # Мини-игры
            CommandHandler("games", self.games_command),
            CommandHandler("play", self.play_command),
            CommandHandler("join", self.join_command),
            CommandHandler("startgame", self.start_game_command),
            CommandHandler("turn", self.game_turn_command),

            # D&D
            CommandHandler("dnd", self.dnd_command),
            CommandHandler("dnd_create", self.dnd_create_command),
            CommandHandler("dnd_join", self.dnd_join_command),
            CommandHandler("dnd_roll", self.dnd_roll_command),
            CommandHandler("dnd_sessions", self.dnd_sessions_command),

            # Мотивация
            CommandHandler("daily", self.daily_bonus_command),
            CommandHandler("bonus", self.daily_bonus_command),
            CommandHandler("challenges", self.challenges_command),
            CommandHandler("streak", self.motivation_stats_command),

            # Достижения и уведомления
            CommandHandler("achievements", self.achievements_command),
            CommandHandler("notifications", self.notifications_command),
            CommandHandler("notifications_clear", self.notifications_clear_command),

            # Социальные функции
            CommandHandler("friends", self.friends_command),
            CommandHandler("friend_add", self.friend_add_command),
            CommandHandler("friend_accept", self.friend_accept_command),
            CommandHandler("gift", self.gift_command),
            CommandHandler("clan", self.clan_command),
            CommandHandler("clan_create", self.clan_create_command),
            CommandHandler("clan_join", self.clan_join_command),
            CommandHandler("clan_leave", self.clan_leave_command),

            # Админ-команды
            CommandHandler("admin", self.admin_command),
            CommandHandler("add_points", self.add_points_command),
            CommandHandler("add_admin", self.add_admin_command),
            CommandHandler("admin_stats", self.admin_stats_command),
            CommandHandler("admin_adjust", self.admin_adjust_command),
            CommandHandler("admin_addcoins", self.admin_addcoins_command),
            CommandHandler("admin_removecoins", self.admin_removecoins_command),
            CommandHandler("admin_merge", self.admin_merge_command),
            CommandHandler("admin_transactions", self.admin_transactions_command),
            CommandHandler("admin_transaction", self.admin_transactions_command),  # Алиас
            CommandHandler("admin_balances", self.admin_balances_command),
            CommandHandler("admin_users", self.admin_users_command),
            CommandHandler("admin_rates", self.admin_rates_command),
            CommandHandler("admin_rate", self.admin_rate_command),
            CommandHandler("admin_cleanup", self.admin_cleanup_command),
            CommandHandler("admin_shop_add", self.admin_shop_add_command),
            CommandHandler("admin_shop_edit", self.admin_shop_edit_command),
            CommandHandler("admin_games_stats", self.admin_games_stats_command),
            CommandHandler("admin_reset_game", self.admin_reset_game_command),
            CommandHandler("admin_ban_player", self.admin_ban_player_command),
            CommandHandler("admin_health", self.admin_health_command),
            CommandHandler("admin_errors", self.admin_errors_command),
            CommandHandler("admin_backup", self.admin_backup_command),
            
            # Advanced Admin Commands (Task 7.4 and 8.3)
            CommandHandler("parsing_stats", self.advanced_admin_commands.parsing_stats_command),
            CommandHandler("broadcast", self.advanced_admin_commands.broadcast_command),
            CommandHandler("user_stats", self.advanced_admin_commands.user_stats_command),
            CommandHandler("add_item", self.advanced_admin_commands.add_item_command),
            
            # Background Task Management Commands (Task 10.3)
            CommandHandler("admin_background_status", self.admin_background_status_command),
            CommandHandler("admin_background_health", self.admin_background_health_command),
            CommandHandler("admin_background_restart", self.admin_background_restart_command),
            
            # Message Parsing Configuration Commands (Task 11.2)
            CommandHandler("admin_parsing_reload", self.admin_parsing_reload_command),
            CommandHandler("admin_parsing_config", self.admin_parsing_config_command),
            
            # Configuration Management Commands (Full Set)
            CommandHandler("reload_config", config_commands.reload_config_handler),
            CommandHandler("config_status", config_commands.config_status_handler),
            CommandHandler("list_parsing_rules", config_commands.list_parsing_rules_handler),
            CommandHandler("add_parsing_rule", config_commands.add_parsing_rule_handler),
            CommandHandler("update_parsing_rule", config_commands.update_parsing_rule_handler),
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
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.parse_all_messages
        ))

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
            if hasattr(self, 'application') and self.application:
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
                if task_status['is_running']:
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
                self.background_task_manager = BackgroundTaskManager(db, self.sticker_manager)
                logger.info("BackgroundTaskManager initialized successfully")
                
                # Запускаем периодические задачи очистки (Requirement 12.1)
                await self.background_task_manager.start_periodic_cleanup()
                logger.info("Periodic cleanup tasks started (5-minute intervals)")
                
                # Проверяем статус задач
                task_status = self.background_task_manager.get_task_status()
                logger.info("Background task system status", **task_status)
                
                # Проверяем, что задачи действительно запущены
                if not task_status['is_running']:
                    raise Exception("Background tasks failed to start properly")
                
                logger.info("Background task system initialization completed successfully")
                
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

        if data.startswith('friend_accept_'):
            friend_id = int(data.split('_')[2])
            await self.handle_friend_accept(update, context, user_id, friend_id)
        elif data.startswith('notification_read_'):
            notification_id = int(data.split('_')[2])
            await self.handle_notification_read(update, context, user_id, notification_id)
        elif data.startswith('achievement_'):
            achievement_id = int(data.split('_')[1])
            await self.handle_achievement_view(update, context, achievement_id)

    async def handle_friend_accept(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   user_id: int, friend_id: int):
        """Обработка принятия запроса в друзья"""
        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.accept_friend_request(user_id, friend_id)

            if result['success']:
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

    async def handle_notification_read(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       user_id: int, notification_id: int):
        """Обработка пометки уведомления как прочитанного"""
        db = next(get_db())
        try:
            notification_system = NotificationSystem(db)
            success = notification_system.mark_as_read(notification_id, user_id)

            if success:
                await update.callback_query.edit_message_text("Uvedomlenie ometeno kak prochtennoe")
            else:
                await update.callback_query.edit_message_text("Uvedomlenie ne naideno")
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            await update.callback_query.edit_message_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def handle_achievement_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      achievement_id: int):
        """Просмотр информации о достижении"""
        db = next(get_db())
        try:
            from database.database import Achievement
            achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()

            if achievement:
                text = f"""
🏆 <b>{achievement.name}</b>

{achievement.description}

📊 Категория: {achievement.category}
🥇 Уровень: {achievement.tier}
💎 Очки: {achievement.points}
                """

                await update.callback_query.edit_message_text(text, parse_mode='HTML')
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

    async def buy_contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_contact для покупки товаров."""
        await buy_contact_command(update, context, self.admin_system, get_db)
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy - покупка товара."""
        await buy_command(update, context, auto_registration_middleware, get_db)

    async def buy_1_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_1 - покупка первого товара."""
        await _handle_purchase_command(update, context, 1, auto_registration_middleware, get_db)

    async def buy_2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_2 - покупка второго товара."""
        await _handle_purchase_command(update, context, 2, auto_registration_middleware, get_db)

    async def buy_3_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_3 - покупка третьего товара."""
        await _handle_purchase_command(update, context, 3, auto_registration_middleware, get_db)

    async def buy_4_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_4 - покупка четвертого товара."""
        await _handle_purchase_command(update, context, 4, auto_registration_middleware, get_db)

    async def buy_5_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_5 - покупка пятого товара."""
        await _handle_purchase_command(update, context, 5, auto_registration_middleware, get_db)

    async def buy_6_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_6 - покупка шестого товара."""
        await _handle_purchase_command(update, context, 6, auto_registration_middleware, get_db)

    async def buy_7_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_7 - покупка седьмого товара."""
        await _handle_purchase_command(update, context, 7, auto_registration_middleware, get_db)

    async def buy_8_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_8 - покупка восьмого товара."""
        await _handle_purchase_command(update, context, 8, auto_registration_middleware, get_db)

    async def inventory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /inventory - инвентарь."""
        await inventory_command(update, context, get_db)

    # ===== Мини-игры =====
    async def games_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /games - информация о мини-играх"""
        text = """
[GAME] <b>Мини-игры</b>

Доступные игры:

1. <b>[CITY] Города</b>
   • Классическая игра в города
   • Назовите город на последнюю букву предыдущего
   • Награда: 5 монет за ход
   • Команды: /play cities

2. <b>[KNIFE] Слова, которые могут убить</b>
   • Придумывайте "убийственные" слова
   • Слова связанные с оружием, ядами и т.д.
   • Награда: до 15 монет за слово
   • Команды: /play killer_words

3. <b>[MUSIC] Уровни GD</b>
   • Аналог игры в города, но с уровнями Geometry Dash
   • Награда: 5 монет за ход
   • Команды: /play gd_levels

[NOTE] <b>Как играть:</b>
1. Создайте игру: /play <тип_игры>
2. Другие игроки присоединяются: /join <id_игры>
3. Начинайте игру: /startgame <id_игры>
4. Делайте ходы: /turn <ваш_ход>

[TARGET] <b>Текущие активные игры:</b>
   /games_list - список активных игр
        """

        await update.message.reply_text(text, parse_mode='HTML')

    async def play_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /play - создание игры"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "Ukazhite tip igry:\n"
                "/play cities\n"
                "/play killer_words\n"
                "/play gd_levels"
            )
            return

        game_type = context.args[0].lower()
        valid_games = ['cities', 'killer_words', 'gd_levels']

        if game_type not in valid_games:
            await update.message.reply_text(
                f"Neizvestnyy tip igry. Dostupnye: {', '.join(valid_games)}"
            )
            return

        db = next(get_db())
        try:
            games = GamesSystem(db)
            session = games.create_game_session(game_type, user.id)

            text = f"""
[GAME] <b>Игра создана!</b>

Тип игры: {game_type}
ID игры: {session.id}
Создатель: {user.first_name}

[PEOPLE] Другие игроки могут присоединиться:
/join {session.id}

[PLAY] Чтобы начать игру:
/startgame {session.id}
            """

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /join - присоединение к игре"""
        user = update.effective_user

        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Ispolzuyte: /join <id_igry>")
            return

        session_id = int(context.args[0])

        db = next(get_db())
        try:
            games = GamesSystem(db)
            success = games.join_game_session(session_id, user.id)

            if success:
                await update.message.reply_text(
                    f"✅ Вы присоединились к игре #{session_id}\n"
                    f"Ожидайте начала игры от создателя."
                )
            else:
                await update.message.reply_text(
                    "Ne udalos prisoyedinit k igre. Vozmozhnye prichiny:\n"
                    "• Igra uzhe nachalas\n"
                    "• Vy uzhe uchastvuyete v igre\n"
                    "• Dostignut limit igrokov\n"
                    "• Igra ne naidena"
                )
        except Exception as e:
            logger.error(f"Error in join command: {e}")
            await update.message.reply_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def start_game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /startgame - начало игры"""
        user = update.effective_user

        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Ispolzuyte: /startgame <id_igry>")
            return

        session_id = int(context.args[0])

        db = next(get_db())
        try:
            games = GamesSystem(db)
            success = games.start_game_session(session_id, user.id)

            if success:
                session_info = games.get_game_session_info(session_id)
                if session_info:
                    current_player = next(
                        (p for p in session_info['players'] if p['user_id'] == session_info['current_player_id']),
                        None
                    )

                    if current_player:
                        text = f"""
[GAME] <b>Игра #{session_id} началась!</b>

Тип игры: {session_info['game_type']}
Текущий игрок: Пользователь #{current_player['user_id']}
Количество игроков: {len(session_info['players'])}

[TIP] Текущий игрок может сделать ход:
/turn {session_id} <ваш_ход>
                        """

                        await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(
                    "Ne udalos nachat igru. Vozmozhnye prichiny:\n"
                    "• Vy ne sozdatel igry\n"
                    "• Igra uzhe nachalas\n"
                    "• Nedostatochno igrokov (minimum 2)\n"
                    "• Igra ne naidena"
                )
        except Exception as e:
            logger.error(f"Error in startgame command: {e}")
            await update.message.reply_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def game_turn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /turn - сделать ход в игре"""
        user = update.effective_user

        if len(context.args) < 2:
            await update.message.reply_text("Ispolzuyte: /turn <id_igry> <vash_khod>")
            return

        try:
            session_id = int(context.args[0])
            turn_input = ' '.join(context.args[1:])
        except ValueError:
            await update.message.reply_text("Nevernyy format komandy")
            return

        db = next(get_db())
        try:
            games = GamesSystem(db)
            session_info = games.get_game_session_info(session_id)

            if not session_info or session_info['status'] != 'active':
                await update.message.reply_text("Igra ne aktivna ili ne naidena")
                return

            if session_info['current_player_id'] != user.id:
                await update.message.reply_text("Seichas ne vash khod")
                return

            # Обработка хода в зависимости от типа игры
            if session_info['game_type'] == 'cities':
                result = games.process_cities_turn(session_id, user.id, turn_input)
            elif session_info['game_type'] == 'killer_words':
                result = games.process_killer_words_turn(session_id, user.id, turn_input)
            elif session_info['game_type'] == 'gd_levels':
                result = games.process_gd_levels_turn(session_id, user.id, turn_input)
            else:
                await update.message.reply_text("Neizvestnyy tip igry")
                return

            if result['success']:
                next_player = result.get('next_player_id')
                reward = result.get('reward', 0)

                text = f"""
[OK] <b>Ход принят!</b>

Ваш ход: {turn_input}
{'[KNIFE] Это убийственное слово!' if result.get('is_killer') else ''}
{'[MUSIC] Уровень принят!' if session_info['game_type'] == 'gd_levels' else ''}

[MONEY] Награда: {reward} монет
[USER] Следующий игрок: Пользователь #{next_player}

[TIP] Следующий игрок делает ход:
/turn {session_id} <ход>
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"{result.get('reason', 'Oshibka pri obrabotke khoda')}")
        except Exception as e:
            logger.error(f"Error in turn command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== D&D =====
    async def dnd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dnd - информация о D&D системе"""
        text = """
[DICE] <b>D&D Мастерская</b>

Система для проведения настольных ролевых игр в Telegram.

[LIST] <b>Основные команды:</b>

1. <b>Создание сессии:</b>
   /dnd_create <название> [описание] - создать новую сессию

2. <b>Присоединение к сессии:</b>
   /dnd_join <id_сессии> - присоединиться к сессии
   /dnd_sessions - список доступных сессий

3. <b>Управление персонажем:</b>
   /dnd_character_create - создать персонажа
   /dnd_character <id> - информация о персонаже

4. <b>Бросок кубиков:</b>
   /dnd_roll <тип> [модификатор] [цель] - бросок кубиков
   Пример: /dnd_roll d20+5 "Атака мечом"

5. <b>Для мастера:</b>
   /dnd_start <id_сессии> - начать сессию
   /dnd_quest <id_персонажа> <название> <описание> - создать квест

[TARGET] <b>Доступные кубики:</b>
   d4, d6, d8, d10, d12, d20, d100

[TIPS] <b>Советы:</b>
   • Мастер создает сессию и приглашает игроков
   • Игроки создают персонажей и присоединяются
   • Используйте бросок кубиков для определения успеха действий
   • Мастер создает квесты и награждает игроков
        """

        await update.message.reply_text(text, parse_mode='HTML')

    async def dnd_create_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dnd_create - создание D&D сессии"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "❌ Используйте: /dnd_create <название> [описание]\n"
                "Пример: /dnd_create \"Поход в подземелье\" \"Исследование древних руин\""
            )
            return

        name = context.args[0]
        description = ' '.join(context.args[1:]) if len(context.args) > 1 else None

        db = next(get_db())
        try:
            dnd = DndSystem(db)
            session = dnd.create_session(user.id, name, description)

            text = f"""
[DICE] <b>D&D сессия создана!</b>

Название: {name}
{'Описание: ' + description if description else ''}
ID сессии: {session.id}
Мастер: {user.first_name}
Максимум игроков: {session.max_players}

[PEOPLE] Игроки могут присоединиться:
/dnd_join {session.id}

[PLAY] Чтобы начать сессию:
/dnd_start {session.id}
            """

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in dnd_create command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def dnd_join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dnd_join - присоединение к D&D сессии"""
        user = update.effective_user

        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Используйте: /dnd_join <id_сессии>")
            return

        session_id = int(context.args[0])

        db = next(get_db())
        try:
            dnd = DndSystem(db)
            success = dnd.join_session(session_id, user.id)

            if success:
                session_info = dnd.get_session_info(session_id)
                if session_info:
                    text = f"""
✅ <b>Вы присоединились к D&D сессии!</b>

Название: {session_info['name']}
ID сессии: {session_info['id']}
Мастер: Пользователь #{session_info['master_id']}
Игроков: {session_info['current_players']}/{session_info['max_players']}

💡 Создайте персонажа:
/dnd_character_create {session_id} <имя> <класс>
                    """

                    await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(
                    "❌ Не удалось присоединиться к сессии. Возможные причины:\n"
                    "• Сессия уже началась\n"
                    "• Достигнут лимит игроков\n"
                    "• Вы уже участвуете в сессии\n"
                    "• Сессия не найдена"
                )
        except Exception as e:
            logger.error(f"Error in dnd_join command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def dnd_sessions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dnd_sessions - список D&D сессий"""
        user = update.effective_user

        db = next(get_db())
        try:
            dnd = DndSystem(db)
            sessions = dnd.get_player_sessions(user.id)

            if not sessions:
                await update.message.reply_text("📭 Вы не участвуете ни в одной D&D сессии")
                return

            text = "[DICE] <b>Ваши D&D сессии</b>\n\n"

            for session in sessions:
                status_icon = {
                    'planning': '[LIST]',
                    'active': '[GAME]',
                    'completed': '[OK]'
                }.get(session['status'], '[QUESTION]')

                text += f"{status_icon} <b>{session['name']}</b>\n"
                text += f"   ID: {session['id']}\n"
                text += f"   Статус: {session['status']}\n"
                text += f"   Вы: {'Мастер' if session['is_master'] else 'Игрок'}\n"
                text += f"   Создана: {session['created_at'].strftime('%d.%m.%Y')}\n\n"

            text += "[TIP] Присоединиться к сессии: /dnd_join <id>"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in dnd_sessions command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def dnd_roll_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /dnd_roll - бросок кубиков"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "❌ Используйте: /dnd_roll <тип_кубика> [модификатор] [цель]\n"
                "Примеры:\n"
                "/dnd_roll d20\n"
                "/dnd_roll d20+5\n"
                "/dnd_roll 2d6+3 \"Урон мечом\"\n"
                "/dnd_roll d100 \"Шанс удачи\""
            )
            return

        dice_input = context.args[0]
        purpose = ' '.join(context.args[1:]) if len(context.args) > 1 else None

        # Парсим ввод кубиков
        try:
            if 'd' not in dice_input:
                raise ValueError("Неверный формат кубика")

            # Удаляем пробелы
            dice_input = dice_input.replace(' ', '')

            # Парсим количество кубиков
            if dice_input[0].isdigit():
                dice_count_str = ''
                i = 0
                while i < len(dice_input) and dice_input[i].isdigit():
                    dice_count_str += dice_input[i]
                    i += 1
                dice_count = int(dice_count_str)
                dice_type = dice_input[i:]
            else:
                dice_count = 1
                dice_type = dice_input

            # Парсим модификатор
            modifier = 0
            if '+' in dice_type:
                dice_type, modifier_str = dice_type.split('+')
                modifier = int(modifier_str)
            elif '-' in dice_type:
                dice_type, modifier_str = dice_type.split('-')
                modifier = -int(modifier_str)

            # Валидация типа кубика
            valid_dice = ['d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100']
            if dice_type not in valid_dice:
                raise ValueError(f"Неверный тип кубика. Доступные: {', '.join(valid_dice)}")

            if dice_count < 1 or dice_count > 100:
                raise ValueError("Количество кубиков должно быть от 1 до 100")

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка парсинга: {str(e)}")
            return

        db = next(get_db())
        try:
            # Для простоты используем первую активную сессию пользователя
            dnd = DndSystem(db)
            sessions = dnd.get_player_sessions(user.id)

            active_session = next((s for s in sessions if s['status'] == 'active'), None)

            if not active_session:
                await update.message.reply_text(
                    "❌ У вас нет активных D&D сессий.\n"
                    "Сначала присоединитесь к сессии: /dnd_join <id>"
                )
                return

            # Бросаем кубики
            import random
            results = []
            for _ in range(dice_count):
                max_value = int(dice_type[1:])
                results.append(random.randint(1, max_value))

            result = sum(results)
            total = result + modifier

            # Формируем сообщение
            text = f"""
[DICE] <b>Бросок кубиков</b>

Игрок: {user.first_name}
Кубики: {dice_count}{dice_type}
{'Модификатор: ' + ('+' if modifier >= 0 else '') + str(modifier) if modifier != 0 else ''}
{'Цель: ' + purpose if purpose else ''}

[STATS] <b>Результаты:</b>
   • Выпавшие значения: {', '.join(map(str, results))}
   • Сумма: {result}
   • {'С модификатором: ' + str(total) if modifier != 0 else ''}

[TARGET] <b>Итог:</b> {total}
            """

            await update.message.reply_text(text, parse_mode='HTML')

        except Exception as e:
            logger.error(f"Error in dnd_roll command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== Мотивационная система =====
    async def daily_bonus_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /daily - ежедневный бонус"""
        user = update.effective_user

        db = next(get_db())
        try:
            motivation = MotivationSystem(db)
            result = motivation.claim_daily_bonus(user.id)

            if result['success']:
                text = f"""
[GIFT] <b>Ежедневный бонус получен!</b>

[MONEY] Начислено: {result['amount']} банковских монет
[FIRE] Текущий стрик: {result['streak']} дней
[CHART] Следующий множитель: {result['next_multiplier']}x

[TIP] Возвращайтесь завтра для получения следующего бонуса!
                """

                # Отправляем уведомление
                notification_system = NotificationSystem(db)
                notification_system.send_system_notification(
                    user.id,
                    "🎁 Ежедневный бонус",
                    f"Вы получили ежедневный бонус: {result['amount']} монет\n"
                    f"Текущий стрик: {result['streak']} дней"
                )
            else:
                text = f"❌ {result['reason']}"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in daily bonus command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def challenges_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /challenges - еженедельные задания"""
        user = update.effective_user

        db = next(get_db())
        try:
            motivation = MotivationSystem(db)
            challenges = motivation.get_weekly_challenges(user.id)

            text = f"""
[TARGET] <b>Еженедельные задания</b> (Неделя {challenges['week']})

"""
            for challenge in challenges['challenges']:
                text += f"🏆 <b>{challenge['name']}</b>\n"
                text += f"   {challenge['description']}\n"
                text += f"   📊 Прогресс: {challenge['progress']}/{challenge['target']}\n"
                text += f"   💰 Награда: {challenge['reward']} монет\n\n"

            text += "💡 Выполняйте задания для получения дополнительных наград!"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in challenges command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def motivation_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /streak - статистика мотивации"""
        user = update.effective_user

        db = next(get_db())
        try:
            motivation = MotivationSystem(db)
            stats = motivation.get_user_motivation_stats(user.id)

            text = f"""
[STATS] <b>Ваша мотивационная статистика</b>

[FIRE] Текущий стрик: {stats['current_streak']} дней
[GIFT] Статус бонуса: {'[YES] Доступен' if stats['can_claim_today'] else '[NO] Уже получен'}

"""
            if stats['can_claim_today']:
                text += f"[MONEY] Следующий бонус: {stats['next_bonus_amount']} монет\n"
                text += f"[CHART] Множитель: {stats['next_multiplier']}x\n"
                text += "\n[TIP] Используйте /daily для получения бонуса!"
            else:
                text += f"⏰ Последний бонус: {stats['last_bonus_date'].strftime('%d.%m.%Y') if stats['last_bonus_date'] else 'Никогда'}\n"
                text += "\n[TIP] Возвращайтесь завтра для нового бонуса!"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in motivation stats command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== Достижения =====
    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /achievements - достижения"""
        user = update.effective_user

        db = next(get_db())
        try:
            achievement_system = AchievementSystem(db)
            user_achievements = achievement_system.get_user_achievements(user.id)
            available_achievements = achievement_system.get_available_achievements(user.id)

            text = f"""
[TROPHY] <b>Ваши достижения</b>

[STATS] Общая статистика:
   • Получено достижений: {user_achievements['total_achievements']}
   • Накоплено очков: {user_achievements['total_points']}
   • Доступно для получения: {available_achievements['total_available']}

"""
            # Последние полученные достижения
            if user_achievements['unlocked']:
                text += "[MEDAL] <b>Последние достижения:</b>\n\n"
                for ach in user_achievements['unlocked'][:3]:
                    tier_icon = {
                        'bronze': '[BRONZE]',
                        'silver': '[SILVER]',
                        'gold': '[GOLD]'
                    }.get(ach['tier'], '[MEDAL]')

                    text += f"{tier_icon} <b>{ach['name']}</b>\n"
                    text += f"   {ach['description']}\n"
                    text += f"   📅 {ach['unlocked_at']} | 💎 {ach['points']} очков\n\n"

            # Ближайшие к получению
            if available_achievements['available']:
                text += "[TARGET] <b>Ближайшие к получению:</b>\n\n"
                for ach in available_achievements['available'][:3]:
                    progress_bar = "▓" * (ach['progress_percentage'] // 10) + "░" * (
                                10 - (ach['progress_percentage'] // 10))
                    text += f"• {ach['name']}\n"
                    text += f"   {ach['description']}\n"
                    text += f"   📊 {progress_bar} {ach['progress_percentage']}%\n\n"

            text += "[TIP] Продолжайте активность, чтобы открыть новые достижения!"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in achievements command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== Уведомления =====
    async def notifications_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /notifications - уведомления"""
        user = update.effective_user

        db = next(get_db())
        try:
            notification_system = NotificationSystem(db)
            notifications = notification_system.get_user_notifications(user.id, unread_only=False, limit=10)
            unread_count = notification_system.get_unread_count(user.id)

            text = f"""
[BELL] <b>Ваши уведомления</b>

[INBOX] Непрочитанных: {unread_count}
[LIST] Всего показано: {len(notifications)}

"""
            if notifications:
                for notification in notifications:
                    status = "[YES]" if notification['is_read'] else "[NEW]"
                    created = notification['created_at'].strftime('%d.%m.%Y %H:%M')
                    text += f"{status} <b>{notification['title']}</b>\n"
                    text += f"   {notification['message'][:100]}...\n"
                    text += f"   📅 {created}\n\n"

                # Кнопки для управления уведомлениями
                keyboard = [
                    [InlineKeyboardButton("📋 Пометить все как прочитанные", callback_data="mark_all_read")],
                    [InlineKeyboardButton("🗑️ Очистить все", callback_data="clear_all")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)
            else:
                text += "[EMPTY] У вас нет уведомлений"
                await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in notifications command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def notifications_clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /notifications_clear - очистка уведомлений"""
        user = update.effective_user

        db = next(get_db())
        try:
            notification_system = NotificationSystem(db)
            cleared_count = notification_system.mark_all_as_read(user.id)

            text = f"""
✅ <b>Уведомления очищены</b>

🗑️ Помечено как прочитанные: {cleared_count} уведомлений

Теперь все ваши уведомления отмечены как прочитанные.
            """

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in notifications_clear command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== Социальные функции =====
    async def friends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /friends - список друзей"""
        user = update.effective_user

        db = next(get_db())
        try:
            social = SocialSystem(db)
            friends = social.get_friends(user.id)
            friend_requests = social.get_friend_requests(user.id)

            text = f"""
👥 <b>Ваши друзья</b>

📊 Статистика:
   • Друзей: {len(friends)}
   • Входящих запросов: {len(friend_requests)}

"""
            if friend_requests:
                text += "📩 <b>Входящие запросы:</b>\n"
                for req in friend_requests[:5]:  # Показываем первые 5
                    keyboard = [
                        [InlineKeyboardButton("✅ Принять", callback_data=f"friend_accept_{req['user_id']}"),
                         InlineKeyboardButton("❌ Отклонить", callback_data=f"friend_reject_{req['user_id']}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    request_text = f"""
👤 Пользователь: {req['first_name'] or f"#{req['user_id']}"}
{'@' + req['username'] if req['username'] else ''}
📅 Отправлен: {req['sent_at'].strftime('%d.%m.%Y %H:%M')}
                    """

                    await update.message.reply_text(request_text, reply_markup=reply_markup)
                text += "\n"

            if friends:
                text += "✅ <b>Ваши друзья:</b>\n"
                for friend in friends[:10]:  # Показываем первых 10
                    friend_name = friend['first_name'] or f"#{friend['id']}"
                    text += f"• {friend_name}\n"
                    text += f"  {'@' + friend['username'] if friend['username'] else ''}\n"
                    text += f"  💰 Баланс: {friend['balance']} монет\n"
                    text += f"  👥 Друзья с: {friend['friends_since'].strftime('%d.%m.%Y')}\n\n"
            else:
                text += "📭 У вас пока нет друзей\n"
                text += "💡 Добавьте друзей: /friend_add @username\n"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in friends command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def friend_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /friend_add - добавить друга"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "❌ Используйте: /friend_add <username или id>\n"
                "Примеры:\n"
                "/friend_add @username\n"
                "/friend_add Имя Фамилия\n"
                "/friend_add 123456789"
            )
            return

        friend_identifier = ' '.join(context.args)

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.send_friend_request(user.id, friend_identifier)

            if result['success']:
                await update.message.reply_text(
                    f"✅ Запрос на добавление в друзья отправлен!\n"
                    f"ID пользователя: {result['friend_id']}\n"
                    f"Ожидайте подтверждения."
                )
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in friend_add command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def friend_accept_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /friend_accept - принять запрос в друзья"""
        user = update.effective_user

        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ Используйте: /friend_accept <id_пользователя>")
            return

        friend_id = int(context.args[0])

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.accept_friend_request(user.id, friend_id)

            if result['success']:
                await update.message.reply_text(
                    f"✅ Запрос в друзья принят!\n"
                    f"Теперь вы друзья с пользователем #{friend_id}"
                )
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in friend_accept command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def gift_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /gift - отправить подарок"""
        user = update.effective_user

        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Используйте: /gift <получатель> <сумма> [сообщение]\n"
                "Примеры:\n"
                "/gift @username 100 \"С днем рождения!\"\n"
                "/gift Имя Фамилия 50\n"
                "/gift 123456789 200 \"Спасибо за помощь!\""
            )
            return

        receiver_identifier = context.args[0]

        try:
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except ValueError:
            await update.message.reply_text("❌ Неверная сумма")
            return

        message = ' '.join(context.args[2:]) if len(context.args) > 2 else None

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.send_gift(user.id, receiver_identifier, 'coins', amount, message)

            if result['success']:
                text = f"""
🎁 <b>Подарок отправлен!</b>

Получатель: Пользователь #{result['receiver_id']}
Сумма: {result['amount']} монет
{'Сообщение: ' + message if message else ''}

💡 Получатель получит уведомление о подарке.
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in gift command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def clan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clan - информация о клане"""
        user = update.effective_user

        db = next(get_db())
        try:
            social = SocialSystem(db)
            clan_info = social.get_user_clan(user.id)

            if clan_info:
                text = f"""
👥 <b>Ваш клан: {clan_info['name']}</b>

{'Описание: ' + clan_info['description'] if clan_info['description'] else ''}
Владелец: {clan_info['owner']['first_name'] or f"#{clan_info['owner']['id']}"}
{'@' + clan_info['owner']['username'] if clan_info['owner']['username'] else ''}
Участников: {clan_info['member_count']}
Общий баланс: {clan_info['total_balance']} монет
Создан: {clan_info['created_at'].strftime('%d.%m.%Y')}

📊 <b>Участники:</b>
"""
                for member in clan_info['members'][:10]:  # Показываем первых 10
                    role_icon = {
                        'owner': '👑',
                        'officer': '⭐',
                        'member': '👤'
                    }.get(member['role'], '👤')

                    member_name = member['first_name'] or f"#{member['id']}"
                    text += f"{role_icon} {member_name}\n"
                    text += f"   {'@' + member['username'] if member['username'] else ''}\n"
                    text += f"   Роль: {member['role']}\n"
                    text += f"   Баланс: {member['balance']} монет\n"
                    text += f"   В клане с: {member['joined_at'].strftime('%d.%m.%Y')}\n\n"

                if len(clan_info['members']) > 10:
                    text += f"... и еще {len(clan_info['members']) - 10} участников\n"

                text += "\n💡 Выйти из клана: /clan_leave"

            else:
                text = """
📭 <b>Вы не состоите в клане</b>

Клан - это группа игроков, объединенных общими целями.

🎯 <b>Преимущества клана:</b>
   • Общий чат и координация
   • Совместные мероприятия
   • Бонусы за активность клана
   • Рейтинги и достижения

💡 <b>Как вступить в клан:</b>
   1. Создайте свой клан: /clan_create <название> [описание]
   2. Или вступите в существующий: /clan_join <название_клана>

📋 <b>Список доступных кланов:</b>
   (Функция в разработке)
                """

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in clan command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def clan_create_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clan_create - создать клан"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "❌ Используйте: /clan_create <название> [описание]\n"
                "Пример: /clan_create \"Драконы Севера\" \"Самый сильный клан в королевстве\""
            )
            return

        name = context.args[0]
        description = ' '.join(context.args[1:]) if len(context.args) > 1 else None

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.create_clan(user.id, name, description)

            if result['success']:
                text = f"""
👑 <b>Клан создан!</b>

Название: {result['clan_name']}
ID клана: {result['clan_id']}
{'Описание: ' + description if description else ''}

🎯 Теперь вы владелец клана.
👥 Другие игроки могут присоединиться:
/clan_join {result['clan_name']}

💡 Управление кланом:
/clan - информация о клане
/clan_leave - покинуть клан (если вы владелец, клан удалится)
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in clan_create command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def clan_join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clan_join - вступить в клан"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text("❌ Используйте: /clan_join <название_клана>")
            return

        clan_name = ' '.join(context.args)

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.join_clan(user.id, clan_name)

            if result['success']:
                text = f"""
✅ <b>Вы вступили в клан!</b>

Название: {result['clan_name']}
ID клана: {result['clan_id']}

🎯 Теперь вы член клана.
💡 Информация о клане: /clan
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in clan_join command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def clan_leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /clan_leave - покинуть клан"""
        user = update.effective_user

        db = next(get_db())
        try:
            social = SocialSystem(db)
            result = social.leave_clan(user.id)

            if result['success']:
                if result['clan_name']:
                    text = f"""
👋 <b>Вы покинули клан</b>

Название: {result['clan_name']}

💡 Вы можете создать новый клан или вступить в другой.
                    """
                else:
                    text = "👋 <b>Вы покинули клан</b>"

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ {result['reason']}")
        except Exception as e:
            logger.error(f"Error in clan_leave command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    # ===== Админ-команды =====
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin - панель администратора с точным форматом вывода"""
        await admin_command(update, context, self.admin_system, get_db)

    async def add_points_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add_points для начисления очков"""
        user = update.effective_user
        
        # Проверяем права администратора
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            logger.warning(f"User {user.id} (@{user.username}) attempted to use add_points command without permissions")
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
                await update.message.reply_text("❌ Количество очков должно быть положительным числом")
                return
        except ValueError:
            await update.message.reply_text("❌ Неверный формат количества очков")
            return
        
        try:
            # Находим пользователя по username
            target_user = self.admin_system.get_user_by_username(username)
            
            # Если не найден по username, попробуем найти по telegram_id (если это число)
            if not target_user:
                clean_username = username.lstrip('@')
                if clean_username.isdigit():
                    target_user = self.admin_system.get_user_by_id(int(clean_username))
            
            # Если все еще не найден, попробуем найти текущего пользователя (для самого себя)
            if not target_user and (username.lower() in ['me', 'self'] or username.lstrip('@') == user.username):
                target_user = self.admin_system.get_user_by_id(user.id)
            
            if not target_user:
                await update.message.reply_text(f"❌ Пользователь {username} не найден")
                return
            
            # Обновляем баланс пользователя
            new_balance = self.admin_system.update_balance(target_user['telegram_id'], amount)
            if new_balance is None:
                await update.message.reply_text("❌ Не удалось обновить баланс пользователя")
                return
            
            # Создаем транзакцию типа 'add'
            self.admin_system.add_transaction(
                target_user['telegram_id'], amount, 'add', user.id
            )
            
            # Отправляем подтверждение в точном формате
            clean_username = username.lstrip('@')
            text = f"Пользователю @{clean_username} начислено {int(amount)} очков. Новый баланс: {int(new_balance)}"
            
            await update.message.reply_text(text)
            logger.info(f"Admin {user.id} added {amount} points to user {target_user['telegram_id']}")
            
        except Exception as e:
            logger.error(f"Error in add_points command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при начислении очков. "
                "Попробуйте позже или обратитесь к разработчику."
            )

    async def add_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add_admin для назначения администратора"""
        user = update.effective_user
        
        # Проверяем права администратора
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            logger.warning(f"User {user.id} (@{user.username}) attempted to use add_admin command without permissions")
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
            if target_user['is_admin']:
                await update.message.reply_text(
                    f"ℹ️ Пользователь @{target_user['username'] or target_user['id']} "
                    f"уже является администратором"
                )
                return
            
            # Назначаем администратором
            success = self.admin_system.set_admin_status(target_user['telegram_id'], True)
            if not success:
                await update.message.reply_text("❌ Не удалось назначить пользователя администратором")
                return
            
            # Отправляем подтверждение в точном формате
            clean_username = username.lstrip('@')
            text = f"Пользователь @{clean_username} теперь администратор"
            
            await update.message.reply_text(text)
            logger.info(f"Admin {user.id} granted admin rights to user {target_user['telegram_id']}")
            
        except Exception as e:
            logger.error(f"Error in add_admin command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при назначении администратора. "
                "Попробуйте позже или обратитесь к разработчику."
            )

    async def admin_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_stats - статистика системы"""
        await admin_stats_command(update, context, self.admin_system, get_db)

    async def admin_adjust_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_adjust - корректировка баланса"""
        await admin_adjust_command(update, context, self.admin_system, get_db)

    async def admin_addcoins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_addcoins - добавление монет пользователю"""
        await admin_addcoins_command(update, context, self.admin_system, get_db)

    async def admin_removecoins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_removecoins - удаление монет у пользователя"""
        await admin_removecoins_command(update, context, self.admin_system, get_db)

    async def admin_merge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_merge - объединение аккаунтов"""
        await admin_merge_command(update, context, self.admin_system, get_db)

    async def admin_transactions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_transactions - транзакции пользователя"""
        await admin_transactions_command(update, context, self.admin_system, get_db)

    async def admin_balances_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_balances - балансы всех пользователей (доступно всем)"""
        await admin_balances_command(update, context, self.admin_system, get_db)

    async def admin_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_users - список пользователей"""
        await admin_users_command(update, context, self.admin_system, get_db)

    async def admin_rates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_rates - коэффициенты конвертации"""
        await admin_rates_command(update, context, self.admin_system)

    async def admin_rate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_rate - изменение коэффициента"""
        await admin_rate_command(update, context, self.admin_system)

    async def admin_cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_cleanup - очистка системы"""
        await admin_cleanup_command(update, context, self.admin_system, get_db)

    async def admin_shop_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_shop_add - добавление товара (заглушка)"""
        await admin_shop_add_command(update, context, self.admin_system)

    async def admin_shop_edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_shop_edit - редактирование товара (заглушка)"""
        await admin_shop_edit_command(update, context, self.admin_system)

    async def admin_games_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_games_stats - статистика игр"""
        await admin_games_stats_command(update, context, self.admin_system, get_db)

    async def admin_reset_game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_reset_game - сброс игры (заглушка)"""
        await admin_reset_game_command(update, context, self.admin_system)

    async def admin_ban_player_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_ban_player - бан игрока (заглушка)"""
        await admin_ban_player_command(update, context, self.admin_system)

    async def admin_health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_health - здоровье системы"""
        await admin_health_command(update, context, self.admin_system, self.monitoring_system)

    async def admin_errors_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_errors - просмотр ошибок"""
        await admin_errors_command(update, context, self.admin_system, self.error_handling_system)

    async def admin_backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_backup - резервное копирование"""
        await admin_backup_command(update, context, self.admin_system, self.backup_system)

    # ===== Обработка сообщений =====
    async def parse_all_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений - только ручной парсинг по команде 'парсинг'"""
        message_text = update.message.text
        chat = update.effective_chat

        # Проверяем, является ли это командой "парсинг" в ответ на сообщение
        # Убираем упоминание бота если оно есть
        if message_text:
            clean_text = message_text.replace('@lt_lo_game_bot', '').strip().lower()
            if clean_text == "парсинг" and update.message.reply_to_message:
                # NEW: Use unified parsing handler
                await self.parsing_handler.handle_manual_parsing(update, context)
                return

        # Пропускаем все остальные сообщения - автоматический парсинг отключен
        # Обработка только по команде "парсинг"
        logger.debug(f"Message ignored (automatic parsing disabled): {message_text[:50] if message_text else 'No text'}...")
        
        # Если это личное сообщение от пользователя и не команда, покажем справку
        if chat.type == "private" and not message_text.startswith('/'):
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

    # ===== Background Task Management Commands =====
    @admin_required
    async def admin_background_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_background_status - статус фоновых задач"""
        await admin_background_status_command(update, context, self.admin_system, self.background_task_manager)

    @admin_required
    async def admin_background_health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_background_health - проверка здоровья фоновых задач"""
        await admin_background_health_command(update, context, self.admin_system, self.background_task_manager)

    @admin_required
    async def admin_background_restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_background_restart - перезапуск фоновых задач"""
        await admin_background_restart_command(update, context, self.admin_system, self.background_task_manager)

    # ===== Message Parsing Configuration Commands (Task 11.2) =====
    @admin_required
    async def admin_parsing_reload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_parsing_reload - перезагрузка правил парсинга"""
        await admin_parsing_reload_command(update, context, self.admin_system, self.message_parser)

    async def admin_parsing_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_parsing_config - просмотр конфигурации парсинга"""
        await admin_parsing_config_command(update, context, self.admin_system, get_db)

    def run(self):
        """Запуск бота с интеграцией фоновых задач и системы парсинга (Task 11.2)"""
        logger.info("Starting enhanced bot with background task integration and message parsing...")

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
            
            logger.info("Background task system initialized and started successfully (Task 11.3)")
            
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
                if hasattr(self, 'admin_system') and self.admin_system:
                    # AdminSystem использует SQLite, закрытие не требуется
                    pass
                
                logger.info("Graceful shutdown completed successfully")
                
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")
                # Даже при ошибке считаем shutdown завершенным
                logger.info("Graceful shutdown completed with errors")

        # Регистрируем обработчик shutdown
        self.application.add_handler(
            MessageHandler(filters.ALL, lambda u, c: None),
            group=-1
        )

        # Запускаем бота с обработкой ошибок (Task 11.3)
        try:
            logger.info("Enhanced bot starting polling with background task system integration...")
            
            # Проверяем статус фоновых задач перед запуском
            if self.is_background_system_running():
                logger.info("Background task system confirmed running before bot start")
            else:
                logger.warning("Background task system not running - some features may be limited")
            
            self.application.run_polling(
                drop_pending_updates=True,
                close_loop=False
            )
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
                logger.info("No parsing rules found in database, creating default rules...")
                
                # Создаем правила по умолчанию
                default_rules = [
                    {
                        'bot_name': 'Shmalala',
                        'pattern': r'Монеты:\s*\+(\d+)',
                        'multiplier': Decimal('1.0'),
                        'currency_type': 'coins'
                    },
                    {
                        'bot_name': 'GDcards',
                        'pattern': r'Очки:\s*\+(\d+)',
                        'multiplier': Decimal('1.0'),
                        'currency_type': 'points'
                    },
                    {
                        'bot_name': 'Shmalala',
                        'pattern': r'Победил\(а\).*и забрал\(а\).*(\d+).*💰',
                        'multiplier': Decimal('1.0'),
                        'currency_type': 'coins'
                    },
                    {
                        'bot_name': 'GDcards',
                        'pattern': r'🃏.*НОВАЯ КАРТА.*🃏.*Очки:\s*\+(\d+)',
                        'multiplier': Decimal('1.0'),
                        'currency_type': 'points'
                    }
                ]
                
                for rule_data in default_rules:
                    db_rule = ParsingRule(
                        bot_name=rule_data['bot_name'],
                        pattern=rule_data['pattern'],
                        multiplier=rule_data['multiplier'],
                        currency_type=rule_data['currency_type'],
                        is_active=True
                    )
                    db.add(db_rule)
                
                db.commit()
                logger.info(f"Created {len(default_rules)} default parsing rules")
            else:
                logger.info(f"Found {existing_rules} existing parsing rules in database")
            
            # Проверяем конфигурацию парсинга
            from core.managers.config_manager import get_config_manager
            config_manager = get_config_manager()
            
            # Принудительно перезагружаем конфигурацию
            config_manager.reload_configuration()
            
            config = config_manager.get_configuration()
            logger.info(f"Parsing configuration loaded: {len(config.parsing_rules)} rules available")
            
            # Проверяем наличие ошибок валидации
            if config_manager.has_validation_errors():
                errors = config_manager.get_validation_errors()
                logger.warning(f"Parsing configuration has validation errors: {errors}")
            else:
                logger.info("Parsing configuration validation passed")
                
        except Exception as e:
            logger.error(f"Error ensuring parsing rules initialization: {e}")
            # Не прерываем запуск бота, но логируем ошибку
            logger.warning("Bot will continue with potentially incomplete parsing rules")


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()