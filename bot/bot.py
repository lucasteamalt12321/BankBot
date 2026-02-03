# bot.py - Объединенный Telegram-бот банк-аггрегатора LucasTeam
import logging
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from sqlalchemy.orm import Session
from database.database import create_tables, get_db
from core.bank_system import BankSystem
from core.shop_system import EnhancedShopSystem
from core.games_system import GamesSystem
from core.dnd_system import DndSystem
from core.motivation_system import MotivationSystem
from utils.notification_system import NotificationSystem
from core.achievements import AchievementSystem
from core.social_system import SocialSystem
from utils.user_manager import UserManager
from utils.config import settings, update_currency_rate, get_currency_config
from utils.monitoring_system import MonitoringSystem, AlertSystem
from database.backup_system import BackupSystem
from utils.error_handling import ErrorHandlingSystem
from utils.admin_middleware import auto_registration_middleware
from utils.admin_system import AdminSystem, admin_required
from datetime import datetime
import structlog
from telegram.error import BadRequest, TelegramError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = structlog.get_logger()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(settings.bot_token).build()
        self.setup_handlers()
        self.setup_error_handler()  # Добавьте эту строку
        
        # Инициализация систем мониторинга и безопасности
        self.monitoring_system = None
        self.alert_system = None
        self.backup_system = None
        self.error_handling_system = None
        
        # Инициализация административной системы
        admin_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bot.db')
        self.admin_system = AdminSystem(admin_db_path)
        # База данных уже инициализирована, не нужно создавать отдельные таблицы

    def setup_handlers(self):
        """Настройка обработчиков команд"""
        logger.info("Setting up enhanced handlers...")

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
        ]

        for handler in handlers:
            self.application.add_handler(handler)
            logger.info(f"Added handler: {handler.callback.__name__}")

        # Обработка колбэков
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Обработка всех сообщений для парсинга
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.parse_all_messages
        ))

        logger.info("All enhanced handlers set up successfully")

    def setup_error_handler(self):
        """Настройка обработчика ошибок"""

        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Exception while handling an update: {context.error}")

            # Попытка отправить сообщение об ошибке
            try:
                if update and update.effective_message:
                    await update.effective_message.reply_text(
                        f"Proizoshla oshibka pri obrabotke komandy. "
                        f"Pozhaluysta, poprobuyte pozje ili obratites k administratoru."
                    )
            except Exception as e:
                logger.error(f"Could not send error message: {e}")

        self.application.add_error_handler(error_handler)
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
            achievement_system = AchievementSystem(db)
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
        """Команда /start - интегрированная с новой системой регистрации"""
        user = update.effective_user
        
        registration_status = "❌ Ошибка регистрации"
        admin_status = "❌ Не администратор"
        
        # Принудительная регистрация в административной системе
        try:
            admin_user = self.admin_system.get_user_by_id(user.id)
            if not admin_user:
                # Регистрируем пользователя
                success = self.admin_system.register_user(
                    user.id, 
                    user.username, 
                    user.first_name
                )
                if success:
                    logger.info(f"Force-registered user {user.id} in admin system")
                    registration_status = "✅ Пользователь зарегистрирован"
                    
                    # Если это пользователь из конфига - делаем администратором
                    if user.id == 2091908459:  # LucasTeamLuke
                        admin_success = self.admin_system.set_admin_status(user.id, True)
                        if admin_success:
                            logger.info(f"Set admin status for user {user.id}")
                            admin_status = "✅ Права администратора установлены"
                        else:
                            admin_status = "❌ Ошибка установки прав администратора"
                    
                    # Получаем пользователя снова для проверки
                    admin_user = self.admin_system.get_user_by_id(user.id)
                else:
                    logger.error(f"Failed to register user {user.id} in admin system")
                    registration_status = "❌ Ошибка регистрации"
            else:
                registration_status = "✅ Пользователь уже зарегистрирован"
                if admin_user['is_admin']:
                    admin_status = "✅ Права администратора активны"
                else:
                    admin_status = "❌ Нет прав администратора"
                    
                    # Если это пользователь из конфига - делаем администратором
                    if user.id == 2091908459:  # LucasTeamLuke
                        admin_success = self.admin_system.set_admin_status(user.id, True)
                        if admin_success:
                            admin_status = "✅ Права администратора установлены"
                        
        except Exception as e:
            logger.error(f"Error in admin system registration: {e}")
            registration_status = f"❌ Ошибка: {str(e)}"
        
        # Process automatic user registration (old system)
        await auto_registration_middleware.process_message(update, context)

        welcome_text = f"""
[BANK] Добро пожаловать в Мета-Игровую Платформу LucasTeam!

[HELLO] Привет, {user.first_name}!

[SYSTEM] <b>Статус регистрации:</b>
{registration_status}
{admin_status}
Ваш Telegram ID: {user.id}

Я автоматически отслеживаю вашу активность в играх и начисляю банковские монеты.

[COMMANDS] <b>Основные команды:</b>
/balance - проверить баланс
/history - история транзакций
/profile - ваш профиль
/shop - магазин товаров
/games - мини-игры
/dnd - D&D мастерская
/daily - ежедневный бонус
/challenges - задания

[SOCIAL] <b>Социальные функции:</b>
/friends - друзья
/gift - отправить подарок
/clan - кланы

[ACHIEVEMENTS] <b>Достижения и уведомления:</b>
/achievements - ваши достижения
/notifications - уведомления

[GAMES] <b>Поддерживаемые игры:</b>
• Shmalala (курс 1:1)
• GD Cards (курс 2:1)
• True Mafia (курс 15:1)
• Bunker RP (курс 20:1)

[PLAY] Просто играйте, а я буду автоматически начислять вам монеты за активность!
        """

        await update.message.reply_text(welcome_text, parse_mode='HTML')

        # Регистрируем пользователя в основной системе (SQLAlchemy)
        # Это сохраняет существующий функционал согласно требованию 8.7
        db = next(get_db())
        try:
            user_manager = UserManager(db)
            identified_user = user_manager.identify_user(
                user.username or user.first_name,
                user.id
            )

            # Отправляем приветственное уведомление только для новых пользователей
            # Проверяем, был ли пользователь только что создан
            if identified_user.created_at and (datetime.utcnow() - identified_user.created_at).total_seconds() < 60:
                notification_system = NotificationSystem(db)
                notification_system.send_system_notification(
                    identified_user.id,
                    "🎉 Добро пожаловать!",
                    "Вы успешно зарегистрированы в системе. Начните зарабатывать монеты, участвуя в играх!"
                )

            logger.info(f"User processed in main system: {identified_user.id} (Telegram ID: {user.id})")
        except Exception as e:
            logger.error(f"Error processing user in main system: {e}")
        finally:
            db.close()

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /balance - проверка баланса"""
        # Process automatic user registration first
        await auto_registration_middleware.process_message(update, context)
        
        user = update.effective_user

        try:
            # Try to get balance from new admin system first
            admin_user = self.admin_system.get_user_by_id(user.id)
            
            if admin_user:
                # User exists in new admin system, use that balance
                text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {admin_user['first_name'] or user.first_name or 'Неизвестно'}
[BALANCE] Баланс: {admin_user['balance']} очков
[STATUS] Статус: {'Администратор' if admin_user['is_admin'] else 'Пользователь'}

[TIP] Используйте /history для просмотра транзакций
                """
                await update.message.reply_text(text, parse_mode='HTML')
                return
            
            # Fallback to old system if user not found in admin system
            db = next(get_db())
            try:
                bank = BankSystem(db)
                result = bank.get_user_balance(user.username or user.first_name, user.id)

                text = f"""
[MONEY] <b>Ваш баланс</b>

[USER] Пользователь: {result.get('first_name', '')} {result.get('last_name', '')}
[BALANCE] Баланс: {result['balance']} банковских монет
[TIME] Последняя активность: {result['last_activity'].strftime('%d.%m.%Y %H:%M') if result['last_activity'] else 'Нет данных'}

[TIP] Используйте /history для просмотра транзакций
                """

                await update.message.reply_text(text, parse_mode='HTML')
            finally:
                db.close()
                
        except Exception as e:
            logger.error("Error in balance command", error=str(e), user_id=user.id, username=user.username)
            await update.message.reply_text(f"❌ Произошла ошибка при получении баланса. Попробуйте позже.")

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /history - история транзакций"""
        user = update.effective_user
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10

        db = next(get_db())
        try:
            bank = BankSystem(db)
            result = bank.get_user_history(user.username or user.first_name, limit, user.id)

            if not result['transactions']:
                await update.message.reply_text("📭 У вас пока нет транзакций")
                return

            text = f"""
