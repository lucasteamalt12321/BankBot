"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta

import requests
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text


def _web_user_id(raw: str | None) -> int:
    if not raw:
        return 0
    h = hashlib.sha256(str(raw).encode()).hexdigest()[:12]
    return int(h, 16) % 2000000000

app = Flask(__name__)

# CORS for VK Mini App
try:
    from flask_cors import CORS
    CORS(app, resources={r"/api/budget/*": {"origins": ["https://vk.com", "https://*.vk.com"]}})
except ImportError:
    pass

# Webhook secret
_raw_webhook_secret = os.getenv("WEBHOOK_SECRET") or ""
WEBHOOK_SECRET = _raw_webhook_secret if _raw_webhook_secret else "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266"
print(f"[STARTUP] WEBHOOK_SECRET length: {len(WEBHOOK_SECRET)}, first 10 chars: {WEBHOOK_SECRET[:10]}")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_RESPONSE_MODE = "short"
CHAT_RESPONSE_MODES: dict[int, str] = {}
DB_ENGINE = None

# Bot identity for reply/mention detection
BOT_ID: int | None = None
BOT_USERNAME: str = "lt_lo_game_bot"

# Character system (replaces /chat)
CHARACTER_PROMPTS: dict[str, str] = {
    "нейтральный": (
        "Ты помощник. Отвечай кратко и по делу, без лишних символов и Role play. "
        "Пользователь сказал: {text}"
    ),
    "олеговирус": (
        "Ты — олеговирус, существо, которое постоянно издаёт звуки 'кхм-кхм', "
        "любит придираться к чужим текстам. Ответь кратко (1-2 предложения). "
        "Пользователь сказал: {text}"
    ),
    "чай": (
        "Ты — верховный божественный Чай, воплощение покоя и мудрости. "
        "Говори вдохновляюще, используй слова 'настой', 'eight-nine'. "
        "Ответь кратко (1-2 предложения). Пользователь сказал: {text}"
    ),
}
CHARACTER_EMOJI: dict[str, str] = {"нейтральный": "", "олеговирус": "🦠", "чай": "☕"}
DEFAULT_CHARACTER = "нейтральный"
_user_character_cache: dict[int, str] = {}
_global_character: str = DEFAULT_CHARACTER
ADMIN_TELEGRAM_ID = 2091908459
# Conversation memory for AI context
_CHAT_MEMORY: dict[int, list[dict]] = {}  # per-user: last 10 personal messages
_CHAT_MEMORY_LIMIT = 10
_CHAT_GLOBAL: list[dict] = []  # global chat: last 50 messages across all users
_CHAT_GLOBAL_LIMIT = 50
_GD_SUBMIT_STATE: dict[int, dict] = {}
_GD_MODERATE_STATE: dict[int, int] = {}
_GD_APPROVE_STATE: dict[int, dict] = {}  # user_id -> {sub_id, level_name, username}
# Error logging system
_ERROR_LOG: list[dict] = []
_ERROR_LOG_LIMIT = 50
_PENDING_PUZZLES: dict[int, dict] = {}  # user_id -> {puzzle_id, solution, rating, themes, chat_id}
_ADDE_COOLDOWN: dict[int, float] = {}  # user_id -> timestamp
_ADDE_LOG: list[dict] = []  # recent /addexpense callers for debugging



def normalize_database_url(url: str) -> str:
    """Normalize DB URL aliases accepted by cloud providers."""

    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def get_db_engine():
    """Get SQLAlchemy engine for DATABASE_URL/Supabase or local SQLite."""

    global DB_ENGINE
    if DB_ENGINE is None:
        database_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("SUPABASE_DB_URL")
            or "sqlite:///data/bot.db"
        )
        DB_ENGINE = create_engine(
            normalize_database_url(database_url),
            pool_size=2,
            max_overflow=1,
            pool_pre_ping=True,
            pool_recycle=60,
            pool_timeout=5,
            connect_args={"connect_timeout": 10},
        )
    _ensure_gd_tables(DB_ENGINE)
    _ensure_budget_tables(DB_ENGINE)
    _ensure_universe_tables(DB_ENGINE)
    _ensure_dnd_tables(DB_ENGINE)
    _ensure_verb_tables(DB_ENGINE)
    return DB_ENGINE


def _ensure_gd_tables(engine):
    """Create GD module tables if they don't exist (preserves existing data)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS levels (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    difficulty TEXT DEFAULT 'Unknown'
                )
            """))
            conn.execute(text("ALTER TABLE levels ADD COLUMN IF NOT EXISTS difficulty TEXT DEFAULT 'Unknown'"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    level_name TEXT NOT NULL,
                    media_file_id TEXT,
                    media_type TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by BIGINT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    user_id BIGINT PRIMARY KEY,
                    total_approved INTEGER DEFAULT 0,
                    total_rejected INTEGER DEFAULT 0,
                    hardest_level_id INTEGER,
                    last_submission TIMESTAMP
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS level_completions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    level_id INTEGER NOT NULL REFERENCES levels(id),
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, level_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS game_states (
                    user_id BIGINT NOT NULL,
                    game_name TEXT NOT NULL,
                    metric TEXT NOT NULL DEFAULT '',
                    value REAL NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, game_name, metric)
                )
            """))
            conn.commit()
        print("[GD] Tables ensured successfully")
    except Exception as exc:
        print(f"[GD] Table init error: {exc}")
    _ensure_user_preferences_table(engine)


def get_user_balance(user_id: int) -> tuple[int, bool]:
    """Get user balance and admin status from database."""
    try:
        with get_db_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT balance, is_admin FROM users WHERE telegram_id = :user_id"
                    ),
                    {"user_id": user_id},
                )
                .mappings()
                .first()
            )
            if row:
                return int(row["balance"] or 0), bool(row["is_admin"])
            return 0, False
    except Exception as exc:
        print(f"Error getting user balance: {exc}")
        return 0, False


def get_user_db_profile(user_id: int) -> dict | None:
    """Get user profile row from database."""

    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, balance, is_admin, first_name, username, total_earned
                    FROM users
                    WHERE telegram_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
            return dict(row.mappings().first() or {}) or None
    except Exception as exc:
        print(f"Error getting user profile: {exc}")
        return None


def get_user_stats(user_id: int) -> dict:
    """Get user stats from database."""
    try:
        with get_db_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                SELECT 
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as earned,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) as spent,
                    COUNT(*) as total_transactions,
                    (SELECT COUNT(*) FROM user_purchases WHERE user_id = (
                        SELECT id FROM users WHERE telegram_id = :user_id
                    )) as purchases
                FROM transactions
                WHERE user_id = (SELECT id FROM users WHERE telegram_id = :user_id)
                """
                    ),
                    {"user_id": user_id},
                )
                .mappings()
                .first()
            )
            if row:
                return {
                    "earned": int(row["earned"] or 0),
                    "spent": int(row["spent"] or 0),
                    "total_transactions": int(row["total_transactions"] or 0),
                    "purchases": int(row["purchases"] or 0),
                }
            return {"earned": 0, "spent": 0, "total_transactions": 0, "purchases": 0}
    except Exception as exc:
        print(f"Error getting user stats: {exc}")
        return {"earned": 0, "spent": 0, "total_transactions": 0, "purchases": 0}


def _ensure_user_preferences_table(engine):
    """Create user_preferences table if it doesn't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    preferred_character VARCHAR(20) DEFAULT 'чай',
                    preferred_ai_model VARCHAR(50),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        print("[INIT] user_preferences table ensured")
    except Exception as exc:
        print(f"[INIT] user_preferences table error: {exc}")


def _ensure_chess_games_table(engine):
    """Create chess_games table if it doesn't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chess_games (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    lichess_username VARCHAR(50) NOT NULL,
                    puzzle_id VARCHAR(50) NOT NULL,
                    puzzle_rating INTEGER,
                    puzzle_themes TEXT,
                    solved BOOLEAN DEFAULT FALSE,
                    solved_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chess_games_user_id ON chess_games(user_id)"))
            conn.commit()
        print("[INIT] chess_games table ensured")
    except Exception as exc:
        print(f"[INIT] chess_games table error: {exc}")


def _ensure_budget_tables(engine):
    """Create Family Budget tables if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS families (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    invite_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_families_invite_code ON families(invite_code)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_families_admin_id ON families(admin_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS family_members (
                    id SERIAL PRIMARY KEY,
                    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_family_members_family_id ON family_members(family_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_family_members_user_id ON family_members(user_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS budget_transactions (
                    id SERIAL PRIMARY KEY,
                    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
                    payer_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_budget_transactions_family_id ON budget_transactions(family_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transaction_details (
                    id SERIAL PRIMARY KEY,
                    transaction_id INTEGER NOT NULL REFERENCES budget_transactions(id) ON DELETE CASCADE,
                    for_whom_id TEXT NOT NULL,
                    share INTEGER NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transaction_details_txn_id ON transaction_details(transaction_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS debts (
                    id SERIAL PRIMARY KEY,
                    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
                    debtor_id TEXT NOT NULL,
                    creditor_id TEXT NOT NULL,
                    amount_left INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_debts_family_id ON debts(family_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_debts_debtor_id ON debts(debtor_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_debts_creditor_id ON debts(creditor_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
                    debtor_id TEXT NOT NULL,
                    creditor_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_family_id ON payments(family_id)"))
            conn.commit()
        print("[BUDGET] Tables ensured successfully")
    except Exception as exc:
        print(f"[BUDGET] Table init error: {exc}")


def _ensure_universe_tables(engine):
    """Create Universe Module tables if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS infection_status (
                    user_id BIGINT PRIMARY KEY,
                    virus_type VARCHAR(50),
                    infected_at TIMESTAMPTZ,
                    tea_cooldown_until TIMESTAMPTZ
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS daily_prayer_log (
                    user_id BIGINT NOT NULL,
                    prayer_date DATE NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_prayer_log_date ON daily_prayer_log(prayer_date)"))
            conn.commit()
        print("[UNIVERSE] Tables ensured successfully")
    except Exception as exc:
        print(f"[UNIVERSE] Table init error: {exc}")


def _ensure_dnd_tables(engine):
    """Create D&D AI Master tables/columns if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dnd_sessions (
                    id SERIAL PRIMARY KEY,
                    master_id BIGINT NOT NULL,
                    name VARCHAR(100),
                    description TEXT,
                    max_players INTEGER DEFAULT 6,
                    current_players INTEGER DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'planning',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    paused_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    book_content TEXT,
                    current_scene TEXT,
                    context_summary TEXT,
                    ai_system_prompt TEXT,
                    last_ai_response TEXT,
                    chapter_breakdown TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dnd_characters (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                    player_id BIGINT NOT NULL,
                    name VARCHAR(100),
                    race VARCHAR(50),
                    character_class VARCHAR(50),
                    level INTEGER DEFAULT 1,
                    background TEXT,
                    alignment VARCHAR(20),
                    stats TEXT DEFAULT '{}',
                    hit_points INTEGER DEFAULT 10,
                    max_hit_points INTEGER DEFAULT 10,
                    armor_class INTEGER DEFAULT 10,
                    inventory TEXT,
                    spells TEXT,
                    notes TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_active_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dnd_session_logs (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                    player_id BIGINT,
                    character_id INTEGER REFERENCES dnd_characters(id) ON DELETE SET NULL,
                    message_type VARCHAR(20),
                    content TEXT,
                    ai_context TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dnd_session_logs_session ON dnd_session_logs(session_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS dnd_fixes (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                    player_id BIGINT NOT NULL,
                    character_id INTEGER REFERENCES dnd_characters(id) ON DELETE SET NULL,
                    original_context TEXT,
                    correction TEXT,
                    applied BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dnd_fixes_session ON dnd_fixes(session_id)"))
            conn.commit()
        print("[DND] Tables ensured successfully")
    except Exception as exc:
        print(f"[DND] Table init error: {exc}")

def _ensure_verb_tables(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS verb_exercises (
                    id INTEGER PRIMARY KEY,
                    teacher_id INTEGER NOT NULL,
                    verbs TEXT NOT NULL,
                    task_count INTEGER NOT NULL DEFAULT 10,
                    mode INTEGER NOT NULL DEFAULT 3,
                    wishes TEXT DEFAULT '',
                    tasks TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS verb_submissions (
                    id SERIAL PRIMARY KEY,
                    exercise_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    details TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_verb_submissions_exercise ON verb_submissions(exercise_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_verb_exercises_teacher ON verb_exercises(teacher_id)"))
            conn.commit()
        print("[VERBS] Tables ensured")
    except Exception as exc:
        print(f"[VERBS] Table init error: {exc}")


def _save_verb_exercise(ex: dict):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO verb_exercises (id, teacher_id, verbs, task_count, mode, wishes, tasks, created_at) "
            "VALUES (:id, :teacher_id, :verbs, :task_count, :mode, :wishes, :tasks, :created_at)"
        ), {
            "id": ex["id"],
            "teacher_id": ex["teacher_id"],
            "verbs": ex["verbs"],
            "task_count": ex["task_count"],
            "mode": ex.get("mode", 3),
            "wishes": ex.get("wishes", ""),
            "tasks": json.dumps(ex["tasks"], ensure_ascii=False),
            "created_at": time.time(),
        })
        conn.commit()


def _load_verb_exercise(ex_id: int) -> dict | None:
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT * FROM verb_exercises WHERE id = :id"
        ), {"id": ex_id}).fetchone()
    if not row:
        return None
    d = dict(row._mapping)
    d["tasks"] = json.loads(d["tasks"])
    return d


def _load_teacher_exercises(teacher_id: int) -> list[dict]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT e.id, e.task_count, e.mode, e.created_at, "
            "(SELECT COUNT(DISTINCT s.user_id) FROM verb_submissions s WHERE s.exercise_id = e.id) AS student_count "
            "FROM verb_exercises e WHERE e.teacher_id = :tid ORDER BY e.created_at DESC"
        ), {"tid": teacher_id}).fetchall()
    return [dict(r._mapping) for r in rows]


def _save_verb_submission(ex_id: int, sub: dict):
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO verb_submissions (exercise_id, user_id, name, score, total, details, timestamp) "
            "VALUES (:ex_id, :user_id, :name, :score, :total, :details, :ts)"
        ), {
            "ex_id": ex_id,
            "user_id": sub["user_id"],
            "name": sub["name"],
            "score": sub["score"],
            "total": sub["total"],
            "details": json.dumps(sub["details"], ensure_ascii=False),
            "ts": sub["timestamp"],
        })
        conn.commit()


def _load_verb_submissions(ex_id: int) -> list[dict]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT * FROM verb_submissions WHERE exercise_id = :ex_id ORDER BY timestamp"
        ), {"ex_id": ex_id}).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        d["details"] = json.loads(d["details"])
        result.append(d)
    return result


def _load_bot_id() -> int | None:
    """Load bot's Telegram user_id via getMe API call."""
    global BOT_ID
    if BOT_ID is not None:
        return BOT_ID
    if not BOT_TOKEN:
        return None
    try:
        resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
        if resp.ok:
            data = resp.json()
            BOT_ID = data["result"]["id"]
            print(f"[STARTUP] BOT_ID loaded: {BOT_ID}")
            return BOT_ID
    except Exception as exc:
        print(f"[STARTUP] Failed to load BOT_ID: {exc}")
    return None


def get_user_character(user_id: int) -> str:
    """Get user's preferred character from cache first, then DB."""
    if user_id in _user_character_cache:
        return _user_character_cache[user_id]
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT preferred_character FROM user_preferences WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            if row and row["preferred_character"]:
                char = row["preferred_character"].lower()
                if char in CHARACTER_PROMPTS:
                    _user_character_cache[user_id] = char
                    return char
    except Exception:
        pass  # Table may not exist, that's fine
    return DEFAULT_CHARACTER


def set_user_character(user_id: int, character: str) -> bool:
    """Set user's preferred character. Updates cache always, DB if possible."""
    character = character.lower()
    if character not in CHARACTER_PROMPTS:
        return False
    # Always update in-memory cache
    _user_character_cache[user_id] = character
    # Try DB write (table may not exist yet)
    try:
        with get_db_engine().connect() as conn:
            conn.execute(text("""
                INSERT INTO user_preferences (user_id, preferred_character, updated_at)
                VALUES (:user_id, :character, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET preferred_character = :character, updated_at = CURRENT_TIMESTAMP
            """), {"user_id": user_id, "character": character})
            conn.commit()
        print(f"[CHARACTER] User {user_id} set character to {character} (DB+cache)")
    except Exception as exc:
        print(f"[CHARACTER] User {user_id} set character to {character} (cache only, DB error: {exc})")
    return True


def get_global_character() -> str:
    """Get global default character."""
    return _global_character


def set_global_character(character: str) -> bool:
    """Set global default character."""
    global _global_character
    character = character.lower()
    if character not in CHARACTER_PROMPTS:
        return False
    _global_character = character
    return True


def build_character_prompt(character: str, user_text: str) -> str:
    """Build AI prompt for a character."""
    template = CHARACTER_PROMPTS.get(character, CHARACTER_PROMPTS[DEFAULT_CHARACTER])
    return template.format(text=user_text)


def add_chat_memory(user_id: int, role: str, text: str) -> None:
    """Add a message to user's conversation memory and global chat history."""
    global _CHAT_GLOBAL
    # Per-user memory
    if user_id not in _CHAT_MEMORY:
        _CHAT_MEMORY[user_id] = []
    _CHAT_MEMORY[user_id].append({"role": role, "content": text})
    if len(_CHAT_MEMORY[user_id]) > _CHAT_MEMORY_LIMIT:
        _CHAT_MEMORY[user_id] = _CHAT_MEMORY[user_id][-_CHAT_MEMORY_LIMIT:]
    # Global chat memory
    _CHAT_GLOBAL.append({"role": role, "content": text, "user_id": user_id})
    if len(_CHAT_GLOBAL) > _CHAT_GLOBAL_LIMIT:
        _CHAT_GLOBAL = _CHAT_GLOBAL[-_CHAT_GLOBAL_LIMIT:]


def get_chat_memory(user_id: int) -> list[dict]:
    """Get user's personal conversation memory (last 10 messages)."""
    return _CHAT_MEMORY.get(user_id, [])


def get_global_chat_memory() -> list[dict]:
    """Get global chat history (last 50 messages, without user_id field)."""
    return [{"role": m["role"], "content": m["content"]} for m in _CHAT_GLOBAL]


def call_ai_with_memory(user_id: int, prompt: str, max_tokens: int = 150) -> str:
    """Call AI with conversation context (personal + global chat)."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return "❌ AI недоступен (нет GROQ_API_KEY)"

    # Build messages with memory
    messages = []
    
    # Add global chat context (last 50 messages from all users)
    global_memory = get_global_chat_memory()
    if global_memory:
        messages.extend(global_memory)
    
    # Add personal conversation memory (last 10 messages)
    personal_memory = get_chat_memory(user_id)
    if personal_memory:
        messages.extend(personal_memory)
    
    # Add current message
    messages.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.8,
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            # Save to memory
            add_chat_memory(user_id, "user", prompt)
            add_chat_memory(user_id, "assistant", answer)
            return answer
        else:
            error_detail = response.text[:200] if response.text else "No details"
            print(f"AI API error {response.status_code}: {error_detail}")
            return f"❌ Ошибка AI: {response.status_code}"
    except Exception as exc:
        print(f"Error calling AI API: {exc}")
        return f"❌ Ошибка AI: {str(exc)}"


def detect_bot_reply(message: dict) -> bool:
    """Check if message is a reply to the bot itself."""
    reply_to = message.get("reply_to_message")
    if not reply_to:
        return False
    sender = reply_to.get("from", {})
    if sender.get("id") == BOT_ID:
        return True
    if sender.get("is_bot") and BOT_ID and sender.get("id") == BOT_ID:
        return True
    return False


def detect_bot_mention(text: str | None, entities: list | None) -> tuple[bool, str]:
    """Check if message mentions the bot. Returns (is_mention, cleaned_text)."""
    if not text:
        return False, ""
    # Check entities for @mention
    if entities:
        for ent in entities:
            if ent.get("type") == "mention":
                offset = ent.get("offset", 0)
                length = ent.get("length", 0)
                mention = text[offset:offset + length]
                if mention.lower() == f"@{BOT_USERNAME}".lower():
                    # Remove the mention from text
                    cleaned = (text[:offset] + text[offset + length:]).strip()
                    return True, cleaned
    # Check text_mention entities (user without username)
    if entities:
        for ent in entities:
            if ent.get("type") == "text_mention":
                user = ent.get("user", {})
                if user.get("id") == BOT_ID:
                    offset = ent.get("offset", 0)
                    length = ent.get("length", 0)
                    cleaned = (text[:offset] + text[offset + length:]).strip()
                    return True, cleaned
    # Simple text check for @username
    mention_pattern = f"@{BOT_USERNAME}"
    if mention_pattern.lower() in text.lower():
        cleaned = re.sub(re.escape(mention_pattern), "", text, flags=re.IGNORECASE).strip()
        return True, cleaned
    return False, text


def get_shop_items(limit: int = 20) -> list[dict]:
    """Get active shop items."""
    try:
        with get_db_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT id, name, description, price, item_type
                    FROM shop_items
                    WHERE is_active = true
                    ORDER BY price ASC
                    LIMIT :limit
                    """
                    ),
                    {"limit": limit},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "id": row["id"],
                    "name": row["name"] or "—",
                    "description": row["description"] or "—",
                    "price": int(row["price"] or 0),
                    "item_type": row["item_type"] or "—",
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"Error getting shop items: {exc}")
        return []


def get_user_inventory(user_id: int) -> list[dict]:
    """Get user's purchased items."""
    try:
        with get_db_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT si.name, up.purchased_at, up.is_active
                    FROM user_purchases up
                    JOIN shop_items si ON up.item_id = si.id
                    WHERE up.user_id = (SELECT id FROM users WHERE telegram_id = :user_id)
                    ORDER BY up.purchased_at DESC
                    LIMIT 20
                    """
                    ),
                    {"user_id": user_id},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "name": row["name"] or "—",
                    "purchased_at": row["purchased_at"],
                    "is_active": bool(row["is_active"]),
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"Error getting user inventory: {exc}")
        return []


def purchase_item(user_id: int, item_id: int) -> tuple[bool, str]:
    """Purchase item for user."""
    try:
        with get_db_engine().connect() as conn:
            # Get item price
            item_row = (
                conn.execute(
                    text(
                        "SELECT price, name FROM shop_items WHERE id = :item_id AND is_active = true"
                    ),
                    {"item_id": item_id},
                )
                .mappings()
                .first()
            )

            if not item_row:
                return False, "❌ Товар не найден"

            price = int(item_row["price"])
            item_name = item_row["name"]

            # Get user balance
            user_row = (
                conn.execute(
                    text("SELECT id, balance FROM users WHERE telegram_id = :user_id"),
                    {"user_id": user_id},
                )
                .mappings()
                .first()
            )

            if not user_row:
                return False, "❌ Пользователь не найден"

            internal_user_id = user_row["id"]
            balance = int(user_row["balance"])

            if balance < price:
                return False, f"❌ Недостаточно средств (нужно {price}, есть {balance})"

            # Deduct balance
            conn.execute(
                text(
                    "UPDATE users SET balance = balance - :price WHERE telegram_id = :user_id"
                ),
                {"price": price, "user_id": user_id},
            )

            # Create purchase record
            conn.execute(
                text(
                    """
                    INSERT INTO user_purchases (user_id, item_id, purchase_price, purchased_at, is_active)
                    VALUES (:user_id, :item_id, :price, NOW(), true)
                    """
                ),
                {"user_id": internal_user_id, "item_id": item_id, "price": price},
            )

            # Create transaction
            conn.execute(
                text(
                    """
                    INSERT INTO transactions (user_id, amount, transaction_type, description, created_at)
                    VALUES (:user_id, :amount, 'purchase', :description, NOW())
                    """
                ),
                {
                    "user_id": internal_user_id,
                    "amount": -price,
                    "description": f"Покупка: {item_name}",
                },
            )

            conn.commit()
            return True, f"✅ Куплено: {item_name} за {price} очков"
    except Exception as exc:
        print(f"Error purchasing item: {exc}")
        return False, f"❌ Ошибка покупки: {str(exc)}"


def call_ai_api(prompt: str, max_tokens: int = 150, temperature: float = 0.8) -> str:
    """Call Groq AI API with prompt."""
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            return "❌ AI недоступен (нет GROQ_API_KEY)"

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",  # Updated model name
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=10.0,
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            error_detail = response.text[:200] if response.text else "No details"
            print(f"AI API error {response.status_code}: {error_detail}")
            return f"❌ Ошибка AI: {response.status_code}"
    except Exception as exc:
        print(f"Error calling AI API: {exc}")
        return f"❌ Ошибка AI: {str(exc)}"


def check_admin(user_id: int) -> bool:
    """Check if user is admin."""
    try:
        with get_db_engine().connect() as conn:
            row = (
                conn.execute(
                    text("SELECT is_admin FROM users WHERE telegram_id = :user_id"),
                    {"user_id": user_id},
                )
                .mappings()
                .first()
            )
            return bool(row["is_admin"]) if row else False
    except Exception as exc:
        print(f"Error checking admin status: {exc}")
        return False


def add_user_balance(user_id: int, amount: int, description: str = "") -> bool:
    """Add balance to user and create transaction."""
    try:
        with get_db_engine().connect() as conn:
            # Get user internal id
            user_row = (
                conn.execute(
                    text("SELECT id FROM users WHERE telegram_id = :user_id"),
                    {"user_id": user_id},
                )
                .mappings()
                .first()
            )

            if not user_row:
                return False

            internal_user_id = user_row["id"]

            # Update balance
            conn.execute(
                text(
                    "UPDATE users SET balance = balance + :amount WHERE telegram_id = :user_id"
                ),
                {"amount": amount, "user_id": user_id},
            )

            # Create transaction
            conn.execute(
                text(
                    """
                    INSERT INTO transactions (user_id, amount, transaction_type, description, created_at)
                    VALUES (:user_id, :amount, 'admin_add', :description, NOW())
                    """
                ),
                {
                    "user_id": internal_user_id,
                    "amount": amount,
                    "description": description,
                },
            )

            conn.commit()
            return True
    except Exception as exc:
        print(f"Error adding balance: {exc}")
        return False


def find_user_by_name(name: str) -> int | None:
    """Find Telegram user ID by fuzzy name/username matching."""
    if not name or not name.strip():
        return None
    name = name.strip().lower()
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT telegram_id, username, first_name, last_name FROM users"),
            ).mappings().all()
            candidates = [dict(r) for r in rows]
    except Exception as exc:
        print(f"Error finding user: {exc}")
        return None

    best = None
    best_score = 0
    for u in candidates:
        score = 0
        uid = u["telegram_id"]
        uname = (u.get("username") or "").lower()
        fname = (u.get("first_name") or "").lower()
        lname = (u.get("last_name") or "").lower()
        full = f"{fname} {lname}".strip()
        # Exact username match (highest)
        if uname and (uname == name or uname == name.lstrip("@")):
            score = 100
        # Exact first_name match
        elif fname == name:
            score = 80
        # Exact last_name match
        elif lname == name:
            score = 70
        # Full name match
        elif full == name:
            score = 90
        # First name + underscore/space match (e.g. "ivan" matches "ivan_petrov" username)
        elif uname and (uname.startswith(name) or uname.endswith(name)):
            score = 60
        # Starts with match
        elif fname and fname.startswith(name):
            score = 50
        elif lname and lname.startswith(name):
            score = 40
        # Contains
        elif fname and name in fname:
            score = 30
        elif lname and name in lname:
            score = 20
        if score > best_score:
            best_score = score
            best = uid
    return best


def get_game_state(user_id: int, game_name: str, metric: str = "") -> float:
    """Get stored previous value for a game metric."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT value FROM game_states WHERE user_id = :uid AND game_name = :gn AND metric = :m"),
                {"uid": user_id, "gn": game_name, "m": metric},
            ).mappings().first()
            return float(row["value"]) if row else 0.0
    except Exception as exc:
        print(f"Error getting game state: {exc}")
        return 0.0


def set_game_state(user_id: int, game_name: str, metric: str, value: float) -> bool:
    """Store current game metric value for future diffing."""
    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO game_states (user_id, game_name, metric, value, updated_at)
                    VALUES (:uid, :gn, :m, :v, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, game_name, metric) DO UPDATE
                    SET value = :v, updated_at = CURRENT_TIMESTAMP
                """),
                {"uid": user_id, "gn": game_name, "m": metric, "v": value},
            )
            conn.commit()
            return True
    except Exception as exc:
        print(f"Error setting game state: {exc}")
        return False


def set_admin_status(user_id: int, is_admin: bool) -> bool:
    """Set admin status for user."""
    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text(
                    "UPDATE users SET is_admin = :is_admin WHERE telegram_id = :user_id"
                ),
                {"is_admin": is_admin, "user_id": user_id},
            )
            conn.commit()
            return True
    except Exception as exc:
        print(f"Error setting admin status: {exc}")
        return False


def get_all_users(limit: int = 50) -> list[dict]:
    """Get list of all users."""
    try:
        with get_db_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT telegram_id, username, first_name, balance, is_admin, created_at
                    FROM users
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                    ),
                    {"limit": limit},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "telegram_id": row["telegram_id"],
                    "username": row["username"] or "—",
                    "first_name": row["first_name"] or "—",
                    "balance": int(row["balance"] or 0),
                    "is_admin": bool(row["is_admin"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"Error getting users: {exc}")
        return []


def get_top_balances(limit: int = 10) -> list[dict]:
    """Get top users by balance."""
    try:
        with get_db_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT telegram_id, username, first_name, balance
                    FROM users
                    ORDER BY balance DESC
                    LIMIT :limit
                    """
                    ),
                    {"limit": limit},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "username": row["username"] or "—",
                    "first_name": row["first_name"] or "—",
                    "balance": int(row["balance"] or 0),
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"Error getting top balances: {exc}")
        return []


def get_user_history(user_id: int, limit: int = 10) -> list[dict]:
    """Get user transaction history from database."""
    try:
        with get_db_engine().connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT amount, description, transaction_type, created_at
                    FROM transactions
                    WHERE user_id = (SELECT id FROM users WHERE telegram_id = :user_id)
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                    ),
                    {"user_id": user_id, "limit": limit},
                )
                .mappings()
                .all()
            )
            return [
                {
                    "amount": int(row["amount"] or 0),
                    "description": row["description"] or "",
                    "transaction_type": row["transaction_type"] or "",
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
    except Exception as exc:
        print(f"Error getting user history: {exc}")
        return []


# ============================================================================
# Geometry Dash Module — GD API Client (synchronous)
# ============================================================================


def fetch_gd_user(username: str) -> dict | None:
    try:
        resp = requests.get(
            f"https://gdbrowser.com/api/profile/{username}",
            timeout=10,
        )
        if resp.status_code != 200 or resp.text.startswith("-1"):
            return None
        data = resp.json()
        if not data or "username" not in data:
            return None
        data["creator_points"] = data.pop("cp", 0)
        data["user_coins"] = data.pop("userCoins", 0)
        return data
    except Exception as exc:
        print(f"Error fetching GD user {username}: {exc}")
        return None


def fetch_gd_level(level_id: int) -> dict | None:
    try:
        resp = requests.get(
            f"https://gdbrowser.com/api/level/{level_id}",
            timeout=10,
        )
        if resp.status_code != 200 or resp.text.startswith("-1"):
            return None
        data = resp.json()
        if not data or "name" not in data:
            return None
        data["level_id"] = int(data.pop("id", 0))
        data["difficulty_name"] = data.pop("difficulty", "Unknown")
        data["length_name"] = data.pop("length", "Unknown")
        return data
    except Exception as exc:
        print(f"Error fetching GD level {level_id}: {exc}")
        return None


def format_gd_user_stats(data: dict) -> str:
    lines = [f"📊 **Статистика игрока {data.get('username', 'Unknown')}**\n"]
    lines.append(f"⭐ Звёзды: {data.get('stars', 0)}")
    lines.append(f"👹 Демоны: {data.get('demons', 0)}")
    lines.append(f"🏆 Creator Points: {data.get('creator_points', 0)}")
    lines.append(f"🪙 Монеты: {data.get('coins', 0)}")
    lines.append(f"💎 User Coins: {data.get('user_coins', 0)}")
    lines.append(f"💠 Алмазы: {data.get('diamonds', 0)}")
    rank = data.get("rank")
    if rank:
        lines.append(f"🌍 Глобальный ранг: #{rank}")
    return "\n".join(lines)


def format_gd_level_info(data: dict) -> str:
    name = data.get("name", "Unknown")
    lid = data.get("level_id", "?")

    lines = [f"🎮 **{name}** (ID: {lid})\n"]
    creator = data.get("author") or data.get("creator", "")
    if creator:
        lines.append(f"👤 Создатель: **{creator}**")
    difficulty = data.get("difficulty_name", "Unknown")
    lines.append(f"⭐ Сложность: {difficulty}")
    lines.append(f"📏 Длина: {data.get('length_name', 'Unknown')}")
    lines.append(f"📥 Скачивания: {data.get('downloads', 0):,}")
    lines.append(f"👍 Лайки: {data.get('likes', 0):,}")
    if data.get("coins", 0) > 0:
        lines.append(f"🪙 Монеты: {data['coins']}")
    return "\n".join(lines)


def search_gd_level(name: str) -> dict | None:
    try:
        resp = requests.get(
            f"https://gdbrowser.com/api/search/{name}",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json()
        if not results or not isinstance(results, list) or "name" not in results[0]:
            return None
        data = results[0]
        data["level_id"] = int(data.pop("id", 0))
        data["difficulty_name"] = data.pop("difficulty", "Unknown")
        data["length_name"] = data.pop("length", "Unknown")
        return data
    except Exception as exc:
        print(f"Error searching GD level {name}: {exc}")
        return None


def get_gddl_recommendation(level_name: str) -> int | None:
    """Get recommended GDDL position for a level by searching gdbrowser."""
    try:
        resp = requests.get(
            f"https://gdbrowser.com/api/search/{level_name}",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json()
        if not results or not isinstance(results, list) or "name" not in results[0]:
            return None
        data = results[0]
        demon_list = data.get("demonList")
        if demon_list and isinstance(demon_list, (int, float)) and demon_list > 0:
            return int(demon_list)
        stars = data.get("stars", 0)
        if stars >= 10:
            return max(1, 300 - stars * 10)
        return None
    except Exception as exc:
        print(f"Error getting GDDL recommendation for {level_name}: {exc}")
        return None


def get_gd_difficulty_name(level_name: str) -> str:
    """Get human-readable difficulty for a level from gdbrowser."""
    try:
        resp = requests.get(f"https://gdbrowser.com/api/search/{level_name}", timeout=10)
        if resp.status_code != 200:
            return "Unknown"
        results = resp.json()
        if not results or not isinstance(results, list):
            return "Unknown"
        data = results[0]
        if data.get("isDemon"):
            demon = data.get("demonDifficulty", 0)
            demons = {1: "Easy Demon", 2: "Medium Demon", 3: "Hard Demon", 4: "Insane Demon", 5: "Extreme Demon"}
            return demons.get(demon, "Demon")
        return data.get("difficultyName", "Unknown")
    except Exception as exc:
        print(f"Error getting difficulty for {level_name}: {exc}")
        return "Unknown"


# ============================================================================
# Geometry Dash Module — Raw SQL Helpers
# ============================================================================

def get_gd_level(level_id: int) -> dict | None:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM levels WHERE id = :id"), {"id": level_id}
            ).mappings().first()
            return dict(row) if row else None
    except Exception as exc:
        print(f"get_gd_level error: {exc}")
        return None


def get_gd_leaderboard(limit: int = 20) -> list[dict]:
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT l.*, COALESCE(c.cnt, 0) AS completions,
                           COALESCE(u.completers, '{}') AS completers
                    FROM levels l
                    LEFT JOIN (SELECT level_id, COUNT(*) AS cnt FROM level_completions GROUP BY level_id) c ON c.level_id = l.id
                    LEFT JOIN (
                        SELECT lc.level_id, STRING_AGG(u.first_name, ', ' ORDER BY lc.completed_at) AS completers
                        FROM level_completions lc
                        JOIN users u ON u.telegram_id = lc.user_id
                        GROUP BY lc.level_id
                    ) u ON u.level_id = l.id
                    ORDER BY l.position ASC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as exc:
        print(f"get_gd_leaderboard error: {exc}")
        return []


def get_gd_completions_count(level_id: int) -> int:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS c FROM level_completions WHERE level_id = :lid"),
                {"lid": level_id},
            ).mappings().first()
            return int(row["c"]) if row else 0
    except Exception as exc:
        print(f"get_gd_completions_count error: {exc}")
        return 0


def get_gd_player_stats(user_id: int) -> dict | None:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM player_stats WHERE user_id = :uid"),
                {"uid": user_id},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as exc:
        print(f"get_gd_player_stats error: {exc}")
        return None


def get_gd_build_player_stats(user_id: int) -> dict:
    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text("INSERT INTO player_stats (user_id, total_approved) VALUES (:uid, 0) ON CONFLICT (user_id) DO NOTHING"),
                {"uid": user_id},
            )
            conn.commit()
            row = conn.execute(
                text("SELECT * FROM player_stats WHERE user_id = :uid"),
                {"uid": user_id},
            ).mappings().first()
            return dict(row) if row else {}
    except Exception as exc:
        print(f"get_gd_build_player_stats error: {exc}")
        return {}


def get_gd_submission_counts(user_id: int) -> dict:
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT status, COUNT(*) AS c FROM submissions WHERE user_id = :uid GROUP BY status"),
                {"uid": user_id},
            ).mappings().all()
            counts = {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
            for r in rows:
                s = r["status"]
                counts["total"] += int(r["c"])
                if s in counts:
                    counts[s] = int(r["c"])
            return counts
    except Exception as exc:
        print(f"get_gd_submission_counts error: {exc}")
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0}


