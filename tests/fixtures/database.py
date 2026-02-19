"""
Общие фикстуры для работы с базой данных в тестах
Централизованная инициализация таблиц и подключений
"""
import pytest
import sqlite3
import tempfile
import os
from typing import Generator


@pytest.fixture
def test_db_path() -> Generator[str, None, None]:
    """
    Фикстура для создания временного файла БД
    
    Yields:
        str: Путь к временной БД
    """
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = db_file.name
    db_file.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_db_connection(test_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Фикстура для подключения к тестовой БД
    
    Args:
        test_db_path: Путь к тестовой БД
    
    Yields:
        sqlite3.Connection: Соединение с тестовой БД
    """
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    
    yield conn
    
    conn.close()


def init_admin_tables(conn: sqlite3.Connection) -> None:
    """
    Инициализация таблиц для административной системы
    
    Args:
        conn: Соединение с БД
    """
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            type TEXT,
            admin_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (admin_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()


def init_shop_tables(conn: sqlite3.Connection) -> None:
    """
    Инициализация таблиц для магазина
    
    Args:
        conn: Соединение с БД
    """
    cursor = conn.cursor()
    
    # Таблица категорий магазина
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Таблица товаров магазина
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            description TEXT,
            price INTEGER,
            item_type TEXT,
            meta_data TEXT,
            purchase_limit INTEGER DEFAULT 0,
            cooldown_hours INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (category_id) REFERENCES shop_categories (id)
        )
    ''')
    
    # Таблица покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (item_id) REFERENCES shop_items (id)
        )
    ''')
    
    conn.commit()


def init_all_tables(conn: sqlite3.Connection) -> None:
    """
    Инициализация всех таблиц БД
    
    Args:
        conn: Соединение с БД
    """
    init_admin_tables(conn)
    init_shop_tables(conn)


@pytest.fixture
def admin_db(test_db_connection: sqlite3.Connection) -> sqlite3.Connection:
    """
    Фикстура для БД с таблицами административной системы
    
    Args:
        test_db_connection: Соединение с тестовой БД
    
    Returns:
        sqlite3.Connection: БД с инициализированными таблицами
    """
    init_admin_tables(test_db_connection)
    return test_db_connection


@pytest.fixture
def shop_db(test_db_connection: sqlite3.Connection) -> sqlite3.Connection:
    """
    Фикстура для БД с таблицами магазина
    
    Args:
        test_db_connection: Соединение с тестовой БД
    
    Returns:
        sqlite3.Connection: БД с инициализированными таблицами магазина
    """
    init_shop_tables(test_db_connection)
    return test_db_connection


@pytest.fixture
def full_db(test_db_connection: sqlite3.Connection) -> sqlite3.Connection:
    """
    Фикстура для БД со всеми таблицами
    
    Args:
        test_db_connection: Соединение с тестовой БД
    
    Returns:
        sqlite3.Connection: БД со всеми таблицами
    """
    init_all_tables(test_db_connection)
    return test_db_connection


@pytest.fixture
def db_with_foreign_keys(test_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Фикстура для БД с включенными foreign keys
    
    Args:
        test_db_path: Путь к тестовой БД
    
    Yields:
        sqlite3.Connection: Соединение с БД с foreign keys
    """
    conn = sqlite3.connect(test_db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    
    init_all_tables(conn)
    
    yield conn
    
    conn.close()