[STATS] <b>История транзакций</b>

[USER] Пользователь: {result.get('first_name', '')} {result.get('last_name', '')}
[BALANCE] Текущий баланс: {result['balance']} монет
[LIST] Показано последних: {len(result['transactions'])} транзакций

"""
            for t in result['transactions']:
                amount_text = f"+{t['amount']}" if t['amount'] > 0 else str(t['amount'])
                arrow = "UP" if t['amount'] > 0 else "DOWN" if t['amount'] < 0 else "EQUAL"

                text += f"[{arrow}] {amount_text} монет\n"
                text += f"   Тип: {t['type']}\n"
                text += f"   Источник: {t['source'] or 'система'}\n"
                text += f"   Описание: {t['description'][:50]}...\n"
                text += f"   Дата: {t['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in history command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /profile - профиль пользователя"""
        user = update.effective_user
        
        # Process automatic user registration first
        await auto_registration_middleware.process_message(update, context)
        
        # Принудительная регистрация если пользователь не найден
        admin_user = None
        try:
            admin_user = self.admin_system.get_user_by_id(user.id)
            if not admin_user:
                # Регистрируем пользователя
                success = self.admin_system.register_user(
                    user.id, 
                    user.username, 
                    user.first_name
                )
                if success:
                    logger.info(f"Force-registered user {user.id} in profile command")
                    
                    # Если это пользователь из конфига - делаем администратором
                    if user.id == 2091908459:  # LucasTeamLuke
                        self.admin_system.set_admin_status(user.id, True)
                        logger.info(f"Set admin status for user {user.id}")
                    
                    # Получаем пользователя снова
                    admin_user = self.admin_system.get_user_by_id(user.id)
                    
                    # Если все еще не найден, создаем временный объект
                    if not admin_user:
                        admin_user = {
                            'id': None,
                            'telegram_id': user.id,
                            'username': user.username,
                            'first_name': user.first_name,
                            'balance': 0,
                            'is_admin': user.id == 2091908459
                        }
                        logger.warning(f"Created temporary user object for {user.id}")
                else:
                    # Создаем временный объект если регистрация не удалась
                    admin_user = {
                        'id': None,
                        'telegram_id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'balance': 0,
                        'is_admin': False
                    }
                    logger.warning(f"Registration failed, created fallback user object for {user.id}")
        except Exception as e:
            logger.error(f"Error in admin system registration: {e}")
            # Создаем временный объект пользователя для отображения
            admin_user = {
                'id': None,
                'telegram_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'balance': 0,
                'is_admin': False
            }
            logger.warning(f"Created fallback user object for {user.id} due to error: {e}")

        try:
            if not admin_user:
                await update.message.reply_text("❌ Критическая ошибка: пользователь не найден после регистрации")
                return

            # Получаем количество транзакций из основной базы данных
            conn = self.admin_system.get_db_connection()
            cursor = conn.cursor()
            
            # Получаем внутренний ID для запросов к транзакциям
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user.id,))
            user_row = cursor.fetchone()
            internal_id = user_row['id'] if user_row else None
            
            total_transactions = 0
            total_deposits = 0
            if internal_id:
                cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = ?", (internal_id,))
                result = cursor.fetchone()
                total_transactions = result['count'] if result else 0
                
                cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = ? AND amount > 0", (internal_id,))
                result = cursor.fetchone()
                total_deposits = result['count'] if result else 0
            
            conn.close()

            text = f"""
[USER] <b>Ваш профиль</b>

[INFO] <b>Основная информация:</b>
   • ID: {user.id}
   • Имя: {admin_user['first_name'] or 'Не указано'}
   • Username: @{admin_user['username'] or 'Не указан'}
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

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error("Error in profile command", error=str(e), user_id=user.id, username=user.username)
            await update.message.reply_text(f"❌ Произошла ошибка при получении профиля: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - персональная статистика"""
        user = update.effective_user

        db = next(get_db())
        try:
            from database.database import User, Transaction, UserPurchase
            from sqlalchemy import func

            user_db = db.query(User).filter(User.telegram_id == user.id).first()
            if not user_db:
                await update.message.reply_text("❌ Пользователь не найден")
                return

            # Базовая статистика
            total_earned = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_db.id,
                Transaction.amount > 0
            ).scalar() or 0

            total_spent = abs(db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_db.id,
                Transaction.amount < 0
            ).scalar() or 0)

            total_purchases = db.query(UserPurchase).filter(
                UserPurchase.user_id == user_db.id
            ).count()

            # Активность за последнюю неделю
            week_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            week_transactions = db.query(Transaction).filter(
                Transaction.user_id == user_db.id,
                Transaction.created_at >= week_ago
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

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    # ===== Магазин =====
    async def shop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /shop - просмотр магазина"""
        # Process automatic user registration first
        await auto_registration_middleware.process_message(update, context)
        
        user = update.effective_user
        logger.info(f"Shop command from user {user.id}")

        try:
            # Import ShopHandler
            from core.shop_handler import ShopHandler
            
            # Create shop handler and generate display
            shop_handler = ShopHandler()
            shop_display = shop_handler.display_shop(user.id)
            
            await update.message.reply_text(shop_display)
            
        except Exception as e:
            logger.error(f"Error in shop command: {e}")
            # Fallback to simple display if there's an error
            fallback_text = """🛒 МАГАЗИН

❌ Произошла ошибка при загрузке магазина. Попробуйте позже.

Для связи с администратором используйте /buy_contact"""
            await update.message.reply_text(fallback_text)

    async def buy_contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_contact для покупки товаров"""
        # Process automatic user registration first
        await auto_registration_middleware.process_message(update, context)
        
        user = update.effective_user
        
        try:
            # Получаем пользователя из административной системы
            admin_user = self.admin_system.get_user_by_username(user.username or str(user.id))
            if not admin_user:
                # Если пользователь не найден, регистрируем его
                success = self.admin_system.register_user(
                    user.id, 
                    user.username, 
                    user.first_name
                )
                if not success:
                    await update.message.reply_text("❌ Ошибка регистрации пользователя")
                    return
                
                # Получаем пользователя снова после регистрации
                admin_user = self.admin_system.get_user_by_username(user.username or str(user.id))
                if not admin_user:
                    await update.message.reply_text("❌ Не удалось найти пользователя")
                    return
            
            # Проверяем баланс пользователя (минимум 10 очков)
            current_balance = admin_user['balance']
            required_amount = 10
            
            if current_balance < required_amount:
                await update.message.reply_text(
                    f"❌ Недостаточно очков для покупки. "
                    f"Требуется: {required_amount} очков, "
                    f"у вас: {int(current_balance)} очков"
                )
                return
            
            # Списываем 10 очков с баланса пользователя
            new_balance = self.admin_system.update_balance(user.id, -required_amount)
            if new_balance is None:
                await update.message.reply_text("❌ Не удалось обновить баланс")
                return
            
            # Создаем транзакцию типа 'buy'
            transaction_id = self.admin_system.add_transaction(
                user.id, -required_amount, 'buy'
            )
            
            # Отправляем подтверждение пользователю
            await update.message.reply_text("Вы купили контакт. Администратор свяжется с вами.")
            
            # Отправляем уведомление всем администраторам
            try:
                conn = self.admin_system.get_db_connection()
                cursor = conn.cursor()
                
                # Получаем всех администраторов
                cursor.execute("SELECT telegram_id FROM users WHERE is_admin = TRUE")
                admin_ids = [row['telegram_id'] for row in cursor.fetchall()]
                conn.close()
                
                # Формируем сообщение для администраторов
                username_display = f"@{user.username}" if user.username else f"#{user.id}"
                admin_message = f"Пользователь {username_display} купил контакт. Его баланс: {int(new_balance)} очков"
                
                # Отправляем сообщение каждому администратору
                for admin_id in admin_ids:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notification to admin {admin_id}: {e}")
                
                logger.info(f"User {user.id} bought contact, notified {len(admin_ids)} admins")
                
            except Exception as e:
                logger.error(f"Error notifying admins about purchase: {e}")
                # Покупка уже совершена, поэтому не возвращаем ошибку пользователю
            
        except Exception as e:
            logger.error(f"Error in buy_contact command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при покупке. "
                "Попробуйте позже или обратитесь к администратору."
            )
    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy - покупка товара"""
        user = update.effective_user

        if not context.args:
            await update.message.reply_text("Ispolzuyte: /buy <id_tovara>")
            return

        try:
            item_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Nevernyy ID tovara")
            return

        db = next(get_db())
        try:
            shop = EnhancedShopSystem(db)
            result = shop.purchase_item(user.id, item_id)

            if result['success']:
                activation_msg = result['activation_result'].get('message', 'Товар активирован')
                text = f"""
[OK] <b>Покупка успешна!</b>

[GIFT] Товар: {result['item_name']}
[MONEY] Стоимость: {result['price']} монет
[BALANCE] Новый баланс: {result['new_balance']} монет
[BOX] ID покупки: {result['purchase_id']}

{activation_msg}
                """

                # Отправляем уведомление
                notification_system = NotificationSystem(db)
                notification_system.send_purchase_notification(
                    user.id,
                    result['item_name'],
                    result['price'],
                    result['new_balance']
                )
            else:
                text = f"Ne udalos kupit tovar: {result['reason']}"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in buy command: {e}")
            await update.message.reply_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

    async def buy_1_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_1 - покупка первого товара"""
        await self._handle_purchase_command(update, context, 1)

    async def buy_2_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_2 - покупка второго товара"""
        await self._handle_purchase_command(update, context, 2)

    async def buy_3_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /buy_3 - покупка третьего товара"""
        await self._handle_purchase_command(update, context, 3)

    async def _handle_purchase_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, item_number: int):
        """Обработчик команд покупки товаров из магазина"""
        # Process automatic user registration first
        await auto_registration_middleware.process_message(update, context)
        
        user = update.effective_user
        logger.info(f"Purchase command /buy_{item_number} from user {user.id}")

        try:
            # Import and use PurchaseHandler
            from core.purchase_handler import PurchaseHandler
            
            # Create purchase handler and process purchase
            purchase_handler = PurchaseHandler()
            result = purchase_handler.process_purchase(user.id, item_number)
            
            if result.success:
                # Success message
                text = f"""✅ <b>Покупка успешна!</b>

{result.message}

💳 Новый баланс: {result.new_balance} монет
🛒 ID покупки: {result.purchase_id}

Товар будет активирован в ближайшее время."""
                
                await update.message.reply_text(text, parse_mode='HTML')
                logger.info(f"Purchase successful: user {user.id}, item {item_number}, purchase {result.purchase_id}")
                
            else:
                # Error message
                await update.message.reply_text(f"❌ {result.message}")
                logger.warning(f"Purchase failed: user {user.id}, item {item_number}, error: {result.error_code}")
            
        except Exception as e:
            logger.error(f"Error in buy_{item_number} command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке покупки. "
                "Попробуйте позже или обратитесь к администратору."
            )

    async def inventory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /inventory - инвентарь"""
        user = update.effective_user

        db = next(get_db())
        try:
            shop = EnhancedShopSystem(db)
            inventory = shop.get_user_inventory(user.id)

            if not inventory:
                await update.message.reply_text("Vash inventar pust")
                return

            text = "[BAG] <b>Ваш инвентарь</b>\n\n"

            active_items = [i for i in inventory if i['is_active']]
            expired_items = [i for i in inventory if not i['is_active']]

            if active_items:
                text += "[YES] <b>Активные товары:</b>\n"
                for item in active_items:
                    text += f"• {item['item_name']}\n"
                    if item['expires_at']:
                        text += f"  ⏰ Истекает: {item['expires_at'].strftime('%d.%m.%Y %H:%M')}\n"
                    text += f"  🛒 Куплен: {item['purchased_at'].strftime('%d.%m.%Y')}\n\n"

            if expired_items:
                text += "[NO] <b>Неактивные товары:</b>\n"
                for item in expired_items[:5]:  # Показываем только 5
                    text += f"• {item['item_name']} (истек)\n"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in inventory command: {e}")
            await update.message.reply_text(f"Oshibka: {str(e)}")
        finally:
            db.close()

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
                text += f"\n[TIP] Используйте /daily для получения бонуса!"
            else:
                text += f"⏰ Последний бонус: {stats['last_bonus_date'].strftime('%d.%m.%Y') if stats['last_bonus_date'] else 'Никогда'}\n"
                text += f"\n[TIP] Возвращайтесь завтра для нового бонуса!"

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
        user = update.effective_user
        
        # Проверяем права администратора
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                "Обратитесь к администратору бота для получения доступа."
            )
            logger.warning(f"User {user.id} (@{user.username}) attempted to use admin command without permissions")
            return
        
        users_count = self.admin_system.get_users_count()
        
        text = f"Админ-панель:\n/add_points @username [число] - начислить очки\n/add_admin @username - добавить администратора\nВсего пользователей: {users_count}"
        
        await update.message.reply_text(text)
        logger.info(f"Admin panel accessed by user {user.id}")

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
            transaction_id = self.admin_system.add_transaction(
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
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        db = next(get_db())
        try:
            bank = BankSystem(db)
            stats = bank.get_system_stats()

            text = f"""
