"""
Database manager for the Telegram Bot Shop System
Handles database operations for shop items, purchases, and scheduled tasks
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from core.shop_models import ShopItem, Purchase, ScheduledTask, User


class ShopDatabaseManager:
    """Database manager for shop system operations"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.create_tables()
        self.initialize_default_items()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def create_tables(self):
        """Create the shop system tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create shop_items table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            price INTEGER NOT NULL DEFAULT 100,
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Create user_purchases table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            data JSON NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (item_id) REFERENCES shop_items(id)
        );
        """)
        
        # Create scheduled_tasks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_id INTEGER NULL,
            chat_id INTEGER NOT NULL,
            task_type VARCHAR(50) NOT NULL,
            execute_at TIMESTAMP NOT NULL,
            task_data JSON NULL,
            is_completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)
        
        conn.commit()
        conn.close()
    
    def initialize_default_items(self):
        """Initialize the three default shop items"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if items already exist
        cursor.execute("SELECT COUNT(*) FROM shop_items")
        count = cursor.fetchone()[0]
        
        if count == 0:
            default_items = [
                ('Безлимитные стикеры на 24 часа', 100, 'Получите возможность отправлять неограниченное количество стикеров в течение 24 часов'),
                ('Запрос на админ-права', 100, 'Отправить запрос владельцу бота на получение прав администратора'),
                ('Рассылка сообщения всем пользователям', 100, 'Отправить ваше сообщение всем пользователям бота')
            ]
            
            for name, price, description in default_items:
                cursor.execute("""
                INSERT INTO shop_items (name, price, description, is_active)
                VALUES (?, ?, ?, TRUE)
                """, (name, price, description))
            
            conn.commit()
        
        conn.close()
    
    def get_shop_items(self) -> List[ShopItem]:
        """Get all active shop items"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, name, price, description, is_active
        FROM shop_items
        WHERE is_active = TRUE
        ORDER BY id
        """)
        
        items = []
        for row in cursor.fetchall():
            items.append(ShopItem(
                id=row['id'],
                name=row['name'],
                price=row['price'],
                description=row['description'],
                is_active=bool(row['is_active']),
                created_at=None  # Set to None since column doesn't exist
            ))
        
        conn.close()
        return items
    
    def get_shop_item(self, item_id: int) -> Optional[ShopItem]:
        """Get a specific shop item by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, name, price, description, is_active
        FROM shop_items
        WHERE id = ? AND is_active = TRUE
        """, (item_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return ShopItem(
                id=row['id'],
                name=row['name'],
                price=row['price'],
                description=row['description'],
                is_active=bool(row['is_active']),
                created_at=None  # Set to None since column doesn't exist
            )
        return None
    
    def create_purchase(self, user_id: int, item_id: int, expires_at: Optional[datetime] = None, 
                       data: Optional[Dict[str, Any]] = None) -> int:
        """Create a new purchase record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        data_json = json.dumps(data) if data else None
        expires_at_str = expires_at.isoformat() if expires_at else None
        
        cursor.execute("""
        INSERT INTO user_purchases (user_id, item_id, purchase_time, expires_at, data)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, item_id, datetime.utcnow().isoformat(), expires_at_str, data_json))
        
        purchase_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return purchase_id
    
    def get_user_purchases(self, user_id: int) -> List[Purchase]:
        """Get all purchases for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, user_id, item_id, purchase_time, expires_at, data
        FROM user_purchases
        WHERE user_id = ?
        ORDER BY purchase_time DESC
        """, (user_id,))
        
        purchases = []
        for row in cursor.fetchall():
            purchase_time = datetime.fromisoformat(row['purchase_time'])
            expires_at = datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None
            data = json.loads(row['data']) if row['data'] else None
            
            purchases.append(Purchase(
                id=row['id'],
                user_id=row['user_id'],
                item_id=row['item_id'],
                purchase_time=purchase_time,
                expires_at=expires_at,
                data=data
            ))
        
        conn.close()
        return purchases
    
    def create_scheduled_task(self, user_id: int, chat_id: int, task_type: str, 
                            execute_at: datetime, message_id: Optional[int] = None,
                            task_data: Optional[Dict[str, Any]] = None) -> int:
        """Create a new scheduled task"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        task_data_json = json.dumps(task_data) if task_data else None
        
        cursor.execute("""
        INSERT INTO scheduled_tasks (user_id, message_id, chat_id, task_type, execute_at, task_data, is_completed, created_at)
        VALUES (?, ?, ?, ?, ?, ?, FALSE, ?)
        """, (user_id, message_id, chat_id, task_type, execute_at.isoformat(), task_data_json, datetime.utcnow().isoformat()))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task_id
    
    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all pending scheduled tasks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, user_id, message_id, chat_id, task_type, execute_at, task_data, is_completed, created_at
        FROM scheduled_tasks
        WHERE is_completed = FALSE
        ORDER BY execute_at
        """)
        
        tasks = []
        for row in cursor.fetchall():
            execute_at = datetime.fromisoformat(row['execute_at'])
            created_at = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            task_data = json.loads(row['task_data']) if row['task_data'] else None
            
            tasks.append(ScheduledTask(
                id=row['id'],
                user_id=row['user_id'],
                chat_id=row['chat_id'],
                task_type=row['task_type'],
                execute_at=execute_at,
                message_id=row['message_id'],
                task_data=task_data,
                is_completed=bool(row['is_completed']),
                created_at=created_at
            ))
        
        conn.close()
        return tasks
    
    def complete_task(self, task_id: int):
        """Mark a scheduled task as completed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE scheduled_tasks
        SET is_completed = TRUE
        WHERE id = ?
        """, (task_id,))
        
        conn.commit()
        conn.close()
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, telegram_id, username, first_name, balance, is_admin
        FROM users
        WHERE telegram_id = ?
        """, (telegram_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                id=row['id'],
                telegram_id=row['telegram_id'],
                username=row['username'],
                first_name=row['first_name'],
                balance=row['balance'],
                is_admin=bool(row['is_admin'])
            )
        return None
    
    def update_user_balance(self, user_id: int, new_balance: int):
        """Update user balance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE users
        SET balance = ?
        WHERE id = ?
        """, (new_balance, user_id))
        
        conn.commit()
        conn.close()
    
    def add_transaction(self, user_id: int, amount: int, transaction_type: str, description: str):
        """Add a transaction record"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO transactions (user_id, amount, transaction_type, description, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, transaction_type, description, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self) -> List[User]:
        """Get all users from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, telegram_id, username, first_name, balance, is_admin
        FROM users
        ORDER BY id
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append(User(
                id=row['id'],
                telegram_id=row['telegram_id'],
                username=row['username'],
                first_name=row['first_name'],
                balance=row['balance'],
                is_admin=bool(row['is_admin'])
            ))
        
        conn.close()
        return users