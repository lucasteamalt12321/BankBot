# admin_system.py - Система проверки прав администратора
import sqlite3
import logging
from functools import wraps
from typing import Optional, Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

# Используем централизованное подключение к БД
from database.connection import get_connection

logger = logging.getLogger(__name__)


class AdminSystem:
    """Система проверки прав администратора для Telegram бота"""

    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Создаёт необходимые таблицы, если они не существуют."""
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    balance REAL DEFAULT 0,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error ensuring schema: {e}")

    def get_db_connection(self) -> sqlite3.Connection:
        """Получение соединения с базой данных"""
        return get_connection(self.db_path)

    def is_admin(self, user_id: int) -> bool:
        """
        Проверка прав администратора пользователя
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            bool: True если пользователь администратор, False иначе
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Проверяем существует ли поле is_admin
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_is_admin = 'is_admin' in column_names

            if has_is_admin:
                cursor.execute(
                    "SELECT is_admin FROM users WHERE telegram_id = ?",
                    (user_id,)
                )

                result = cursor.fetchone()
                conn.close()

                if result:
                    return bool(result['is_admin'])
                else:
                    # Пользователь не найден в базе данных
                    logger.warning(f"User {user_id} not found in database for admin check")
                    from src.config import settings
                    return user_id == settings.ADMIN_TELEGRAM_ID  # Fallback для LucasTeamLuke
            else:
                # Если поля is_admin нет, используем hardcoded проверку
                conn.close()
                from src.config import settings
                return user_id == settings.ADMIN_TELEGRAM_ID  # LucasTeamLuke

        except Exception as e:
            logger.error(f"Error checking admin status for user {user_id}: {e}")
            from src.config import settings
            return user_id == settings.ADMIN_TELEGRAM_ID  # Fallback для LucasTeamLuke

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
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Проверяем, существует ли пользователь
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            if cursor.fetchone():
                conn.close()
                return True  # Пользователь уже существует

            # Проверяем существует ли поле is_admin
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_is_admin = 'is_admin' in column_names

            # Создаем нового пользователя с правильной структурой базы данных
            from datetime import datetime

            if has_is_admin:
                cursor.execute(
                    """INSERT INTO users (telegram_id, username, first_name, balance, is_admin, created_at, last_activity) 
                       VALUES (?, ?, ?, 0, FALSE, ?, ?)""",
                    (user_id, username, first_name, datetime.now(), datetime.now())
                )
            else:
                # Если поля is_admin нет, создаем без него
                cursor.execute(
                    """INSERT INTO users (telegram_id, username, first_name, balance, created_at, last_activity) 
                       VALUES (?, ?, ?, 0, ?, ?)""",
                    (user_id, username, first_name, datetime.now(), datetime.now())
                )

            conn.commit()
            conn.close()

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

            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Проверяем существует ли поле is_admin
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_is_admin = 'is_admin' in column_names

            # Ищем пользователя по username или first_name
            if has_is_admin:
                cursor.execute(
                    "SELECT id, telegram_id, username, first_name, balance, is_admin FROM users WHERE username = ? OR first_name = ?",
                    (clean_username, clean_username)
                )
            else:
                cursor.execute(
                    "SELECT id, telegram_id, username, first_name, balance FROM users WHERE username = ? OR first_name = ?",
                    (clean_username, clean_username)
                )

            result = cursor.fetchone()

            # Если не найден, попробуем найти по частичному совпадению
            if not result:
                if has_is_admin:
                    cursor.execute(
                        "SELECT id, telegram_id, username, first_name, balance, is_admin FROM users WHERE username LIKE ? OR first_name LIKE ?",
                        (f"%{clean_username}%", f"%{clean_username}%")
                    )
                else:
                    cursor.execute(
                        "SELECT id, telegram_id, username, first_name, balance FROM users WHERE username LIKE ? OR first_name LIKE ?",
                        (f"%{clean_username}%", f"%{clean_username}%")
                    )
                result = cursor.fetchone()

            conn.close()

            if result:
                from src.config import settings
                return {
                    'id': result['id'],
                    'telegram_id': result['telegram_id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin']) if has_is_admin else (result['telegram_id'] == settings.ADMIN_TELEGRAM_ID)
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
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Проверяем существует ли поле is_admin
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_is_admin = 'is_admin' in column_names

            if has_is_admin:
                cursor.execute(
                    "SELECT id, telegram_id, username, first_name, balance, is_admin FROM users WHERE telegram_id = ?",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT id, telegram_id, username, first_name, balance FROM users WHERE telegram_id = ?",
                    (user_id,)
                )

            result = cursor.fetchone()
            conn.close()

            if result:
                from src.config import settings
                user_data = {
                    'id': result['id'],
                    'telegram_id': result['telegram_id'],
                    'username': result['username'],
                    'first_name': result['first_name'],
                    'balance': result['balance'],
                    'is_admin': bool(result['is_admin']) if has_is_admin else (user_id == settings.ADMIN_TELEGRAM_ID)
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
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Получаем текущий баланс
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return None

            new_balance = result['balance'] + amount

            # Обновляем баланс
            cursor.execute(
                "UPDATE users SET balance = ? WHERE telegram_id = ?",
                (new_balance, user_id)
            )

            conn.commit()
            conn.close()

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
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Проверяем существует ли поле is_admin
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_is_admin = 'is_admin' in column_names

            if not has_is_admin:
                # Если поля нет, добавляем его
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
                conn.commit()
                logger.info("Added is_admin column to users table")

            cursor.execute(
                "UPDATE users SET is_admin = ? WHERE telegram_id = ?",
                (is_admin, user_id)
            )

            if cursor.rowcount == 0:
                conn.close()
                return False  # Пользователь не найден

            conn.commit()
            conn.close()

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
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM users")
            result = cursor.fetchone()
            conn.close()

            return result['count'] if result else 0

        except Exception as e:
            logger.error(f"Error getting users count: {e}")
            return 0

    def add_transaction(self, user_id: int, amount: float, transaction_type: str, admin_id: int = None) -> Optional[int]:
        """
        Добавление транзакции в базу данных
        
        Args:
            user_id: Telegram ID пользователя
            amount: Сумма транзакции
            transaction_type: Тип транзакции ('add', 'remove', 'buy')
            admin_id: ID администратора (если применимо)
            
        Returns:
            int: ID созданной транзакции или None при ошибке
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Get internal user ID from telegram_id
            cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                logger.error(f"User with telegram_id {user_id} not found")
                conn.close()
                return None

            internal_user_id = user_row['id']

            from datetime import datetime
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, transaction_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (internal_user_id, amount, transaction_type, f"Admin transaction: {transaction_type}", datetime.now())
            )

            transaction_id = cursor.lastrowid
            conn.commit()
            conn.close()

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
