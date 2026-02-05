"""
Example usage of BroadcastSystem in the Telegram bot
This demonstrates how to integrate the BroadcastSystem with bot commands
"""

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
from database.database import get_db
from core.systems.broadcast_system import BroadcastSystem
from utils.admin.admin_system import AdminSystem
import logging

logger = logging.getLogger(__name__)


class BroadcastIntegrationExample:
    """Example integration of BroadcastSystem with bot commands"""
    
    def __init__(self, bot, admin_system: AdminSystem):
        self.bot = bot
        self.admin_system = admin_system
    
    async def admin_broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Admin command to broadcast message to all users
        Usage: /broadcast <message>
        """
        user = update.effective_user
        
        # Check admin privileges
        if not self.admin_system.is_admin(user.id):
            await update.message.reply_text(
                "🔒 У вас нет прав администратора для выполнения этой команды."
            )
            return
        
        # Check if message provided
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите сообщение для рассылки!\n\n"
                "Использование: /broadcast <сообщение>\n"
                "Пример: /broadcast Важное объявление для всех пользователей"
            )
            return
        
        message = " ".join(context.args)
        
        # Get database session
        db = next(get_db())
        try:
            # Create broadcast system
            broadcast_system = BroadcastSystem(db, self.bot, self.admin_system)
            
            # Send broadcast
            await update.message.reply_text("📡 Начинаю рассылку сообщения...")
            
            result = await broadcast_system.broadcast_to_all(message, user.id)
            
            # Report results
            report = f"""✅ <b>Рассылка завершена!</b>

📊 <b>Статистика:</b>
• Всего пользователей: {result.total_users}
• Успешно отправлено: {result.successful_sends}
• Ошибок доставки: {result.failed_sends}

{result.completion_message}"""
            
            if result.errors:
                report += f"\n\n⚠️ Первые ошибки:\n" + "\n".join(result.errors[:3])
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error in admin broadcast: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка при рассылке: {str(e)}"
            )
        finally:
            db.close()
    
    async def handle_mention_all_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
        """
        Handle mention-all broadcast after user purchases the feature
        This would be called from the shop system after successful purchase
        """
        user = update.effective_user
        
        # Get database session
        db = next(get_db())
        try:
            # Create broadcast system
            broadcast_system = BroadcastSystem(db, self.bot, self.admin_system)
            
            # Send mention-all broadcast
            await update.message.reply_text("📡 Отправляю ваше сообщение всем пользователям...")
            
            result = await broadcast_system.mention_all_users(message, user.id)
            
            # Report results to user
            report = f"""✅ <b>Ваше сообщение отправлено!</b>

📊 <b>Статистика рассылки:</b>
• Охвачено пользователей: {result.total_users}
• Успешно доставлено: {result.successful_sends}
• Не удалось доставить: {result.failed_sends}

Спасибо за использование функции рассылки!"""
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Error in mention-all broadcast: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка при рассылке: {str(e)}\n"
                "Обратитесь к администратору для решения проблемы."
            )
        finally:
            db.close()
    
    async def send_admin_notification_example(self, user_id: int, purchase_info: str):
        """
        Example of sending admin notification after purchase
        This would be called from the shop system
        """
        db = next(get_db())
        try:
            # Create broadcast system
            broadcast_system = BroadcastSystem(db, self.bot, self.admin_system)
            
            # Send notification to admins
            notification = f"Пользователь совершил покупку: {purchase_info}"
            result = await broadcast_system.notify_admins(notification, user_id)
            
            logger.info(f"Admin notification sent: {result.message}")
            
        except Exception as e:
            logger.error(f"Error sending admin notification: {e}")
        finally:
            db.close()


# Example of how to register the commands in the bot
def setup_broadcast_commands(application, admin_system):
    """Setup broadcast-related commands in the bot application"""
    from telegram.ext import CommandHandler
    
    broadcast_integration = BroadcastIntegrationExample(application.bot, admin_system)
    
    # Add admin broadcast command
    application.add_handler(
        CommandHandler("broadcast", broadcast_integration.admin_broadcast_command)
    )
    
    logger.info("Broadcast commands registered successfully")


# Example configuration for BroadcastSystem
def configure_broadcast_system(broadcast_system: BroadcastSystem):
    """Configure BroadcastSystem with optimal settings"""
    
    # Set batch size based on expected user count
    broadcast_system.set_batch_size(50)  # Process 50 users at a time
    
    # Set rate limiting to respect Telegram limits
    broadcast_system.set_rate_limit_delay(0.15)  # 150ms between messages
    
    # Set retry attempts for failed messages
    broadcast_system.set_max_retries(3)  # Retry up to 3 times
    
    logger.info("BroadcastSystem configured with optimal settings")