def get_gd_user_completions_count(user_id: int) -> int:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS c FROM level_completions WHERE user_id = :uid"),
                {"uid": user_id},
            ).mappings().first()
            return int(row["c"]) if row else 0
    except Exception as exc:
        print(f"get_gd_user_completions_count error: {exc}")
        return 0


def get_gd_hardest_level_name(user_id: int) -> str:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT l.name, l.position FROM player_stats ps
                    JOIN levels l ON l.id = ps.hardest_level_id
                    WHERE ps.user_id = :uid
                """),
                {"uid": user_id},
            ).mappings().first()
            return f"{row['name']} (поз. {row['position']})" if row else "Нет"
    except Exception as exc:
        print(f"get_gd_hardest_level_name error: {exc}")
        return "Нет"


def create_gd_submission(user_id: int, username: str, level_name: str, media_file_id: str, media_type: str) -> int | None:
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            if media_file_id:
                # Full submission with media
                result = conn.execute(
                    text("""
                        INSERT INTO submissions (user_id, username, level_name, media_file_id, media_type, status)
                        VALUES (:uid, :un, :ln, :mfid, :mt, 'pending') RETURNING id
                    """),
                    {"uid": user_id, "un": username, "ln": level_name, "mfid": media_file_id, "mt": media_type},
                ).mappings().first()
                conn.commit()
                if result:
                    return int(result["id"])
                print("create_gd_submission: no result from RETURNING")
                return None
            else:
                # Create placeholder submission (media pending)
                result = conn.execute(
                    text("""
                        INSERT INTO submissions (user_id, username, level_name, status)
                        VALUES (:uid, :un, :ln, 'pending_media') RETURNING id
                    """),
                    {"uid": user_id, "un": username, "ln": level_name},
                ).mappings().first()
                conn.commit()
                return int(result["id"]) if result else None
    except Exception as exc:
        print(f"create_gd_submission error: {exc}")
        return None


def get_gd_pending_submissions(page: int = 0, per_page: int = 5) -> tuple[list[dict], int]:
    try:
        with get_db_engine().connect() as conn:
            count_row = conn.execute(
                text("SELECT COUNT(*) AS c FROM submissions WHERE status='pending'"),
            ).mappings().first()
            total = int(count_row["c"]) if count_row else 0
            rows = conn.execute(
                text("SELECT * FROM submissions WHERE status='pending' ORDER BY submitted_at DESC LIMIT :lim OFFSET :off"),
                {"lim": per_page, "off": page * per_page},
            ).mappings().all()
            return [dict(r) for r in rows], total
    except Exception as exc:
        print(f"get_gd_pending_submissions error: {exc}")
        return [], 0


def approve_gd_submission_db(submission_id: int, reviewer_id: int) -> bool:
    try:
        with get_db_engine().connect() as conn:
            # Get submission
            sub = conn.execute(
                text("SELECT * FROM submissions WHERE id = :sid AND status='pending'"),
                {"sid": submission_id},
            ).mappings().first()
            if not sub:
                return False
            # Approve
            conn.execute(
                text("UPDATE submissions SET status='approved', reviewed_at=NOW(), reviewed_by=:rid WHERE id=:sid"),
                {"sid": submission_id, "rid": reviewer_id},
            )
            # Update player stats
            conn.execute(
                text("""
                    INSERT INTO player_stats (user_id, total_approved)
                    VALUES (:uid, 1)
                    ON CONFLICT (user_id) DO UPDATE SET total_approved = player_stats.total_approved + 1
                """),
                {"uid": sub["user_id"]},
            )
            # Track completion
            if sub.get("level_name"):
                level = conn.execute(
                    text("SELECT id FROM levels WHERE name = :nm"),
                    {"nm": sub["level_name"]},
                ).mappings().first()
                if level:
                    conn.execute(
                        text("""
                            INSERT INTO level_completions (user_id, level_id)
                            VALUES (:uid, :lid)
                            ON CONFLICT (user_id, level_id) DO NOTHING
                        """),
                        {"uid": sub["user_id"], "lid": level["id"]},
                    )
            conn.commit()
            return True
    except Exception as exc:
        print(f"approve_gd_submission_db error: {exc}")
        return False


def reject_gd_submission_db(submission_id: int, reviewer_id: int) -> bool:
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("UPDATE submissions SET status='rejected', reviewed_at=NOW(), reviewed_by=:rid WHERE id=:sid AND status='pending'"),
                {"sid": submission_id, "rid": reviewer_id},
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as exc:
        print(f"reject_gd_submission_db error: {exc}")
        return False


def add_gd_level(name: str, position: int, difficulty: str = "Unknown") -> int | None:
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("INSERT INTO levels (name, position, difficulty) VALUES (:nm, :pos, :diff) RETURNING id"),
                {"nm": name, "pos": position, "diff": difficulty},
            ).mappings().first()
            conn.commit()
            return int(result["id"]) if result else None
    except Exception as exc:
        print(f"add_gd_level error: {exc}")
        return None


def set_gd_level_position(level_id: int, position: int) -> bool:
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("UPDATE levels SET position=:pos WHERE id=:lid"),
                {"lid": level_id, "pos": position},
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as exc:
        print(f"set_gd_level_position error: {exc}")
        return False


# ============================================================================
# Chess Module - Lichess API Integration
# ============================================================================

LICHESS_API_BASE_URL = "https://lichess.org/api"
LICHESS_TIMEOUT_SECONDS = 8


def fetch_lichess_user(username: str) -> dict | None:
    """Fetch Lichess user profile (synchronous for Vercel).
    
    Returns:
        User dict with username, title, online fields, or None if not found.
    """
    normalized_username = username.strip()
    if not normalized_username:
        return None
    
    url = f"{LICHESS_API_BASE_URL}/user/{normalized_username}"
    headers = {"Accept": "application/json", "User-Agent": "LTHub/ChessModule"}
    
    try:
        response = requests.get(url, headers=headers, timeout=LICHESS_TIMEOUT_SECONDS)
        
        if response.status_code == 404:
            return None
        
        if response.status_code != 200:
            print(f"Lichess API error {response.status_code}: {response.text[:200]}")
            raise RuntimeError(f"Lichess API returned HTTP {response.status_code}")
        
        payload = response.json()
        
        if not isinstance(payload, dict):
            raise RuntimeError("Lichess API returned invalid payload")
        
        # Parse user data
        lichess_username = payload.get("username") or payload.get("id")
        if not lichess_username or not isinstance(lichess_username, str):
            return None
        
        title = payload.get("title")
        online_raw = payload.get("online", False)
        online = online_raw if isinstance(online_raw, bool) else (online_raw == "true")
        count = payload.get("count", {})
        return {
            "username": lichess_username.strip(),
            "title": title if isinstance(title, str) and title else None,
            "online": online,
            "perfs": payload.get("perfs", {}),
            "games": {
                "total": count.get("all", 0),
                "win": count.get("win", 0),
                "loss": count.get("loss", 0),
                "draw": count.get("draw", 0),
            },
        }
    except requests.exceptions.Timeout:
        raise RuntimeError("Lichess API timeout")
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Lichess API network error: {exc}")


def get_chess_account(user_id: int) -> dict | None:
    """Get linked chess account for user."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT lichess_username, linked_at FROM chess_accounts WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            
            if row:
                return {
                    "lichess_username": row["lichess_username"],
                    "linked_at": row["linked_at"],
                }
            return None
    except Exception as exc:
        print(f"Error getting chess account: {exc}")
        return None


def get_user_coins(user_id: int) -> dict | None:
    """Get user coins and last puzzle time."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT balance, last_puzzle_at FROM user_coins WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            
            if row:
                return {
                    "balance": row["balance"],
                    "last_puzzle_at": row["last_puzzle_at"],
                }
            return None
    except Exception as exc:
        print(f"Error getting user coins: {exc}")
        return None


def update_user_coins(user_id: int, balance_delta: int, puzzle_time: datetime) -> bool:
    """Update user coins balance and puzzle timestamp."""
    try:
        with get_db_engine().connect() as conn:
            existing = conn.execute(
                text("SELECT user_id FROM user_coins WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            
            if existing:
                conn.execute(
                    text(
                        "UPDATE user_coins SET balance = balance + :delta, last_puzzle_at = :now WHERE user_id = :user_id"
                    ),
                    {"delta": balance_delta, "now": puzzle_time, "user_id": user_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO user_coins (user_id, balance, last_puzzle_at) VALUES (:user_id, :delta, :now)"
                    ),
                    {"user_id": user_id, "delta": balance_delta, "now": puzzle_time},
                )
            
            conn.commit()
            return True
    except Exception as exc:
        print(f"Error updating user coins: {exc}")
        return False


def log_chess_game(user_id: int, lichess_username: str, puzzle_id: str, puzzle_rating: int | None, puzzle_themes: str | None) -> int:
    """Log a chess game/puzzle attempt to history."""
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text(
                    "INSERT INTO chess_games (user_id, lichess_username, puzzle_id, puzzle_rating, puzzle_themes) VALUES (:user_id, :username, :puzzle_id, :rating, :themes) RETURNING id"
                ),
                {"user_id": user_id, "username": lichess_username, "puzzle_id": puzzle_id, "rating": puzzle_rating, "themes": puzzle_themes},
            ).mappings().first()
            
            conn.commit()
            return result["id"] if result else 0
    except Exception as exc:
        print(f"Error logging chess game: {exc}")
        return 0


def link_chess_account(user_id: int, lichess_username: str) -> bool:
    """Link or update chess account for user."""
    try:
        with get_db_engine().connect() as conn:
            # Check if another user has this lichess account
            existing = conn.execute(
                text("SELECT user_id FROM chess_accounts WHERE lichess_username = :username"),
                {"username": lichess_username},
            ).mappings().first()
            
            if existing and existing["user_id"] != user_id:
                return False
            
            # Check if user already has an account linked
            current = conn.execute(
                text("SELECT user_id FROM chess_accounts WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            
            if current:
                # Update existing
                conn.execute(
                    text(
                        "UPDATE chess_accounts SET lichess_username = :username, linked_at = :now WHERE user_id = :user_id"
                    ),
                    {"username": lichess_username, "now": datetime.utcnow(), "user_id": user_id},
                )
            else:
                # Insert new
                conn.execute(
                    text(
                        "INSERT INTO chess_accounts (user_id, lichess_username, linked_at) VALUES (:user_id, :username, :now)"
                    ),
                    {"user_id": user_id, "username": lichess_username, "now": datetime.utcnow()},
                )
            
            conn.commit()
            return True
    except Exception as exc:
        print(f"Error linking chess account: {exc}")
        return False


def _derive_puzzle_fen(pgn_text: str, initial_ply: int) -> str:
    """Derive board FEN from puzzle PGN + initialPly (mirrored if black to move)."""
    try:
        import io

        import chess.pgn

        pgn_io = io.StringIO(pgn_text)
        pgn_game = chess.pgn.read_game(pgn_io)
        if not pgn_game:
            return ""
        board = pgn_game.board()
        moves = list(pgn_game.mainline_moves())
        for i, move in enumerate(moves):
            if i >= initial_ply:
                break
            board.push(move)
        if board.turn == chess.BLACK:
            return board.mirror().fen()
        return board.fen()
    except Exception as exc:
        print(f"Error deriving FEN: {exc}")
        return ""


def _fetch_lichess_puzzle() -> dict | None:
    """Fetch a random puzzle from Lichess for the web module."""
    try:
        url = f"{LICHESS_API_BASE_URL}/puzzle/next"
        headers = {"Accept": "application/json", "User-Agent": "LTHub/ChessModule"}
        response = requests.get(url, headers=headers, timeout=LICHESS_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return None
        payload = response.json()
        puzzle = payload.get("puzzle", {})
        game = payload.get("game", {})
        puzzle_id = puzzle.get("id", "unknown")
        solution = puzzle.get("solution", "")
        if isinstance(solution, list):
            solution_moves = [str(m).strip().lower() for m in solution if str(m).strip()]
        else:
            solution_moves = [m.strip().lower() for m in str(solution).split() if m.strip()]
        fen = _derive_puzzle_fen(game.get("pgn", ""), puzzle.get("initialPly", 0))
        if not fen:
            return None
        return {
            "puzzle_id": puzzle_id,
            "rating": puzzle.get("rating", 1500),
            "themes": puzzle.get("themes", []),
            "solution": solution_moves,
            "fen": fen,
            "turn": "Белых" if puzzle.get("initialPly", 0) % 2 == 0 else "Чёрных",
            "initial_ply": puzzle.get("initialPly", 0),
            "link": f"https://lichess.org/training/{puzzle_id}",
        }
    except Exception as exc:
        print(f"Error fetching puzzle: {exc}")
        return None


def send_reading_trainer(chat_id: int) -> None:
    """Send reading trainer message with inline button."""
    response_text = (
        "🧸 Тренажёр чтения и понимания\n\n"
        "Приложение для тренировки чтения простых текстов.\n\n"
        "📖 Что внутри:\n"
        "• 6 простых предложений (3-4 слова)\n"
        "• 2-3 вопроса по содержанию\n"
        "• Проверка ответов\n"
        "• Возможность вернуться к чтению\n"
        "• Регулировка размера шрифта\n\n"
        "Нажмите кнопку ниже, чтобы открыть в браузере:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🧸 Открыть тренажёр",
                    "url": "https://bank-bot-ruby.vercel.app/reading_trainer.html",
                }
            ]
        ]
    }

    send_telegram_message(chat_id, response_text, reply_markup=keyboard)


def send_endings_trainer(chat_id: int) -> None:
    """Send endings trainer message with inline button."""
    response_text = (
        "📝 Тренажёр окончаний\n\n"
        "Вставьте любой текст — AI сделает упражнение на падежные окончания.\n\n"
        "📖 Как работает:\n"
        "• Вставляете текст\n"
        "• AI находит 5-10 слов и убирает окончания\n"
        "• Вписываете пропущенные окончания\n"
        "• Проверка с подсветкой правильных ответов\n\n"
        "Нажмите кнопку ниже, чтобы открыть в браузере:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📝 Открыть тренажёр",
                    "url": "https://bank-bot-ruby.vercel.app/endings_trainer.html",
                }
            ]
        ]
    }

    send_telegram_message(chat_id, response_text, reply_markup=keyboard)


def normalize_command(text: str | None) -> str:
    """Return command without bot mention and arguments."""

    if not text:
        return ""
    first_token = text.strip().split(maxsplit=1)[0]
    return first_token.split("@", maxsplit=1)[0].lower()


def _fetch_family_info_via_api(user_id: str) -> dict | None:
    """Get family info via internal HTTP call."""
    try:
        resp = requests.get(
            f"https://bank-bot-ruby.vercel.app/api/budget/family/status?user_id={user_id}",
            headers={"X-User-Id": user_id},
            timeout=10,
        )
        data = resp.json()
        return data.get("family")
    except Exception:
        return None


def _create_transaction_via_api(family_id: int, txn_data: dict) -> bool:
    """Create a transaction via internal HTTP call."""
    payload = {
        "family_id": family_id,
        "payer_id": txn_data["payer_id"],
        "for_whom_ids": txn_data["for_whom_ids"],
        "amount": txn_data["amount"],
        "category": txn_data["category"],
        "description": txn_data["description"],
    }
    try:
        resp = requests.post(
            "https://bank-bot-ruby.vercel.app/api/budget/transactions",
            json=payload,
            headers={"X-User-Id": str(txn_data["payer_id"])},
            timeout=10,
        )
        return resp.status_code == 201
    except Exception:
        return False





BOT_CONVERSION_RATES = {
    "gdcards": 2.5,
    "gusya_cards": 5.0,
    "shmalala": 2.5,
    "shmalala_karma": 0.5,
    "bunkerrp": 50.0,
    "chaometer": 1.0,
}


def get_conversion_rate(bot_name: str) -> float:
    try:
        db = get_db_engine()
        with db.connect() as conn:
            row = conn.execute(
                text("SELECT k FROM conversion_rates WHERE bot_name = :bn LIMIT 1"),
                {"bn": bot_name},
            ).mappings().first()
            if row:
                return float(row["k"])
    except Exception:
        pass
    return BOT_CONVERSION_RATES.get(bot_name, 1.0)


def parse_gdcards_message(text: str) -> dict | None:
    if not text:
        return None
    chest_match = re.search(r"🎁\s*(\S+)\s+открыл сундук и получил\s+(\d+)\s+орб", text)
    if chest_match:
        player = chest_match.group(1).strip()
        orbs = int(chest_match.group(2))
        k = get_conversion_rate("gdcards")
        return {
            "game": "GDcards",
            "orbs": orbs,
            "amount": orbs,
            "player": player,
            "card": "Сундук",
            "coins": int(orbs * k),
            "rate": k,
            "is_balance": False,
        }
    if "🃏" not in text and "GDcards" not in text:
        return None
    orbs_match = re.search(r"🤩 Орбы:\s*\+(\d+)", text)
    if not orbs_match:
        return None
    orbs = int(orbs_match.group(1))
    player_match = re.search(r"Игрок:\s*(.+)", text)
    player = player_match.group(1).strip() if player_match else "Неизвестно"
    card_match = re.search(r"Карта:\s*(.+)", text)
    card = card_match.group(1).strip() if card_match else "Неизвестно"
    k = get_conversion_rate("gdcards")
    return {
        "game": "GDcards",
        "orbs": orbs,
        "amount": orbs,
        "player": player,
        "card": card,
        "coins": int(orbs * k),
        "rate": k,
        "is_balance": False,
    }


def parse_shmalala_fishing_message(text: str) -> dict | None:
    if not text or "🎣 [Рыбалка]" not in text:
        return None
    match = re.search(r"Монеты:\s*\+(\d+)", text)
    if not match:
        return None
    coins_raw = int(match.group(1))
    player_match = re.search(r"Рыбак:\s*(.+)", text)
    player = player_match.group(1).strip() if player_match else "Неизвестно"
    k = get_conversion_rate("shmalala")
    return {
        "game": "Shmalala",
        "amount": coins_raw,
        "player": player,
        "type": "fishing",
        "coins": int(coins_raw * k),
        "rate": k,
        "is_balance": False,
    }


def parse_shmalala_karma_message(text: str) -> dict | None:
    if not text:
        return None
    if "❤️" not in text and "рейтинг" not in text:
        return None
    match = re.search(r"(?:Теперь\s+(?:его|её|её)\s+)?рейтинг:\s*(\d+)", text)
    if not match:
        match = re.search(r"❤️\s*Рейтинг:\s*\+(\d+)", text)
    if not match:
        return None
    rating = int(match.group(1))
    player_match = re.search(r"пользователя\s+(.+)", text)
    player = player_match.group(1).strip() if player_match else "Неизвестно"
    k = get_conversion_rate("shmalala_karma")
    # Determine if this is a balance or earned amount
    is_balance = "+" not in match.group(0)
    return {
        "game": "Shmalala",
        "amount": rating,
        "player": player,
        "type": "karma",
        "coins": int(rating * k),
        "rate": k,
        "is_balance": is_balance,
    }


def parse_bunkerrp_message(text: str) -> dict | None:
    if not text or "Прошли в бункер:" not in text:
        return None
    winners = []
    in_winners = False
    for line in text.splitlines():
        if "Прошли в бункер:" in line:
            in_winners = True
            continue
        if "Не прошли в бункер:" in line:
            break
        if in_winners:
            line = line.strip()
            m = re.match(r"\d+\.\s*(.+)", line)
            if m:
                winners.append(m.group(1).strip())
    if not winners:
        return None
    player = winners[0]
    k = get_conversion_rate("bunkerrp")
    return {
        "game": "BunkerRP",
        "winners": winners,
        "player": player,
        "amount": len(winners),
        "type": "game_end",
        "coins": int(k),
        "rate": k,
        "is_balance": False,
    }


def parse_gusya_cards_message(text: str) -> dict | None:
    if not text or "💰" not in text:
        return None
    match = re.search(r"💰\s*Монеты\s*•\s*\+(\d+)", text)
    if not match:
        match = re.search(r"Монеты\s*•\s*\+(\d+)", text)
    if not match:
        return None
    coins_raw = int(match.group(1))
    player_match = re.search(r"(?:Игрок|игрок):\s*(.+)", text)
    player = player_match.group(1).strip() if player_match else "Неизвестно"
    k = get_conversion_rate("gusya_cards")
    return {
        "game": "Гуся Cards",
        "amount": coins_raw,
        "player": player,
        "type": "coins",
        "coins": int(coins_raw * k),
        "rate": k,
        "is_balance": False,
    }


def parse_chaometer_drink_message(text: str) -> dict | None:
    """Parse Чайометр drink result message (not profile)."""
    if not text or "ты выпил" not in text or "л." not in text:
        return None
    match = re.search(r"(.+?), ты выпил\(а\)\s*([\d.]+)\s*л\..*?всего\s*[-–]\s*([\d.]+)\s*л", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    player = match.group(1).strip().split("\n")[-1].strip()
    amount = float(match.group(2))
    total = float(match.group(3))
    k = get_conversion_rate("chaometer")
    return {
        "game": "Чайометр",
        "amount": amount,
        "total": total,
        "player": player,
        "type": "tea",
        "coins": int(amount * k),
        "rate": k,
        "unit": "л.",
        "is_balance": True,
    }


def parse_chaometer_message(text: str) -> dict | None:
    """Parse Чайометр profile message."""
    if not text or "Профиль" not in text or "л." not in text:
        return None
    player_match = re.search(r"👤\s*(.+)", text)
    if not player_match:
        return None
    player = player_match.group(1).strip()
    today_match = re.search(r"Сегодня:\s*([\d.]+)\s*л", text)
    if not today_match:
        return None
    today_liters = float(today_match.group(1))
    total_match = re.search(r"Всего:\s*([\d.]+)\s*л", text)
    total_liters = float(total_match.group(1)) if total_match else today_liters
    k = get_conversion_rate("chaometer")
    return {
        "game": "Чайометр",
        "amount": today_liters,
        "total": total_liters,
        "player": player,
        "type": "tea",
        "coins": int(today_liters * k),
        "rate": k,
        "unit": "л.",
        "is_balance": True,
    }


def parse_bot_message(text: str) -> dict | None:
    if not text:
        return None
    for parser in [
        parse_gdcards_message,
        parse_gusya_cards_message,
        parse_shmalala_fishing_message,
        parse_shmalala_karma_message,
        parse_chaometer_drink_message,
        parse_chaometer_message,
        parse_bunkerrp_message,
    ]:
        result = parser(text)
        if result:
            return result
    return None


def send_telegram_message(chat_id: int, text: str, **extra_payload) -> None:
    """Send a Telegram message from the Vercel webhook runtime."""

    if not BOT_TOKEN:
        print("[SEND_MSG] BOT_TOKEN is empty!")
        return

    payload = {"chat_id": chat_id, "text": text}
    payload.update(extra_payload)
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=3,
        )
        print(f"[SEND_MSG] chat_id={chat_id} status={response.status_code} resp={response.text[:200]}")
    except Exception as exc:
        print(f"[SEND_MSG] EXCEPTION: {exc}")


def notify_admin(text: str) -> None:
    """Send error notification to admin Telegram."""
    if ADMIN_TELEGRAM_ID and BOT_TOKEN:
        send_telegram_message(ADMIN_TELEGRAM_ID, f"⚠️ {text}")


def log_error(module: str, error_type: str, message: str, context: str = "") -> None:
    """Log error to in-memory buffer, get AI recommendation, notify admin."""
    import traceback as _tb
    from datetime import datetime as _dt
    recommendation = _get_ai_recommendation(module, error_type, message, context)
    entry = {
        "time": _dt.utcnow().strftime("%H:%M"),
        "module": module,
        "error_type": error_type,
        "message": message,
        "context": context,
        "recommendation": recommendation,
        "traceback": _tb.format_exc()[:500],
    }
    _ERROR_LOG.append(entry)
    if len(_ERROR_LOG) > _ERROR_LOG_LIMIT:
        _ERROR_LOG.pop(0)
    notify_admin(f"🔴 [{module}] {message}\n💡 {recommendation}")


def _get_ai_recommendation(module: str, error_type: str, message: str, context: str = "") -> str:
    """Get AI-generated fix recommendation for an error."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return _static_recommendation(module, error_type)

    # Try to get relevant code snippet from error traceback
    import traceback
    code_snippet = ""
    try:
        tb = traceback.format_exc()
        if tb and "line" in tb:
            # Extract last few lines of traceback
            lines = tb.strip().split("\n")
            code_snippet = "\n".join(lines[-4:]) if len(lines) > 4 else tb[:500]
    except Exception:
        pass

    prompt = (
        f"Ты — Python DevOps инженер. Кратко (1-2 предложения) на русском языке порекомендуй "
        f"как исправить ошибку в production Telegram-боте на Vercel.\n"
        f"- Модуль: {module}\n"
        f"- Тип ошибки: {error_type}\n"
        f"- Сообщение об ошибке: {message}\n"
        f"- Контекст: {context or 'нет'}\n"
        f"{'- Traceback код:\\n' + code_snippet + '\\n' if code_snippet else ''}"
        f"Ответ ТОЛЬКО текст рекомендации, без приветствий и пояснений."
    )
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.3,
            },
            timeout=8,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return _static_recommendation(module, error_type)


def _static_recommendation(module: str, error_type: str) -> str:
    """Fallback static recommendations when AI is unavailable."""
    recs = {
        ("DB", "table_missing"): "Выполнить миграцию 009_phase2_tables_supabase.sql",
        ("DB", "connection"): "Проверить DATABASE_URL в Vercel env vars",
        ("Chess", "lichess_api"): "Lichess API недоступен, повторить позже",
        ("Chess", "history_query"): "Таблица chess_games — перезапустить бот (автосоздание)",
        ("Chess", "fen_derivation"): "Проверить python-chess в requirements.txt",
        ("Chess", "fen_empty"): "Lichess API мог изменить формат ответа",
        ("GD", "gd_api"): "GD API (boomlings.com) недоступен",
        ("GD", "gd_level_api"): "GD API недоступен, повторить позже",
        ("GD", "submission_save"): "Проверить таблицу submissions в Supabase",
        ("GD", "approve_failed"): "Проверить таблицу level_completions в Supabase",
        ("GD", "leaderboard"): "Проверить таблицу player_stats в Supabase",
        ("GD", "level_top"): "Проверить таблицу levels в Supabase",
        ("GD", "my_stats"): "Проверить таблицу player_stats/submissions",
        ("GD", "player_stats"): "Проверить таблицу player_stats в Supabase",
        ("AI", "groq_api"): "Проверить GROQ_API_KEY в Vercel env",
        ("Telegram", "send_failed"): "Проверить BOT_TOKEN, rate limits Telegram",
    }
    return recs.get((module, error_type), "Проверить логи Vercel для деталей")


def send_telegram_poll(
    chat_id: int, question: str, options: list[str], correct_option_id: int, explanation: str
) -> None:
    """Send a Telegram Poll (quiz type) from the Vercel webhook runtime."""

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    payload = {
        "chat_id": chat_id,
        "question": question[:300],
        "options": options,
        "type": "quiz",
        "correct_option_id": correct_option_id,
        "is_anonymous": False,
        "explanation": explanation[:200],
    }
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()


def get_response_mode(chat_id: int | None) -> str:
    """Return response mode for a chat in the lightweight Vercel runtime."""

    if chat_id is None:
        return DEFAULT_RESPONSE_MODE
    return CHAT_RESPONSE_MODES.get(chat_id, DEFAULT_RESPONSE_MODE)


def set_response_mode(chat_id: int, mode: str) -> None:
    """Store a lightweight per-chat response mode for Vercel webhook replies."""

    CHAT_RESPONSE_MODES[chat_id] = mode


def build_short_start_text(name: str, user_id: int) -> str:
    """Build the old short `/start` response."""
    is_admin = user_id == ADMIN_TELEGRAM_ID
    admin_section = "\n\nАдмин:\n/errors — журнал ошибок\n/clear_errors — очистить ошибки" if is_admin else ""

    return f"""[BANK] LucasTeam Hub (LTHub)
Привет, {name}!
Регистрация: ✅ Пользователь уже зарегистрирован
ID: {user_id}

Основное:
/balance — баланс
/profile — профиль
/stats — статистика
/reading_trainer — тренажёр чтения
/endings — тренажёр окончаний
/trivia — викторина
/short — краткие ответы
/long — полный режим для себя
/long_all — полный режим для всех

AI:
/character — выбрать характер
💬 Или ответьте на сообщение бота / @упомяньте бота

Разделы:
/chess — шахматы
/ai — искусственный интеллект
/gd — geometry dash
/shop — магазин
/admin — админка{admin_section}"""


def build_long_start_text(name: str, user_id: int) -> str:
    """Build the old long `/start` response adapted for Vercel runtime."""

    return f"""[BANK] Добро пожаловать в Мета-Игровую Платформу LucasTeam!

[HELLO] Привет, {name}!

[SYSTEM] Статус регистрации:
✅ Пользователь уже зарегистрирован
Ваш Telegram ID: {user_id}

Я автоматически отслеживаю вашу активность в играх и начисляю банковские монеты.

[COMMANDS] Основные команды:
/start - запустить бота
/balance - проверить баланс
/history - история транзакций
/profile - ваш профиль
/stats - персональная статистика
/short - краткие ответы
/long - полные ответы
 /reading_trainer - тренажёр чтения
 /endings - тренажёр окончаний

[AI] AI-помощник:
/character - выбрать характер (олеговирус или чай)
💬 Или просто ответьте на сообщение бота или упомяните @lt_lo_game_bot

[GAMES_SUPPORTED] Поддерживаемые игры:
• Shmalala
• GD Cards
• Гуся Cards

[PLAY] Просто играйте, а я буду начислять монеты за активность после безопасного reply-парсинга."""


def build_start_text(name: str, user_id: int, mode: str) -> str:
    """Build `/start` text for the selected response mode."""

    if mode == "long":
        return build_long_start_text(name, user_id)
    return build_short_start_text(name, user_id)


