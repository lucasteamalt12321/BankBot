-- Phase 2 Tables Migration for Supabase PostgreSQL
-- Date: 2026-05-24
-- Revision: 009

-- ========== Geometry Dash Module ==========

-- Table: levels
CREATE TABLE IF NOT EXISTS levels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    position INTEGER NOT NULL UNIQUE,
    external_link TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_levels_position ON levels(position);

-- Table: submissions
CREATE TABLE IF NOT EXISTS submissions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    level_id INTEGER REFERENCES levels(id) ON DELETE CASCADE,
    video_file_id TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by BIGINT,
    CONSTRAINT check_submission_status CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS ix_submissions_user_id ON submissions(user_id);
CREATE INDEX IF NOT EXISTS ix_submissions_status ON submissions(status);
CREATE INDEX IF NOT EXISTS ix_submissions_level_id ON submissions(level_id);

-- Table: player_stats
CREATE TABLE IF NOT EXISTS player_stats (
    user_id BIGINT PRIMARY KEY,
    hardest_level_id INTEGER REFERENCES levels(id) ON DELETE SET NULL,
    total_approved INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_player_stats_hardest_level ON player_stats(hardest_level_id);

-- Table: level_completions
CREATE TABLE IF NOT EXISTS level_completions (
    user_id BIGINT NOT NULL,
    level_id INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, level_id)
);

CREATE INDEX IF NOT EXISTS ix_level_completions_level_id ON level_completions(level_id);

-- ========== Chess Module ==========

-- Table: chess_accounts
CREATE TABLE IF NOT EXISTS chess_accounts (
    user_id BIGINT PRIMARY KEY,
    lichess_username VARCHAR(50) NOT NULL UNIQUE,
    linked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chess_accounts_lichess_username ON chess_accounts(lichess_username);

-- Table: user_coins
CREATE TABLE IF NOT EXISTS user_coins (
    user_id BIGINT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    last_puzzle_at TIMESTAMPTZ
);

-- ========== Universe Module ==========

-- Table: infection_status
CREATE TABLE IF NOT EXISTS infection_status (
    user_id BIGINT PRIMARY KEY,
    virus_type VARCHAR(50),
    infected_at TIMESTAMPTZ,
    tea_cooldown_until TIMESTAMPTZ
);

-- Table: daily_prayer_log
CREATE TABLE IF NOT EXISTS daily_prayer_log (
    user_id BIGINT NOT NULL,
    prayer_date DATE NOT NULL,
    PRIMARY KEY (user_id, prayer_date)
);

CREATE INDEX IF NOT EXISTS ix_daily_prayer_log_date ON daily_prayer_log(prayer_date);

-- ========== AI Module ==========

-- Table: user_preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT PRIMARY KEY,
    preferred_ai_model VARCHAR(50),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Phase 2 tables created successfully!';
END $$;
