# Design Document: Advanced Telegram Bot Features

## Overview

This design extends the existing telegram-bot-admin-system with three major feature sets: an enhanced shop system with sticker management, message parsing from external bots with currency conversion, and expanded administrative functions. The architecture follows a modular approach with clear separation of concerns, enabling each subsystem to operate independently while integrating seamlessly with the existing bot framework.

The system introduces several new database tables and background processes to support real-time message parsing, automated sticker cleanup, and comprehensive transaction logging. All new features maintain backward compatibility with the existing system while providing extensible foundations for future enhancements.

## Architecture

The advanced features integrate into the existing bot architecture through three primary modules:

### Shop Enhancement Module
- Extends existing shop functionality with item-specific behaviors
- Implements time-based access control for premium features
- Manages sticker permissions and automatic cleanup
- Handles purchase validation and balance deduction

### Message Parser Module
- Monitors group messages using middleware pattern
- Applies regex-based parsing for multiple bot sources
- Converts currencies using configurable multipliers
- Logs all transactions for audit and statistics

### Admin Enhancement Module
- Provides advanced administrative commands
- Implements secure broadcast functionality
- Enables dynamic shop management
- Offers comprehensive user analytics

### Integration Points
- Shared database connection pool for all modules
- Common user authentication and authorization
- Unified logging and error handling
- Consistent async/await patterns throughout

## Components and Interfaces

### ShopManager
```python
class ShopManager:
    async def process_purchase(self, user_id: int, item_number: int) -> PurchaseResult
    async def validate_balance(self, user_id: int, item_price: Decimal) -> bool
    async def activate_item(self, user_id: int, item: ShopItem) -> None
    async def add_item(self, name: str, price: Decimal, item_type: str) -> ShopItem
```

### StickerManager
```python
class StickerManager:
    async def grant_unlimited_access(self, user_id: int, duration_hours: int = 24) -> None
    async def check_access(self, user_id: int) -> bool
    async def cleanup_expired_stickers(self) -> int
    async def auto_delete_sticker(self, message_id: int, delay_minutes: int = 2) -> None
```

### MessageParser
```python
class MessageParser:
    async def parse_message(self, message: Message) -> Optional[ParsedTransaction]
    def load_parsing_rules(self) -> List[ParsingRule]
    async def apply_currency_conversion(self, amount: Decimal, source_bot: str) -> Decimal
    async def log_transaction(self, transaction: ParsedTransaction) -> None
```

### BroadcastSystem
```python
class BroadcastSystem:
    async def broadcast_to_all(self, message: str, sender_id: int) -> BroadcastResult
    async def mention_all_users(self, message: str, sender_id: int) -> BroadcastResult
    async def notify_admins(self, notification: str) -> NotificationResult
```

### AdminManager
```python
class AdminManager:
    async def get_user_stats(self, username: str) -> UserStats
    async def get_parsing_stats(self, timeframe: str) -> ParsingStats
    def is_admin(self, user_id: int) -> bool
    async def broadcast_admin_message(self, message: str, admin_id: int) -> BroadcastResult
```

### BackgroundTaskManager
```python
class BackgroundTaskManager:
    async def start_periodic_cleanup(self) -> None
    async def cleanup_expired_access(self) -> CleanupResult
    async def monitor_parsing_health(self) -> HealthStatus
```

## Data Models

### Enhanced User Model
```python
@dataclass
class User:
    id: int
    username: str
    balance: Decimal
    sticker_unlimited: bool = False
    sticker_unlimited_until: Optional[datetime] = None
    last_activity: datetime
    total_purchases: int = 0
    is_admin: bool = False
```

### Shop Item Model
```python
@dataclass
class ShopItem:
    id: int
    name: str
    price: Decimal
    item_type: str  # 'sticker', 'admin', 'mention_all', 'custom'
    description: str
    is_active: bool = True
    created_at: datetime
```

