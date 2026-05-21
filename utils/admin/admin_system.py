# admin_system.py - Система проверки прав администратора
import logging
from functools import wraps
from typing import Optional, Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy import inspect, text

from database.database import SessionLocal

logger = logging.getLogger(__name__)


class AdminSystem:
    """Система проверки прав администратора для Telegram бота"""

    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Создаёт необходимые таблицы, если они не существуют."""
        try:
            from database.database import Base, engine

            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.error(f"Error ensuring schema: {e}")

    def _has_column(self, table_name: str, column_name: str) -> bool:
        """Check whether a column exists in current SQLAlchemy database."""
        db = SessionLocal()
        try:
            inspector = inspect(db.bind)
            return column_name in [column["name"] for column in inspector.get_columns(table_name)]
        finally:
            db.close()

    @staticmethod
    def _row_to_dict(row) -> Optional[dict]:
        """Convert SQLAlchemy row/mapping to dict."""
        if row is None:
            return None
        return dict(row._mapping)

    def is_admin(self, user_id: int) -> bool:
        """
        Проверка прав администратора пользователя
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            bool: True если пользователь администратор, False иначе
        """
        try:
            db = SessionLocal()
            try:
                result = db.execute(
                    text("SELECT is_admin FROM users WHERE telegram_id = :telegram_id"),
                    {"telegram_id": user_id},
                ).mappings().first()
            finally:
                db.close()

            if result:
                return bool(result["is_admin"])

            logger.warning(f"User {user_id} not found in database for admin check")
            from src.config import settings
            return user_id == settings.ADMIN_TELEGRAM_ID

        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
            from src.config import settings
            return user_id == settings.ADMIN_TELEGRAM_ID

    def register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """
        Регистрация нового пользователя в системе
        
        Args:
            user_id: Telegram ID пользователя
            username: Username пользователя (без @)
            first_name: Имя пользователя
            
        Returns:
            bool: True если пользователь зарегистрирован успешно
        """
        try:
            from datetime import datetime

            db = SessionLocal()
            try:
                existing_user = db.execute(
                    text("SELECT id FROM users WHERE telegram_id = :telegram_id"),
                    {"telegram_id": user_id},
                ).first()
                if existing_user:
                    return True

                now = datetime.now()
                db.execute(
                    text(
                        """
                        INSERT INTO users (
                            telegram_id, username, first_name, balance,
                            is_admin, created_at, last_activity
                        ) VALUES (
                            :telegram_id, :username, :first_name, 0,
                            false, :created_at, :last_activity
                        )
                        """
                    ),
                    {
                        "telegram_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "created_at": now,
                        "last_activity": now,
                    },
                )
                db.commit()
            finally:
                db.close()

            logger.info(f"User {user_id} registered successfully")
            return True

        except Exception as e:
            logger.error(f"Error registering user {user_id}: {e}")
            return False

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        Поиск пользователя по username
        
        Args:
            username: Username пользователя (с @ или без)
            
        Returns:
            dict: Данные пользователя или None если не найден
        """
        try:
            # Убираем @ если есть
            clean_username = username.lstrip('@')

            db = SessionLocal()
            try:
                result = db.execute(
                    text(
                        """
                        SELECT id, telegram_id, username, first_name, balance, is_admin
                        FROM users
                        WHERE username = :username OR first_name = :first_name
                        """
                    ),
                    {"username": clean_username, "first_name": clean_username},
                ).mappings().first()

                if not result:
                    result = db.execute(
                        text(
                            """
                            SELECT id, telegram_id, username, first_name, balance, is_admin
                            FROM users
                            WHERE username LIKE :pattern OR first_name LIKE :pattern
                            """
                        ),
                        {"pattern": f"%{clean_username}%"},
                    ).mappings().first()
            finally:
                db.close()

            if result:
                return {
                    'id': result['id'],
                    'telegram_id': result['telegram_id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin']),
                }
            else:
                return None

        except Exception as e:
            logger.error(f"Error finding user by username {username}: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        Поиск пользователя по ID
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            dict: Данные пользователя или None если не найден
        """
        try:
            db = SessionLocal()
            try:
                result = db.execute(
                    text(
                        """
                        SELECT id, telegram_id, username, first_name, balance, is_admin
                        FROM users
                        WHERE telegram_id = :telegram_id
                        """
                    ),
                    {"telegram_id": user_id},
                ).mappings().first()
            finally:
                db.close()

            if result:
                user_data = {
                    'id': result['id'],
                    'telegram_id': result['telegram_id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin']),
                }
                return user_data
            else:
                return None

        except Exception as e:
            logger.error(f"Error finding user by ID {user_id}: {e}")
            return None

    def update_balance(self, user_id: int, amount: float) -> Optional[float]:
        """
        Обновление баланса пользователя
        
        Args:
            user_id: ID пользователя
            amount: Сумма для добавления (может быть отрицательной)
            
        Returns:
            float: Новый баланс или None при ошибке
        """
        try:
            db = SessionLocal()
            try:
                result = db.execute(
                    text("SELECT balance FROM users WHERE telegram_id = :telegram_id"),
                    {"telegram_id": user_id},
                ).mappings().first()

                if not result:
                    return None

                new_balance = result['balance'] + amount

                db.execute(
                    text("UPDATE users SET balance = :balance WHERE telegram_id = :telegram_id"),
                    {"balance": new_balance, "telegram_id": user_id},
                )
                db.commit()
            finally:
                db.close()

            return new_balance

        except Exception as e:
            logger.error(f"Error updating balance for user {user_id}: {e}")
            return None

    def set_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """
        Установка статуса администратора для пользователя
        
        Args:
            user_id: ID пользователя
            is_admin: Статус администратора
            
        Returns:
            bool: True если статус обновлен успешно
        """
        try:
            db = SessionLocal()
            try:
                result = db.execute(
                    text("UPDATE users SET is_admin = :is_admin WHERE telegram_id = :telegram_id"),
                    {"is_admin": is_admin, "telegram_id": user_id},
                )

                if result.rowcount == 0:
                    return False

                db.commit()
            finally:
                db.close()

            logger.info(f"Admin status for user {user_id} set to {is_admin}")
            return True

        except Exception as e:
            logger.error(f"Error setting admin status for user {user_id}: {e}")
            return False

    def get_users_count(self) -> int:
        """
        Получение общего количества пользователей
        
        Returns:
            int: Количество пользователей
        """
        try:
            db = SessionLocal()
            try:
                result = db.execute(text("SELECT COUNT(*) AS count FROM users")).mappings().first()
            finally:
                db.close()

            return result['count'] if result else 0

        except Exception as e:
            logger.error(f"Error getting users count: {e}")
            return 0

    def add_transaction(
        self,
        user_id: int,
        amount: float,
        transaction_type: str,
        admin_id: int = None,
        description: str | None = None,
    ) -> Optional[int]:
        """
        Добавление транзакции в базу данных
        
        Args:
            user_id: Telegram ID пользователя
            amount: Сумма транзакции
            transaction_type: Тип транзакции ('add', 'remove', 'buy')
            admin_id: ID администратора (если применимо)
            description: Комментарий/описание транзакции
            
        Returns:
            int: ID созданной транзакции или None при ошибке
        """
        try:
            from datetime import datetime

            db = SessionLocal()
            try:
                user_row = db.execute(
                    text("SELECT id FROM users WHERE telegram_id = :telegram_id"),
                    {"telegram_id": user_id},
                ).mappings().first()
                if not user_row:
                    logger.error(f"User with telegram_id {user_id} not found")
                    return None

                db.execute(
                    text(
                        """
                        INSERT INTO transactions (
                            user_id, amount, transaction_type, description, created_at
                        ) VALUES (
                            :user_id, :amount, :transaction_type, :description, :created_at
                        )
                        """
                    ),
                    {
                        "user_id": user_row["id"],
                        "amount": amount,
                        "transaction_type": transaction_type,
                        "description": description or f"Admin transaction: {transaction_type}",
                        "created_at": datetime.now(),
                    },
                )
                db.commit()
                transaction_id = db.execute(text("SELECT MAX(id) FROM transactions")).scalar()
            finally:
                db.close()

            logger.info(f"Transaction {transaction_id} created for user {user_id}")
            return transaction_id

        except Exception as e:
            logger.error(f"Error adding transaction for user {user_id}: {e}")
            return None


def admin_required(admin_system: AdminSystem):
    """
    Декоратор для защиты административных команд
    
    Args:
        admin_system: Экземпляр AdminSystem для проверки прав
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
            user = update.effective_user

            if not user:
                await update.message.reply_text("❌ Не удалось определить пользователя")
                return

            # Проверяем права администратора
            if not admin_system.is_admin(user.id):
                await update.message.reply_text(
                    "🔒 У вас нет прав администратора для выполнения этой команды.\n"
                    "Обратитесь к администратору бота для получения доступа."
                )
                logger.warning(f"User {user.id} (@{user.username}) attempted to use admin command without permissions")
                return

            # Выполняем оригинальную функцию
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in admin command {func.__name__}: {e}")
                await update.message.reply_text(
                    "❌ Произошла ошибка при выполнении команды. "
                    "Попробуйте позже или обратитесь к разработчику."
                )

        return wrapper
    return decorator


class PermissionError(Exception):
    """Исключение для ошибок доступа"""
    pass


class UserNotFoundError(Exception):
    """Исключение когда пользователь не найден"""
    pass


class InsufficientBalanceError(Exception):
    """Исключение при недостаточном балансе"""
    pass