📊 <b>Статистика системы</b>

👤 Пользователи: {stats['total_users']}
💰 Общий баланс: {stats['total_balance']} монет
📈 Транзакций сегодня: {stats['today_transactions']}

💱 <b>Коэффициенты конвертации:</b>
"""
            for game, config in stats['currency_config'].items():
                text += f"   • {game}: {config['base_rate']}x\n"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in admin_stats command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_adjust_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_adjust - корректировка баланса"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Используйте: /admin_adjust <пользователь> <сумма> <причина>\n"
                "Пример: /admin_adjust @username 100 \"Бонус за активность\"\n"
                "Пример: /admin_adjust Имя Фамилия -50 \"Штраф за нарушение\""
            )
            return

        user_identifier = context.args[0]

        try:
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Неверная сумма")
            return

        reason = ' '.join(context.args[2:])

        db = next(get_db())
        try:
            bank = BankSystem(db)
            result = bank.admin_adjust_balance(user_identifier, amount, reason, user.id)

            if result['success']:
                text = f"""
✅ <b>Баланс скорректирован</b>

Пользователь: #{result['user_id']}
Изменение: {amount} монет
Новый баланс: {result['new_balance']} монет
Причина: {reason}
ID транзакции: {result['transaction_id']}
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"❌ Ошибка при корректировке баланса")
        except Exception as e:
            logger.error(f"Error in admin_adjust command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_addcoins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_addcoins - добавление монет пользователю"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("У вас нет прав администратора для использования этой команды")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Неправильное использование: /admin_addcoins <пользователь> <сумма> [причина]\n"
                "Пример: /admin_addcoins @username 100\n"
                "Пример: /admin_addcoins @username 100 \"Бонус за активность\""
            )
            return

        user_identifier = context.args[0]

        try:
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Сумма должна быть числом")
            return

        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else f"Добавлено администратором {user.username or user.first_name}"

        db = next(get_db())
        try:
            bank = BankSystem(db)
            result = bank.admin_adjust_balance(user_identifier, amount, reason, user.id)

            if result['success']:
                text = f"""
[COINS] <b>Монеты успешно добавлены</b>

ID пользователя: #{result['user_id']}
Добавлено: {amount} монет
Новый баланс: {result['new_balance']} монет
Причина: {reason}
ID транзакции: {result['transaction_id']}
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"Ошибка при добавлении монет пользователю")
        except Exception as e:
            logger.error(f"Error in admin_addcoins command: {e}")
            await update.message.reply_text(f"Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_removecoins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_removecoins - удаление монет у пользователя"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("У вас нет прав администратора для использования этой команды")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Неправильное использование: /admin_removecoins <пользователь> <сумма> [причина]\n"
                "Пример: /admin_removecoins @username 50\n"
                "Пример: /admin_removecoins @username 50 \"Штраф за нарушение\""
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

        # Make amount negative for removal
        amount = -abs(amount)  # Ensure it's negative
        
        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else f"Удалено администратором {user.username or user.first_name}"

        db = next(get_db())
        try:
            bank = BankSystem(db)
            result = bank.admin_adjust_balance(user_identifier, amount, reason, user.id)

            if result['success']:
                text = f"""
