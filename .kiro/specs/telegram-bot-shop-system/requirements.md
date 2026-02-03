# Requirements Document

## Introduction

A Telegram bot shop system that allows users to purchase virtual items using an in-bot coin currency. The system provides three purchasable items: unlimited stickers for 24 hours, admin rights requests, and broadcast messaging capabilities. All items cost 100 coins and integrate with an existing bot that has a balance system and admin commands.

## Glossary

- **Shop_System**: The complete shop functionality within the Telegram bot
- **User**: A Telegram user interacting with the bot
- **Bot_Owner**: The person who owns and operates the bot (identified by OWNER_ID)
- **Coin**: The virtual currency used within the bot
- **Sticker_Item**: The unlimited stickers for 24 hours shop item
- **Admin_Request_Item**: The admin rights request shop item
- **Broadcast_Item**: The broadcast message to all users shop item
- **Purchase**: A transaction where a user buys a shop item
- **Scheduler**: APScheduler system for managing delayed tasks
- **FSM**: Finite State Machine for managing user conversation states
- **Balance**: The amount of coins a user currently has

## Requirements

### Requirement 1: Shop Display

**User Story:** As a user, I want to view available shop items with their prices, so that I can decide what to purchase.

#### Acceptance Criteria

1. WHEN a user sends the `/shop` command, THE Shop_System SHALL display a formatted list of all available items
2. THE Shop_System SHALL show each item with its name, description, and price in coins
3. THE Shop_System SHALL include purchase commands for each item in the display
4. THE Shop_System SHALL format the display as: "🛒 МАГАЗИН" followed by numbered items and purchase instructions

### Requirement 2: Purchase Processing

**User Story:** As a user, I want to purchase shop items using my coin balance, so that I can access premium features.

#### Acceptance Criteria

1. WHEN a user sends a purchase command (`/buy_1`, `/buy_2`, `/buy_3`), THE Shop_System SHALL verify the user has sufficient balance
2. IF the user has insufficient balance, THEN THE Shop_System SHALL respond with "Недостаточно средств! Ваш баланс: X"
3. WHEN a user has sufficient balance (>= 100 coins), THE Shop_System SHALL deduct 100 coins from their balance
4. WHEN a purchase is successful, THE Shop_System SHALL execute the corresponding item logic
5. THE Shop_System SHALL log all purchases in the transactions table with type 'shop_purchase'

### Requirement 3: Unlimited Stickers Item

**User Story:** As a user, I want to purchase unlimited stickers for 24 hours, so that I can send stickers without restrictions.

#### Acceptance Criteria

1. WHEN a user purchases the stickers item, THE Shop_System SHALL send the message "Вы получили безлимитные стикеры на 24 часа!"
2. THE Scheduler SHALL automatically delete this message after exactly 24 hours
3. WHEN deleting the expired message, THE Shop_System SHALL send "Время действия стикеров истекло!"
4. THE Shop_System SHALL persist scheduled deletion tasks to survive bot restarts
5. THE Shop_System SHALL restore active timers from the database when the bot starts

### Requirement 4: Admin Rights Request Item

**User Story:** As a user, I want to request admin rights through the shop, so that I can potentially become a bot administrator.

#### Acceptance Criteria

1. WHEN a user purchases the admin request item, THE Shop_System SHALL send a private message to the Bot_Owner
2. THE Shop_System SHALL format the owner message as: "Пользователь @username (ID: user_id) купил админку. Хочет стать администратором. Его текущий баланс: X монет"
3. THE Shop_System SHALL send confirmation to the purchaser: "Запрос на админ-права отправлен владельцу бота"
4. THE Shop_System SHALL handle cases where the user has no username by using their user ID

### Requirement 5: Broadcast Message Item

**User Story:** As a user, I want to send a message to all bot users, so that I can communicate with the entire user base.

#### Acceptance Criteria

1. WHEN a user purchases the broadcast item, THE Shop_System SHALL prompt "Введите текст для рассылки:"
2. THE FSM SHALL wait for the user's text input after the purchase
3. WHEN text is received, THE Shop_System SHALL send the message to all users in the database
4. THE Shop_System SHALL format broadcast messages as "@username, [message text]" or use first_name if no username
5. THE Shop_System SHALL add delays of 0.1-0.2 seconds between message sends to respect Telegram API limits
6. WHEN broadcast is complete, THE Shop_System SHALL notify the sender: "Рассылка выполнена! Сообщение отправлено X пользователям"
7. THE Shop_System SHALL handle blocked users gracefully and continue the broadcast

### Requirement 6: Database Management

**User Story:** As a system administrator, I want proper data persistence for shop operations, so that all purchase data and scheduled tasks are maintained.

#### Acceptance Criteria

1. THE Shop_System SHALL create and maintain a shop_items table with id, name, price, and description fields
2. THE Shop_System SHALL create and maintain a user_purchases table with id, user_id, item_id, purchase_time, expires_at, and data fields
3. THE Shop_System SHALL create and maintain a scheduled_tasks table with id, user_id, message_id, chat_id, task_type, and execute_at fields
4. THE Shop_System SHALL store all purchase records for audit and tracking purposes
5. THE Shop_System SHALL persist scheduled task information to survive bot restarts

### Requirement 7: Bot Owner Management

**User Story:** As a bot owner, I want automatic admin privileges setup, so that I can manage the bot without manual database configuration.

#### Acceptance Criteria

1. WHEN the bot starts, THE Shop_System SHALL check if the OWNER_ID exists as an admin in the database
2. IF the OWNER_ID is not found as an admin, THEN THE Shop_System SHALL automatically add them with is_admin = TRUE
3. THE Shop_System SHALL use the OWNER_ID configuration variable to identify the bot owner
4. THE Shop_System SHALL ensure the bot owner receives admin request notifications

### Requirement 8: Task Scheduling and Persistence

**User Story:** As a system administrator, I want reliable task scheduling that survives bot restarts, so that timed features work consistently.

#### Acceptance Criteria

1. THE Scheduler SHALL use APScheduler with SQLite persistence for all delayed tasks
2. WHEN the bot restarts, THE Scheduler SHALL restore all pending scheduled tasks from the database
3. THE Scheduler SHALL execute scheduled message deletions at the correct time
4. THE Shop_System SHALL clean up completed scheduled tasks from the database
5. THE Scheduler SHALL handle timezone considerations for accurate timing

### Requirement 9: Error Handling and API Limits

**User Story:** As a system administrator, I want robust error handling for Telegram API interactions, so that the bot operates reliably under various conditions.

#### Acceptance Criteria

1. THE Shop_System SHALL respect Telegram API limits of maximum 30 messages per second during broadcasts
2. WHEN a user blocks the bot, THE Shop_System SHALL handle the error gracefully and continue operations
3. THE Shop_System SHALL log failed message deliveries during broadcasts
4. THE Shop_System SHALL provide appropriate error messages to users when operations fail
5. THE Shop_System SHALL maintain operation continuity even when individual message sends fail

### Requirement 10: Integration with Existing Systems

**User Story:** As a developer, I want seamless integration with the existing bot infrastructure, so that the shop system works with current balance and admin systems.

#### Acceptance Criteria

1. THE Shop_System SHALL integrate with the existing user balance system for coin deductions
2. THE Shop_System SHALL use the existing transactions table for purchase logging
3. THE Shop_System SHALL work with the existing admin system and user database
4. THE Shop_System SHALL maintain compatibility with current bot command structure
5. THE Shop_System SHALL use existing database connections and configurations