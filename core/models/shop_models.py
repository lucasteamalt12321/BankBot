"""
Data models for the Telegram Bot Shop System
Defines data classes for ShopItem, Purchase, ScheduledTask, and result objects
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class ShopItem:
    """Data class representing a shop item"""
    id: int
    name: str
    price: int
    description: str
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Purchase:
    """Data class representing a user purchase"""
    id: int
    user_id: int
    item_id: int
    purchase_time: datetime
    expires_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None


@dataclass
class ScheduledTask:
    """Data class representing a scheduled task"""
    id: int
    user_id: int
    chat_id: int
    task_type: str
    execute_at: datetime
    message_id: Optional[int] = None
    task_data: Optional[Dict[str, Any]] = None
    is_completed: bool = False
    created_at: Optional[datetime] = None


@dataclass
class PurchaseResult:
    """Result object for purchase operations"""
    success: bool
    message: str
    error_code: Optional[str] = None
    purchase_id: Optional[int] = None
    new_balance: Optional[int] = None


@dataclass
class ProcessResult:
    """Result object for item processing operations"""
    success: bool
    message: str
    error_code: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@dataclass
class BroadcastResult:
    """Result object for broadcast operations"""
    total_users: int
    successful_sends: int
    failed_sends: int
    errors: List[str]
    completion_message: str


@dataclass
class ShopConfig:
    """Configuration for the shop system"""
    owner_id: int
    default_item_price: int = 100
    sticker_duration_hours: int = 24
    broadcast_rate_limit: float = 0.15
    max_broadcast_retries: int = 3


@dataclass
class DatabaseConfig:
    """Database configuration for the shop system"""
    db_url: str
    scheduler_db_url: str
    connection_pool_size: int = 5


@dataclass
class User:
    """Simplified user data class for shop operations"""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    balance: int
    is_admin: bool = False


# Error classes for shop operations
class ShopError(Exception):
    """Base exception for shop-related errors"""
    pass


class InsufficientBalanceError(ShopError):
    """Exception raised when user has insufficient balance"""
    def __init__(self, user_id: int, current_balance: int, required: int):
        self.user_id = user_id
        self.current_balance = current_balance
        self.required = required
        super().__init__(f"User {user_id} has {current_balance}, needs {required}")


class TelegramAPIError(ShopError):
    """Exception raised for Telegram API errors"""
    def __init__(self, error_code: str, description: str):
        self.error_code = error_code
        self.description = description
        super().__init__(f"Telegram API error {error_code}: {description}")


class ItemNotFoundError(ShopError):
    """Exception raised when shop item is not found"""
    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"Shop item {item_id} not found")


class UserNotFoundError(ShopError):
    """Exception raised when user is not found"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")