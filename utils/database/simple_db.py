# simple_db.py - Simplified database functions for admin system
"""
DEPRECATED: Этот модуль устарел. Используйте:
- database.connection для подключения к БД
- utils.admin.admin_system.AdminSystem для работы с пользователями
"""
import sqlite3
import os
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Импортируем централизованное подключение
from database.connection import get_connection

logger = logging.getLogger(__name__)

# Database path - для обратной совместимости
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'bot.db')

def get_db_connection() -> sqlite3.Connection:
    """
    DEPRECATED: Используйте database.connection.get_connection()
    Get database connection with proper configuration
    """
    return get_connection()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram ID"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Clean username (remove @ if present)
        clean_username = username.lstrip('@')
        cursor.execute('SELECT * FROM users WHERE username = ?', (clean_username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user by username {username}: {e}")
        return None
    finally:
        conn.close()

def update_user_balance(user_id: int, amount: float) -> Optional[float]:
    """Update user balance and return new balance"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get current balance
        cursor.execute('SELECT balance FROM users WHERE telegram_id = ?', (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        new_balance = row['balance'] + amount
        
        # Update balance
        cursor.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, user_id))
        conn.commit()
        
        return new_balance
        
    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_internal_user_id(telegram_id: int) -> Optional[int]:
    """Get internal user ID by Telegram ID"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        return row['id'] if row else None
    except Exception as e:
        logger.error(f"Error getting internal user ID for telegram_id {telegram_id}: {e}")
        return None
    finally:
        conn.close()

def add_transaction(user_id: int, amount: float, transaction_type: str, admin_id: int = None, description: str = None) -> Optional[int]:
    """Add transaction record using the actual database structure"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get internal user ID from telegram_id
        internal_user_id = get_internal_user_id(user_id)
        if not internal_user_id:
            logger.error(f"User with telegram_id {user_id} not found")
            return None
        
        # Use the actual column names from the database
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, transaction_type, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (internal_user_id, amount, transaction_type, description or f"Admin transaction: {transaction_type}", datetime.now()))
        
        conn.commit()
        return cursor.lastrowid
        
    except Exception as e:
        logger.error(f"Error adding transaction: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_users_count() -> int:
    """Get total number of users"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM users')
        row = cursor.fetchone()
        return row['count'] if row else 0
    except Exception as e:
        logger.error(f"Error getting users count: {e}")
        return 0
    finally:
        conn.close()

def register_user(user_id: int, username: str = None, first_name: str = None) -> bool:
    """
    Register a new user in the database
    
    DEPRECATED: Use utils.admin.admin_system.AdminSystem.register_user() instead
    
    Args:
        user_id: Telegram user ID
        username: Username (without @)
        first_name: User's first name
        
    Returns:
        True if user was registered, False if user already exists or error occurred
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user_id,))
        if cursor.fetchone():
            return False  # User already exists
        
        # Clean username (remove @ if present)
        clean_username = username.lstrip('@') if username else None
        
        # Insert new user
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, balance, is_admin)
            VALUES (?, ?, ?, 0.0, 0)
        ''', (user_id, clean_username, first_name))
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error registering user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def init_database():
    """
    Initialize database tables
    
    DEPRECATED: Database initialization is handled by database.connection module
    
    This function is kept for backward compatibility with tests.
    """
    # Database initialization is now handled by database.connection
    # This is a no-op for backward compatibility
    pass

# УДАЛЕНО: Дублирует функциональность AdminSystem
# Используйте utils.admin.admin_system.AdminSystem.is_admin()
# Используйте utils.admin.admin_system.AdminSystem.set_admin_status()