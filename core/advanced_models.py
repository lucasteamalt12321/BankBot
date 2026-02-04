"""
Data models for the Advanced Telegram Bot Features
Defines data classes for new entities: ShopItem, ParsingRule, ParsedTransaction, PurchaseRecord
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal


@dataclass
class ShopItem:
    """Enhanced shop item model for advanced features"""
    id: int
    name: str
    price: Decimal
    item_type: str  # 'sticker', 'admin', 'mention_all', 'custom'
    description: str
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class ParsingRule:
    """Data class for message parsing rules"""
    id: int
    bot_name: str
    pattern: str  # regex pattern
    multiplier: Decimal
    currency_type: str
    is_active: bool = True


@dataclass
class ParsedTransaction:
    """Data class for parsed transaction records"""
    id: int
    user_id: int
    source_bot: str
    original_amount: Decimal
    converted_amount: Decimal
    currency_type: str
    parsed_at: datetime
    message_text: str


@dataclass
class PurchaseRecord:
    """Data class for purchase records"""
    id: int
    user_id: int
    item_id: int
    price_paid: Decimal
    purchased_at: datetime
    expires_at: Optional[datetime] = None


@dataclass
class EnhancedUser:
    """Enhanced user model with new fields for advanced features"""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    balance: Decimal
    daily_streak: int = 0
    last_daily: Optional[datetime] = None
    total_earned: Decimal = Decimal('0')
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    is_vip: bool = False
    vip_until: Optional[datetime] = None
    is_admin: bool = False
    # New fields for advanced features
    sticker_unlimited: bool = False
    sticker_unlimited_until: Optional[datetime] = None
    total_purchases: int = 0


# Result classes for operations
@dataclass
class PurchaseResult:
    """Result object for purchase operations"""
    success: bool
    message: str
    error_code: Optional[str] = None
    purchase_id: Optional[int] = None
    new_balance: Optional[Decimal] = None


@dataclass
class BroadcastResult:
    """Result object for broadcast operations"""
    total_users: int
    successful_sends: int
    failed_sends: int
    errors: List[str]
    completion_message: str
    execution_time: float = 0.0


@dataclass
class NotificationResult:
    """Result object for notification operations"""
    success: bool
    message: str
    notified_admins: int
    failed_notifications: int


@dataclass
class ParsingResult:
    """Result object for message parsing operations"""
    success: bool
    parsed_amount: Optional[Decimal] = None
    converted_amount: Optional[Decimal] = None
    source_bot: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class CleanupResult:
    """Result object for cleanup operations"""
    cleaned_users: int
    cleaned_files: int
    errors: List[str]
    completion_message: str


@dataclass
class UserStats:
    """Data class for comprehensive user statistics"""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    current_balance: int
    total_purchases: int
    total_earned: int
    total_parsing_earnings: float
    last_activity: str  # ISO format datetime string
    created_at: str  # ISO format datetime string
    active_subscriptions: List[Dict[str, Any]]
    parsing_transaction_history: List[Dict[str, Any]]
    recent_purchases: List[Dict[str, Any]]
    is_admin: bool
    is_vip: bool
    daily_streak: int


@dataclass
class ParsingStats:
    """Data class for comprehensive parsing statistics"""
    timeframe: str
    period_name: str
    start_time: str  # ISO format datetime string
    end_time: str  # ISO format datetime string
    total_transactions: int
    successful_parses: int
    failed_parses: int
    total_amount_converted: float
    success_rate: float
    active_bots: int
    total_configured_bots: int
    bot_statistics: List[Dict[str, Any]]
    parsing_rules: List[Dict[str, Any]]


@dataclass
class HealthStatus:
    """Data class for system health status"""
    is_healthy: bool
    parsing_active: bool
    background_tasks_running: bool
    database_connected: bool
    last_check: datetime
    errors: List[str]


# Configuration classes
@dataclass
class BotConfig:
    """Configuration for the advanced bot features"""
    parsing_rules: List[ParsingRule]
    admin_user_ids: List[int]
    sticker_cleanup_interval: int = 300  # 5 minutes
    sticker_auto_delete_delay: int = 120  # 2 minutes
    broadcast_batch_size: int = 50
    max_parsing_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization"""
        return {
            'parsing_rules': [
                {
                    'id': rule.id,
                    'bot_name': rule.bot_name,
                    'pattern': rule.pattern,
                    'multiplier': float(rule.multiplier),
                    'currency_type': rule.currency_type,
                    'is_active': rule.is_active
                } for rule in self.parsing_rules
            ],
            'admin_user_ids': self.admin_user_ids,
            'sticker_cleanup_interval': self.sticker_cleanup_interval,
            'sticker_auto_delete_delay': self.sticker_auto_delete_delay,
            'broadcast_batch_size': self.broadcast_batch_size,
            'max_parsing_retries': self.max_parsing_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotConfig':
        """Create configuration from dictionary"""
        from decimal import Decimal
        
        parsing_rules = []
        for rule_data in data.get('parsing_rules', []):
            rule = ParsingRule(
                id=rule_data['id'],
                bot_name=rule_data['bot_name'],
                pattern=rule_data['pattern'],
                multiplier=Decimal(str(rule_data['multiplier'])),
                currency_type=rule_data['currency_type'],
                is_active=rule_data.get('is_active', True)
            )
            parsing_rules.append(rule)
        
        return cls(
            parsing_rules=parsing_rules,
            admin_user_ids=data.get('admin_user_ids', []),
            sticker_cleanup_interval=data.get('sticker_cleanup_interval', 300),
            sticker_auto_delete_delay=data.get('sticker_auto_delete_delay', 120),
            broadcast_batch_size=data.get('broadcast_batch_size', 50),
            max_parsing_retries=data.get('max_parsing_retries', 3)
        )
    
    def validate_schema(self) -> List[str]:
        """Validate configuration against schema requirements"""
        errors = []
        
        # Validate parsing rules
        if not isinstance(self.parsing_rules, list):
            errors.append("parsing_rules must be a list")
        
        # Validate admin user IDs
        if not isinstance(self.admin_user_ids, list):
            errors.append("admin_user_ids must be a list")
        elif not all(isinstance(uid, int) and uid > 0 for uid in self.admin_user_ids):
            errors.append("admin_user_ids must contain positive integers")
        
        # Validate timing configurations
        if not isinstance(self.sticker_cleanup_interval, int) or self.sticker_cleanup_interval <= 0:
            errors.append("sticker_cleanup_interval must be a positive integer")
        
        if not isinstance(self.sticker_auto_delete_delay, int) or self.sticker_auto_delete_delay <= 0:
            errors.append("sticker_auto_delete_delay must be a positive integer")
        
        if not isinstance(self.broadcast_batch_size, int) or self.broadcast_batch_size <= 0:
            errors.append("broadcast_batch_size must be a positive integer")
        
        if not isinstance(self.max_parsing_retries, int) or self.max_parsing_retries <= 0:
            errors.append("max_parsing_retries must be a positive integer")
        
        return errors


@dataclass
class ConfigurationBackup:
    """Configuration backup metadata"""
    backup_id: str
    created_at: datetime
    config_data: Dict[str, Any]
    description: str
    created_by: Optional[int] = None  # Admin user ID who created backup


# Error classes for advanced features
class AdvancedFeatureError(Exception):
    """Base exception for advanced feature errors"""
    pass


class ParsingError(AdvancedFeatureError):
    """Exception raised for message parsing errors"""
    def __init__(self, message: str, source_bot: str = None):
        self.source_bot = source_bot
        super().__init__(message)


class StickerAccessError(AdvancedFeatureError):
    """Exception raised for sticker access errors"""
    def __init__(self, user_id: int, message: str):
        self.user_id = user_id
        super().__init__(message)


class BroadcastError(AdvancedFeatureError):
    """Exception raised for broadcast errors"""
    def __init__(self, message: str, failed_users: List[int] = None):
        self.failed_users = failed_users or []
        super().__init__(message)


class ConfigurationError(AdvancedFeatureError):
    """Exception raised for configuration errors"""
    pass


class BackgroundTaskError(AdvancedFeatureError):
    """Exception raised for background task errors"""
    pass