[COINS] <b>Монеты успешно удалены</b>

ID пользователя: #{result['user_id']}
Удалено: {abs(amount)} монет
Новый баланс: {result['new_balance']} монет
Причина: {reason}
ID транзакции: {result['transaction_id']}
                """

                await update.message.reply_text(text, parse_mode='HTML')
            else:
                await update.message.reply_text(f"Ошибка при удалении монет у пользователя")
        except Exception as e:
            logger.error(f"Error in admin_removecoins command: {e}")
            await update.message.reply_text(f"Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_merge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_merge - объединение аккаунтов"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Используйте: /admin_merge <основной_пользователь> <дублирующий_пользователь>\n"
                "Пример: /admin_merge @username @old_username\n"
                "Пример: /admin_merge \"Имя Фамилия\" \"Старое Имя\""
            )
            return

        primary_identifier = context.args[0]
        secondary_identifier = context.args[1]

        db = next(get_db())
        try:
            from utils.user_manager import UserManager
            user_manager = UserManager(db)

            primary_user = user_manager.identify_user(primary_identifier)
            secondary_user = user_manager.identify_user(secondary_identifier)

            if not primary_user or not secondary_user:
                await update.message.reply_text("❌ Один из пользователей не найден")
                return

            if primary_user.id == secondary_user.id:
                await update.message.reply_text("❌ Нельзя объединить пользователя с самим собой")
                return

            # Объединяем пользователей
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

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in admin_merge command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_transactions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_transactions - транзакции пользователя"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Используйте: /admin_transactions <пользователь> [лимит]\n"
                "Пример: /admin_transactions @username 20\n"
                "Пример: /admin_transactions \"Имя Фамилия\""
            )
            return

        user_identifier = context.args[0]
        limit = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 20

        db = next(get_db())
        try:
            bank = BankSystem(db)
            from utils.user_manager import UserManager
            user_manager = UserManager(db)

            user_obj = user_manager.identify_user(user_identifier)
            if not user_obj:
                await update.message.reply_text("❌ Пользователь не найден")
                return

            result = bank.get_user_history(user_identifier, limit)

            text = f"""
