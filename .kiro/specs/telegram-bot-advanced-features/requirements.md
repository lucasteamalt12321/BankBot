# Requirements Document

## Introduction

This document specifies advanced features for an existing Telegram bot system, including an enhanced shop system with sticker management, message parsing from other bots with currency conversion, and expanded admin functions. These features extend the current telegram-bot-admin-system with sophisticated commerce, monitoring, and administrative capabilities.

## Glossary

- **Bot_System**: The Telegram bot application that processes commands and manages user interactions
- **Shop_Module**: The commerce subsystem that handles item purchases and inventory
- **Parser_Module**: The message monitoring subsystem that extracts currency data from other bots
- **Admin_Module**: The administrative subsystem that provides management commands
- **Sticker_Manager**: The component that manages sticker access permissions and expiration
- **Broadcast_System**: The component that sends messages to multiple users
- **Currency_Converter**: The component that applies conversion rates to parsed amounts
- **Transaction_Logger**: The component that records parsed transaction data

## Requirements

### Requirement 1: Shop System with Balance Validation

**User Story:** As a user, I want to purchase items from the bot shop using my balance, so that I can access premium features and services.

#### Acceptance Criteria

1. WHEN a user executes /buy [item_number] command, THE Bot_System SHALL validate the user has sufficient balance for the requested item
2. WHEN a user has insufficient balance for an item, THE Bot_System SHALL return an error message and prevent the purchase
3. WHEN a purchase is successful, THE Bot_System SHALL deduct the item price from the user's balance
4. WHEN a purchase is successful, THE Bot_System SHALL activate the purchased item's functionality for the user
5. THE Shop_Module SHALL support at least three distinct item types with different behaviors

### Requirement 2: Sticker Access Management

**User Story:** As a user who purchased stickers, I want unlimited sticker access for 24 hours, so that I can use stickers freely during my access period.

#### Acceptance Criteria

1. WHEN a user purchases item 1 (stickers), THE Sticker_Manager SHALL set sticker_unlimited flag to True
2. WHEN sticker access is granted, THE Sticker_Manager SHALL set sticker_unlimited_until to current time plus 24 hours
3. WHILE sticker_unlimited is True and current time is before sticker_unlimited_until, THE Bot_System SHALL allow unlimited sticker usage
4. WHEN sticker_unlimited_until expires, THE Sticker_Manager SHALL automatically set sticker_unlimited to False
5. WHEN sticker_unlimited is False, THE Bot_System SHALL auto-delete user stickers after 2 minutes

### Requirement 3: Admin Notification System

**User Story:** As an admin, I want to be notified when users purchase admin-related items, so that I can provide appropriate support or services.

#### Acceptance Criteria

1. WHEN a user purchases item 2 (admin), THE Bot_System SHALL send a notification message to all administrators
2. THE notification message SHALL include the purchaser's username, user ID, and timestamp
3. THE Admin_Module SHALL maintain a list of administrator user IDs for notification targeting
4. WHEN the notification is sent, THE Bot_System SHALL confirm successful delivery to the purchaser

### Requirement 4: Mention All Broadcast System

**User Story:** As a user who purchased mention all access, I want to send messages to all bot users, so that I can communicate with the entire community.

#### Acceptance Criteria

1. WHEN a user purchases item 3 (mention all), THE Bot_System SHALL prompt the user to provide broadcast message text
2. WHEN broadcast text is provided, THE Broadcast_System SHALL send the message to all registered users with @mention tags
3. THE Broadcast_System SHALL use async methods to handle large user lists without blocking
4. WHEN the broadcast is complete, THE Bot_System SHALL report the number of users successfully messaged
5. THE Broadcast_System SHALL handle failed message deliveries gracefully and continue processing

### Requirement 5: Message Parsing from External Bots

**User Story:** As a system administrator, I want the bot to parse currency messages from other bots, so that I can track user earnings from external sources.

#### Acceptance Criteria

1. THE Parser_Module SHALL monitor group messages for patterns from configured external bots
2. WHEN a message from Shmalala bot contains "Монеты: +[number]" pattern, THE Parser_Module SHALL extract the number value
3. WHEN a message from GDcards bot contains "Очки: +[number]" pattern, THE Parser_Module SHALL extract the number value
4. THE Parser_Module SHALL use regex patterns for reliable message parsing
5. THE Parser_Module SHALL support adding new bot parsing rules through configuration

