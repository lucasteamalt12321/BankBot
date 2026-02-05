# admin_commands.py - Административные команды для Telegram бота
import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.admin.admin_system import AdminSystem, admin_required, UserNotFoundError, InsufficientBalanceError

logger = logging.getLogger(__name__)


class AdminCommands:
    """Класс для обработки административных команд"""
    
    def __init__(self, db_path: str = "data/bot.db"):
        self.admin_system = AdminSystem(db_path)
    
    @admin_required
    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /admin - панель администратора
        Показывает доступные команды и статистику
        """
        user = update.effective_user
        users_count = self.admin_system.get_users_count()
        
        text = f"""
🔧 <b>Панель администратора</b>

👋 Добро пожаловать, {user.first_name}!

📊 <b>Статистика:</b>
   • Всего пользователей: {users_count}

🛠️ <b>Доступные команды:</b>
   • /add_points @username [число] - начислить очки
   • /add_admin @username - добавить администратора
   • /admin - показать эту панель

💡 <b>Примеры использования:</b>
   • /add_points @john_doe 100
   • /add_admin @new_admin

⚠️ Будьте осторожны с административными командами!
        """
        
        await update.message.reply_text(text, parse_mode='HTML')
        logger.info(f"Admin panel accessed by user {user.id} (@{user.username})")
    
    @admin_required
    async def add_points_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /add_points - начисление очков пользователю
        Формат: /add_points @username amount
        """
        user = update.effective_user
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ <b>Неверный формат команды</b>\n\n"
                "Используйте: /add_points @username [количество]\n\n"
                "<b>Примеры:</b>\n"
                "• /add_points @john_doe 100\n"
                "• /add_points user123 50",
                parse_mode='HTML'
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
            # Находим пользователя
            target_user = self.admin_system.get_user_by_username(username)
            if not target_user:
                raise UserNotFoundError(f"Пользователь {username} не найден")
            
            # Обновляем баланс
            new_balance = self.admin_system.update_balance(target_user['id'], amount)
            if new_balance is None:
                raise Exception("Не удалось обновить баланс пользователя")
            
            # Создаем транзакцию
            transaction_id = self.admin_system.add_transaction(
                target_user['id'], amount, 'add', user.id
            )
            
            # Отправляем подтверждение
            text = f"""
✅ <b>Очки успешно начислены!</b>

👤 Пользователь: @{target_user['username'] or target_user['id']}
💰 Начислено: {amount} очков
💳 Новый баланс: {new_balance} очков
📝 ID транзакции: {transaction_id}

Администратор: @{user.username or user.first_name}
            """
            
            await update.message.reply_text(text, parse_mode='HTML')
            logger.info(f"Admin {user.id} added {amount} points to user {target_user['id']}")
            
        except UserNotFoundError as e:
            await update.message.reply_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error in add_points command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при начислении очков. "
                "Попробуйте позже или обратитесь к разработчику."
            )
    
    @admin_required
    async def add_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /add_admin - назначение администратора
        Формат: /add_admin @username
        """
        user = update.effective_user
        
        if len(context.args) < 1:
            await update.message.reply_text(
                "❌ <b>Неверный формат команды</b>\n\n"
                "Используйте: /add_admin @username\n\n"
                "<b>Примеры:</b>\n"
                "• /add_admin @john_doe\n"
                "• /add_admin user123",
                parse_mode='HTML'
            )
            return
        
        username = context.args[0]
        
        try:
            # Находим пользователя
            target_user = self.admin_system.get_user_by_username(username)
            if not target_user:
                raise UserNotFoundError(f"Пользователь {username} не найден")
            
            # Проверяем, не является ли пользователь уже администратором
            if target_user['is_admin']:
                await update.message.reply_text(
                    f"ℹ️ Пользователь @{target_user['username'] or target_user['id']} "
                    f"уже является администратором"
                )
                return
            
            # Назначаем администратором
            success = self.admin_system.set_admin_status(target_user['id'], True)
            if not success:
                raise Exception("Не удалось назначить пользователя администратором")
            
            # Отправляем подтверждение
            text = f"""
✅ <b>Администратор назначен!</b>

👤 Пользователь: @{target_user['username'] or target_user['id']}
🔧 Статус: Администратор
👑 Назначен: @{user.username or user.first_name}

Теперь пользователь имеет доступ к административным командам.
            """
            
            await update.message.reply_text(text, parse_mode='HTML')
            logger.info(f"Admin {user.id} granted admin rights to user {target_user['id']}")
            
        except UserNotFoundError as e:
            await update.message.reply_text(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error in add_admin command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при назначении администратора. "
                "Попробуйте позже или обратитесь к разработчику."
            )
    
    def get_admin_system(self) -> AdminSystem:
        """Получение экземпляра AdminSystem для использования в декораторе"""
        return self.admin_system