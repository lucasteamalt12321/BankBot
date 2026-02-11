# simple_db.py - Simplified database functions for admin system
import sqlite3
import os
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Database path - используем основную базу данных
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'bot.db')

def get_db_connection() -> sqlite3.Connection:
    """Get database connection with proper configuration"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    return conn

def register_user(user_id: int, username: str = None, first_name: str = None) -> bool:
    """Register a new user in the admin system"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if user already exists by telegram_id
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user_id,))
        if cursor.fetchone():
            return False  # User already exists
        
        # Clean username (remove @ if present)
        clean_username = username.lstrip('@') if username else None
        
        # Insert new user using the actual database structure
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, balance, is_admin, created_at, last_activity)
            VALUES (?, ?, ?, 0, FALSE, ?, ?)
        ''', (user_id, clean_username, first_name, datetime.now(), datetime.now()))
        
        conn.commit()
        logger.info(f"User {user_id} registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error registering user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

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

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE telegram_id = ?', (user_id,))
        row = cursor.fetchone()
        return bool(row['is_admin']) if row else False
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id}: {e}")
        return False
    finally:
        conn.close()

def set_admin_status(user_id: int, is_admin_flag: bool) -> bool:
    """Set admin status for user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = ? WHERE telegram_id = ?', (is_admin_flag, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error setting admin status for user {user_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()