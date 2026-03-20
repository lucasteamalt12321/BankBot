"""Abstract database repository interface for balance management."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from src.models import BotBalance, UserBalance


class DatabaseRepository(ABC):
    """Abstract interface for database operations."""
    
    @abstractmethod
    def get_or_create_user(self, user_name: str) -> UserBalance:
        """Get existing user or create new one with zero balance."""
        pass
    
    @abstractmethod
    def get_bot_balance(self, user_id: str, game: str) -> Optional[BotBalance]:
        """Get bot balance for user and game, or None if not exists."""
        pass
    
    @abstractmethod
    def create_bot_balance(
        self,
        user_id: str,
        game: str,
        last_balance: Decimal,
        current_bot_balance: Decimal
    ) -> None:
        """Create new bot balance record."""
        pass
    
    @abstractmethod
    def update_user_balance(self, user_id: str, new_balance: Decimal) -> None:
        """Update user's bank balance."""
        pass
    
    @abstractmethod
    def update_bot_last_balance(
        self,
        user_id: str,
        game: str,
        new_last_balance: Decimal
    ) -> None:
        """Update last_balance field in bot_balances."""
        pass
    
    @abstractmethod
    def update_bot_current_balance(
        self,
        user_id: str,
        game: str,
        new_current_balance: Decimal
    ) -> None:
        """Update current_bot_balance field in bot_balances."""
        pass
    
    @abstractmethod
    def begin_transaction(self) -> None:
        """Start a database transaction."""
        pass
    
    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit current transaction."""
        pass
    
    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        pass
    
    @abstractmethod
    def message_id_exists(self, message_id: str) -> bool:
        """Check if message ID has been processed."""
        pass
    
    @abstractmethod
    def store_message_id(self, message_id: str) -> None:
        """Store message ID to mark it as processed."""
        pass


class SQLiteRepository(DatabaseRepository):
    """SQLite implementation of database repository."""
    
    def __init__(self, db_path: str):
        """
        Initialize with database path and create schema.
        
        Args:
            db_path: Path to SQLite database file
        """
        import sqlite3
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._in_transaction = False
        self._init_schema()
    
    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_balances (
                user_id TEXT PRIMARY KEY,
                user_name TEXT UNIQUE NOT NULL,
                bank_balance TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_balances (
                user_id TEXT NOT NULL,
                game TEXT NOT NULL,
                last_balance TEXT NOT NULL,
                current_bot_balance TEXT NOT NULL,
                PRIMARY KEY (user_id, game),
                FOREIGN KEY (user_id) REFERENCES user_balances(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_messages_timestamp 
            ON processed_messages(processed_at)
        """)
        
        self.conn.commit()
    
    def get_or_create_user(self, user_name: str) -> UserBalance:
        """
        Get existing user or create new one with zero balance.
        
        Args:
            user_name: Name of the user
            
        Returns:
            UserBalance object
        """
        cursor = self.conn.cursor()
        
        # Try to get existing user
        cursor.execute(
            "SELECT user_id, user_name, bank_balance FROM user_balances WHERE user_name = ?",
            (user_name,)
        )
        row = cursor.fetchone()
        
        if row:
            return UserBalance(
                user_id=row[0],
                user_name=row[1],
                bank_balance=Decimal(row[2])
            )
        
        # Create new user with zero balance
        import uuid
        user_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO user_balances (user_id, user_name, bank_balance) VALUES (?, ?, ?)",
            (user_id, user_name, "0")
        )
        if not self._in_transaction:
            self.conn.commit()
        
        return UserBalance(
            user_id=user_id,
            user_name=user_name,
            bank_balance=Decimal(0)
        )
    
    def get_bot_balance(self, user_id: str, game: str) -> Optional[BotBalance]:
        """
        Get bot balance for user and game, or None if not exists.
        
        Args:
            user_id: User identifier
            game: Game name
            
        Returns:
            BotBalance object or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT user_id, game, last_balance, current_bot_balance 
               FROM bot_balances 
               WHERE user_id = ? AND game = ?""",
            (user_id, game)
        )
        row = cursor.fetchone()
        
        if row:
            return BotBalance(
                user_id=row[0],
                game=row[1],
                last_balance=Decimal(row[2]),
                current_bot_balance=Decimal(row[3])
            )
        
        return None
    
    def create_bot_balance(
        self,
        user_id: str,
        game: str,
        last_balance: Decimal,
        current_bot_balance: Decimal
    ) -> None:
        """
        Create new bot balance record.
        
        Args:
            user_id: User identifier
            game: Game name
            last_balance: Last recorded balance from profile
            current_bot_balance: Current accumulated bot balance
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO bot_balances (user_id, game, last_balance, current_bot_balance)
               VALUES (?, ?, ?, ?)""",
            (user_id, game, str(last_balance), str(current_bot_balance))
        )
        if not self._in_transaction:
            self.conn.commit()
    
    def update_user_balance(self, user_id: str, new_balance: Decimal) -> None:
        """
        Update user's bank balance.
        
        Args:
            user_id: User identifier
            new_balance: New bank balance value
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE user_balances SET bank_balance = ? WHERE user_id = ?",
            (str(new_balance), user_id)
        )
        if not self._in_transaction:
            self.conn.commit()
    
    def update_bot_last_balance(
        self,
        user_id: str,
        game: str,
        new_last_balance: Decimal
    ) -> None:
        """
        Update last_balance field in bot_balances.
        
        Args:
            user_id: User identifier
            game: Game name
            new_last_balance: New last balance value
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE bot_balances SET last_balance = ? WHERE user_id = ? AND game = ?",
            (str(new_last_balance), user_id, game)
        )
        if not self._in_transaction:
            self.conn.commit()
    
    def update_bot_current_balance(
        self,
        user_id: str,
        game: str,
        new_current_balance: Decimal
    ) -> None:
        """
        Update current_bot_balance field in bot_balances.
        
        Args:
            user_id: User identifier
            game: Game name
            new_current_balance: New current bot balance value
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE bot_balances SET current_bot_balance = ? WHERE user_id = ? AND game = ?",
            (str(new_current_balance), user_id, game)
        )
        if not self._in_transaction:
            self.conn.commit()
    
    def begin_transaction(self) -> None:
        """Start a database transaction."""
        # SQLite is in autocommit mode by default when using the connection object
        # We need to explicitly begin a transaction
        self.conn.execute("BEGIN")
        self._in_transaction = True
    
    def commit_transaction(self) -> None:
        """Commit current transaction."""
        self.conn.commit()
        self._in_transaction = False
    
    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        self.conn.rollback()
        self._in_transaction = False
    
    def message_id_exists(self, message_id: str) -> bool:
        """
        Check if message ID has been processed.
        
        Args:
            message_id: Unique message identifier
            
        Returns:
            True if message was already processed, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?",
            (message_id,)
        )
        return cursor.fetchone() is not None
    
    def store_message_id(self, message_id: str) -> None:
        """
        Store message ID to mark it as processed.
        
        Args:
            message_id: Unique message identifier
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO processed_messages (message_id) VALUES (?)",
            (message_id,)
        )
        if not self._in_transaction:
            self.conn.commit()
