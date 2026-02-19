"""
Admin Middleware - автоматическая регистрация пользователей
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class AutoRegistrationMiddleware:
    """Middleware для автоматической регистрации пользователей"""
    
    def __init__(self):
        self.registered_users = set()
    
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обрабатывает сообщение и автоматически регистрирует пользователя
        
        Args:
            update: Telegram Update объект
            context: Telegram Context объект
        """
        if not update.effective_user:
            return
        
        user = update.effective_user
        user_id = user.id
        
        # Если пользователь уже обработан в этой сессии, пропускаем
        if user_id in self.registered_users:
            return
        
        try:
            # Импортируем здесь чтобы избежать циклических зависимостей
            from database.database import get_db
            from utils.core.user_manager import UserManager
            
            db = next(get_db())
            try:
                user_manager = UserManager(db)
                
                # Идентифицируем/регистрируем пользователя
                db_user = user_manager.identify_user(
                    user.username or user.first_name,
                    user_id
                )
                
                # Добавляем в кэш обработанных пользователей
                self.registered_users.add(user_id)
                
                logger.info(f"Auto-registered user: {user_id} ({user.username or user.first_name})")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in auto-registration middleware: {e}")


# Глобальный экземпляр middleware
auto_registration_middleware = AutoRegistrationMiddleware()
