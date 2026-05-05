-- Migration 001: Initial Schema
-- Creates the base tables for the message parsing system
-- Date: 2025-01-01

-- User balances (unified bank balance)
CREATE TABLE IF NOT EXISTS user_balances (
    user_id TEXT PRIMARY KEY,
    user_name TEXT UNIQUE NOT NULL,
    bank_balance TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bot balances (per-game tracking)
CREATE TABLE IF NOT EXISTS bot_balances (
    user_id TEXT NOT NULL,
    game TEXT NOT NULL,
    last_balance TEXT NOT NULL,
    current_bot_balance TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, game),
    FOREIGN KEY (user_id) REFERENCES user_balances(user_id) ON DELETE CASCADE
);

-- Processed messages (idempotency)
CREATE TABLE IF NOT EXISTS processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_balances_name ON user_balances(user_name);
CREATE INDEX IF NOT EXISTS idx_bot_balances_game ON bot_balances(game);
CREATE INDEX IF NOT EXISTS idx_processed_messages_timestamp ON processed_messages(processed_at);

-- Migration metadata
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (1, '001_initial_schema');
