-- Migration 004: Add bridge_state table for Bridge module
-- Tracks last forwarded message IDs to enable state recovery after restart

CREATE TABLE IF NOT EXISTS bridge_state (
    id               INTEGER PRIMARY KEY DEFAULT 1,
    last_tg_msg_id   INTEGER NOT NULL DEFAULT 0,
    last_vk_msg_id   INTEGER NOT NULL DEFAULT 0,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Insert the single row (id=1) if it doesn't exist
INSERT OR IGNORE INTO bridge_state (id, last_tg_msg_id, last_vk_msg_id, updated_at)
VALUES (1, 0, 0, CURRENT_TIMESTAMP);