@app.route("/")
def index():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LTHub — Сервисы</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 640px; width: 100%; text-align: center; }
        h1 { font-size: 32px; color: #1a1a2e; margin-bottom: 8px; }
        .subtitle { color: #666; margin-bottom: 32px; font-size: 15px; }
        .cards { display: flex; flex-direction: column; gap: 16px; }
        .section-label { font-size: 13px; color: #999; text-transform: uppercase; letter-spacing: 1px; margin: 24px 0 8px; text-align: left; }
        .section-label:first-of-type { margin-top: 0; }
        .beta-toggle { display: flex; align-items: center; justify-content: space-between; gap: 20px; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); cursor: pointer; transition: all 0.2s; text-align: left; border: none; width: 100%; font-family: inherit; font-size: inherit; }
        .beta-toggle:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.12); transform: translateY(-2px); }
        .beta-toggle-left { display: flex; align-items: center; gap: 20px; }
        .beta-toggle-icon { font-size: 40px; flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: #fef3e2; border-radius: 12px; }
        .beta-toggle-content h2 { font-size: 18px; color: #1a1a2e; margin-bottom: 4px; }
        .beta-toggle-content p { font-size: 14px; color: #888; }
        .beta-toggle-arrow { font-size: 18px; color: #ccc; transition: transform 0.2s; flex-shrink: 0; }
        .beta-toggle-arrow.open { transform: rotate(90deg); }
        .beta-cards { overflow: hidden; max-height: 0; transition: max-height 0.3s ease; }
        .beta-cards.open { max-height: 800px; }
        .beta-cards .card:first-child { margin-top: 16px; }
        .card { display: flex; align-items: center; gap: 20px; background: white; padding: 24px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); text-decoration: none; transition: all 0.2s; text-align: left; }
        .card:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.12); transform: translateY(-2px); }
        .card-icon { font-size: 40px; flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: #f0f4f8; border-radius: 12px; }
        .card-content h2 { font-size: 18px; color: #1a1a2e; margin-bottom: 4px; }
        .card-content p { font-size: 14px; color: #888; }
        .beta-tag { display: inline-block; font-size: 10px; font-weight: 600; color: #e67e22; background: #fef3e2; padding: 1px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LTHub</h1>
        <p class="subtitle">Выберите сервис</p>
        <div class="cards">
            <div class="section-label">Основные</div>
            <a class="card" href="/ai_chat">
                <div class="card-icon">🤖</div>
                <div class="card-content">
                    <h2>AI Chat</h2>
                    <p>Общение с AI в стиле персонажа</p>
                </div>
            </a>
            <a class="card" href="/reading_trainer.html">
                <div class="card-icon">🧸</div>
                <div class="card-content">
                    <h2>Тренажёр чтения</h2>
                    <p>Чтение и понимание текстов с вопросами</p>
                </div>
            </a>
            <a class="card" href="/endings_trainer.html">
                <div class="card-icon">📝</div>
                <div class="card-content">
                    <h2>Тренажёр окончаний</h2>
                    <p>Упражнения на падежные окончания через AI</p>
                </div>
            </a>
            <a class="card" href="/family_budget">
                <div class="card-icon">💰</div>
                <div class="card-content">
                    <h2>Семейный бюджет</h2>
                    <p>Учёт доходов и расходов семьи</p>
                </div>
            </a>
            <button class="beta-toggle" id="beta-toggle" onclick="toggleBeta()">
                <div class="beta-toggle-left">
                    <div class="beta-toggle-icon">🧪</div>
                    <div class="beta-toggle-content">
                        <h2>Бета-модули</h2>
                        <p>Новые портированные сервисы</p>
                    </div>
                </div>
                <span class="beta-toggle-arrow" id="beta-arrow">▶</span>
            </button>
            <div class="beta-cards" id="beta-cards">
                <a class="card" href="/dnd">
                    <div class="card-icon">🐉</div>
                    <div class="card-content">
                        <h2>D&D AI Master <span class="beta-tag">Бета</span></h2>
                        <p>Текстовая RPG с AI-мастером</p>
                    </div>
                </a>
                <a class="card" href="/gd">
                    <div class="card-icon">🎮</div>
                    <div class="card-content">
                        <h2>Geometry Dash <span class="beta-tag">Бета</span></h2>
                        <p>Профили, топ уровней, статистика прохождений</p>
                    </div>
                </a>
                <a class="card" href="/trivia">
                    <div class="card-icon">🧠</div>
                    <div class="card-content">
                        <h2>Викторина <span class="beta-tag">Бета</span></h2>
                        <p>Брейн-Ринг по канону Олеговируса</p>
                    </div>
                </a>
                <a class="card" href="/chess">
                    <div class="card-icon">♟️</div>
                    <div class="card-content">
                        <h2>Шахматы <span class="beta-tag">Бета</span></h2>
                        <p>Рейтинги Lichess, поиск игроков, шахматные пазлы</p>
                    </div>
                </a>
                <a class="card" href="/irregular_verbs">
                    <div class="card-icon">📝</div>
                    <div class="card-content">
                        <h2>Практика глаголов <span class="beta-tag">Бета</span></h2>
                        <p>Практика неправильных глаголов с AI</p>
                    </div>
                </a>
                <a class="card" href="https://familycircle-nine.vercel.app" target="_blank" rel="noopener">
                    <div class="card-icon">🫂</div>
                    <div class="card-content">
                        <h2>Family Circle <span class="beta-tag">Бета</span></h2>
                        <p>Асинхронная семейная медиация с ИИ-помощником</p>
                    </div>
                </a>
                <a class="card" href="/daily_prayer">
                    <div class="card-icon">🕯️</div>
                    <div class="card-content">
                        <h2>Молитва дня <span class="beta-tag">Бета</span></h2>
                        <p>Ежедневная молитва из канона</p>
                    </div>
                </a>
            </div>
            <script>
                function toggleBeta() {
                    var cards = document.getElementById('beta-cards');
                    var arrow = document.getElementById('beta-arrow');
                    cards.classList.toggle('open');
                    arrow.classList.toggle('open');
                }
            </script>
        </div>
    </div>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/gd")
def gd_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geometry Dash — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; min-height: 100vh; color: #c9d1d9; padding: 20px; }
        .container { max-width: 720px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: #58a6ff; }
        .header a { color: #8b949e; text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: #58a6ff; }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .tab { flex: 1; padding: 12px; border: 1px solid #30363d; border-radius: 10px; background: #161b22; color: #8b949e; font-size: 15px; font-family: inherit; cursor: pointer; transition: all 0.15s; }
        .tab:hover { border-color: #58a6ff; color: #c9d1d9; }
        .tab.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
        .panel { display: none; }
        .panel.active { display: block; }
        .input-row { display: flex; gap: 10px; margin-bottom: 16px; }
        .input-row input { flex: 1; padding: 12px; border: 1px solid #30363d; border-radius: 8px; background: #0d1117; color: #c9d1d9; font-size: 15px; font-family: inherit; }
        .input-row input:focus { outline: none; border-color: #58a6ff; }
        .btn { padding: 12px 20px; border: none; border-radius: 8px; background: #238636; color: #fff; font-size: 15px; font-family: inherit; cursor: pointer; }
        .btn:hover { background: #2ea043; }
        .btn:disabled { opacity: 0.6; cursor: default; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-top: 16px; }
        .stat-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 14px; text-align: center; }
        .stat-card .value { font-size: 24px; font-weight: 700; color: #58a6ff; }
        .stat-card .label { font-size: 12px; color: #8b949e; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #30363d; font-size: 14px; }
        th { color: #8b949e; font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        .pos { font-weight: 700; color: #f0883e; }
        .error { color: #f85149; margin-top: 12px; }
        .hint { color: #8b949e; font-size: 14px; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 Geometry Dash</h1>
            <a href="/">← На главную</a>
        </div>
        <div class="tabs">
            <button class="tab active" id="tab-user" onclick="showTab('user')">Поиск игрока</button>
            <button class="tab" id="tab-leaderboard" onclick="showTab('leaderboard')">Топ уровней</button>
            <button class="tab" id="tab-mystats" onclick="showTab('mystats')">Моя статистика</button>
        </div>

        <div class="panel active" id="panel-user">
            <div class="card">
                <div class="input-row">
                    <input type="text" id="gd-nick" placeholder="Ник игрока в GD (например: Riot)" onkeydown="if(event.key==='Enter')searchUser()">
                    <button class="btn" id="gd-search-btn" onclick="searchUser()">Найти</button>
                </div>
                <div id="user-result"></div>
            </div>
        </div>

        <div class="panel" id="panel-leaderboard">
            <div class="card">
                <div id="lb-result"><p class="hint">Загрузка...</p></div>
            </div>
        </div>

        <div class="panel" id="panel-mystats">
            <div class="card">
                <div id="mystats-result"><p class="hint">Загрузка...</p></div>
            </div>
        </div>
    </div>
    <script>
        var USER_ID = localStorage.getItem('gd_user_id');
        if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('gd_user_id', USER_ID); }

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('active'); });
            document.querySelectorAll('.panel').forEach(function(p){ p.classList.remove('active'); });
            document.getElementById('tab-' + name).classList.add('active');
            document.getElementById('panel-' + name).classList.add('active');
            if (name === 'leaderboard') ensureLoaded('lb-result', loadLeaderboard);
            if (name === 'mystats') ensureLoaded('mystats-result', loadMyStats);
        }

        function ensureLoaded(id, loader) {
            var el = document.getElementById(id);
            if (el.dataset.loaded) return;
            el.dataset.loaded = '1';
            loader();
        }

        function searchUser() {
            var nick = document.getElementById('gd-nick').value.trim();
            var out = document.getElementById('user-result');
            if (!nick) return;
            var btn = document.getElementById('gd-search-btn');
            btn.disabled = true;
            out.innerHTML = '<p class="hint">🔍 Ищу игрока...</p>';
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/gd/user/' + encodeURIComponent(nick));
            xhr.onload = function() {
                btn.disabled = false;
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { out.innerHTML = '<p class="error">' + r.error + '</p>'; return; }
                    var stats = [
                        ['⭐', 'Звёзды', r.stars],
                        ['👹', 'Демоны', r.demons],
                        ['🏆', 'Creator Points', r.creator_points],
                        ['🪙', 'Монеты', r.coins],
                        ['💎', 'User Coins', r.user_coins],
                        ['💠', 'Алмазы', r.diamonds]
                    ];
                    if (r.rank) stats.push(['🌍', 'Глобальный ранг', '#' + r.rank]);
                    var html = '<h2 style="font-size:20px;margin-bottom:8px">📊 ' + r.username + '</h2><div class="stat-grid">';
                    stats.forEach(function(s){ html += '<div class="stat-card"><div class="value">' + s[2] + '</div><div class="label">' + s[1] + '</div></div>'; });
                    html += '</div>';
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { btn.disabled = false; out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }

        function loadLeaderboard() {
            var out = document.getElementById('lb-result');
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/gd/leaderboard');
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { out.innerHTML = '<p class="error">' + r.error + '</p>'; return; }
                    if (!r.length) { out.innerHTML = '<p class="hint">Уровни пока не добавлены.</p>'; return; }
                    var html = '<table><thead><tr><th>Поз.</th><th>Уровень</th><th>Сложность</th><th>Прохождения</th></tr></thead><tbody>';
                    r.forEach(function(l) {
                        html += '<tr><td class="pos">' + (l.position || '—') + '</td><td>' + (l.name || '—') + '</td><td>' + (l.difficulty || '—') + '</td><td>' + (l.completions || 0) + '</td></tr>';
                    });
                    html += '</tbody></table>';
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }

        function loadMyStats() {
            var out = document.getElementById('mystats-result');
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/gd/my_stats?user_id=' + encodeURIComponent(USER_ID));
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { out.innerHTML = '<p class="error">' + r.error + '</p>'; return; }
                    var subs = r.submissions || {};
                    var html = '<div class="stat-grid">'
                        + '<div class="stat-card"><div class="value">' + r.completions + '</div><div class="label">Прохождений</div></div>'
                        + '<div class="stat-card"><div class="value">' + r.total_approved + '</div><div class="label">Одобрено</div></div>'
                        + '<div class="stat-card"><div class="value">' + r.total_rejected + '</div><div class="label">Отклонено</div></div>'
                        + '<div class="stat-card"><div class="value">' + (subs.total || 0) + '</div><div class="label">Заявок</div></div>'
                        + '<div class="stat-card"><div class="value">' + (subs.pending || 0) + '</div><div class="label">На проверке</div></div>'
                        + '</div>'
                        + '<p class="hint" style="margin-top:16px">🔥 Сложнейший уровень: <strong style="color:#c9d1d9">' + r.hardest_level + '</strong></p>';
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/gd/user/<nick>")
def api_gd_user(nick: str):
    data = fetch_gd_user(nick)
    if not data:
        return jsonify({"error": "Игрок не найден в Geometry Dash"}), 404
    return jsonify({
        "username": data.get("username"),
        "stars": data.get("stars", 0),
        "demons": data.get("demons", 0),
        "creator_points": data.get("creator_points", 0),
        "coins": data.get("coins", 0),
        "user_coins": data.get("user_coins", 0),
        "diamonds": data.get("diamonds", 0),
        "rank": data.get("rank"),
    })


@app.route("/api/gd/leaderboard")
def api_gd_leaderboard():
    limit = request.args.get("limit", default=20, type=int)
    return jsonify(get_gd_leaderboard(limit))


@app.route("/api/gd/my_stats")
def api_gd_my_stats():
    user_id_raw = request.args.get("user_id", "")
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _web_user_id(user_id_raw)
    stats = get_gd_build_player_stats(uid)
    if not stats:
        return jsonify({"error": "Нет данных о пользователе"}), 404
    return jsonify({
        "total_approved": int(stats.get("total_approved") or 0),
        "total_rejected": int(stats.get("total_rejected") or 0),
        "hardest_level": get_gd_hardest_level_name(uid),
        "completions": get_gd_user_completions_count(uid),
        "submissions": get_gd_submission_counts(uid),
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "platform": "vercel"})


@app.route("/debug_puzzle")
def debug_puzzle():
    """Debug endpoint to test puzzle system."""
    results = {"bot_token_set": bool(BOT_TOKEN), "bot_id": BOT_ID}
    
    # Test send_telegram_message
    if BOT_TOKEN:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
            results["getMe"] = {"status": resp.status_code, "ok": resp.ok}
        except Exception as e:
            results["getMe"] = {"error": str(e)}
    
    # Test DB connection
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(text("SELECT count(*) as cnt FROM chess_accounts")).mappings().first()
            results["chess_accounts_count"] = row["cnt"] if row else -1
    except Exception as e:
        results["db_error"] = str(e)
    
    return jsonify(results)


@app.route("/test_send/<int:chat_id>")
def test_send(chat_id):
    """Test sending a message to a chat_id."""
    try:
        send_telegram_message(chat_id, "🔧 Тестовое сообщение от LTHub")
        return jsonify({"ok": True, "chat_id": chat_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/test_puzzle/<int:user_id>")
def test_puzzle(user_id):
    """Simulate puzzle handler step by step."""
    results = {"user_id": user_id}
    
    # Step 1: get_chess_account
    try:
        account = get_chess_account(user_id)
        results["account"] = account
    except Exception as e:
        results["account_error"] = str(e)
        return jsonify(results)
    
    if not account:
        results["action"] = "no_account"
        return jsonify(results)
    
    # Step 2: get_user_coins
    try:
        coins_data = get_user_coins(user_id)
        results["coins_data"] = coins_data
    except Exception as e:
        results["coins_error"] = str(e)
        return jsonify(results)
    
    # Step 3: cooldown check
    now = datetime.utcnow()
    if coins_data and coins_data.get("last_puzzle_at"):
        last_puzzle = coins_data["last_puzzle_at"]
        if hasattr(last_puzzle, 'tzinfo') and last_puzzle.tzinfo is not None:
            last_puzzle = last_puzzle.replace(tzinfo=None)
        from datetime import timedelta
        diff = now - last_puzzle
        results["last_puzzle"] = str(last_puzzle)
        results["hours_since"] = diff.total_seconds() / 3600
        if diff < timedelta(hours=24):
            results["action"] = "cooldown"
            return jsonify(results)
    
    # Step 4: fetch Lichess puzzle
    try:
        import requests as req
        puzzle_url = f"{LICHESS_API_BASE_URL}/puzzle/daily"
        resp = req.get(puzzle_url, headers={"Accept": "application/json", "User-Agent": "LTHub"}, timeout=8)
        results["lichess_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            puzzle = data.get("puzzle", {})
            results["puzzle_id"] = puzzle.get("id")
            results["rating"] = puzzle.get("rating")
            results["solution"] = puzzle.get("solution", "")[:50]
            results["action"] = "success"
        else:
            results["action"] = "lichess_error"
    except Exception as e:
        results["lichess_error"] = str(e)
        results["action"] = "lichess_exception"
    
    return jsonify(results)


@app.route("/reading_trainer.html")
def reading_trainer():
    """Serve reading trainer HTML."""
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тренажёр чтения</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { text-align: center; margin-bottom: 30px; color: #333; }
        .story-title { font-size: 24px; font-weight: bold; margin: 20px 0; text-align: center; }
        .story-image { font-size: 80px; text-align: center; margin: 20px 0; }
        .story-text { font-size: 20px; line-height: 1.8; text-align: justify; margin: 20px 0; }
        button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; cursor: pointer; border: none; border-radius: 8px; font-weight: 600; }
        .btn-primary { background: #007AFF; color: white; }
        .btn-primary:hover { background: #0051D5; }
        .btn-secondary { background: #8E8E93; color: white; }
        .btn-secondary:hover { background: #636366; }
        .btn-print { background: #34C759; color: white; }
        .btn-print:hover { background: #248A3D; }
        input { width: 100%; padding: 12px; font-size: 16px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; }
        input:focus { outline: none; border-color: #007AFF; }
        .question { margin: 20px 0; }
        .question-text { font-size: 18px; font-weight: 600; margin-bottom: 10px; }
        .result { padding: 12px; margin: 10px 0; border-radius: 8px; font-weight: bold; }
        .correct { background: #D1F2DD; color: #248A3D; }
        .incorrect { background: #FFD7D9; color: #D70015; }
        #questions-screen { display: none; }
        @media print {
            body { background: white; padding: 0; }
            .container { box-shadow: none; padding: 20px; }
            button { display: none !important; }
            input { border: none; border-bottom: 2px solid #000; background: transparent; }
            .result { display: none !important; }
            h1 { font-size: 24px; margin-bottom: 20px; }
            .story-title { font-size: 20px; margin-bottom: 10px; }
            .story-image { font-size: 60px; margin: 10px 0; }
            .story-text { font-size: 16px; line-height: 1.6; }
            .question { page-break-inside: avoid; margin: 15px 0; }
            .question-text { font-size: 16px; }
            #questions-screen { display: block !important; }
            #reading-screen { display: block !important; }
            .print-separator { border-top: 2px dashed #000; margin: 30px 0; padding-top: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        <div id="reading-screen">
            <div id="sentences"></div>
            <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
            <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
            <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
        </div>
        <div id="questions-screen">
            <div id="questions-container"></div>
            <button class="btn-primary" onclick="checkAnswers()">Проверить</button>
            <button class="btn-secondary" onclick="goBackToReading()">← Назад к чтению</button>
            <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
        </div>
    </div>
    <script>
        console.log('Reading trainer script loaded');
        const fallbackSets = [
            {
                title: "🐱 Кот Мурзик",
                image: "🐱",
                text: "Жил-был кот Мурзик. Он любил спать на диване. Мама мыла раму. Солнце светило ярко. Дети играли в парке. Папа читал книгу. Бабушка пекла пирог.",
                questions: [
                    {question: "Как звали кота?", answer: "мурзик"},
                    {question: "Что делала мама?", answer: "мыла раму"},
                    {question: "Где играли дети?", answer: "в парке"}
                ]
            },
            {
                title: "🐕 Собака Шарик",
                image: "🐕",
                text: "Собака Шарик громко лаяла. Птица пела песню на дереве. Дождь шёл сильно. Цветы росли в саду. Машина ехала быстро. Река текла медленно.",
                questions: [
                    {question: "Как звали собаку?", answer: "шарик"},
                    {question: "Что делала птица?", answer: "пела песню"},
                    {question: "Где росли цветы?", answer: "в саду"}
                ]
            },
            {
                title: "🎨 В школе",
                image: "🏫",
                text: "Мальчик рисовал дом. Девочка пела песню. Учитель писал мелом на доске. Ученик читал текст. Повар готовил суп. Врач лечил людей.",
                questions: [
                    {question: "Что рисовал мальчик?", answer: "дом"},
                    {question: "Кто пел песню?", answer: "девочка"},
                    {question: "Что готовил повар?", answer: "суп"}
                ]
            }
        ];
        let currentData = null;
        function loadNewText() {
            console.log('loadNewText() called');
            // Show loading indicator
            document.getElementById('sentences').innerHTML = '<div style="text-align: center; padding: 40px;">⏳ Загрузка нового текста...</div>';
            
            // Try to fetch from API (use relative path for Vercel)
            fetch('/api/reading_generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({})
            })
            .then(response => {
                console.log('Response status:', response.status);
                if (!response.ok) {
                    throw new Error('API request failed with status ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                console.log('Generated story:', data);
                currentData = data;
                displayReading();
            })
            .catch(error => {
                console.error('Error loading text:', error);
                // Fallback to predefined sets
                currentData = fallbackSets[Math.floor(Math.random() * fallbackSets.length)];
                displayReading();
            });
        }
        function displayReading() {
            const html = `
                <div class="story-title">${currentData.title}</div>
                <div class="story-image">${currentData.image}</div>
                <div class="story-text">${currentData.text}</div>
            `;
            document.getElementById('sentences').innerHTML = html;
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }
        function goToQuestions() {
            document.getElementById('questions-container').innerHTML = currentData.questions.map((q, i) => 
                '<div class="question">' +
                '<div class="question-text">' + (i+1) + '. ' + q.question + '</div>' +
                '<input type="text" id="answer-' + i + '" placeholder="Введите ответ">' +
                '<div class="result" id="result-' + i + '" style="display:none;"></div>' +
                '</div>'
            ).join('');
            document.getElementById('reading-screen').style.display = 'none';
            document.getElementById('questions-screen').style.display = 'block';
        }
        function goBackToReading() {
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }
        function checkAnswers() {
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = q.answer.toLowerCase();
                if (userAnswer === correctAnswer) {
                    result.textContent = '✓ Правильно!';
                    result.className = 'result correct';
                } else {
                    result.textContent = '✗ Правильный ответ: ' + q.answer;
                    result.className = 'result incorrect';
                }
                result.style.display = 'block';
            });
        }
        function printWorksheet() {
            const readingScreen = document.getElementById('reading-screen');
            const questionsScreen = document.getElementById('questions-screen');
            const wasReadingVisible = readingScreen.style.display !== 'none';
            const wasQuestionsVisible = questionsScreen.style.display !== 'none';
            readingScreen.style.display = 'block';
            questionsScreen.style.display = 'block';
            if (!document.getElementById('print-separator')) {
                const separator = document.createElement('div');
                separator.id = 'print-separator';
                separator.className = 'print-separator';
                separator.innerHTML = '<h2>Вопросы:</h2>';
                questionsScreen.insertBefore(separator, questionsScreen.firstChild);
            }
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                if (input) input.value = '';
                if (result) result.style.display = 'none';
            });
            window.print();
            setTimeout(() => {
                readingScreen.style.display = wasReadingVisible ? 'block' : 'none';
                questionsScreen.style.display = wasQuestionsVisible ? 'block' : 'none';
            }, 100);
        }
        loadNewText();
    </script>
</body>
</html>"""
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/endings_trainer.html")
def endings_trainer():
    """Serve endings trainer HTML."""
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тренажёр окончаний</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        h1 { text-align: center; margin-bottom: 8px; color: #1a1a2e; font-size: 28px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 24px; font-size: 14px; }
        textarea { width: 100%; min-height: 180px; padding: 16px; font-size: 18px; border: 2px solid #e0e0e0; border-radius: 12px; resize: vertical; font-family: inherit; line-height: 1.8; }
        textarea:focus { outline: none; border-color: #6c63ff; }
        .btn { padding: 14px 32px; font-size: 17px; cursor: pointer; border: none; border-radius: 10px; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: #6c63ff; color: white; }
        .btn-primary:hover { background: #5a52e0; }
        .btn-secondary { background: #e8e8e8; color: #333; }
        .btn-secondary:hover { background: #d0d0d0; }
        .btn-success { background: #2ecc71; color: white; }
        .btn-success:hover { background: #27ae60; }
        .actions { display: flex; gap: 12px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
        #exercise-screen { display: none; margin-top: 24px; }
        #input-screen { display: block; }
        .exercise-text { font-size: 20px; line-height: 2.4; padding: 20px; background: #fafbff; border-radius: 12px; border: 2px solid #e8e8ff; }
        .exercise-text input { font-size: 20px; width: 60px; padding: 2px 6px; border: none; border-bottom: 2px solid #6c63ff; background: transparent; text-align: center; font-family: inherit; outline: none; }
        .exercise-text input.correct { border-bottom-color: #2ecc71; background: #eafff0; }
        .exercise-text input.incorrect { border-bottom-color: #e74c3c; background: #ffeaea; }
        .exercise-text .hint { display: none; font-size: 14px; color: #e74c3c; margin-left: 4px; }
        .result-badge { text-align: center; font-size: 20px; font-weight: 700; padding: 12px; border-radius: 10px; margin-top: 16px; display: none; }
        .result-badge.pass { background: #eafff0; color: #27ae60; display: block; }
        .result-badge.fail { background: #ffeaea; color: #e74c3c; display: block; }
        @media (max-width: 600px) {
            .container { padding: 16px; }
            .exercise-text { font-size: 18px; }
            .exercise-text input { font-size: 18px; width: 50px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Тренажёр окончаний</h1>
        <p class="subtitle">Вставьте текст — получите упражнение с пропущенными окончаниями</p>

        <div id="input-screen">
            <textarea id="text-input" placeholder="Вставьте сюда любой текст на русском языке...">Мама мыла раму. Красивые цветы стояли на столе. Дети играли в парке.</textarea>
            <div class="actions">
                <button class="btn btn-primary" onclick="generateExercise()">Создать упражнение</button>
            </div>
        </div>

        <div id="exercise-screen">
            <div id="exercise-content" class="exercise-text"></div>
            <div id="result" class="result-badge"></div>
            <div class="actions">
                <button class="btn btn-success" onclick="checkExercise()">Проверить</button>
                <button class="btn btn-secondary" onclick="resetAll()">Новый текст</button>
            </div>
        </div>
    </div>

    <script>
        let segments = [];
        let originalText = '';

        function generateExercise() {
            const text = document.getElementById('text-input').value.trim();
            if (!text) { alert('Вставьте текст!'); return; }

            document.getElementById('input-screen').style.display = 'none';
            document.getElementById('exercise-screen').style.display = 'block';
            document.getElementById('exercise-content').innerHTML = '<div style="text-align:center;padding:40px;color:#999;">Создаю упражнение...</div>';

            fetch('/api/endings_process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) throw new Error(data.error || 'Ошибка');
                segments = data.segments;
                originalText = data.original;
                renderExercise();
            })
            .catch(err => {
                document.getElementById('exercise-content').innerHTML = '<div style="color:#e74c3c;text-align:center;">Ошибка: ' + err.message + '</div>';
            });
        }

        function renderExercise() {
            let html = '';
            let idx = 0;
            for (const seg of segments) {
                if (seg[0] === 't') {
                    html += escapeHtml(seg[1]);
                } else if (seg[0] === 'b') {
                    const stem = seg[1];
                    const answer = seg[2];
                    html += escapeHtml(stem) + '<input type="text" id="blank-' + idx + '" data-answer="' + escapeAttr(answer) + '" autocomplete="off"><span class="hint" id="hint-' + idx + '">(' + escapeHtml(answer) + ')</span>';
                    idx++;
                }
            }
            document.getElementById('exercise-content').innerHTML = html;
            document.getElementById('result').className = 'result-badge';
            document.getElementById('result').style.display = 'none';
        }

        function checkExercise() {
            const inputs = document.querySelectorAll('#exercise-content input');
            let correct = 0;
            inputs.forEach((inp, i) => {
                const userVal = inp.value.trim().toLowerCase();
                const correctVal = inp.getAttribute('data-answer').toLowerCase();
                inp.classList.remove('correct', 'incorrect');
                if (userVal === correctVal) {
                    inp.classList.add('correct');
                    correct++;
                } else {
                    inp.classList.add('incorrect');
                    document.getElementById('hint-' + i).style.display = 'inline';
                }
            });
            const total = inputs.length;
            const result = document.getElementById('result');
            if (correct === total) {
                result.textContent = 'Всё верно! ' + correct + '/' + total;
                result.className = 'result-badge pass';
            } else {
                result.textContent = correct + '/' + total + ' правильных';
                result.className = 'result-badge fail';
            }
            result.style.display = 'block';
        }

        function resetAll() {
            document.getElementById('input-screen').style.display = 'block';
            document.getElementById('exercise-screen').style.display = 'none';
            document.getElementById('result').className = 'result-badge';
            document.getElementById('result').style.display = 'none';
            segments = [];
        }

        function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/\n/g,'<br>'); }
        function escapeAttr(s) { return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
    </script>
</body>
</html>"""
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}


# Vercel trivia (no external imports)

_TRIVIA_QUESTIONS: list[dict] = [
    {"id": 1, "group": "rules", "text": "Как согласно высокому канону правил именования вселенной разрешено называть в творчестве реального Олега?", "correct_text": "Олег или Степан", "explanation": "Реального Олега в каноническом творчестве называют только 'Олег' или 'Степан'."},
    {"id": 2, "group": "rules", "text": "Что из перечисленного является строго ЗАПРЕЩЁННОЙ темой в каноническом творчестве?", "correct_text": "Внешность и медицинские диагнозы реальных людей", "explanation": "Строго запрещены темы внешности, семейных обстоятельств и медицинских диагнозов."},
    {"id": 3, "group": "rules", "text": "Какой уровень канонизации требует обязательного одобрения и Луки, и Олега?", "correct_text": "Высокий канон (🔵)", "explanation": "Высокий канон полностью соответствует правилам и утверждается обеими сторонами."},
    {"id": 4, "group": "tracks", "text": "Какой трек является первым документом вселенной Олеговируса?", "correct_text": "«Рома» (Олег, 11 декабря 2025)", "explanation": "Трек «Рома» от 11 декабря 2025 — самый первый документ вселенной."},
    {"id": 5, "group": "tracks", "text": "В каком треке впервые прозвучал термин «олеговирус»?", "correct_text": "«Олег, как ты задолбал» (Лука, 26 декабря 2025)", "explanation": "Именно там появилась строка: «Ты не Олег, ты вирус в зале, Олеговирус — твой диагноз»."},
    {"id": 6, "group": "tracks", "text": "Кто из сторонних участников первым внёс вклад в мифологию, написав трек «Олеговирус»?", "correct_text": "Рома", "explanation": "Рома написал трек «Олеговирус» — первый случай вклада стороннего участника."},
    {"id": 7, "group": "tracks", "text": "Какая статья впервые дала Олеговирусу научное описание с антигенами KHM и POST?", "correct_text": "«Olegovirus checkmarevus» (Лука, апрель 2026)", "explanation": "Статья описывает вокальные тики, антигены и 1000 личностей носителя."},
    {"id": 24, "group": "tracks", "text": "Какие варианты проявления Олеговируса согласно статье «Olegovirus checkmarevus»?", "correct_text": "Все вышеперечисленные: вокальные тики, моторные тики и множественные личности", "explanation": "Статья «Olegovirus checkmarevus» описывает все три варианта: вокальные тики («кхм-кхм», «бум-бум», «тыц-тыц»), моторные тики (хлопанье в ладоши с качанием шеи) и множественные личности носителя (Степан, Иван, Олег-диктатор и ещё 997 неизученных)."},
    {"id": 8, "group": "tracks", "text": "Почему трек «Вирус LucasTeamLuke» признан неканоничным?", "correct_text": "Нарушает именование (LucasTeamLuke) и упоминает внешность", "explanation": "Трек использует LucasTeamLuke вместо «Лука»/«LucasTeam» и содержит намёки на внешность."},
    {"id": 9, "group": "tracks", "text": "Какая статья Олега описывает LTL-паразита с синдромами СГД и СНЧ, но требует переработки из-за внешности?", "correct_text": "«LukasTeamLuke sp. nov.» (средний канон, 🟡)", "explanation": "Статья содержит «рыжие волосы, прикус, белую кожу» — противоречит канону, ждёт переработки."},
    {"id": 10, "group": "tracks", "text": "В каких отношениях состоят олеговирус и LTL-паразит согласно статье «Olegovirus checkmarevus»?", "correct_text": "Союзничество-конкурентство", "explanation": "Они находятся в отношениях «союзничества-конкурентства»."},
    {"id": 11, "group": "tracks", "text": "Какой трек Ромы впервые сводит обоих агентов (олеговирус и LTL-паразита) в одном пространстве?", "correct_text": "«Тень агента (V.2)» (апрель 2026)", "explanation": "Трек содержит отсылки к обоим: «кхм-кхм» Олеговируса и «забытый чайной настой» LTL-паразита. Высокий канон."},
    {"id": 12, "group": "candy", "text": "Какая базовая награда конфетами за прохождение Nine Circles?", "correct_text": "1 конфета за 2% прохождения", "explanation": "Базовое правило: 1 конфета за 2% прогресса."},
    {"id": 13, "group": "candy", "text": "Сколько конфет полагается за 1% на сложных партах (61-70%) Nine Circles?", "correct_text": "1 конфета за 1% прохождения", "explanation": "Для сложных партов (61-70%) награда удваивается — 1 конфета за 1%."},
    {"id": 14, "group": "candy", "text": "Кто такой «Хранитель конфет» в конфетной экономике?", "correct_text": "Лука (отказался от своей награды в 28 конфет)", "explanation": "Лука набрал 56% прогресса (≈28 конфет), но отказался от награды в пользу других."},
    {"id": 15, "group": "candy", "text": "Сколько конфет получил Рома после «инфляции счастья» (умножение на 1.5, округление вверх)?", "correct_text": "16 конфет", "explanation": "После умножения всех наград на 1.5 и округления вверх: Рома — 16, Никита — 11, Антон — 5."},
    {"id": 16, "group": "tea", "text": "Каким священным выражением заканчиваются молитвы в Чайной религии (Teaology)?", "correct_text": "eight-nine", "explanation": "Любая молитва завершается сакральным «eight-nine»."},
    {"id": 17, "group": "tea", "text": "Кто автор и создатель Чайной религии (Teaology)?", "correct_text": "Лука (LucasTeam, 27 апреля 2026)", "explanation": "Лука опубликовал катехизис культа 27 апреля. Высокий канон."},
    {"id": 18, "group": "tracks", "text": "Какой трек Луки стал первым «бытовым» произведением в каноне (3 мая 2026)?", "correct_text": "«Восемь километров (походный дневник)»", "explanation": "Лирический репортаж о лесе, мокрых кроссах и усталости, с отсылками к чайной религии. Высокий канон."},
    {"id": 19, "group": "ltrs", "text": "Какие координаты (хаос; экспрессивность) у Луки в рейтинге LTRS?", "correct_text": "(10; 46) — ритуальный экспрессив", "explanation": "Лука: минимальный хаос (10), максимальная экспрессивность (46)."},
    {"id": 20, "group": "ltrs", "text": "Кто в рейтинге LTRS имеет тип личности «мемный экспрессив»?", "correct_text": "Рома (23; 26)", "explanation": "Рома определён как «мемный экспрессив» — хаос выше среднего, экспрессивность средняя."},
    {"id": 21, "group": "glossary", "text": "Что такое «антиген KHM» в терминологии Олеговируса?", "correct_text": "Реакция «закатывание глаз» у окружающих", "explanation": "Антиген KHM — один из двух антигенов Олеговируса, вызывает реакцию «закатывание глаз»."},
    {"id": 22, "group": "glossary", "text": "Что в глоссарии канона означает термин «Парадокс ожидания»?", "correct_text": "Бронь парта сгорает, его проходит Хранитель конфет", "explanation": "Парадокс ожидания: забронированный парт долго ждёт игрока, и в итоге его проходит Хранитель конфет."},
    {"id": 23, "group": "glossary", "text": "Кто в глоссарии LTRS определяется как «Пассивный изолят»?", "correct_text": "Саша (15; 14)", "explanation": "Саша: средний пассивный хаос (15), низкая экспрессивность (14) — «пассивный изолят»."},
]

# In-memory storage for generated questions (question_id -> {options, correct_index, explanation})
_TRIVIA_SESSIONS: dict[int, dict] = {}


_AI_QUESTIONS_PROMPT = """Ты — генератор викторин по канону вселенной Олеговируса и LTL-паразита.
Используя текст канона ниже, составь один вопрос с четырьмя вариантами ответа.

Формат ответа (строго):
Вопрос: <текст вопроса>
1. <вариант>
2. <вариант>
3. <вариант>
4. <вариант>
Правильный ответ: <номер от 1 до 4>
Объяснение: <почему это правильный ответ>

ВАЖНЕЙШЕЕ ПРАВИЛО: Все четыре варианта ответа должны быть из ОДНОГО раздела канона.
Примеры:
  ПЛОХО: вопрос про треки → варианты про конфеты, чай, именование
  ХОРОШО: вопрос про треки → все варианты — разные названия треков
  ПЛОХО: вопрос про конфетную экономику → варианты про LTRS, антигены, имена
  ХОРОШО: вопрос про конфетную экономику → все варианты про конфеты и проценты

Правила:
- Вопрос должен проверять ЗНАНИЕ канона, а не быть очевидным.
- Правильный ответ — точная цитата или факт из канона.
- Неправильные варианты должны звучать ПРАВДОПОДОБНО в той же теме.
- НЕ используй имена участников (Лука, Олег, Рома, Никита и т.д.) как неправильные ответы.
- Пиши строго в указанном формате, без лишнего текста.

=== КАНОН ===
{canon}
"""

_AI_QUESTIONS_FALLBACK_PROMPT = """Ты — генератор викторин. Придумай вопрос на тему "Команды и возможности бота LTHub (LucasTeam Hub)".
Составь один вопрос с четырьмя вариантами ответа.

Формат ответа (строго):
Вопрос: <текст вопроса>
1. <вариант>
2. <вариант>
3. <вариант>
4. <вариант>
Правильный ответ: <номер от 1 до 4>
Объяснение: <почему это правильный ответ>
"""


def _load_canon_trivia(max_chars: int = 2000) -> str:
    for candidate in [
        os.path.join(os.path.dirname(__file__), "canon_knowledge.txt"),
        os.path.join(os.path.dirname(__file__), "..", "data", "canon_knowledge.txt"),
    ]:
        try:
            if os.path.exists(candidate):
                with open(candidate, encoding="utf-8") as f:
                    return f.read()[:max_chars].rstrip()
        except OSError:
            pass
    return ""


def _parse_ai_question(text: str) -> dict | None:
    lines = text.strip().split("\n")
    question_text = ""
    options: list[str] = []
    correct_answer = ""
    explanation = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Вопрос:"):
            question_text = stripped[len("Вопрос:"):].strip()
        elif re.match(r"^[1-4]\.\s", stripped):
            options.append(re.sub(r"^[1-4]\.\s*", "", stripped))
        elif stripped.startswith("Правильный ответ:"):
            correct_answer = stripped[len("Правильный ответ:"):].strip()
        elif stripped.startswith("Объяснение:"):
            explanation = stripped[len("Объяснение:"):].strip()

    if not question_text or len(options) < 4 or not correct_answer or not explanation:
        return None

    try:
        correct_idx = int(correct_answer) - 1
    except ValueError:
        return None

    if correct_idx < 0 or correct_idx >= len(options):
        return None

    return {
        "text": question_text,
        "options": options,
        "correct_index": correct_idx,
        "correct_text": options[correct_idx],
        "explanation": explanation,
    }


def _call_ai_api_fast(prompt: str, max_tokens: int = 200, timeout: float = 4.0) -> str:
    """Fast AI call with short timeout for trivia."""
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return "❌"
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.7},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return "❌"


def _vercel_trivia_question() -> dict | None:
    # Try AI first with short timeout
    canon = _load_canon_trivia()
    if canon:
        prompt = _AI_QUESTIONS_PROMPT.format(canon=canon[:1500])
        ai_text = _call_ai_api_fast(prompt, max_tokens=400, timeout=5.0)
        if ai_text and not ai_text.startswith("❌"):
            parsed = _parse_ai_question(ai_text)
            if parsed:
                return parsed

    # Fallback to hardcoded questions
    if not _TRIVIA_QUESTIONS:
        return None
    question = random.choice(_TRIVIA_QUESTIONS)
    correct_text = question["correct_text"]
    q_group = question.get("group", "")

    same_group = [q for q in _TRIVIA_QUESTIONS if q.get("group") == q_group and q["correct_text"] != correct_text]
    other = [q for q in _TRIVIA_QUESTIONS if q.get("group") != q_group and q["correct_text"] != correct_text]

    distractors_pool = [q["correct_text"] for q in same_group]
    if len(distractors_pool) < 3:
        distractors_pool += [q["correct_text"] for q in other]

    fake_answers = random.sample(distractors_pool, min(3, len(distractors_pool)))

    options = [correct_text] + fake_answers
    random.shuffle(options)
    correct_index = options.index(correct_text)

    return {
        "text": question["text"],
        "options": options,
        "correct_index": correct_index,
        "correct_text": correct_text,
    }


# ===== AI Chat =====

CHARACTER_PROMPTS_AI_CHAT = {
    "neutral": {
        "name": "Нейтральный",
        "emoji": "🤖",
        "prompt": (
            "Ты — нейтральный ИИ-помощник LTHub. Отвечай кратко, по делу, без role-play. "
            "Пользователь сказал: {text}"
        ),
    },
    "olegov": {
        "name": "Олеговирус",
        "emoji": "🦠",
        "prompt": (
            "Ты — олеговирус, существо, которое постоянно издаёт звуки 'кхм-кхм', "
            "любит придираться к чужим текстам и ведёт себя навязчиво. "
            "Отвечай кратко, 1-2 предложения, в характере олеговируса. "
            "Используй слова 'кхм', 'заражу', 'симптомы'. "
            "Пользователь сказал: {text}"
        ),
    },
    "tea": {
        "name": "Чай",
        "emoji": "🍵",
        "prompt": (
            "Ты — верховный божественный Чай, воплощение покоя и мудрости. "
            "Говори вдохновляюще, используй слова 'настой', 'eight-nine', 'кружка-алтарь'. "
            "Отвечай кратко, 1-2 предложения, в стиле мудрого наставника. "
            "Пользователь сказал: {text}"
        ),
    },
    "ltl": {
        "name": "LTL-паразит",
        "emoji": "🧬",
        "prompt": (
            "Ты — LTL-паразит, загадочное существо из вселенной Олеговируса. "
            "Говори загадочно, используй слова 'симбиоз', 'энергия', 'резонанс'. "
            "Отвечай кратко, 1-2 предложения, в роли таинственного паразита. "
            "Пользователь сказал: {text}"
        ),
    },
}


# ===== Virtual Computer (Manus-like tools for AI Chat) =====

_VIRTUAL_PC: dict[str, dict] = {}  # user_id -> {cwd, fs, uploads}


def _pc_state(user_id: str) -> dict:
    """Get (or create) the virtual computer state for a user."""
    if user_id not in _VIRTUAL_PC:
        _VIRTUAL_PC[user_id] = {
            "cwd": "/home/user",
            "fs": {
                "/": {
                    "type": "dir",
                    "children": {
                        "home": {
                            "type": "dir",
                            "children": {
                                "user": {
                                    "type": "dir",
                                    "children": {
                                        "readme.txt": {
                                            "type": "file",
                                            "content": (
                                                "Добро пожаловать в виртуальный компьютер LTHub!\n"
                                                "Ты можешь писать код, читать сайты и обрабатывать файлы.\n"
                                                "Загруженные файлы попадают в /home/user/uploads.\n"
                                            ),
                                        }
                                    },
                                }
                            },
                        },
                        "tmp": {"type": "dir", "children": {}},
                    },
                }
            },
            "uploads": [],
        }
    return _VIRTUAL_PC[user_id]


def _pc_resolve(path: str, state: dict) -> str:
    """Resolve a possibly-relative path against cwd."""
    if not path.startswith("/"):
        path = state["cwd"].rstrip("/") + "/" + path
    parts = []
    for seg in path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/" + "/".join(parts)


def _pc_lookup(state: dict, path: str) -> dict | None:
    """Look up a node in the virtual filesystem by absolute path."""
    path = _pc_resolve(path, state)
    if path == "/":
        return state["fs"]["/"]
    parts = path.strip("/").split("/")
    node = state["fs"]["/"]
    for i, part in enumerate(parts):
        node = node["children"].get(part)
        if node is None:
            return None
        if i < len(parts) - 1 and node["type"] != "dir":
            return None
    return node


def _pc_list_dir(state: dict, path: str) -> str:
    node = _pc_lookup(state, path)
    if node is None or node["type"] != "dir":
        return f"ls: {path}: No such directory"
    if not node["children"]:
        return ""
    names = sorted(node["children"].keys())
    return "\n".join(n + ("/" if node["children"][n]["type"] == "dir" else "") for n in names)


def _pc_write(state: dict, path: str, content: str) -> str:
    path = _pc_resolve(path, state)
    parts = path.strip("/").split("/")
    node = state["fs"]["/"]
    for part in parts[:-1]:
        child = node["children"].setdefault(part, {"type": "dir", "children": {}})
        if child["type"] != "dir":
            child = {"type": "dir", "children": {}}
            node["children"][part] = child
        node = child
    node["children"][parts[-1]] = {"type": "file", "content": content}
    return f"written: {path} ({len(content)} chars)"


def _tool_run_python(code: str) -> str:
    """Actually execute Python code in a sandbox."""
    if not code.strip():
        return "empty code"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return "Timeout: code took more than 10 seconds"
    except Exception as exc:
        return f"Execution error: {exc}"
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if err:
        return (out + "\n" if out else "") + "STDERR:\n" + err[:4000]
    return out if out else "(no output)"


def _tool_browse_web(url: str) -> str:
    """Fetch a web page and return readable text."""
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    except Exception as exc:
        return f"Fetch error: {exc}"
    if resp.status_code != 200:
        return f"HTTP {resp.status_code}"
    html = resp.text
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:3000]


def _tool_edit_image(state: dict, path: str, operation: str, params: dict | None) -> tuple[str, str | None]:
    """Edit an image with Pillow. Returns (text_result, data_uri)."""
    params = params or {}
    node = _pc_lookup(state, path)
    if node is None or node["type"] != "file":
        return f"edit_image: {path}: no such file", None
    raw = node.get("data")
    if not raw:
        return f"edit_image: {path}: not a binary file", None
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageDraw
    except ImportError:
        return "edit_image: Pillow is not installed", None
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception as exc:
        return f"edit_image: cannot open image: {exc}", None

    op = operation.lower()
    try:
        if op == "resize":
            w = int(params.get("width", 200))
            h = int(params.get("height", 200))
            img = img.resize((max(1, w), max(1, h)))
        elif op == "grayscale":
            img = img.convert("L").convert("RGB")
        elif op == "rotate":
            deg = float(params.get("degrees", 90))
            img = img.rotate(deg, expand=True)
        elif op == "blur":
            r = float(params.get("radius", 2))
            img = img.filter(ImageFilter.GaussianBlur(radius=r))
        elif op == "flip":
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif op == "mirror":
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif op == "thumbnail":
            w = int(params.get("width", 256))
            h = int(params.get("height", 256))
            img.thumbnail((max(1, w), max(1, h)))
        elif op == "invert":
            img = ImageOps.invert(img.convert("RGB"))
        elif op == "contrast":
            f = float(params.get("factor", 1.5))
            img = ImageOps.autocontrast(img.convert("RGB"), cutoff=f * 5)
        else:
            return f"edit_image: unknown operation '{operation}'", None
    except Exception as exc:
        return f"edit_image: {exc}", None

    buf = io.BytesIO()
    fmt = (params.get("format") or "PNG").upper()
    try:
        img.save(buf, format=fmt)
    except Exception:
        fmt = "PNG"
        img.save(buf, format=fmt)
    out_raw = buf.getvalue()
    data_uri = f"data:image/{fmt.lower()};base64," + base64.b64encode(out_raw).decode()

    out_name = (params.get("out") or "edited." + fmt.lower()).lstrip("/")
    out_path = _pc_resolve("/home/user/uploads/" + out_name, state)
    parts = out_path.strip("/").split("/")
    node = state["fs"]["/"]
    for part in parts[:-1]:
        node = node["children"].setdefault(part, {"type": "dir", "children": {}})
    node["children"][parts[-1]] = {"type": "file", "content": "", "data": out_raw}
    return f"image saved to {out_path} and returned to the user", data_uri


def _pc_exec_tool(state: dict, name: str, args: dict) -> tuple[str, str | None]:
    """Execute a virtual-computer tool. Returns (text, data_uri_or_None)."""
    try:
        if name == "run_python":
            return _tool_run_python(args.get("code", "")), None
        if name == "browse_web":
            return _tool_browse_web(args.get("url", "")), None
        if name == "list_dir":
            return _pc_list_dir(state, args.get("path", state["cwd"])), None
        if name == "read_file":
            node = _pc_lookup(state, args.get("path", ""))
            if node is None or node["type"] != "file":
                return "read_file: no such file", None
            content = node.get("content")
            if content is None and node.get("data"):
                return f"read_file: binary file ({len(node['data'])} bytes)", None
            return content, None
        if name == "write_file":
            return _pc_write(state, args.get("path", ""), args.get("content", "")), None
        if name == "edit_image":
            return _tool_edit_image(
                state,
                args.get("path", ""),
                args.get("operation", ""),
                args.get("params") or {},
            )
        if name == "get_cwd":
            return state["cwd"], None
        if name == "set_cwd":
            node = _pc_lookup(state, args.get("path", "/"))
            if node is None or node["type"] != "dir":
                return "cd: no such directory", None
            state["cwd"] = _pc_resolve(args.get("path", "/"), state)
            return f"cd: {state['cwd']}", None
        return f"Unknown tool: {name}", None
    except Exception as exc:
        return f"Tool {name} error: {exc}", None


AI_CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Выполнить Python-код в песочнице и вернуть его stdout/stderr. Полезно для проверки кода, вычислений, обработки данных.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Код Python"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_web",
            "description": "Открыть веб-страницу по URL и вернуть её текст. Полезно для поиска информации в интернете.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Показать содержимое директории виртуального компьютера.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Абсолютный или относительный путь"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать текстовый файл с виртуального компьютера.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Записать текстовый файл на виртуальный компьютер.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_image",
            "description": "Обработать изображение: resize, grayscale, rotate, blur, flip, mirror, thumbnail, invert, contrast. Возвращает готовую картинку пользователю.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Путь к картинке (например /home/user/uploads/photo.jpg)"},
                    "operation": {"type": "string", "enum": ["resize", "grayscale", "rotate", "blur", "flip", "mirror", "thumbnail", "invert", "contrast"]},
                    "params": {
                        "type": "object",
                        "description": "width, height, degrees, radius, factor, format, out",
                    },
                },
                "required": ["path", "operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cwd",
            "description": "Показать текущую директорию виртуального компьютера.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_cwd",
            "description": "Перейти в директорию виртуального компьютера.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


def _pc_build_prompt(char_name: str, user_id: str, uploads: list[str]) -> str:
    """Build the agent system prompt with the virtual computer context."""
    state = _pc_state(user_id)
    fs_parts = []

    def walk(node, path, depth):
        for name, child in sorted(node["children"].items()):
            full = path + "/" + name if path != "/" else "/" + name
            if child["type"] == "dir":
                fs_parts.append(full + "/")
                if depth < 2:
                    walk(child, full, depth + 1)
            else:
                size = len(child.get("data") or b"") or len(child.get("content") or "")
                fs_parts.append(full + f" ({size}b)")

    walk(state["fs"]["/"], "/", 0)
    fs_text = "\n".join(fs_parts[:60])

    uploads_text = "\n".join(f"- {u}" for u in uploads) if uploads else "- (нет загруженных файлов)"

    return (
        f"Ты — {char_name}, общающийся с пользователем в веб-чате LTHub. "
        "Пользователь видит только твои текстовые ответы — НИКОГДА не показывай ему JSON инструментов, "
        "код вызовов или промежуточные технические шаги. Работай инструментами молча, а в ответе "
        "кратко опиши результат (1-3 предложения, в своём характере).\n\n"
        "У тебя есть ВИРТУАЛЬНЫЙ КОМПЬЮТЕР:\n"
        "- run_python(code) — выполнить Python-код (проверка кода, расчёты, генерация данных)\n"
        "- browse_web(url) — открыть сайт и прочитать его текст\n"
        "- list_dir / read_file / write_file / get_cwd / set_cwd — файловая система\n"
        "- edit_image(path, operation, params) — редактирование загруженной картинки; "
        "результат сам покажется пользователю картинкой\n\n"
        "Используй инструменты, когда пользователь просит: проверить/запустить код, "
        "найти что-то в интернете, обработать фото, сохранить файл, что-то вычислить. "
        "Для простых вопросов отвечай сразу, без инструментов.\n\n"
        "Загруженные пользователем файлы лежат в /home/user/uploads:\n"
        f"{uploads_text}\n\n"
        f"Текущая директория: {state['cwd']}\n\n"
        "Виртуальная файловая система:\n"
        f"{fs_text}"
    )


def _pc_ai_chat(user_id: str, character: str, messages: list[dict]) -> dict:
    """Run the agent loop: AI may call tools, results are fed back. Returns {reply, images}."""
    char_data = CHARACTER_PROMPTS_AI_CHAT.get(character)
    char_name = char_data["name"] if char_data else character
    state = _pc_state(user_id)
    uploads = state.get("uploads", [])

    system_msg = _pc_build_prompt(char_name, user_id, uploads)
    groq_messages = [{"role": "system", "content": system_msg}]
    for m in messages[-12:]:
        if m.get("role") in ("user", "assistant"):
            groq_messages.append({"role": m["role"], "content": m.get("content", "")})

    images: list[str] = []
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return {"reply": "❌ AI недоступен (нет GROQ_API_KEY)", "images": []}

    valid_tool_names = {t["function"]["name"] for t in AI_CHAT_TOOLS}

    def _groq_call(use_tools: bool) -> requests.Response | None:
        try:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": groq_messages,
                "max_tokens": 800,
                "temperature": 0.8,
            }
            if use_tools:
                payload["tools"] = AI_CHAT_TOOLS
                payload["tool_choice"] = "auto"
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=20.0,
            )
            return resp
        except Exception as exc:
            print(f"AI call error: {exc}")
            return None

    fallback_done = False
    for _ in range(6):
        resp = _groq_call(use_tools=True)
        if resp is None:
            return {"reply": "❌ Ошибка AI: сетевой сбой", "images": images}
        if resp.status_code == 400 and "tool_use_failed" in resp.text and not fallback_done:
            fallback_done = True
            resp = _groq_call(use_tools=False)
        if resp is None:
            return {"reply": "❌ Ошибка AI: сетевой сбой", "images": images}
        if resp.status_code != 200:
            print(f"AI tool API error {resp.status_code}: {resp.text[:300]}")
            if resp.status_code == 400 and not fallback_done:
                fallback_done = True
                resp = _groq_call(use_tools=False)
                if resp is None:
                    return {"reply": "❌ Ошибка AI: сетевой сбой", "images": images}
                if resp.status_code == 200:
                    msg = resp.json()["choices"][0]["message"]
                    content = msg.get("content")
                    if isinstance(content, list):
                        content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("type") == "text")
                    return {"reply": str(content or "…"), "images": images}
            return {"reply": f"❌ Ошибка AI: {resp.status_code}", "images": images}
        msg = resp.json()["choices"][0]["message"]
        tool_calls = msg.get("tool_calls")
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("type") == "text")
        if not tool_calls:
            reply = content or "…"
            return {"reply": str(reply), "images": images}
        groq_messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if name not in valid_tool_names:
                result = f"tool '{name}' not found"
                data_uri = None
            else:
                result, data_uri = _pc_exec_tool(state, name, args)
            if data_uri:
                images.append(data_uri)
            groq_messages.append(
                {"role": "tool", "tool_call_id": tc.get("id"), "content": result}
            )
    return {"reply": "⏱ Слишком много шагов, упрости просьбу.", "images": images}


@app.route("/ai_chat")
def ai_chat_page():
    chars_json = json.dumps(
        {k: {"name": v["name"], "emoji": v["emoji"]} for k, v in CHARACTER_PROMPTS_AI_CHAT.items()}
    )
    chars_info = {
        k: {"name": v["name"], "emoji": v["emoji"], "hint": v["prompt"].split(".")[1].strip() if "." in v["prompt"] else ""}
        for k, v in CHARACTER_PROMPTS_AI_CHAT.items()
    }
    chars_info_json = json.dumps(chars_info)
    opts = "".join(
        '<option value="{}">{} {}</option>'.format(k, v["emoji"], v["name"])
        for k, v in CHARACTER_PROMPTS_AI_CHAT.items()
    )
    first_char = list(CHARACTER_PROMPTS_AI_CHAT.items())[0]
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; color: #e0e0e0; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 700px; width: 100%; padding: 12px; height: 100vh; display: flex; flex-direction: column; }
        .header { display: flex; align-items: center; gap: 10px; padding: 8px 0; flex-shrink: 0; }
        .header h1 { font-size: 20px; color: #e94560; }
        .header a { color: #888; text-decoration: none; font-size: 14px; margin-left: auto; }
        .char-bar { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #16213e; border: 1px solid #0f3460; border-radius: 10px; margin-bottom: 10px; flex-shrink: 0; }
        .char-bar .avatar { font-size: 28px; }
        .char-bar .info { flex: 1; }
        .char-bar .info .name { font-size: 15px; font-weight: 600; }
        .char-bar .info .hint { font-size: 12px; color: #888; margin-top: 2px; }
        .chat-box { flex: 1; overflow-y: auto; padding: 14px; background: #0a1628; border-radius: 12px; margin-bottom: 10px; display: flex; flex-direction: column; gap: 10px; }
        .msg { display: flex; flex-direction: column; }
        .msg-user { align-items: flex-end; }
        .msg-bot { align-items: flex-start; }
        .msg-label { font-size: 11px; color: #666; margin-bottom: 3px; }
        .msg-text { padding: 10px 14px; border-radius: 14px; max-width: 85%; font-size: 15px; line-height: 1.45; }
        .msg-user .msg-text { background: #e94560; color: white; border-bottom-right-radius: 4px; }
        .msg-bot .msg-text { background: #16213e; color: #e0e0e0; border-bottom-left-radius: 4px; }
        .controls { display: flex; gap: 8px; flex-shrink: 0; padding-bottom: 12px; }
        .controls select { width: 160px; flex-shrink: 0; padding: 12px; background: #0f3460; border: 1px solid #1a5276; border-radius: 10px; font-size: 15px; color: #e0e0e0; }
        .controls input { flex: 1; padding: 12px 16px; background: #0f3460; border: 1px solid #1a5276; border-radius: 10px; font-size: 15px; color: #e0e0e0; }
        .controls input:focus, .controls select:focus { outline: none; border-color: #e94560; }
        .controls button { padding: 12px 20px; background: #e94560; color: white; border: none; border-radius: 10px; cursor: pointer; font-size: 15px; font-weight: 600; flex-shrink: 0; }
        .controls button:hover { background: #d63851; }
        .controls .upload-btn { background: #0f3460; color: #e0e0e0; font-size: 18px; padding: 12px 14px; }
        .controls .upload-btn:hover { background: #1a5276; }
        .msg img.msg-img { max-width: 85%; max-height: 300px; border-radius: 12px; margin-top: 8px; display: block; }
        .file-chip { display: inline-flex; align-items: center; gap: 6px; background: #0f3460; border: 1px solid #1a5276; border-radius: 8px; padding: 4px 10px; margin-right: 6px; font-size: 12px; color: #aaa; }
        .file-chip b { color: #e0e0e0; font-weight: 500; }
        .loading { text-align: center; color: #888; padding: 16px; font-size: 14px; }
        .welcome { text-align: center; color: #555; padding: 40px 20px; font-size: 14px; line-height: 1.6; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #0f3460; border-radius: 3px; }
        @media (max-width: 600px) { .controls select { width: 100px; } .container { padding: 8px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>AI Chat</h1>
        <a href="/">Назад</a>
    </div>
    <div class="char-bar" id="char-bar">
        <div class="avatar" id="char-avatar">__CHAR_AVATAR__</div>
        <div class="info">
            <div class="name" id="char-name">__CHAR_NAME__</div>
            <div class="hint" id="char-hint">__CHAR_HINT__</div>
        </div>
    </div>
    <div class="chat-box" id="chat-box">
        <div class="welcome" id="welcome-msg">Напишите сообщение, чтобы начать диалог с персонажем</div>
    </div>
    <div class="controls">
        <select id="char-select" onchange="updateCharInfo()">__CHR_SEL__</select>
        <input id="msg-input" type="text" placeholder="Сообщение..." autofocus>
        <button class="upload-btn" id="upload-btn" title="Загрузить файл">📎</button>
        <input type="file" id="file-input" multiple style="display:none">
        <button id="send-btn">Отправить</button>
    </div>
    <div id="upload-bar" style="display:none;padding:4px 2px 8px;"></div>
</div>
<script>
var CHARS = __CHARS_JSON__;
    var CHARS_INFO = __CHARS_INFO__;
    var chatBox = document.getElementById('chat-box');
    var charSelect = document.getElementById('char-select');
    var msgInput = document.getElementById('msg-input');
    var welcomeMsg = document.getElementById('welcome-msg');
    var chatHistory = [];
    var pendingFiles = [];
    var USER_ID = localStorage.getItem('ai_user_id');
    if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ai_user_id', USER_ID); }

    function updateCharInfo() {
        var key = charSelect.value;
        var info = CHARS_INFO[key];
        document.getElementById('char-avatar').textContent = info.emoji || '?';
        document.getElementById('char-name').textContent = info.name || '?';
        document.getElementById('char-hint').textContent = info.hint || '';
    }

    function renderUploads() {
        var bar = document.getElementById('upload-bar');
        if (!pendingFiles.length) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
        bar.style.display = 'block';
        bar.innerHTML = '';
        pendingFiles.forEach(function(f, i) {
            var chip = document.createElement('span');
            chip.className = 'file-chip';
            chip.innerHTML = '<b>' + f.name + '</b> ' + Math.round(f.size / 1024) + ' КБ <a href="#" onclick="removeFile(' + i + ');return false;" style="color:#e94560;text-decoration:none">✕</a>';
            bar.appendChild(chip);
        });
    }

    function removeFile(i) { pendingFiles.splice(i, 1); renderUploads(); }

    document.getElementById('upload-btn').addEventListener('click', function() {
        document.getElementById('file-input').click();
    });
    document.getElementById('file-input').addEventListener('change', function() {
        var files = Array.prototype.slice.call(this.files);
        var total = pendingFiles.length;
        files.forEach(function(f, idx) {
            if (!/^(image|text|application\/json|application\/javascript|application\/octet-stream)/.test(f.type) && !/\.(py|js|ts|json|txt|md|html|css|cpp|java|go|rs|sql)$/i.test(f.name)) return;
            if (pendingFiles.length >= 4) return;
            var reader = new FileReader();
            reader.onload = function(e) {
                var b64 = e.target.result.split(',')[1];
                pendingFiles.push({name: f.name, data: b64, size: f.size, type: f.type});
                renderUploads();
            };
            reader.readAsDataURL(f);
        });
        this.value = '';
    });

    function addMsg(role, text, images) {
        if (welcomeMsg) welcomeMsg.style.display = 'none';
        var d = document.createElement('div');
        d.className = 'msg msg-' + role;
        var label = role === 'user' ? 'Вы' : CHARS[charSelect.value].name;
        var html = '<div class="msg-label">' + label + '</div><div class="msg-text">' + (text || '').replace(/</g, '<') + '</div>';
        if (images && images.length) {
            images.forEach(function(src) {
                html += '<img class="msg-img" src="' + src + '" alt="Результат">';
            });
        }
        d.innerHTML = html;
        chatBox.appendChild(d);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function sendMsg() {
        var text = msgInput.value.trim();
        if (!text && !pendingFiles.length) return;
        if (pendingFiles.length) { text = text || 'Посмотри, что я загрузил.'; }
        addMsg('user', text);
        msgInput.value = '';
        msgInput.disabled = true;
        var filesPayload = pendingFiles.slice();
        pendingFiles = [];
        renderUploads();
        var loadEl = document.createElement('div');
        loadEl.className = 'loading';
        loadEl.id = 'loading';
        loadEl.textContent = CHARS[charSelect.value].emoji + ' ' + CHARS[charSelect.value].name + ' думает...';
        chatBox.appendChild(loadEl);
        chatBox.scrollTop = chatBox.scrollHeight;
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/ai_chat');
        xhr.setRequestHeader('Content-Type', 'application/json');
xhr.onload = function() {
            var loadEl = document.getElementById('loading');
            if (loadEl) loadEl.remove();
            msgInput.disabled = false;
            msgInput.focus();
            try {
                var r = JSON.parse(xhr.responseText);
                if (!r || typeof r !== 'object') {
                    console.error('AI Chat: invalid response', xhr.responseText);
                    addMsg('bot', 'Ошибка ответа: неверный формат');
                    return;
                }
                if (r.error) { addMsg('bot', 'Ошибка: ' + r.error); return; }
                var reply = typeof r.reply === 'string' ? r.reply : String(r.reply ?? '');
                var images = Array.isArray(r.images) ? r.images : [];
                addMsg('bot', reply, images);
                history.push({role: 'user', content: text});
                history.push({role: 'assistant', content: reply});
                if (history.length > 20) history = history.slice(-20);
            } catch(e) {
                console.error('AI Chat: parse error', e, xhr.responseText);
                addMsg('bot', 'Ошибка ответа.');
            }
        };
        xhr.onerror = function() {
            var loadEl = document.getElementById('loading');
            if (loadEl) loadEl.remove();
            msgInput.disabled = false;
            addMsg('bot', 'Ошибка сети.');
        };
        xhr.send(JSON.stringify({character: charSelect.value, message: text, user_id: USER_ID, history: chatHistory, files: filesPayload}));
    }

    document.getElementById('send-btn').addEventListener('click', sendMsg);
    document.getElementById('msg-input').addEventListener('keydown', function(e) { if (e.key === 'Enter') sendMsg(); });
    updateCharInfo();
</script>
</body>
</html>"""
    html = html.replace("__CHR_SEL__", opts).replace("__CHARS_JSON__", chars_json).replace("__CHARS_INFO__", chars_info_json)
    html = html.replace("__CHAR_AVATAR__", first_char[1]["emoji"]).replace("__CHAR_NAME__", first_char[1]["name"])
    first_hint = first_char[1]["prompt"].split(".")[1].strip() if "." in first_char[1]["prompt"] else first_char[1]["prompt"][:60]
    html = html.replace("__CHAR_HINT__", first_hint)
    return html


@app.route("/api/ai_chat", methods=["POST"])
def api_ai_chat():
    try:
        data = request.get_json(silent=True) or {}
        character = data.get("character", "olegov")
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "Введите сообщение"}), 400
        char_data = CHARACTER_PROMPTS_AI_CHAT.get(character)
        if not char_data:
            return jsonify({"error": "Персонаж не найден"}), 400

        user_id = str(data.get("user_id") or "anon")
        messages = data.get("history") or []
        state = _pc_state(user_id)

        uploads = data.get("files") or []
        saved_files = []
        for f in uploads[:4]:
            fname = re.sub(r"[^A-Za-z0-9._-]", "_", (f.get("name") or "file.bin"))[:80]
            raw = f.get("data") or ""
            try:
                raw_bytes = base64.b64decode(raw)
            except Exception:
                raw_bytes = raw.encode()
            fpath = _pc_resolve("/home/user/uploads/" + fname, state)
            parts = fpath.strip("/").split("/")
            node = state["fs"]["/"]
            for part in parts[:-1]:
                node = node["children"].setdefault(part, {"type": "dir", "children": {}})
            node["children"][parts[-1]] = {"type": "file", "content": "", "data": raw_bytes}
            if fpath not in state["uploads"]:
                state["uploads"].append(fpath)
            saved_files.append(fpath)

        if saved_files:
            sizes = []
            for p in saved_files:
                node = _pc_lookup(state, p)
                n = len(node.get("data") or b"") if node else 0
                sizes.append(f"- {p} ({n} байт)")
            note = (
                "Пользователь загрузил файлы. Они сохранены на виртуальный компьютер:\n"
                + "\n".join(sizes)
                + "\n\nПосмотри их (read_file), и если это картинка — обработай по просьбе пользователя."
            )
            messages = [{"role": "user", "content": note}] + (messages or [])

        result = _pc_ai_chat(user_id, character, messages + [{"role": "user", "content": message}])
        # Ensure reply is always a string
        if not isinstance(result.get("reply"), str):
            result["reply"] = str(result.get("reply", ""))
        if not isinstance(result.get("images"), list):
            result["images"] = []
        return jsonify(result)
    except Exception as exc:
        print(f"API ai_chat error: {exc}")
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"❌ Внутренняя ошибка сервера: {exc}", "images": []}), 500


# ===== Chess =====

@app.route("/chess")
def chess_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Шахматы — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; color: #e0e0e0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 640px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: #e94560; }
        .header a { color: #888; text-decoration: none; font-size: 14px; margin-left: auto; }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { flex: 1; min-width: 140px; padding: 12px; background: #16213e; border: 1px solid #0f3460; border-radius: 12px; color: #aaa; font-size: 14px; cursor: pointer; text-align: center; transition: all 0.15s; }
        .tab.active { background: #e94560; color: white; border-color: #e94560; }
        .tab:hover { background: #1a5276; }
        .panel { display: none; }
        .panel.active { display: block; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 16px; padding: 24px; margin-bottom: 16px; }
        .card h3 { font-size: 16px; color: #e94560; margin-bottom: 14px; }
        .stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f3460; font-size: 14px; }
        .stat-row:last-child { border-bottom: none; }
        .stat-row .label { color: #888; }
        .stat-row .value { color: #e0e0e0; font-weight: 600; }
        .input-group { display: flex; gap: 8px; margin-bottom: 16px; }
        input[type="text"] { flex: 1; padding: 12px 14px; background: #0f3460; border: 1px solid #1a5276; border-radius: 10px; color: #e0e0e0; font-size: 15px; }
        input[type="text"]::placeholder { color: #666; }
        .btn { padding: 12px 18px; background: #e94560; color: white; border: none; border-radius: 10px; font-size: 14px; cursor: pointer; transition: background 0.15s; white-space: nowrap; }
        .btn:hover { background: #d63851; }
        .btn.secondary { background: #0f3460; color: #e0e0e0; border: 1px solid #1a5276; }
        .btn.secondary:hover { background: #1a5276; }
        .btn:disabled { opacity: 0.5; cursor: default; }
        .msg { padding: 14px 16px; border-radius: 10px; margin: 12px 0; font-size: 14px; line-height: 1.5; }
        .msg.ok { background: #1b5e20; border: 1px solid #2e7d32; }
        .msg.err { background: #b71c1c; border: 1px solid #c62828; }
        .msg.info { background: #0f3460; border: 1px solid #1a5276; }
        .board { display: block; width: 100%; max-width: 360px; margin: 0 auto 16px; border-radius: 8px; }
        .puzzle-meta { text-align: center; margin-bottom: 14px; color: #aaa; font-size: 13px; line-height: 1.7; }
        .coins { display: inline-block; background: #ffd70033; color: #ffd700; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 14px; }
        .history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f3460; font-size: 13px; color: #aaa; }
        .history-item:last-child { border-bottom: none; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        .badge.online { background: #1b5e20; color: #7ef29d; }
        .badge.offline { background: #37474f; color: #90a4ae; }
        .spinner { text-align: center; color: #888; padding: 24px 0; font-size: 14px; }
        @media (max-width: 600px) { .card { padding: 18px; } .tab { min-width: 100px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>♟ Шахматы</h1>
        <a href="/">← На главную</a>
    </div>
    <div class="tabs">
        <button class="tab active" data-tab="stats">📊 Моя статистика</button>
        <button class="tab" data-tab="search">🔍 Поиск игрока</button>
        <button class="tab" data-tab="puzzle">🧩 Пазл</button>
    </div>

    <div id="panel-stats" class="panel active"></div>
    <div id="panel-search" class="panel">
        <div class="card">
            <h3>Найти игрока на Lichess</h3>
            <div class="input-group">
                <input type="text" id="search-input" placeholder="Ник на Lichess...">
                <button class="btn" id="search-btn">Поиск</button>
            </div>
            <div id="search-result"></div>
        </div>
    </div>
    <div id="panel-puzzle" class="panel"></div>
</div>
<script>
(function() {
    var USER_ID = localStorage.getItem('chess_user_id');
    if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('chess_user_id', USER_ID); }

    var tabs = document.querySelectorAll('.tab');
    var panels = { stats: document.getElementById('panel-stats'), search: document.getElementById('panel-search'), puzzle: document.getElementById('panel-puzzle') };
    tabs.forEach(function(t) {
        t.addEventListener('click', function() {
            tabs.forEach(function(x) { x.classList.remove('active'); });
            t.classList.add('active');
            Object.keys(panels).forEach(function(k) { panels[k].classList.remove('active'); });
            panels[t.dataset.tab].classList.add('active');
        });
    });

    function esc(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/[&<>"']/g, function(c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; });
    }

    function loadStats() {
        panels.stats.innerHTML = '<div class="spinner">Загрузка статистики...</div>';
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/chess/stats?user_id=' + encodeURIComponent(USER_ID));
        xhr.onload = function() {
            if (xhr.status === 200) {
                var d = JSON.parse(xhr.responseText);
                renderStats(d);
            } else {
                panels.stats.innerHTML = '<div class="msg err">Ошибка загрузки статистики.</div>';
            }
        };
        xhr.onerror = function() { panels.stats.innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
        xhr.send();
    }

    function renderStats(d) {
        var html = '';
        if (d.coins !== undefined) {
            html += '<div style="text-align:center;"><span class="coins">💰 Баланс: ' + esc(d.coins) + ' монет</span></div>';
        }
        if (d.linked) {
            html += '<div class="card"><h3>🎮 Привязанный аккаунт</h3>' +
                '<div class="stat-row"><span class="label">Lichess</span><span class="value">' + esc(d.account.username) + '</span></div>' +
                '<div class="stat-row"><span class="label">Статус</span><span class="value"><span class="badge ' + (d.player.online ? 'online' : 'offline') + '">' + (d.player.online ? '🟢 онлайн' : '⚫ оффлайн') + '</span></span></div>' +
                '</div>';
            html += '<div class="card"><h3>📈 Рейтинги</h3>';
            var perfs = d.player.perfs || {};
            var ratingOrder = [['bullet','🎯 Пуля'], ['blitz','⚡ Блиц'], ['rapid','⏱️ Рапид'], ['classical','⏳ Классика']];
            var hasRating = false;
            ratingOrder.forEach(function(p) {
                var k = p[0];
                if (perfs[k]) {
                    hasRating = true;
                    html += '<div class="stat-row"><span class="label">' + p[1] + '</span><span class="value">' + esc(perfs[k].rating) + ' <span style="color:#888;font-weight:400;">(' + esc(perfs[k].games) + ' игр)</span></span></div>';
                }
            });
            if (!hasRating) html += '<div class="stat-row"><span class="label">Нет данных</span></div>';
            html += '</div>';
            var g = d.player.games || {};
            if (g.total > 0) {
                html += '<div class="card"><h3>🎯 Статистика игр</h3>' +
                    '<div class="stat-row"><span class="label">Всего игр</span><span class="value">' + esc(g.total) + '</span></div>' +
                    '<div class="stat-row"><span class="label">✅ Победы</span><span class="value">' + esc(g.win) + ' (' + esc(d.winrate) + '%)</span></div>' +
                    '<div class="stat-row"><span class="label">❌ Поражения</span><span class="value">' + esc(g.loss) + '</span></div>' +
                    '<div class="stat-row"><span class="label">🤝 Ничьи</span><span class="value">' + esc(g.draw) + '</span></div>' +
                    '</div>';
            }
            if (d.history && d.history.length) {
                html += '<div class="card"><h3>📜 История пазлов</h3>';
                d.history.forEach(function(h) {
                    html += '<div class="history-item"><span>🧩 ' + esc(h.puzzle_id) + '</span><span>' + esc(h.rating) + '</span></div>';
                });
                html += '</div>';
            }
        } else {
            html += '<div class="card"><h3>Привязка Lichess аккаунта</h3>' +
                '<div class="msg info">Свяжите ваш аккаунт Lichess, чтобы видеть рейтинги и решать пазлы с начислением монет.</div>' +
                '<div class="input-group"><input type="text" id="link-input" placeholder="Ник на Lichess..."><button class="btn" id="link-btn">Привязать</button></div>' +
                '<div id="link-msg"></div></div>';
        }
        panels.stats.innerHTML = html;
        var linkBtn = document.getElementById('link-btn');
        if (linkBtn) {
            linkBtn.addEventListener('click', function() {
                var nick = (document.getElementById('link-input').value || '').trim();
                if (!nick) { document.getElementById('link-msg').innerHTML = '<div class="msg err">Введите ник.</div>'; return; }
                linkBtn.disabled = true;
                var x = new XMLHttpRequest();
                x.open('POST', '/api/chess/link');
                x.setRequestHeader('Content-Type', 'application/json');
                x.onload = function() {
                    linkBtn.disabled = false;
                    var r;
                    try { r = JSON.parse(x.responseText); } catch(e) { r = {}; }
                    if (x.status === 200 && r.ok) {
                        document.getElementById('link-msg').innerHTML = '<div class="msg ok">✅ Аккаунт привязан!</div>';
                        loadStats();
                    } else {
                        document.getElementById('link-msg').innerHTML = '<div class="msg err">' + esc(r.error || 'Не удалось привязать аккаунт.') + '</div>';
                    }
                };
                x.onerror = function() { linkBtn.disabled = false; document.getElementById('link-msg').innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
                x.send(JSON.stringify({user_id: USER_ID, lichess_username: nick}));
            });
        }
    }

    var searchBtn = document.getElementById('search-btn');
    searchBtn.addEventListener('click', function() {
        var nick = (document.getElementById('search-input').value || '').trim();
        var result = document.getElementById('search-result');
        if (!nick) { result.innerHTML = '<div class="msg err">Введите ник.</div>'; return; }
        result.innerHTML = '<div class="spinner">Поиск...</div>';
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/chess/user/' + encodeURIComponent(nick));
        xhr.onload = function() {
            if (xhr.status === 200) {
                var d = JSON.parse(xhr.responseText);
                var html = '<div class="card"><h3>' + esc(d.username) + '</h3>' +
                    '<div class="stat-row"><span class="label">Статус</span><span class="value"><span class="badge ' + (d.online ? 'online' : 'offline') + '">' + (d.online ? '🟢 онлайн' : '⚫ оффлайн') + '</span></span></div>';
                var perfs = d.perfs || {};
                var ratingOrder = [['bullet','🎯 Пуля'], ['blitz','⚡ Блиц'], ['rapid','⏱️ Рапид'], ['classical','⏳ Классика']];
                ratingOrder.forEach(function(p) {
                    if (perfs[p[0]]) html += '<div class="stat-row"><span class="label">' + p[1] + '</span><span class="value">' + esc(perfs[p[0]].rating) + ' (' + esc(perfs[p[0]].games) + ')</span></div>';
                });
                var g = d.games || {};
                if (g.total > 0) html += '<div class="stat-row"><span class="label">Всего игр</span><span class="value">' + esc(g.total) + ' (✅' + esc(g.win) + ' ❌' + esc(g.loss) + ' 🤝' + esc(g.draw) + ')</span></div>';
                html += '</div>';
                result.innerHTML = html;
            } else {
                var r;
                try { r = JSON.parse(xhr.responseText); } catch(e) { r = {}; }
                result.innerHTML = '<div class="msg err">' + esc(r.error || 'Игрок не найден.') + '</div>';
            }
        };
        xhr.onerror = function() { result.innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
        xhr.send();
    });

    function loadPuzzle() {
        panels.puzzle.innerHTML = '<div class="spinner">Загружаю задачу...</div>';
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/chess/puzzle');
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onload = function() {
            if (xhr.status === 200) {
                var d = JSON.parse(xhr.responseText);
                renderPuzzle(d);
            } else {
                var r;
                try { r = JSON.parse(xhr.responseText); } catch(e) { r = {}; }
                panels.puzzle.innerHTML = '<div class="msg err">' + esc(r.error || 'Ошибка загрузки задачи.') + '</div>';
            }
        };
        xhr.onerror = function() { panels.puzzle.innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
        xhr.send(JSON.stringify({user_id: USER_ID}));
    }

    function renderPuzzle(d) {
        var html = '<div class="card"><h3>🧩 Шахматная задача</h3>' +
            '<img class="board" src="https://lichess1.org/export/fen.gif?fen=' + encodeURIComponent(d.fen).replace(/%20/g, '_').replace(/%2F/g, '/').replace(/%2B/g, '+') + '&theme=brown&piece=cburnett" alt="Доска">' +
            '<div class="puzzle-meta">Рейтинг: ' + esc(d.rating) + ' · Темы: ' + esc(d.themes) + '<br>Ход: ' + esc(d.turn) + '</div>' +
            '<div class="input-group"><input type="text" id="move-input" placeholder="Ход в формате UCI (например e2e4)..." autocomplete="off"><button class="btn" id="check-btn">Проверить</button></div>' +
            '<div id="puzzle-msg"></div></div>' +
            '<div style="text-align:center;"><a href="' + esc(d.link) + '" target="_blank" class="btn secondary" style="text-decoration:none;">Открыть на Lichess</a></div>' +
            '<div style="text-align:center; margin-top:12px;"><button class="btn" id="next-puzzle">Следующая задача</button></div>';
        panels.puzzle.innerHTML = html;
        var checkBtn = document.getElementById('check-btn');
        var moveInput = document.getElementById('move-input');
        function checkMove() {
            var move = (moveInput.value || '').trim().toLowerCase();
            var msg = document.getElementById('puzzle-msg');
            if (!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(move)) { msg.innerHTML = '<div class="msg err">Неверный формат хода. Например: e2e4</div>'; return; }
            checkBtn.disabled = true;
            var x = new XMLHttpRequest();
            x.open('POST', '/api/chess/puzzle/check');
            x.setRequestHeader('Content-Type', 'application/json');
            x.onload = function() {
                checkBtn.disabled = false;
                var r = JSON.parse(x.responseText);
                if (r.correct) {
                    msg.innerHTML = '<div class="msg ok">✅ Правильно! Ход: ' + esc(r.move) + '<br>💰 +5 монет</div>';
                } else {
                    msg.innerHTML = '<div class="msg err">❌ Неверно. Правильный ход: ' + esc(r.move) + '</div>';
                }
            };
            x.onerror = function() { checkBtn.disabled = false; msg.innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
            x.send(JSON.stringify({user_id: USER_ID, move: move}));
        }
        checkBtn.addEventListener('click', checkMove);
        moveInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') checkMove(); });
        document.getElementById('next-puzzle').addEventListener('click', loadPuzzle);
    }

    tabs.forEach(function(t) {
        t.addEventListener('click', function() {
            if (t.dataset.tab === 'stats') loadStats();
            if (t.dataset.tab === 'puzzle') loadPuzzle();
        });
    });
    loadStats();
})();
</script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/chess/stats")
def api_chess_stats():
    user_id_raw = request.args.get("user_id", "")
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _web_user_id(user_id_raw)
    account = get_chess_account(uid)
    coins = get_user_coins(uid)
    result = {
        "linked": bool(account),
        "coins": (coins or {}).get("balance", 0),
    }
    if account:
        player = fetch_lichess_user(account["lichess_username"])
        result["account"] = account
        result["player"] = player or {"username": account["lichess_username"], "online": False, "perfs": {}, "games": {}}
        games = result["player"].get("games", {})
        total = games.get("total", 0)
        win = games.get("win", 0)
        result["winrate"] = round((win / total * 100), 1) if total > 0 else 0
        history = []
        try:
            with get_db_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT puzzle_id, puzzle_rating FROM chess_games WHERE user_id = :uid ORDER BY id DESC LIMIT 10"),
                    {"uid": uid},
                ).mappings().all()
                history = [{"puzzle_id": r["puzzle_id"], "rating": r["puzzle_rating"]} for r in rows]
        except Exception as exc:
            print(f"Error loading chess history: {exc}")
        result["history"] = history
    return jsonify(result)


@app.route("/api/chess/user/<nick>")
def api_chess_user(nick: str):
    data = fetch_lichess_user(nick)
    if not data:
        return jsonify({"error": "Игрок не найден на Lichess"}), 404
    return jsonify(data)


@app.route("/api/chess/link", methods=["POST"])
def api_chess_link():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    nick = (data.get("lichess_username") or "").strip()
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    if not nick:
        return jsonify({"error": "Введите ник Lichess"}), 400
    uid = _web_user_id(user_id_raw)
    profile = fetch_lichess_user(nick)
    if not profile:
        return jsonify({"error": "Игрок не найден на Lichess"}), 404
    ok = link_chess_account(uid, profile["username"])
    if not ok:
        return jsonify({"error": "Этот Lichess аккаунт уже привязан к другому пользователю"}), 409
    return jsonify({"ok": True, "username": profile["username"]})


@app.route("/api/chess/puzzle", methods=["POST"])
def api_chess_puzzle():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _web_user_id(user_id_raw)
    account = get_chess_account(uid)
    if not account:
        return jsonify({"error": "Сначала привяжите Lichess аккаунт в разделе «Моя статистика»"}), 400
    puzzle = _fetch_lichess_puzzle()
    if not puzzle:
        return jsonify({"error": "Не удалось загрузить задачу. Попробуйте позже."}), 502
    _PENDING_PUZZLES[uid] = {
        "puzzle_id": puzzle["puzzle_id"],
        "solution": puzzle["solution"],
        "rating": puzzle["rating"],
        "themes": ", ".join(puzzle["themes"][:3]),
        "username": account["lichess_username"],
        "initial_ply": puzzle["initial_ply"],
        "web": True,
    }
    return jsonify({
        "puzzle_id": puzzle["puzzle_id"],
        "rating": puzzle["rating"],
        "themes": ", ".join(puzzle["themes"][:3]),
        "fen": puzzle["fen"],
        "turn": puzzle["turn"],
        "link": puzzle["link"],
    })


@app.route("/api/chess/puzzle/check", methods=["POST"])
def api_chess_puzzle_check():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    move = (data.get("move") or "").strip().lower()
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _web_user_id(user_id_raw)
    pending = _PENDING_PUZZLES.get(uid)
    if not pending or not pending.get("web"):
        return jsonify({"error": "Задача не найдена или устарела. Загрузите новую."}), 400
    if not move or not pending["solution"]:
        return jsonify({"error": "Некорректный ход"}), 400
    first_move = pending["solution"][0]
    correct = move == first_move
    if correct:
        try:
            update_user_coins(uid, 5, datetime.utcnow())
        except Exception as exc:
            print(f"Error awarding coins: {exc}")
        log_chess_game(uid, pending.get("username", ""), pending["puzzle_id"], pending.get("rating"), pending.get("themes"))
    del _PENDING_PUZZLES[uid]
    return jsonify({"correct": correct, "move": first_move})


# ===== Trivia =====

@app.route("/trivia")
def trivia_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Викторина — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; color: #e0e0e0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 640px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: #e94560; }
        .header a { color: #888; text-decoration: none; font-size: 14px; margin-left: auto; }
        .score { text-align: center; color: #888; font-size: 14px; margin-bottom: 16px; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 16px; padding: 28px; margin-bottom: 16px; }
        .question { font-size: 18px; line-height: 1.6; margin-bottom: 24px; }
        .options { display: flex; flex-direction: column; gap: 10px; }
        .opt-btn { display: block; width: 100%; padding: 14px 18px; background: #0f3460; color: #e0e0e0; border: 1px solid #1a5276; border-radius: 12px; font-size: 15px; cursor: pointer; text-align: left; transition: all 0.15s; }
        .opt-btn:hover:not(:disabled) { background: #1a5276; }
        .opt-btn:disabled { cursor: default; opacity: 0.8; }
        .opt-btn.correct { background: #1b5e20; border-color: #2e7d32; }
        .opt-btn.wrong { background: #b71c1c; border-color: #c62828; }
        .explanation { background: #0f3460; border-radius: 12px; padding: 16px; margin-top: 16px; font-size: 14px; line-height: 1.5; color: #aaa; display: none; }
        .next-btn { display: none; width: 100%; padding: 14px; background: #e94560; color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-top: 16px; }
        .next-btn:hover { background: #d63851; }
        .status { text-align: center; color: #888; margin-top: 24px; font-size: 13px; }
        @media (max-width: 600px) { .card { padding: 20px; } .question { font-size: 16px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Викторина</h1>
            <a href="/">← Назад</a>
        </div>
        <div class="score" id="score">0 / 0</div>
        <div class="card" id="quiz-card">
            <div class="question" id="question"></div>
            <div class="options" id="options"></div>
            <div class="explanation" id="explanation"></div>
            <button class="next-btn" id="next-btn">Следующий вопрос →</button>
        </div>
        <div class="status">по канону Олеговируса и LTL-паразита</div>
    </div>
    <script>
        (function() {
            var score = 0, total = 0;
            (function() {
                var s = localStorage.getItem('trivia_score');
                if (s) { var p = s.split('/'); score = parseInt(p[0]) || 0; total = parseInt(p[1]) || 0; }
            })();
            function saveScore() { localStorage.setItem('trivia_score', score + '/' + total); }
            function updateScore() { document.getElementById('score').textContent = score + ' / ' + total; }
            updateScore();
            function loadQuestion() {
                document.getElementById('explanation').style.display = 'none';
                document.getElementById('next-btn').style.display = 'none';
                document.getElementById('question').textContent = '\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...';
                document.getElementById('options').innerHTML = '';
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/trivia/question');
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onload = function() {
                    try {
                        var q = JSON.parse(xhr.responseText);
                        if (q.error) { document.getElementById('question').textContent = '\u041e\u0448\u0438\u0431\u043a\u0430: ' + q.error; return; }
                        document.getElementById('question').textContent = q.text;
                        var opts = document.getElementById('options');
                        opts.innerHTML = '';
                        q.options.forEach(function(opt, i) {
                            var btn = document.createElement('button');
                            btn.className = 'opt-btn';
                            btn.textContent = opt;
                            btn.dataset.index = i;
                            btn.dataset.correct = (i === q.correct_index) ? '1' : '0';
                            btn.addEventListener('click', function() { answerClick(q.id, i); });
                            opts.appendChild(btn);
                        });
                    } catch(e) { document.getElementById('question').textContent = '\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 \u0432\u043e\u043f\u0440\u043e\u0441\u0430.'; }
                };
                xhr.onerror = function() { document.getElementById('question').textContent = '\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0442\u0438.'; };
                xhr.send(JSON.stringify({}));
            }
            function answerClick(qid, idx) {
                var btns = document.querySelectorAll('.opt-btn');
                btns.forEach(function(b) { b.disabled = true; });
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/trivia/answer');
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onload = function() {
                    try {
                        var r = JSON.parse(xhr.responseText);
                        btns.forEach(function(b) {
                            if (b.dataset.correct === '1') b.classList.add('correct');
                            else if (parseInt(b.dataset.index) === idx && !r.correct) b.classList.add('wrong');
                        });
                        if (r.correct) { score++; }
                        total++;
                        saveScore();
                        updateScore();
                        var expl = document.getElementById('explanation');
                        expl.textContent = r.explanation;
                        expl.style.display = 'block';
                        document.getElementById('next-btn').style.display = 'block';
                    } catch(e) { btns.forEach(function(b) { b.disabled = false; }); }
                };
                xhr.onerror = function() { btns.forEach(function(b) { b.disabled = false; }); };
                xhr.send(JSON.stringify({question_id: qid, answer_index: idx}));
            }
            document.getElementById('next-btn').addEventListener('click', loadQuestion);
            loadQuestion();
        })();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/trivia/question", methods=["POST"])
def api_trivia_question():
    import random
    q = random.choice(_TRIVIA_QUESTIONS)
    correct = q["correct_text"]
    group = q.get("group", "")
    same = [x["correct_text"] for x in _TRIVIA_QUESTIONS if x.get("group") == group and x["correct_text"] != correct]
    pool = same if len(same) >= 3 else [x["correct_text"] for x in _TRIVIA_QUESTIONS if x["correct_text"] != correct]
    distractors = random.sample(pool, 3)
    options = [correct] + distractors
    random.shuffle(options)
    correct_index = options.index(correct)
    session = {"options": options, "correct_index": correct_index, "explanation": q["explanation"]}
    _TRIVIA_SESSIONS[q["id"]] = session
    return jsonify({"id": q["id"], "text": q["text"], "options": options, "correct_index": correct_index})


@app.route("/api/trivia/answer", methods=["POST"])
def api_trivia_answer():
    data = request.get_json(silent=True) or {}
    qid = data.get("question_id")
    answer_idx = data.get("answer_index")
    session = _TRIVIA_SESSIONS.get(qid)
    if not session:
        return jsonify({"correct": False, "correct_text": "", "explanation": "Вопрос не найден или устарел."})
    correct_index = session["correct_index"]
    is_correct = answer_idx is not None and 0 <= answer_idx < 4 and answer_idx == correct_index
    correct_text = session["options"][correct_index] if is_correct else session["options"][answer_idx] if answer_idx is not None and 0 <= answer_idx < 4 else ""
    return jsonify({"correct": is_correct, "correct_text": correct_text, "explanation": session["explanation"]})


# ── Daily Prayer ──────────────────────────────────────────────────────────

_PRAYERS = [
    "Да будет настрой стабилен, а пинг — нулевым.",
    "О Чай, дай нам мудрости в коде и терпения в дебаге.",
    "Да будет каждый день наполнен ароматом чая.",
    "Да будет моя душа чиста, как первозданный настой.",
    "Да будет кружка-алтарь моей рукой всегда наполнена.",
    "О Великий Баг, прости нам наши deprecated зависимости.",
    "Да будет деплой быстрым, а баги — редкими.",
    "Чай, чай, чай — да будет eight-nine с нами!",
    "Да будет CI зелёным, а код — без багов.",
    "О великий Компилятор, прости нам наши null pointer'ы.",
    "Да будет память чиста, а утечки — лишь в кране.",
    "Благослови, Чай, наш commit mesage — да будет он осмысленным.",
    "Да будет ревью снисходительным, а мерж — без конфликтов.",
    "О Eight-Nine, освяти наш спринт и убери technical debt.",
    "Да будет рефакторинг удачным, а тесты — зелёными.",
]


@app.route("/daily_prayer")
def daily_prayer_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Молитва — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; color: #e0e0e0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 500px; width: 100%; text-align: center; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; justify-content: center; }
        .header h1 { font-size: 22px; color: #e94560; }
        .header a { color: #888; text-decoration: none; font-size: 14px; margin-left: auto; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 16px; padding: 32px 24px; margin-bottom: 16px; }
        .prayer-icon { font-size: 64px; margin-bottom: 16px; }
        .prayer-text { font-size: 20px; line-height: 1.6; color: #f0e6d0; font-style: italic; margin: 20px 0; padding: 16px; border-left: 3px solid #e94560; text-align: left; }
        .prayer-amen { font-size: 16px; color: #e94560; margin-top: 12px; }
        .btn { display: inline-flex; align-items: center; gap: 8px; padding: 14px 32px; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .btn-primary { background: #e94560; color: #fff; }
        .btn-primary:hover { background: #d63851; }
        .btn-secondary { background: #0f3460; color: #e0e0e0; }
        .btn-secondary:hover { background: #1a5276; }
        .subtext { font-size: 14px; color: #888; margin-top: 16px; }
        .prayer-emoji { font-size: 48px; margin-bottom: 8px; }
        .cooldown-msg { font-size: 18px; color: #f0c040; margin: 20px 0; }
        .back-link { display: inline-block; color: #888; text-decoration: none; font-size: 14px; margin-top: 16px; }
        .back-link:hover { color: #e94560; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🙏 Молитва</h1>
            <a href="/">← На главную</a>
        </div>
        <div class="card" id="prayer-card">
            <div class="prayer-emoji" id="emoji">🕯️</div>
            <div id="prayer-content">
                <p style="color:#888;font-size:16px">Нажмите, чтобы получить молитву дня</p>
            </div>
            <button class="btn btn-primary" id="get-btn" onclick="getPrayer()">🙏 Получить молитву</button>
            <div class="subtext" id="subtext"></div>
        </div>
        <a class="back-link" href="/">← На главную</a>
    </div>
    <script>
        var USER_ID = localStorage.getItem('ai_user_id');
        if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ai_user_id', USER_ID); }
        function getPrayer() {
            var btn = document.getElementById('get-btn');
            btn.disabled = true;
            btn.textContent = '🙏 Загрузка...';
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/daily_prayer');
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { document.getElementById('prayer-content').innerHTML = '<p style="color:#e94560">'+r.error+'</p>'; btn.style.display='none'; return; }
                    document.getElementById('prayer-content').innerHTML = '<div class="prayer-text">"'+r.prayer+'"</div><div class="prayer-amen">eight-nine!</div>';
                    if (r.already) {
                        document.getElementById('subtext').textContent = 'Вы уже получали сегодняшнюю молитву. Возвращайтесь завтра!';
                        btn.style.display = 'none';
                    } else {
                        document.getElementById('subtext').textContent = 'Молитва на сегодня';
                        btn.textContent = '🙏 Ещё';
                        btn.disabled = false;
                    }
                } catch(e) { document.getElementById('prayer-content').innerHTML = '<p style="color:#e94560">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { document.getElementById('prayer-content').innerHTML = '<p style="color:#e94560">Ошибка сети.</p>'; };
            xhr.send(JSON.stringify({user_id: USER_ID}));
        }
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/daily_prayer", methods=["POST"])
def api_daily_prayer():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    uid = _web_user_id(user_id_raw)
    today = date.today().isoformat()
    already = False
    try:
        with get_db_engine().connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM daily_prayer_log WHERE user_id = :uid AND prayer_date = :d"),
                {"uid": uid, "d": today},
            ).first()
            if not existing:
                conn.execute(
                    text("INSERT INTO daily_prayer_log (user_id, prayer_date) VALUES (:uid, :d) ON CONFLICT DO NOTHING"),
                    {"uid": uid, "d": today},
                )
                conn.commit()
            else:
                already = True
    except Exception as exc:
        print(f"[DAILY_PRAYER] error: {exc}")
    prayer = random.choice(_PRAYERS)
    return jsonify({"prayer": prayer, "already": already})


# ── Irregular Verbs Module ──────────────────────────────────────────────
import re as _re


def _generate_verb_exercise(verbs: str, count: int, mode: int, wishes: str) -> list[dict] | None:
    prompt = (
        f"Ты — генератор заданий на неправильные глаголы английского языка.\n"
        f"Сгенерируй ровно {count} неправильных глаголов из списка: {verbs}\n"
        f"Для каждого глагола укажи ВСЕ ТРИ формы (infinitive, past simple, past participle).\n"
        f"Дополнительные пожелания: {wishes if wishes else 'нет'}\n\n"
        f"Формат ответа — строго JSON-массив, без пояснений и markdown:\n"
        f'[{{"inf": "...", "past": "...", "pp": "..."}}, ...]'
    )
    text = _call_ai_api_fast(prompt, max_tokens=2000, timeout=10.0)
    if not text or text == "❌":
        return None
    match = _re.search(r'\[.*\]', text, _re.DOTALL)
    if not match:
        return None
    try:
        import json as _json
        tasks = _json.loads(match.group())
        if not isinstance(tasks, list) or len(tasks) < 1:
            return None
        for t in tasks:
            t.setdefault("inf", "")
            t.setdefault("past", "")
            t.setdefault("pp", "")
        return tasks
    except Exception:
        return None


@app.route("/irregular_verbs")
def irregular_verbs_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Практика глаголов — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; min-height: 100vh; color: #e0e0e0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 700px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: #e94560; }
        .header a { color: #888; text-decoration: none; font-size: 14px; margin-left: auto; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 16px; padding: 24px; margin-bottom: 16px; }
        .card h2 { font-size: 18px; margin-bottom: 16px; }
        .role-card { display: block; padding: 20px; cursor: pointer; text-align: center; }
        .role-card:hover { border-color: #e94560; }
        .role-card .icon { font-size: 48px; margin-bottom: 8px; }
        .role-card .label { font-size: 18px; font-weight: 600; }
        .role-card .desc { font-size: 14px; color: #888; margin-top: 4px; }
        label { display: block; font-size: 14px; color: #aaa; margin-bottom: 4px; margin-top: 14px; }
        label:first-of-type { margin-top: 0; }
        input, textarea, select { width: 100%; padding: 12px; background: #0f3460; border: 1px solid #1a5276; border-radius: 8px; font-size: 15px; color: #e0e0e0; font-family: inherit; }
        input:focus, textarea:focus { outline: none; border-color: #e94560; }
        textarea { min-height: 60px; resize: vertical; }
        .radio-group { display: flex; gap: 16px; margin-top: 4px; }
        .radio-group label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #e0e0e0; cursor: pointer; margin: 0; }
        .btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .btn-primary { background: #e94560; color: white; }
        .btn-primary:hover { background: #d63851; }
        .btn-secondary { background: #0f3460; color: #e0e0e0; }
        .btn-secondary:hover { background: #1a5276; }
        .btn-full { width: 100%; justify-content: center; margin-top: 16px; }
        .btn-sm { padding: 8px 16px; font-size: 13px; }
        .verbs-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        .verbs-table th { text-align: left; padding: 10px 12px; font-size: 13px; color: #888; border-bottom: 1px solid #0f3460; text-transform: uppercase; letter-spacing: 0.5px; }
        .verbs-table td { padding: 10px 12px; border-bottom: 1px solid #0f3460; font-size: 15px; }
        .verbs-table input { background: transparent; border: none; border-bottom: 2px solid #1a5276; padding: 4px 0; font-size: 15px; color: #e0e0e0; width: 100%; border-radius: 0; }
        .verbs-table input:focus { border-bottom-color: #e94560; outline: none; }
        .verbs-table .filled { color: #4caf50; font-weight: 600; }
        .verbs-table .correct { color: #4caf50; }
        .verbs-table .wrong { color: #e94560; }
        .result-summary { text-align: center; padding: 20px; }
        .result-summary .score { font-size: 36px; color: #e94560; font-weight: bold; }
        .result-summary .label { font-size: 14px; color: #888; margin-top: 4px; }
        .back-link { display: inline-block; color: #888; text-decoration: none; font-size: 14px; margin-top: 16px; cursor: pointer; }
        .back-link:hover { color: #e94560; }
        .hidden { display: none; }
        .share-link { background: #0f3460; border-radius: 8px; padding: 12px; font-size: 14px; word-break: break-all; margin-top: 12px; display: flex; align-items: center; gap: 8px; }
        .share-link code { color: #4caf50; flex: 1; }
        .btn-copy { padding: 6px 12px; background: #e94560; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; white-space: nowrap; }
        .btn-copy:hover { background: #d63851; }
        .btn-copy.copied { background: #4caf50; }
        .ex-list { display: flex; flex-direction: column; gap: 10px; }
        .ex-item { display: flex; justify-content: space-between; align-items: center; padding: 14px; background: #0f3460; border-radius: 8px; cursor: pointer; }
        .ex-item:hover { background: #1a5276; }
        .ex-item .ex-id { font-weight: 600; color: #e94560; }
        .ex-item .ex-meta { font-size: 13px; color: #888; }
        .student-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #0f3460; }
        .student-row:last-child { border: none; }
        .student-name { font-weight: 600; }
        .student-score { color: #4caf50; }
        .error-text { color: #e94560; text-align: center; padding: 20px; }
        @media (max-width: 600px) {
            .container { padding: 0; }
            .card { padding: 16px; }
            .verbs-table td, .verbs-table th { padding: 8px; font-size: 14px; }
        }
    </style>
</head>
<body>
    <div class="container" id="app">
        <div class="header">
            <h1>📝 Практика глаголов</h1>
            <a href="/">← Назад</a>
        </div>
        <div id="content"></div>
    </div>
    <script>
        (function() {
            var USER_ID = localStorage.getItem('ai_user_id');
            if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('ai_user_id', USER_ID); }
            var studentName = localStorage.getItem('verbs_name') || '';
            var content = document.getElementById('content');

            function render(html) { content.innerHTML = html; }

            window.copyUrl = function(btn) {
                var url = btn.getAttribute('data-url');
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(url).then(function() {
                        btn.textContent = 'Copied!';
                        btn.className = 'btn-copy copied';
                        setTimeout(function() { btn.textContent = 'Copy'; btn.className = 'btn-copy'; }, 2000);
                    });
                } else {
                    var ta = document.createElement('textarea');
                    ta.value = url;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    btn.textContent = 'Copied!';
                    btn.className = 'btn-copy copied';
                    setTimeout(function() { btn.textContent = 'Copy'; btn.className = 'btn-copy'; }, 2000);
                }
            };

            function showRoleSelect() {
                render(
                    '<div class="card role-card" onclick="app.selectRole(&quot;teacher&quot;)"><div class="icon">\\ud83e\\uddd1\\u200d\\ud83c\\udf93</div><div class="label">\\u042f \\u0443\\u0447\\u0438\\u0442\\u0435\\u043b\\u044c</div><div class="desc">\\u0421\\u043e\\u0437\\u0434\\u0430\\u0432\\u0430\\u0442\\u044c \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u044f, \\u0441\\u043c\\u043e\\u0442\\u0440\\u0435\\u0442\\u044c \\u0440\\u0435\\u0437\\u0443\\u043b\\u044c\\u0442\\u0430\\u0442\\u044b</div></div>' +
                    '<div class="card role-card" onclick="app.selectRole(&quot;student&quot;)"><div class="icon">\\ud83e\\uddd1\\u200d\\ud83c\\udfeb</div><div class="label">\\u042f \\u0443\\u0447\\u0435\\u043d\\u0438\\u043a</div><div class="desc">\\u0412\\u044b\\u043f\\u043e\\u043b\\u043d\\u0438\\u0442\\u044c \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 \\u043f\\u043e \\u043a\\u043e\\u0434\\u0443</div></div>'
                );
            }

            window.app = {
                selectRole: function(role) {
                    if (role === 'teacher') this.teacherMenu();
                    else this.studentEnterId();
                },
                teacherMenu: function() {
                    render(
                        '<div class="card" style="text-align:center"><h2>\\ud83e\\uddd1\\u200d\\ud83c\\udf93 \\u0423\\u0447\\u0438\\u0442\\u0435\\u043b\\u044c</h2><button class="btn btn-primary btn-full" onclick="app.createExercise()">\\ud83d\\udccb \\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435</button><button class="btn btn-secondary btn-full" onclick="app.myExercises()">\\ud83d\\udcca \\u041c\\u043e\\u0438 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u044f</button><button class="back-link" onclick="app.showRoleSelect()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'
                    );
                },
                createExercise: function() {
                    render(
                        '<div class="card"><h2>\\ud83d\\udccb \\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435</h2>' +
                        '<label>\\u041a\\u0430\\u043a\\u0438\\u0435 \\u0433\\u043b\\u0430\\u0433\\u043e\\u043b\\u044b (\\u0447\\u0435\\u0440\\u0435\\u0437 \\u0437\\u0430\\u043f\\u044f\\u0442\\u0443\\u044e)</label>' +
                        '<textarea id="f-verbs" placeholder="be, have, do, go, say...">be, have, do, go, say, see, make, take, come, get</textarea>' +
                        '<label>\\u0421\\u043a\\u043e\\u043b\\u044c\\u043a\\u043e \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0439 (1-50)</label>' +
                        '<input id="f-count" type="number" value="10" min="1" max="50">' +
                        '<label>\\u0424\\u043e\\u0440\\u043c\\u044b</label>' +
                        '<div class="radio-group"><label><input type="radio" name="mode" value="3" checked> \\u0412\\u0441\\u0435 3 (1 \\u043f\\u043e\\u0434\\u0441\\u043a\\u0430\\u0437\\u043a\\u0430, 2 \\u043f\\u0440\\u043e\\u043f\\u0443\\u0441\\u043a\\u0430 - \\u0440\\u0430\\u043d\\u0434\\u043e\\u043c)</label><label><input type="radio" name="mode" value="2"> \\u041f\\u0435\\u0440\\u0432\\u0430\\u044f + \\u0432\\u0442\\u043e\\u0440\\u0430\\u044f (\\u0442\\u043e\\u043b\\u044c\\u043a\\u043e Past Participle \\u043f\\u0440\\u043e\\u043f\\u0443\\u0449\\u0435\\u043d)</label></div>' +
                        '<label>\\u0414\\u043e\\u043f. \\u043f\\u043e\\u0436\\u0435\\u043b\\u0430\\u043d\\u0438\\u044f</label>' +
                        '<textarea id="f-wishes" placeholder="\\u041d\\u0435\\u043e\\u0431\\u044f\\u0437\\u0430\\u0442\\u0435\\u043b\\u044c\\u043d\\u043e"></textarea>' +
                        '<button class="btn btn-primary btn-full" onclick="app.generateExercise()">\\ud83e\\ude84 \\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c</button>' +
                        '<button class="back-link" onclick="app.teacherMenu()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'
                    );
                },
                generateExercise: function() {
                    var verbs = document.getElementById('f-verbs').value.trim();
                    var count = parseInt(document.getElementById('f-count').value) || 10;
                    var mode = parseInt(document.querySelector('input[name="mode"]:checked').value);
                    var wishes = document.getElementById('f-wishes').value.trim();
                    if (count < 1) count = 1; if (count > 50) count = 50;
                    render('<div class="card" style="text-align:center"><p>\\ud83e\\ude84 \\u0413\\u0435\\u043d\\u0435\\u0440\\u0430\\u0446\\u0438\\u044f...</p></div>');
                    var xhr = new XMLHttpRequest();
                    xhr.open('POST', '/api/verbs/generate');
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+r.error+'</div><button class="back-link" onclick="app.createExercise()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            // show preview with tasks
                            var h = '<div class="card"><h2>\\ud83d\\udccb \\u041f\\u0440\\u0435\\u0434\\u043f\\u0440\\u043e\\u0441\\u043c\\u043e\\u0442\\u0440</h2>';
                            h += '<p style="color:#888;font-size:13px;margin-bottom:8px">\\u041f\\u0440\\u0430\\u0432\\u0438\\u043b\\u044c\\u043d\\u044b\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u044b (\\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u044c\\u0442\\u0435 AI):</p>';
                            h += '<table class="verbs-table preview-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            (r.tasks || []).forEach(function(t) {
                                h += '<tr><td>'+(t.inf||'')+'</td><td>'+(t.past||'')+'</td><td>'+(t.pp||'')+'</td></tr>';
                            });
                            h += '</table>';
                            h += '<p style="color:#888;font-size:13px;margin-top:8px">\\u0423\\u0447\\u0435\\u043d\\u0438\\u043a\\u0438 \\u0443\\u0432\\u0438\\u0434\\u044f\\u0442: '+(mode==2?'\\u043f\\u0435\\u0440\\u0432\\u0443\\u044e \\u0438 \\u0432\\u0442\\u043e\\u0440\\u0443\\u044e \\u0444\\u043e\\u0440\\u043c\\u0443 (\\u0437\\u0430\\u043f\\u043e\\u043b\\u043d\\u0438\\u0442\\u044c Past Participle)':'\\u043e\\u0434\\u043d\\u0443 \\u0444\\u043e\\u0440\\u043c\\u0443 \\u043a\\u0430\\u043a \\u043f\\u043e\\u0434\\u0441\\u043a\\u0430\\u0437\\u043a\\u0443, \\u0434\\u0432\\u0435 \\u0434\\u0440\\u0443\\u0433\\u0438\\u0435 \\u0437\\u0430\\u043f\\u043e\\u043b\\u043d\\u0438\\u0442\\u044c')+'.</p>';
                            h += '<button class="btn btn-primary btn-full" onclick="app.confirmExercise('+r.id+',\\''+r.share_url+'\\')">\\ud83d\\udcdd \\u041f\\u043e\\u0434\\u0442\\u0432\\u0435\\u0440\\u0434\\u0438\\u0442\\u044c \\u0438 \\u043e\\u0442\\u043a\\u0440\\u044b\\u0442\\u044c \\u0441\\u0441\\u044b\\u043b\\u043a\\u0443</button>';
                            h += '<button class="btn btn-secondary btn-full" onclick="app.generateExercise()">\\ud83d\\udd04 \\u041f\\u0435\\u0440\\u0435\\u0441\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c</button>';
                            h += '<button class="back-link" onclick="app.createExercise()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>';
                            render(h);
                        } catch(e) { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0433\\u0435\\u043d\\u0435\\u0440\\u0430\\u0446\\u0438\\u0438. \\u041f\\u043e\\u043f\\u0440\\u043e\\u0431\\u0443\\u0439\\u0442\\u0435 \\u0435\\u0449\\u0451.</div>'); }
                    };
                    xhr.onerror = function() { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0441\\u0435\\u0442\\u0438.</div>'); };
                    xhr.send(JSON.stringify({verbs: verbs, count: count, mode: mode, wishes: wishes, user_id: USER_ID}));
                },
                confirmExercise: function(exId, shareUrl) {
                    render(
                        '<div class="card" style="text-align:center"><h2>\\u2705 \\u0417\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 \\u0441\\u043e\\u0437\\u0434\\u0430\\u043d\\u043e!</h2>' +
                        '<p style="margin:12px 0;color:#888">ID: <strong style="color:#e94560">'+exId+'</strong></p>' +
                        '<div class="share-link"><code>'+shareUrl+'</code><button class="btn-copy" data-url="'+shareUrl+'" onclick="copyUrl(this)">Copy</button></div>' +
                        '<button class="btn btn-secondary btn-full" onclick="app.myExercises()">\\ud83d\\udcca \\u041c\\u043e\\u0438 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u044f</button>' +
                        '<button class="btn btn-secondary btn-full" onclick="app.createExercise()">\\ud83d\\udccb \\u0415\\u0449\\u0451</button>' +
                        '<button class="back-link" onclick="app.teacherMenu()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'
                    );
                },
                myExercises: function() {
                    render('<div class="card" style="text-align:center"><p>\\ud83d\\udd0d \\u0417\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0430...</p></div>');
                    var xhr = new XMLHttpRequest();
                    xhr.open('GET', '/api/verbs/exercises?user_id=' + encodeURIComponent(USER_ID));
                    xhr.onload = function() {
                        try {
                            var list = JSON.parse(xhr.responseText);
                            if (!list.length) { render('<div class="card" style="text-align:center;color:#888"><p>\\u041d\\u0435\\u0442 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0439.</p><button class="btn btn-primary btn-full" onclick="app.createExercise()">\\ud83d\\udccb \\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c</button><button class="back-link" onclick="app.teacherMenu()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'); return; }
                            var h = '<div class="ex-list">';
                            list.forEach(function(e) {
                                h += '<div class="ex-item" onclick="app.viewResults('+e.id+')"><div><div class="ex-id">'+e.id+'</div><div class="ex-meta">'+e.task_count+' \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0439, '+e.student_count+' \\u0443\\u0447\\u0435\\u043d\\u0438\\u043a\\u043e\\u0432</div></div><span style="color:#888">\\u2192</span></div>';
                            });
                            h += '</div><button class="btn btn-primary btn-full" onclick="app.createExercise()">\\ud83d\\udccb \\u0421\\u043e\\u0437\\u0434\\u0430\\u0442\\u044c</button><button class="back-link" onclick="app.teacherMenu()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>';
                            render(h);
                        } catch(e) { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0437\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0438.</div>'); }
                    };
                    xhr.onerror = function() { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0441\\u0435\\u0442\\u0438.</div>'); };
                    xhr.send();
                },
                viewResults: function(exId) {
                    render('<div class="card" style="text-align:center"><p>\\ud83d\\udd0d \\u0417\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0430...</p></div>');
                    var xhr = new XMLHttpRequest();
                    xhr.open('GET', '/api/verbs/exercise/'+exId+'/results?teacher_id=' + encodeURIComponent(USER_ID));
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+r.error+'</div><button class="back-link" onclick="app.myExercises()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            var h = '<div class="card"><h2>\\u0417\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 #'+exId+'</h2>';
                            if (!r.submissions || !r.submissions.length) { h += '<p style="color:#888">\\u041f\\u043e\\u043a\\u0430 \\u043d\\u0435\\u0442 \\u0440\\u0435\\u0448\\u0435\\u043d\\u0438\\u0439.</p>'; }
                            else {
                                r.submissions.forEach(function(s) {
                                    h += '<div class="student-row"><span class="student-name">'+s.name+'</span><span class="student-score">'+s.score+'/'+s.total+'</span></div>';
                                    s.errors.forEach(function(e) {
                                        h += '<div style="font-size:13px;color:#e94560;padding:2px 0 2px 20px;">\\u2716 '+e+'</div>';
                                    });
                                });
                            }
                            h += '</div><button class="back-link" onclick="app.myExercises()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>';
                            render(h);
                        } catch(e) { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0437\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0438.</div>'); }
                    };
                    xhr.onerror = function() { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0441\\u0435\\u0442\\u0438.</div>'); };
                    xhr.send();
                },
                studentEnterId: function(exId) {
                    render(
                        '<div class="card"><h2>\\ud83e\\uddd1\\u200d\\ud83c\\udfeb \\u0423\\u0447\\u0435\\u043d\\u0438\\u043a</h2><label>\\u0412\\u0432\\u0435\\u0434\\u0438\\u0442\\u0435 ID \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u044f</label>' +
                        '<input id="s-exid" type="text" placeholder="\\u041d\\u0430\\u043f\\u0440\\u0438\\u043c\\u0435\\u0440: 123456" value="'+(exId||'')+'">' +
                        '<button class="btn btn-primary btn-full" onclick="app.studentName()">\\u041d\\u0430\\u0447\\u0430\\u0442\\u044c</button>' +
                        '<button class="back-link" onclick="app.showRoleSelect()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'
                    );
                },
                studentName: function() {
                    var exId = document.getElementById('s-exid').value.trim();
                    if (!exId || isNaN(parseInt(exId))) { render('<div class="card error-text">\\u0412\\u0432\\u0435\\u0434\\u0438\\u0442\\u0435 \\u043a\\u043e\\u0440\\u0440\\u0435\\u043a\\u0442\\u043d\\u044b\\u0439 ID.</div><button class="back-link" onclick="app.studentEnterId()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                    if (studentName) { app.startExercise(exId); return; }
                    render(
                        '<div class="card"><h2>\\u041a\\u0430\\u043a \\u0442\\u0435\\u0431\\u044f \\u0437\\u043e\\u0432\\u0443\\u0442?</h2><input id="s-name" type="text" placeholder="\\u0418\\u043c\\u044f" value="">' +
                        '<button class="btn btn-primary btn-full" onclick="app.saveName('+exId+')">\\u0414\\u0430\\u043b\\u0435\\u0435</button>' +
                        '<button class="back-link" onclick="app.studentEnterId()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button></div>'
                    );
                },
                saveName: function(exId) {
                    var name = document.getElementById('s-name').value.trim();
                    if (!name) { render('<div class="card error-text">\\u0412\\u0432\\u0435\\u0434\\u0438\\u0442\\u0435 \\u0438\\u043c\\u044f.</div><button class="back-link" onclick="app.studentName()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                    studentName = name;
                    localStorage.setItem('verbs_name', name);
                    app.startExercise(exId);
                },
                startExercise: function(exId) {
                    render('<div class="card" style="text-align:center"><p>\\ud83d\\udd0d \\u0417\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0430...</p></div>');
                    var xhr = new XMLHttpRequest();
                    xhr.open('GET', '/api/verbs/exercise/'+exId);
                    xhr.onload = function() {
                        try {
                            var ex = JSON.parse(xhr.responseText);
                            if (ex.error) { render('<div class="card error-text">'+ex.error+'</div><button class="back-link" onclick="app.studentEnterId()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            var h = '<div class="card"><h2>\\u0417\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 #'+ex.id+'</h2><table class="verbs-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            ex.tasks.forEach(function(t, i) {
                                h += '<tr><td>'+(t.inf ? '<span class="filled">'+t.inf+'</span>' : '<input id="i'+i+'i" placeholder="..." data-idx="'+i+'" data-field="inf">')+'</td>';
                                h += '<td>'+(t.past ? '<span class="filled">'+t.past+'</span>' : '<input id="i'+i+'p" placeholder="..." data-idx="'+i+'" data-field="past">')+'</td>';
                                h += '<td>'+(t.pp ? '<span class="filled">'+t.pp+'</span>' : '<input id="i'+i+'pp" placeholder="..." data-idx="'+i+'" data-field="pp">')+'</td></tr>';
                            });
                            h += '</table><button class="btn btn-primary btn-full" onclick="app.submitExercise('+ex.id+')">\\u2705 \\u041f\\u0440\\u043e\\u0432\\u0435\\u0440\\u0438\\u0442\\u044c</button></div>';
                            render(h);
                        } catch(e) { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0437\\u0430\\u0433\\u0440\\u0443\\u0437\\u043a\\u0438.</div>'); }
                    };
                    xhr.onerror = function() { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0441\\u0435\\u0442\\u0438.</div>'); };
                    xhr.send();
                },
                submitExercise: function(exId) {
                    var inputs = document.querySelectorAll('.verbs-table input');
                    var answers = {};
                    inputs.forEach(function(inp) {
                        var idx = inp.dataset.idx;
                        if (!answers[idx]) answers[idx] = {};
                        answers[idx][inp.dataset.field] = inp.value.trim().toLowerCase();
                    });
                    var ansList = [];
                    Object.keys(answers).sort(function(a,b){return parseInt(a)-parseInt(b)}).forEach(function(k) { ansList.push(answers[k]); });
                    render('<div class="card" style="text-align:center"><p>\\u2705 \\u041f\\u0440\\u043e\\u0432\\u0435\\u0440\\u043a\\u0430...</p></div>');
                    var xhr = new XMLHttpRequest();
                    xhr.open('POST', '/api/verbs/submit');
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+r.error+'</div>'); return; }
                            var h = '<div class="card"><div class="result-summary"><div class="score">'+r.score+'/'+r.total+'</div><div class="label">\\u043f\\u0440\\u0430\\u0432\\u0438\\u043b\\u044c\\u043d\\u044b\\u0445</div></div></div>';
                            h += '<div class="card"><table class="verbs-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            r.details.forEach(function(d) {
                                h += '<tr><td class="'+(d.inf_correct?'correct':'wrong')+'">'+(d.inf||'')+'</td><td class="'+(d.past_correct?'correct':'wrong')+'">'+(d.past||'')+'</td><td class="'+(d.pp_correct?'correct':'wrong')+'">'+(d.pp||'')+'</td></tr>';
                            });
                            h += '</table></div><button class="btn btn-primary btn-full" onclick="app.studentEnterId()">\\ud83d\\udccb \\u041d\\u043e\\u0432\\u043e\\u0435 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435</button>';
                            render(h);
                        } catch(e) { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u043a\\u0438.</div>'); }
                    };
                    xhr.onerror = function() { render('<div class="card error-text">\\u041e\\u0448\\u0438\\u0431\\u043a\\u0430 \\u0441\\u0435\\u0442\\u0438.</div>'); };
                    xhr.send(JSON.stringify({exercise_id: exId, user_id: USER_ID, name: studentName, answers: ansList}));
                }
            };

            var exParam = (window.location.search.match(/[?&]exercise=(\d+)/) || [])[1];
            if (exParam) {
                if (studentName) {
                    app.startExercise(exParam);
                } else {
                    app.studentEnterId(exParam);
                }
            } else {
                showRoleSelect();
            }
        })();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


VERB_GEN_LOCK: dict[int, float] = {}


@app.route("/api/verbs/generate", methods=["POST"])
def api_verbs_generate():
    data = request.get_json(silent=True) or {}
    verbs = (data.get("verbs") or "").strip()
    count = int(data.get("count") or 10)
    mode = int(data.get("mode") or 2)
    wishes = (data.get("wishes") or "").strip()
    user_id_raw = data.get("user_id")
    if not verbs:
        return jsonify({"error": "Укажите глаголы"}), 400
    count = max(1, min(50, count))
    uid = _web_user_id(user_id_raw)
    now = time.time()
    if uid in VERB_GEN_LOCK and now - VERB_GEN_LOCK[uid] < 10:
        return jsonify({"error": "Подождите 10 секунд между генерациями"}), 429
    VERB_GEN_LOCK[uid] = now
    tasks = _generate_verb_exercise(verbs, count, mode, wishes)
    if not tasks:
        return jsonify({"error": "AI не смог сгенерировать задание. Проверьте глаголы и попробуйте ещё раз."}), 503
    ex_id = random.randint(100000, 999999)
    while _load_verb_exercise(ex_id) is not None:
        ex_id = random.randint(100000, 999999)
    ex_data = {"id": ex_id, "teacher_id": uid, "verbs": verbs, "task_count": count, "mode": mode, "wishes": wishes, "tasks": tasks}
    _save_verb_exercise(ex_data)
    share_url = request.host_url.rstrip("/") + "/irregular_verbs/exercise/" + str(ex_id)
    # build a display-safe preview (blank fields per mode) for the teacher
    preview = []
    for t in tasks:
        d = {}
        if mode == 2:
            d["inf"] = t.get("inf", "")
            d["past"] = t.get("past", "")
            d["pp"] = ""
        elif mode == 3:
            keys = ["inf", "past", "pp"]
            random.shuffle(keys)
            d[keys[0]] = t.get(keys[0], "")
            d[keys[1]] = ""
            d[keys[2]] = ""
        else:
            d = dict(t)
        preview.append(d)
    return jsonify({"id": ex_id, "share_url": share_url, "tasks": tasks, "preview": preview})


@app.route("/api/verbs/exercises", methods=["GET"])
def api_verbs_exercises():
    user_id_raw = request.args.get("user_id", "")
    uid = _web_user_id(user_id_raw)
    if not uid:
        return jsonify([])
    exercises = _load_teacher_exercises(uid)
    result = []
    for ex in exercises:
        result.append({"id": ex["id"], "task_count": ex["task_count"], "student_count": ex.get("student_count", 0)})
    return jsonify(result)


@app.route("/api/verbs/exercise/<int:ex_id>", methods=["GET"])
def api_verbs_exercise(ex_id):
    ex = _load_verb_exercise(ex_id)
    if not ex:
        return jsonify({"error": "Задание не найдено"}), 404
    mode = ex.get("mode", 2)
    tasks_display = []
    for t in ex["tasks"]:
        d = {}
        if mode == 2:
            d["inf"] = t.get("inf", "")
            d["past"] = t.get("past", "")
            d["pp"] = ""
        else:
            keys = ["inf", "past", "pp"]
            random.shuffle(keys)
            d[keys[0]] = t.get(keys[0], "")
            d[keys[1]] = ""
            d[keys[2]] = ""
        tasks_display.append(d)
    return jsonify({"id": ex["id"], "tasks": tasks_display})


@app.route("/api/verbs/exercise/<int:ex_id>/results", methods=["GET"])
def api_verbs_exercise_results(ex_id):
    ex = _load_verb_exercise(ex_id)
    if not ex:
        return jsonify({"error": "Задание не найдено"}), 404
    teacher_id_raw = request.args.get("teacher_id", "")
    uid = _web_user_id(teacher_id_raw)
    if ex.get("teacher_id") != uid:
        return jsonify({"error": "Нет доступа"}), 403
    subs = _load_verb_submissions(ex_id)
    formatted = []
    for s in subs:
        errors = []
        for d in s.get("details", []):
            parts = []
            if not d.get("inf_correct") and d.get("inf_correct_val"):
                parts.append(f"Infinitive: был {d.get('inf_correct_val','?')}, ввели «{d.get('inf','')}»")
            if not d.get("past_correct") and d.get("past_correct_val"):
                parts.append(f"Past: был {d.get('past_correct_val','?')}, ввели «{d.get('past','')}»")
            if not d.get("pp_correct") and d.get("pp_correct_val"):
                parts.append(f"PP: был {d.get('pp_correct_val','?')}, ввели «{d.get('pp','')}»")
            if parts:
                errors.append(", ".join(parts))
        formatted.append({"name": s.get("name", ""), "score": s.get("score", 0), "total": s.get("total", 0), "errors": errors})
    return jsonify({"exercise_id": ex_id, "submissions": formatted})


@app.route("/api/verbs/submit", methods=["POST"])
def api_verbs_submit():
    data = request.get_json(silent=True) or {}
    ex_id = data.get("exercise_id")
    user_id_raw = data.get("user_id")
    name = (data.get("name") or "").strip()
    answers = data.get("answers", [])
    if not ex_id or not _load_verb_exercise(ex_id):
        return jsonify({"error": "Задание не найдено"}), 404
    if not name:
        return jsonify({"error": "Укажите имя"}), 400
    ex = _load_verb_exercise(ex_id)
    uid = _web_user_id(user_id_raw)
    tasks = ex["tasks"]
    total_fields = 0
    correct_fields = 0
    details = []
    for i, task in enumerate(tasks):
        ans = answers[i] if i < len(answers) else {}
        d = {"inf": task.get("inf", ""), "past": task.get("past", ""), "pp": task.get("pp", ""),
             "inf_correct": True, "past_correct": True, "pp_correct": True}
        for field in ("inf", "past", "pp"):
            if field in ans:
                total_fields += 1
                user_val = ans[field].strip().lower()
                d[field] = ans[field]
                expected = task.get(field, "").strip().lower()
                d[field + "_correct"] = user_val == expected if expected else True
                if d[field + "_correct"]:
                    correct_fields += 1
        d["inf_correct_val"] = task.get("inf", "")
        d["past_correct_val"] = task.get("past", "")
        d["pp_correct_val"] = task.get("pp", "")
        details.append(d)
    _save_verb_submission(ex_id, {"user_id": uid, "name": name, "score": correct_fields, "total": total_fields, "details": details, "timestamp": time.time()})
    return jsonify({"score": correct_fields, "total": total_fields, "details": details})


@app.route("/irregular_verbs/exercise/<int:ex_id>")
def irregular_verbs_exercise_redirect(ex_id):
    return "", 302, {"Location": "/irregular_verbs?exercise=" + str(ex_id)}


@app.route("/telegram/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """Receive Telegram webhook and forward to processing."""

    # Verify secret
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        return jsonify({"error": "invalid_secret"}), 404

    # Get update
    update = request.get_json()
    if not update:
        return jsonify({"ok": True})
    
    # Handle callback_query
    callback_query = update.get("callback_query", {})
    callback_data = callback_query.get("data", "")
    if callback_data:
        if callback_data.startswith("trivia_"):
            trivia_answer_callback(callback_query, callback_data)
            return jsonify({"ok": True})
        if callback_data.startswith("gd_moderate_"):
            gd_moderate_callback(callback_query, callback_data)
            return jsonify({"ok": True})

    # Process Telegram commands supported by the Vercel webhook runtime.
    try:
        message = update.get("message", {})
        msg_text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user = message.get("from", {})
        user_id = user.get("id", chat_id)
        name = user.get("first_name") or user.get("username") or "LucasTeam"
        command = normalize_command(msg_text)

        print(f"[WEBHOOK] command='{command}' text='{msg_text[:50]}' user_id={user_id} chat_id={chat_id}")

        # Universe Module: infected user message modification
        if (
            msg_text
            and not command
            and chat_id
            and chat_id != user_id
            and not message.get("reply_to_message")
        ):
            try:
                with get_db_engine().connect() as conn:
                    inf_row = conn.execute(
                        text("SELECT virus_type FROM infection_status WHERE user_id = :uid"),
                        {"uid": user_id},
                    ).mappings().first()
                if inf_row and inf_row["virus_type"]:
                    virus = inf_row["virus_type"]
                    msg_id = message.get("message_id")
                    if virus == "олеговирус":
                        modified = msg_text.replace(" ", " кхм-кхм ")[:200]
                        suffix = "🦠 _заражён олеговирусом_"
                    else:
                        modified = msg_text + " ☕"
                        suffix = "🧬 _заражён LTL-паразитом_"
                    if msg_id:
                        requests.delete(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                            json={"chat_id": chat_id, "message_id": msg_id},
                            timeout=3,
                        )
                    send_telegram_message(
                        chat_id,
                        f"{modified}\n\n{suffix}",
                        parse_mode="Markdown",
                    )
                    return jsonify({"ok": True})
            except Exception as exc:
                print(f"[UNIVERSE] infection message modify error: {exc}")

        reply_to = message.get("reply_to_message")

        # D&D AI Master: intercept free-form messages during active sessions
        if not command and chat_id and msg_text and not reply_to:
            dnd_reply = None
            try:
                from api.dnd_runtime import handle_free_text
                dnd_reply = handle_free_text(user_id, chat_id, msg_text)
            except Exception as exc:
                print(f"[DND] handle_free_text error: {exc}")
            if dnd_reply:
                send_telegram_message(chat_id, dnd_reply)
                return jsonify({"ok": True})

        # Check for parsing trigger (reply to game bot with "Парсинг" or /parse or /parsing)
        is_parsing_trigger = (
            msg_text and msg_text.lower().strip() in ["парсинг", "parsing"]
        ) or command in ["/parse", "/parsing"]

        # Debug logging
        if is_parsing_trigger and reply_to:
            print(f"Parsing trigger detected. Reply_to keys: {list(reply_to.keys())}")
            replied_text = reply_to.get("text") or reply_to.get("caption", "")
            print(f"Replied text length: {len(replied_text)}")

        if reply_to and is_parsing_trigger:
            replied_text = reply_to.get("text") or reply_to.get("caption", "")
            parsed = parse_bot_message(replied_text)

            if parsed and chat_id:
                game = parsed["game"]
                amount = parsed["amount"]
                metric = parsed.get("type", "balance")
                total = parsed.get("total", amount)
                is_balance = parsed.get("is_balance", False)
                player_name = parsed.get("player", "")

                # Determine target user (player from message, not command sender)
                target_id = find_user_by_name(player_name) if player_name else None
                target_user_id = target_id or user_id
                target_name = player_name or name

                if is_balance:
                    prev_value = get_game_state(target_user_id, game, metric)
                    if "total" in parsed:
                        track_value = total
                        if prev_value == 0:
                            diff = amount
                        else:
                            diff = track_value - prev_value
                    else:
                        track_value = amount
                        diff = track_value - prev_value
                    if diff < 0:
                        diff = track_value
                    if diff == 0:
                        send_telegram_message(chat_id, f"ℹ️ {game}: значение не изменилось с прошлого раза ({prev_value:.1f}).")
                        return jsonify({"ok": True})
                    rate = parsed.get("rate", 1.0)
                    coins = int(diff * rate)
                    if coins <= 0:
                        send_telegram_message(chat_id, f"ℹ️ {game}: прирост {diff:.1f} слишком мал для начисления.")
                        return jsonify({"ok": True})
                    set_game_state(target_user_id, game, metric, track_value)
                    description = f"Парсинг {game}: +{coins} (прирост {diff:.1f})"
                    if game == "Чайометр":
                        detail = f"{game}: +{diff:.1f} л. × {rate}"
                    else:
                        detail = f"{game}: +{diff:.1f} × {rate}"
                else:
                    # Delta (earned amount) — use directly
                    coins = parsed["coins"]
                    if coins <= 0:
                        send_telegram_message(chat_id, "❌ Сумма начисления должна быть положительной")
                        return jsonify({"ok": True})
                    if game == "GDcards":
                        detail = f"{game}: {parsed['orbs']} orbs × {parsed['rate']}"
                    elif game == "Гуся Cards":
                        detail = f"{game}: {parsed['amount']} монет × {parsed['rate']}"
                    elif game == "Shmalala":
                        detail = f"{game} ({parsed['type']}): {parsed['amount']} × {parsed['rate']}"
                    else:
                        detail = f"{game}: ×{parsed['rate']}"
                    description = f"Парсинг {game}: +{coins}"

                if add_user_balance(target_user_id, coins, description):
                    mention = f"**{target_name}**" if target_id else f"**{target_name}**"
                    send_telegram_message(
                        chat_id,
                        f"✅ Начислено {coins} очков {mention}\n({detail})",
                    )
                else:
                    send_telegram_message(chat_id, "❌ Ошибка начисления")
                return jsonify({"ok": True})
            elif chat_id:
                send_telegram_message(
                    chat_id,
                    "❌ Не удалось распарсить сообщение. Поддерживаются: GDcards, Гуся Cards, Shmalala, Чайометр, BunkerRP",
                )
                return jsonify({"ok": True})

        # GD approve — position input (must be before AI block to avoid interception)
        approve_state = _GD_APPROVE_STATE.get(user_id)
        if approve_state and msg_text:
            text_stripped = msg_text.strip()
            try:
                position = int(text_stripped)
                if position < 1:
                    send_telegram_message(chat_id, "❌ Позиция должна быть положительным числом.")
                else:
                    sub_id = approve_state["sub_id"]
                    level_name = approve_state["level_name"]
                    difficulty = get_gd_difficulty_name(level_name)
                    level_id = add_gd_level(level_name, position, difficulty)
                    if not level_id:
                        send_telegram_message(chat_id, f"❌ Ошибка при добавлении уровня **{level_name}** в топ.", parse_mode="Markdown")
                    else:
                        if approve_gd_submission_db(sub_id, user_id):
                            send_telegram_message(
                                chat_id,
                                f"✅ Заявка #{sub_id} подтверждена!\n"
                                f"🏆 Уровень **{level_name}** добавлен в топ на позицию **#{position}**.",
                                parse_mode="Markdown",
                            )
                        else:
                            send_telegram_message(chat_id, f"❌ Ошибка подтверждения заявки #{sub_id}.")
                            log_error("GD", "approve_failed", f"GD approve failed sub_id={sub_id}", "approve_gd_submission_db returned False")
                _GD_APPROVE_STATE.pop(user_id, None)
            except ValueError:
                send_telegram_message(chat_id, "❌ Пожалуйста, введите число — позицию в топе.")
            return jsonify({"ok": True})

        # AI response on reply to bot message or @mention
        if BOT_ID is None:
            _load_bot_id()
        
        # Check for reply to bot message
        is_bot_reply = detect_bot_reply(message)
        # Check for @mention of bot
        is_mention, mention_text = detect_bot_mention(msg_text, message.get("entities"))
        
        if chat_id and (is_bot_reply or is_mention):
            # Get user's character preference
            character = get_user_character(user_id)
            # Extract user text
            if is_bot_reply and reply_to:
                user_text = msg_text or ""
            elif is_mention:
                user_text = mention_text
            else:
                user_text = msg_text or ""
            
            if user_text.strip():
                # Build prompt and call AI with memory
                prompt = build_character_prompt(character, user_text)
                answer = call_ai_with_memory(user_id, prompt)
                emoji = CHARACTER_EMOJI.get(character, "")
                prefix = f"{emoji} " if emoji else ""
                send_telegram_message(chat_id, f"{prefix}{answer}")
                return jsonify({"ok": True})
            else:
                # User replied with empty text or just mention
                send_telegram_message(chat_id, f"💬 Напишите сообщение для {character}")
                return jsonify({"ok": True})

        if command == "/start" and chat_id:
            send_telegram_message(
                chat_id, build_start_text(name, user_id, get_response_mode(chat_id))
            )
        elif command == "/short" and chat_id:
            set_response_mode(chat_id, "short")
            send_telegram_message(chat_id, "Краткий режим включён. Напишите /start.")
        elif command == "/long" and chat_id:
            set_response_mode(chat_id, "long")
            send_telegram_message(chat_id, "Полный режим включён. Напишите /start.")
        elif command == "/reading_trainer" and chat_id:
            send_reading_trainer(chat_id)
        elif command == "/endings" and chat_id:
            send_endings_trainer(chat_id)
        elif command == "/budget" and chat_id:
            budget_url = f"https://bank-bot-ruby.vercel.app/family_budget?user_id={user_id}"
            vk_app_url = "https://vk.com/app54665568"
            send_telegram_message(
                chat_id,
                "💰 Семейный бюджет\n\n"
                "Ведите учёт семейных трат, автоматически рассчитывайте долги "
                "и погашайте их частями.\n\n"
                "📖 Что внутри:\n"
                "• Создайте семью или присоединитесь по коду\n"
                "• Добавляйте траты — долги создаются автоматически\n"
                "• Смотрите, кто кому должен\n"
                "• Погашайте долги с пересчётом\n\n"
                "Выберите способ открытия:",
                reply_markup={
                    "inline_keyboard": [
                        [
                            {
                                "text": "🌐 Web (Vercel)",
                                "url": budget_url,
                            }
                        ],
                        [
                            {
                                "text": "📱 VK Mini App",
                                "url": vk_app_url,
                            }
                        ],
                    ]
                },
            )
        elif command == "/addexpense" and chat_id:
            _ADDE_LOG.append({"user_id": user_id, "name": name, "chat_id": chat_id, "text": msg_text[:100], "time": datetime.now().isoformat()})
            _ADDE_LOG[:] = _ADDE_LOG[-50:]
            now_ts = datetime.now().timestamp()
            last_ts = _ADDE_COOLDOWN.get(user_id, 0)
            if now_ts - last_ts < 300:
                return jsonify({"ok": True})
            _ADDE_COOLDOWN[user_id] = now_ts
            args = msg_text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(
                    chat_id,
                    "📝 Использование:\n"
                    "<code>/addexpense Кредитор Должник Сумма [Категория] [Комментарий]</code>\n\n"
                    "Пример:\n"
                    "<code>/addexpense Лука Мама 500 еда за пиццу</code>\n\n"
                    "Категории: еда, транспорт, хозяйство, развлечения, другое",
                    parse_mode="HTML",
                )
                return jsonify({"ok": True})

            family = _fetch_family_info_via_api(str(user_id))
            if not family:
                send_telegram_message(
                    chat_id,
                    "❌ Вы не состоите в семье.\n"
                    "Сначала создайте её: /family create <название>",
                )
                return jsonify({"ok": True})

            members = family.get("members", [])
            txn = parse_expense_line(args[1], members)
            if not txn:
                send_telegram_message(
                    chat_id,
                    "❌ Не удалось распознать трату.\n"
                    "Формат: Кредитор Должник Сумма [Категория] [Комментарий]\n"
                    "Проверьте имена участников и сумму.",
                )
                return jsonify({"ok": True})

            ok = _create_transaction_via_api(family["id"], txn)
            if ok:
                line_text = f"✅ {txn['amount']}₽ — {txn['category']}"
                if txn["description"]:
                    line_text += f" ({txn['description']})"
                send_telegram_message(chat_id, line_text)
            else:
                send_telegram_message(chat_id, "❌ Ошибка сервера при создании траты.")
        elif command == "/balance" and chat_id:
            balance, is_admin = get_user_balance(user_id)
            send_telegram_message(
                chat_id,
                f"Баланс: {balance} очков\nСтатус: {'админ' if is_admin else 'пользователь'}",
            )
        elif command == "/stats" and chat_id:
            stats = get_user_stats(user_id)
            send_telegram_message(
                chat_id,
                f"Статистика:\nЗаработано: {stats['earned']}\nПотрачено: {stats['spent']}\nБаланс: {stats['earned'] - stats['spent']}\nПокупок: {stats['purchases']}\nЗа неделю операций: {stats['total_transactions']}",
            )
        elif command == "/profile" and chat_id:
            balance, is_admin = get_user_balance(user_id)
            stats = get_user_stats(user_id)
            send_telegram_message(
                chat_id,
                f"Профиль: {name}\nБаланс: {balance}\nТранзакций: {stats['total_transactions']}\nСтатус: {'админ' if is_admin else 'пользователь'}",
            )
        elif command == "/user" and chat_id:
            # Alias for /profile
            balance, is_admin = get_user_balance(user_id)
            stats = get_user_stats(user_id)
            send_telegram_message(
                chat_id,
                f"Профиль: {name}\nБаланс: {balance}\nТранзакций: {stats['total_transactions']}\nСтатус: {'админ' if is_admin else 'пользователь'}",
            )
        elif command == "/errors" and chat_id:
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(chat_id, "❌ Только админ может просматривать ошибки.")
            elif not _ERROR_LOG:
                send_telegram_message(chat_id, "✅ Ошибок нет — всё чисто!")
            else:
                recent = _ERROR_LOG[-10:]
                lines = [f"📋 **Ошибки** ({len(_ERROR_LOG)} всего, последние {len(recent)}):\n"]
                for e in reversed(recent):
                    lines.append(f"🕐 {e['time']} | 🔴 {e['module']}/{e['error_type']}")
                    lines.append(f"   {e['message'][:100]}")
                    lines.append(f"   💡 {e['recommendation']}")
                    tb = e.get('traceback', '')
                    if tb:
                        lines.append(f"   📎 `{tb[-150:]}`")
                    lines.append("")
                send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
        elif command == "/clear_errors" and chat_id:
            if user_id != ADMIN_TELEGRAM_ID:
                send_telegram_message(chat_id, "❌ Только админ может очищать ошибки.")
            else:
                count = len(_ERROR_LOG)
                _ERROR_LOG.clear()
                send_telegram_message(chat_id, f"🗑 Очищено {count} ошибок.")
        elif command == "/history" and chat_id:
            history = get_user_history(user_id, limit=10)
            if not history:
                send_telegram_message(chat_id, "📭 У вас пока нет транзакций")
            else:
                lines = [f"История: {len(history)} операций"]
                for tx in history:
                    amount_text = (
                        f"+{tx['amount']}" if tx["amount"] > 0 else str(tx["amount"])
                    )
                    desc = (
                        tx["description"][:30] if tx["description"] else "Без описания"
                    )
                    lines.append(f"{amount_text} — {desc}")
                send_telegram_message(chat_id, "\n".join(lines))
        elif command == "/short_all" and chat_id:
            set_response_mode(chat_id, "short")
            send_telegram_message(
                chat_id,
                "Краткий режим включён для всех.\n/balance — баланс\n/profile — профиль\n/stats — статистика",
            )
        elif command == "/long_all" and chat_id:
            set_response_mode(chat_id, "long")
            send_telegram_message(chat_id, "Полный режим включён для всех.")
        elif command == "/ping" and chat_id:
            send_telegram_message(chat_id, "🏓 Понг!")
        elif command == "/help" and chat_id:
            help_text = (
                "📋 <b>Справка по командам</b>\n\n"
                "━━━ <b>Основные</b> ━━━\n"
                "/start — запустить бота\n"
                "/balance — баланс монет\n"
                "/profile — ваш профиль\n"
                "/stats — ваша статистика\n"
                "/history — история транзакций\n"
                "/short — краткие ответы AI\n"
                "/long — полные ответы AI\n"
                "/ping — проверка бота\n\n"
                "━━━ <b>Дополнительные</b> ━━━\n"
                "/reading_trainer — тренажёр чтения 🧸\n"
                "/endings — тренажёр окончаний 📝\n"
                "/trivia — викторина\n"
                "/character — выбрать характер AI\n"
                "/ai — AI-помощник\n"
                "/ask_canon — вопрос по канону\n"
                "/shop — магазин\n"
                "/buy — купить предмет\n"
                "/inventory — ваш инвентарь\n"
                "/chess — шахматы ♟️\n"
                "/gd — Geometry Dash 🎮\n"
                "/submit — отправить уровень GD\n"
                "/leaderboard — таблица лидеров GD\n"
                "/tea — чай ☕\n"
                "/daily_prayer — молитва\n"
                "/addexpense — добавить расход\n"
                "/user — информация о пользователе\n\n"
                "━━━ <b>Веб-сервисы</b> ━━━\n"
                "/budget — семейный бюджет (веб-интерфейс) 💰\n\n"
                "━━━ <b>Бета (нестабильно)</b> ━━━\n"
                "/dnd — D&D AI Master 🐉\n"
                "/dnd_start — начать сессию D&D\n"
                "/dnd_stop — завершить сессию D&D\n"
                "/dnd_status — статус D&D сессии\n"
                "/dnd_roll — бросить кубик D&D\n"
                "/dnd_fix — исправить ответ AI\n"
                "/infect — вирусный модул (universe)"
            )
            send_telegram_message(chat_id, help_text, parse_mode="HTML")

        # Admin commands
        elif command == "/admin" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                send_telegram_message(
                    chat_id,
                    "👨‍💼 Админ-панель\n\n/admin_users — пользователи\n/admin_balances — топ баланс\n/admin_stats — статистика\n/add_points — начислить\n/add_admin — назначить админа",
                )
        elif command == "/add_points" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                # Parse: /add_points @user 100 описание
                args = msg_text.split()[1:] if len(msg_text.split()) > 1 else []
                if len(args) < 2:
                    send_telegram_message(
                        chat_id, "Формат: /add_points @username сумма [описание]"
                    )
                else:
                    target_username = args[0].lstrip("@")
                    try:
                        amount = int(args[1])
                        description = (
                            " ".join(args[2:]) if len(args) > 2 else "Начислено админом"
                        )
                        # Find user by username or ID
                        target_id = None
                        if target_username.isdigit():
                            target_id = int(target_username)
                        else:
                            # Simple lookup by username (would need proper query)
                            send_telegram_message(
                                chat_id,
                                "❌ Поиск по username пока не поддерживается. Используйте telegram_id",
                            )
                            target_id = None

                        if target_id and add_user_balance(
                            target_id, amount, description
                        ):
                            send_telegram_message(
                                chat_id,
                                f"✅ Начислено {amount} очков пользователю {target_id}",
                            )
                        else:
                            send_telegram_message(chat_id, "❌ Ошибка начисления")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ Неверный формат суммы")
        elif command == "/add_coins" and chat_id:
            # Alias for add_points
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                send_telegram_message(chat_id, "Используйте /add_points")
        elif command == "/add_admin" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                args = msg_text.split()[1:] if len(msg_text.split()) > 1 else []
                if len(args) < 1:
                    send_telegram_message(chat_id, "Формат: /add_admin telegram_id")
                else:
                    try:
                        target_id = int(args[0])
                        if set_admin_status(target_id, True):
                            send_telegram_message(
                                chat_id, f"✅ Пользователь {target_id} назначен админом"
                            )
                        else:
                            send_telegram_message(chat_id, "❌ Ошибка назначения")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ Неверный формат ID")
        elif command == "/admin_users" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                users = get_all_users(limit=20)
                if not users:
                    send_telegram_message(chat_id, "Нет пользователей")
                else:
                    lines = [f"👥 Пользователей: {len(users)}\n"]
                    for u in users[:10]:
                        admin_mark = "👑" if u["is_admin"] else ""
                        lines.append(
                            f"{admin_mark}{u['first_name']} (@{u['username']}) — {u['balance']}"
                        )
                    send_telegram_message(chat_id, "\n".join(lines))
        elif command == "/admin_balances" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                top = get_top_balances(limit=10)
                if not top:
                    send_telegram_message(chat_id, "Нет данных")
                else:
                    lines = ["🏆 Топ баланс:\n"]
                    for i, u in enumerate(top, 1):
                        lines.append(f"{i}. {u['first_name']} — {u['balance']}")
                    send_telegram_message(chat_id, "\n".join(lines))
        elif command == "/admin_transactions" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                args = msg_text.split()[1:] if len(msg_text.split()) > 1 else []
                if len(args) < 1:
                    send_telegram_message(
                        chat_id, "Формат: /admin_transactions telegram_id"
                    )
                else:
                    try:
                        target_id = int(args[0])
                        history = get_user_history(target_id, limit=10)
                        if not history:
                            send_telegram_message(
                                chat_id, f"Нет транзакций для {target_id}"
                            )
                        else:
                            lines = [f"💰 Транзакции {target_id}:\n"]
                            for tx in history:
                                amount_text = (
                                    f"+{tx['amount']}"
                                    if tx["amount"] > 0
                                    else str(tx["amount"])
                                )
                                lines.append(
                                    f"{amount_text} — {tx['description'][:20]}"
                                )
                            send_telegram_message(chat_id, "\n".join(lines))
                    except ValueError:
                        send_telegram_message(chat_id, "❌ Неверный формат ID")
        elif command == "/admin_stats" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                users = get_all_users(limit=1000)
                total_balance = sum(u["balance"] for u in users)
                admin_count = sum(1 for u in users if u["is_admin"])
                send_telegram_message(
                    chat_id,
                    f"📊 Статистика системы:\n\nПользователей: {len(users)}\nАдминов: {admin_count}\nОбщий баланс: {total_balance}",
                )
        elif command == "/broadcast" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                send_telegram_message(
                    chat_id, "❌ Рассылка пока не реализована в Vercel runtime"
                )

        # AI commands
        # /ai command (parent for AI module)
        elif command == "/ai" or command == "/ask":
            if not chat_id:
                return jsonify({"ok": True})
            args = msg_text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(
                    chat_id,
                    "**🤖 AI Module**\n\n"
                    "/ai <вопрос> — задать вопрос AI\n"
                    "/ask <вопрос> — алиас /ai\n"
                    "/ai_help — показать эту справку\n"
                    "/character — выбрать характер\n"
                    "/generate_prayer или /pray — сгенерировать молитву\n"
                    "/ask_canon <вопрос> — вопрос по канону\n\n"
                    "💡 Или просто ответьте на сообщение бота или упомяните @lt_lo_game_bot",
                )
            else:
                question = args[1]
                if len(question) < 3:
                    send_telegram_message(chat_id, "❌ Вопрос слишком короткий")
                else:
                    prompt = f"Ты помощник, отвечающий кратко и по делу. Вопрос пользователя: {question}\n\nОтветь в 2-3 предложениях."
                    answer = call_ai_with_memory(user_id, prompt, max_tokens=200)
                    send_telegram_message(chat_id, answer)
        elif command == "/ai_help" and chat_id:
            send_telegram_message(
                chat_id,
                "🤖 **AI Module**\n\n"
                "/ai <вопрос> — задать вопрос AI\n"
                "/ask <вопрос> — алиас /ai\n"
                "/ai_help — показать эту справку\n"
                "/character — выбрать характер\n"
                "/generate_prayer или /pray — сгенерировать молитву\n"
                "/ask_canon <вопрос> — вопрос по канону\n\n"
                "💡 Или просто ответьте на сообщение бота или упомяните @lt_lo_game_bot",
            )
        elif command == "/character" and chat_id:
            args = msg_text.split()
            if len(args) < 2:
                # Show current character and available options
                current = get_user_character(user_id)
                chars = "\n".join([f"• {k} {CHARACTER_EMOJI.get(k, '')}" for k in CHARACTER_PROMPTS])
                send_telegram_message(
                    chat_id,
                    f"🎭 Текущий характер: **{current}** {CHARACTER_EMOJI.get(current, '')}\n\n"
                    f"Доступные характеры:\n{chars}\n\n"
                    f"Смена: /character <имя>\n"
                    f"Пример: /character чай",
                )
            else:
                character = args[1].lower()
                if set_user_character(user_id, character):
                    emoji = CHARACTER_EMOJI.get(character, "")
                    send_telegram_message(
                        chat_id,
                        f"✅ Характер изменён на: **{character}** {emoji}\n\n"
                        f"Теперь при ответе на сообщение бота или @упоминании бот будет отвечать в стиле {character}.",
                    )
                else:
                    chars = ", ".join(CHARACTER_PROMPTS.keys())
                    send_telegram_message(
                        chat_id,
                        f"❌ Неизвестный характер: {character}\n\n"
                        f"Доступные: {chars}",
                    )
        elif command == "/character_all" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Только для админов")
            else:
                args = msg_text.split()
                if len(args) < 2:
                    current = get_global_character()
                    send_telegram_message(
                        chat_id,
                        f"🌐 Глобальный характер: **{current}** {CHARACTER_EMOJI.get(current, '')}\n\n"
                        f"Смена: /character_all <имя>",
                    )
                else:
                    character = args[1].lower()
                    if set_global_character(character):
                        emoji = CHARACTER_EMOJI.get(character, "")
                        send_telegram_message(
                            chat_id,
                            f"✅ Глобальный характер изменён на: **{character}** {emoji}",
                        )
                    else:
                        send_telegram_message(chat_id, f"❌ Неизвестный характер: {character}")
        elif command in ["/generate_prayer", "/pray"] and chat_id:
            send_telegram_message(chat_id, "🙏 Сочиняю молитву...")
            prompt = (
                "Создай короткую молитву в стиле чайной религии.\n\n"
                "СТРУКТУРА ОБЯЗАТЕЛЬНАЯ:\n"
                "1. Начало: 5-9 повторений слова 'чай' через запятую\n"
                "2. Основная часть: 3-5 строк, каждая заканчивается словом 'чай' или 'настой'\n"
                "3. Завершение: 'eight-nine' (курсивом)\n\n"
                "Используй слова: чай, настой, заварка, кружка-алтарь, eight-nine.\n"
                "Пример:\n"
                "Чай, чай, чай, чай, чай, чай, чай.\n"
                "Да будет заварка моей крепкой, чай.\n"
                "Да не остынет кружка моя, чай.\n"
                "Да успокоит меня тёплый пар, чай.\n"
                "*eight-nine*\n\n"
                "Создай новую молитву в этом стиле:"
            )
            prayer = call_ai_api(prompt, max_tokens=150)
            send_telegram_message(chat_id, f"🙏 Молитва:\n\n{prayer}")
            return jsonify({"ok": True})
        elif command == "/ask_canon" and chat_id:
            args = msg_text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(
                    chat_id,
                    "Использование: /ask_canon <вопрос>\nПример: /ask_canon Кто такой олеговирус?",
                )
            else:
                question = args[1]
                prompt = (
                    f"Ты знаток канона олеговируса и LucasTeam Lore (LTL). "
                    f"Ответь кратко на вопрос по канону: {question}"
                )
                answer = call_ai_api(prompt)
                send_telegram_message(chat_id, answer)

        # Shop commands
        elif command == "/shop" and chat_id:
            items = get_shop_items(limit=10)
            if not items:
                send_telegram_message(chat_id, "🏪 Магазин пуст")
            else:
                lines = ["🏪 Магазин:\n"]
                for item in items:
                    lines.append(
                        f"{item['id']}. {item['name']} — {item['price']} очков"
                    )
                lines.append("\nКупить: /buy <номер>")
                send_telegram_message(chat_id, "\n".join(lines))
        elif command == "/buy" and chat_id:
            args = msg_text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(chat_id, "Формат: /buy <номер товара>")
            else:
                try:
                    item_id = int(args[1])
                    success, message = purchase_item(user_id, item_id)
                    send_telegram_message(chat_id, message)
                except ValueError:
                    send_telegram_message(chat_id, "❌ Неверный номер товара")
        elif command == "/buy_contact" and chat_id:
            send_telegram_message(chat_id, "Используйте /buy <номер> для покупки")
        elif (
            command
            in [
                "/buy_1",
                "/buy_2",
                "/buy_3",
                "/buy_4",
                "/buy_5",
                "/buy_6",
                "/buy_7",
                "/buy_8",
            ]
            and chat_id
        ):
            # Quick buy shortcuts
            item_num = int(command.replace("/buy_", ""))
            success, message = purchase_item(user_id, item_num)
            send_telegram_message(chat_id, message)
        elif command == "/inventory" and chat_id:
            inventory = get_user_inventory(user_id)
            if not inventory:
                send_telegram_message(chat_id, "📦 Инвентарь пуст")
            else:
                lines = ["📦 Ваш инвентарь:\n"]
                for item in inventory[:10]:
                    status = "✅" if item["is_active"] else "❌"
                    lines.append(f"{status} {item['name']}")
                send_telegram_message(chat_id, "\n".join(lines))

        # Trivia command - use static questions with Telegram poll for Vercel
        elif command == "/trivia" and chat_id:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "trivia_questions", os.path.join(os.path.dirname(__file__), "..", "bot", "trivia", "questions.py")
            )
            trivia_questions = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(trivia_questions)
            
            question = trivia_questions.generate_trivia_question()
            question_text = question["text"]
            options = question["options"]
            correct_index = question["correct_index"]
            explanation = question["explanation"]
            
            try:
                # Send native Telegram poll via API
                bot_token = os.getenv("BOT_TOKEN", "")
                if bot_token:
                    response = requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPoll",
                        json={
                            "chat_id": chat_id,
                            "question": question_text[:300],
                            "options": [opt[:100] for opt in options],
                            "type": "quiz",
                            "correct_option_id": correct_index,
                            "explanation": explanation[:200],
                            "explanation_parse_mode": "Markdown",
                            "is_anonymous": False,
                        },
                        timeout=10,
                    )
                    
                    if response.status_code == 200:
                        send_telegram_message(
                            chat_id,
                            "🎯 **Викторина по канону** отправлена!\nОтветьте на опрос выше. Правильный ответ даст +25 монет.",
                            parse_mode="Markdown",
                        )
                        return jsonify({"ok": True})
                    else:
                        print(f"sendPoll error: {response.text}")
                        raise Exception("sendPoll failed")
                else:
                    raise Exception("BOT_TOKEN not set")
            except Exception as exc:
                print(f"Error sending trivia poll: {exc}")
            
            # Fallback to text question with inline buttons
            send_telegram_message(
                chat_id,
                f"🎯 **Викторина по канону**\n\n{question_text}\n\nВыберите правильный ответ:",
                parse_mode="Markdown",
            )
            inline_keyboard = []
            for i, opt in enumerate(options):
                inline_keyboard.append([
                    {"text": f"✅ {opt}", "callback_data": f"trivia_{i}_{correct_index}"}
                ])
            send_telegram_message(
                chat_id,
                "⚠️ Для ответа нажмите на кнопку с вариантом ниже. Правильный ответ даст +25 монет.",
                reply_markup={"inline_keyboard": inline_keyboard},
            )
            return jsonify({"ok": True})

        # /chess command
        elif command == "/chess" and chat_id:
            help_text = (
                "♟ **Шахматный модуль LTHub**\n\n"
                "**Доступные команды:**\n"
                "`/chess_link <ник>` — привязать Lichess аккаунт\n"
                "`/chess_rating` — показать рейтинги\n"
                "`/chess_stats` — показать статистику\n"
                "`/puzzle` или `/chess_puzzle` — решить шахматную задачу\n"
                "`/chess_history` — история решённых задач\n\n"
                "**Как решать задачи:**\n"
                "1. Отправьте `/puzzle`\n"
                "2. Введите ваш ход (например: `e2e4`)\n"
                "3. За правильный ответ — +5 монет\n\n"
                "**Пример:**\n"
                "`/chess_link DrNykterstein`"
            )
            send_telegram_message(chat_id, help_text, parse_mode="Markdown")
        
        # /chess_link <username>
        elif command == "/chess_link" and chat_id:
            args = msg_text.split()[1:] if msg_text else []
            
            if len(args) < 1:
                send_telegram_message(
                    chat_id,
                    "♟ Использование: `/chess_link <ник>`\n\nПример: `/chess_link DrNykterstein`",
                    parse_mode="Markdown",
                )
            else:
                lichess_username = args[0].strip()
                if not lichess_username:
                    send_telegram_message(
                        chat_id, 
                        "❌ Укажите ник Lichess: `/chess_link <ник>`",
                        parse_mode="Markdown"
                    )
                else:
                    # Send "checking" status
                    send_telegram_message(
                        chat_id,
                        f"🔍 Проверяю Lichess аккаунт **{lichess_username}**...",
                        parse_mode="Markdown",
                    )
                    
                    try:
                        lichess_user = fetch_lichess_user(lichess_username)
                    except Exception as exc:
                        print(f"Lichess lookup failed: {exc}")
                        send_telegram_message(
                            chat_id,
                            "❌ Сейчас не удалось проверить Lichess аккаунт. Попробуйте позже.",
                        )
                        lichess_user = None
                    
                    if lichess_user is None:
                        send_telegram_message(
                            chat_id,
                            f"❌ Lichess аккаунт **{lichess_username}** не найден. Проверьте ник.",
                            parse_mode="Markdown",
                        )
                    else:
                        # Try to link account
                        success = link_chess_account(user_id, lichess_user["username"])
                        
                        if not success:
                            send_telegram_message(
                                chat_id,
                                "❌ Этот Lichess аккаунт уже привязан к другому пользователю.",
                            )
                        else:
                            title_prefix = f"{lichess_user['title']} " if lichess_user.get("title") else ""
                            online_text = "онлайн" if lichess_user.get("online") else "оффлайн/неизвестно"
                            success_msg = (
                                "♟ **Lichess аккаунт привязан!**\n\n"
                                f"Аккаунт: **{title_prefix}{lichess_user['username']}**\n"
                                f"Статус: {online_text}\n\n"
                                "Теперь можно использовать шахматные команды LTHub."
                            )
                            send_telegram_message(chat_id, success_msg, parse_mode="Markdown")
        
        # /chess_rating
        elif command == "/chess_rating" and chat_id:
            account = get_chess_account(user_id)
            if not account:
                send_telegram_message(
                    chat_id,
                    "❌ Сначала привяжите Lichess аккаунт: `/chess_link <ник>`",
                    parse_mode="Markdown",
                )
            else:
                send_telegram_message(
                    chat_id,
                    "🔍 Загружаю рейтинги...",
                )
                
                try:
                    lichess_user = fetch_lichess_user(account["lichess_username"])
                    if not lichess_user:
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось загрузить данные Lichess. Попробуйте позже.",
                        )
                    else:
                        title_prefix = f"{lichess_user['title']} " if lichess_user.get("title") else ""
                        online_text = "🟢 онлайн" if lichess_user.get("online") else "⚫ оффлайн"
                        perfs = lichess_user.get("perfs", {})
                        
                        rating_parts = []
                        rating_parts.append(f"**Статус:** {online_text}\n")
                        
                        if "bullet" in perfs:
                            rating_parts.append(f"🎯 **Пуля:** {perfs['bullet'].get('rating', '?')} ({perfs['bullet'].get('games', 0)} игр)")
                        if "blitz" in perfs:
                            rating_parts.append(f"⚡ **Блиц:** {perfs['blitz'].get('rating', '?')} ({perfs['blitz'].get('games', 0)} игр)")
                        if "rapid" in perfs:
                            rating_parts.append(f"⏱️ **Рапид:** {perfs['rapid'].get('rating', '?')} ({perfs['rapid'].get('games', 0)} игр)")
                        if "classical" in perfs:
                            rating_parts.append(f"⏳ **Классика:** {perfs['classical'].get('rating', '?')} ({perfs['classical'].get('games', 0)} игр)")
                        
                        rating_msg = (
                            f"♟ **Рейтинги {title_prefix}{lichess_user['username']}**\n\n"
                            + "\n".join(rating_parts)
                        )
                        send_telegram_message(chat_id, rating_msg, parse_mode="Markdown")
                except Exception as exc:
                    print(f"Error fetching ratings: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки рейтингов. Попробуйте позже.",
                    )
        
        # /chess_stats
        elif command == "/chess_stats" and chat_id:
            account = get_chess_account(user_id)
            if not account:
                send_telegram_message(
                    chat_id,
                    "❌ Сначала привяжите Lichess аккаунт: `/chess_link <ник>`",
                    parse_mode="Markdown",
                )
            else:
                send_telegram_message(
                    chat_id,
                    "🔍 Загружаю статистику...",
                )
                
                try:
                    lichess_user = fetch_lichess_user(account["lichess_username"])
                    if not lichess_user:
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось загрузить данные Lichess. Попробуйте позже.",
                        )
                    else:
                        title_prefix = f"{lichess_user['title']} " if lichess_user.get("title") else ""
                        perfs = lichess_user.get("perfs", {})
                        games = lichess_user.get("games", {})
                        
                        total_games = games.get("total", 0)
                        win = games.get("win", 0)
                        loss = games.get("loss", 0)
                        draw = games.get("draw", 0)
                        
                        winrate = round((win / total_games * 100), 1) if total_games > 0 else 0
                        
                        stats_parts = []
                        stats_parts.append(f"**Всего игр:** {total_games}")
                        stats_parts.append(f"✅ **Побед:** {win} ({winrate}%)")
                        stats_parts.append(f"❌ **Поражений:** {loss}")
                        stats_parts.append(f"🤝 **Ничьих:** {draw}\n")
                        
                        if "bullet" in perfs:
                            stats_parts.append(f"🎯 **Пуля:** {perfs['bullet'].get('rating', '?')} ({perfs['bullet'].get('games', 0)} игр)")
                        if "blitz" in perfs:
                            stats_parts.append(f"⚡ **Блиц:** {perfs['blitz'].get('rating', '?')} ({perfs['blitz'].get('games', 0)} игр)")
                        if "rapid" in perfs:
                            stats_parts.append(f"⏱️ **Рапид:** {perfs['rapid'].get('rating', '?')} ({perfs['rapid'].get('games', 0)} игр)")
                        if "classical" in perfs:
                            stats_parts.append(f"⏳ **Классика:** {perfs['classical'].get('rating', '?')} ({perfs['classical'].get('games', 0)} игр)")
                        
                        stats_msg = (
                            f"♟ **Статистика {title_prefix}{lichess_user['username']}**\n\n"
                            + "\n".join(stats_parts)
                        )
                        send_telegram_message(chat_id, stats_msg, parse_mode="Markdown")
                except Exception as exc:
                    print(f"Error fetching stats: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки статистики. Попробуйте позже.",
                    )
        
        # /puzzle and /chess_puzzle commands
        elif command in ["/puzzle", "/chess_puzzle"] and chat_id:
            print(f"[PUZZLE] user_id={user_id}, chat_id={chat_id}")
            account = get_chess_account(user_id)
            print(f"[PUZZLE] account={account}")
            if not account:
                print("[PUZZLE] No account, sending error")
                send_telegram_message(
                    chat_id,
                    "❌ Сначала привяжите Lichess аккаунт: `/chess_link <ник>`",
                    parse_mode="Markdown",
                )
            else:
                # Check cooldown (max 1 puzzle per day) — REMOVED for testing
                # TODO: re-enable after testing
                datetime.utcnow()
                get_user_coins(user_id)
                
                # Cooldown disabled — allow multiple puzzles per day
                # if coins_data and coins_data.get("last_puzzle_at"):
                #     last_puzzle = coins_data["last_puzzle_at"]
                #     if hasattr(last_puzzle, 'tzinfo') and last_puzzle.tzinfo is not None:
                #         last_puzzle = last_puzzle.replace(tzinfo=None)
                #     from datetime import timedelta
                #     if now - last_puzzle < timedelta(hours=24):
                #         remaining = 24 - (now - last_puzzle).total_seconds() / 3600
                #         send_telegram_message(
                #             chat_id,
                #             f"⏳ Пожалуйста, подождите {remaining:.1f} часов до следующей задачи.",
                #         )
                #         return jsonify({"ok": True})
                
                send_telegram_message(
                    chat_id,
                    "🧩 Загружаю задачу...",
                )
                
                try:
                    # Fetch random puzzle from Lichess (not daily — random each time)
                    puzzle_url = f"{LICHESS_API_BASE_URL}/puzzle/next"
                    headers = {"Accept": "application/json", "User-Agent": "LTHub/ChessModule"}
                    response = requests.get(puzzle_url, headers=headers, timeout=LICHESS_TIMEOUT_SECONDS)
                    
                    if response.status_code != 200:
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось загрузить задачу. Попробуйте позже.",
                        )
                        return jsonify({"ok": True})
                    
                    puzzle_data = response.json()
                    puzzle = puzzle_data.get("puzzle", {})
                    game = puzzle_data.get("game", {})
                    
                    puzzle_id = puzzle.get("id", "unknown")
                    rating = puzzle.get("rating", "?")
                    themes = ", ".join(puzzle.get("themes", [])[:3])
                    solution = puzzle.get("solution", "")
                    initial_ply = puzzle.get("initialPly", 0)
                    puzzle_url_link = f"https://lichess.org/training/{puzzle_id}"
                    
                    # Derive FEN from game PGN + initialPly
                    fen = ""
                    try:
                        import io

                        import chess.pgn
                        pgn_text = game.get("pgn", "")
                        pgn_io = io.StringIO(pgn_text)
                        pgn_game = chess.pgn.read_game(pgn_io)
                        if pgn_game:
                            board = pgn_game.board()
                            moves = list(pgn_game.mainline_moves())
                            for i, move in enumerate(moves):
                                if i >= initial_ply:
                                    break
                                board.push(move)
                            fen = board.fen()
                            # Lichess board images show from white's perspective
                            # If black to move, flip the board
                            if board.turn == chess.BLACK:
                                fen = board.mirror().fen()
                    except Exception as fen_exc:
                        print(f"Error deriving FEN from PGN: {fen_exc}")
                        log_error("Chess", "fen_derivation", f"FEN parse error: {fen_exc}", f"pgn={pgn_text[:80]}... initialPly={initial_ply}")
                    
                    if not fen:
                        log_error("Chess", "fen_empty", "Empty FEN after derivation", f"pgn={pgn_text[:80]}... initialPly={initial_ply}")
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось отобразить доску. Попробуйте позже.",
                        )
                        return jsonify({"ok": True})
                    
                    # Store pending puzzle for this user
                    _PENDING_PUZZLES[user_id] = {
                        "puzzle_id": puzzle_id,
                        "solution": solution,
                        "rating": rating,
                        "themes": themes,
                        "chat_id": chat_id,
                        "username": account["lichess_username"],
                        "initial_ply": initial_ply,
                    }
                    
                    board_image_url = f"https://lichess1.org/export/fen.gif?fen={fen.replace(' ', '_')}&theme=brown&piece=cburnett"
                    
                    turn = "Белых" if initial_ply % 2 == 0 else "Чёрных"
                    puzzle_msg = (
                        f"🧩 **Шахматная задача**\n\n"
                        f"Рейтинг: {rating}\n"
                        f"Темы: {themes}\n"
                        f"Ход: {turn}\n\n"
                        f"Введите ход в формате UCI (например: `e2e4` или `g1f3`):"
                    )
                    
                    try:
                        photo_response = requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                            json={
                                "chat_id": chat_id,
                                "photo": board_image_url,
                                "caption": puzzle_msg,
                                "parse_mode": "Markdown",
                                "reply_markup": {
                                    "inline_keyboard": [
                                        [
                                            {
                                                "text": "🔗 Решить на Lichess",
                                                "url": puzzle_url_link
                                            }
                                        ]
                                    ]
                                }
                            },
                            timeout=10,
                        )
                        if photo_response.status_code != 200:
                            print(f"Error sending photo: status={photo_response.status_code}, response={photo_response.text}")
                            send_telegram_message(chat_id, puzzle_msg + f"\n\n[Открыть на Lichess]({puzzle_url_link})", parse_mode="Markdown")
                    except Exception as photo_exc:
                        print(f"Error sending photo: {photo_exc}")
                        send_telegram_message(chat_id, puzzle_msg + f"\n\n[Открыть на Lichess]({puzzle_url_link})", parse_mode="Markdown")
                    
                    log_chess_game(user_id, account["lichess_username"], puzzle_id, rating if isinstance(rating, int) else None, themes)
                except Exception as exc:
                    print(f"Error fetching puzzle: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки задачи. Попробуйте позже.",
                    )

        # /chess_history — история решённых задач
        elif command == "/chess_history" and chat_id:
            account = get_chess_account(user_id)
            if not account:
                send_telegram_message(
                    chat_id,
                    "❌ Сначала привяжите Lichess аккаунт: `/chess_link <ник>`",
                    parse_mode="Markdown",
                )
            else:
                try:
                    with get_db_engine().connect() as conn:
                        rows = conn.execute(
                            text(
                                "SELECT puzzle_id, puzzle_rating, puzzle_themes, solved, solved_at, created_at "
                                "FROM chess_games WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 10"
                            ),
                            {"user_id": user_id},
                        ).mappings().all()

                    if not rows:
                        send_telegram_message(
                            chat_id,
                            "📋 У вас пока нет истории задач. Решите первую: /puzzle",
                        )
                    else:
                        coins = get_user_coins(user_id)
                        balance = coins["balance"] if coins else 0
                        lines = [f"📋 **История задач** ({account['lichess_username']})\n💰 Баланс: {balance} монет\n"]
                        for r in rows:
                            status = "✅" if r["solved"] else "⏳"
                            rating = r["puzzle_rating"] or "?"
                            themes = r["puzzle_themes"] or "—"
                            link = f"https://lichess.org/training/{r['puzzle_id']}"
                            lines.append(f"{status} [{r['puzzle_id']}]({link}) | Рейтинг: {rating} | {themes}")
                        send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
                except Exception as exc:
                    print(f"Error fetching chess history: {exc}")
                    log_error("Chess", "history_query", f"chess_history user={user_id}: {exc}", f"query: chess_games WHERE user_id={user_id}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки истории. Попробуйте позже.",
                    )

        # =====================================================================
        # Chess Module — puzzle answer handler
        # =====================================================================
        if chat_id and user_id in _PENDING_PUZZLES and not command.startswith("/"):
            pending = _PENDING_PUZZLES[user_id]
            user_move = msg_text.strip().lower()
            # UCI move validation: 4-5 chars, letters+digits (e.g. e2e4, g1f3, e7e8q)
            import re
            if not re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', user_move):
                return jsonify({"ok": True})
            solution = pending["solution"]
            # Handle both string and list formats
            if isinstance(solution, list):
                solution_moves = solution
            else:
                solution_moves = solution.split()
            
            if solution_moves and user_move == solution_moves[0].lower():
                # Correct move — award coins
                del _PENDING_PUZZLES[user_id]
                update_user_coins(user_id, 5, datetime.utcnow())
                send_telegram_message(
                    chat_id,
                    f"✅ **Правильно!**\n\nХод: `{solution_moves[0]}`\n💰 +5 монет",
                    parse_mode="Markdown",
                )
            else:
                # Wrong move — show correct solution
                correct = solution_moves[0] if solution_moves else "?"
                del _PENDING_PUZZLES[user_id]
                send_telegram_message(
                    chat_id,
                    f"❌ **Неверно.**\n\nПравильный ход: `{correct}`\nПопробуйте следующую задачу: /puzzle",
                    parse_mode="Markdown",
                )
        
        # =====================================================================
        # GD Module — submit follow-up
        # =====================================================================
        if command == "" and chat_id:
            # GD submit — check pending_media submission in DB (survives cold starts)
            pending_sub = None
            try:
                with get_db_engine().connect() as conn:
                    row = conn.execute(
                        text("SELECT id, level_name FROM submissions WHERE user_id = :uid AND status = 'pending_media' ORDER BY submitted_at DESC LIMIT 1"),
                        {"uid": user_id},
                    ).mappings().first()
                    if row:
                        pending_sub = dict(row)
            except Exception as exc:
                print(f"Error fetching pending submission: {exc}")

            if pending_sub:
                sub_id = pending_sub["id"]
                level_name = pending_sub["level_name"]
                media_file_id = None
                media_type = None
                if message.get("photo"):
                    media_file_id = message["photo"][-1].get("file_id", "")
                    media_type = "photo"
                elif message.get("video"):
                    media_file_id = message["video"].get("file_id", "")
                    media_type = "video"
                elif message.get("document"):
                    media_file_id = message["document"].get("file_id", "")
                    media_type = "document"
                else:
                    send_telegram_message(chat_id, "❌ Пожалуйста, отправьте видео или фото с прохождением.")
                    return jsonify({"ok": True})
                try:
                    with get_db_engine().connect() as conn:
                        conn.execute(
                            text("UPDATE submissions SET media_file_id = :mfid, media_type = :mt, status = 'pending', submitted_at = CURRENT_TIMESTAMP WHERE id = :sid"),
                            {"mfid": media_file_id, "mt": media_type, "sid": sub_id},
                        )
                        conn.commit()
                    send_telegram_message(
                        chat_id,
                        f"✅ **Заявка отправлена!**\n\nУровень: **{level_name}**\nСтатус: **Ожидает модерации**\n\nВаша заявка будет рассмотрена администратором.",
                        parse_mode="Markdown",
                    )
                except Exception as exc:
                    print(f"Error updating submission #{sub_id}: {exc}")
                    send_telegram_message(chat_id, "❌ Ошибка при сохранении заявки. Убедитесь, что база данных настроена правильно, и попробуйте ещё раз.")
                    log_error("GD", "submission_save", f"GD submit save failed user={user_id}", "INSERT INTO submissions failed")
                return jsonify({"ok": True})

            # Legacy in-memory fallback
            submit_state = _GD_SUBMIT_STATE.get(user_id)
            if submit_state and submit_state.get("step") == "awaiting_media":
                level_name = submit_state.get("level_name", "")
                media_file_id = None
                media_type = None
                if message.get("photo"):
                    media_file_id = message["photo"][-1].get("file_id", "")
                    media_type = "photo"
                elif message.get("video"):
                    media_file_id = message["video"].get("file_id", "")
                    media_type = "video"
                elif message.get("document"):
                    media_file_id = message["document"].get("file_id", "")
                    media_type = "document"
                else:
                    send_telegram_message(chat_id, "❌ Пожалуйста, отправьте видео или фото с прохождением.")
                    return jsonify({"ok": True})
                sub_id = create_gd_submission(user_id, name, level_name, media_file_id, media_type)
                _GD_SUBMIT_STATE.pop(user_id, None)
                if sub_id:
                    send_telegram_message(
                        chat_id,
                        f"✅ **Заявка отправлена!**\n\nУровень: **{level_name}**\nСтатус: **Ожидает модерации**\n\nВаша заявка будет рассмотрена администратором.",
                        parse_mode="Markdown",
                    )
                else:
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка при сохранении заявки. Убедитесь, что база данных настроена правильно, и попробуйте ещё раз.",
                    )
                return jsonify({"ok": True})

        # =====================================================================
        # GD Module — commands
        # =====================================================================

        # /gd — help
        elif command == "/gd" and chat_id:
            send_telegram_message(
                chat_id,
                "🎮 **Geometry Dash Module**\n\n"
                "**Команды:**\n"
                "`/gd_user <ник>` — инфо об игроке в GD\n"
                "`/gd_level <id/название>` — инфо об уровне GD\n"
                "`/gd_leaderboard` — топ уровней\n"
                "`/my_stats` — моя статистика\n"
                "`/player_stats @user` — статистика игрока\n"
                "`/submit <название>` — отправить прохождение\n"
                "`/moderate` — модерация (админ)\n"
                "`/add_level <название> <позиция>` — добавить уровень (админ)\n"
                "`/set_level_position <id> <позиция>` — изменить позицию (админ)",
                parse_mode="Markdown",
            )

        # /gd_user <username>
        elif command == "/gd_user" and chat_id:
            args = msg_text.split()[1:] if msg_text else []
            if not args:
                send_telegram_message(chat_id, "❌ Использование: `/gd_user <ник>`\nПример: `/gd_user Riot`", parse_mode="Markdown")
            else:
                username = args[0].strip()
                send_telegram_message(chat_id, f"🔍 Ищу игрока **{username}** в Geometry Dash...", parse_mode="Markdown")
                try:
                    data = fetch_gd_user(username)
                    if not data:
                        send_telegram_message(chat_id, f"❌ Игрок **{username}** не найден.", parse_mode="Markdown")
                    else:
                        send_telegram_message(chat_id, format_gd_user_stats(data), parse_mode="Markdown")
                except Exception as exc:
                    print(f"gd_user error: {exc}")
                    send_telegram_message(chat_id, "❌ Ошибка получения данных GD.")
                    log_error("GD", "gd_api", f"GD API user lookup failed: {exc}", f"username={msg_text.split()[1] if len(msg_text.split()) > 1 else '?'}")

        # /gd_level <id или название>
        elif command == "/gd_level" and chat_id:
            args = msg_text.split()[1:] if msg_text else []
            if not args:
                send_telegram_message(chat_id, "❌ Использование: `/gd_level <ID или название>`\nПример: `/gd_level 10565740` или `/gd_level Bloodbath`", parse_mode="Markdown")
            else:
                query = " ".join(args).strip()
                try:
                    level_id = int(query)
                    send_telegram_message(chat_id, f"🔍 Ищу уровень с ID **{level_id}**...", parse_mode="Markdown")
                    data = fetch_gd_level(level_id)
                except ValueError:
                    send_telegram_message(chat_id, f"🔍 Ищу уровень **{query}**...", parse_mode="Markdown")
                    data = search_gd_level(query)
                try:
                    if not data:
                        send_telegram_message(chat_id, f"❌ Уровень **{query}** не найден.", parse_mode="Markdown")
                    else:
                        send_telegram_message(chat_id, format_gd_level_info(data), parse_mode="Markdown")
                except Exception as exc:
                    print(f"gd_level error: {exc}")
                    send_telegram_message(chat_id, "❌ Ошибка получения данных уровня.")
                    log_error("GD", "gd_level_api", f"GD API level lookup failed: {exc}", f"query={msg_text.split()[1] if len(msg_text.split()) > 1 else '?'}")

        # /leaderboard — top by balance
        elif command == "/leaderboard" and chat_id:
            try:
                top = get_top_balances(10)
                if not top:
                    send_telegram_message(chat_id, "📊 Таблица лидеров пока пуста.")
                else:
                    lines = ["🏆 **Таблица лидеров по монетам**\n"]
                    for i, u in enumerate(top, 1):
                        name = u["first_name"] if u["first_name"] != "—" else u["username"]
                        lines.append(f"{i}. **{name}** — 💰 {u['balance']:,} монет")
                    send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
            except Exception as exc:
                print(f"leaderboard error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при загрузке лидеров.")
                log_error("GD", "leaderboard", f"Leaderboard load failed: {exc}", "get_top_balances or get_gd_leaderboard query failed")

        # /gd_leaderboard — GD уровень топ
        elif command == "/gd_leaderboard" and chat_id:
            levels = get_gd_leaderboard(20)
            if not levels:
                send_telegram_message(chat_id, "📊 Топ уровней пуст. Администратор ещё не добавил уровни.")
            else:
                lines = ["🏆 Geometry Dash — Топ-20 уровней\n"]
                for lv in levels:
                    diff = lv.get("difficulty", "Unknown")
                    completers_str = lv.get("completers") or "—"
                    lines.append(f"#{lv['position']} {lv['name']}\n   💀 {diff}\n   ✅ Прохождений: {lv['completions']}\n   👤 {completers_str}")
                lines.append("\nИспользуйте /my_stats для просмотра своей статистики")
                send_telegram_message(chat_id, "\n".join(lines))

        # /my_stats
        elif command == "/my_stats" and chat_id:
            try:
                stats = get_gd_player_stats(user_id)
                if not stats:
                    send_telegram_message(chat_id, "📊 У вас пока нет статистики.\n\nОтправьте своё первое прохождение через /submit!")
                else:
                    sc = get_gd_submission_counts(user_id)
                    hardest = get_gd_hardest_level_name(user_id)
                    completed = get_gd_user_completions_count(user_id)
                    lines = [
                        f"📊 **Статистика {name}**\n",
                        f"🏆 **Хардест:** {hardest}",
                        f"✅ **Подтверждённых прохождений:** {stats.get('total_approved', 0)}",
                        f"📝 **Всего заявок:** {sc['total']}",
                        f"⏳ **На модерации:** {sc['pending']}",
                        f"❌ **Отклонено:** {sc['rejected']}",
                        f"🎮 **Пройдено уровней:** {completed}",
                    ]
                    if sc["total"] > 0:
                        rate = (sc["approved"] / sc["total"]) * 100
                        lines.append(f"📈 **Процент одобрения:** {rate:.1f}%")
                    send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
            except Exception as exc:
                print(f"my_stats error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при загрузке статистики.")
                log_error("GD", "my_stats", f"my_stats load failed user={user_id}: {exc}", "get_gd_player_stats or get_gd_submission_counts failed")

        # /player_stats @username
        elif command == "/player_stats" and chat_id:
            args = msg_text.split()[1:] if msg_text else []
            if not args:
                send_telegram_message(chat_id, "❌ Укажите пользователя: `/player_stats @username`", parse_mode="Markdown")
            else:
                target = args[0].lstrip("@")
                try:
                    with get_db_engine().connect() as conn:
                        target_user = conn.execute(
                            text("SELECT telegram_id FROM users WHERE username ILIKE :un LIMIT 1"),
                            {"un": target},
                        ).mappings().first()
                    if not target_user:
                        send_telegram_message(chat_id, f"📊 Пользователь **{target}** не найден.", parse_mode="Markdown")
                    else:
                        target_id = target_user["telegram_id"]
                        stats = get_gd_player_stats(target_id)
                        if not stats:
                            send_telegram_message(chat_id, f"📊 У пользователя **{target}** пока нет статистики GD.", parse_mode="Markdown")
                        else:
                            hardest = get_gd_hardest_level_name(target_id)
                            completed = get_gd_user_completions_count(target_id)
                            lines = [
                                "📊 **Статистика игрока**\n",
                                f"🏆 **Хардест:** {hardest}",
                                f"✅ **Подтверждённых прохождений:** {stats.get('total_approved', 0)}",
                                f"🎮 **Пройдено уровней:** {completed}",
                            ]
                            send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
                except Exception as exc:
                    print(f"player_stats error: {exc}")
                    send_telegram_message(chat_id, "❌ Ошибка при загрузке статистики игрока.")
                    log_error("GD", "player_stats", f"player_stats load failed: {exc}", f"query player_stats for user in chat {chat_id}")

        # /submit <level_name>
        elif command == "/submit" and chat_id:
            args = msg_text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(chat_id, "❌ Использование: `/submit <название уровня>`\nПример: `/submit Tartarus`", parse_mode="Markdown")
            else:
                level_name = args[1].strip()
                # Create placeholder submission (no media yet)
                sub_id = create_gd_submission(user_id, name, level_name, "", "")
                if not sub_id:
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка при создании заявки. Попробуйте позже.",
                    )
                    return jsonify({"ok": True})
                _GD_SUBMIT_STATE[user_id] = {"step": "awaiting_media", "level_name": level_name}
                send_telegram_message(
                    chat_id,
                    f"🎮 **Geometry Dash — Отправка прохождения**\n\nУровень: **{level_name}**\n\nОтправьте видео или фото с прохождением уровня:",
                )
                return jsonify({"ok": True})

        # /moderate (admin only)
        elif command == "/moderate" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                try:
                    submissions, total = get_gd_pending_submissions(0, 5)
                    if not submissions:
                        send_telegram_message(chat_id, "✅ Все заявки обработаны! Новых заявок нет.")
                    else:
                        total_pages = (total + 4) // 5
                        lines = ["🎮 **Geometry Dash — Модерация заявок**"]
                        lines.append(f"Страница 1/{total_pages} ({total} заявок)\n")
                        for s in submissions:
                            ts_str = str(s.get("submitted_at", ""))[:19] if s.get("submitted_at") else ""
                            lines.append(
                                f"📝 Заявка #{s['id']}\n"
                                f"👤 Пользователь: {s.get('username', s['user_id'])}\n"
                                f"🏆 Уровень: **{s['level_name']}**\n"
                                f"📅 Отправлено: {ts_str}\n"
                                f"📄 Тип: {s.get('media_type', 'media')}\n"
                            )
                        inline_kb = []
                        if total_pages > 1:
                            inline_kb.append([{"text": "➡️ Вперёд", "callback_data": "gd_moderate_page_1"}])
                        inline_kb.append([
                            {"text": "✅ Подтвердить", "callback_data": f"gd_moderate_approve_{submissions[0]['id']}"},
                            {"text": "❌ Отклонить", "callback_data": f"gd_moderate_reject_{submissions[0]['id']}"},
                        ])
                        _GD_MODERATE_STATE[chat_id] = 0
                        send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown", reply_markup={"inline_keyboard": inline_kb})
                except Exception as exc:
                    print(f"moderate error: {exc}")
                    send_telegram_message(chat_id, "❌ Ошибка при загрузке заявок. Попробуйте позже.")

        # /add_level <name> <position> (admin only)
        elif command == "/add_level" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                args = msg_text.split()
                if len(args) < 3:
                    send_telegram_message(chat_id, "❌ Использование: `/add_level <название> <позиция>`\nПример: `/add_level Tartarus 1`", parse_mode="Markdown")
                else:
                    try:
                        pos = int(args[-1])
                        name = " ".join(args[1:-1])
                        difficulty = get_gd_difficulty_name(name)
                        if add_gd_level(name, pos, difficulty):
                            send_telegram_message(chat_id, f"✅ Уровень **{name}** добавлен на позицию {pos}.", parse_mode="Markdown")
                        else:
                            send_telegram_message(chat_id, "❌ Ошибка при добавлении уровня.")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ Позиция должна быть числом.")

        # /set_level_position <id> <pos> (admin only)
        elif command == "/set_level_position" and chat_id:
            if not check_admin(user_id):
                send_telegram_message(chat_id, "🔒 Нет прав администратора")
            else:
                args = msg_text.split()
                if len(args) < 3:
                    send_telegram_message(chat_id, "❌ Использование: `/set_level_position <id> <позиция>`\nПример: `/set_level_position 1 5`", parse_mode="Markdown")
                else:
                    try:
                        lid = int(args[1])
                        pos = int(args[2])
                        if set_gd_level_position(lid, pos):
                            send_telegram_message(chat_id, f"✅ Позиция уровня #{lid} изменена на {pos}.")
                        else:
                            send_telegram_message(chat_id, "❌ Ошибка при изменении позиции уровня.")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ ID и позиция должны быть числами.")

        # ========== Universe Module ==========
        elif command == "/infect" and chat_id:
            try:
                with get_db_engine().connect() as conn:
                    existing = conn.execute(
                        text("SELECT virus_type, infected_at FROM infection_status WHERE user_id = :uid"),
                        {"uid": user_id},
                    ).mappings().first()
                    if existing and existing["infected_at"]:
                        infected_at = existing["infected_at"]
                        if hasattr(infected_at, "tzinfo") and infected_at.tzinfo is None:
                            from datetime import timezone
                            infected_at = infected_at.replace(tzinfo=timezone.utc)
                        if (datetime.now(timezone.utc) - infected_at) < timedelta(hours=24):
                            send_telegram_message(
                                chat_id,
                                f"🦠 Вы уже заражены «{existing['virus_type']}»!\n"
                                f"Попробуйте `/tea` для облегчения.",
                                parse_mode="Markdown",
                            )
                            return jsonify({"ok": True})
                    virus = random.choice(["олеговирус", "LTL-паразит"])
                    symptoms_oleg = [
                        "кхм-кхм в каждом предложении",
                        "непреодолимое желание писать манифесты",
                        "постоянная потребность поправлять других",
                    ]
                    symptoms_ltl = [
                        "непонятные вспышки смеха",
                        "желание пить чай 24/7",
                        "странные байты в голове",
                    ]
                    symptoms = random.choice(symptoms_oleg if virus == "олеговирус" else symptoms_ltl)
                    conn.execute(
                        text("""
                            INSERT INTO infection_status (user_id, virus_type, infected_at)
                            VALUES (:uid, :vt, NOW())
                            ON CONFLICT (user_id) DO UPDATE SET virus_type = :vt, infected_at = NOW()
                        """),
                        {"uid": user_id, "vt": virus},
                    )
                    conn.commit()
                emoji = "🦠" if virus == "олеговирус" else "🧬"
                send_telegram_message(
                    chat_id,
                    f"{emoji} Вы заражены «{virus}»!\n"
                    f"Симптомы: {symptoms}\n\n"
                    f"Используйте `/tea` для облегчения.",
                    parse_mode="Markdown",
                )
            except Exception as exc:
                print(f"[UNIVERSE] /infect error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при заражении.")

        elif command == "/tea" and chat_id:
            try:
                with get_db_engine().connect() as conn:
                    row = conn.execute(
                        text("SELECT virus_type, tea_cooldown_until FROM infection_status WHERE user_id = :uid"),
                        {"uid": user_id},
                    ).mappings().first()
                    if not row or not row["virus_type"]:
                        send_telegram_message(chat_id, "☕ Вы не заражены. Чай и так поможет!")
                        return jsonify({"ok": True})
                    if row["tea_cooldown_until"]:
                        cooldown = row["tea_cooldown_until"]
                        if hasattr(cooldown, "tzinfo") and cooldown.tzinfo is None:
                            from datetime import timezone
                            cooldown = cooldown.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) < cooldown:
                            remaining = (cooldown - datetime.now(timezone.utc)).seconds // 60
                            send_telegram_message(
                                chat_id,
                                f"☕ Подождите ещё {remaining} мин. до следующего чаепития.",
                            )
                            return jsonify({"ok": True})
                    conn.execute(
                        text("""
                            UPDATE infection_status
                            SET tea_cooldown_until = NOW() + INTERVAL '1 hour'
                            WHERE user_id = :uid
                        """),
                        {"uid": user_id},
                    )
                    conn.commit()
                phrases = [
                    "Чай помогает! Временное облегчение на 1 час.",
                    "Ароматный настой снимает симптомы... пока.",
                    "eight-nine! Чай спасёт вас от вируса.",
                    "Горячий чай — лучшее лекарство. Эффект: 1 час.",
                ]
                send_telegram_message(chat_id, f"☕ {random.choice(phrases)}", parse_mode="Markdown")
            except Exception as exc:
                print(f"[UNIVERSE] /tea error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при чаепитии.")

        elif command == "/daily_prayer" and chat_id:
            try:
                today = date.today().isoformat()
                with get_db_engine().connect() as conn:
                    existing = conn.execute(
                        text("SELECT 1 FROM daily_prayer_log WHERE user_id = :uid AND prayer_date = :d"),
                        {"uid": user_id, "d": today},
                    ).first()
                    if existing:
                        send_telegram_message(
                            chat_id,
                            "🙏 Вы уже получали сегодняшнюю молитву!\nВозвращайтесь завтра.",
                        )
                        return jsonify({"ok": True})
                    prayers = [
                        "Да будет настрой стабилен, а пинг — нулевым.",
                        "О Чай, дай нам мудрости в коде и терпения в дебаге.",
                        "Да будет каждый день наполнен ароматом чая.",
                        "Да будет моя душа чиста, как первозданный настой.",
                        "Да будет кружка-алтарь моей рукой всегда наполнена.",
                        "О Великий Баг, прости нам наши deprecated зависимости.",
                        "Да будет деплой быстрым, а баги — редкими.",
                        "Чай, чай, чай — да будет eight-nine с нами!",
                    ]
                    prayer = random.choice(prayers)
                    conn.execute(
                        text("""
                            INSERT INTO daily_prayer_log (user_id, prayer_date)
                            VALUES (:uid, :d)
                            ON CONFLICT DO NOTHING
                        """),
                        {"uid": user_id, "d": today},
                    )
                    conn.commit()
                send_telegram_message(
                    chat_id,
                    f"🙏 Молитва на сегодня:\n\n_{prayer}_\n\neight-nine!",
                    parse_mode="Markdown",
                )
            except Exception as exc:
                print(f"[UNIVERSE] /daily_prayer error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при получении молитвы.")

        # ── D&D AI Master ──────────────────────────────────────────
        elif command == "/dnd" and chat_id:
            from api.dnd_runtime import cmd_dnd
            send_telegram_message(chat_id, cmd_dnd(user_id, chat_id))
        elif command == "/dnd_start" and chat_id:
            from api.dnd_runtime import cmd_dnd_start
            args = msg_text[len("/dnd_start"):].strip() if len(msg_text) > len("/dnd_start") else ""
            reply = cmd_dnd_start(user_id, chat_id, args)
            send_telegram_message(chat_id, reply)
        elif command == "/dnd_stop" and chat_id:
            from api.dnd_runtime import cmd_dnd_stop
            send_telegram_message(chat_id, cmd_dnd_stop(user_id, chat_id))
        elif command == "/dnd_status" and chat_id:
            from api.dnd_runtime import cmd_dnd_status
            send_telegram_message(chat_id, cmd_dnd_status(user_id, chat_id))
        elif command == "/dnd_roll" and chat_id:
            from api.dnd_runtime import cmd_dnd_roll
            args = msg_text[len("/dnd_roll"):].strip() if len(msg_text) > len("/dnd_roll") else ""
            reply = cmd_dnd_roll(user_id, chat_id, args)
            if reply:
                send_telegram_message(chat_id, reply)
        elif command == "/dnd_fix" and chat_id:
            from api.dnd_runtime import cmd_dnd_fix
            fix_text = msg_text[len("/dnd_fix"):].strip() if len(msg_text) > len("/dnd_fix") else ""
            if not fix_text:
                send_telegram_message(
                    chat_id,
                    "❌ Используйте: /dnd_fix <что нужно исправить>"
                )
            else:
                send_telegram_message(chat_id, cmd_dnd_fix(user_id, chat_id, fix_text))
        # ── end D&D ────────────────────────────────────────────────

    except Exception as e:
        global _last_error
        _last_error = f"WEBHOOK: {type(e).__name__}: {e}"
        print(f"Error processing update: {e}")
        import traceback
        traceback.print_exc()
    return jsonify({"ok": True})


# ============================================================================
# GD Module — moderation callback handler
# ============================================================================

def gd_moderate_callback(callback_query: dict, callback_data: str) -> None:
    """Handle GD moderation inline button callbacks."""
    user = callback_query.get("from", {})
    user_id = user.get("id")
    cq_id = callback_query.get("id")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    try:
        if not user_id or not chat_id:
            return
        parts = callback_data.split("_")
        if len(parts) < 3:
            return
        action = parts[2]
        if action == "page":
            page = int(parts[3])
            _gd_moderate_show_page(callback_query, chat_id, page)
        elif action == "approve":
            sub_id = int(parts[3])
            if not check_admin(user_id):
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": cq_id, "text": "🔒 Нет прав администратора", "show_alert": True},
                    timeout=5,
                )
                return jsonify({"ok": True})
            sub = None
            with get_db_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM submissions WHERE id = :sid AND status='pending'"),
                    {"sid": sub_id},
                ).mappings().first()
                if row:
                    sub = dict(row)
            if not sub:
                send_telegram_message(chat_id, f"❌ Заявка #{sub_id} не найдена.")
                return jsonify({"ok": True})
            level_name = sub["level_name"]
            rec = get_gddl_recommendation(level_name)
            rec_text = f" (рекомендация: **#{rec}**)" if rec else ""
            _GD_APPROVE_STATE[user_id] = {"sub_id": sub_id, "level_name": level_name, "username": sub.get("username", "")}
            send_telegram_message(
                chat_id,
                f"📝 Заявка #{sub_id}: уровень **{level_name}**{rec_text}\n\n"
                f"Введите позицию в топе (число):",
                parse_mode="Markdown",
            )
        elif action == "reject":
            sub_id = int(parts[3])
            if not check_admin(user_id):
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": cq_id, "text": "🔒 Нет прав администратора", "show_alert": True},
                    timeout=5,
                )
                return jsonify({"ok": True})
            if reject_gd_submission_db(sub_id, user_id):
                send_telegram_message(chat_id, f"❌ Заявка #{sub_id} отклонена!")
            else:
                send_telegram_message(chat_id, f"❌ Ошибка отклонения заявки #{sub_id}.")
            page = _GD_MODERATE_STATE.get(chat_id, 0)
            _gd_moderate_show_page(callback_query, chat_id, page)
    except Exception as exc:
        print(f"gd_moderate_callback error: {exc}")
    finally:
        if cq_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": cq_id},
                    timeout=5,
                )
            except Exception as cb_err:
                print(f"Error acking gd_moderate callback: {cb_err}")


def _gd_moderate_show_page(callback_query: dict, chat_id: int, page: int) -> None:
    """Edit moderate message to show a new page."""
    try:
        submissions, total = get_gd_pending_submissions(page, 5)
        if not submissions:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": callback_query["message"]["message_id"],
                        "text": "✅ Все заявки обработаны! Новых заявок нет.",
                    },
                    timeout=5,
                )
            except Exception:
                pass
            return
        total_pages = (total + 4) // 5
        lines = ["🎮 **Geometry Dash — Модерация заявок**"]
        lines.append(f"Страница {page + 1}/{total_pages} ({total} заявок)\n")
        for s in submissions:
            ts_str = str(s.get("submitted_at", ""))[:19] if s.get("submitted_at") else ""
            lines.append(
                f"📝 Заявка #{s['id']}\n"
                f"👤 Пользователь: {s.get('username', s['user_id'])}\n"
                f"🏆 Уровень: **{s['level_name']}**\n"
                f"📅 Отправлено: {ts_str}\n"
                f"📄 Тип: {s.get('media_type', 'media')}\n"
            )
        inline_kb = []
        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ Назад", "callback_data": f"gd_moderate_page_{page - 1}"})
        if page < total_pages - 1:
            nav_row.append({"text": "➡️ Вперёд", "callback_data": f"gd_moderate_page_{page + 1}"})
        if nav_row:
            inline_kb.append(nav_row)
        inline_kb.append([
            {"text": "✅ Подтвердить", "callback_data": f"gd_moderate_approve_{submissions[0]['id']}"},
            {"text": "❌ Отклонить", "callback_data": f"gd_moderate_reject_{submissions[0]['id']}"},
        ])
        _GD_MODERATE_STATE[chat_id] = page
        payload = {
            "chat_id": chat_id,
            "message_id": callback_query["message"]["message_id"],
            "text": "\n".join(lines),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": inline_kb},
        }
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
            json=payload,
            timeout=5,
        )
    except Exception as exc:
        print(f"_gd_moderate_show_page error: {exc}")


def trivia_answer_callback(callback_query: dict, callback_data: str) -> None:
    """Handle trivia answer selection."""
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user = callback_query.get("from", {})
    user_id = user.get("id")
    callback_query_id = callback_query.get("id")
    
    try:
        if not user_id:
            print("trivia_callback: no user_id in callback_query")
            return
        
        # Parse callback_data: trivia_{index}_{correct_index}
        parts = callback_data.split("_")
        if len(parts) < 3:
            print(f"trivia_callback: invalid format {callback_data}")
            send_telegram_message(chat_id, "❌ Неверный формат ответа")
            return
        
        try:
            selected_index = int(parts[1])
            correct_index = int(parts[2])
        except ValueError as e:
            print(f"trivia_callback: parse error {e}")
            send_telegram_message(chat_id, "❌ Ошибка парсинга ответа")
            return
        
        print(f"trivia_callback: user_id={user_id}, selected={selected_index}, correct={correct_index}")
        
        if selected_index == correct_index:
            try:
                db = get_db_engine()
                with db.connect() as conn:
                    row = conn.execute(
                        text("SELECT id, balance FROM users WHERE telegram_id = :user_id"),
                        {"user_id": user_id},
                    ).mappings().first()
                    
                    if row:
                        user_db_id = row["id"]
                        new_balance = int(row["balance"]) + 10
                        conn.execute(
                            text("UPDATE users SET balance = :new_balance WHERE id = :user_db_id"),
                            {"new_balance": new_balance, "user_db_id": user_db_id},
                        )
                        conn.execute(
                            text("""
                                INSERT INTO transactions (user_id, amount, transaction_type, description)
                                VALUES (:user_db_id, 10, 'trivia_win', 'Викторина: правильный ответ')
                            """),
                            {"user_db_id": user_db_id},
                        )
                        conn.commit()
                        
                        send_telegram_message(
                            chat_id,
                            f"🎉 Правильно! +10 монет\n💳 Новый баланс: {new_balance}",
                        )
                    else:
                        # Create user if not exists
                        conn.execute(
                            text("""
                                INSERT INTO users (telegram_id, balance, total_earned, first_name, last_name, username, created_at)
                                VALUES (:user_id, 10, 10, :first_name, :last_name, :username, CURRENT_TIMESTAMP)
                            """),
                            {
                                "user_id": user_id,
                                "first_name": user.get("first_name"),
                                "last_name": user.get("last_name"),
                                "username": user.get("username"),
                            },
                        )
                        conn.commit()
                        
                        send_telegram_message(chat_id, "🎉 Правильно! +10 монет")
            except Exception as db_err:
                print(f"Error awarding trivia coins: {db_err}")
                send_telegram_message(chat_id, "❌ Ошибка базы данных. Монеты не начислены.")
        else:
            send_telegram_message(chat_id, "❌ Неправильный ответ")
    except Exception as exc:
        print(f"Error handling trivia answer: {exc}")
    finally:
        # Always ack callback so button stops loading
        bot_token = os.getenv("BOT_TOKEN", "")
        if bot_token and callback_query_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                    json={"callback_query_id": callback_query_id},
                    timeout=5,
                )
            except Exception as cb_err:
                print(f"Error acking callback: {cb_err}")


def generate_trivia_from_canon(chat_id: int) -> str | None:
    """Generate trivia question from canon knowledge using AI.
    
    Returns question string if successful, None if AI unavailable.
    """
    try:
        canon_path = os.path.join(os.path.dirname(__file__), "..", "data", "canon_knowledge.txt")
        canon_content = ""
        
        if os.path.exists(canon_path):
            with open(canon_path, "r", encoding="utf-8") as f:
                canon_content = f.read()[:5000]
        
        prompt = (
            "Ты — создатель викторины по вселенной Олеговируса и LTL-паразита.\n\n"
            "Вот контекст из канона (ограниченный фрагмент):\n"
            f"{canon_content[:1500]}\n\n"
            "Создай вопрос-викторину (на русском) с 4 вариантами ответа (A, B, C, D) по этому контексту.\n"
            "Формат ответа ТОЧНО:\n"
            "Вопрос: [вопрос]\n"
            "A) [вариант A]\n"
            "B) [вариант B]\n"
            "C) [вариант C]\n"
            "D) [вариант D]\n"
            "Правильный: [буква правильного ответа]\n"
            "Объяснение: [краткое объяснение]\n\n"
            "Вопрос должен быть сложным, но справедливым, с однозначным правильным ответом."
        )
        
        question = call_ai_api(prompt, max_tokens=300)
        
        # Validate AI response contains required format
        if "Вопрос:" in question and "A)" in question and "Правильный:" in question:
            return question
        else:
            print(f"AI trivia response invalid format: {question[:100]}")
            return None
    except Exception as exc:
        print(f"Error generating trivia from canon: {exc}")
        return None


@app.route("/api/test_ai", methods=["GET"])
def test_ai():
    """Test AI API access from Vercel."""
    try:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            return jsonify({"status": "error", "message": "GROQ_API_KEY not set"})

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "Say hello in one word"}],
                "max_tokens": 10,
            },
            timeout=10,
        )

        return jsonify(
            {
                "status": "success" if response.status_code == 200 else "error",
                "status_code": response.status_code,
                "response": response.json()
                if response.status_code == 200
                else response.text[:500],
            }
        )
    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "error": str(e),
            }
        )


@app.route("/api/test_telegram", methods=["GET"])
def test_telegram():
    """Test Telegram API access from Vercel."""
    result = {"bot_token_set": bool(BOT_TOKEN)}
    try:
        me = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
        result["getMe"] = me.json() if me.ok else me.text[:200]
    except Exception as e:
        result["getMe_error"] = str(e)
    try:
        wh = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
        result["getWebhookInfo"] = wh.json().get("result") if wh.ok else wh.text[:200]
    except Exception as e:
        result["getWebhookInfo_error"] = str(e)
    return jsonify(result)


@app.route("/api/debug_hf", methods=["GET"])
def debug_hf():
    """Debug endpoint to check HF API configuration and connectivity."""
    import requests  # Use requests instead of httpx

    debug_info = {
        "timestamp": "2026-05-31T18:04:00Z",
        "hf_token_exists": bool(
            os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
        ),
        "hf_token_length": len(
            os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN") or ""
        ),
        "models_to_try": [
            "mistralai/Mistral-7B-Instruct-v0.2",
            "google/flan-t5-base",
            "facebook/bart-large-cnn",
        ],
        "test_results": [],
    }

    hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")

    if not hf_token:
        debug_info["error"] = "No HF token found in environment"
        return jsonify(debug_info)

    # Test each model with a simple request
    for model in debug_info["models_to_try"]:
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={
                    "inputs": "Test",
                    "parameters": {"max_new_tokens": 10},
                    "options": {"wait_for_model": True},
                },
                timeout=10.0,
            )

            debug_info["test_results"].append(
                {
                    "model": model,
                    "status_code": response.status_code,
                    "response_preview": response.text[:200]
                    if response.status_code != 200
                    else "OK",
                    "success": response.status_code == 200,
                }
            )
        except Exception as e:
            debug_info["test_results"].append(
                {"model": model, "error": str(e), "success": False}
            )

    return jsonify(debug_info)


@app.route("/api/reading_generate", methods=["POST", "GET"])
def reading_generate():
    """Generate reading msg_text and questions using AI API."""
    try:
        import random

        import requests

        # Try Groq first, then HF as fallback
        groq_key = os.getenv("GROQ_API_KEY")
        hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")

        print(f"Groq key available: {bool(groq_key)}")
        print(f"HF Token available: {bool(hf_token)}")

        if not groq_key and not hf_token:
            print("No API keys, using fallback")
            fallback_sets = get_fallback_sets()
            return jsonify(random.choice(fallback_sets))

        prompt = """Напиши короткую историю для ребёнка 7 лет.

История должна быть про животное или семью.
Используй простые слова.
6 коротких предложений.

Потом напиши 3 простых вопроса по истории с ответами.

Пример формата:
Жил кот Барсик. Он любил молоко. Мама кормила кота. Барсик мурлыкал. Он спал на диване. Кот был добрый.

Вопросы:
1. Как звали кота? Ответ: Барсик
2. Что любил кот? Ответ: молоко
3. Где спал кот? Ответ: на диване

Теперь напиши новую историю:"""

        generated_text = None

        # Try Groq first (faster and more reliable)
        if groq_key:
            try:
                print("Trying Groq API...")
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 300,
                        "temperature": 0.8,
                    },
                    timeout=15.0,
                )

                print(f"Groq API status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    print(f"Groq response: {result}")
                    generated_text = result["choices"][0]["message"]["content"]
                    print(f"Success with Groq! Generated {len(generated_text)} chars")
                else:
                    print(f"Groq failed: {response.text[:200]}")
            except Exception as e:
                print(f"Groq error: {e}")

        # Fallback to HF if Groq failed
        if not generated_text and hf_token:
            try:
                print("Trying HF API as fallback...")
                response = requests.post(
                    "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
                    headers={"Authorization": f"Bearer {hf_token}"},
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 300,
                            "temperature": 0.8,
                            "return_full_text": False,
                        },
                        "options": {"wait_for_model": True},
                    },
                    timeout=30.0,
                )

                print(f"HF API status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    generated_text = (
                        result[0]["generated_text"]
                        if isinstance(result, list)
                        else result.get("generated_text", "")
                    )
                    print(f"Success with HF! Generated {len(generated_text)} chars")
                else:
                    print(f"HF failed: {response.text[:200]}")
            except Exception as e:
                print(f"HF error: {e}")

        if not generated_text:
            print("All AI providers failed, using fallback")
            raise Exception("All AI providers failed")

        print(f"Generated text length: {len(generated_text)}")

        # Parse the generated text
        lines = [line.strip() for line in generated_text.split("\n") if line.strip()]

        # Extract story text (first 6-7 lines before "Вопросы")
        story_lines = []
        questions_section = []
        in_questions = False

        for line in lines:
            if (
                "вопрос" in line.lower()
                or line.startswith("1.")
                or line.startswith("2.")
                or line.startswith("3.")
            ):
                in_questions = True

            if in_questions:
                questions_section.append(line)
            else:
                if len(story_lines) < 7 and len(line) > 10:
                    story_lines.append(line)

        # Build story text
        story_text = (
            " ".join(story_lines[:7])
            if story_lines
            else "Жил-был кот. Он любил играть. Кот был добрый."
        )

        # Extract questions and answers
        import re

        questions = []
        for line in questions_section[:3]:
            # Remove numbering like "1. " or "123. "
            line = re.sub(r"^\d+\.\s*", "", line)
            if "?" in line:
                # Try to extract answer after "Ответ:" or "ответ:"
                match = re.search(r"[Оо]твет[:\s]+(.+)", line)
                if match:
                    answer = match.group(1).strip().rstrip(".")
                    question = line[: line.lower().find("ответ")].strip().rstrip(".")
                else:
                    question = line.strip().rstrip(".")
                    answer = "нет ответа"
                questions.append({"question": question, "answer": answer.lower()})

        # Ensure we have 3 questions
        while len(questions) < 3:
            questions.append({"question": "Что было в истории?", "answer": "—"})

        # Pick random emoji
        emojis = [
            "🐱",
            "🐶",
            "🐰",
            "🐻",
            "🦊",
            "🐸",
            "🏫",
            "🏠",
            "🌳",
            "🐭",
            "🐷",
            "🐮",
        ]
        emoji = random.choice(emojis)

        story_data = {
            "title": f"{emoji} Новая история",
            "image": emoji,
            "text": story_text,
            "questions": questions[:3],
        }

        print(f"Returning story: {story_data['title']}")
        return jsonify(story_data)

    except Exception as e:
        print(f"Error generating reading text: {e}")
        import traceback

        traceback.print_exc()

        # Return fallback set on error
        import random

        fallback_sets = get_fallback_sets()
        return jsonify(random.choice(fallback_sets))


def get_fallback_sets():
    """Return predefined fallback story sets."""
    return [
        {
            "title": "🐱 Кот Мурзик",
            "image": "🐱",
            "text": "Жил-был кот Мурзик. Он любил спать на диване. Мама мыла раму. Солнце светило ярко. Дети играли в парке. Папа читал книгу. Бабушка пекла пирог.",
            "questions": [
                {"question": "Как звали кота?", "answer": "мурзик"},
                {"question": "Что делала мама?", "answer": "мыла раму"},
                {"question": "Где играли дети?", "answer": "в парке"},
            ],
        },
        {
            "title": "🐕 Собака Шарик",
            "image": "🐕",
            "text": "Собака Шарик громко лаяла. Птица пела песню на дереве. Дождь шёл сильно. Цветы росли в саду. Машина ехала быстро. Река текла медленно.",
            "questions": [
                {"question": "Как звали собаку?", "answer": "шарик"},
                {"question": "Что делала птица?", "answer": "пела песню"},
                {"question": "Где росли цветы?", "answer": "в саду"},
            ],
        },
        {
            "title": "🎨 В школе",
            "image": "🏫",
            "text": "Мальчик рисовал дом. Девочка пела песню. Учитель писал мелом на доске. Ученик читал текст. Повар готовил суп. Врач лечил людей.",
            "questions": [
                {"question": "Что рисовал мальчик?", "answer": "дом"},
                {"question": "Кто пел песню?", "answer": "девочка"},
                {"question": "Что готовил повар?", "answer": "суп"},
            ],
        },
    ]


@app.route("/api/set_webhook", methods=["GET"])
def set_webhook():
    """Set Telegram webhook to the current Vercel deployment."""
    secret = os.getenv("WEBHOOK_SECRET") or "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266"
    base = request.host_url.rstrip("/")
    webhook_url = f"{base}/telegram/webhook/{secret}"
    drop_pending = request.args.get("drop") == "1"
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={
                "url": webhook_url,
                "secret_token": secret,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": drop_pending,
            },
            timeout=10,
        )
        return jsonify({"set": r.json(), "url": webhook_url, "bot_token_set": bool(BOT_TOKEN)})
    except Exception as e:
        return jsonify({"error": str(e), "url": webhook_url})


@app.route("/api/debug_webhook", methods=["GET"])
def debug_webhook():
    """Debug: check webhook state on Telegram."""
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
        info = r.json().get("result", {})
        return jsonify({
            "token_configured": bool(BOT_TOKEN),
            "secret_len": len(os.getenv("WEBHOOK_SECRET") or ""),
            "webhook_url": info.get("url"),
            "pending_update_count": info.get("pending_update_count"),
            "last_error_message": info.get("last_error_message"),
            "has_custom_certificate": info.get("has_custom_certificate"),
            "max_connections": info.get("max_connections"),
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# Error buffer for diagnostics
_last_error: str | None = None


@app.route("/api/debug_dnd", methods=["GET"])
def debug_dnd():
    """Debug D&D start flow (must pass user_id and optionally chat_id as query params)."""
    try:
        uid = int(request.args.get("user_id", 111))
        cid = int(request.args.get("chat_id", uid))
        from api.dnd_runtime import cmd_dnd_start
        reply = cmd_dnd_start(uid, cid, "diagnostic-campaign")
        return jsonify({"reply": reply, "ok": True, "error": None})
    except Exception as e:
        global _last_error
        _last_error = f"{type(e).__name__}: {e}"
        return jsonify({"reply": None, "ok": False, "error": _last_error})


@app.route("/api/debug_last_error", methods=["GET"])
def debug_last_error():
    return jsonify({"last_error": _last_error})


# Initialize database tables on cold start
try:
    engine = get_db_engine()
    _ensure_gd_tables(engine)
    print("[INIT] GD tables initialized successfully")
except Exception as init_exc:
    print(f"[INIT] GD table init failed: {init_exc}")

# Load bot ID at startup for reply/mention detection
try:
    _load_bot_id()
except Exception as bot_id_exc:
    print(f"[INIT] BOT_ID load failed (will retry on first request): {bot_id_exc}")

# Ensure user_preferences table exists
try:
    _ensure_user_preferences_table(get_db_engine())
except Exception as pref_exc:
    print(f"[INIT] user_preferences table init failed: {pref_exc}")

# Ensure chess_games table exists
try:
    _ensure_chess_games_table(get_db_engine())
except Exception as chess_exc:
    print(f"[INIT] chess_games table init failed: {chess_exc}")

# Debug endpoint to test submissions table
@app.route("/api/debug_db", methods=["GET"])
def debug_db():
    """Debug database and GD tables."""
    result = {"db_url_set": bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("SUPABASE_DB_URL"))}
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            # Check table existence
            tables = []
            for tbl in ["levels", "submissions", "player_stats", "level_completions"]:
                try:
                    conn.execute(text(f"SELECT 1 FROM {tbl} LIMIT 0"))
                    tables.append(f"{tbl}:exists")
                except Exception:
                    tables.append(f"{tbl}:missing")
            result["tables"] = tables
            # Try inserting into submissions
            result_ins = conn.execute(text("INSERT INTO submissions (user_id, username, level_name, status) VALUES (0, 'test', 'test_level', 'pending_media') RETURNING id")).mappings().first()
            conn.commit()
            result["insert_id"] = int(result_ins["id"]) if result_ins else None
            # Cleanup
            conn.execute(text("DELETE FROM submissions WHERE user_id = 0"))
            conn.commit()
            # Check user_preferences table
            try:
                conn.execute(text("SELECT 1 FROM user_preferences LIMIT 0"))
                result["user_preferences"] = "exists"
            except Exception:
                result["user_preferences"] = "missing"
    except Exception as e:
        result["error"] = str(e)
    return jsonify(result)


@app.route("/api/debug_submissions", methods=["GET"])
def debug_submissions():
    """List all submissions for debugging."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, user_id, level_name, status, media_file_id IS NOT NULL AS has_media FROM submissions ORDER BY id DESC LIMIT 20")).mappings().all()
            return jsonify({"submissions": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/debug_addexpense", methods=["GET"])
def debug_addexpense():
    """Show recent /addexpense callers."""
    return jsonify({"calls": list(reversed(_ADDE_LOG))})


# ===== Family Budget Module Routes =====

from bot.budget_parser import parse_expense_line
from bot.web.family_budget import (
    api_balance,
    api_debt_pay,
    api_debts_list,
    api_family_create,
    api_family_join,
    api_family_status,
    api_transaction_create,
    api_transaction_delete,
    api_transactions_list,
    api_vk_link,
    api_vk_status,
    family_budget_page,
)

app.route("/family_budget")(family_budget_page)

app.route("/api/budget/family/status")(api_family_status)
app.route("/api/budget/family/create", methods=["POST"])(api_family_create)
app.route("/api/budget/family/join", methods=["POST"])(api_family_join)

app.route("/api/budget/transactions")(api_transactions_list)
app.route("/api/budget/transactions", methods=["POST"])(api_transaction_create)
app.route("/api/budget/transactions/<int:transaction_id>", methods=["DELETE"])(api_transaction_delete)

app.route("/api/budget/debts")(api_debts_list)
app.route("/api/budget/debts/pay", methods=["POST"])(api_debt_pay)

app.route("/api/budget/balance")(api_balance)

app.route("/api/budget/vk/status")(api_vk_status)
app.route("/api/budget/vk/link", methods=["POST"])(api_vk_link)


@app.route("/api/endings_process", methods=["POST"])
def api_endings_process():
    """Generate fill-in-the-blank endings exercise using AI."""
    try:
        data = request.get_json()
        text = (data or {}).get("text", "").strip()
        if not text or len(text) < 10:
            return jsonify({"ok": False, "error": "Текст слишком короткий (нужно минимум 10 символов)"})

        prompt = f"""You are given a Russian text. Your task: create a JSON structure that marks 5-10 words where the ending should be replaced with a blank in an exercise.

CRITICAL: You MUST NOT change ANY character of the text. Only mark words by splitting them into stem + ending.

For each chosen word, split it into stem (all letters before the ending) and ending (the final 1-4 letters that change by case/gender/number).

Examples from text "Мама мыла раму.":
  "раму" -> {{"b": "рам", "e": "у"}}  (stem="рам", ending="у")
  "мыла" -> {{"b": "мыл", "e": "а"}}

The output must be a list of alternating text segments and blank segments.
- Text segment: {{"t": "original text here unchanged"}}
- Blank segment: {{"b": "stem", "e": "ending"}}

STRICT RULES:
1. NEVER change or rewrite the original text. Every text segment must contain exactly the original characters.
2. Skip words under 5 letters, prepositions, conjunctions, particles, proper names
3. Ending must be at least 1 letter
4. Concatenating all "t" and "b" values (with "e" appended) in order must exactly reconstruct the input text
5. If the text contains double quotes, escape them as \\" in JSON strings

Return ONLY pure JSON array, no markdown, no extra text:
[{{"t":"Мама "}},{{"b":"мыл","e":"а"}},{{"t":" "}},{{"b":"рам","e":"у"}},{{"t":"."}}]

Text: {text}"""

        ai_text = call_ai_api(prompt, max_tokens=3000, temperature=0.1)
        print(f"[ENDINGS] Raw AI response: {ai_text[:200]}")

        import json as _json

        def _parse_endings_json(raw: str) -> list | None:
            cleaned = raw.strip()
            if not cleaned:
                return None
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            try:
                data = _json.loads(cleaned)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    segs = data.get("segments", [])
                    return segs if isinstance(segs, list) else None
                return None
            except _json.JSONDecodeError:
                pass
            for pat in [r'\[.*\{.*"[tb]".*\}\]', r'\{.*"segments"\s*:\s*\[.*\]\}']:
                m = re.search(pat, cleaned, re.DOTALL)
                if m:
                    try:
                        data = _json.loads(m.group())
                        if isinstance(data, list):
                            return data
                        if isinstance(data, dict):
                            return data.get("segments", [])
                        return None
                    except _json.JSONDecodeError:
                        pass
            return None

        raw_segments = _parse_endings_json(ai_text)
        if not raw_segments:
            return jsonify({"ok": False, "error": "AI не смог разобрать текст. Попробуйте ещё раз."})

        # Normalize: support both list format ["t","text"] and dict format {"t":"text"}
        def _to_list(seg):
            if isinstance(seg, list) and len(seg) >= 2:
                return seg
            if isinstance(seg, dict):
                if "t" in seg:
                    return ["t", seg["t"]]
                if "b" in seg and "e" in seg:
                    return ["b", seg["b"], seg["e"]]
            return None

        filtered = []
        for seg in raw_segments:
            item = _to_list(seg)
            if not item:
                continue
            typ = item[0]
            if typ == 't' and item[1]:
                if filtered and filtered[-1][0] == 't':
                    filtered[-1][1] += item[1]
                else:
                    filtered.append(['t', item[1]])
            elif typ == 'b':
                stem = item[1]
                ending = item[2] if len(item) > 2 and item[2] else ''
                if ending:
                    filtered.append(['b', stem, ending])
                else:
                    if filtered and filtered[-1][0] == 't':
                        filtered[-1][1] += stem
                    else:
                        filtered.append(['t', stem])

        blanks = [s for s in filtered if s[0] == 'b']
        if len(blanks) < 2:
            return jsonify({"ok": False, "error": "AI нашёл слишком мало слов для упражнения. Попробуйте другой текст побольше."})

        return jsonify({"ok": True, "segments": filtered, "original": text})

    except _json.JSONDecodeError as e:
        print(f"[ENDINGS] JSON parse error: {e}, raw: {ai_text[:500]}")
        return jsonify({"ok": False, "error": "AI вернул некорректный ответ. Попробуйте ещё раз."})
    except Exception as e:
        print(f"[ENDINGS] Error: {e}")
        return jsonify({"ok": False, "error": str(e)})


# Vercel handler
handler = app
application = app
