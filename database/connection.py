"""
Единый модуль для подключения к базе данных
Централизованное управление соединениями с SQLite
"""
import sqlite3
import os
from typing import Optional

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'bot.db')


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Получить соединение с базой данных
    
    Args:
        db_path: Путь к БД (опционально, по умолчанию используется DB_PATH)
    
    Returns:
        sqlite3.Connection: Соединение с БД с настроенным row_factory
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени
    return conn


def get_connection_with_foreign_keys(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Получить соединение с БД с включенными foreign keys
    
    Args:
        db_path: Путь к БД (опционально)
    
    Returns:
        sqlite3.Connection: Соединение с БД с включенными foreign keys
    """
    conn = get_connection(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Для обратной совместимости
def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Алиас для get_connection() для обратной совместимости
    
    Args:
        db_path: Путь к БД (опционально)
    
    Returns:
        sqlite3.Connection: Соединение с БД
    """
    return get_connection(db_path)
