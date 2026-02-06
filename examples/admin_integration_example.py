# admin_integration_example.py - Пример интеграции административной системы с ботом
"""
Этот файл показывает, как интегрировать систему проверки прав администратора
с существующим Telegram ботом.

Основные шаги интеграции:
1. Импортировать AdminSystem и admin_required
2. Создать экземпляр AdminSystem
3. Использовать декоратор @admin_required для защиты команд
4. Добавить автоматическую регистрацию пользователей
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Импортируем нашу административную систему
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.admin.admin_system import AdminSystem, admin_required
from bot.commands.admin_commands import AdminCommands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExampleBot:
    """Пример бота с интегрированной административной системой"""
    
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        
        # Инициализируем административную систему
        self.admin_system = AdminSystem("data/bot.db")
        self.admin_commands = AdminCommands("data/bot.db")
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        
        # Административные команды с защитой
        self.application.add_handler(CommandHandler("admin", self.admin_commands.admin_panel_command))
        self.application.add_handler(CommandHandler("add_points", self.admin_commands.add_points_command))
        self.application.add_handler(CommandHandler("add_admin", self.admin_commands.add_admin_command))
        
        # Обработчик всех сообщений для автоматической регистрации
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start с автоматической регистрацией"""
        user = update.effective_user
        
        # Автоматически регистрируем пользователя
        self.admin_system.register_user(
            user.id,
            user.username,
            user.first_name
        )
        
        welcome_text = f"""
👋 Добро пожаловать, {user.first_name}!

Вы успешно зарегистрированы в системе.

📋 <b>Доступные команды:</b>
• /start - начать работу
• /balance - проверить баланс

🔧 <b>Для администраторов:</b>
• /admin - панель администратора
• /add_points @username [число] - начислить очки
• /add_admin @username - добавить администратора
        """
        
        await update.message.reply_text(welcome_text, parse_mode='HTML')
        logger.info(f"User {user.id} registered and welcomed")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /balance - проверка баланса"""
        user = update.effective_user
        
        # Автоматически регистрируем пользователя если его нет
        self.admin_system.register_user(
            user.id,
            user.username,
            user.first_name
        )
        
        # Получаем данные пользователя
        user_data = self.admin_system.get_user_by_username(user.username or str(user.id))
        
        if user_data:
            text = f"""
💳 <b>Ваш баланс</b>

👤 Пользователь: {user_data['first_name']}
💰 Баланс: {user_data['balance']} очков
🔧 Статус: {'Администратор' if user_data['is_admin'] else 'Пользователь'}
            """
        else:
            text = "❌ Не удалось получить информацию о балансе"
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех сообщений для автоматической регистрации"""
        user = update.effective_user
        
        # Автоматически регистрируем пользователя
        self.admin_system.register_user(
            user.id,
            user.username,
            user.first_name
        )
        
        # Здесь можно добавить дополнительную логику обработки сообщений
        # Например, парсинг игровых результатов и начисление очков
    
    def run(self):
        """Запуск бота"""
        logger.info("Starting example bot with admin system...")
        self.application.run_polling()


# Пример создания первого администратора
def create_initial_admin(admin_system: AdminSystem, user_id: int, username: str, first_name: str):
    """
    Создание первого администратора системы
    Эту функцию нужно вызвать один раз при первом запуске бота
    """
    # Регистрируем пользователя
    admin_system.register_user(user_id, username, first_name)
    
    # Назначаем администратором
    success = admin_system.set_admin_status(user_id, True)
    
    if success:
        logger.info(f"Initial admin created: {user_id} (@{username})")
        return True
    else:
        logger.error(f"Failed to create initial admin: {user_id}")
        return False


if __name__ == "__main__":
    # Замените на ваш токен бота
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Создаем и запускаем бота
    bot = ExampleBot(BOT_TOKEN)
    
    # Создаем первого администратора (выполните один раз)
    # create_initial_admin(bot.admin_system, YOUR_TELEGRAM_ID, "your_username", "Your Name")
    
    bot.run()