📊 <b>Транзакции пользователя</b>

👤 Пользователь: #{user_obj.id}
💳 Баланс: {result['balance']} монет
📋 Показано: {len(result['transactions'])} транзакций

"""
            for t in result['transactions']:
                amount_text = f"+{t['amount']}" if t['amount'] > 0 else str(t['amount'])
                emoji = "⬆️" if t['amount'] > 0 else "⬇️" if t['amount'] < 0 else "➡️"

                text += f"{emoji} {amount_text} монет\n"
                text += f"   ID: {t['id']}\n"
                text += f"   Тип: {t['type']}\n"
                text += f"   Источник: {t['source'] or 'система'}\n"
                text += f"   Описание: {t['description'][:50]}{'...' if len(t['description']) > 50 else ''}\n"
                text += f"   Дата: {t['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in admin_transactions command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_balances_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_balances - балансы всех пользователей"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        db = next(get_db())
        try:
            from database.database import User
            from sqlalchemy import desc

            # Получаем топ пользователей по балансу
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

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in admin_balances command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_users - список пользователей"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        db = next(get_db())
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
                text += f"   Зарегистрирован: {user_db.created_at.strftime('%d.%m.%Y')}\n"
                text += f"   Последняя активность: {user_db.last_activity.strftime('%d.%m.%Y %H:%M') if user_db.last_activity else 'Нет данных'}\n\n"

            text += f"💡 Всего пользователей: {db.query(User).count()}"

            await update.message.reply_text(text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error in admin_users command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_rates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_rates - коэффициенты конвертации"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        currency_config = get_currency_config()

        text = "💰 <b>Текущие коэффициенты конвертации:</b>\n\n"
        for game, config in currency_config.items():
            text += f"🎮 <b>{game}</b>: {config['base_rate']}x\n"
            if 'event_multipliers' in config:
                for event, multiplier in config['event_multipliers'].items():
                    text += f"   ├ {event}: {multiplier}x\n"
            if 'rarity_multipliers' in config:
                for rarity, multiplier in config['rarity_multipliers'].items():
                    text += f"   ├ {rarity}: {multiplier}x\n"
            text += "\n"

        text += "💡 Используйте /admin_rate <игра> <коэффициент> для изменения"

        await update.message.reply_text(text, parse_mode='HTML')

    async def admin_rate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_rate - изменение коэффициента"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
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
                await update.message.reply_text("❌ Коэффициент должен быть положительным числом")
                return

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

    async def admin_cleanup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_cleanup - очистка системы"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        db = next(get_db())
        try:
            shop = EnhancedShopSystem(db)
            expired_count = shop.check_expired_items()

            # Очистка старых уведомлений
            from database.database import UserNotification
            from datetime import datetime, timedelta

            month_ago = datetime.utcnow() - timedelta(days=30)
            old_notifications = db.query(UserNotification).filter(
                UserNotification.created_at < month_ago
            ).delete()
            db.commit()

            db.commit()

            await update.message.reply_text(
                f"🧹 <b>Очистка системы завершена</b>\n\n"
                f"📦 Деактивировано просроченных товаров: {expired_count}\n"
                f"🗑️ Удалено старых уведомлений: {old_notifications}\n"
                f"✅ Система оптимизирована",
                parse_mode='HTML'
            )

        except Exception as e:
            logger.error(f"Error in admin_cleanup command: {e}")
            await update.message.reply_text(f"❌ Ошибка при очистке: {str(e)}")
        finally:
            db.close()

    async def admin_shop_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_shop_add - добавление товара (заглушка)"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        await update.message.reply_text(
            "🛍️ <b>Добавление товара</b>\n\n"
            "Функция в разработке. Используйте прямой SQL для добавления товаров.",
            parse_mode='HTML'
        )

    async def admin_shop_edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_shop_edit - редактирование товара (заглушка)"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        await update.message.reply_text(
            "✏️ <b>Редактирование товара</b>\n\n"
            "Функция в разработке. Используйте прямой SQL для редактирования товаров.",
            parse_mode='HTML'
        )

    async def admin_games_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_games_stats - статистика игр"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        db = next(get_db())
        try:
            from database.database import GameSession

            total_games = db.query(GameSession).count()
            active_games = db.query(GameSession).filter(GameSession.status == 'active').count()
            waiting_games = db.query(GameSession).filter(GameSession.status == 'waiting').count()

            await update.message.reply_text(
                f"🎮 <b>Статистика мини-игр</b>\n\n"
                f"Всего игр: {total_games}\n"
                f"Активных: {active_games}\n"
                f"Ожидающих начала: {waiting_games}",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error in admin_games_stats command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            db.close()

    async def admin_reset_game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_reset_game - сброс игры (заглушка)"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        await update.message.reply_text(
            "🔄 <b>Сброс игры</b>\n\n"
            "Функция в разработке.",
            parse_mode='HTML'
        )

    async def admin_ban_player_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_ban_player - бан игрока (заглушка)"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        await update.message.reply_text(
            "🚫 <b>Бан игрока</b>\n\n"
            "Функция в разработке.",
            parse_mode='HTML'
        )

    async def admin_health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_health - здоровье системы"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        # Используем нашу систему мониторинга
        if self.monitoring_system:
            health_data = self.monitoring_system.get_system_health()
            metrics = self.monitoring_system.get_all_metrics()
            
            text = f"""
