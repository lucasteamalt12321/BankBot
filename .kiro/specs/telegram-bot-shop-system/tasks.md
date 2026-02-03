# Implementation Plan: Telegram Bot Shop System

## Overview

This implementation plan breaks down the Telegram bot shop system into discrete coding tasks that build incrementally. The system integrates with the existing Python bot infrastructure and adds shop functionality with three purchasable items: unlimited stickers, admin rights requests, and broadcast messaging.

## Tasks

- [~] 1. Set up database schema and core data models
  - Create database migration script for new tables (shop_items, user_purchases, scheduled_tasks)
  - Define Python data classes for ShopItem, Purchase, ScheduledTask, and result objects
  - Initialize shop_items table with the three default items
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 2. Implement core shop infrastructure
  - [~] 2.1 Create ShopHandler class for displaying shop items
    - Implement shop display formatting with Russian text
    - Add `/shop` command handler to bot
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [~] 2.2 Write property test for shop display completeness
    - **Property 1: Shop Display Completeness**
    - **Validates: Requirements 1.2, 1.3**
  
  - [~] 2.3 Create PurchaseHandler class for processing purchases
    - Implement balance validation and deduction logic
    - Add purchase command handlers (`/buy_1`, `/buy_2`, `/buy_3`)
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [~] 2.4 Write property test for balance validation and deduction
    - **Property 2: Balance Validation and Deduction**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 3. Implement APScheduler integration
  - [~] 3.1 Create SchedulerManager class with SQLite persistence
    - Configure APScheduler with SQLite jobstore
    - Implement task scheduling and restoration methods
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [~] 3.2 Write property test for scheduled task persistence
    - **Property 4: Scheduled Task Persistence**
    - **Validates: Requirements 3.2, 3.4, 3.5, 8.2, 8.3**
  
  - [~] 3.3 Add bot startup task restoration
    - Implement restoration of pending scheduled tasks on bot restart
    - Add cleanup for completed tasks
    - _Requirements: 3.5, 8.4_
  
  - [~] 3.4 Write property test for task cleanup efficiency
    - **Property 14: Task Cleanup Efficiency**
    - **Validates: Requirements 8.4**

- [ ] 4. Implement sticker item processor
  - [~] 4.1 Create StickerItemProcessor class
    - Send confirmation message "Вы получили безлимитные стикеры на 24 часа!"
    - Schedule message deletion after 24 hours
    - Send expiration message "Время действия стикеров истекло!"
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [~] 4.2 Write unit tests for sticker item processor
    - Test confirmation message sending
    - Test expiration message handling
    - _Requirements: 3.1, 3.3_

- [ ] 5. Implement admin request item processor
  - [~] 5.1 Create AdminRequestProcessor class
    - Send formatted message to bot owner with user details
    - Send confirmation to purchaser
    - Handle users without usernames
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [~] 5.2 Write property test for admin request notification
    - **Property 5: Admin Request Notification**
    - **Validates: Requirements 4.1, 4.2**
  
  - [~] 5.3 Implement bot owner auto-admin setup
    - Check and create admin privileges for OWNER_ID on startup
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [~] 5.4 Write property test for owner admin privileges
    - **Property 10: Owner Admin Privileges**
    - **Validates: Requirements 7.2, 7.3**

- [ ] 6. Implement broadcast system with FSM
  - [~] 6.1 Create FSMManager class for conversation states
    - Implement state management for broadcast text collection
    - Handle state transitions and cleanup
    - _Requirements: 5.2_
  
  - [ ] 6.2 Write property test for broadcast state management
    - **Property 6: Broadcast State Management**
    - **Validates: Requirements 5.2, 5.3**
  
  - [ ] 6.3 Create BroadcastEngine class
    - Implement mass messaging with rate limiting (0.1-0.2s delays)
    - Format messages with username/first_name mentions
    - Handle blocked users gracefully
    - _Requirements: 5.3, 5.4, 5.5, 5.7_
  
  - [ ] 6.4 Write property test for message formatting consistency
    - **Property 7: Message Formatting Consistency**
    - **Validates: Requirements 5.4, 5.6**
  
  - [ ] 6.5 Write property test for rate limiting compliance
    - **Property 8: Rate Limiting Compliance**
    - **Validates: Requirements 5.5, 9.1**

- [ ] 7. Implement broadcast item processor
  - [ ] 7.1 Create BroadcastProcessor class
    - Prompt user for broadcast text
    - Integrate with FSM for text collection
    - Trigger broadcast execution and send completion notification
    - _Requirements: 5.1, 5.6_
  
  - [ ] 7.2 Write unit tests for broadcast processor
    - Test prompt message sending
    - Test completion notification format
    - _Requirements: 5.1, 5.6_

- [ ] 8. Integrate item processors with purchase system
  - [ ] 8.1 Wire item processors to purchase handler
    - Connect each processor to corresponding purchase commands
    - Implement purchase execution and logging
    - _Requirements: 2.4, 2.5_
  
  - [ ] 8.2 Write property test for purchase execution and logging
    - **Property 3: Purchase Execution and Logging**
    - **Validates: Requirements 2.4, 2.5**
  
  - [ ] 8.3 Add comprehensive error handling
    - Implement error handling for all shop operations
    - Add appropriate user-facing error messages
    - _Requirements: 9.2, 9.3, 9.4, 9.5_
  
  - [ ] 8.4 Write property test for error handling resilience
    - **Property 9: Error Handling Resilience**
    - **Validates: Requirements 5.7, 9.2, 9.3, 9.4, 9.5**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Final integration and system compatibility
  - [ ] 10.1 Integrate with existing bot infrastructure
    - Connect to existing balance system, database, and admin functionality
    - Ensure command compatibility with existing bot commands
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [ ] 10.2 Write property test for system integration compatibility
    - **Property 12: System Integration Compatibility**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
  
  - [ ] 10.3 Add database schema validation
    - Verify all required tables exist with correct structure
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [ ] 10.4 Write property test for database schema integrity
    - **Property 11: Database Schema Integrity**
    - **Validates: Requirements 6.1, 6.2, 6.3**

- [ ] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation and testing
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- The implementation uses Python and integrates with existing pyTelegramBotAPI infrastructure
- APScheduler with SQLite persistence ensures reliable task scheduling
- Rate limiting and error handling ensure robust Telegram API integration