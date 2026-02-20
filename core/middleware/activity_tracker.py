"""
Activity Tracker Middleware
Отслеживает активность пользователей и обновляет last_activity
"""
import structlog
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database.database import get_db, User

logger = structlog.get_logger()


async def track_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Middleware для отслеживания активности пользователей.
    Обновляет поле last_activity при каждом взаимодействии с ботом.
    """
    if not update.effective_user:
        return
    
    user_id = update.effective_user.id
    
    try:
        db = next(get_db())
        user = db.query(User).filter(User.telegram_id == user_id).first()
        
        if user:
            user.last_activity = datetime.utcnow()
            db.commit()
            logger.debug(f"Updated last_activity for user {user_id}")
        else:
            # Создаем нового пользователя, если его нет
            new_user = User(
                telegram_id=user_id,
                username=update.effective_user.username or f"user_{user_id}",
                balance=0,
                last_activity=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.add(new_user)
            db.commit()
            logger.info(f"Created new user {user_id} with initial last_activity")
            
    except Exception as e:
        logger.error(f"Error tracking user activity for {user_id}: {e}")
    finally:
        db.close()
