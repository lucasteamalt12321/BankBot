-- Migration 003: Add parsing_rules_config table
-- Creates the new unified parsing configuration table
-- Date: 2025-01-15

-- Create new parsing_rules_config table
CREATE TABLE IF NOT EXISTS parsing_rules_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_name TEXT UNIQUE NOT NULL,
    parser_class TEXT NOT NULL,
    coefficient REAL DEFAULT 1.0,
    enabled INTEGER DEFAULT 1,
    config TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_parsing_rules_config_game_name ON parsing_rules_config(game_name);
CREATE INDEX IF NOT EXISTS idx_parsing_rules_config_enabled ON parsing_rules_config(enabled);

-- Insert migration record
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (3, '003_add_parsing_rules_config');