### Parsing Rule Model
```python
@dataclass
class ParsingRule:
    id: int
    bot_name: str
    pattern: str  # regex pattern
    multiplier: Decimal
    currency_type: str
    is_active: bool = True
```

### Parsed Transaction Model
```python
@dataclass
class ParsedTransaction:
    id: int
    user_id: int
    source_bot: str
    original_amount: Decimal
    converted_amount: Decimal
    currency_type: str
    parsed_at: datetime
    message_text: str
```

### Purchase Record Model
```python
@dataclass
class PurchaseRecord:
    id: int
    user_id: int
    item_id: int
    price_paid: Decimal
    purchased_at: datetime
    expires_at: Optional[datetime] = None
```

### Database Schema Extensions

#### New Tables
```sql
-- Shop items table
CREATE TABLE shop_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    item_type VARCHAR(20) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parsing rules table
CREATE TABLE parsing_rules (
    id SERIAL PRIMARY KEY,
    bot_name VARCHAR(50) NOT NULL,
    pattern VARCHAR(200) NOT NULL,
    multiplier DECIMAL(10,4) NOT NULL,
    currency_type VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Parsed transactions table
CREATE TABLE parsed_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    source_bot VARCHAR(50) NOT NULL,
    original_amount DECIMAL(10,2) NOT NULL,
    converted_amount DECIMAL(10,2) NOT NULL,
    currency_type VARCHAR(20) NOT NULL,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_text TEXT
);

-- Purchase records table
CREATE TABLE purchase_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    item_id INTEGER REFERENCES shop_items(id),
    price_paid DECIMAL(10,2) NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

#### Modified Tables
```sql
-- Add new columns to existing users table
ALTER TABLE users ADD COLUMN sticker_unlimited BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN sticker_unlimited_until TIMESTAMP;
ALTER TABLE users ADD COLUMN total_purchases INTEGER DEFAULT 0;
```

### Configuration Structure
```python
@dataclass
class BotConfig:
    parsing_rules: List[ParsingRule]
    admin_user_ids: List[int]
    sticker_cleanup_interval: int = 300  # 5 minutes
    sticker_auto_delete_delay: int = 120  # 2 minutes
    broadcast_batch_size: int = 50
    max_parsing_retries: int = 3
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Purchase Balance Validation
*For any* user and shop item, when executing a purchase command, the system should validate balance correctly: allowing purchase when balance >= price and rejecting when balance < price
**Validates: Requirements 1.1, 1.2**

### Property 2: Successful Purchase Effects
*For any* successful purchase, the user's balance should decrease by exactly the item price and the item's functionality should be activated for the user
**Validates: Requirements 1.3, 1.4**

### Property 3: Sticker Access Lifecycle
*For any* user purchasing stickers, the system should set unlimited access to True with expiration exactly 24 hours from purchase time, and automatically revoke access when expired
**Validates: Requirements 2.1, 2.2, 2.4**

### Property 4: Sticker Usage Control
*For any* user, sticker operations should be allowed when unlimited access is active and before expiration, and stickers should auto-delete after 2 minutes when unlimited access is False
**Validates: Requirements 2.3, 2.5**

### Property 5: Admin Notification System
*For any* admin item purchase, all administrators should receive notification messages containing purchaser username, user ID, and timestamp, with confirmation sent to the purchaser
**Validates: Requirements 3.1, 3.2, 3.4**

### Property 6: Broadcast Message Delivery
*For any* broadcast operation (mention-all or admin broadcast), the message should be delivered to all registered users with accurate delivery statistics reported
**Validates: Requirements 4.2, 4.4, 8.1, 8.4**

### Property 7: Broadcast Error Handling
*For any* broadcast operation, failed message deliveries should be handled gracefully without stopping the broadcast process, with error reporting provided
**Validates: Requirements 4.5, 8.5**

### Property 8: Message Pattern Parsing
*For any* message from configured external bots matching defined regex patterns, the numeric values should be extracted correctly regardless of the specific bot source
**Validates: Requirements 5.2, 5.3**