### Requirement 6: Currency Conversion and Transaction Logging

**User Story:** As a system administrator, I want parsed currency amounts to be converted and logged, so that I can maintain accurate user balance records.

#### Acceptance Criteria

1. WHEN currency is parsed from external bot messages, THE Currency_Converter SHALL apply configured multiplier rates
2. THE Transaction_Logger SHALL record all parsed transactions with timestamp, source bot, original amount, converted amount, and target user
3. THE Bot_System SHALL update user balances based on converted currency amounts
4. THE Transaction_Logger SHALL store transaction data in parsed_transactions table
5. THE Parser_Module SHALL handle parsing errors gracefully and log failed parsing attempts

### Requirement 7: Parsing Statistics and Reporting

**User Story:** As an administrator, I want to view parsing statistics, so that I can monitor the effectiveness of the currency parsing system.

#### Acceptance Criteria

1. WHEN an admin executes /parsing_stats command, THE Bot_System SHALL display total transactions parsed by source bot
2. THE statistics SHALL include total amount converted, number of successful parses, and number of failed parses
3. THE statistics SHALL show data for the last 24 hours, 7 days, and 30 days
4. THE Bot_System SHALL restrict /parsing_stats command to administrator users only
5. THE statistics display SHALL be formatted clearly with currency amounts and percentages

### Requirement 8: Administrative Broadcast System

**User Story:** As an administrator, I want to broadcast messages to all users, so that I can communicate important announcements and updates.

#### Acceptance Criteria

1. WHEN an admin executes /broadcast [text] command, THE Broadcast_System SHALL send the message to all registered users
2. THE Bot_System SHALL verify the user has administrator privileges before processing broadcast commands
3. THE Broadcast_System SHALL use async methods to handle message delivery to large user bases
4. WHEN broadcast is complete, THE Bot_System SHALL report delivery statistics to the administrator
5. THE Broadcast_System SHALL handle message delivery failures and provide error reporting

### Requirement 9: Dynamic Shop Management

**User Story:** As an administrator, I want to add new shop items dynamically, so that I can expand the shop without code changes.

#### Acceptance Criteria

1. WHEN an admin executes /add_item [name] [price] [type] command, THE Shop_Module SHALL create a new purchasable item
2. THE Shop_Module SHALL validate that item names are unique within the shop
3. THE Shop_Module SHALL support item types: sticker, admin, mention_all, and custom
4. THE new item SHALL be immediately available for purchase through /buy command
5. THE Bot_System SHALL restrict /add_item command to administrator users only

### Requirement 10: User Statistics Display

**User Story:** As an administrator, I want to view detailed user statistics, so that I can monitor user activity and engagement.

#### Acceptance Criteria

1. WHEN an admin executes /user_stats @username command, THE Bot_System SHALL display comprehensive user information
2. THE statistics SHALL include current balance, total purchases, active subscriptions, and last activity timestamp
3. THE statistics SHALL show parsing transaction history for the specified user
4. THE Bot_System SHALL handle cases where the specified username does not exist
5. THE Bot_System SHALL restrict /user_stats command to administrator users only

### Requirement 11: Configuration Management System

**User Story:** As a system administrator, I want to configure parsing rules and system settings through files, so that I can modify behavior without code changes.

#### Acceptance Criteria

1. THE Bot_System SHALL load parsing rules from a parsing_rules configuration table
2. THE configuration SHALL support regex patterns, multiplier rates, and bot identification
3. WHEN configuration files are updated, THE Bot_System SHALL reload settings without restart
4. THE Bot_System SHALL validate configuration syntax and report errors clearly
5. THE Bot_System SHALL provide default configuration values for all required settings

### Requirement 12: Background Task Management

**User Story:** As a system administrator, I want automated cleanup of expired features, so that the system maintains accurate state without manual intervention.

#### Acceptance Criteria

1. THE Bot_System SHALL run background tasks to check for expired sticker access every 5 minutes
2. WHEN sticker access expires, THE background task SHALL update user permissions automatically
3. THE background task SHALL clean up expired sticker files from storage
4. THE Bot_System SHALL log all background task activities for monitoring
5. THE background task system SHALL handle errors gracefully and continue operation