⚙️ <b>Состояние системы</b>

💻 <b>Процессор:</b>
   • Загрузка: {health_data['cpu']['percent']}%
   • Ядер: {health_data['cpu']['count']}

🧠 <b>Память:</b>
   • Всего: {health_data['memory']['total'] // (1024 ** 3)} GB
   • Использовано: {health_data['memory']['used'] // (1024 ** 3)} GB ({health_data['memory']['percent']}%)
   • Свободно: {health_data['memory']['available'] // (1024 ** 3)} GB

💾 <b>Диск:</b>
   • Всего: {health_data['disk']['total'] // (1024 ** 3)} GB
   • Использовано: {health_data['disk']['used'] // (1024 ** 3)} GB ({health_data['disk']['percent']}%)
   • Свободно: {health_data['disk']['free'] // (1024 ** 3)} GB

📊 <b>Бизнес-метрики:</b>
   • Всего пользователей: {metrics['business_metrics']['total_users']}
   • Активных сегодня: {metrics['business_metrics']['active_users_today']}
   • Транзакций сегодня: {metrics['business_metrics']['today_transactions']}

📈 <b>Производительность:</b>
   • Проверка: {metrics['performance_metrics']['total_check_time']:.2f}s
   • Проблемы: {len(metrics['performance_metrics']['performance_issues'])}
            """
        else:
            # Резервная реализация с psutil
            import psutil
            import os

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            text = f"""
⚙️ <b>Состояние системы</b>

💻 <b>Процессор:</b>
   • Загрузка: {cpu_percent}%
   • Ядер: {psutil.cpu_count()}

🧠 <b>Память:</b>
   • Всего: {memory.total // (1024 ** 3)} GB
   • Использовано: {memory.used // (1024 ** 3)} GB ({memory.percent}%)
   • Свободно: {memory.available // (1024 ** 3)} GB

💾 <b>Диск:</b>
   • Всего: {disk.total // (1024 ** 3)} GB
   • Использовано: {disk.used // (1024 ** 3)} GB ({disk.percent}%)
   • Свободно: {disk.free // (1024 ** 3)} GB

📊 <b>Бот:</b>
   • PID: {os.getpid()}
   • Время работы: {psutil.Process(os.getpid()).create_time()}
            """

        await update.message.reply_text(text, parse_mode='HTML')

    async def admin_errors_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_errors - просмотр ошибок"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        # Используем нашу систему обработки ошибок
        if self.error_handling_system:
            errors = self.error_handling_system.get_recent_errors(10)
            stats = self.error_handling_system.get_error_statistics()
            
            text = f"""
🚨 <b>Последние ошибки</b>

📊 <b>Статистика ошибок:</b>
   • Всего ошибок: {stats['total_errors']}
   • Сегодня: {stats['errors_today']}
   • На этой неделе: {stats['errors_this_week']}
   • Самая частая: {stats['most_common_error']['type']} ({stats['most_common_error']['count']} раз)

📝 <b>Последние ошибки:</b>
"""
            for error in errors[-5:]:  # Показываем последние 5 ошибок
                text += f"• {error['error_type']}: {error['message'][:50]}...\n"
                text += f"  📅 {error['timestamp'].strftime('%d.%m.%Y %H:%M')}\n\n"
                
            text += "💡 Используйте /admin_cleanup для очистки старых ошибок"
        else:
            text = (
                "🚨 <b>Просмотр ошибок</b>\n\n"
                "Функция в разработке. Ошибки логируются в файлы логов."
            )

        await update.message.reply_text(text, parse_mode='HTML')

    async def admin_backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admin_backup - резервное копирование"""
        user = update.effective_user

        if user.id not in settings.admin_user_ids:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return

        # Используем нашу систему бэкапов
        if self.backup_system:
            result = self.backup_system.create_backup()
            if result['success']:
                await update.message.reply_text(
                    f"✅ <b>Резервная копия создана</b>\n\n"
                    f"Файл: {result['backup_file']}\n"
                    f"Размер: {result['size']} байт\n"
                    f"Время: {result['timestamp']}",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    f"❌ <b>Ошибка создания резервной копии</b>\n\n"
                    f"{result['message']}",
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(
                "💾 <b>Резервное копирование</b>\n\n"
                "Функция в разработке. Резервные копии создаются автоматически.",
                parse_mode='HTML'
            )

    # ===== Обработка сообщений =====
    async def parse_all_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка всех сообщений"""
        # First, process automatic user registration
        await auto_registration_middleware.process_message(update, context)
        
        message_text = update.message.text
        user = update.effective_user
        chat = update.effective_chat

        # Пропускаем сообщения от самого бота
        if user.is_bot:
            return

        chat_type = "private" if chat.type == "private" else f"group/{chat.type}"
        logger.info(f"Message received in {chat_type} chat {chat.id} from user {user.id}: {message_text[:100]}...")

        # Если это личное сообщение и не команда, покажем справку
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
                "В группах я автоматически отслеживаю вашу игровую активность!"
            )
            return

        # Обработка игровых сообщений в группах
        if chat.type in ["group", "supergroup"]:
            await self.process_game_message(update, context)
        elif chat.type == "private":
            # В личных сообщениях тоже можем получать игровые сообщения от других ботов
            # если пользователь пересылает их или боты отправляют напрямую
            message_text = update.message.text
            # Проверяем, содержит ли сообщение игровые ключевые слова и обрабатываем его
            # Добавляем больше ключевых слов для разных игр, включая русские варианты
            lower_text = message_text.lower()
            # Русские ключевые слова
            russian_keywords = [
                'рыбалка', 'рыбак', 'карта', 'новая карта', 'game', 'игр',
                'шмалала', 'шмала', 'battle', 'битва', 'battle_win', 'крокодил',
                'угадал', 'слово', 'crocodile', 'fishing', 'fish', 'рыбка',
                'gd cards', 'gdcards', 'card', 'карточка', 'gdcards',
                'очки:', 'игрок:', 'шмал', 'mafia', 'мафия', 'бункер', 'bunker',
                '🏆', '💰', 'монет', 'points', 'points:', '💎', '⭐', '🌟'
            ]
            
            # Проверяем наличие ключевых слов или структуры игрового сообщения
            has_keyword = any(keyword in lower_text for keyword in russian_keywords)
            
            # Также проверяем наличие типичной структуры игровых сообщений
            has_game_structure = (
                ('игрок:' in lower_text and ('очки:' in lower_text or 'монет' in lower_text)) or
                ('рыбак:' in lower_text) or
                ('победил' in lower_text and 'монетки' in lower_text) or
                ('карта:' in lower_text) or
                ('🏆' in message_text) or ('💰' in message_text) or ('💎' in message_text)
            )
            
            if has_keyword or has_game_structure:
                # Send immediate feedback to let user know we're processing
                await update.message.reply_text("🔄 Обрабатываю игровое сообщение...")
                await self.process_game_message(update, context)

    async def process_game_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка игровых сообщений в группах"""
        message_text = update.message.text
        user = update.effective_user
        chat = update.effective_chat

        logger.info("Processing game message", chat_id=chat.id, message_preview=message_text[:200])

        db = next(get_db())
        try:
            bank = BankSystem(db)
            results = bank.process_message(message_text)
            
            # Логируем все результаты для отладки
            logger.info("Message processing results", result_count=len(results), chat_id=chat.id)
            for result in results:
                if result.get('success'):
                    logger.info(
                        "Activity processed successfully",
                        user=result['user_name'],
                        amount=result['converted_amount'],
                        new_balance=result['new_balance'],
                        chat_id=chat.id
                    )
                else:
                    logger.warning(
                        "Failed to process activity",
                        error=result.get('error'),
                        activity_type=result.get('activity', {}).activity_type if result.get('activity') else 'unknown',
                        chat_id=chat.id
                    )

            # Логируем результаты парсинга
            for result in results:
                if result.get('success'):
                    logger.info(
                        "Activity parsed successfully",
                        user_id=result['user_id'],
                        activity_type=result['activity'].activity_type,
                        amount=result['converted_amount']
                    )

                    # Отправляем уведомление о начислении
                    if result['converted_amount'] > 0:
                        await update.message.reply_text(
                            f"💫 {result['user_name']} получил(а) {result['converted_amount']} банковских монет!\n"
                            f"💳 Новый баланс: {result['new_balance']} монет"
                        )

                        # Отправляем уведомление пользователю
                        notification_system = NotificationSystem(db)
                        notification_system.send_transaction_notification(
                            result['user_id'],
                            result['converted_amount'],
                            'game_reward',
                            f"Активность в {result['activity'].game_source}: {result['activity'].activity_type}"
                        )

                        # Проверяем достижения
                        achievement_system = AchievementSystem(db)
                        achievement_system.check_achievements(
                            result['user_id'],
                            'game_activity',
                            {'game': result['activity'].game_source}
                        )
                else:
                    logger.warning(
                        "Failed to parse activity",
                        error=result.get('error'),
                        user_identifier=result.get('activity', {}).user_identifier if result.get(
                            'activity') else 'unknown'
                    )

        except Exception as e:
            logger.error("Error processing game message", error=str(e), chat_id=chat.id)
        finally:
            db.close()

    def run(self):
        """Запуск бота"""
        logger.info("Starting enhanced bot...")

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

            # Инициализируем достижения
            achievement_system = AchievementSystem(db)
            logger.info("Achievement system initialized successfully")
            
            # Инициализируем системы мониторинга и безопасности
            self.monitoring_system = MonitoringSystem(db)
            self.alert_system = AlertSystem(self.monitoring_system)
            self.backup_system = BackupSystem()
            self.error_handling_system = ErrorHandlingSystem(db)
            logger.info("Monitoring and security systems initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize systems", error=str(e))
        finally:
            db.close()

        # Запускаем бота
        logger.info("Enhanced bot starting polling...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()