### Property 9: Currency Conversion and Logging
*For any* parsed currency amount, the system should apply the correct multiplier, update user balance, and log complete transaction details with all required fields
**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 10: Admin Command Authorization
*For any* administrative command (/parsing_stats, /broadcast, /add_item, /user_stats), the system should verify administrator privileges before execution and reject unauthorized users
**Validates: Requirements 7.4, 8.2, 9.5, 10.5**

### Property 11: Dynamic Shop Management
*For any* valid /add_item command, a new purchasable item should be created with unique name validation, immediate availability through /buy command, and support for all defined item types
**Validates: Requirements 9.1, 9.2, 9.4**

### Property 12: Configuration Management
*For any* configuration update, the system should reload settings without restart, validate syntax with clear error reporting, and provide default values for missing settings
**Validates: Requirements 11.3, 11.4, 11.5**

### Property 13: Background Task Reliability
*For any* background task execution, the system should run at scheduled intervals, handle errors gracefully while continuing operation, and log all activities for monitoring
**Validates: Requirements 12.1, 12.4, 12.5**

### Property 14: Parsing Error Handling
*For any* message parsing attempt, parsing errors should be handled gracefully with failed attempts logged, and the system should continue processing other messages
**Validates: Requirements 6.5**

### Property 15: User Statistics Completeness
*For any* valid /user_stats request, the displayed information should include current balance, total purchases, active subscriptions, last activity timestamp, and parsing transaction history
**Validates: Requirements 10.1, 10.2, 10.3**

## Error Handling

### Input Validation
- All user commands must be validated for correct syntax and parameter types
- Invalid item numbers, usernames, or amounts should return clear error messages
- Malformed regex patterns in configuration should be detected and reported

### Database Error Handling
- Connection failures should trigger automatic retry with exponential backoff
- Transaction rollbacks should occur on any purchase or parsing operation failure
- Database constraint violations should be caught and converted to user-friendly messages

### External Service Integration
- Telegram API rate limits should be respected with automatic throttling
- Message delivery failures should be logged and retried up to 3 times
- Network timeouts should not crash the application

### Background Task Error Handling
- Failed background tasks should log errors and continue with next scheduled execution
- Database connection issues during cleanup should not prevent future cleanup attempts
- File system errors during sticker cleanup should be logged but not halt the process

### Configuration Error Handling
- Invalid parsing rules should be skipped with warnings logged
- Missing configuration files should use default values
- Malformed JSON or YAML configuration should provide clear syntax error messages

## Testing Strategy

### Dual Testing Approach
The system requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests** focus on:
- Specific command parsing examples (/buy 1, /broadcast hello)
- Edge cases like empty balances, expired access, invalid usernames
- Integration points between modules
- Error conditions and exception handling
- Database constraint violations

**Property Tests** focus on:
- Universal properties that hold for all inputs
- Comprehensive input coverage through randomization
- Correctness properties defined in this design document
- Round-trip operations (parse→convert→store→retrieve)

### Property-Based Testing Configuration
- **Library**: Use `hypothesis` for Python implementation
- **Iterations**: Minimum 100 iterations per property test
- **Test Tagging**: Each property test must reference its design document property
- **Tag Format**: `# Feature: telegram-bot-advanced-features, Property {number}: {property_text}`

### Test Data Management
- Use factory patterns to generate realistic test data
- Implement database fixtures for consistent test environments
- Mock external Telegram API calls for isolated testing
- Create parsing_examples.txt with realistic bot message samples

### Integration Testing
- Test complete purchase workflows from command to database update
- Verify message parsing pipeline from detection to balance update
- Test broadcast systems with multiple user scenarios
- Validate background task execution and cleanup operations

### Performance Testing
- Broadcast performance with large user bases (1000+ users)
- Message parsing throughput under high message volume
- Database query performance with large transaction histories
- Background task execution time and resource usage