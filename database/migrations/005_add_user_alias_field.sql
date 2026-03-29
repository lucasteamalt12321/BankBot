-- Migration 005: Add alias field to users table
-- Adds a user-defined display alias (2-32 characters) with fallback to Telegram profile name

ALTER TABLE users ADD COLUMN IF NOT EXISTS alias VARCHAR(32) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_users_alias ON users(alias);
