"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import io
import json
import os
import random
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, redirect, request
from sqlalchemy import bindparam, create_engine, text

from core.canon import (
    CANON_VERSION,
    find_canon,
    load_canon_text,
    render_markdown,
)
from core.canon.glossary import GLOSSARY_TERMS
from core.canon.prayers import PRAYERS as _PRAYERS
from core.canon.questions import TRIVIA_QUESTIONS as _TRIVIA_QUESTIONS
from core.canon.works import CANON_WORKS
from core.history import EMPERORS as _EMPERORS
from core.history import RULERS as _RULERS
from core.history import EVENTS as _HISTORY_EVENTS
from core.history import PERSONS as _HISTORY_PERSONS


# === Web Auth Helpers ===
# Временный user_id для анонимных пользователей генерируется на фронтенде и хранится в localStorage.
# Backend не хранит состояние для анонимов — валидирует только формат.
# Для привязанных к Telegram аккаунтов используем telegram_id из БД.

_WEB_USER_PREFIX = "web_"
_TELEGRAM_USER_PREFIX = "tg_"

def _generate_web_user_id() -> str:
    """Generate a new anonymous web user ID."""
    return _WEB_USER_PREFIX + uuid.uuid4().hex[:24]

def _is_valid_web_user_id(user_id: str) -> bool:
    """Validate web user ID format."""
    return (
        isinstance(user_id, str) and
        (user_id.startswith(_WEB_USER_PREFIX) or user_id.startswith(_TELEGRAM_USER_PREFIX)) and
        len(user_id) >= 10
    )

def _extract_telegram_id(user_id: str) -> int | None:
    """Extract telegram_id from tg_ prefixed user_id."""
    if user_id.startswith(_TELEGRAM_USER_PREFIX):
        try:
            return int(user_id[len(_TELEGRAM_USER_PREFIX):])
        except ValueError:
            return None
    return None

def _web_user_id_to_int(user_id: str) -> int:
    """Convert web_user_id to int for compatibility with existing code expecting int user_id."""
    if user_id.startswith(_TELEGRAM_USER_PREFIX):
        return _extract_telegram_id(user_id) or 0
    if user_id.startswith(_WEB_USER_PREFIX):
        # Hash the UUID part to int
        h = hashlib.sha256(user_id.encode()).hexdigest()[:12]
        return int(h, 16) % 2000000000
    # Fallback for legacy ai_user_id format
    h = hashlib.sha256(str(user_id).encode()).hexdigest()[:12]
    return int(h, 16) % 2000000000


def _web_user_id(raw: str | None) -> int:
    if not raw:
        return 0
    h = hashlib.sha256(str(raw).encode()).hexdigest()[:12]
    return int(h, 16) % 2000000000


def _hash_password(password: str) -> str:
    """Hash a password with PBKDF2-SHA256 (salt stored in hash)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _create_session(user_id: int) -> str | None:
    """Create a session token for a web user."""
    token = secrets.token_hex(32)
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(
                text("INSERT INTO web_sessions (token, user_id) VALUES (:t, :uid)"),
                {"t": token, "uid": user_id},
            )
            conn.commit()
        return token
    except Exception as exc:
        print(f"[AUTH] create session error: {exc}")
        return None


def _get_session_user(token: str | None) -> dict | None:
    """Resolve a session token to a web user dict, or None."""
    if not token:
        return None
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT u.id, u.login, u.display_name, u.gd_nickname, u.telegram_id, u.lichess_nickname, u.is_admin
                    FROM web_sessions s JOIN web_users u ON u.id = s.user_id
                    WHERE s.token = :t
                """),
                {"t": token},
            ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "login": row["login"],
            "display_name": row["display_name"] or row["login"],
            "gd_nickname": row["gd_nickname"],
            "telegram_id": row["telegram_id"],
            "lichess_nickname": row["lichess_nickname"],
            "is_admin": bool(row["is_admin"]),
        }
    except Exception as exc:
        print(f"[AUTH] get session error: {exc}")
        return None


def _auth_token_from_request() -> str | None:
    """Extract session token from Authorization header or X-Auth-Token."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Auth-Token") or request.args.get("token")


def _web_admin_session() -> dict | None:
    """Resolve current request to a web admin session user, or None."""
    user = _get_session_user(_auth_token_from_request())
    if not user:
        return None
    if not user.get("is_admin"):
        return None
    return user


def _award_web_coins(user_id: int, amount: int, description: str = "") -> bool:
    """Add coins to a web user balance and log the transaction.

    user_id is the web_users.id; the user_coins key for web users is
    _web_user_id("u<id>") (the same hashing used by the chess/GD modules).
    """
    uid = _web_user_id("u" + str(user_id))
    try:
        with get_db_engine().connect() as conn:
            existing = conn.execute(
                text("SELECT user_id FROM user_coins WHERE user_id = :user_id"),
                {"user_id": uid},
            ).mappings().first()
            if existing:
                conn.execute(
                    text("UPDATE user_coins SET balance = balance + :delta WHERE user_id = :user_id"),
                    {"delta": amount, "user_id": uid},
                )
            else:
                conn.execute(
                    text("INSERT INTO user_coins (user_id, balance, last_puzzle_at) VALUES (:user_id, :delta, NOW())"),
                    {"user_id": uid, "delta": amount},
                )
            conn.execute(
                text("INSERT INTO web_coin_log (user_id, amount, description) VALUES (:user_id, :amount, :desc)"),
                {"user_id": uid, "amount": amount, "desc": description},
            )
            conn.commit()
            return True
    except Exception as exc:
        print(f"[ADMIN] award coins error: {exc}")
        return False

app = Flask(__name__)

# CORS for VK Mini App
try:
    from flask_cors import CORS
    CORS(app, resources={r"/api/budget/*": {"origins": ["https://vk.com", "https://*.vk.com"]}})
except ImportError:
    pass

# Centralized light/dark theme injection for all HTML responses
from core.theme import inject_theme

@app.after_request
def _inject_theme_into_response(response):
    ctype = response.headers.get("Content-Type", "")
    if "text/html" in ctype:
        try:
            body = response.get_data(as_text=True)
            response.set_data(inject_theme(body))
        except Exception:
            pass
    return response

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
_PENDING_PUZZLE_TTL = 1800  # seconds; stale entries are lazily pruned
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
        _ensure_family_tables(DB_ENGINE)
        _ensure_web_auth_tables(DB_ENGINE)
        _ensure_parsing_tables(DB_ENGINE)
        _ensure_emperors_tables(DB_ENGINE)
        _ensure_achievements_tables(DB_ENGINE)
        _ensure_chess_games_table(DB_ENGINE)
        try:
            _ensure_canon_tables(DB_ENGINE)
        except Exception as exc:
            print(f"[CANON] table init skipped: {exc}")
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
                    prayer_date DATE NOT NULL,
                    UNIQUE (user_id, prayer_date)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_prayer_log_date ON daily_prayer_log(prayer_date)"))
            try:
                conn.execute(text(
                    "DELETE FROM daily_prayer_log a USING daily_prayer_log b "
                    "WHERE a.user_id = b.user_id AND a.prayer_date = b.prayer_date AND a.rowid > b.rowid"
                ))
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_prayer_log_user_date ON daily_prayer_log(user_id, prayer_date)"
                ))
            except Exception as exc:
                print(f"[UNIVERSE] daily_prayer_log unique index warn: {exc}")
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
                ALTER TABLE dnd_sessions
                    ADD COLUMN IF NOT EXISTS description TEXT,
                    ADD COLUMN IF NOT EXISTS max_players INTEGER DEFAULT 6,
                    ADD COLUMN IF NOT EXISTS current_players INTEGER DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'planning',
                    ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS book_content TEXT,
                    ADD COLUMN IF NOT EXISTS current_scene TEXT,
                    ADD COLUMN IF NOT EXISTS context_summary TEXT,
                    ADD COLUMN IF NOT EXISTS ai_system_prompt TEXT,
                    ADD COLUMN IF NOT EXISTS last_ai_response TEXT,
                    ADD COLUMN IF NOT EXISTS chapter_breakdown TEXT
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


def _ensure_family_tables(engine):
    """Create Family Circle mediation tables if they don't exist (preserves existing data)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    status VARCHAR(20) DEFAULT 'active',
                    participants_total INTEGER NOT NULL DEFAULT 1,
                    spoke_count INTEGER DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS members (
                    id VARCHAR(36) PRIMARY KEY,
                    room_id VARCHAR(20) REFERENCES rooms(id) ON DELETE CASCADE,
                    display_name VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    finished BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_members_room ON members(room_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR(36) PRIMARY KEY,
                    member_id VARCHAR(36) REFERENCES members(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    response TEXT,
                    intent_type VARCHAR(20),
                    needs_extracted TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_member ON messages(member_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS needs (
                    id VARCHAR(36) PRIMARY KEY,
                    room_id VARCHAR(20) REFERENCES rooms(id) ON DELETE CASCADE,
                    need_text TEXT NOT NULL,
                    member_id VARCHAR(36) REFERENCES members(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_needs_room ON needs(room_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS final_reports (
                    id VARCHAR(36) PRIMARY KEY,
                    room_id VARCHAR(20) REFERENCES rooms(id) ON DELETE CASCADE,
                    report_text TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_final_reports_room ON final_reports(room_id)"))
            conn.commit()
        print("[FAMILY] Tables ensured")
    except Exception as exc:
        print(f"[FAMILY] Table init error: {exc}")


def _ensure_web_auth_tables(engine):
    """Create web auth tables (users + sessions) if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
CREATE TABLE IF NOT EXISTS web_users (
    id SERIAL PRIMARY KEY,                 -- 810
    login VARCHAR(64) UNIQUE NOT NULL,   -- 811
    password_hash VARCHAR(255) NOT NULL, -- 812
    display_name VARCHAR(100),           -- 813
    gd_nickname VARCHAR(64),             -- 814
    telegram_id BIGINT,                  -- 815
    lichess_nickname VARCHAR(64),        -- 816
    is_admin BOOLEAN DEFAULT FALSE,      -- 817
    created_at TIMESTAMPTZ DEFAULT NOW(),-- 818
    email VARCHAR(255) UNIQUE            -- email column for authentication
)
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_sessions (
                    token VARCHAR(64) PRIMARY KEY,
                    user_id INTEGER REFERENCES web_users(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_coin_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    amount INTEGER NOT NULL,
                    description VARCHAR(255),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_feedback (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    login VARCHAR(64),
                    author_name VARCHAR(100),
                    category VARCHAR(16) NOT NULL,
                    module VARCHAR(64),
                    message TEXT NOT NULL,
                    status VARCHAR(16) DEFAULT 'open',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_sessions_user ON web_sessions(user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_coin_log_user ON web_coin_log(user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_feedback_status ON web_feedback(status)"))
            try:
                conn.execute(text("ALTER TABLE web_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE web_users ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE"))
            except Exception:
                pass
            conn.commit()
        print("[AUTH] Tables ensured")
    except Exception as exc:
        print(f"[AUTH] Table init error: {exc}")


def _html_escape(s: str) -> str:
    """Escape user/DB text for safe embedding in HTML."""
    return html.escape(s or "", quote=True)


def format_bytes(size) -> str:
    """Human-readable размер в байтах."""
    try:
        size = int(size or 0)
    except (TypeError, ValueError):
        size = 0
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size / (1024 * 1024):.1f} МБ"


def _canon_work_to_dict(work) -> dict:
    """Сериализация CanonWork / строки canon_works в JSON-словарь."""
    if hasattr(work, "items"):
        return dict(work)
    return {
        "id": getattr(work, "id", None) or 0,
        "title": getattr(work, "title", "") or "",
        "kind": getattr(work, "kind", "") or "",
        "author": getattr(work, "author", "") or "",
        "date": getattr(work, "date", "") or "",
        "canon_level": getattr(work, "canon_level", "") or "",
        "url": getattr(work, "url", "") or "",
        "content": getattr(work, "content", "") or "",
        "audio_name": getattr(work, "audio_name", None) or None,
        "audio_mime": getattr(work, "audio_mime", None) or None,
        "audio_size": getattr(work, "audio_size", None) or None,
        "has_audio": bool(getattr(work, "audio_data", None)),
    }


def _ensure_canon_tables(engine):
    """Create canon DB tables (works, requests, doc overlay) and seed metadata."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS canon_works (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'track',
                author VARCHAR(100),
                date VARCHAR(50),
                canon_level VARCHAR(16) NOT NULL DEFAULT 'medium',
                url TEXT,
                content TEXT DEFAULT '',
                status VARCHAR(16) NOT NULL DEFAULT 'approved',
                submitted_by INTEGER,
                audio_data BYTEA,
                audio_name VARCHAR(255),
                audio_mime VARCHAR(100),
                audio_size INTEGER,
                view_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        # ALTER-дополнения для уже существующей прод-таблицы (Supabase).
        for column_sql in (
            "ADD COLUMN IF NOT EXISTS audio_data BYTEA",
            "ADD COLUMN IF NOT EXISTS audio_name VARCHAR(255)",
            "ADD COLUMN IF NOT EXISTS audio_mime VARCHAR(100)",
            "ADD COLUMN IF NOT EXISTS audio_size INTEGER",
            "ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0",
        ):
            try:
                conn.execute(text(f"ALTER TABLE canon_works {column_sql}"))
            except Exception as exc:
                print(f"[CANON] alter canon_works ({column_sql[:30]}...) skipped: {exc}")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS canon_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                title VARCHAR(200) NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'track',
                author VARCHAR(100),
                date VARCHAR(50),
                canon_level VARCHAR(16) NOT NULL DEFAULT 'medium',
                url TEXT,
                content TEXT DEFAULT '',
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                reviewer_id INTEGER,
                review_note TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS canon_doc (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                updated_by INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_canon_works_status ON canon_works(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_canon_requests_status ON canon_requests(status)"))
        # Сид: если canon_works пуста — влить базовые произведения из core.canon.
        count_row = conn.execute(
            text("SELECT COUNT(*) AS c FROM canon_works")
        ).mappings().first()
        if int(count_row["c"] or 0) == 0:
            for work in CANON_WORKS:
                conn.execute(
                    text("""
                        INSERT INTO canon_works
                            (title, kind, author, date, canon_level, url, content, status)
                        VALUES (:t, :k, :a, :d, :l, :u, '', 'approved')
                    """),
                    {
                        "t": work.title,
                        "k": work.kind,
                        "a": work.author,
                        "d": work.date,
                        "l": work.canon_level,
                        "u": work.url,
                    },
                )
            print("[CANON] Seeded canon_works from core.canon.works")
        conn.commit()


def _ensure_parsing_tables(engine):
    """Create parsing tracking tables if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS parsed_transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    source_bot VARCHAR(50) NOT NULL,
                    original_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    converted_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    currency_type VARCHAR(20),
                    status VARCHAR(16) NOT NULL DEFAULT 'success',
                    chat_id BIGINT,
                    message_id BIGINT,
                    message_text TEXT,
                    parsed_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            try:
                conn.execute(text("ALTER TABLE parsed_transactions ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'success'"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE parsed_transactions ADD COLUMN IF NOT EXISTS chat_id BIGINT"))
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE parsed_transactions ADD COLUMN IF NOT EXISTS message_id BIGINT"))
            except Exception:
                pass
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_parsed_transactions_parsed_at ON parsed_transactions(parsed_at)"))
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_parsed_transactions_msg ON parsed_transactions(chat_id, message_id) WHERE message_id IS NOT NULL"))
            except Exception:
                pass
            _sync_conversion_rates(conn)
            conn.commit()
        print("[PARSING] Tables ensured")
    except Exception as exc:
        print(f"[PARSING] Table init error: {exc}")


def _ensure_emperors_tables(engine):
    """Create Emperors module tables if they don't exist (preserves existing data)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS emperors_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    card_key TEXT NOT NULL,
                    reps INTEGER NOT NULL DEFAULT 0,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    ease REAL NOT NULL DEFAULT 2.5,
                    due REAL NOT NULL DEFAULT 0,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    counter INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """))
            conn.execute(text("ALTER TABLE emperors_progress ADD COLUMN IF NOT EXISTS counter INTEGER NOT NULL DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_emperors_progress_user ON emperors_progress(user_id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_emperors_progress_user_card ON emperors_progress(user_id, card_key)"))
            conn.commit()
        print("[EMPERORS] Tables ensured")
    except Exception as exc:
        print(f"[EMPERORS] Table init error: {exc}")


def _ensure_achievements_tables(engine):
    """Create the unified achievements/streak tables if they don't exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_achievements (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    unlocked_at REAL NOT NULL
                )
            """))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_web_achievements_user_code ON web_achievements(user_id, code)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_achievements_user ON web_achievements(user_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_streak (
                    user_id INTEGER PRIMARY KEY,
                    last_active_day TEXT NOT NULL,
                    current_streak INTEGER NOT NULL DEFAULT 0,
                    longest_streak INTEGER NOT NULL DEFAULT 0,
                    total_active_days INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_activity_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    day TEXT NOT NULL,
                    module TEXT NOT NULL,
                    actions INTEGER NOT NULL DEFAULT 1
                )
            """))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_web_activity_user_day_module ON web_activity_log(user_id, day, module)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_activity_user ON web_activity_log(user_id)"))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS web_events (
                    user_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    updated_at REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, event)
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_web_events_user ON web_events(user_id)"))
            conn.commit()
        print("[ACHIEVEMENTS] Tables ensured")
    except Exception as exc:
        print(f"[ACHIEVEMENTS] Table init error: {exc}")


ACHIEVEMENTS: dict[str, dict] = {
    # --- Первые шаги ---
    "first_step": {"icon": "🚀", "name": "Первый шаг", "desc": "Выполнить любое действие на портале", "module": "system", "weight": 10},
    "first_quiz": {"icon": "🎯", "name": "Первая победа", "desc": "Правильно ответить в любом тренажёре", "module": "system", "weight": 10},
    "first_streak": {"icon": "🔥", "name": "Начало серии", "desc": "Активность 2 дня подряд", "module": "streak", "weight": 10},
    # --- Активность ---
    "first_50_actions": {"icon": "⚡", "name": "Энергичный", "desc": "Выполнить 50 действий на портале", "module": "system", "weight": 10},
    "first_100_actions": {"icon": "⚡", "name": "Продуктивный", "desc": "Выполнить 100 действий на портале", "module": "system", "weight": 10},
    "first_250_actions": {"icon": "⚡", "name": "Трудоголик", "desc": "Выполнить 250 действий на портале", "module": "system", "weight": 10},
    "first_500_actions": {"icon": "🌟", "name": "Активист", "desc": "Выполнить 500 действий на портале", "module": "system", "weight": 10},
    "first_1000_actions": {"icon": "🌟", "name": "Марафонец", "desc": "Выполнить 1000 действий на портале", "module": "system", "weight": 10},
    "first_2500_actions": {"icon": "🌟", "name": "Стахановец", "desc": "Выполнить 2500 действий на портале", "module": "system", "weight": 10},
    "first_5000_actions": {"icon": "🏆", "name": "Гигант", "desc": "Выполнить 5000 действий на портале", "module": "system", "weight": 10},
    # --- Исследователь ---
    "module_2": {"icon": "🧭", "name": "Любознательный", "desc": "Посетить 2 разных модуля", "module": "system", "weight": 10},
    "module_3": {"icon": "🧭", "name": "Исследователь-новичок", "desc": "Посетить 3 разных модуля", "module": "system", "weight": 10},
    "module_4": {"icon": "🧭", "name": "Исследователь-любитель", "desc": "Посетить 4 разных модуля", "module": "system", "weight": 10},
    "module_5": {"icon": "🧭", "name": "Путешественник", "desc": "Посетить 5 разных модулей", "module": "system", "weight": 10},
    "module_6": {"icon": "🧭", "name": "Исследователь-профи", "desc": "Посетить 6 разных модулей", "module": "system", "weight": 10},
    "module_7": {"icon": "🌐", "name": "Коллекционер модулей", "desc": "Посетить 7 разных модулей", "module": "system", "weight": 10},
    "module_8": {"icon": "🌐", "name": "Полиглот портала", "desc": "Посетить 8 разных модулей", "module": "system", "weight": 10},
    "module_9": {"icon": "🌐", "name": "Картограф", "desc": "Посетить 9 разных модулей", "module": "system", "weight": 10},
    "module_10": {"icon": "🌐", "name": "Старожил", "desc": "Посетить 10 разных модулей", "module": "system", "weight": 10},
    "module_11": {"icon": "🚀", "name": "Исследователь", "desc": "Посетить все 11 модулей", "module": "system", "weight": 10},
    "module_12": {"icon": "🚀", "name": "Всезнайка", "desc": "Посетить 12 разных модулей", "module": "system", "weight": 10},
    "module_13": {"icon": "🚀", "name": "Вездесущий", "desc": "Посетить 13 разных модулей", "module": "system", "weight": 10},
    # --- Серии дней ---
    "streak_3": {"icon": "🔥", "name": "Серия 3 дня", "desc": "Активность 3 дня подряд", "module": "streak", "weight": 10},
    "streak_5": {"icon": "🔥", "name": "Серия 5 дней", "desc": "Активность 5 дней подряд", "module": "streak", "weight": 10},
    "streak_7": {"icon": "⚡", "name": "Серия 7 дней", "desc": "Активность 7 дней подряд", "module": "streak", "weight": 10},
    "streak_10": {"icon": "🔥", "name": "Серия 10 дней", "desc": "Активность 10 дней подряд", "module": "streak", "weight": 10},
    "streak_14": {"icon": "🌟", "name": "Серия 14 дней", "desc": "Активность 14 дней подряд", "module": "streak", "weight": 10},
    "streak_20": {"icon": "🔥", "name": "Серия 20 дней", "desc": "Активность 20 дней подряд", "module": "streak", "weight": 10},
    "streak_30": {"icon": "💎", "name": "Серия 30 дней", "desc": "Активность 30 дней подряд", "module": "streak", "weight": 10},
    "streak_45": {"icon": "🌟", "name": "Серия 45 дней", "desc": "Активность 45 дней подряд", "module": "streak", "weight": 10},
    "streak_60": {"icon": "🏆", "name": "Серия 60 дней", "desc": "Активность 60 дней подряд", "module": "streak", "weight": 10},
    "streak_90": {"icon": "🌟", "name": "Серия 90 дней", "desc": "Активность 90 дней подряд", "module": "streak", "weight": 10},
    "streak_100": {"icon": "👑", "name": "Серия 100 дней", "desc": "Активность 100 дней подряд", "module": "streak", "weight": 10},
    "streak_150": {"icon": "💎", "name": "Серия 150 дней", "desc": "Активность 150 дней подряд", "module": "streak", "weight": 10},
    "streak_200": {"icon": "👑", "name": "Серия 200 дней", "desc": "Активность 200 дней подряд", "module": "streak", "weight": 10},
    "streak_250": {"icon": "💎", "name": "Серия 250 дней", "desc": "Активность 250 дней подряд", "module": "streak", "weight": 10},
    "streak_365": {"icon": "🌞", "name": "Год активности", "desc": "Активность 365 дней подряд", "module": "streak", "weight": 10},
    "streak_400": {"icon": "🏆", "name": "Серия 400 дней", "desc": "Активность 400 дней подряд", "module": "streak", "weight": 10},
    "streak_500": {"icon": "🌞", "name": "Полтора года", "desc": "Активность 500 дней подряд", "module": "streak", "weight": 10},
    "streak_750": {"icon": "👑", "name": "Серия 750 дней", "desc": "Активность 750 дней подряд", "module": "streak", "weight": 10},
    "streak_1000": {"icon": "👑", "name": "Серия 1000 дней", "desc": "Активность 1000 дней подряд", "module": "streak", "weight": 10},
    # --- Активные дни (всего) ---
    "days_3": {"icon": "📅", "name": "3 дня на портале", "desc": "Активность в 3 разных днях", "module": "streak", "weight": 10},
    "days_5": {"icon": "📅", "name": "5 дней на портале", "desc": "Активность в 5 разных днях", "module": "streak", "weight": 10},
    "days_7": {"icon": "📅", "name": "Неделя на портале", "desc": "Активность в 7 разных днях", "module": "streak", "weight": 10},
    "days_10": {"icon": "📅", "name": "10 дней на портале", "desc": "Активность в 10 разных днях", "module": "streak", "weight": 10},
    "days_14": {"icon": "📅", "name": "2 недели на портале", "desc": "Активность в 14 разных днях", "module": "streak", "weight": 10},
    "days_20": {"icon": "📅", "name": "20 дней на портале", "desc": "Активность в 20 разных днях", "module": "streak", "weight": 10},
    "days_30": {"icon": "🗓️", "name": "Месяц на портале", "desc": "Активность в 30 разных днях", "module": "streak", "weight": 10},
    "days_45": {"icon": "🗓️", "name": "45 дней на портале", "desc": "Активность в 45 разных днях", "module": "streak", "weight": 10},
    "days_60": {"icon": "🗓️", "name": "2 месяца на портале", "desc": "Активность в 60 разных днях", "module": "streak", "weight": 10},
    "days_89": {"icon": "📅", "name": "Восемь-девять дней", "desc": "Активность в 89 разных днях", "module": "streak", "weight": 10},
    "days_90": {"icon": "🗓️", "name": "90 дней на портале", "desc": "Активность в 90 разных днях", "module": "streak", "weight": 10},
    "days_100": {"icon": "🎖️", "name": "100 дней на портале", "desc": "Активность в 100 разных днях", "module": "streak", "weight": 10},
    "days_150": {"icon": "🎖️", "name": "150 дней на портале", "desc": "Активность в 150 разных днях", "module": "streak", "weight": 10},
    "days_200": {"icon": "🎖️", "name": "200 дней на портале", "desc": "Активность в 200 разных днях", "module": "streak", "weight": 10},
    "days_250": {"icon": "🎖️", "name": "250 дней на портале", "desc": "Активность в 250 разных днях", "module": "streak", "weight": 10},
    "days_365": {"icon": "🏅", "name": "Год на портале", "desc": "Активность в 365 разных днях", "module": "streak", "weight": 10},
    "days_400": {"icon": "🎖️", "name": "400 дней на портале", "desc": "Активность в 400 разных днях", "module": "streak", "weight": 10},
    "days_750": {"icon": "🏅", "name": "750 дней на портале", "desc": "Активность в 750 разных днях", "module": "streak", "weight": 10},
    "days_1000": {"icon": "🏅", "name": "1000 дней на портале", "desc": "Активность в 1000 разных днях", "module": "streak", "weight": 10},
    # --- Тривиа (Викторина) ---
    "trivia_first": {"icon": "🧠", "name": "Первая викторина", "desc": "Ответить на вопрос викторины", "module": "trivia", "weight": 10},
    "trivia_5": {"icon": "🧠", "name": "Начало пути", "desc": "Ответить на 5 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_7": {"icon": "🧠", "name": "Счастливая семёрка", "desc": "Ответить на 7 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_10": {"icon": "🧠", "name": "Знаток викторины", "desc": "Ответить на 10 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_25": {"icon": "🧠", "name": "Викториан-25", "desc": "Ответить на 25 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_50": {"icon": "🧠", "name": "Викториан-50", "desc": "Ответить на 50 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_77": {"icon": "🧠", "name": "Семь семёрок", "desc": "Ответить на 77 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_89": {"icon": "🧠", "name": "Эрудит-89", "desc": "Ответить на 89 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_100": {"icon": "🎓", "name": "Мастер викторины", "desc": "Ответить на 100 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_123": {"icon": "🧠", "name": "Один-два-три", "desc": "Ответить на 123 вопроса викторины", "module": "trivia", "weight": 10},
    "trivia_200": {"icon": "🎓", "name": "Гуру викторины", "desc": "Ответить на 200 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_250": {"icon": "🎓", "name": "Четверть тысячи", "desc": "Ответить на 250 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_500": {"icon": "🏆", "name": "Легенда викторины", "desc": "Ответить на 500 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_666": {"icon": "🧠", "name": "Зловещая эрудиция", "desc": "Ответить на 666 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_777": {"icon": "🎓", "name": "Джекпот эрудиции", "desc": "Ответить на 777 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_999": {"icon": "🏆", "name": "Почти тысяча", "desc": "Ответить на 999 вопросов викторины", "module": "trivia", "weight": 10},
    "trivia_1000": {"icon": "🏆", "name": "Тысяча ответов", "desc": "Ответить на 1000 вопросов викторины", "module": "trivia", "weight": 10},
    # --- Тривиа: серия правильных ---
    "trivia_streak_3": {"icon": "🎯", "name": "Хет-трик", "desc": "Ответить правильно 3 раза подряд", "module": "trivia", "weight": 10},
    "trivia_streak_5": {"icon": "🎯", "name": "Пять подряд", "desc": "Ответить правильно 5 раз подряд", "module": "trivia", "weight": 10},
    "trivia_streak_10": {"icon": "🏅", "name": "Десять подряд", "desc": "Ответить правильно 10 раз подряд", "module": "trivia", "weight": 10},
    # --- Императоры ---
    "emperors_first": {"icon": "👑", "name": "Первые императоры", "desc": "Ответить на вопрос об императорах", "module": "emperors", "weight": 10},
    "emperors_7": {"icon": "👑", "name": "Семь эпох", "desc": "Ответить на 7 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_10": {"icon": "👑", "name": "Историк-новичок", "desc": "Ответить на 10 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_25": {"icon": "👑", "name": "Историк-любитель", "desc": "Ответить на 25 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_50": {"icon": "👑", "name": "Историк-профессионал", "desc": "Ответить на 50 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_77": {"icon": "🏛️", "name": "Летопись-77", "desc": "Ответить на 77 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_89": {"icon": "👑", "name": "Восемь-девять эпох", "desc": "Ответить на 89 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_100": {"icon": "🏛️", "name": "Историк-академик", "desc": "Ответить на 100 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_123": {"icon": "🏛️", "name": "Ровно 123", "desc": "Ответить на 123 вопроса об императорах", "module": "emperors", "weight": 10},
    "emperors_200": {"icon": "🏛️", "name": "Профессор истории", "desc": "Ответить на 200 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_250": {"icon": "🏛️", "name": "Квадрига", "desc": "Ответить на 250 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_333": {"icon": "👑", "name": "Три тройки", "desc": "Ответить на 333 вопроса об императорах", "module": "emperors", "weight": 10},
    "emperors_500": {"icon": "👑", "name": "Хранитель истории", "desc": "Ответить на 500 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_666": {"icon": "👑", "name": "Тьма истории", "desc": "Ответить на 666 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_777": {"icon": "🏆", "name": "Джекпот эпох", "desc": "Ответить на 777 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_999": {"icon": "🏆", "name": "Миллениум", "desc": "Ответить на 999 вопросов об императорах", "module": "emperors", "weight": 10},
    "emperors_1000": {"icon": "👑", "name": "Тысяча вопросов", "desc": "Ответить на 1000 вопросов об императорах", "module": "emperors", "weight": 10},
    # --- Императоры: режимы ---
    "emperors_mode_study": {"icon": "📚", "name": "Изучающий", "desc": "Попробовать режим «Изучить»", "module": "emperors", "weight": 10},
    "emperors_mode_quiz": {"icon": "🧠", "name": "Тренирующийся", "desc": "Попробовать режим «Тренажёр»", "module": "emperors", "weight": 10},
    "emperors_mode_match": {"icon": "🎯", "name": "Сопоставляющий", "desc": "Попробовать режим «Сопоставление»", "module": "emperors", "weight": 10},
    "emperors_mode_chrono": {"icon": "📜", "name": "Хронолог", "desc": "Попробовать режим «Хронология»", "module": "emperors", "weight": 10},
    "emperors_all_modes": {"icon": "🌟", "name": "Мастер режимов", "desc": "Попробовать все 4 режима императоров", "module": "emperors", "weight": 10},
    # --- Императоры: освоенные карточки ---
    "emperors_mastered_5": {"icon": "🎖️", "name": "Первые пять", "desc": "Освоить 5 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_10": {"icon": "🎖️", "name": "Десятка", "desc": "Освоить 10 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_25": {"icon": "🎖️", "name": "Двадцать пять", "desc": "Освоить 25 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_50": {"icon": "🏅", "name": "Полсотни", "desc": "Освоить 50 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_100": {"icon": "🏅", "name": "Сотня карточек", "desc": "Освоить 100 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_150": {"icon": "🏅", "name": "Полтораста", "desc": "Освоить 150 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_200": {"icon": "🏆", "name": "Двести карточек", "desc": "Освоить 200 карточек императоров", "module": "emperors", "weight": 10},
    "emperors_mastered_258": {"icon": "🏆", "name": "Коллекционер эпох", "desc": "Освоить все 258 карточек императоров", "module": "emperors", "weight": 10},
    # --- Чтение ---
    "reading_first": {"icon": "📖", "name": "Первое чтение", "desc": "Проверить первое задание по чтению", "module": "reading", "weight": 10},
    "reading_5": {"icon": "📖", "name": "Читатель-новичок", "desc": "Проверить 5 заданий по чтению", "module": "reading", "weight": 10},
    "reading_7": {"icon": "📖", "name": "Неделя чтения", "desc": "Проверить 7 заданий по чтению", "module": "reading", "weight": 10},
    "reading_10": {"icon": "📖", "name": "Читатель-любитель", "desc": "Проверить 10 заданий по чтению", "module": "reading", "weight": 10},
    "reading_25": {"icon": "📖", "name": "Читатель-профи", "desc": "Проверить 25 заданий по чтению", "module": "reading", "weight": 10},
    "reading_50": {"icon": "📚", "name": "Книжный червь", "desc": "Проверить 50 заданий по чтению", "module": "reading", "weight": 10},
    "reading_77": {"icon": "📖", "name": "Библиофил-77", "desc": "Проверить 77 заданий по чтению", "module": "reading", "weight": 10},
    "reading_89": {"icon": "📖", "name": "Книжник-89", "desc": "Проверить 89 заданий по чтению", "module": "reading", "weight": 10},
    "reading_100": {"icon": "📚", "name": "Библиотекарь", "desc": "Проверить 100 заданий по чтению", "module": "reading", "weight": 10},
    "reading_123": {"icon": "📚", "name": "Книжный клуб", "desc": "Проверить 123 задания по чтению", "module": "reading", "weight": 10},
    "reading_200": {"icon": "📚", "name": "Книжный эксперт", "desc": "Проверить 200 заданий по чтению", "module": "reading", "weight": 10},
    "reading_250": {"icon": "📚", "name": "Читальный зал", "desc": "Проверить 250 заданий по чтению", "module": "reading", "weight": 10},
    "reading_500": {"icon": "📚", "name": "Литературовед", "desc": "Проверить 500 заданий по чтению", "module": "reading", "weight": 10},
    "reading_666": {"icon": "📚", "name": "Чёрная библиотека", "desc": "Проверить 666 заданий по чтению", "module": "reading", "weight": 10},
    "reading_777": {"icon": "📚", "name": "Джекпот чтения", "desc": "Проверить 777 заданий по чтению", "module": "reading", "weight": 10},
    "reading_1000": {"icon": "📚", "name": "Книжный миллионер", "desc": "Проверить 1000 заданий по чтению", "module": "reading", "weight": 10},
    # --- Чтение: серия ---
    "reading_streak_3": {"icon": "🎯", "name": "Читательский хет-трик", "desc": "Правильно выполнить 3 задания подряд", "module": "reading", "weight": 10},
    "reading_streak_5": {"icon": "🎯", "name": "Пять подряд", "desc": "Правильно выполнить 5 заданий подряд", "module": "reading", "weight": 10},
    "reading_streak_10": {"icon": "🏅", "name": "Десять подряд", "desc": "Правильно выполнить 10 заданий подряд", "module": "reading", "weight": 10},
    # --- Глаголы ---
    "verbs_first": {"icon": "🔤", "name": "Первый глагол", "desc": "Выполнить первое упражнение по глаголам", "module": "verbs", "weight": 10},
    "verbs_5": {"icon": "🔤", "name": "Глаголист-новичок", "desc": "Выполнить 5 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_7": {"icon": "🔤", "name": "Неделя глаголов", "desc": "Выполнить 7 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_10": {"icon": "🔤", "name": "Глаголист-любитель", "desc": "Выполнить 10 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_25": {"icon": "🔤", "name": "Глаголист-профи", "desc": "Выполнить 25 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_50": {"icon": "🔠", "name": "Мастер глаголов", "desc": "Выполнить 50 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_77": {"icon": "🔤", "name": "Спряжение-77", "desc": "Выполнить 77 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_89": {"icon": "🔤", "name": "Спряжение-89", "desc": "Выполнить 89 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_100": {"icon": "🔠", "name": "Профессор глаголов", "desc": "Выполнить 100 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_123": {"icon": "🔠", "name": "Все времена", "desc": "Выполнить 123 упражнения по глаголам", "module": "verbs", "weight": 10},
    "verbs_200": {"icon": "🔠", "name": "Легенда глаголов", "desc": "Выполнить 200 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_250": {"icon": "🔠", "name": "Глагольный марафон", "desc": "Выполнить 250 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_500": {"icon": "🔠", "name": "Глагольный эксперт", "desc": "Выполнить 500 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_777": {"icon": "🔠", "name": "Джекпот глаголов", "desc": "Выполнить 777 упражнений по глаголам", "module": "verbs", "weight": 10},
    "verbs_1000": {"icon": "🔠", "name": "Глагольный миллионер", "desc": "Выполнить 1000 упражнений по глаголам", "module": "verbs", "weight": 10},
    # --- Глаголы: серия ---
    "verbs_streak_3": {"icon": "🎯", "name": "Глагольный хет-трик", "desc": "Правильно выполнить 3 упражнения подряд", "module": "verbs", "weight": 10},
    "verbs_streak_5": {"icon": "🎯", "name": "Пять подряд", "desc": "Правильно выполнить 5 упражнений подряд", "module": "verbs", "weight": 10},
    "verbs_streak_10": {"icon": "🏅", "name": "Десять подряд", "desc": "Правильно выполнить 10 упражнений подряд", "module": "verbs", "weight": 10},
    # --- Шахматы ---
    "chess_first": {"icon": "♟️", "name": "Первый ход", "desc": "Решить первый шахматный пазл", "module": "chess", "weight": 10},
    "chess_5": {"icon": "♟️", "name": "Шахматист-новичок", "desc": "Решить 5 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_7": {"icon": "♟️", "name": "Неделя шахмат", "desc": "Решить 7 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_10": {"icon": "♟️", "name": "Шахматист-любитель", "desc": "Решить 10 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_25": {"icon": "♟️", "name": "Шахматист-профи", "desc": "Решить 25 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_50": {"icon": "♞", "name": "Мастер шахмат", "desc": "Решить 50 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_77": {"icon": "♞", "name": "Шахматный скаут", "desc": "Решить 77 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_89": {"icon": "♟️", "name": "Эндшпиль-89", "desc": "Решить 89 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_100": {"icon": "♛", "name": "Гроссмейстер", "desc": "Решить 100 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_150": {"icon": "♞", "name": "Полтораста пазлов", "desc": "Решить 150 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_200": {"icon": "♛", "name": "Чемпион шахмат", "desc": "Решить 200 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_250": {"icon": "♛", "name": "Шахматный марафон", "desc": "Решить 250 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_500": {"icon": "♛", "name": "Гений шахмат", "desc": "Решить 500 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_777": {"icon": "♛", "name": "Джекпот шахмат", "desc": "Решить 777 шахматных пазлов", "module": "chess", "weight": 10},
    "chess_1000": {"icon": "♛", "name": "Шахматный миллионер", "desc": "Решить 1000 шахматных пазлов", "module": "chess", "weight": 10},
    # --- Шахматы: поиск игроков ---
    "chess_search_1": {"icon": "🔍", "name": "Разведчик", "desc": "Впервые найти игрока на Lichess", "module": "chess", "weight": 10},
    "chess_search_10": {"icon": "🔍", "name": "Скаут-10", "desc": "Найти 10 игроков на Lichess", "module": "chess", "weight": 10},
    "chess_search_50": {"icon": "🔍", "name": "Шахматный сыщик", "desc": "Найти 50 игроков на Lichess", "module": "chess", "weight": 10},
    "chess_search_100": {"icon": "🧭", "name": "Поисковик-100", "desc": "Найти 100 игроков на Lichess", "module": "chess", "weight": 10},
    # --- Шахматы: привязка аккаунтов ---
    "chess_link_1": {"icon": "🔗", "name": "Первая связь", "desc": "Привязать аккаунт Lichess", "module": "chess", "weight": 10},
    "chess_link_5": {"icon": "🔗", "name": "Надёжная связь", "desc": "Привязать 5 аккаунтов Lichess", "module": "chess", "weight": 10},
    "chess_link_10": {"icon": "🔗", "name": "Сеть контактов", "desc": "Привязать 10 аккаунтов Lichess", "module": "chess", "weight": 10},
    # --- Канон ---
    "canon_first": {"icon": "📜", "name": "Читатель канона", "desc": "Открыть произведение канона", "module": "canon", "weight": 10},
    "canon_2": {"icon": "📜", "name": "Двойной улов", "desc": "Открыть 2 произведения канона", "module": "canon", "weight": 10},
    "canon_5": {"icon": "📜", "name": "Канонист-новичок", "desc": "Открыть 5 произведений канона", "module": "canon", "weight": 10},
    "canon_6": {"icon": "📜", "name": "Полдюжины", "desc": "Открыть 6 произведений канона", "module": "canon", "weight": 10},
    "canon_10": {"icon": "📜", "name": "Канонист-любитель", "desc": "Открыть 10 произведений канона", "module": "canon", "weight": 10},
    "canon_12": {"icon": "📜", "name": "Дюжина", "desc": "Открыть 12 произведений канона", "module": "canon", "weight": 10},
    "canon_16": {"icon": "📖", "name": "Прочитал весь канон", "desc": "Открыть все 16 произведений канона", "module": "canon", "weight": 10},
    "canon_18": {"icon": "📖", "name": "Восемнадцать", "desc": "Открыть 18 произведений канона", "module": "canon", "weight": 10},
    "canon_20": {"icon": "📖", "name": "Канонист-профи", "desc": "Открыть 20 произведений канона", "module": "canon", "weight": 10},
    "canon_all": {"icon": "🏆", "name": "Хранитель канона", "desc": "Открыть все доступные произведения канона", "module": "canon", "weight": 10},
    # --- Канон: глоссарий ---
    "canon_terms_10": {"icon": "🧩", "name": "Глоссарист", "desc": "Посмотреть 10 терминов глоссария", "module": "canon", "weight": 10},
    "canon_terms_25": {"icon": "🧩", "name": "Словарь-25", "desc": "Посмотреть 25 терминов глоссария", "module": "canon", "weight": 10},
    "canon_terms_50": {"icon": "🧩", "name": "Лексикограф", "desc": "Посмотреть 50 терминов глоссария", "module": "canon", "weight": 10},
    # --- Канон: аудио ---
    "canon_audio_1": {"icon": "🎧", "name": "Первый звук", "desc": "Прослушать произведение канона с аудио", "module": "canon", "weight": 10},
    "canon_audio_5": {"icon": "🎧", "name": "Меломан", "desc": "Прослушать 5 произведений канона с аудио", "module": "canon", "weight": 10},
    # --- Молитва ---
    "prayer_first": {"icon": "🙏", "name": "Первая молитва", "desc": "Прочитать молитву дня", "module": "prayer", "weight": 10},
    "prayer_2": {"icon": "🙏", "name": "Вторая молитва", "desc": "Прочитать молитву 2 дня", "module": "prayer", "weight": 10},
    "prayer_3": {"icon": "🙏", "name": "Три молитвы", "desc": "Прочитать молитву 3 дня", "module": "prayer", "weight": 10},
    "prayer_5": {"icon": "🙏", "name": "Пять дней", "desc": "Прочитать молитву 5 дней", "module": "prayer", "weight": 10},
    "prayer_7": {"icon": "🙏", "name": "Неделя молитвы", "desc": "Прочитать молитву 7 дней", "module": "prayer", "weight": 10},
    "prayer_14": {"icon": "🙏", "name": "Две недели", "desc": "Прочитать молитву 14 дней", "module": "prayer", "weight": 10},
    "prayer_30": {"icon": "🕯️", "name": "Месяц молитвы", "desc": "Прочитать молитву 30 дней", "module": "prayer", "weight": 10},
    "prayer_60": {"icon": "🕯️", "name": "Два месяца", "desc": "Прочитать молитву 60 дней", "module": "prayer", "weight": 10},
    "prayer_89": {"icon": "🍵", "name": "Восемь-девять", "desc": "Прочитать 89 молитв — сакральное число чайной религии", "module": "prayer", "weight": 10},
    "prayer_100": {"icon": "🕯️", "name": "100 молитв", "desc": "Прочитать молитву 100 дней", "module": "prayer", "weight": 10},
    "prayer_150": {"icon": "🕯️", "name": "Пять месяцев", "desc": "Прочитать молитву 150 дней", "module": "prayer", "weight": 10},
    "prayer_200": {"icon": "🕯️", "name": "200 молитв", "desc": "Прочитать молитву 200 дней", "module": "prayer", "weight": 10},
    "prayer_250": {"icon": "🕯️", "name": "250 молитв", "desc": "Прочитать молитву 250 дней", "module": "prayer", "weight": 10},
    "prayer_365": {"icon": "🕯️", "name": "Год молитвы", "desc": "Прочитать молитву 365 дней", "module": "prayer", "weight": 10},
    "prayer_500": {"icon": "🕯️", "name": "500 молитв", "desc": "Прочитать молитву 500 дней", "module": "prayer", "weight": 10},
    "prayer_1000": {"icon": "🕯️", "name": "Тысяча молитв", "desc": "Прочитать молитву 1000 дней", "module": "prayer", "weight": 10},
    # --- GD ---
    "gd_first": {"icon": "🎮", "name": "Первый рекорд", "desc": "Отправить первый рекорд GD", "module": "gd", "weight": 10},
    "gd_5": {"icon": "🎮", "name": "Рекордсмен-новичок", "desc": "Отправить 5 рекордов GD", "module": "gd", "weight": 10},
    "gd_7": {"icon": "🎮", "name": "Неделя рекордов", "desc": "Отправить 7 рекордов GD", "module": "gd", "weight": 10},
    "gd_10": {"icon": "🎮", "name": "Рекордсмен-любитель", "desc": "Отправить 10 рекордов GD", "module": "gd", "weight": 10},
    "gd_25": {"icon": "🎮", "name": "Рекордсмен-профи", "desc": "Отправить 25 рекордов GD", "module": "gd", "weight": 10},
    "gd_50": {"icon": "🕹️", "name": "Легенда GD", "desc": "Отправить 50 рекордов GD", "module": "gd", "weight": 10},
    "gd_77": {"icon": "🎮", "name": "Семь семёрок", "desc": "Отправить 77 рекордов GD", "module": "gd", "weight": 10},
    "gd_89": {"icon": "🎮", "name": "Восемь-девять рекордов", "desc": "Отправить 89 рекордов GD", "module": "gd", "weight": 10},
    "gd_100": {"icon": "🕹️", "name": "Икона GD", "desc": "Отправить 100 рекордов GD", "module": "gd", "weight": 10},
    "gd_150": {"icon": "🕹️", "name": "Полтораста", "desc": "Отправить 150 рекордов GD", "module": "gd", "weight": 10},
    "gd_200": {"icon": "🏆", "name": "Мастер рекордов", "desc": "Отправить 200 рекордов GD", "module": "gd", "weight": 10},
    "gd_250": {"icon": "🕹️", "name": "Рекордный марафон", "desc": "Отправить 250 рекордов GD", "module": "gd", "weight": 10},
    "gd_500": {"icon": "🏆", "name": "Легенда GD", "desc": "Отправить 500 рекордов GD", "module": "gd", "weight": 10},
    "gd_777": {"icon": "🏆", "name": "Джекпот рекордов", "desc": "Отправить 777 рекордов GD", "module": "gd", "weight": 10},
    "gd_1000": {"icon": "🏆", "name": "Рекордный миллионер", "desc": "Отправить 1000 рекордов GD", "module": "gd", "weight": 10},
    # --- D&D ---
    "dnd_first": {"icon": "🎲", "name": "Первая сессия", "desc": "Начать первую D&D сессию", "module": "dnd", "weight": 10},
    "dnd_roll_7": {"icon": "🎲", "name": "Неделя кубиков", "desc": "Сделать 7 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_10": {"icon": "🎲", "name": "Любитель костей", "desc": "Сделать 10 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_30": {"icon": "🎲", "name": "Тридцать бросков", "desc": "Сделать 30 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_50": {"icon": "🎲", "name": "Игрок-ветеран", "desc": "Сделать 50 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_75": {"icon": "🎲", "name": "75 бросков", "desc": "Сделать 75 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_89": {"icon": "🎲", "name": "Восемь-девять кубиков", "desc": "Сделать 89 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_100": {"icon": "🎲", "name": "Мастер бросков", "desc": "Сделать 100 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_150": {"icon": "🎲", "name": "Полтораста бросков", "desc": "Сделать 150 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_200": {"icon": "🎲", "name": "Легенда бросков", "desc": "Сделать 200 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_300": {"icon": "🎲", "name": "Триста бросков", "desc": "Сделать 300 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_500": {"icon": "🎲", "name": "Владыка бросков", "desc": "Сделать 500 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_777": {"icon": "🎲", "name": "Джекпот кубиков", "desc": "Сделать 777 бросков в D&D", "module": "dnd", "weight": 10},
    "dnd_roll_1000": {"icon": "🎲", "name": "Тысяча бросков", "desc": "Сделать 1000 бросков в D&D", "module": "dnd", "weight": 10},
    # --- D&D: критические броски ---
    "dnd_nat20": {"icon": "🎯", "name": "Естественная двадцатка", "desc": "Выбросить 20 на d20 в D&D", "module": "dnd", "weight": 10},
    "dnd_nat1": {"icon": "💀", "name": "Естественная единица", "desc": "Выбросить 1 на d20 в D&D", "module": "dnd", "weight": 10},
    # --- Монеты ---
    "coins_10": {"icon": "💰", "name": "Первые монеты", "desc": "Заработать 10 монет", "module": "coins", "weight": 10},
    "coins_25": {"icon": "💰", "name": "Четвертак", "desc": "Заработать 25 монет", "module": "coins", "weight": 10},
    "coins_50": {"icon": "💰", "name": "Полтинник", "desc": "Заработать 50 монет", "module": "coins", "weight": 10},
    "coins_89": {"icon": "💰", "name": "Чайная казна", "desc": "Заработать 89 монет", "module": "coins", "weight": 10},
    "coins_100": {"icon": "🪙", "name": "Сотня", "desc": "Заработать 100 монет", "module": "coins", "weight": 10},
    "coins_250": {"icon": "💰", "name": "Двести пятьдесят", "desc": "Заработать 250 монет", "module": "coins", "weight": 10},
    "coins_500": {"icon": "💵", "name": "Полтысячи", "desc": "Заработать 500 монет", "module": "coins", "weight": 10},
    "coins_750": {"icon": "💵", "name": "Семь сотен", "desc": "Заработать 750 монет", "module": "coins", "weight": 10},
    "coins_1000": {"icon": "💎", "name": "Тысяча", "desc": "Заработать 1000 монет", "module": "coins", "weight": 10},
    "coins_2500": {"icon": "💎", "name": "Две с половиной", "desc": "Заработать 2500 монет", "module": "coins", "weight": 10},
    "coins_5000": {"icon": "👑", "name": "Казначей", "desc": "Заработать 5000 монет", "module": "coins", "weight": 10},
    "coins_10000": {"icon": "🏦", "name": "Банкир", "desc": "Заработать 10000 монет", "module": "coins", "weight": 10},
    "coins_25000": {"icon": "🏦", "name": "Двадцать пять тысяч", "desc": "Заработать 25000 монет", "module": "coins", "weight": 10},
    "coins_50000": {"icon": "🏆", "name": "Миллиардер", "desc": "Заработать 50000 монет", "module": "coins", "weight": 10},
    "coins_75000": {"icon": "🏆", "name": "Семьдесят пять тысяч", "desc": "Заработать 75000 монет", "module": "coins", "weight": 10},
    "coins_100000": {"icon": "👑", "name": "Легенда монет", "desc": "Заработать 100000 монет", "module": "coins", "weight": 10},
    "coins_500000": {"icon": "👑", "name": "Полмиллиона", "desc": "Заработать 500000 монет", "module": "coins", "weight": 10},
    "coins_1000000": {"icon": "🏆", "name": "Финансовый гений", "desc": "Заработать 1000000 монет", "module": "coins", "weight": 10},
    "coins_10000000": {"icon": "🏆", "name": "Десять миллионов", "desc": "Заработать 10000000 монет", "module": "coins", "weight": 10},
}


def _day_str(dt=None):
    """Return a UTC date string YYYY-MM-DD for the given datetime (or now)."""
    d = dt or datetime.utcnow()
    return d.strftime("%Y-%m-%d")


def _get_streak_row(conn, user_id):
    row = conn.execute(
        text("SELECT * FROM web_streak WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    return row


def _unlock_achievements(conn, user_id, codes, now_ts):
    """Insert newly unlocked codes into web_achievements and return them.

    Pre-reads existing codes to avoid UNIQUE violations (a PostgreSQL
    UniqueViolation would abort the whole transaction, blocking later inserts).
    """
    if not codes:
        return []
    try:
        existing = {
            r["code"]
            for r in conn.execute(
                text("SELECT code FROM web_achievements WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().all()
        }
    except Exception:
        existing = set()
    newly = []
    for code in codes:
        if code not in ACHIEVEMENTS:
            continue
        if code in existing:
            continue
        try:
            conn.execute(
                text("INSERT INTO web_achievements (user_id, code, unlocked_at) VALUES (:u, :c, :t)"),
                {"u": user_id, "c": code, "t": now_ts},
            )
            newly.append(code)
            existing.add(code)
        except Exception:
            # Already unlocked (or DB conflict) — skip silently
            continue
    return newly


def _check_web_achievements(conn, user_id):
    """Evaluate achievement conditions from accumulated facts and unlock new ones.

    Runs inside the caller's transaction (same conn). Returns list of newly
    unlocked achievement codes.
    """
    now = datetime.utcnow()
    now_ts = now.timestamp()
    facts = {}

    # --- streak facts ---
    streak_row = _get_streak_row(conn, user_id)
    facts["current_streak"] = streak_row["current_streak"] if streak_row else 0
    facts["longest_streak"] = streak_row["longest_streak"] if streak_row else 0
    facts["total_active_days"] = streak_row["total_active_days"] if streak_row else 0

    # --- active days / modules facts ---
    day_rows = conn.execute(
        text("SELECT DISTINCT day FROM web_activity_log WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().all()
    facts["active_days"] = len(day_rows)
    module_rows = conn.execute(
        text("SELECT DISTINCT module FROM web_activity_log WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().all()
    facts["modules"] = {r["module"] for r in module_rows}

    # --- per-module action counts ---
    counts = {}
    rows = conn.execute(
        text("""
            SELECT module, SUM(actions) AS total
            FROM web_activity_log WHERE user_id = :user_id
            GROUP BY module
        """),
        {"user_id": user_id},
    ).mappings().all()
    for r in rows:
        counts[r["module"]] = int(r["total"] or 0)
    facts["counts"] = counts

    # --- coins facts ---
    uid = _web_user_id("u" + str(user_id))
    coin_row = conn.execute(
        text("SELECT balance FROM user_coins WHERE user_id = :uid"),
        {"uid": uid},
    ).mappings().first()
    facts["coins"] = int(coin_row["balance"]) if coin_row else 0

    # --- event counters (searches, links, modes, crits, streaks...) ---
    events = {}
    try:
        ev_rows = conn.execute(
            text("SELECT event, count FROM web_events WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).mappings().all()
        for r in ev_rows:
            events[r["event"]] = int(r["count"] or 0)
    except Exception as exc:
        print(f"[ACHIEVEMENTS] events facts error: {exc}")
    facts["events"] = events

    # --- emperors mastered cards (reps >= 3 in the SM-2 progress table) ---
    emastered = 0
    try:
        mrow = conn.execute(
            text("SELECT COUNT(*) AS n FROM emperors_progress WHERE user_id = :uid AND reps >= 3"),
            {"uid": uid},
        ).mappings().first()
        emastered = int(mrow["n"] or 0) if mrow else 0
    except Exception as exc:
        print(f"[ACHIEVEMENTS] emperors mastered fact error: {exc}")
    facts["emperors_mastered"] = emastered

    # --- evaluate conditions ---
    should = []
    c = facts["current_streak"]
    if facts["total_active_days"] >= 1 and facts["active_days"] >= 1:
        should.append("first_step")
    if facts["counts"].get("trivia") or facts["counts"].get("emperors") or facts["counts"].get("reading") or facts["counts"].get("verbs"):
        should.append("first_quiz")
    if c >= 2:
        should.append("first_streak")
    if c >= 3:
        should.append("streak_3")
    if c >= 7:
        should.append("streak_7")
    if c >= 14:
        should.append("streak_14")
    if c >= 30:
        should.append("streak_30")
    if c >= 60:
        should.append("streak_60")
    if c >= 100:
        should.append("streak_100")
    if c >= 200:
        should.append("streak_200")
    if c >= 365:
        should.append("streak_365")
    if c >= 500:
        should.append("streak_500")
    if c >= 5:
        should.append("streak_5")
    if c >= 10:
        should.append("streak_10")
    if c >= 20:
        should.append("streak_20")
    if c >= 45:
        should.append("streak_45")
    if c >= 90:
        should.append("streak_90")
    if c >= 150:
        should.append("streak_150")
    if c >= 250:
        should.append("streak_250")
    if c >= 400:
        should.append("streak_400")
    if c >= 750:
        should.append("streak_750")
    if c >= 1000:
        should.append("streak_1000")
    if facts["active_days"] >= 3:
        should.append("days_3")
    if facts["active_days"] >= 7:
        should.append("days_7")
    if facts["active_days"] >= 14:
        should.append("days_14")
    if facts["active_days"] >= 30:
        should.append("days_30")
    if facts["active_days"] >= 60:
        should.append("days_60")
    if facts["active_days"] >= 100:
        should.append("days_100")
    if facts["active_days"] >= 200:
        should.append("days_200")
    if facts["active_days"] >= 365:
        should.append("days_365")
    if facts["active_days"] >= 5:
        should.append("days_5")
    if facts["active_days"] >= 10:
        should.append("days_10")
    if facts["active_days"] >= 20:
        should.append("days_20")
    if facts["active_days"] >= 45:
        should.append("days_45")
    if facts["active_days"] >= 90:
        should.append("days_90")
    if facts["active_days"] >= 89:
        should.append("days_89")
    if facts["active_days"] >= 150:
        should.append("days_150")
    if facts["active_days"] >= 250:
        should.append("days_250")
    if facts["active_days"] >= 400:
        should.append("days_400")
    if facts["active_days"] >= 750:
        should.append("days_750")
    if facts["active_days"] >= 1000:
        should.append("days_1000")
    nm = len(facts["modules"])
    if nm >= 2:
        should.append("module_2")
    if nm >= 5:
        should.append("module_5")
    if nm >= 8:
        should.append("module_8")
    if nm >= 11:
        should.append("module_11")
    if nm >= 3:
        should.append("module_3")
    if nm >= 4:
        should.append("module_4")
    if nm >= 6:
        should.append("module_6")
    if nm >= 7:
        should.append("module_7")
    if nm >= 9:
        should.append("module_9")
    if nm >= 10:
        should.append("module_10")
    if nm >= 12:
        should.append("module_12")
    if nm >= 13:
        should.append("module_13")
    total_actions = sum(facts["counts"].values())
    if total_actions >= 50:
        should.append("first_50_actions")
    if total_actions >= 100:
        should.append("first_100_actions")
    if total_actions >= 250:
        should.append("first_250_actions")
    if total_actions >= 500:
        should.append("first_500_actions")
    if total_actions >= 1000:
        should.append("first_1000_actions")
    if total_actions >= 2500:
        should.append("first_2500_actions")
    if total_actions >= 5000:
        should.append("first_5000_actions")

    # per-module counts
    trivia = facts["counts"].get("trivia", 0)
    if trivia >= 1:
        should.append("trivia_first")
    if trivia >= 5:
        should.append("trivia_5")
    if trivia >= 10:
        should.append("trivia_10")
    if trivia >= 25:
        should.append("trivia_25")
    if trivia >= 50:
        should.append("trivia_50")
    if trivia >= 89:
        should.append("trivia_89")
    if trivia >= 100:
        should.append("trivia_100")
    if trivia >= 200:
        should.append("trivia_200")
    if trivia >= 500:
        should.append("trivia_500")
    if trivia >= 7:
        should.append("trivia_7")
    if trivia >= 77:
        should.append("trivia_77")
    if trivia >= 123:
        should.append("trivia_123")
    if trivia >= 250:
        should.append("trivia_250")
    if trivia >= 666:
        should.append("trivia_666")
    if trivia >= 777:
        should.append("trivia_777")
    if trivia >= 999:
        should.append("trivia_999")
    if trivia >= 1000:
        should.append("trivia_1000")

    # trivia second scale: correct-answer streak (events)
    ev = facts["events"]
    if ev.get("trivia_streak_3", 0) >= 1:
        should.append("trivia_streak_3")
    if ev.get("trivia_streak_5", 0) >= 1:
        should.append("trivia_streak_5")
    if ev.get("trivia_streak_10", 0) >= 1:
        should.append("trivia_streak_10")

    emperors = facts["counts"].get("emperors", 0)
    if emperors >= 1:
        should.append("emperors_first")
    if emperors >= 10:
        should.append("emperors_10")
    if emperors >= 25:
        should.append("emperors_25")
    if emperors >= 50:
        should.append("emperors_50")
    if emperors >= 89:
        should.append("emperors_89")
    if emperors >= 100:
        should.append("emperors_100")
    if emperors >= 200:
        should.append("emperors_200")
    if emperors >= 500:
        should.append("emperors_500")
    if emperors >= 7:
        should.append("emperors_7")
    if emperors >= 77:
        should.append("emperors_77")
    if emperors >= 123:
        should.append("emperors_123")
    if emperors >= 250:
        should.append("emperors_250")
    if emperors >= 333:
        should.append("emperors_333")
    if emperors >= 666:
        should.append("emperors_666")
    if emperors >= 777:
        should.append("emperors_777")
    if emperors >= 999:
        should.append("emperors_999")
    if emperors >= 1000:
        should.append("emperors_1000")

    # emperors second/third scales: modes tried + mastered cards
    if ev.get("emperors_mode_study", 0) >= 1:
        should.append("emperors_mode_study")
    if ev.get("emperors_mode_quiz", 0) >= 1:
        should.append("emperors_mode_quiz")
    if ev.get("emperors_mode_match", 0) >= 1:
        should.append("emperors_mode_match")
    if ev.get("emperors_mode_chrono", 0) >= 1:
        should.append("emperors_mode_chrono")
    em_modes = sum(1 for m in ("study", "quiz", "match", "chrono") if ev.get("emperors_mode_" + m, 0) >= 1)
    if em_modes >= 4:
        should.append("emperors_all_modes")
    mastered = facts["emperors_mastered"]
    if mastered >= 5:
        should.append("emperors_mastered_5")
    if mastered >= 10:
        should.append("emperors_mastered_10")
    if mastered >= 25:
        should.append("emperors_mastered_25")
    if mastered >= 50:
        should.append("emperors_mastered_50")
    if mastered >= 100:
        should.append("emperors_mastered_100")
    if mastered >= 150:
        should.append("emperors_mastered_150")
    if mastered >= 200:
        should.append("emperors_mastered_200")
    if mastered >= 258:
        should.append("emperors_mastered_258")

    reading = facts["counts"].get("reading", 0)
    if reading >= 1:
        should.append("reading_first")
    if reading >= 5:
        should.append("reading_5")
    if reading >= 10:
        should.append("reading_10")
    if reading >= 25:
        should.append("reading_25")
    if reading >= 50:
        should.append("reading_50")
    if reading >= 89:
        should.append("reading_89")
    if reading >= 100:
        should.append("reading_100")
    if reading >= 200:
        should.append("reading_200")
    if reading >= 500:
        should.append("reading_500")
    if reading >= 7:
        should.append("reading_7")
    if reading >= 77:
        should.append("reading_77")
    if reading >= 123:
        should.append("reading_123")
    if reading >= 250:
        should.append("reading_250")
    if reading >= 666:
        should.append("reading_666")
    if reading >= 777:
        should.append("reading_777")
    if reading >= 1000:
        should.append("reading_1000")
    if ev.get("reading_streak_3", 0) >= 1:
        should.append("reading_streak_3")
    if ev.get("reading_streak_5", 0) >= 1:
        should.append("reading_streak_5")
    if ev.get("reading_streak_10", 0) >= 1:
        should.append("reading_streak_10")

    verbs = facts["counts"].get("verbs", 0)
    if verbs >= 1:
        should.append("verbs_first")
    if verbs >= 5:
        should.append("verbs_5")
    if verbs >= 10:
        should.append("verbs_10")
    if verbs >= 25:
        should.append("verbs_25")
    if verbs >= 50:
        should.append("verbs_50")
    if verbs >= 89:
        should.append("verbs_89")
    if verbs >= 100:
        should.append("verbs_100")
    if verbs >= 200:
        should.append("verbs_200")
    if verbs >= 7:
        should.append("verbs_7")
    if verbs >= 77:
        should.append("verbs_77")
    if verbs >= 123:
        should.append("verbs_123")
    if verbs >= 250:
        should.append("verbs_250")
    if verbs >= 500:
        should.append("verbs_500")
    if verbs >= 777:
        should.append("verbs_777")
    if verbs >= 1000:
        should.append("verbs_1000")
    if ev.get("verbs_streak_3", 0) >= 1:
        should.append("verbs_streak_3")
    if ev.get("verbs_streak_5", 0) >= 1:
        should.append("verbs_streak_5")
    if ev.get("verbs_streak_10", 0) >= 1:
        should.append("verbs_streak_10")

    chess = facts["counts"].get("chess", 0)
    if chess >= 1:
        should.append("chess_first")
    if chess >= 5:
        should.append("chess_5")
    if chess >= 10:
        should.append("chess_10")
    if chess >= 25:
        should.append("chess_25")
    if chess >= 50:
        should.append("chess_50")
    if chess >= 89:
        should.append("chess_89")
    if chess >= 100:
        should.append("chess_100")
    if chess >= 200:
        should.append("chess_200")
    if chess >= 500:
        should.append("chess_500")
    if chess >= 7:
        should.append("chess_7")
    if chess >= 77:
        should.append("chess_77")
    if chess >= 150:
        should.append("chess_150")
    if chess >= 250:
        should.append("chess_250")
    if chess >= 777:
        should.append("chess_777")
    if chess >= 1000:
        should.append("chess_1000")
    # chess second/third scales: player search + account linking (events)
    if ev.get("chess_search", 0) >= 1:
        should.append("chess_search_1")
    if ev.get("chess_search", 0) >= 10:
        should.append("chess_search_10")
    if ev.get("chess_search", 0) >= 50:
        should.append("chess_search_50")
    if ev.get("chess_search", 0) >= 100:
        should.append("chess_search_100")
    if ev.get("chess_link", 0) >= 1:
        should.append("chess_link_1")
    if ev.get("chess_link", 0) >= 5:
        should.append("chess_link_5")
    if ev.get("chess_link", 0) >= 10:
        should.append("chess_link_10")

    canon = facts["counts"].get("canon", 0)
    if canon >= 1:
        should.append("canon_first")
    if canon >= 5:
        should.append("canon_5")
    if canon >= 10:
        should.append("canon_10")
    if canon >= 16:
        should.append("canon_16")
    if canon >= 20:
        should.append("canon_20")
    if canon >= 2:
        should.append("canon_2")
    if canon >= 6:
        should.append("canon_6")
    if canon >= 12:
        should.append("canon_12")
    if canon >= 18:
        should.append("canon_18")
    if canon >= len(CANON_WORKS):
        should.append("canon_all")
    if ev.get("canon_terms", 0) >= 10:
        should.append("canon_terms_10")
    if ev.get("canon_terms", 0) >= 25:
        should.append("canon_terms_25")
    if ev.get("canon_terms", 0) >= 50:
        should.append("canon_terms_50")
    if ev.get("canon_audio", 0) >= 1:
        should.append("canon_audio_1")
    if ev.get("canon_audio", 0) >= 5:
        should.append("canon_audio_5")

    prayer = facts["counts"].get("prayer", 0)
    if prayer >= 1:
        should.append("prayer_first")
    if prayer >= 3:
        should.append("prayer_3")
    if prayer >= 7:
        should.append("prayer_7")
    if prayer >= 30:
        should.append("prayer_30")
    if prayer >= 89:
        should.append("prayer_89")
    if prayer >= 100:
        should.append("prayer_100")
    if prayer >= 200:
        should.append("prayer_200")
    if prayer >= 365:
        should.append("prayer_365")
    if prayer >= 2:
        should.append("prayer_2")
    if prayer >= 5:
        should.append("prayer_5")
    if prayer >= 14:
        should.append("prayer_14")
    if prayer >= 60:
        should.append("prayer_60")
    if prayer >= 150:
        should.append("prayer_150")
    if prayer >= 250:
        should.append("prayer_250")
    if prayer >= 500:
        should.append("prayer_500")
    if prayer >= 1000:
        should.append("prayer_1000")

    gd = facts["counts"].get("gd", 0)
    if gd >= 1:
        should.append("gd_first")
    if gd >= 5:
        should.append("gd_5")
    if gd >= 10:
        should.append("gd_10")
    if gd >= 25:
        should.append("gd_25")
    if gd >= 50:
        should.append("gd_50")
    if gd >= 89:
        should.append("gd_89")
    if gd >= 100:
        should.append("gd_100")
    if gd >= 200:
        should.append("gd_200")
    if gd >= 500:
        should.append("gd_500")
    if gd >= 7:
        should.append("gd_7")
    if gd >= 77:
        should.append("gd_77")
    if gd >= 150:
        should.append("gd_150")
    if gd >= 250:
        should.append("gd_250")
    if gd >= 777:
        should.append("gd_777")
    if gd >= 1000:
        should.append("gd_1000")

    dnd = facts["counts"].get("dnd", 0)
    if dnd >= 1:
        should.append("dnd_first")
    if dnd >= 10:
        should.append("dnd_roll_10")
    if dnd >= 50:
        should.append("dnd_roll_50")
    if dnd >= 89:
        should.append("dnd_roll_89")
    if dnd >= 100:
        should.append("dnd_roll_100")
    if dnd >= 200:
        should.append("dnd_roll_200")
    if dnd >= 500:
        should.append("dnd_roll_500")
    if dnd >= 7:
        should.append("dnd_roll_7")
    if dnd >= 30:
        should.append("dnd_roll_30")
    if dnd >= 75:
        should.append("dnd_roll_75")
    if dnd >= 150:
        should.append("dnd_roll_150")
    if dnd >= 300:
        should.append("dnd_roll_300")
    if dnd >= 777:
        should.append("dnd_roll_777")
    if dnd >= 1000:
        should.append("dnd_roll_1000")
    # dnd second scale: natural crits on d20 (events)
    if ev.get("dnd_nat20", 0) >= 1:
        should.append("dnd_nat20")
    if ev.get("dnd_nat1", 0) >= 1:
        should.append("dnd_nat1")

    coins = facts["coins"]
    if coins >= 10:
        should.append("coins_10")
    if coins >= 50:
        should.append("coins_50")
    if coins >= 89:
        should.append("coins_89")
    if coins >= 100:
        should.append("coins_100")
    if coins >= 500:
        should.append("coins_500")
    if coins >= 1000:
        should.append("coins_1000")
    if coins >= 5000:
        should.append("coins_5000")
    if coins >= 10000:
        should.append("coins_10000")
    if coins >= 50000:
        should.append("coins_50000")
    if coins >= 100000:
        should.append("coins_100000")
    if coins >= 1000000:
        should.append("coins_1000000")
    if coins >= 25:
        should.append("coins_25")
    if coins >= 250:
        should.append("coins_250")
    if coins >= 750:
        should.append("coins_750")
    if coins >= 2500:
        should.append("coins_2500")
    if coins >= 25000:
        should.append("coins_25000")
    if coins >= 75000:
        should.append("coins_75000")
    if coins >= 500000:
        should.append("coins_500000")
    if coins >= 10000000:
        should.append("coins_10000000")

    newly = _unlock_achievements(conn, user_id, should, now_ts)
    if newly:
        conn.commit()
        # award coins for each newly unlocked achievement
        for code in newly:
            _award_web_coins(user_id, ACHIEVEMENTS[code]["weight"], f"Достижение: {ACHIEVEMENTS[code]['name']}")
    return newly


def _record_activity(conn, user_id, module, actions):
    """Record an activity action for a user; updates streak and activity log.

    Streak logic: today's action keeps/extends the streak if the last active
    day was today or yesterday; otherwise the streak resets to 1.
    """
    today = _day_str()
    streak_row = _get_streak_row(conn, user_id)
    last_day = streak_row["last_active_day"] if streak_row else ""
    current = streak_row["current_streak"] if streak_row else 0
    longest = streak_row["longest_streak"] if streak_row else 0
    total = streak_row["total_active_days"] if streak_row else 0

    if last_day == today:
        new_streak = current if current > 0 else 1
    elif _prev_day(today) == last_day:
        new_streak = current + 1
    else:
        new_streak = 1

    if last_day != today:
        total += 1
    longest = max(longest, new_streak)

    conn.execute(
        text("""
            INSERT INTO web_streak (user_id, last_active_day, current_streak, longest_streak, total_active_days)
            VALUES (:uid, :day, :cur, :long, :total)
            ON CONFLICT (user_id) DO UPDATE SET
                last_active_day = :day,
                current_streak = :cur,
                longest_streak = :long,
                total_active_days = :total
        """),
        {"uid": user_id, "day": today, "cur": new_streak, "long": longest, "total": total},
    )

    try:
        conn.execute(
            text("""
                INSERT INTO web_activity_log (user_id, day, module, actions)
                VALUES (:uid, :day, :module, :actions)
                ON CONFLICT (user_id, day, module) DO UPDATE SET
                    actions = web_activity_log.actions + :actions
            """),
            {"uid": user_id, "day": today, "module": module, "actions": actions},
        )
    except Exception as exc:
        print(f"[ACHIEVEMENTS] activity log error: {exc}")
        try:
            conn.execute(
                text("INSERT INTO web_activity_log (user_id, day, module, actions) VALUES (:uid, :day, :module, :actions)"),
                {"uid": user_id, "day": today, "module": module, "actions": actions},
            )
        except Exception:
            pass
    conn.commit()
    return new_streak, longest, total


def _record_events(conn, user_id, events):
    """Increment counters for action-type events (searches, links, modes, crits...).

    Uses INSERT ... ON CONFLICT to be safe against duplicate key races. Runs
    inside the caller's connection; caller commits.
    """
    if not events:
        return
    now = time.time()
    for ev in events:
        ev = str(ev or "").strip()
        if not ev:
            continue
        try:
            conn.execute(
                text("""
                    INSERT INTO web_events (user_id, event, count, updated_at)
                    VALUES (:uid, :ev, 1, :ts)
                    ON CONFLICT (user_id, event) DO UPDATE SET
                        count = web_events.count + 1,
                        updated_at = :ts
                """),
                {"uid": user_id, "ev": ev, "ts": now},
            )
        except Exception as exc:
            print(f"[ACHIEVEMENTS] event log error: {exc}")
            try:
                conn.execute(
                    text("INSERT INTO web_events (user_id, event, count, updated_at) VALUES (:uid, :ev, 1, :ts)"),
                    {"uid": user_id, "ev": ev, "ts": now},
                )
            except Exception:
                pass


def _prev_day(day_str):
    """Return the previous calendar day string for a YYYY-MM-DD string."""
    try:
        d = datetime.strptime(day_str, "%Y-%m-%d")
        return (d - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _sync_conversion_rates(conn):
    """Seed/refresh conversion_rates with canonical values from core.rates.

    Sets k to the canonical value for known bots so both parsing stacks read the
    same single source of truth. Preserves any admin-tweaked rows by only updating
    rows that currently match the old seeded default (1.0).
    """
    try:
        for bot_name, k in BOT_CONVERSION_RATES.items():
            resource_type = PARSING_RESOURCE_TYPES.get(bot_name, bot_name)
            existing = conn.execute(
                text("SELECT k FROM conversion_rates WHERE bot_name = :bn AND resource_type = :rt"),
                {"bn": bot_name, "rt": resource_type},
            ).mappings().first()
            if existing is None:
                conn.execute(
                    text("INSERT INTO conversion_rates (bot_name, resource_type, k) VALUES (:bn, :rt, :k)"),
                    {"bn": bot_name, "rt": resource_type, "k": k},
                )
            elif float(existing["k"]) == 1.0 and float(existing["k"]) != k:
                conn.execute(
                    text("UPDATE conversion_rates SET k = :k WHERE bot_name = :bn AND resource_type = :rt"),
                    {"bn": bot_name, "rt": resource_type, "k": k},
                )
    except Exception as exc:
        print(f"[PARSING] conversion_rates sync error: {exc}")


def _log_parsed_transaction(
    conn,
    user_id: int | None,
    source_bot: str,
    original_amount: float,
    converted_amount: float,
    currency_type: str,
    message_text: str,
    status: str = "success",
    chat_id: int | None = None,
    message_id: int | None = None,
) -> None:
    """Record a parsing attempt (success or failure) in parsed_transactions."""
    try:
        conn.execute(
            text("""
                INSERT INTO parsed_transactions
                    (user_id, source_bot, original_amount, converted_amount, currency_type, status, chat_id, message_id, message_text)
                VALUES (:uid, :bot, :orig, :conv, :curr, :status, :chat_id, :msg_id, :msg)
            """),
            {
                "uid": user_id,
                "bot": source_bot,
                "orig": original_amount,
                "conv": converted_amount,
                "curr": currency_type,
                "status": status,
                "chat_id": chat_id,
                "msg_id": message_id,
                "msg": message_text[:2000],
            },
        )
    except Exception as exc:
        print(f"[PARSING] log parsed_transaction error: {exc}")


def _record_parsing_result(
    user_id: int | None,
    game: str,
    original_amount: float,
    converted_amount: float,
    currency_type: str,
    message_text: str,
    success: bool,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Record a parsing attempt in parsed_transactions (resolves internal user id).

    Returns False if the (chat_id, message_id) pair was already parsed
    (idempotency guard against double accrual on repeated 'парсинг' replies,
    enforced by the UNIQUE index uq_parsed_transactions_msg).
    """
    try:
        internal_id = None
        if user_id:
            with get_db_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT id FROM users WHERE telegram_id = :tid"),
                    {"tid": user_id},
                ).mappings().first()
                internal_id = row["id"] if row else None
        with get_db_engine().connect() as conn:
            _log_parsed_transaction(
                conn,
                internal_id,
                game,
                float(original_amount),
                float(converted_amount),
                currency_type,
                message_text,
                status="success" if success else "failed",
                chat_id=chat_id,
                message_id=message_id,
            )
            conn.commit()
        return True
    except Exception as exc:
        # Duplicate (chat_id, message_id) -> unique index violation
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            return False
        print(f"[PARSING] record parsing result error: {exc}")
        return True


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
        diff = data.get("difficulty")
        if diff:
            return str(diff)
        return data.get("difficultyName", "Unknown")
    except Exception as exc:
        print(f"Error getting difficulty for {level_name}: {exc}")
        return "Unknown"


# ============================================================================
# Geometry Dash Module — Raw SQL Helpers
# ============================================================================

def _gd_norm_name(name: str) -> str:
    """Normalize a level name: lowercase + collapse whitespace + strip."""
    import re
    return re.sub(r"\s+", " ", name or "").strip().lower()


def _gd_pick_canonical_name(name_diffs: list[tuple[str, str]]) -> str:
    """Pick the most canonical level name from (name, difficulty) pairs."""
    best = name_diffs[0]
    for nd in name_diffs[1:]:
        cur_known = (nd[1] or "").strip().lower() != "unknown"
        best_known = (best[1] or "").strip().lower() != "unknown"
        if cur_known and not best_known:
            best = nd
        elif cur_known == best_known:
            if len(nd[0]) > len(best[0]):
                best = nd
            elif len(nd[0]) == len(best[0]) and nd[0] < best[0]:
                best = nd
    return best[0]


def _gd_merge_rows(items: list[dict]) -> dict:
    """Merge duplicate level rows (same normalized name) into one."""
    out = dict(items[0])
    out["completions"] = sum(int(i.get("completions") or 0) for i in items)
    names = []
    seen = set()
    for i in items:
        for n in (str(i.get("completers") or "")).strip("{}").split(","):
            n = n.strip()
            if n and n not in seen:
                seen.add(n)
                names.append(n)
    out["completers"] = ", ".join(names)
    out["position"] = min(int(i.get("position") or 0) for i in items)
    out["id"] = min(int(i.get("id") or 0) for i in items)
    out["name"] = _gd_pick_canonical_name(
        [(str(i.get("name") or ""), str(i.get("difficulty") or "")) for i in items]
    )
    return out


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
                        SELECT lv.id AS level_id,
                               STRING_AGG(DISTINCT COALESCE(NULLIF(u.first_name, ''), u.username, s.username, '?'), ', ') AS completers
                        FROM submissions s
                        JOIN levels lv ON LOWER(TRIM(lv.name)) = LOWER(TRIM(s.level_name))
                        LEFT JOIN users u ON u.telegram_id = s.user_id
                        WHERE s.status = 'approved'
                        GROUP BY lv.id
                    ) u ON u.level_id = l.id
                    ORDER BY l.position ASC
                """),
            ).mappings().all()
            groups: dict[str, list[dict]] = {}
            for r in rows:
                d = dict(r)
                key = _gd_norm_name(d.get("name") or "")
                if key:
                    groups.setdefault(key, []).append(d)
            merged = [_gd_merge_rows(items) for items in groups.values()]
            merged.sort(key=lambda x: int(x.get("position") or 0))
            return merged[:limit]
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


def _update_gd_hardest_level(conn, user_id: int) -> None:
    """Recompute and persist hardest level (MIN position) for a user."""
    try:
        row = conn.execute(
            text("""
                SELECT lc.level_id FROM level_completions lc
                JOIN levels l ON l.id = lc.level_id
                WHERE lc.user_id = :uid
                ORDER BY l.position ASC, lc.completed_at DESC
                LIMIT 1
            """),
            {"uid": user_id},
        ).mappings().first()
        if not row:
            return
        conn.execute(
            text("""
                INSERT INTO player_stats (user_id, hardest_level_id)
                VALUES (:uid, :lid)
                ON CONFLICT (user_id) DO UPDATE SET hardest_level_id = :lid
            """),
            {"uid": user_id, "lid": row["level_id"]},
        )
    except Exception as exc:
        print(f"_update_gd_hardest_level error: {exc}")


def get_gd_hardest_level_name(user_id: int) -> str:
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT l.name, l.position FROM player_stats ps
                    JOIN levels l ON l.id = ps.hardest_level_id
                    WHERE ps.user_id = :uid AND ps.hardest_level_id IS NOT NULL
                """),
                {"uid": user_id},
            ).mappings().first()
            if not row:
                row = conn.execute(
                    text("""
                        SELECT l.name, l.position FROM level_completions lc
                        JOIN levels l ON l.id = lc.level_id
                        WHERE lc.user_id = :uid
                        ORDER BY l.position ASC, lc.completed_at DESC
                        LIMIT 1
                    """),
                    {"uid": user_id},
                ).mappings().first()
            return f"{row['name']} (поз. {row['position']})" if row else "Нет"
    except Exception as exc:
        print(f"get_gd_hardest_level_name error: {exc}")
        return "Нет"


def create_gd_submission(user_id: int, username: str, level_name: str, media_file_id: str, media_type: str, status: str | None = None) -> int | None:
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
                # Create placeholder submission (media pending by default, or explicit status)
                result = conn.execute(
                    text("""
                        INSERT INTO submissions (user_id, username, level_name, status)
                        VALUES (:uid, :un, :ln, :st) RETURNING id
                    """),
                    {"uid": user_id, "un": username, "ln": level_name, "st": status or "pending_media"},
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
                    text("SELECT id FROM levels WHERE LOWER(TRIM(name)) = :key"),
                    {"key": _gd_norm_name(sub["level_name"])},
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
                    _update_gd_hardest_level(conn, sub["user_id"])
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


def _gd_shift_positions(conn, position: int, exclude_id: int | None = None) -> None:
    """Shift all levels with position >= :pos down by 1 to free a slot.

    When exclude_id is set, that level keeps its current slot and only the
    levels below it are moved down. Used so that placing a level in the top
    automatically lowers every level below it by one position.
    """
    if exclude_id is not None:
        conn.execute(
            text("UPDATE levels SET position = position + 1 WHERE position >= :pos AND id != :lid"),
            {"pos": position, "lid": exclude_id},
        )
    else:
        conn.execute(
            text("UPDATE levels SET position = position + 1 WHERE position >= :pos"),
            {"pos": position},
        )


def add_gd_level(name: str, position: int, difficulty: str = "Unknown") -> int | None:
    try:
        with get_db_engine().connect() as conn:
            existing = conn.execute(
                text("SELECT id, position FROM levels WHERE LOWER(TRIM(name)) = :key"),
                {"key": _gd_norm_name(name)},
            ).mappings().first()
            if existing:
                _gd_shift_positions(conn, position, exclude_id=existing["id"])
                conn.execute(
                    text("UPDATE levels SET position=:pos, difficulty=:diff WHERE id=:lid"),
                    {"lid": existing["id"], "pos": position, "diff": difficulty},
                )
                conn.commit()
                return int(existing["id"])
            _gd_shift_positions(conn, position)
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
            _gd_shift_positions(conn, position, exclude_id=level_id)
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


_PUZZLE_COOLDOWN_HOURS = 24


def _puzzle_cooldown_remaining_hours(user_id: int) -> float | None:
    """Оставшиеся часы до следующего пазла (None = можно решать).

    Cooldown 1 пазл в сутки: отсчитывается от последнего решённого пазла
    (last_puzzle_at обновляется при верном ответе).
    """
    try:
        coins_data = get_user_coins(user_id)
    except Exception as exc:
        print(f"Error checking puzzle cooldown: {exc}")
        return None
    if not coins_data or not coins_data.get("last_puzzle_at"):
        return None
    last_puzzle = coins_data["last_puzzle_at"]
    if hasattr(last_puzzle, "tzinfo") and last_puzzle.tzinfo is not None:
        last_puzzle = last_puzzle.replace(tzinfo=None)
    now = datetime.utcnow()
    elapsed = now - last_puzzle
    if elapsed >= timedelta(hours=_PUZZLE_COOLDOWN_HOURS):
        return None
    return _PUZZLE_COOLDOWN_HOURS - elapsed.total_seconds() / 3600


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


def link_chess_account(user_id: int, lichess_username: str, force: bool = False) -> bool:
    """Link or update chess account for user.

    Args:
        user_id: Telegram/web user id.
        lichess_username: Lichess nickname.
        force: if True, take over an account already linked to another user.
    """
    try:
        with get_db_engine().connect() as conn:
            # Check if another user has this lichess account
            existing = conn.execute(
                text("SELECT user_id FROM chess_accounts WHERE lichess_username = :username"),
                {"username": lichess_username},
            ).mappings().first()
            
            if existing and existing["user_id"] != user_id and not force:
                return False
            
            # Check if user already has an account linked
            current = conn.execute(
                text("SELECT user_id FROM chess_accounts WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).mappings().first()
            
            if force and existing:
                # Take over the account linked to another user
                conn.execute(
                    text(
                        "UPDATE chess_accounts SET user_id = :new_user, linked_at = :now WHERE lichess_username = :username"
                    ),
                    {"new_user": user_id, "now": datetime.utcnow(), "username": lichess_username},
                )
            elif current:
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
    """Derive board FEN from puzzle PGN + initialPly.

    The position shown to the solver is reached after `initial_ply + 1`
    half-moves (Lichess `solution[0]` is legal from that position). If black
    is to move, the board is mirrored so black sits at the bottom.
    """
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
            if i >= initial_ply + 1:
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
            "turn": "Белых" if (puzzle.get("initialPly", 0) + 1) % 2 == 0 else "Чёрных",
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





from core.rates import BOT_CONVERSION_RATES, PARSING_RESOURCE_TYPES


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
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <title>LTHub — Сервисы</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 640px; width: 100%; text-align: center; }
        h1 { font-size: 32px; color: var(--bb-text); margin-bottom: 8px; letter-spacing: -0.5px; }
        .subtitle { color: var(--bb-muted); margin-bottom: 32px; font-size: 15px; }
        .cards { display: flex; flex-direction: column; gap: 16px; }
        .section-label { font-size: 13px; color: var(--bb-muted); text-transform: uppercase; letter-spacing: 1px; margin: 24px 0 8px; text-align: left; font-weight: 600; }
        .section-label:first-of-type { margin-top: 0; }
        .beta-toggle { display: flex; align-items: center; justify-content: space-between; gap: 20px; background: var(--bb-panel); padding: 24px; border-radius: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border: 1px solid var(--bb-border); cursor: pointer; transition: all 0.2s; text-align: left; border: none; width: 100%; font-family: inherit; font-size: inherit; border: 1px solid var(--bb-border); }
        .beta-toggle:hover { box-shadow: 0 10px 30px rgba(0,0,0,0.18); transform: translateY(-2px); border-color: var(--bb-primary); }
        .beta-toggle-left { display: flex; align-items: center; gap: 20px; }
        .beta-toggle-icon { font-size: 40px; flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: var(--bb-elev); border-radius: 12px; }
        .beta-toggle-content h2 { font-size: 18px; color: var(--bb-text); margin-bottom: 4px; }
        .beta-toggle-content p { font-size: 14px; color: var(--bb-muted); }
        .beta-toggle-arrow { font-size: 18px; color: var(--bb-dim); transition: transform 0.2s; flex-shrink: 0; }
        .beta-toggle-arrow.open { transform: rotate(90deg); color: var(--bb-primary); }
        .beta-cards { display: none; }
        .beta-cards.open { display: block; }
        .beta-cards .card:first-child { margin-top: 16px; }
        .card { display: flex; align-items: center; gap: 20px; background: var(--bb-panel); padding: 24px; border-radius: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); border: 1px solid var(--bb-border); text-decoration: none; transition: all 0.2s; text-align: left; }
        .card:hover { box-shadow: 0 10px 30px rgba(0,0,0,0.18); transform: translateY(-2px); border-color: var(--bb-primary); }
        .card-icon { font-size: 40px; flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: var(--bb-elev); border-radius: 12px; }
        .card-content h2 { font-size: 18px; color: var(--bb-text); margin-bottom: 4px; }
        .card-content p { font-size: 14px; color: var(--bb-muted); }
        .beta-tag { display: inline-block; font-size: 10px; font-weight: 600; color: var(--bb-orange); background: var(--bb-elev); padding: 1px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle; border: 1px solid var(--bb-border); }
        .card-content h2 span { font-size: 12px; font-weight: 600; color: var(--bb-orange); margin-left: 6px; }
        .user-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--bb-elev); color: var(--bb-text); padding: 12px 20px; border-radius: 12px; margin-bottom: 24px; font-size: 14px; border: 1px solid var(--bb-border); }
        .user-bar .user-info { display: flex; align-items: center; gap: 10px; }
        .user-bar .user-avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--bb-primary); display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; color: var(--bb-panel); flex-shrink: 0; }
        .user-bar .user-name { font-weight: 600; }
        .user-bar .user-sub { font-size: 12px; color: var(--bb-muted); }
        .user-bar a { color: var(--bb-link); text-decoration: none; font-weight: 600; }
        .user-bar a:hover { text-decoration: underline; }
        .user-bar .logout-btn { background: none; border: 1px solid var(--bb-link); color: var(--bb-link); border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 12px; }
        .user-bar .logout-btn:hover { background: var(--bb-link); color: var(--bb-panel); }
        .bug-fab { position: fixed; right: 20px; bottom: 20px; width: 54px; height: 54px; border-radius: 50%; background: var(--bb-primary); color: var(--bb-panel); font-size: 24px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 16px rgba(0,0,0,.4); z-index: 999; text-decoration: none; }
        .bug-fab:hover { background: var(--bb-accent2); transform: scale(1.08); }
        /* Pico pilot: маппинг палитры Pico на переменные темы + правки утечек */
        :root { --pico-border-radius: 16px; --pico-primary: var(--bb-primary); --pico-primary-background: var(--bb-primary); --pico-primary-hover: var(--bb-accent2); --pico-primary-underline: var(--bb-accent2); }
        .user-bar .logout-btn { width: auto; display: inline-block; }
        .card, .card:hover { text-decoration: none; }
        h1, .card-content h2, .beta-toggle-content h2 { margin-top: 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LTHub</h1>
        <p class="subtitle">Выберите сервис</p>
        <div class="user-bar" id="user-bar">
            <div class="user-info">
                <div class="user-avatar" id="user-avatar">?</div>
                <div>
                    <div class="user-name" id="user-name">Загрузка...</div>
                    <div class="user-sub" id="user-sub"></div>
                </div>
            </div>
            <div id="user-actions"></div>
        </div>
        <div class="cards">
            <div class="section-label">Основные</div>
            <a class="card" href="/achievements">
                <div class="card-icon">🏆</div>
                <div class="card-content">
                    <h2>Достижения <span id="ach-count"></span></h2>
                    <p>Ваши награды, серия дней и календарь активности</p>
                </div>
            </a>
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
            <a class="card" href="/chess">
                <div class="card-icon">♟️</div>
                <div class="card-content">
                    <h2>Шахматы</h2>
                    <p>Рейтинги Lichess, поиск игроков, шахматные пазлы</p>
                </div>
            </a>
            <a class="card" href="/daily_prayer">
                <div class="card-icon">🕯️</div>
                <div class="card-content">
                    <h2>Молитва дня</h2>
                    <p>Ежедневная молитва из канона</p>
                </div>
            </a>
            <a class="card" href="/canon">
                <div class="card-icon">📖</div>
                <div class="card-content">
                    <h2>Канон</h2>
                    <p>Полный текст канона, произведения и глоссарий</p>
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
                <a class="card" href="/irregular_verbs">
                    <div class="card-icon">📝</div>
                    <div class="card-content">
                        <h2>Практика глаголов <span class="beta-tag">Бета</span></h2>
                        <p>Практика неправильных глаголов с AI</p>
                    </div>
                </a>
                <a class="card" href="/emperors">
                    <div class="card-icon">👑</div>
                    <div class="card-content">
                        <h2>Императоры России <span class="beta-tag">Бета</span></h2>
                        <p>Шпаргалка и тренажёр: имена и события к императорам</p>
                    </div>
                </a>
                <a class="card" href="/math">
                    <div class="card-icon">💻</div>
                    <div class="card-content">
                        <h2>Информатика — ОГЭ <span class="beta-tag">Бета</span></h2>
                        <p>Теория и тренажёр по информатике (сложность алгоритмов, делители, графы, комбинаторика)</p>
                    </div>
                </a>
                <a class="card" href="/family">
                    <div class="card-icon">🫂</div>
                    <div class="card-content">
                        <h2>Family Circle <span class="beta-tag">Бета</span></h2>
                        <p>Асинхронная семейная медиация с ИИ-помощником</p>
                    </div>
                </a>
                <a class="card" href="/admin">
                    <div class="card-icon">👨‍💼</div>
                    <div class="card-content">
                        <h2>Администрирование <span class="beta-tag">Бета</span></h2>
                        <p>Пользователи, монеты, статистика, ошибки</p>
                    </div>
                </a>
                <a class="card" href="/suggest">
                    <div class="card-icon">💡</div>
                    <div class="card-content">
                        <h2>Предложения</h2>
                        <p>Идеи по улучшению или сообщить о баге</p>
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

                function loadUser() {
                    var uid = localStorage.getItem('web_user_id');
                    var token = localStorage.getItem('web_token');
                    if (!uid || uid.indexOf('tg_') === 0) {
                        uid = 'web_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
                        localStorage.setItem('web_user_id', uid);
                    }
                    var avatar = document.getElementById('user-avatar');
                    var nameEl = document.getElementById('user-name');
                    var subEl = document.getElementById('user-sub');
                    var actionsEl = document.getElementById('user-actions');
                    if (uid.indexOf('u') === 0 && token) {
                        fetch('/api/auth/me', { headers: { 'X-Auth-Token': token } })
                            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
                            .then(function (res) {
                                if (!res.ok) {
                                    localStorage.removeItem('web_token');
                                    localStorage.removeItem('web_user_id');
                                    window.location.reload();
                                    return;
                                }
                                var p = res.j;
                                var name = p.display_name || p.login || 'Пользователь';
                                avatar.textContent = name.charAt(0).toUpperCase();
                                nameEl.textContent = name;
                                subEl.textContent = '@' + p.login;
                                actionsEl.innerHTML = '<a class="logout-btn" href="/account">Личный кабинет</a> <button class="logout-btn" onclick="logout()">Выйти</button>';
                            })
                            .catch(function () {
                                nameEl.textContent = 'Пользователь';
                                subEl.textContent = 'Аккаунт';
                                actionsEl.innerHTML = '<a class="logout-btn" href="/account">Личный кабинет</a> <button class="logout-btn" onclick="logout()">Выйти</button>';
                            });
                    } else {
                        avatar.textContent = uid.slice(4, 5).toUpperCase() || '?';
                        nameEl.textContent = 'Аноним';
                        subEl.textContent = 'Данные хранятся в браузере';
                        actionsEl.innerHTML = '<a href="/login" style="margin-right:10px">Войти</a><a href="/register">Зарегистрироваться</a>';
                    }
                }
                function logout() {
                    var token = localStorage.getItem('web_token');
                    if (token) {
                        fetch('/api/auth/logout', { method: 'POST', headers: { 'X-Auth-Token': token } }).catch(function () {});
                    }
                    localStorage.removeItem('web_user_id');
                    localStorage.removeItem('web_token');
                    window.location.reload();
                }
                function loadAch() {
                    var token = localStorage.getItem('web_token');
                    var uid = localStorage.getItem('web_user_id') || '';
                    var el = document.getElementById('ach-count');
                    if (!token || uid.indexOf('u') !== 0) {
                        var acts = {};
                        try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                        var days = Object.keys(acts).length;
                        el.textContent = '🔥 ' + days + ' дн.';
                        return;
                    }
                    fetch('/api/achievements', { headers: { 'X-Auth-Token': token } })
                        .then(function (r) { return r.json(); })
                        .then(function (d) {
                            if (d.error) return;
                            el.textContent = '🏆 ' + (d.unlocked_count || 0) + '/' + (d.total_count || 0) + ' · 🔥 ' + ((d.streak || {}).current || 0);
                        })
                        .catch(function () {});
                }
                loadUser();
                loadAch();
                window.addEventListener('error', function() { showBugBtn(); });
                window.addEventListener('unhandledrejection', function() { showBugBtn(); });
                function showBugBtn() {
                    var b = document.getElementById('bug-fab');
                    if (b && b.style.display !== 'block') b.style.display = 'block';
                }
            </script>
        </div>
    </div>
    <a id="bug-fab" class="bug-fab" href="/suggest?type=bug&module=hub" title="Сообщить о баге" style="display:none">🐛</a>
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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text); padding: 20px; }
        .container { max-width: 720px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--gh-accent); }
        .header a { color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--gh-accent); }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .tab { flex: 1; padding: 12px; border: 1px solid var(--gh-border); border-radius: 10px; background: var(--gh-panel); color: var(--gh-muted); font-size: 15px; font-family: inherit; cursor: pointer; transition: all 0.15s; }
        .tab:hover { border-color: var(--gh-accent); color: var(--gh-text); }
        .tab.active { background: var(--gh-accent); border-color: var(--gh-accent); color: var(--gh-text2); }
        .card { background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 20px; }
        .panel { display: none; }
        .panel.active { display: block; }
        .input-row { display: flex; gap: 10px; margin-bottom: 16px; }
        .input-row input { flex: 1; padding: 12px; border: 1px solid var(--gh-border); border-radius: 8px; background: var(--gh-bg); color: var(--gh-text); font-size: 15px; font-family: inherit; }
        .input-row input:focus { outline: none; border-color: var(--gh-accent); }
        .file-label { display: block; flex: 1; padding: 12px; border: 1px dashed var(--gh-border); border-radius: 8px; background: var(--gh-bg); color: var(--gh-muted); font-size: 14px; font-family: inherit; cursor: pointer; text-align: center; }
        .file-label.has-file { border-color: var(--gh-accent); color: var(--gh-accent); }
        .input-row input[type="file"] { display: none; }
        .btn { padding: 12px 20px; border: none; border-radius: 8px; background: var(--gh-green); color: var(--gh-text2); font-size: 15px; font-family: inherit; cursor: pointer; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .btn:hover { background: var(--gh-green); }
        .btn:disabled { opacity: 0.6; cursor: default; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-top: 16px; }
        .stat-card { background: var(--gh-bg); border: 1px solid var(--gh-border); border-radius: 10px; padding: 14px; text-align: center; }
        .stat-card .value { font-size: 24px; font-weight: 700; color: var(--gh-accent); }
        .stat-card .label { font-size: 12px; color: var(--gh-muted); margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--gh-border); font-size: 14px; }
        th { color: var(--gh-muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        .pos { font-weight: 700; color: #f0883e; }
        .error { color: var(--gh-red); margin-top: 12px; }
        .hint { color: var(--gh-muted); font-size: 14px; margin-top: 12px; }
        .completers { font-size: 12px; color: var(--gh-muted); margin-top: 4px; }
        .sub-card { background: var(--gh-bg); border: 1px solid var(--gh-border); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }
        .mod-btns { margin-top: 8px; }
        .btn-approve { background: var(--gh-green); }
        .btn-approve:hover { background: var(--gh-green); }
        .btn-reject { background: var(--gh-red); margin-left: 8px; }
        .btn-reject:hover { background: var(--gh-red); }
        .btn-mini { padding: 4px 8px; font-size: 13px; border: none; border-radius: 6px; background: var(--gh-border); color: var(--gh-text); cursor: pointer; font-family: inherit; }
        .btn-mini:hover { background: var(--bb-border); }
        .edit-inline { width: 100%; box-sizing: border-box; padding: 4px 6px; font-size: 13px; border: 1px solid var(--gh-accent); border-radius: 6px; background: var(--gh-bg); color: var(--gh-text); font-family: inherit; }
        .btn-danger { background: var(--gh-red); }
        .btn-danger:hover { background: var(--gh-red); }
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
            <button class="tab" id="tab-submit" onclick="showTab('submit')">Отправить рекорд</button>
            <button class="tab" id="tab-moderate" onclick="showTab('moderate')">Модерация</button>
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

        <div class="panel" id="panel-submit">
            <div class="card">
                <div class="input-row">
                    <input type="text" id="sub-level" placeholder="Название уровня (например: Tartarus)" onkeydown="if(event.key==='Enter')submitRecord()">
                </div>
                <div class="input-row">
                    <input type="text" id="sub-name" placeholder="Ваше имя (необязательно)">
                </div>
                <div class="input-row">
                    <label class="file-label" for="sub-media">📎 Видео или фото с прохождением</label>
                    <input type="file" id="sub-media" accept="video/*,image/*,.mp4,.mov,.webm,.mkv,.jpg,.jpeg,.png,.webp,.gif">
                </div>
                <button class="btn" id="sub-btn" onclick="submitRecord()">📨 Отправить рекорд</button>
                <div id="sub-result"></div>
            </div>
        </div>

        <div class="panel" id="panel-moderate">
            <div class="card">
                <div id="mod-result"><p class="hint">Загрузка...</p></div>
            </div>
        </div>
    </div>
    <script>
        var USER_ID = localStorage.getItem('gd_user_id');
        if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('gd_user_id', USER_ID); }
        var urlParams = new URLSearchParams(window.location.search);
        var qid = urlParams.get('user_id');
        if (qid) { USER_ID = qid; localStorage.setItem('gd_user_id', qid); }
        var IS_ADMIN = false;
        var LB_LEVELS = [];
        (function() {
            var token = localStorage.getItem('web_token');
            if (!token) return;
            fetch('/api/auth/me', { headers: { 'X-Auth-Token': token } })
                .then(function(r) { return r.json(); })
                .then(function(p) {
                    if (p && !p.error && p.is_admin) IS_ADMIN = true;
                })
                .catch(function() {});
        })();

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('active'); });
            document.querySelectorAll('.panel').forEach(function(p){ p.classList.remove('active'); });
            document.getElementById('tab-' + name).classList.add('active');
            document.getElementById('panel-' + name).classList.add('active');
            if (name === 'leaderboard') ensureLoaded('lb-result', loadLeaderboard);
            if (name === 'mystats') ensureLoaded('mystats-result', loadMyStats);
            if (name === 'moderate') renderModeration(0);
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
                    LB_LEVELS = r;
                    var html = '<table id="gd-table"><thead><tr><th>Поз.</th><th>Уровень</th><th>Сложность</th><th>Прохождения</th>' + (IS_ADMIN ? '<th>Действия</th>' : '') + '</tr></thead><tbody>';
                    r.forEach(function(l) {
                        var who = (l.completers && l.completers !== '{}') ? '<div class="completers">👤 ' + l.completers + '</div>' : '';
                        var actions = IS_ADMIN
                            ? '<button class="btn btn-mini" id="act-edit-' + l.id + '" onclick="editLevel(' + l.id + ')">✏️</button> <button class="btn btn-mini btn-danger" onclick="deleteLevel(' + l.id + ', this)">🗑️</button>'
                            : '';
                        html += '<tr data-id="' + l.id + '"><td class="pos" data-field="position">' + (l.position || '—') + '</td><td data-field="name">' + (l.name || '—') + '</td><td data-field="difficulty">' + (l.difficulty || '—') + '</td><td>' + (l.completions || 0) + who + '</td>' + (IS_ADMIN ? '<td>' + actions + '</td>' : '') + '</tr>';
                    });
                    html += '</tbody></table>';
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }

        function editLevel(id) {
            if (!IS_ADMIN) return;
            var tr = document.querySelector('#gd-table tbody tr[data-id="' + id + '"]');
            if (!tr) return;
            var lvl = null;
            for (var i = 0; i < LB_LEVELS.length; i++) { if (LB_LEVELS[i].id === id) { lvl = LB_LEVELS[i]; break; } }
            if (!lvl) return;
            var cells = tr.querySelectorAll('td[data-field]');
            var fields = { position: 'position', name: 'name', difficulty: 'difficulty' };
            var inputs = {};
            cells.forEach(function(cell) {
                var f = cell.getAttribute('data-field');
                if (!f || !fields[f]) return;
                var cur = (lvl[f] != null) ? lvl[f] : '';
                var input = document.createElement('input');
                input.className = 'edit-inline';
                input.value = cur;
                inputs[f] = input;
                cell.innerHTML = '';
                cell.appendChild(input);
            });
            var act = tr.querySelector('td:last-child');
            if (act) {
                act.innerHTML = '<button class="btn btn-mini" onclick="saveLevel(' + id + ')">✅</button> <button class="btn btn-mini" onclick="cancelEdit(' + id + ')">❌</button>';
            }
            tr.querySelector('.edit-inline').focus();
        }

        function saveLevel(id) {
            if (!IS_ADMIN) return;
            var tr = document.querySelector('#gd-table tbody tr[data-id="' + id + '"]');
            if (!tr) return;
            var inputs = {};
            tr.querySelectorAll('td[data-field] input').forEach(function(input) {
                inputs[input.closest('td').getAttribute('data-field')] = input.value.trim();
            });
            var pos = parseInt(inputs.position, 10);
            if (!pos || pos < 1) { alert('Позиция должна быть положительным числом'); return; }
            if (!inputs.name) { alert('Название не может быть пустым'); return; }
            var xhr = new XMLHttpRequest();
            xhr.open('PUT', '/api/gd/admin/level/' + id);
            xhr.setRequestHeader('Content-Type', 'application/json');
            if (localStorage.getItem('web_token')) { xhr.setRequestHeader('X-Auth-Token', localStorage.getItem('web_token')); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { alert('❌ ' + r.error); return; }
                    loadLeaderboard();
                } catch(e) { alert('Ошибка'); }
            };
            xhr.onerror = function() { alert('Ошибка сети'); };
            xhr.send(JSON.stringify({name: inputs.name, position: pos, difficulty: inputs.difficulty || 'Unknown'}));
        }

        function cancelEdit(id) {
            if (!IS_ADMIN) return;
            loadLeaderboard();
        }

        function deleteLevel(id, btn) {
            if (!IS_ADMIN) return;
            var name = '';
            for (var i = 0; i < LB_LEVELS.length; i++) { if (LB_LEVELS[i].id === id) { name = LB_LEVELS[i].name || ''; break; } }
            if (!confirm('⚠️ Удалить уровень «' + name + '» из топа?')) return;
            var typed = prompt('Для подтверждения введите название уровня («' + name + '»):');
            if (typed === null) return;
            if (typed.trim().toLowerCase() !== name.trim().toLowerCase()) { alert('❌ Название не совпадает. Удаление отменено.'); return; }
            if (btn) btn.disabled = true;
            var xhr = new XMLHttpRequest();
            xhr.open('DELETE', '/api/gd/admin/level/' + id);
            if (localStorage.getItem('web_token')) { xhr.setRequestHeader('X-Auth-Token', localStorage.getItem('web_token')); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { alert('❌ ' + r.error); return; }
                    alert('✅ Уровень удалён');
                    loadLeaderboard();
                } catch(e) { alert('Ошибка'); }
            };
            xhr.onerror = function() { alert('Ошибка сети'); };
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
                        + '<p class="hint" style="margin-top:16px">🔥 Сложнейший уровень: <strong style="color:var(--gh-text)">' + r.hardest_level + '</strong></p>';
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }

        function submitRecord() {
            var level = document.getElementById('sub-level').value.trim();
            var name = document.getElementById('sub-name').value.trim();
            var mediaInput = document.getElementById('sub-media');
            var mediaFile = mediaInput && mediaInput.files && mediaInput.files.length ? mediaInput.files[0] : null;
            var out = document.getElementById('sub-result');
            if (!level) { out.innerHTML = '<p class="error">Укажите название уровня</p>'; return; }
            if (!mediaFile) { out.innerHTML = '<p class="error">Прикрепите видео или фото с прохождением</p>'; return; }
            var btn = document.getElementById('sub-btn');
            btn.disabled = true;
            out.innerHTML = '<p class="hint">📨 Отправка...</p>';
            var doSubmit = function(finalName) {
                var fd = new FormData();
                fd.append('user_id', USER_ID);
                fd.append('level_name', level);
                fd.append('username', finalName || '');
                fd.append('token', localStorage.getItem('web_token') || '');
                fd.append('media', mediaFile, mediaFile.name);
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/api/gd/submit');
                xhr.timeout = 30000;
                xhr.onload = function() {
                    btn.disabled = false;
                    try {
                        var r = JSON.parse(xhr.responseText);
                        if (r.error) { out.innerHTML = '<p class="error">' + r.error + '</p>'; return; }
                        out.innerHTML = '<p class="hint">✅ Рекорд отправлен! Заявка #' + r.submission_id + ' ожидает модерации.</p>';
                        hubTrack('gd', 1);
                        document.getElementById('sub-level').value = '';
                        document.getElementById('sub-name').value = '';
                        if (mediaInput) { mediaInput.value = ''; updateMediaLabel(); }
                    } catch(e) { out.innerHTML = '<p class="error">Ошибка отправки.</p>'; }
                };
                xhr.onerror = function() { btn.disabled = false; out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
                xhr.ontimeout = function() { btn.disabled = false; out.innerHTML = '<p class="error">Сервер не ответил. Попробуйте ещё раз.</p>'; };
                xhr.send(fd);
            };
            if (name) { doSubmit(name); return; }
            var token = localStorage.getItem('web_token');
            if (!token) { doSubmit(''); return; }
            fetch('/api/auth/me', { headers: { 'X-Auth-Token': token } })
                .then(function(r) { return r.json(); })
                .then(function(p) {
                    if (p && !p.error && p.gd_nickname) { doSubmit(p.gd_nickname); }
                    else { doSubmit(''); }
                })
                .catch(function() { doSubmit(''); });
        }

        function updateMediaLabel() {
            var input = document.getElementById('sub-media');
            var label = document.querySelector('.file-label');
            if (!input || !label) return;
            if (input.files && input.files.length) {
                label.textContent = '📎 ' + input.files[0].name;
                label.classList.add('has-file');
            } else {
                label.textContent = '📎 Видео или фото с прохождением';
                label.classList.remove('has-file');
            }
        }
        document.getElementById('sub-media').addEventListener('change', updateMediaLabel);

        function renderModeration(page) {
            var out = document.getElementById('mod-result');
            out.innerHTML = '<p class="hint">Загрузка...</p>';
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/gd/moderate?page=' + page);
            if (localStorage.getItem('web_token')) { xhr.setRequestHeader('X-Auth-Token', localStorage.getItem('web_token')); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { out.innerHTML = '<p class="error">' + r.error + '</p>'; return; }
                    if (!r.submissions.length) {
                        out.innerHTML = '<p class="hint">✅ Все заявки обработаны! Новых заявок нет.</p>';
                        return;
                    }
                    var html = '<p class="hint" style="margin-top:0;margin-bottom:12px">Страница ' + (r.page + 1) + '/' + r.total_pages + ' · ' + r.total + ' заявок</p>';
                    r.submissions.forEach(function(s) {
                        html += '<div class="sub-card">'
                            + '<div style="color:var(--gh-muted);font-size:13px">Заявка #' + s.id + ' · ' + (s.username || s.user_id) + '</div>'
                            + '<div style="color:var(--gh-text);font-size:15px;margin:6px 0">🎮 ' + s.level_name + '</div>'
                            + '<div class="hint" style="margin-top:0">📅 ' + (s.submitted_at || '—') + ' · ' + (s.media_type || 'без медиа') + '</div>'
                            + '<div class="hint" style="margin-top:0">'
                            + ((s.media_file_id && s.media_file_id.indexOf('data:') === 0)
                                ? '<a href="' + s.media_file_id + '" target="_blank" rel="noopener noreferrer">🎬 Смотреть медиа</a>'
                                : '')
                            + '</div>'
                            + '<div class="mod-btns">'
                            + '<button class="btn btn-approve" onclick="approveSub(' + s.id + ')">✅ Подтвердить</button>'
                            + '<button class="btn btn-reject" onclick="rejectSub(' + s.id + ')">❌ Отклонить</button>'
                            + '</div></div>';
                    });
                    if (r.total_pages > 1) {
                        html += '<div class="nav-row">';
                        if (r.page > 0) html += '<button class="tab" style="flex:none" onclick="renderModeration(' + (r.page - 1) + ')">⬅️ Назад</button>';
                        if (r.page < r.total_pages - 1) html += '<button class="tab" style="flex:none" onclick="renderModeration(' + (r.page + 1) + ')">➡️ Вперёд</button>';
                        html += '</div>';
                    }
                    out.innerHTML = html;
                } catch(e) { out.innerHTML = '<p class="error">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { out.innerHTML = '<p class="error">Ошибка сети.</p>'; };
            xhr.send();
        }

        function approveSub(id) {
            var pos = prompt('Введите позицию уровня в топе (число):', '1');
            if (pos === null) return;
            pos = parseInt(pos, 10);
            if (!pos || pos < 1) { alert('Позиция должна быть положительным числом'); return; }
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/gd/moderate/approve');
            xhr.setRequestHeader('Content-Type', 'application/json');
            if (localStorage.getItem('web_token')) { xhr.setRequestHeader('X-Auth-Token', localStorage.getItem('web_token')); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    alert(r.error ? '❌ ' + r.error : '✅ Заявка #' + id + ' подтверждена!');
                    renderModeration(0);
                } catch(e) { alert('Ошибка'); }
            };
            xhr.onerror = function() { alert('Ошибка сети'); };
            xhr.send(JSON.stringify({user_id: USER_ID, submission_id: id, position: pos}));
        }

        function rejectSub(id) {
            if (!confirm('Отклонить заявку #' + id + '?')) return;
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/gd/moderate/reject');
            xhr.setRequestHeader('Content-Type', 'application/json');
            if (localStorage.getItem('web_token')) { xhr.setRequestHeader('X-Auth-Token', localStorage.getItem('web_token')); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    alert(r.error ? '❌ ' + r.error : '❌ Заявка #' + id + ' отклонена');
                    renderModeration(0);
                } catch(e) { alert('Ошибка'); }
            };
            xhr.onerror = function() { alert('Ошибка сети'); };
            xhr.send(JSON.stringify({user_id: USER_ID, submission_id: id}));
        }
        function showRegNotice() {
            try {
                if (sessionStorage.getItem('reg_notice_shown')) return;
                sessionStorage.setItem('reg_notice_shown', '1');
                var re = document.getElementById('hub-reg-notice');
                if (!re) {
                    re = document.createElement('div');
                    re.id = 'hub-reg-notice';
                    re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                    re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                    document.body.appendChild(re);
                }
                clearTimeout(re._t);
                re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
            } catch(e) {}
        }
        function hubTrack(module, actions) {
            actions = actions || 1;
            var token = localStorage.getItem('web_token') || '';
            var uid = localStorage.getItem('web_user_id') || '';
            try {
                if (token && uid.indexOf('u') === 0) {
                    fetch('/api/achievements/activity', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                        body: JSON.stringify({ module: module, actions: actions })
                    }).then(function(r) { return r.json(); }).then(function(d) {
                        if (d && d.unlocked_detail && d.unlocked_detail.length) {
                            var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                            var pe = document.getElementById('hub-popup');
                            if (!pe) {
                                pe = document.createElement('div');
                                pe.id = 'hub-popup';
                                pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                document.body.appendChild(pe);
                            }
                            pe.innerHTML = '🏆 ' + names.join('<br>');
                            pe.style.display = 'block';
                            clearTimeout(pe._t);
                            pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                        }
                    }).catch(function() {});
                } else {
                    showRegNotice();
                    var today = new Date();
                    var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                    var acts = {};
                    try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                    acts[dayStr] = (acts[dayStr] || 0) + 1;
                    localStorage.setItem('hub_activity', JSON.stringify(acts));
                }
            } catch(e) {}
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
    levels = get_gd_leaderboard(limit)
    from concurrent.futures import ThreadPoolExecutor
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            diffs = list(pool.map(lambda lv: get_gd_difficulty_name(lv.get("name") or ""), levels))
        for lv, d in zip(levels, diffs):
            if d and d != "Unknown":
                lv["difficulty"] = d
    except Exception as exc:
        print(f"GD leaderboard difficulty enrich error: {exc}")
    return jsonify(levels)


@app.route("/api/gd/admin/level/<int:level_id>", methods=["DELETE"])
def api_gd_admin_level_delete(level_id: int):
    """Admin: delete a GD level (and related completions/stats)."""
    if _web_admin_session() is None:
        return jsonify({"error": "Нет прав администратора"}), 403
    try:
        with get_db_engine().connect() as conn:
            lvl = conn.execute(
                text("SELECT id FROM levels WHERE id = :lid"), {"lid": level_id}
            ).mappings().first()
            if not lvl:
                return jsonify({"error": "Уровень не найден"}), 404
            conn.execute(text("DELETE FROM level_completions WHERE level_id = :lid"), {"lid": level_id})
            conn.execute(text("UPDATE player_stats SET hardest_level_id = NULL WHERE hardest_level_id = :lid"), {"lid": level_id})
            conn.execute(text("DELETE FROM levels WHERE id = :lid"), {"lid": level_id})
            conn.commit()
            return jsonify({"ok": True})
    except Exception as exc:
        print(f"[GD] admin delete level error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/gd/admin/level/<int:level_id>", methods=["PUT"])
def api_gd_admin_level_update(level_id: int):
    """Admin: edit a GD level (name/position/difficulty)."""
    if _web_admin_session() is None:
        return jsonify({"error": "Нет прав администратора"}), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    position = int(data.get("position") or 0)
    difficulty = (data.get("difficulty") or "").strip() or None
    if not name:
        return jsonify({"error": "Название не может быть пустым"}), 400
    if position < 1:
        return jsonify({"error": "Позиция должна быть положительным числом"}), 400
    try:
        with get_db_engine().connect() as conn:
            lvl = conn.execute(
                text("SELECT id, position FROM levels WHERE id = :lid"), {"lid": level_id}
            ).mappings().first()
            if not lvl:
                return jsonify({"error": "Уровень не найден"}), 404
            duplicate = conn.execute(
                text("SELECT id FROM levels WHERE LOWER(TRIM(name)) = :key AND id != :lid"),
                {"key": _gd_norm_name(name), "lid": level_id},
            ).mappings().first()
            if duplicate:
                return jsonify({"error": "Уровень с таким названием уже есть в топе"}), 409
            _gd_shift_positions(conn, position, exclude_id=level_id)
            conn.execute(
                text("UPDATE levels SET name=:nm, position=:pos, difficulty=COALESCE(:diff, difficulty) WHERE id=:lid"),
                {"lid": level_id, "nm": name, "pos": position, "diff": difficulty},
            )
            conn.commit()
            return jsonify({"ok": True, "id": level_id})
    except Exception as exc:
        print(f"[GD] admin update level error: {exc}")
        return jsonify({"error": str(exc)}), 500


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


def _gd_web_uid(user_id_raw: str | None) -> int | None:
    """Resolve web user_id to a numeric id (Telegram id if numeric, else hashed)."""
    if not user_id_raw:
        return None
    if user_id_raw.isdigit():
        return int(user_id_raw)
    return _web_user_id(user_id_raw)


@app.route("/api/gd/me")
def api_gd_me():
    return jsonify({"is_admin": _web_admin_session() is not None})


@app.route("/api/gd/submit", methods=["POST"])
def api_gd_submit():
    uid = _gd_web_uid((request.form.get("user_id") or "").strip() or "")
    level_name = (request.form.get("level_name") or "").strip()
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    if not level_name:
        return jsonify({"error": "Укажите название уровня"}), 400
    username = (request.form.get("username") or "").strip()
    if not username:
        token = (request.form.get("token") or "").strip()
        web_user = _get_session_user(token or None)
        if web_user and web_user.get("gd_nickname"):
            username = web_user["gd_nickname"]
    if not username:
        username = f"web_{uid}"

    # Медиа (видео/фото с прохождением) — обязательно, как в Telegram-флоу.
    media_file = request.files.get("media")
    media_data = media_file.read() if media_file and media_file.filename else None
    if not media_data:
        return jsonify({"error": "Прикрепите видео или фото с прохождением"}), 400
    filename = (media_file.filename or "").lower()
    media_mime = (media_file.mimetype or "").lower()
    if media_mime.startswith("video/") or any(filename.endswith(ext) for ext in (".mp4", ".mov", ".webm", ".mkv")):
        media_type = "video"
    elif media_mime.startswith("image/") or any(filename.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        media_type = "photo"
    else:
        media_type = "document"
    # Храним файл как data-URL (веб не имеет Telegram file_id).
    media_ref = f"data:{media_mime or 'application/octet-stream'};base64,{base64.b64encode(media_data).decode('ascii')}"

    sub_id = create_gd_submission(uid, username, level_name, media_ref, media_type, status="pending")
    if not sub_id:
        return jsonify({"error": "Ошибка создания заявки"}), 500
    return jsonify({"ok": True, "submission_id": sub_id})


@app.route("/api/gd/moderate")
def api_gd_moderate():
    if _web_admin_session() is None:
        return jsonify({"error": "Нет прав администратора"}), 403
    page = max(request.args.get("page", default=0, type=int), 0)
    per_page = 5
    submissions, total = get_gd_pending_submissions(page, per_page)
    for s in submissions:
        if s.get("submitted_at"):
            s["submitted_at"] = str(s["submitted_at"])[:19]
    total_pages = max((total + per_page - 1) // per_page, 1)
    return jsonify({
        "submissions": submissions,
        "total": total,
        "total_pages": total_pages,
        "page": page,
    })


@app.route("/api/gd/moderate/reject", methods=["POST"])
def api_gd_moderate_reject():
    data = request.get_json(silent=True) or {}
    admin = _web_admin_session()
    if admin is None:
        return jsonify({"error": "Нет прав администратора"}), 403
    sub_id = int(data.get("submission_id") or 0)
    admin_id = admin.get("id") or 0
    if not sub_id:
        return jsonify({"error": "Нет submission_id"}), 400
    if reject_gd_submission_db(sub_id, admin_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Заявка не найдена или уже обработана"}), 404


@app.route("/api/gd/moderate/approve", methods=["POST"])
def api_gd_moderate_approve():
    data = request.get_json(silent=True) or {}
    admin = _web_admin_session()
    if admin is None:
        return jsonify({"error": "Нет прав администратора"}), 403
    sub_id = int(data.get("submission_id") or 0)
    position = int(data.get("position") or 0)
    admin_id = admin.get("id") or 0
    if not sub_id:
        return jsonify({"error": "Нет submission_id"}), 400
    if position < 1:
        return jsonify({"error": "Позиция должна быть положительным числом"}), 400
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT level_name FROM submissions WHERE id = :sid AND status = 'pending'"),
                {"sid": sub_id},
            ).mappings().first()
    except Exception as exc:
        print(f"approve fetch error: {exc}")
        return jsonify({"error": "Ошибка базы данных"}), 500
    if not row:
        return jsonify({"error": "Заявка не найдена или уже обработана"}), 404
    level_name = row["level_name"]
    difficulty = get_gd_difficulty_name(level_name)
    level_id = add_gd_level(level_name, position, difficulty)
    if not level_id:
        return jsonify({"error": f"Ошибка при добавлении уровня {level_name} в топ"}), 500
    if approve_gd_submission_db(sub_id, admin_id):
        return jsonify({"ok": True, "level_id": level_id})
    return jsonify({"error": "Заявка не найдена или уже обработана"}), 404


# ── D&D AI Master (web) ────────────────────────────────────────────

def _dnd_plain(text: str) -> str:
    """Strip Telegram HTML tags from D&D replies for clean web display."""
    import re
    return re.sub(r"<[^>]+>", "", text or "").strip()


@app.route("/api/dnd/status")
def api_dnd_status():
    user_id_raw = request.args.get("user_id", "")
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _gd_web_uid(user_id_raw)
    try:
        from api.dnd_runtime import find_active_session, get_session_log, get_session_players
        session = find_active_session(uid)
        if not session:
            return jsonify({"active": False})
        sid = session["id"]
        log = get_session_log(sid)
        players = get_session_players(sid)
        return jsonify({
            "active": True,
            "id": sid,
            "name": session.get("name"),
            "scene": session.get("current_scene") or "Новая игра",
            "log_count": len(log),
            "last_ai_response": (session.get("last_ai_response") or "")[:300],
            "players": [
                {
                    "name": p.get("player_name") or p.get("name") or "Игрок",
                    "char_class": p.get("character_class"),
                    "level": p.get("level"),
                }
                for p in players
            ],
            "log": log,
        })
    except Exception as exc:
        print(f"[DND] status error: {exc}")
        log_error("DnD", "status_query", f"dnd status user={uid}: {exc}", "query: dnd status")
        return jsonify({"active": False})


@app.route("/api/dnd/start", methods=["POST"])
def api_dnd_start():
    data = request.get_json(silent=True) or {}
    uid = _gd_web_uid(data.get("user_id", ""))
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    name = (data.get("name") or "").strip()
    from api.dnd_runtime import cmd_dnd_start
    reply = cmd_dnd_start(uid, uid, name)
    return jsonify({"ok": True, "reply": _dnd_plain(reply)})


@app.route("/api/dnd/act", methods=["POST"])
def api_dnd_act():
    data = request.get_json(silent=True) or {}
    uid = _gd_web_uid(data.get("user_id", ""))
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Пустое действие"}), 400
    from api.dnd_runtime import handle_free_text
    reply = handle_free_text(uid, uid, text)
    if reply is None:
        return jsonify({"error": "Нет активной D&D сессии. Начните новую сессию."}), 400
    return jsonify({"ok": True, "reply": _dnd_plain(reply)})


@app.route("/api/dnd/roll", methods=["POST"])
def api_dnd_roll():
    data = request.get_json(silent=True) or {}
    uid = _gd_web_uid(data.get("user_id", ""))
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    dice = (data.get("dice") or "").strip()
    purpose = (data.get("purpose") or "").strip()
    if not dice:
        return jsonify({"error": "Укажите кубик, например d20 или 2d6+3"}), 400
    from api.dnd_runtime import cmd_dnd_roll
    args = dice + (" " + purpose if purpose else "")
    reply = cmd_dnd_roll(uid, uid, args)
    return jsonify({"ok": True, "reply": _dnd_plain(reply)})


@app.route("/api/dnd/stop", methods=["POST"])
def api_dnd_stop():
    data = request.get_json(silent=True) or {}
    uid = _gd_web_uid(data.get("user_id", ""))
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    try:
        from api.dnd_runtime import cmd_dnd_stop
        reply = cmd_dnd_stop(uid, uid)
    except Exception as exc:
        return jsonify({"error": f"Ошибка: {exc}"}), 500
    return jsonify({"ok": True, "reply": _dnd_plain(reply)})


@app.route("/api/dnd/fix", methods=["POST"])
def api_dnd_fix():
    data = request.get_json(silent=True) or {}
    uid = _gd_web_uid(data.get("user_id", ""))
    if uid is None:
        return jsonify({"error": "Нет user_id"}), 400
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Пустой текст исправления"}), 400
    from api.dnd_runtime import cmd_dnd_fix
    reply = cmd_dnd_fix(uid, uid, text)
    return jsonify({"ok": True, "reply": _dnd_plain(reply)})


@app.route("/dnd")
def dnd_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D&D AI Master — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text); padding: 20px; }
        .container { max-width: 720px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--gh-accent); }
        .header a { color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--gh-accent); }
        .card { background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
        .status-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
        .chip { background: var(--gh-bg); border: 1px solid var(--gh-border); border-radius: 8px; padding: 8px 12px; font-size: 13px; }
        .chip b { color: var(--gh-accent); }
        .log { max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 4px; }
        .msg { padding: 10px 14px; border-radius: 10px; max-width: 85%; font-size: 14px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; }
        .msg.user { background: var(--gh-accent); color: var(--gh-text2); align-self: flex-end; }
        .msg.ai { background: var(--gh-panel); border: 1px solid var(--gh-border); align-self: flex-start; }
        .msg.dice { background: var(--bb-elev); border: 1px solid var(--gh-warn); color: var(--bb-warn); align-self: flex-start; }
        .msg.system { background: transparent; color: var(--gh-muted); font-size: 12px; align-self: center; }
        .input-row { display: flex; gap: 10px; margin-bottom: 12px; }
        .input-row input { flex: 1; padding: 12px; border: 1px solid var(--gh-border); border-radius: 8px; background: var(--gh-bg); color: var(--gh-text); font-size: 15px; font-family: inherit; }
        .input-row input:focus { outline: none; border-color: var(--gh-accent); }
        .btn { padding: 12px 20px; border: none; border-radius: 8px; background: var(--gh-green); color: var(--gh-text2); font-size: 15px; font-family: inherit; cursor: pointer; }
        .btn:hover { background: var(--gh-green); }
        .btn:disabled { opacity: 0.6; cursor: default; }
        .btn-roll { background: #b06e28; }
        .btn-roll:hover { background: var(--gh-warn); }
        .btn-stop { background: var(--gh-red); }
        .btn-stop:hover { background: var(--gh-red); }
        .btn-fix { background: var(--gh-accent); }
        .btn-fix:hover { background: var(--bb-link); }
        .error { color: var(--gh-red); margin-top: 10px; font-size: 14px; }
        .hint { color: var(--gh-muted); font-size: 14px; margin-top: 8px; }
        .sec-label { color: var(--gh-muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; font-weight: 600; }
        #start-panel { display: block; }
        #game-panel { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🐉 D&D AI Master</h1>
            <a href="/">← На главную</a>
        </div>

        <div id="start-panel">
            <div class="card">
                <div class="sec-label">Новая сессия</div>
                <div class="input-row">
                    <input type="text" id="campaign-name" placeholder="Название кампании (например: Проклятие подземелья)" onkeydown="if(event.key==='Enter')startSession()">
                    <button class="btn" id="start-btn" onclick="startSession()">🎲 Начать</button>
                </div>
                <p class="hint">Напишите название кампании или оставьте пустым — бот создаст сессию и станет вашим мастером.</p>
                <div id="start-result"></div>
            </div>
        </div>

        <div id="game-panel">
            <div class="card">
                <div class="status-row" id="status-row"></div>
                <div class="log" id="log"></div>
            </div>
            <div class="card">
                <div class="sec-label">Ваше действие</div>
                <div class="input-row">
                    <input type="text" id="action-text" placeholder="Что вы делаете? Например: осматриваю пещеру" onkeydown="if(event.key==='Enter')sendAction()">
                    <button class="btn" id="act-btn" onclick="sendAction()">➤</button>
                </div>
                <div class="sec-label">Бросок кубика</div>
                <div class="input-row">
                    <input type="text" id="dice-text" placeholder="d20 / 2d6+3" style="max-width:120px" onkeydown="if(event.key==='Enter')rollDice()">
                    <input type="text" id="dice-purpose" placeholder="Зачем (например: Проверка восприятия)" onkeydown="if(event.key==='Enter')rollDice()">
                    <button class="btn btn-roll" onclick="rollDice()">🎲</button>
                </div>
                <div class="sec-label">Исправление мастера</div>
                <div class="input-row">
                    <input type="text" id="fix-text" placeholder="Запомнить исправление: в этом мире нет магии" onkeydown="if(event.key==='Enter')sendFix()">
                    <button class="btn btn-fix" onclick="sendFix()">✏️</button>
                </div>
                <div class="input-row">
                    <button class="btn btn-stop" onclick="stopSession()">⏸ Остановить сессию</button>
                </div>
                <div id="game-result"></div>
            </div>
        </div>
    </div>
    <script>
        var USER_ID = localStorage.getItem('dnd_user_id');
        if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('dnd_user_id', USER_ID); }
        var urlParams = new URLSearchParams(window.location.search);
        var qid = urlParams.get('user_id');
        if (qid) { USER_ID = qid; localStorage.setItem('dnd_user_id', qid); }

        function post(url, body, cb) {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', url);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.timeout = 60000;
            xhr.ontimeout = function() { cb({error: 'Сервер не ответил. Попробуйте ещё раз.'}); };
            xhr.onload = function() { try { cb(JSON.parse(xhr.responseText)); } catch(e) { cb({error: 'Ошибка ответа сервера.'}); } };
            xhr.onerror = function() { cb({error: 'Ошибка сети.'}); };
            xhr.send(JSON.stringify(body));
        }

        function esc(s) {
            return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }

        function showMsg(role, content) {
            var log = document.getElementById('log');
            var div = document.createElement('div');
            div.className = 'msg ' + role;
            div.textContent = content || '';
            log.appendChild(div);
            log.scrollTop = log.scrollHeight;
        }

        function renderLog(log) {
            var logEl = document.getElementById('log');
            logEl.innerHTML = '';
            log.forEach(function(m) {
                var role = m.role;
                if (role !== 'user' && role !== 'ai' && role !== 'dice') role = 'system';
                showMsg(role, m.content);
            });
        }

        function renderStatus(s) {
            var chips = '<span class="chip">📜 <b>' + esc(s.name) + '</b></span>' +
                        '<span class="chip">📖 Сцена: <b>' + esc(s.scene) + '</b></span>' +
                        '<span class="chip">📝 Событий: <b>' + s.log_count + '</b></span>';
            if (s.players && s.players.length) {
                var names = s.players.map(function(p){ return esc(p.name) + ' (' + (p.char_class || '') + ' ' + (p.level || 1) + ')'; }).join(', ');
                chips += '<span class="chip">👥 <b>' + esc(names) + '</b></span>';
            }
            document.getElementById('status-row').innerHTML = chips;
        }

        function refreshStatus() {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/dnd/status?user_id=' + encodeURIComponent(USER_ID));
            xhr.timeout = 30000;
            xhr.ontimeout = function() { showStart('Сервер не ответил. Попробуйте ещё раз.'); };
            xhr.onload = function() {
                if (xhr.status !== 200) { showStart('Не удалось загрузить статус сессии. Проверьте подключение.'); return; }
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (!r.active) { showStart(); return; }
                    showGame();
                    renderStatus(r);
                    renderLog(r.log);
                } catch(e) { showStart('Не удалось обработать ответ сервера.'); }
            };
            xhr.onerror = function() { showStart('Сетевая ошибка. Проверьте подключение.'); };
            xhr.send();
        }

        function showStart(errMsg) {
            document.getElementById('start-panel').style.display = 'block';
            document.getElementById('game-panel').style.display = 'none';
            var el = document.getElementById('start-result');
            if (errMsg) { el.innerHTML = '<p class="error">' + esc(errMsg) + '</p>'; }
            else { el.innerHTML = ''; }
        }

        function showGame() {
            document.getElementById('start-panel').style.display = 'none';
            document.getElementById('game-panel').style.display = 'block';
        }

        function startSession() {
            var name = document.getElementById('campaign-name').value.trim();
            var btn = document.getElementById('start-btn');
            btn.disabled = true;
            post('/api/dnd/start', {user_id: USER_ID, name: name}, function(r) {
                btn.disabled = false;
                if (r.error) { document.getElementById('start-result').innerHTML = '<p class="error">' + esc(r.error) + '</p>'; return; }
                document.getElementById('start-result').innerHTML = '';
                showGame();
                document.getElementById('log').innerHTML = '';
                showMsg('ai', r.reply);
                refreshStatus();
            });
        }

        function sendAction() {
            var text = document.getElementById('action-text').value.trim();
            if (!text) return;
            var btn = document.getElementById('act-btn');
            btn.disabled = true;
            showMsg('user', text);
            document.getElementById('action-text').value = '';
            post('/api/dnd/act', {user_id: USER_ID, text: text}, function(r) {
                btn.disabled = false;
                if (r.error) { showMsg('system', '❌ ' + r.error); return; }
                showMsg('ai', r.reply);
                refreshStatus();
            });
        }

        function rollDice() {
            var dice = document.getElementById('dice-text').value.trim();
            var purpose = document.getElementById('dice-purpose').value.trim();
            if (!dice) return;
            var btn = document.querySelector('.btn-roll');
            btn.disabled = true;
            post('/api/dnd/roll', {user_id: USER_ID, dice: dice, purpose: purpose}, function(r) {
                btn.disabled = false;
                if (r.error) { showMsg('system', '❌ ' + r.error); return; }
                showMsg('dice', r.reply);
                refreshStatus();
                hubTrack('dnd', 1);
            });
        }

        function sendFix() {
            var text = document.getElementById('fix-text').value.trim();
            if (!text) return;
            post('/api/dnd/fix', {user_id: USER_ID, text: text}, function(r) {
                if (r.error) { showMsg('system', '❌ ' + r.error); return; }
                showMsg('system', r.reply);
                document.getElementById('fix-text').value = '';
            });
        }

        function stopSession() {
            post('/api/dnd/stop', {user_id: USER_ID}, function(r) {
                if (r.error) { showMsg('system', '❌ ' + r.error); return; }
                showMsg('system', r.reply);
                showStart();
                document.getElementById('start-result').innerHTML = '';
            });
        }

        refreshStatus();

        function showRegNotice() {
            try {
                if (sessionStorage.getItem('reg_notice_shown')) return;
                sessionStorage.setItem('reg_notice_shown', '1');
                var re = document.getElementById('hub-reg-notice');
                if (!re) {
                    re = document.createElement('div');
                    re.id = 'hub-reg-notice';
                    re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                    re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                    document.body.appendChild(re);
                }
                clearTimeout(re._t);
                re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
            } catch(e) {}
        }
        function hubTrack(module, actions) {
            actions = actions || 1;
            var token = localStorage.getItem('web_token') || '';
            var uid = localStorage.getItem('web_user_id') || '';
            try {
                if (token && uid.indexOf('u') === 0) {
                    fetch('/api/achievements/activity', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                        body: JSON.stringify({ module: module, actions: actions })
                    }).then(function(r) { return r.json(); }).then(function(d) {
                        if (d && d.unlocked_detail && d.unlocked_detail.length) {
                            var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                            var pe = document.getElementById('hub-popup');
                            if (!pe) {
                                pe = document.createElement('div');
                                pe.id = 'hub-popup';
                                pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                document.body.appendChild(pe);
                            }
                            pe.innerHTML = '🏆 ' + names.join('<br>');
                            pe.style.display = 'block';
                            clearTimeout(pe._t);
                            pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                        }
                    }).catch(function() {});
                } else {
                    showRegNotice();
                    var today = new Date();
                    var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                    var acts = {};
                    try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                    acts[dayStr] = (acts[dayStr] || 0) + 1;
                    localStorage.setItem('hub_activity', JSON.stringify(acts));
                }
            } catch(e) {}
        }
    </script>
</body>
</html>"""
    return html


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
        body { font-family: Arial, sans-serif; background: var(--bb-elev); padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: var(--bb-panel); padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { text-align: center; margin-bottom: 30px; color: var(--bb-text); }
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
        .btn-voice { background: #FF9500; color: white; }
        .btn-voice:hover { background: #CC7400; }
        .btn-hint { background: #5E5CE6; color: white; padding: 8px 14px; font-size: 14px; }
        .btn-hint:hover { background: #4A48C4; }
        .toolbar { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 16px 0; }
        .question-tools { display: flex; gap: 8px; margin-top: 8px; }
        .hint-box { margin-top: 8px; padding: 10px 14px; background: var(--bb-elev); border: 1px solid var(--bb-border); border-radius: 8px; color: var(--bb-warn); font-weight: 600; }
        .stats-bar { text-align: center; padding: 10px 16px; margin-bottom: 20px; background: var(--bb-elev); border: 1px solid var(--bb-border); border-radius: 8px; color: var(--bb-link); font-weight: 600; font-size: 15px; }
        input { width: 100%; padding: 12px; font-size: 16px; margin: 10px 0; border: 2px solid var(--bb-border); border-radius: 8px; }
        input:focus { outline: none; border-color: #007AFF; }
        .question { margin: 20px 0; }
        .question-text { font-size: 18px; font-weight: 600; margin-bottom: 10px; }
        .result { padding: 12px; margin: 10px 0; border-radius: 8px; font-weight: bold; }
        .correct { background: var(--bb-green-panel); color: var(--bb-green2); }
        .incorrect { background: var(--bb-danger-bg); color: var(--bb-red); }
        #questions-screen { display: none; }
        @media print {
            body { background: var(--bb-panel); padding: 0; }
            .container { box-shadow: none; padding: 20px; }
            button { display: none !important; }
            input { border: none; border-bottom: 2px solid var(--bb-ink); background: transparent; }
            .result { display: none !important; }
            .hint-box { display: none !important; }
            .stats-bar { display: none !important; }
            h1 { font-size: 24px; margin-bottom: 20px; }
            .story-title { font-size: 20px; margin-bottom: 10px; }
            .story-image { font-size: 60px; margin: 10px 0; }
            .story-text { font-size: 16px; line-height: 1.6; }
            .question { page-break-inside: avoid; margin: 15px 0; }
            .question-text { font-size: 16px; }
            #questions-screen { display: block !important; }
            #reading-screen { display: block !important; }
            .print-separator { border-top: 2px dashed var(--bb-ink); margin: 30px 0; padding-top: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        <div id="stats-bar" class="stats-bar">📊 Пока нет результатов — прочитай текст и ответь на вопросы.</div>
        <div id="reading-screen">
            <div id="sentences"></div>
            <div class="toolbar">
                <button class="btn-voice" onclick="speakStory()">🔊 Слушать</button>
                <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
                <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
                <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
            </div>
        </div>
        <div id="questions-screen">
            <div id="questions-container"></div>
            <div class="toolbar">
                <button class="btn-primary" onclick="checkAnswers()">Проверить</button>
                <button class="btn-secondary" onclick="goBackToReading()">← Назад к чтению</button>
                <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
            </div>
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
                '<div class="question-tools">' +
                '<button type="button" class="btn-hint" onclick="toggleHint(' + i + ')">💡 Подсказка</button>' +
                '<button type="button" class="btn-voice" onclick="speakQuestion(' + i + ')">🔊 Вопрос</button>' +
                '</div>' +
                '<div class="hint-box" id="hint-' + i + '" style="display:none;">Ответ: ' + escapeHtml(q.answer) + '</div>' +
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
            let correctCount = 0;
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = q.answer.toLowerCase();
                if (userAnswer === correctAnswer) {
                    result.textContent = '✓ Правильно!';
                    result.className = 'result correct';
                    correctCount++;
                } else {
                    result.textContent = '✗ Правильный ответ: ' + q.answer;
                    result.className = 'result incorrect';
                }
                result.style.display = 'block';
            });
            const s = loadStats();
            s.runs += 1;
            s.questions += currentData.questions.length;
            s.correct += correctCount;
            saveStats(s);
            renderStats();
        }
        function toggleHint(i) {
            const el = document.getElementById('hint-' + i);
            if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }
        function speakText(text) {
            if (!('speechSynthesis' in window)) {
                alert('Озвучивание не поддерживается этим браузером');
                return;
            }
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(String(text));
            utterance.lang = 'ru-RU';
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
        }
        function speakStory() {
            if (currentData && currentData.text) speakText(currentData.text);
        }
        function speakQuestion(i) {
            if (currentData && currentData.questions[i]) speakText(currentData.questions[i].question);
        }
        function escapeHtml(s) {
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }
        function loadStats() {
            try { return JSON.parse(localStorage.getItem('reading_trainer_stats') || '{"runs":0,"questions":0,"correct":0}'); }
            catch (e) { return {"runs":0,"questions":0,"correct":0}; }
        }
        function saveStats(s) { localStorage.setItem('reading_trainer_stats', JSON.stringify(s)); }
        function renderStats() {
            const el = document.getElementById('stats-bar');
            if (!el) return;
            const s = loadStats();
            if (!s.runs) { el.innerHTML = '📊 Пока нет результатов — прочитай текст и ответь на вопросы.'; return; }
            const pct = s.questions ? Math.round(100 * s.correct / s.questions) : 0;
            el.innerHTML = '📊 Заданий: ' + s.runs + ' · Вопросов: ' + s.questions + ' · Верно: ' + s.correct + ' (' + pct + '%)';
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
        renderStats();
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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: var(--bb-panel); padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        h1 { text-align: center; margin-bottom: 8px; color: var(--bb-text); font-size: 28px; }
        .subtitle { text-align: center; color: var(--bb-muted); margin-bottom: 24px; font-size: 14px; }
        textarea { width: 100%; min-height: 180px; padding: 16px; font-size: 18px; border: 2px solid var(--bb-text); border-radius: 12px; resize: vertical; font-family: inherit; line-height: 1.8; }
        textarea:focus { outline: none; border-color: var(--bb-link); }
        .btn { padding: 14px 32px; font-size: 17px; cursor: pointer; border: none; border-radius: 10px; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: var(--bb-link); color: white; }
        .btn-primary:hover { background: #5a52e0; }
        .btn-secondary { background: var(--bb-elev); color: var(--bb-text); }
        .btn-secondary:hover { background: var(--bb-border); }
        .btn-success { background: var(--bb-green3); color: white; }
        .btn-success:hover { background: var(--bb-green2); }
        .actions { display: flex; gap: 12px; justify-content: center; margin-top: 20px; flex-wrap: wrap; }
        #exercise-screen { display: none; margin-top: 24px; }
        #input-screen { display: block; }
        .exercise-text { font-size: 20px; line-height: 2.4; padding: 20px; background: var(--bb-elev); border-radius: 12px; border: 2px solid var(--bb-border); }
        .exercise-text input { font-size: 20px; width: 60px; padding: 2px 6px; border: none; border-bottom: 2px solid var(--bb-link); background: transparent; text-align: center; font-family: inherit; outline: none; }
        .exercise-text input.correct { border-bottom-color: var(--bb-green3); background: var(--bb-green-panel); }
        .exercise-text input.incorrect { border-bottom-color: var(--gh-red); background: var(--bb-danger-bg); }
        .exercise-text .hint { display: none; font-size: 14px; color: var(--gh-red); margin-left: 4px; }
        .result-badge { text-align: center; font-size: 20px; font-weight: 700; padding: 12px; border-radius: 10px; margin-top: 16px; display: none; }
        .result-badge.pass { background: var(--bb-green-panel); color: var(--bb-green2); display: block; }
        .result-badge.fail { background: var(--bb-danger-bg); color: var(--gh-red); display: block; }
        .notice { display: none; margin-top: 16px; padding: 12px 16px; background: var(--bb-elev); border: 1px solid var(--bb-border); border-radius: 10px; color: var(--bb-warn); font-size: 14px; text-align: center; }
        .notice button { margin-left: 8px; padding: 6px 14px; font-size: 14px; }
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
            <div id="notice" class="notice">
                <span id="notice-text"></span>
                <button class="btn btn-secondary" onclick="generateExercise()">Повторить с ИИ</button>
            </div>
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
                if (data.fallback) {
                    showNotice(data.notice || 'AI временно недоступен — упражнение создано автоматически.');
                } else {
                    hideNotice();
                }
            })
            .catch(err => {
                hideNotice();
                document.getElementById('exercise-content').innerHTML = '<div style="color:var(--gh-red);text-align:center;padding:20px;">' +
                    '<div style="font-size:18px;font-weight:600;margin-bottom:10px;">Не удалось создать упражнение</div>' +
                    '<div style="margin-bottom:16px;color:#555;">' + escapeHtml(err.message) + '</div>' +
                    '<button class="btn btn-primary" onclick="generateExercise()">Повторить</button></div>';
            });
        }

        function showNotice(msg) {
            document.getElementById('notice-text').textContent = msg;
            document.getElementById('notice').style.display = 'block';
        }

        function hideNotice() {
            document.getElementById('notice').style.display = 'none';
        }

        function renderExercise() {
            hideNotice();
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
            hideNotice();
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
# Единый пул вопросов импортируется из core.canon.questions (source of truth).

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
    return load_canon_text()[:max_chars].rstrip()


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

    manual = question.get("distractors") or []
    if len(manual) >= 3:
        distractors_pool = random.sample(manual, 3)
    else:
        same_group = [q for q in _TRIVIA_QUESTIONS if q.get("group") == q_group and q["correct_text"] != correct_text]
        other = [q for q in _TRIVIA_QUESTIONS if q.get("group") != q_group and q["correct_text"] != correct_text]
        distractors_pool = [q["correct_text"] for q in same_group]
        if len(distractors_pool) < 3:
            distractors_pool += [q["correct_text"] for q in other]
        distractors_pool = random.sample(distractors_pool, min(3, len(distractors_pool)))

    options = [correct_text] + distractors_pool
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


def _pc_extract_reply(resp: "requests.Response") -> str:
    """Extract text reply from a Groq/OpenAI chat completion response, tolerating all formats."""
    try:
        data = resp.json()
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return content or ""


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
            content = m.get("content", "")
            if isinstance(content, str) and len(content) > 4000:
                content = content[:4000] + "…"
            groq_messages.append({"role": m["role"], "content": content})

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
                    content = _pc_extract_reply(resp)
                    if not content:
                        return {"reply": "❌ Ошибка AI: пустой ответ модели", "images": images}
                    return {"reply": content, "images": images}
            return {"reply": f"❌ Ошибка AI: {resp.status_code}", "images": images}
        try:
            data = resp.json()
        except Exception:
            return {"reply": "❌ Ошибка AI: не удалось прочитать ответ модели", "images": images}
        if not isinstance(data, dict) or not data.get("choices"):
            return {"reply": "❌ Ошибка AI: пустой ответ модели", "images": images}
        msg = data["choices"][0].get("message")
        if not isinstance(msg, dict):
            return {"reply": "❌ Ошибка AI: пустой ответ модели", "images": images}
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
                try:
                    result, data_uri = _pc_exec_tool(state, name, args)
                except Exception as exc:
                    result = f"Ошибка выполнения инструмента {name}: {exc}"
                    data_uri = None
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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 700px; width: 100%; padding: 12px; height: 100vh; display: flex; flex-direction: column; }
        .header { display: flex; align-items: center; gap: 10px; padding: 8px 0; flex-shrink: 0; }
        .header h1 { font-size: 20px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .char-bar { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 10px; margin-bottom: 10px; flex-shrink: 0; }
        .char-bar .avatar { font-size: 28px; }
        .char-bar .info { flex: 1; }
        .char-bar .info .name { font-size: 15px; font-weight: 600; }
        .char-bar .info .hint { font-size: 12px; color: var(--bb-muted); margin-top: 2px; }
        .chat-box { flex: 1; overflow-y: auto; padding: 14px; background: var(--gh-bg2); border-radius: 12px; margin-bottom: 10px; display: flex; flex-direction: column; gap: 10px; }
        .msg { display: flex; flex-direction: column; }
        .msg-user { align-items: flex-end; }
        .msg-bot { align-items: flex-start; }
        .msg-label { font-size: 11px; color: var(--bb-muted); margin-bottom: 3px; }
        .msg-text { padding: 10px 14px; border-radius: 14px; max-width: 85%; font-size: 15px; line-height: 1.45; }
        .msg-user .msg-text { background: var(--bb-accent); color: white; border-bottom-right-radius: 4px; }
        .msg-bot .msg-text { background: var(--bb-panel); color: var(--bb-text); border-bottom-left-radius: 4px; }
        .controls { display: flex; gap: 8px; flex-shrink: 0; padding-bottom: 12px; }
        .controls select { width: 160px; flex-shrink: 0; padding: 12px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); }
        .controls input { flex: 1; padding: 12px 16px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); }
        .controls input:focus, .controls select:focus { outline: none; border-color: var(--bb-accent); }
        .controls button { padding: 12px 20px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; cursor: pointer; font-size: 15px; font-weight: 600; flex-shrink: 0; }
        .controls button:hover { background: var(--bb-accent2); }
        .controls .upload-btn { background: var(--bb-primary); color: var(--bb-text); font-size: 18px; padding: 12px 14px; }
        .controls .upload-btn:hover { background: var(--bb-link); }
        .msg img.msg-img { max-width: 85%; max-height: 300px; border-radius: 12px; margin-top: 8px; display: block; }
        .file-chip { display: inline-flex; align-items: center; gap: 6px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 8px; padding: 4px 10px; margin-right: 6px; font-size: 12px; color: var(--bb-muted); }
        .file-chip b { color: var(--bb-text); font-weight: 500; }
        .loading { text-align: center; color: var(--bb-muted); padding: 16px; font-size: 14px; }
        .welcome { text-align: center; color: #555; padding: 40px 20px; font-size: 14px; line-height: 1.6; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--bb-primary); border-radius: 3px; }
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
    try { chatHistory = JSON.parse(localStorage.getItem('ai_chat_history') || '[]') || []; } catch(e) { chatHistory = []; }
    var pendingFiles = [];
    var USER_ID = localStorage.getItem('web_user_id');
    if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10); localStorage.setItem('web_user_id', USER_ID); }

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
            chip.innerHTML = '<b>' + f.name + '</b> ' + Math.round(f.size / 1024) + ' КБ <a href="#" onclick="removeFile(' + i + ');return false;" style="color:var(--bb-accent);text-decoration:none">✕</a>';
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
                chatHistory.push({role: 'user', content: text});
                chatHistory.push({role: 'assistant', content: reply});
                if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
                try { localStorage.setItem('ai_chat_history', JSON.stringify(chatHistory)); } catch(e) {}
            } catch(e) {
                console.error('AI Chat: parse error', e, xhr.responseText);
                var detail = (e && e.message) ? e.message : 'неизвестная ошибка';
                addMsg('bot', 'Ошибка ответа. ' + detail);
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
    chatHistory.forEach(function(m) { if (m && m.role && m.content) addMsg(m.role === 'user' ? 'user' : 'bot', m.content); });
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
        msg = f"❌ Внутренняя ошибка сервера: {exc}"
        return jsonify({"error": msg, "reply": msg, "images": []}), 500


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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 640px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { flex: 1; min-width: 140px; padding: 12px; background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 12px; color: var(--bb-muted); font-size: 14px; cursor: pointer; text-align: center; transition: all 0.15s; }
        .tab.active { background: var(--bb-accent); color: white; border-color: var(--bb-accent); }
        .tab:hover { background: var(--bb-link); }
        .panel { display: none; }
        .panel.active { display: block; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 24px; margin-bottom: 16px; }
        .card h3 { font-size: 16px; color: var(--bb-accent); margin-bottom: 14px; }
        .stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--bb-primary); font-size: 14px; }
        .stat-row:last-child { border-bottom: none; }
        .stat-row .label { color: var(--bb-muted); }
        .stat-row .value { color: var(--bb-text); font-weight: 600; }
        .input-group { display: flex; gap: 8px; margin-bottom: 16px; }
        input[type="text"] { flex: 1; padding: 12px 14px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 10px; color: var(--bb-text); font-size: 15px; }
        input[type="text"]::placeholder { color: var(--bb-muted); }
        .btn { padding: 12px 18px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; font-size: 14px; cursor: pointer; transition: background 0.15s; white-space: nowrap; }
        .btn:hover { background: var(--bb-accent2); }
        .btn.secondary { background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); }
        .btn.secondary:hover { background: var(--bb-link); }
        .btn:disabled { opacity: 0.5; cursor: default; }
        .msg { padding: 14px 16px; border-radius: 10px; margin: 12px 0; font-size: 14px; line-height: 1.5; }
        .msg.ok { background: var(--bb-green); border: 1px solid var(--bb-green2); }
        .msg.err { background: var(--bb-red); border: 1px solid var(--bb-red); }
        .msg.info { background: var(--bb-primary); border: 1px solid var(--bb-link); }
        .board { display: block; width: 100%; max-width: 360px; margin: 0 auto 16px; border-radius: 8px; }
        .puzzle-meta { text-align: center; margin-bottom: 14px; color: var(--bb-muted); font-size: 13px; line-height: 1.7; }
        .coins { display: inline-block; background: #ffd70033; color: #ffd700; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 14px; }
        .history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--bb-primary); font-size: 13px; color: var(--bb-muted); }
        .history-item:last-child { border-bottom: none; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
        .badge.online { background: var(--bb-green); color: #7ef29d; }
        .badge.offline { background: var(--bb-border); color: var(--bb-muted); }
        .spinner { text-align: center; color: var(--bb-muted); padding: 24px 0; font-size: 14px; }
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
    var urlUserId = new URLSearchParams(window.location.search).get('user_id');
    if (urlUserId && urlUserId !== USER_ID) { USER_ID = urlUserId; localStorage.setItem('chess_user_id', USER_ID); }
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
                        hubTrack('chess', 0, ['chess_link']);
                        loadStats();
                    } else if (x.status === 409 && r.conflict) {
                        document.getElementById('link-msg').innerHTML =
                            '<div class="msg err">' + esc(r.error || 'Аккаунт уже привязан.') +
                            '</div><div class="input-group" style="margin-top:10px;"><button class="btn" id="link-force-btn">🔓 Это мой аккаунт — забрать</button></div>';
                        var forceBtn = document.getElementById('link-force-btn');
                        forceBtn.addEventListener('click', function() {
                            forceBtn.disabled = true;
                            var x2 = new XMLHttpRequest();
                            x2.open('POST', '/api/chess/link');
                            x2.setRequestHeader('Content-Type', 'application/json');
                            x2.onload = function() {
                                var r2;
                                try { r2 = JSON.parse(x2.responseText); } catch(e) { r2 = {}; }
                                if (x2.status === 200 && r2.ok) {
                                    document.getElementById('link-msg').innerHTML = '<div class="msg ok">✅ Аккаунт перенесён на вас!</div>';
                                    hubTrack('chess', 0, ['chess_link']);
                                    loadStats();
                                } else {
                                    document.getElementById('link-msg').innerHTML = '<div class="msg err">' + esc(r2.error || 'Не удалось привязать аккаунт.') + '</div>';
                                }
                            };
                            x2.onerror = function() { forceBtn.disabled = false; document.getElementById('link-msg').innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
                            x2.send(JSON.stringify({user_id: USER_ID, lichess_username: nick, force: true}));
                        });
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
                hubTrack('chess', 0, ['chess_search']);
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
                var r;
                try { r = JSON.parse(x.responseText); } catch(e) { msg.innerHTML = '<div class="msg err">Ошибка сервера.</div>'; return; }
                if (r.correct) {
                    msg.innerHTML = '<div class="msg ok">✅ Правильно! Ход: ' + esc(r.move) + '<br>💰 +5 монет</div>';
                    hubTrack('chess', 1);
                } else {
                    msg.innerHTML = '<div class="msg err">❌ Неверно. Правильный ход: ' + esc(r.move) + '</div>';
                }
            };
            x.onerror = function() { checkBtn.disabled = false; msg.innerHTML = '<div class="msg err">Сетевая ошибка.</div>'; };
            x.send(JSON.stringify({user_id: USER_ID, move: move}));
        }
        function showRegNotice() {
            try {
                if (sessionStorage.getItem('reg_notice_shown')) return;
                sessionStorage.setItem('reg_notice_shown', '1');
                var re = document.getElementById('hub-reg-notice');
                if (!re) {
                    re = document.createElement('div');
                    re.id = 'hub-reg-notice';
                    re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                    re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                    document.body.appendChild(re);
                }
                clearTimeout(re._t);
                re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
            } catch(e) {}
        }
        function hubTrack(module, actions, events) {
            actions = actions || 1;
            events = events || [];
            var token = localStorage.getItem('web_token') || '';
            var uid = localStorage.getItem('web_user_id') || '';
            try {
                if (token && uid.indexOf('u') === 0) {
                    fetch('/api/achievements/activity', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                        body: JSON.stringify({ module: module, actions: actions, events: events })
                    }).then(function(r) { return r.json(); }).then(function(d) {
                        if (d && d.unlocked_detail && d.unlocked_detail.length) {
                            var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                            var pe = document.getElementById('hub-popup');
                            if (!pe) {
                                pe = document.createElement('div');
                                pe.id = 'hub-popup';
                                pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                document.body.appendChild(pe);
                            }
                            pe.innerHTML = '🏆 ' + names.join('<br>');
                            pe.style.display = 'block';
                            clearTimeout(pe._t);
                            pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                        }
                    }).catch(function() {});
                } else {
                    showRegNotice();
                    var today = new Date();
                    var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                    var acts = {};
                    try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                    acts[dayStr] = (acts[dayStr] || 0) + 1;
                    localStorage.setItem('hub_activity', JSON.stringify(acts));
                }
            } catch(e) {}
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
    force = bool(data.get("force"))
    ok = link_chess_account(uid, profile["username"], force=force)
    if not ok:
        return jsonify({"error": "Этот Lichess аккаунт уже привязан к другому пользователю", "conflict": True}), 409
    return jsonify({"ok": True, "username": profile["username"]})


@app.route("/api/chess/puzzle", methods=["POST"])
def api_chess_puzzle():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    if not user_id_raw:
        return jsonify({"error": "Нет user_id"}), 400
    uid = _web_user_id(user_id_raw)
    now_ts = time.time()
    stale = [k for k, v in _PENDING_PUZZLES.items() if now_ts - v.get("created_at", 0) > _PENDING_PUZZLE_TTL]
    for k in stale:
        _PENDING_PUZZLES.pop(k, None)
    account = get_chess_account(uid)
    if not account:
        return jsonify({"error": "Сначала привяжите Lichess аккаунт в разделе «Моя статистика»"}), 400
    remaining = _puzzle_cooldown_remaining_hours(uid)
    if remaining is not None:
        return jsonify({
            "error": f"Следующая задача доступна через {remaining:.1f} ч.",
            "cooldown": True,
            "cooldown_hours": round(remaining, 1),
        }), 429
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
        "created_at": time.time(),
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
    pending = _PENDING_PUZZLES.pop(uid, None)
    if not pending or not pending.get("web"):
        return jsonify({"error": "Задача не найдена или устарела. Загрузите новую."}), 400
    if time.time() - pending.get("created_at", 0) > _PENDING_PUZZLE_TTL:
        return jsonify({"error": "Задача устарела. Загрузите новую."}), 400
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
    return jsonify({"correct": correct, "move": first_move})


# ===== Web Auth (Register / Login) =====

@app.route("/register")
def register_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Регистрация — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 460px; width: 100%; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 32px; }
        .header { text-align: center; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--bb-accent); }
        .header p { color: var(--bb-muted); font-size: 14px; margin-top: 8px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--bb-muted); margin-bottom: 6px; }
        .form-group label .req { color: var(--bb-accent); }
        .form-group label .opt { color: var(--bb-muted); font-weight: 400; }
        .form-group input { width: 100%; padding: 12px 14px; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); }
        .form-group input:focus { outline: none; border-color: var(--bb-accent); }
        .divider { height: 1px; background: var(--bb-link); margin: 20px 0; }
        .btn { width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; }
        .btn:hover { background: var(--bb-accent2); }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .btn-secondary { background: var(--bb-primary); color: var(--bb-text); margin-top: 12px; }
        .btn-secondary:hover { background: var(--bb-link); }
        .info-box { background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; padding: 14px; margin-top: 16px; font-size: 13px; color: var(--bb-muted); line-height: 1.5; }
        .info-box strong { color: var(--bb-accent); }
        .link { color: var(--bb-accent); text-decoration: none; }
        .link:hover { text-decoration: underline; }
        .back-link { display: inline-block; margin-top: 20px; color: var(--bb-muted); text-decoration: none; font-size: 14px; }
        .back-link:hover { color: var(--bb-accent); }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--bb-green); color: white; padding: 12px 24px; border-radius: 10px; display: none; z-index: 100; }
        .toast.error { background: var(--bb-red); }
        @media (max-width: 480px) { .card { padding: 24px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <div class="header">
            <h1>LTHub</h1>
            <p>Регистрация для синхронизации данных между устройствами</p>
        </div>
        <div class="form-group">
            <label>Email <span class="req">*</span></label>
            <input type="email" id="reg-email" placeholder="example@domain.com" autocomplete="email">
        </div>
        <div class="form-group">
            <label>Логин <span class="req">*</span></label>
            <input type="text" id="reg-login" placeholder="например: lucas" autocomplete="username">
        </div>
        <div class="form-group">
            <label>Пароль <span class="req">*</span></label>
            <input type="password" id="reg-password" placeholder="минимум 6 символов" autocomplete="new-password">
        </div>
        <div class="divider"></div>
        <div class="form-group">
            <label>Имя <span class="opt">(необязательно)</span></label>
            <input type="text" id="reg-name" placeholder="если пусто — будет логин" autocomplete="nickname">
        </div>
        <div class="form-group">
            <label>Geometry Dash nickname <span class="opt">(необязательно)</span></label>
            <input type="text" id="reg-gd" placeholder="например: lucasGD" autocomplete="off">
        </div>
        <div class="form-group">
            <label>Telegram ID <span class="opt">(необязательно)</span></label>
            <input type="number" id="reg-tg" placeholder="123456789" autocomplete="off">
        </div>
        <div class="form-group">
            <label>Lichess nickname <span class="opt">(необязательно)</span></label>
            <input type="text" id="reg-lichess" placeholder="например: lucas_chess" autocomplete="off">
        </div>
        <button class="btn" onclick="doRegister()">Зарегистрироваться</button>
        <div class="info-box">
            <strong>Уже есть аккаунт?</strong>
            <a class="link" href="/login">Войти</a>
            <br><br>
            Опциональные поля можно заполнить позже в <a class="link" href="/account">личном кабинете</a>.
            Анонимный режим по-прежнему работает без регистрации.
        </div>
        <a href="/" class="back-link">← На главную</a>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
    function showToast(msg, error) {
        var t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast' + (error ? ' error' : '');
        t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3500);
    }
    function doRegister() {
        var login = document.getElementById('reg-login').value.trim();
        var password = document.getElementById('reg-password').value;
        if (!login || !password) { showToast('Логин и пароль обязательны', true); return; }
        if (password.length < 6) { showToast('Пароль минимум 6 символов', true); return; }
        var nameVal = document.getElementById('reg-name').value.trim();
        var gdVal = document.getElementById('reg-gd').value.trim();
        var lichessVal = document.getElementById('reg-lichess').value.trim();
        var emailVal = document.getElementById('reg-email').value.trim();
        if (nameVal.length > 100) { showToast('Имя слишком длинное (макс. 100 символов)', true); return; }
        if (gdVal.length > 50) { showToast('GD ник слишком длинный (макс. 50 символов)', true); return; }
        if (lichessVal.length > 50) { showToast('Lichess ник слишком длинный (макс. 50 символов)', true); return; }
        if (!emailVal) { showToast('Email обязателен', true); return; }
        var payload = {
            login: login,
            password: password,
            display_name: nameVal || null,
            gd_nickname: gdVal || null,
            lichess_nickname: lichessVal || null,
            email: emailVal || null
        };
        document.querySelector('.btn').disabled = true;
        fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(r) {
            document.querySelector('.btn').disabled = false;
            if (r.error) { showToast(r.error, true); }
            else {
                localStorage.setItem('web_user_id', 'u' + r.user_id);
                localStorage.setItem('web_token', r.token);
                showToast('Аккаунт создан!');
                setTimeout(function() { window.location.href = '/'; }, 800);
            }
        }).catch(function() { document.querySelector('.btn').disabled = false; showToast('Ошибка сети', true); });
    }
</script>
</body>
</html>"""
    return html


@app.route("/login")
def login_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 420px; width: 100%; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 32px; }
        .header { text-align: center; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--bb-accent); }
        .header p { color: var(--bb-muted); font-size: 14px; margin-top: 8px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--bb-muted); margin-bottom: 6px; }
        .form-group input { width: 100%; padding: 12px 14px; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); }
        .form-group input:focus { outline: none; border-color: var(--bb-accent); }
        .btn { width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; }
        .btn:hover { background: var(--bb-accent2); }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .btn-secondary { background: var(--bb-primary); color: var(--bb-text); margin-top: 12px; }
        .btn-secondary:hover { background: var(--bb-link); }
        .link { color: var(--bb-accent); text-decoration: none; }
        .link:hover { text-decoration: underline; }
        .back-link { display: inline-block; margin-top: 20px; color: var(--bb-muted); text-decoration: none; font-size: 14px; }
        .back-link:hover { color: var(--bb-accent); }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--bb-green); color: white; padding: 12px 24px; border-radius: 10px; display: none; z-index: 100; }
        .toast.error { background: var(--bb-red); }
        @media (max-width: 480px) { .card { padding: 24px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="card">
        <div class="header">
            <h1>LTHub</h1>
            <p>Вход в аккаунт</p>
        </div>
        <div class="form-group">
            <label>Логин</label>
            <input type="text" id="login-login" placeholder="ваш логин" autocomplete="username">
        </div>
        <div class="form-group">
            <label>Пароль</label>
            <input type="password" id="login-password" placeholder="ваш пароль" autocomplete="current-password">
        </div>
        <button class="btn" onclick="doLogin()">Войти</button>
        <div class="info-box" style="margin-top:16px">
            Нет аккаунта? <a class="link" href="/register">Зарегистрироваться</a>
        </div>
        <a href="/" class="back-link">← На главную</a>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
    function showToast(msg, error) {
        var t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast' + (error ? ' error' : '');
        t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3500);
    }
    function doLogin() {
        var login = document.getElementById('login-login').value.trim();
        var password = document.getElementById('login-password').value;
        if (!login || !password) { showToast('Введите логин и пароль', true); return; }
        document.querySelector('.btn').disabled = true;
        fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({login: login, password: password})
        }).then(function(r) { return r.json(); }).then(function(r) {
            document.querySelector('.btn').disabled = false;
            if (r.error) { showToast(r.error, true); }
            else {
                localStorage.setItem('web_user_id', 'u' + r.user_id);
                localStorage.setItem('web_token', r.token);
                showToast('Вход выполнен!');
                setTimeout(function() { window.location.href = '/'; }, 800);
            }
        }).catch(function() { document.querySelector('.btn').disabled = false; showToast('Ошибка сети', true); });
    }
    document.getElementById('login-password').addEventListener('keydown', function(e) { if (e.key === 'Enter') doLogin(); });
</script>
</body>
</html>"""
    return html


@app.route("/account")
def account_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Личный кабинет — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; }
        .container { max-width: 480px; width: 100%; margin: 0 auto; padding-top: 20px; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--bb-accent); }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 28px; margin-bottom: 20px; }
        .profile-top { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
        .avatar { width: 64px; height: 64px; border-radius: 50%; background: var(--bb-accent); display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; color: white; flex-shrink: 0; }
        .profile-top .who h2 { font-size: 20px; }
        .profile-top .who .login { color: var(--bb-muted); font-size: 14px; margin-top: 2px; }
        .coins-row { display: flex; align-items: center; justify-content: space-between; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 12px; padding: 14px 16px; margin-bottom: 20px; }
        .coins-row .lbl { font-size: 13px; color: var(--bb-muted); }
        .coins-row .val { font-size: 22px; font-weight: 700; color: var(--bb-warn); }
        .ach-box { background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 12px; padding: 14px 16px; margin-bottom: 20px; }
        .ach-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; flex-wrap: wrap; gap: 6px; }
        .ach-title { font-size: 15px; font-weight: 700; color: var(--bb-warn); }
        .ach-stats { font-size: 13px; color: var(--bb-muted); }
        .ach-cal { display: grid; grid-template-columns: repeat(28, 1fr); gap: 3px; margin-bottom: 12px; }
        .cal-cell { height: 12px; border-radius: 3px; background: var(--bb-elev); }
        .cal-cell.cal-on { background: var(--bb-accent); }
        .missing { background: #3e2723; border: 1px solid var(--bb-red); border-radius: 10px; padding: 12px 14px; margin-bottom: 16px; font-size: 13px; color: #ef9a9a; line-height: 1.5; }
        .missing b { color: #ffcdd2; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--bb-muted); margin-bottom: 6px; }
        .form-group label .opt { color: var(--bb-muted); font-weight: 400; }
        .form-group input { width: 100%; padding: 12px 14px; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); }
        .form-group input:focus { outline: none; border-color: var(--bb-accent); }
        .btn { width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; text-align: center; text-decoration: none; display: block; }
        .btn:hover { background: var(--bb-accent2); }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .btn-secondary { background: var(--bb-primary); color: var(--bb-text); margin-top: 10px; }
        .btn-secondary:hover { background: var(--bb-link); }
        .btn-gray { background: var(--bb-border); color: var(--bb-text); margin-top: 10px; }
        .btn-gray:hover { background: var(--bb-border); }
        .link { color: var(--bb-accent); text-decoration: none; }
        .link:hover { text-decoration: underline; }
        .back-link { display: inline-block; margin-top: 4px; color: var(--bb-muted); text-decoration: none; font-size: 14px; }
        .back-link:hover { color: var(--bb-accent); }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--bb-green); color: white; padding: 12px 24px; border-radius: 10px; display: none; z-index: 100; }
        .toast.error { background: var(--bb-red); }
        @media (max-width: 480px) { .card { padding: 20px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Личный кабинет</h1>
        <a href="/">На главную</a>
    </div>
    <div class="card" id="card">
        <p style="color:#888;text-align:center;padding:20px 0">Загрузка...</p>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
    var token = localStorage.getItem('web_token');
    var uid = localStorage.getItem('web_user_id');
    function showToast(msg, error) {
        var t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast' + (error ? ' error' : '');
        t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3000);
    }
    function esc(s) { return (s == null ? '' : String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function render(p) {
        var name = p.display_name || p.login || 'Пользователь';
        var adminLink = p.is_admin ? '<a class="btn btn-secondary" href="/admin">🛠 Админ-панель</a>' : '';
        var html = '<div class="profile-top">' +
            '<div class="avatar">' + esc(name.charAt(0).toUpperCase()) + '</div>' +
            '<div class="who"><h2>' + esc(name) + '</h2><div class="login">@' + esc(p.login || '') + ' · ' + (p.is_admin ? '👨‍💼 Админ' : 'Пользователь') + '</div></div>' +
            '</div>' +
            '<div class="coins-row"><div class="lbl">💎 Монеты</div><div class="val">' + (p.coins != null ? p.coins : 0) + '</div></div>' +
            '<div class="ach-box" id="ach-box"><div class="spinner">Загружаю достижения...</div></div>' +
            '<div id="missing-box"></div>' +
            '<div class="form-group"><label>Логин</label><input type="text" id="set-login" disabled style="opacity:0.6"></div>' +
            '<div class="form-group"><label>Имя <span class="opt">(если пусто — будет логин)</span></label><input type="text" id="set-name" placeholder="ваше имя"></div>' +
            '<div class="form-group"><label>Geometry Dash nickname</label><input type="text" id="set-gd" placeholder="например: lucasGD"></div>' +
            '<div class="form-group"><label>Telegram ID</label><input type="number" id="set-tg" placeholder="123456789"></div>' +
            '<div class="form-group"><label>Lichess nickname</label><input type="text" id="set-lichess" placeholder="например: lucas_chess"></div>' +
            '<button class="btn" id="save-btn" onclick="saveSettings()">Сохранить</button>' +
            adminLink +
            '<button class="btn btn-gray" onclick="logout()">Выйти</button>';
        document.getElementById('card').innerHTML = html;
        fillForm(p);
        loadAchievements();
    }
    function loadAchievements() {
        var box = document.getElementById('ach-box');
        if (!box) return;
        fetch('/api/achievements', { headers: { 'X-Auth-Token': token } })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.error) { box.innerHTML = '<b>Достижения</b><div class="hint">' + esc(d.error) + '</div>'; return; }
                var unlocked = d.unlocked_count || 0;
                var cal = d.calendar || [];
                var streak = d.streak || {};
                var calHtml = '';
                cal.forEach(function(day) {
                    var active = day ? ' class="cal-on"' : '';
                    calHtml += '<div class="cal-cell' + active + '"></div>';
                });
                box.innerHTML = '<div class="ach-head">' +
                    '<div class="ach-title">🏆 Достижения</div>' +
                    '<div class="ach-stats">открыто <b>' + unlocked + '</b> из ' + (d.total_count || 0) + ' · серия <b>' + (streak.current || 0) + '</b> дн.</div>' +
                    '</div>' +
                    '<div class="ach-cal">' + calHtml + '</div>' +
                    '<a class="btn btn-secondary" href="/achievements">Смотреть все достижения</a>';
            })
            .catch(function() { box.innerHTML = '<b>Достижения</b><div class="hint">Не удалось загрузить.</div>'; });
    }
    function fillForm(p) {
        document.getElementById('set-login').value = p.login || '';
        document.getElementById('set-name').value = p.display_name || '';
        document.getElementById('set-gd').value = p.gd_nickname || '';
        document.getElementById('set-tg').value = p.telegram_id || '';
        document.getElementById('set-lichess').value = p.lichess_nickname || '';
        renderMissing(p);
    }
    function renderMissing(p) {
        var box = document.getElementById('missing-box');
        var missing = [];
        if (!p.gd_nickname) missing.push('Geometry Dash nickname');
        if (!p.lichess_nickname) missing.push('Lichess nickname');
        if (!p.telegram_id) missing.push('Telegram ID');
        if (!missing.length) { box.style.display = 'none'; return; }
        box.style.display = 'block';
        box.innerHTML = '<b>Рекомендуем заполнить:</b> ' + missing.join(', ') + '.<br>Это позволит автоматически подставлять данные в GD, шахматы и бюджет.';
    }
    function saveSettings() {
        var nameVal = document.getElementById('set-name').value.trim();
        var gdVal = document.getElementById('set-gd').value.trim();
        var lichessVal = document.getElementById('set-lichess').value.trim();
        if (nameVal.length > 100) { showToast('Имя слишком длинное (макс. 100 символов)', true); return; }
        if (gdVal.length > 50) { showToast('GD ник слишком длинный (макс. 50 символов)', true); return; }
        if (lichessVal.length > 50) { showToast('Lichess ник слишком длинный (макс. 50 символов)', true); return; }
        var payload = {
            display_name: nameVal || null,
            gd_nickname: gdVal || null,
            lichess_nickname: lichessVal || null
        };
        document.getElementById('save-btn').disabled = true;
        fetch('/api/auth/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Auth-Token': token},
            body: JSON.stringify(payload)
        }).then(function(r) { return r.json(); }).then(function(r) {
            document.getElementById('save-btn').disabled = false;
            if (r.error) { showToast(r.error, true); }
            else { showToast('Сохранено!'); setTimeout(function() { window.location.href = '/'; }, 800); }
        }).catch(function() { document.getElementById('save-btn').disabled = false; showToast('Ошибка сети', true); });
    }
    function logout() {
        if (token) {
            fetch('/api/auth/logout', { method: 'POST', headers: { 'X-Auth-Token': token } }).catch(function () {});
        }
        localStorage.removeItem('web_user_id');
        localStorage.removeItem('web_token');
        window.location.href = '/';
    }
    if (!token || !uid || uid.indexOf('u') !== 0) {
        showToast('Вы не вошли в аккаунт', true);
        setTimeout(function() { window.location.href = '/login'; }, 1200);
    } else {
        fetch('/api/auth/me', { headers: { 'X-Auth-Token': token } })
            .then(function(r) { return r.json(); })
            .then(function(p) {
                if (p.error) {
                    localStorage.removeItem('web_token');
                    localStorage.removeItem('web_user_id');
                    showToast(p.error, true);
                    setTimeout(function() { window.location.href = '/login'; }, 1200);
                    return;
                }
                render(p);
            })
            .catch(function() { showToast('Ошибка сети', true); });
    }
</script>
</body>
</html>"""
    return html


@app.route("/suggest")
def suggest_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Предложения — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; }
        .container { max-width: 560px; width: 100%; margin: 0 auto; padding-top: 20px; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 28px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; color: var(--bb-muted); margin-bottom: 6px; }
        .seg { display: flex; gap: 8px; margin-bottom: 16px; }
        .seg button { flex: 1; padding: 12px; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; color: var(--bb-text); font-size: 14px; font-weight: 600; cursor: pointer; }
        .seg button.on { background: var(--bb-accent); border-color: var(--bb-accent); color: var(--gh-text2); }
        .form-group textarea, .form-group input, .form-group select { width: 100%; padding: 12px 14px; background: var(--gh-bg2); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; color: var(--bb-text); font-family: inherit; }
        .form-group textarea { min-height: 120px; resize: vertical; }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus { outline: none; border-color: var(--bb-accent); }
        .btn { width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 8px; }
        .btn:hover { background: var(--bb-accent2); }
        .btn:disabled { background: #555; cursor: not-allowed; }
        .hint { margin-top: 16px; font-size: 13px; color: var(--bb-muted); line-height: 1.5; }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--bb-green); color: white; padding: 12px 24px; border-radius: 10px; display: none; z-index: 100; }
        .toast.error { background: var(--bb-red); }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Предложения</h1>
        <a href="/">На главную</a>
    </div>
    <div class="card">
        <div class="seg">
            <button id="seg-bug" class="on" onclick="setCat('bug')">🐛 Сообщить о баге</button>
            <button id="seg-suggestion" onclick="setCat('suggestion')">💡 Предложение</button>
        </div>
        <div class="form-group">
            <label>Раздел</label>
            <select id="fb-module"></select>
        </div>
        <div class="form-group">
            <label>Текст</label>
            <textarea id="fb-text" placeholder="Опишите проблему или идею..."></textarea>
        </div>
        <button class="btn" onclick="sendFeedback()">Отправить</button>
        <div class="hint">
            Для предложения: что бы вы хотели улучшить и почему.<br>
            Для бага: напишите, что делали и что произошло — это поможет быстрее исправить.
        </div>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
    var category = 'bug';
    var MODULES = [
        ['', '— выберите раздел —'],
        ['hub', 'Главная / хаб'],
        ['verbs', 'Практика глаголов'],
        ['reading', 'Тренажёр чтения'],
        ['endings', 'Тренажёр окончаний'],
        ['family', 'Family Circle'],
        ['daily_prayer', 'Молитва дня'],
        ['gd', 'Geometry Dash'],
        ['chess', 'Шахматы'],
        ['budget', 'Семейный бюджет'],
        ['auth', 'Вход / регистрация / настройки'],
        ['other', 'Другое']
    ];
    function showToast(msg, error) {
        var t = document.getElementById('toast');
        t.textContent = msg; t.className = 'toast' + (error ? ' error' : ''); t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3000);
    }
    function setCat(c) {
        category = c;
        document.getElementById('seg-bug').className = c === 'bug' ? 'on' : '';
        document.getElementById('seg-suggestion').className = c === 'suggestion' ? 'on' : '';
    }
    function sendFeedback() {
        var module = document.getElementById('fb-module').value;
        var message = document.getElementById('fb-text').value.trim();
        if (!module) { showToast('Выберите раздел', true); return; }
        if (!message) { showToast('Введите текст', true); return; }
        document.querySelector('.btn').disabled = true;
        fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Auth-Token': localStorage.getItem('web_token') || '' },
            body: JSON.stringify({ category: category, module: module, message: message })
        }).then(function(r) { return r.json(); }).then(function(r) {
            document.querySelector('.btn').disabled = false;
            if (r.error) { showToast(r.error, true); }
            else { showToast('Спасибо! Отправлено'); document.getElementById('fb-text').value = ''; setTimeout(function() { window.location.href = '/'; }, 1500); }
        }).catch(function() { document.querySelector('.btn').disabled = false; showToast('Ошибка сети', true); });
    }
    (function() {
        var sel = document.getElementById('fb-module');
        var params = new URLSearchParams(window.location.search);
        var preModule = params.get('module') || '';
        var preCat = params.get('type') || 'bug';
        setCat(preCat === 'suggestion' ? 'suggestion' : 'bug');
        sel.innerHTML = MODULES.map(function(m) { return '<option value="' + m[0] + '">' + m[1] + '</option>'; }).join('');
        if (preModule) sel.value = preModule;
        var preMsg = params.get('msg');
        if (preMsg) document.getElementById('fb-text').value = decodeURIComponent(preMsg);
    })();
</script>
</body>
</html>"""
    return html


@app.route("/settings")
def settings_page():
    return redirect("/account", code=301)


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """Создать аккаунт с логином/паролем и опциональными полями."""
    data = request.get_json(silent=True) or {}
    login = (data.get("login") or "").strip().lower()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip()
    if not login or not password:
        return jsonify({"error": "Логин и пароль обязательны"}), 400
    if not email:
        return jsonify({"error": "Email обязателен"}), 400
    if len(login) < 3:
        return jsonify({"error": "Логин минимум 3 символа"}), 400
    if len(password) < 6:
        return jsonify({"error": "Пароль минимум 6 символов"}), 400
    if not re.match(r"^[a-z0-9_]+$", login):
        return jsonify({"error": "Логин: только латиница, цифры и _"}), 400
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Неверный формат email"}), 400
    
    display_name = (data.get("display_name") or "").strip() or login
    gd_nickname = (data.get("gd_nickname") or "").strip() or None
    lichess_nickname = (data.get("lichess_nickname") or "").strip() or None
    if len(display_name) > 100:
        return jsonify({"error": "Имя слишком длинное (макс. 100 символов)"}), 400
    if gd_nickname and len(gd_nickname) > 50:
        return jsonify({"error": "GD ник слишком длинный (макс. 50 символов)"}), 400
    if lichess_nickname and len(lichess_nickname) > 50:
        return jsonify({"error": "Lichess ник слишком длинный (макс. 50 символов)"}), 400
    
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM web_users WHERE login = :login"), {"login": login}
            ).mappings().first()
            if existing:
                return jsonify({"error": "Логин уже занят"}), 409
            result = conn.execute(
                text("""
                    INSERT INTO web_users (login, password_hash, display_name, gd_nickname, telegram_id, lichess_nickname, email, is_admin)
                    VALUES (:login, :hash, :name, :gd, :tg, :lichess, :email, FALSE)
                    RETURNING id
                """),
                {
                    "login": login,
                    "hash": _hash_password(password),
                    "name": display_name,
                    "gd": gd_nickname,
                    "tg": None,
                    "lichess": lichess_nickname,
                    "email": email,
                },
            )
            user_id = result.scalar()
            conn.commit()
    except Exception as exc:
        print(f"[AUTH] register error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500

    token = _create_session(user_id)
    if not token:
        return jsonify({"error": "Не удалось создать сессию"}), 500
    return jsonify({"user_id": user_id, "token": token, "login": login})


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """Войти по логину/паролю."""
    data = request.get_json(silent=True) or {}
    login = (data.get("login") or "").strip().lower()
    password = data.get("password") or ""
    if not login or not password:
        return jsonify({"error": "Логин и пароль обязательны"}), 400
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, password_hash FROM web_users WHERE login = :login"),
                {"login": login},
            ).mappings().first()
    except Exception as exc:
        print(f"[AUTH] login error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    if not row or not _verify_password(password, row["password_hash"]):
        return jsonify({"error": "Неверный логин или пароль"}), 401
    token = _create_session(row["id"])
    if not token:
        return jsonify({"error": "Не удалось создать сессию"}), 500
    return jsonify({"user_id": row["id"], "token": token, "login": login})


@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    """Получить профиль текущего пользователя по токену."""
    token = _auth_token_from_request()
    user = _get_session_user(token)
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    try:
        coins = get_user_coins(_web_user_id("u" + str(user["id"])))
        user["coins"] = int((coins or {}).get("balance", 0))
    except Exception as exc:
        print(f"[AUTH] me coins error: {exc}")
        user["coins"] = 0
    return jsonify(user)


@app.route("/api/auth/update", methods=["POST"])
def api_auth_update():
    """Обновить опциональные поля профиля."""
    token = _auth_token_from_request()
    user = _get_session_user(token)
    if not user:
        return jsonify({"error": "Не авторизован"}), 401
    data = request.get_json(silent=True) or {}
    display_name = (data.get("display_name") or "").strip() or None
    gd_nickname = (data.get("gd_nickname") or "").strip() or None
    lichess_nickname = (data.get("lichess_nickname") or "").strip() or None
    if display_name and len(display_name) > 100:
        return jsonify({"error": "Имя слишком длинное (макс. 100 символов)"}), 400
    if gd_nickname and len(gd_nickname) > 50:
        return jsonify({"error": "GD ник слишком длинный (макс. 50 символов)"}), 400
    if lichess_nickname and len(lichess_nickname) > 50:
        return jsonify({"error": "Lichess ник слишком длинный (макс. 50 символов)"}), 400
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE web_users
                    SET display_name = COALESCE(:name, login),
                        gd_nickname = :gd,
                        lichess_nickname = :lichess
                    WHERE id = :uid
                """),
                {
                    "name": display_name,
                    "gd": gd_nickname,
                    "lichess": lichess_nickname,
                    "uid": user["id"],
                },
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as exc:
        print(f"[AUTH] update error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Завершить сессию."""
    token = _auth_token_from_request()
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM web_sessions WHERE token = :t"), {"t": token})
            conn.commit()
    except Exception as exc:
        print(f"[AUTH] logout error: {exc}")
    return jsonify({"success": True})


# ===== Admin Panel (WEB-07) =====

def _admin_require():
    """Return current web admin or abort with 401/403."""
    user = _web_admin_session()
    if not user:
        return None
    return user


@app.route("/api/admin/stats", methods=["GET"])
def api_admin_stats():
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            wu = conn.execute(text("SELECT COUNT(*) AS c FROM web_users")).mappings().first()
            adm = conn.execute(text("SELECT COUNT(*) AS c FROM web_users WHERE is_admin = TRUE")).mappings().first()
            coins = conn.execute(text("SELECT COALESCE(SUM(balance),0) AS s FROM user_coins")).mappings().first()
            tg = conn.execute(text("SELECT COUNT(*) AS c FROM users")).mappings().first()
            tx = conn.execute(text("SELECT COUNT(*) AS c FROM web_coin_log")).mappings().first()
        return jsonify({
            "web_users": int(wu["c"] or 0),
            "admins": int(adm["c"] or 0),
            "total_coins": int(coins["s"] or 0),
            "telegram_users": int(tg["c"] or 0),
            "coin_tx": int(tx["c"] or 0),
        })
    except Exception as exc:
        print(f"[ADMIN] stats error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    q = (request.args.get("q") or "").strip().lower()
    try:
        with get_db_engine().connect() as conn:
            if q:
                rows = conn.execute(
                    text("""
                        SELECT u.id, u.login, u.display_name, u.gd_nickname, u.telegram_id,
                               u.lichess_nickname, u.is_admin, u.created_at
                        FROM web_users u
                        WHERE LOWER(u.login) LIKE :p OR LOWER(u.display_name) LIKE :p
                           OR COALESCE(LOWER(u.gd_nickname), '') LIKE :p
                        ORDER BY u.created_at DESC LIMIT 100
                    """),
                    {"p": f"%{q}%"},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text("""
                        SELECT u.id, u.login, u.display_name, u.gd_nickname, u.telegram_id,
                               u.lichess_nickname, u.is_admin, u.created_at
                        FROM web_users u
                        ORDER BY u.created_at DESC LIMIT 100
                    """),
                ).mappings().all()
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "login": r["login"],
                "display_name": r["display_name"],
                "gd_nickname": r["gd_nickname"],
                "telegram_id": r["telegram_id"],
                "lichess_nickname": r["lichess_nickname"],
                "is_admin": bool(r["is_admin"]),
                "created_at": str(r["created_at"]) if r["created_at"] else None,
                "balance": 0,
            })
        # Batch-fetch coin balances: user_coins stores _web_user_id('u<id>')
        if result:
            ids = [_web_user_id("u" + str(u["id"])) for u in result]
            with get_db_engine().connect() as conn:
                coins = conn.execute(
                    text("SELECT user_id, balance FROM user_coins WHERE user_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                    {"ids": ids},
                ).mappings().all()
            coin_map = {int(c["user_id"]): int(c["balance"] or 0) for c in coins}
            for u in result:
                u["balance"] = coin_map.get(_web_user_id("u" + str(u["id"])), 0)
        return jsonify(result)
    except Exception as exc:
        print(f"[ADMIN] users error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/users/<int:user_id>/coins", methods=["GET"])
def api_admin_user_coins(user_id):
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    uid = _web_user_id("u" + str(user_id))
    try:
        with get_db_engine().connect() as conn:
            coins = conn.execute(
                text("SELECT COALESCE(balance, 0) AS b FROM user_coins WHERE user_id = :uid"),
                {"uid": uid},
            ).mappings().first()
            log = conn.execute(
                text("SELECT amount, description, created_at FROM web_coin_log WHERE user_id = :uid ORDER BY created_at DESC LIMIT 50"),
                {"uid": uid},
            ).mappings().all()
        return jsonify({
            "balance": int(coins["b"] or 0) if coins else 0,
            "log": [
                {"amount": int(r["amount"] or 0), "description": r["description"] or "", "created_at": str(r["created_at"]) if r["created_at"] else None}
                for r in log
            ],
        })
    except Exception as exc:
        print(f"[ADMIN] user coins error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/coins/award", methods=["POST"])
def api_admin_coins_award():
    admin = _admin_require()
    if not admin:
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
        amount = int(data.get("amount") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректные данные"}), 400
    if not user_id:
        return jsonify({"error": "Укажите пользователя"}), 400
    if amount == 0:
        return jsonify({"error": "Сумма не может быть нулевой"}), 400
    if not _award_web_coins(user_id, amount, data.get("description") or "Начисление админом"):
        return jsonify({"error": "Не удалось начислить монеты"}), 500
    return jsonify({"success": True, "user_id": user_id, "amount": amount})


@app.route("/api/admin/set_admin", methods=["POST"])
def api_admin_set_admin():
    admin = _admin_require()
    if not admin:
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректные данные"}), 400
    if not user_id:
        return jsonify({"error": "Укажите пользователя"}), 400
    if user_id == admin["id"]:
        return jsonify({"error": "Нельзя менять статус самого себя"}), 400
    is_admin = bool(data.get("is_admin"))
    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text("UPDATE web_users SET is_admin = :v WHERE id = :uid"),
                {"v": is_admin, "uid": user_id},
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as exc:
        print(f"[ADMIN] set_admin error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/errors", methods=["GET"])
def api_admin_errors():
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    return jsonify({"count": len(_ERROR_LOG), "errors": list(reversed(_ERROR_LOG[-50:]))})


@app.route("/api/admin/errors/clear", methods=["POST"])
def api_admin_errors_clear():
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    _ERROR_LOG.clear()
    return jsonify({"success": True})


@app.route("/api/feedback", methods=["POST"])
def api_feedback_submit():
    """Submit a suggestion or bug report (any web user or anonymous)."""
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "").strip().lower()
    message = (data.get("message") or "").strip()
    if category not in ("suggestion", "bug"):
        return jsonify({"error": "Некорректная категория"}), 400
    if len(message) < 3:
        return jsonify({"error": "Опишите сообщение подробнее"}), 400
    module = (data.get("module") or "").strip()[:64]
    user = _get_session_user(_auth_token_from_request())
    user_id = user.get("id") if user else None
    login = user.get("login") if user else None
    author_name = (user.get("display_name") or login) if user else None
    try:
        with get_db_engine().connect() as conn:
            conn.execute(text("""
                INSERT INTO web_feedback (user_id, login, author_name, category, module, message)
                VALUES (:uid, :login, :name, :cat, :mod, :msg)
            """), {
                "uid": user_id,
                "login": login,
                "name": author_name,
                "cat": category,
                "mod": module or None,
                "msg": message[:4000],
            })
            conn.commit()
    except Exception as exc:
        print(f"[FEEDBACK] submit error: {exc}")
        return jsonify({"error": "Не удалось сохранить"}), 500
    tag = "🐛 Баг" if category == "bug" else "💡 Предложение"
    notify_admin(f"{tag} (модуль: {module or 'не указан'})\n{message[:300]}")
    return jsonify({"success": True, "id": None})


@app.route("/api/admin/feedback", methods=["GET"])
def api_admin_feedback():
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    status = (request.args.get("status") or "").strip()
    category = (request.args.get("category") or "").strip()
    try:
        with get_db_engine().connect() as conn:
            if status:
                rows = conn.execute(text("""
                    SELECT id, login, author_name, category, module, message, status, created_at
                    FROM web_feedback WHERE status = :s ORDER BY created_at DESC LIMIT 200
                """), {"s": status}).mappings().all()
            elif category:
                rows = conn.execute(text("""
                    SELECT id, login, author_name, category, module, message, status, created_at
                    FROM web_feedback WHERE category = :c ORDER BY created_at DESC LIMIT 200
                """), {"c": category}).mappings().all()
            else:
                rows = conn.execute(text("""
                    SELECT id, login, author_name, category, module, message, status, created_at
                    FROM web_feedback ORDER BY (status = 'open') DESC, created_at DESC LIMIT 200
                """)).mappings().all()
        return jsonify({"count": len(rows), "items": [dict(r) for r in rows]})
    except Exception as exc:
        print(f"[FEEDBACK] list error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/feedback/<int:fid>", methods=["DELETE"])
def api_admin_feedback_delete(fid):
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            conn.execute(text("DELETE FROM web_feedback WHERE id = :id"), {"id": fid})
            conn.commit()
    except Exception as exc:
        print(f"[FEEDBACK] delete error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/admin")
def admin_page():
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ-панель — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text); padding: 20px; }
        .container { max-width: 900px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--gh-accent); }
        .header a { color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--gh-accent); }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 10px 16px; border: 1px solid var(--gh-border); border-radius: 10px; background: var(--gh-panel); color: var(--gh-muted); font-size: 14px; font-family: inherit; cursor: pointer; transition: all 0.15s; }
        .tab:hover { border-color: var(--gh-accent); color: var(--gh-text); }
        .tab.active { background: var(--gh-accent); border-color: var(--gh-accent); color: var(--gh-text2); }
        .panel { display: none; }
        .panel.active { display: block; }
        .card { background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
        .stat-card { background: var(--gh-bg); border: 1px solid var(--gh-border); border-radius: 10px; padding: 16px; text-align: center; }
        .stat-card .value { font-size: 26px; font-weight: 700; color: var(--gh-accent); }
        .stat-card .label { font-size: 12px; color: var(--gh-muted); margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--gh-border); font-size: 14px; }
        th { color: var(--gh-muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        .input-row { display: flex; gap: 10px; margin-bottom: 16px; }
        .input-row input, .input-row select { flex: 1; padding: 12px; border: 1px solid var(--gh-border); border-radius: 8px; background: var(--gh-bg); color: var(--gh-text); font-size: 15px; font-family: inherit; }
        .input-row input:focus { outline: none; border-color: var(--gh-accent); }
        .btn { padding: 10px 18px; border: none; border-radius: 8px; background: var(--gh-green); color: var(--gh-text2); font-size: 14px; font-family: inherit; cursor: pointer; }
        .btn:hover { background: var(--gh-green); }
        .btn-danger { background: var(--gh-red); }
        .btn-danger:hover { background: var(--gh-red); }
        .btn-secondary { background: var(--gh-border); color: var(--gh-text); }
        .btn-secondary:hover { background: var(--gh-border); }
        .btn-small { padding: 6px 12px; font-size: 13px; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-admin { background: var(--bb-elev); color: var(--gh-accent); border: 1px solid var(--bb-border); }
        .badge-danger { background: var(--bb-elev); color: var(--gh-red); border: 1px solid var(--bb-border); }
        .badge-user { background: var(--gh-border); color: var(--gh-muted); }
        .error { color: var(--gh-red); margin-top: 8px; }
        .ok { color: var(--bb-green); margin-top: 8px; }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--gh-accent); color: var(--gh-text2); padding: 10px 20px; border-radius: 8px; display: none; z-index: 100; }
        .toast.error { background: var(--gh-red); }
        .search-result { cursor: pointer; }
        .search-result:hover { background: var(--gh-panel); }
        .log-row { padding: 10px 0; border-bottom: 1px solid var(--gh-border); font-size: 13px; line-height: 1.5; }
        .log-ts { color: var(--gh-muted); font-size: 12px; }
        .empty { color: var(--gh-muted); text-align: center; padding: 24px; }
        @media (max-width: 600px) { .tabs { gap: 6px; } .tab { padding: 8px 12px; font-size: 13px; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>👨‍💼 Админ-панель</h1>
        <a href="/">← На главную</a>
    </div>
    <div id="gate" style="display:none; text-align:center; padding:40px;" class="card">
        <p id="gate-msg">Проверка доступа...</p>
    </div>
    <div id="app" style="display:none;">
        <div class="tabs">
            <button class="tab active" data-tab="stats" onclick="showTab('stats')">📊 Статистика</button>
            <button class="tab" data-tab="users" onclick="showTab('users')">👤 Пользователи</button>
            <button class="tab" data-tab="coins" onclick="showTab('coins')">💰 Начисление монет</button>
            <button class="tab" data-tab="errors" onclick="showTab('errors')">📋 Ошибки</button>
            <button class="tab" data-tab="feedback" onclick="showTab('feedback')">💡 Предложения</button>
        </div>
        <div class="panel active" id="panel-stats"></div>
        <div class="panel" id="panel-users"></div>
        <div class="panel" id="panel-coins"></div>
        <div class="panel" id="panel-errors"></div>
        <div class="panel" id="panel-feedback"></div>
    </div>
</div>
<div class="toast" id="toast"></div>
<script>
    var TOKEN = localStorage.getItem('web_token');
    function toast(msg, error) {
        var t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast' + (error ? ' error' : '');
        t.style.display = 'block';
        setTimeout(function() { t.style.display = 'none'; }, 3000);
    }
    function api(path, opts) {
        opts = opts || {};
        opts.headers = opts.headers || {};
        opts.headers['X-Auth-Token'] = TOKEN;
        if (opts.body) opts.headers['Content-Type'] = 'application/json';
        return fetch(path, opts).then(function(r) { return r.json().then(function(j) { return {ok: r.ok, j: j}; }); });
    }
    function showTab(name) {
        document.querySelectorAll('.tab').forEach(function(t) { t.classList.toggle('active', t.dataset.tab === name); });
        document.querySelectorAll('.panel').forEach(function(p) { p.classList.toggle('active', p.id === 'panel-' + name); });
        if (name === 'stats') loadStats();
        if (name === 'users') loadUsers();
        if (name === 'errors') loadErrors();
        if (name === 'feedback') loadFeedback();
    }
    function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

    function loadStats() {
        api('/api/admin/stats').then(function(res) {
            if (!res.ok) { document.getElementById('panel-stats').innerHTML = '<div class="error">' + esc(res.j.error) + '</div>'; return; }
            var s = res.j;
            document.getElementById('panel-stats').innerHTML =
                '<div class="stat-grid">' +
                '<div class="stat-card"><div class="value">' + s.web_users + '</div><div class="label">Веб-пользователей</div></div>' +
                '<div class="stat-card"><div class="value">' + s.admins + '</div><div class="label">Админов</div></div>' +
                '<div class="stat-card"><div class="value">' + s.total_coins + '</div><div class="label">Всего монет</div></div>' +
                '<div class="stat-card"><div class="value">' + s.telegram_users + '</div><div class="label">Telegram-пользователей</div></div>' +
                '<div class="stat-card"><div class="value">' + s.coin_tx + '</div><div class="label">Операций с монетами</div></div>' +
                '</div>';
        });
    }

    function loadUsers(q) {
        var url = '/api/admin/users' + (q ? '?q=' + encodeURIComponent(q) : '');
        api(url).then(function(res) {
            if (!res.ok) { document.getElementById('panel-users').innerHTML = '<div class="error">' + esc(res.j.error) + '</div>'; return; }
            var users = res.j;
            var h = '<div class="input-row"><input id="user-search" placeholder="Поиск по логину, имени, GD никнейму..." value="' + esc(q || '') + '" onkeydown="if(event.key===\\\'Enter\\\'){loadUsers(this.value);}"><button class="btn btn-secondary" onclick="loadUsers(document.getElementById(\\\'user-search\\\').value)">Найти</button></div>';
            h += '<table><tr><th>ID</th><th>Логин</th><th>Имя</th><th>Баланс</th><th>Статус</th><th>Действия</th></tr>';
            if (!users.length) h += '<tr><td colspan="6" class="empty">Пользователи не найдены</td></tr>';
            users.forEach(function(u) {
                h += '<tr>' +
                    '<td>' + u.id + '</td>' +
                    '<td>@' + esc(u.login) + '</td>' +
                    '<td>' + esc(u.display_name) + '</td>' +
                    '<td>' + u.balance + ' 💰</td>' +
                    '<td>' + (u.is_admin ? '<span class="badge badge-admin">Админ</span>' : '<span class="badge badge-user">Пользователь</span>') + '</td>' +
                    '<td><button class="btn btn-secondary btn-small" onclick="viewCoins(' + u.id + ',\\\'' + esc(u.login) + '\\\')">Монеты</button> ' +
                    (u.is_admin
                        ? '<button class="btn btn-danger btn-small" onclick="toggleAdmin(' + u.id + ',false)">Снять админа</button>'
                        : '<button class="btn btn-small" onclick="toggleAdmin(' + u.id + ',true)">Сделать админом</button>') +
                    '</td></tr>';
            });
            h += '</table>';
            document.getElementById('panel-users').innerHTML = h;
        });
    }

    function viewCoins(userId, login) {
        api('/api/admin/users/' + userId + '/coins').then(function(res) {
            if (!res.ok) { toast(res.j.error || 'Ошибка', true); return; }
            var d = res.j;
            var h = '<div class="card"><h3 style="margin-bottom:12px;color:var(--gh-accent)">💰 @' + esc(login) + ' — баланс: ' + d.balance + '</h3>';
            if (!d.log.length) h += '<div class="empty">Операций нет</div>';
            d.log.forEach(function(r) {
                h += '<div class="log-row">' + (r.amount > 0 ? '+' : '') + r.amount + ' монет — ' + esc(r.description) + '<div class="log-ts">' + esc(r.created_at) + '</div></div>';
            });
            h += '<button class="btn btn-secondary" style="margin-top:12px" onclick="loadUsers()">Назад</button></div>';
            document.getElementById('panel-users').innerHTML = h;
        });
    }

    function toggleAdmin(userId, makeAdmin) {
        api('/api/admin/set_admin', {method: 'POST', body: JSON.stringify({user_id: userId, is_admin: makeAdmin})}).then(function(res) {
            if (res.ok) { toast(makeAdmin ? 'Админ назначен' : 'Админ снят'); loadUsers(); }
            else toast(res.j.error || 'Ошибка', true);
        });
    }

    function loadCoinsPanel() {
        api('/api/admin/users?q=').then(function(res) {
            if (!res.ok) return;
            var users = res.j;
            var opts = users.map(function(u) { return '<option value="' + u.id + '">@' + esc(u.login) + ' (id ' + u.id + ')</option>'; }).join('');
            document.getElementById('panel-coins').innerHTML =
                '<div class="card"><h3 style="margin-bottom:16px;color:var(--gh-accent)">Начисление монет</h3>' +
                '<div class="input-row"><select id="coin-user">' + opts + '</select></div>' +
                '<div class="input-row"><input type="number" id="coin-amount" placeholder="Сумма (можно отрицательная)"></div>' +
                '<div class="input-row"><input type="text" id="coin-desc" placeholder="Описание"></div>' +
                '<button class="btn" onclick="awardCoins()">Начислить</button><span id="coin-result"></span></div>';
        });
    }

    function awardCoins() {
        var userId = parseInt(document.getElementById('coin-user').value);
        var amount = parseInt(document.getElementById('coin-amount').value) || 0;
        var desc = document.getElementById('coin-desc').value.trim();
        api('/api/admin/coins/award', {method: 'POST', body: JSON.stringify({user_id: userId, amount: amount, description: desc})}).then(function(res) {
            document.getElementById('coin-result').className = res.ok ? 'ok' : 'error';
            document.getElementById('coin-result').textContent = res.ok ? ' ✓ Начислено' : (' ' + (res.j.error || 'Ошибка'));
        });
    }

    function loadErrors() {
        api('/api/admin/errors').then(function(res) {
            if (!res.ok) { document.getElementById('panel-errors').innerHTML = '<div class="error">' + esc(res.j.error) + '</div>'; return; }
            var d = res.j;
            var h = '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px"><h3 style="color:var(--gh-accent)">Журнал ошибок (' + d.count + ')</h3><button class="btn btn-danger btn-small" onclick="clearErrors()">Очистить</button></div>';
            if (!d.errors.length) h += '<div class="empty">Ошибок нет</div>';
            d.errors.forEach(function(e) {
                h += '<div class="card"><div class="log-ts">' + esc(e.timestamp) + '</div><div>' + esc(e.module) + ' / ' + esc(e.error_type) + '</div><div>' + esc(e.message) + '</div></div>';
            });
            document.getElementById('panel-errors').innerHTML = h;
        });
    }

    function clearErrors() {
        api('/api/admin/errors/clear', {method: 'POST'}).then(function(res) {
            if (res.ok) { toast('Ошибки очищены'); loadErrors(); }
            else toast(res.j.error || 'Ошибка', true);
        });
    }

    function loadFeedback(kind) {
        var url = '/api/admin/feedback';
        if (kind === 'bug' || kind === 'suggestion') url += '?category=' + kind;
        else if (kind === 'open') url += '?status=open';
        api(url).then(function(res) {
            if (!res.ok) { document.getElementById('panel-feedback').innerHTML = '<div class="error">' + esc(res.j.error) + '</div>'; return; }
            var list = res.j.items || [];
            var h = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">' +
                '<button class="btn btn-secondary btn-small" onclick="loadFeedback()">Все</button>' +
                '<button class="btn btn-secondary btn-small" onclick="loadFeedback(\\\'bug\\\')">🐛 Баги</button>' +
                '<button class="btn btn-secondary btn-small" onclick="loadFeedback(\\\'suggestion\\\')">💡 Предложения</button>' +
                '<button class="btn btn-secondary btn-small" onclick="loadFeedback(\\\'open\\\')">Открытые</button></div>';
            if (!list.length) h += '<div class="empty">Пусто</div>';
            list.forEach(function(f) {
                var tag = f.category === 'bug' ? '<span class="badge badge-danger">🐛 Баг</span>' : '<span class="badge badge-admin">💡 Предложение</span>';
                var status = f.status === 'open' ? ' · <span style="color:var(--gh-warn)">открыт</span>' : '';
                h += '<div class="card"><div>' + tag + status + ' · ' + esc(f.author_name || f.login || 'аноним') + (f.module ? ' · ' + esc(f.module) : '') + '</div>' +
                    '<div style="margin-top:6px">' + esc(f.message) + '</div>' +
                    '<button class="btn btn-danger btn-small" style="margin-top:10px" onclick="deleteFeedback(' + f.id + ')">Удалить</button></div>';
            });
            document.getElementById('panel-feedback').innerHTML = h;
        });
    }

    function deleteFeedback(id) {
        api('/api/admin/feedback/' + id, {method: 'DELETE'}).then(function(res) {
            if (res.ok) { toast('Удалено'); loadFeedback(); }
            else toast(res.j.error || 'Ошибка', true);
        });
    }

    (function init() {
        if (!TOKEN) {
            document.getElementById('gate').style.display = 'block';
            document.getElementById('gate-msg').textContent = 'Вы не вошли в аккаунт';
            return;
        }
        api('/api/auth/me').then(function(res) {
            if (!res.ok || !res.j.is_admin) {
                document.getElementById('gate').style.display = 'block';
                document.getElementById('gate-msg').textContent = 'Доступ только для админов';
                return;
            }
            document.getElementById('gate').style.display = 'none';
            document.getElementById('app').style.display = 'block';
            loadStats();
        });
    })();
</script>
</body>
</html>"""
    return html


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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 640px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .score { text-align: center; color: var(--bb-muted); font-size: 14px; margin-bottom: 16px; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 28px; margin-bottom: 16px; }
        .question { font-size: 18px; line-height: 1.6; margin-bottom: 24px; }
        .options { display: flex; flex-direction: column; gap: 10px; }
        .opt-btn { display: block; width: 100%; padding: 14px 18px; background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 12px; font-size: 15px; cursor: pointer; text-align: left; transition: all 0.15s; }
        .opt-btn:hover:not(:disabled) { background: var(--bb-link); }
        .opt-btn:disabled { cursor: default; opacity: 0.8; }
        .opt-btn.correct { background: var(--bb-green); border-color: var(--bb-green2); }
        .opt-btn.wrong { background: var(--bb-red); border-color: var(--bb-red); }
        .explanation { background: var(--bb-primary); border-radius: 12px; padding: 16px; margin-top: 16px; font-size: 14px; line-height: 1.5; color: var(--bb-muted); display: none; }
        .next-btn { display: none; width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-top: 16px; }
        .next-btn:hover { background: var(--bb-accent2); }
        .status { text-align: center; color: var(--bb-muted); margin-top: 24px; font-size: 13px; }
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
            var score = 0, total = 0, currentSession = null;
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
                        currentSession = q.session_id || q.id;
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
                xhr.onerror = function() { showRetryQuestion(); };
                xhr.ontimeout = function() { showRetryQuestion(); };
                xhr.timeout = 20000;
                xhr.send(JSON.stringify({}));
            }
            function showRetryQuestion() {
                var q = document.getElementById('question');
                q.textContent = '\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0442\u0438.';
                var retry = document.getElementById('next-btn');
                retry.textContent = '\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c';
                retry.style.display = 'block';
                retry.onclick = loadQuestion;
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
                        hubTrack('trivia', 1);
                        var expl = document.getElementById('explanation');
                        expl.textContent = r.explanation;
                        expl.style.display = 'block';
                        var nextBtn = document.getElementById('next-btn');
                        nextBtn.textContent = '\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0432\u043e\u043f\u0440\u043e\u0441';
                        nextBtn.onclick = loadQuestion;
                        nextBtn.style.display = 'block';
                    } catch(e) { btns.forEach(function(b) { b.disabled = false; }); }
                };
                xhr.onerror = function() { btns.forEach(function(b) { b.disabled = false; }); document.getElementById('explanation').textContent = '\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0442\u0438. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.'; document.getElementById('explanation').style.display = 'block'; };
                xhr.ontimeout = function() { btns.forEach(function(b) { b.disabled = false; }); document.getElementById('explanation').textContent = '\u0421\u0435\u0440\u0432\u0435\u0440 \u043d\u0435 \u043e\u0442\u0432\u0435\u0442\u0438\u043b. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437.'; document.getElementById('explanation').style.display = 'block'; };
                xhr.timeout = 20000;
                xhr.send(JSON.stringify({session_id: currentSession, answer_index: idx}));
            }
            function showRegNotice() {
                try {
                    if (sessionStorage.getItem('reg_notice_shown')) return;
                    sessionStorage.setItem('reg_notice_shown', '1');
                    var re = document.getElementById('hub-reg-notice');
                    if (!re) {
                        re = document.createElement('div');
                        re.id = 'hub-reg-notice';
                        re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                        re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                        document.body.appendChild(re);
                    }
                    clearTimeout(re._t);
                    re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
                } catch(e) {}
            }
            function hubTrack(module, actions) {
                actions = actions || 1;
                var token = localStorage.getItem('web_token') || '';
                var uid = localStorage.getItem('web_user_id') || '';
                try {
                    if (token && uid.indexOf('u') === 0) {
                        fetch('/api/achievements/activity', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                            body: JSON.stringify({ module: module, actions: actions })
                        }).then(function(r) { return r.json(); }).then(function(d) {
                            if (d && d.unlocked_detail && d.unlocked_detail.length) {
                                var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                                var pe = document.getElementById('hub-popup');
                                if (!pe) {
                                    pe = document.createElement('div');
                                    pe.id = 'hub-popup';
                                    pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                    document.body.appendChild(pe);
                                }
                                pe.innerHTML = '🏆 ' + names.join('<br>');
                                pe.style.display = 'block';
                                clearTimeout(pe._t);
                                pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                            }
                        }).catch(function() {});
                    } else {
                        showRegNotice();
                        var today = new Date();
                        var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                        var acts = {};
                        try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                        acts[dayStr] = (acts[dayStr] || 0) + 1;
                        localStorage.setItem('hub_activity', JSON.stringify(acts));
                    }
                } catch(e) {}
            }
            document.getElementById('next-btn').addEventListener('click', loadQuestion);
            loadQuestion();
        })();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/emperors")
def emperors_page():
    history_data = json.dumps(
        {
            "emperors": [
                {"id": e.id, "name": e.name, "reign": e.reign, "emoji": e.emoji}
                for e in _EMPERORS
            ],
            "rulers": [
                {"id": r.id, "name": r.name, "reign": r.reign, "emoji": r.emoji}
                for r in _RULERS
            ],
            "events": [
                {"year": ev.year, "title": ev.title, "emperor": ev.emperor_id, "note": ev.note, "importance": ev.importance}
                for ev in _HISTORY_EVENTS
            ],
            "persons": [
                {"name": p.name, "emperor": p.emperor_id, "description": p.description, "importance": p.importance}
                for p in _HISTORY_PERSONS
            ],
        },
        ensure_ascii=False,
    )
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Императоры России — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 720px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--bb-accent); }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .tab-btn { flex: 1; padding: 12px; background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .tab-btn:hover { background: var(--bb-link); }
        .tab-btn.active { background: var(--bb-accent); border-color: var(--bb-accent); color: white; }
        .panel { display: none; }
        .panel.active { display: block; }
        .score { text-align: center; color: var(--bb-muted); font-size: 14px; margin-bottom: 16px; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
        .emperor-card { border-left: 5px solid; padding: 18px 20px; }
        .emperor-card h2 { font-size: 18px; margin-bottom: 2px; }
        .emperor-card .reign { font-size: 13px; color: var(--bb-muted); margin-bottom: 12px; }
        .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
        .chip { display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 13px; background: var(--bb-primary); border: 1px solid var(--bb-link); cursor: default; line-height: 1.4; }
        .chip small { color: var(--bb-muted); }
        .stars { color: var(--bb-warn); letter-spacing: 1px; }
        .chip-title { font-size: 12px; color: var(--bb-muted); text-transform: uppercase; letter-spacing: 0.5px; margin: 12px 0 6px; }
        .chip.clickable { cursor: pointer; transition: all 0.15s; }
        .chip.clickable:hover { background: var(--bb-link); border-color: var(--bb-link); }
        .chip.locked { opacity: 0.5; }
        .timeline { background: var(--bb-bg); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 18px 20px; margin-bottom: 16px; }
        .timeline-title { font-size: 14px; color: var(--bb-accent); font-weight: 600; margin-bottom: 14px; }
        .era { margin-bottom: 14px; }
        .era:last-child { margin-bottom: 0; }
        .era-name { font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--bb-muted); margin-bottom: 6px; }
        .era-row { display: flex; flex-wrap: wrap; gap: 6px; }
        .era-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 8px; font-size: 12px; background: var(--bb-primary); border: 1px solid var(--bb-link); line-height: 1.3; cursor: pointer; transition: all 0.15s; }
        .era-chip:hover { background: var(--bb-link); }
        .era-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
        .era-years { color: var(--bb-muted); font-size: 11px; }
        .opt-btn.animate-correct { animation: pulse-green 0.5s; }
        .opt-btn.animate-wrong { animation: shake 0.4s; }
        .question.animate-correct { animation: pulse-green 0.5s; }
        .question.animate-wrong { animation: shake 0.4s; }
        @keyframes pulse-green { 0% { transform: scale(1); } 50% { transform: scale(1.04); } 100% { transform: scale(1); } }
        @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); z-index: 2000; display: none; align-items: center; justify-content: center; padding: 20px; }
        .modal-overlay.show { display: flex; }
        .modal { background: var(--bb-panel); border: 1px solid var(--bb-link); border-radius: 16px; max-width: 560px; width: 100%; padding: 22px; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5); }
        .modal .m-head { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
        .modal .m-tag { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--bb-muted); }
        .modal .m-title { font-size: 18px; font-weight: 600; line-height: 1.4; margin-top: 2px; }
        .modal .m-emperor { font-size: 13px; margin-top: 2px; }
        .modal .m-close { margin-left: auto; background: none; border: 1px solid #333; color: var(--bb-muted); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; font-size: 14px; flex-shrink: 0; }
        .modal .m-close:hover { border-color: var(--bb-accent); color: var(--bb-accent); }
        .modal .m-body { font-size: 14px; line-height: 1.6; color: #c8d2e0; }
        .question { font-size: 18px; line-height: 1.6; margin-bottom: 20px; min-height: 24px; }
        .diff-badge { display: flex; align-items: center; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 14px; font-size: 13px; }
        .diff-stars { color: var(--bb-gold); letter-spacing: 1px; font-size: 15px; }
        .diff-pts { background: var(--bb-primary); border: 1px solid var(--bb-link); color: var(--bb-text); border-radius: 8px; padding: 2px 8px; font-weight: 600; }
        .diff-hint { color: var(--bb-muted); }
        .options { display: flex; flex-direction: column; gap: 10px; }
        .opt-btn { display: block; width: 100%; padding: 14px 18px; background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 12px; font-size: 15px; cursor: pointer; text-align: left; transition: all 0.15s; }
        .opt-btn:hover:not(:disabled) { background: var(--bb-link); }
        .opt-btn:disabled { cursor: default; opacity: 0.85; }
        .opt-btn.correct { background: var(--bb-green); border-color: var(--bb-green2); }
        .opt-btn.wrong { background: var(--bb-red); border-color: var(--bb-red); }
        .info { background: var(--bb-primary); border-radius: 12px; padding: 16px; margin-top: 16px; font-size: 14px; line-height: 1.5; color: var(--bb-muted); display: none; }
        .info .info-label { color: var(--bb-accent); font-weight: 600; }
        .next-btn { display: none; width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-top: 16px; font-family: inherit; }
        .next-btn:hover { background: var(--bb-accent2); }
        .mode-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; justify-content: center; flex-wrap: wrap; }
        .mode-row label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: var(--bb-text); cursor: pointer; }
        .algo-select { background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 8px; padding: 6px 10px; font-size: 13px; font-family: inherit; cursor: pointer; }
        .status { text-align: center; color: var(--bb-muted); margin-top: 24px; font-size: 13px; }
        .reset-btn { background: none; border: 1px solid var(--bb-link); color: var(--bb-muted); border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 12px; font-family: inherit; }
        .reset-btn:hover { border-color: var(--bb-accent); color: var(--bb-accent); }
        .progress-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
        .progress-bar { flex: 1; height: 8px; background: var(--bb-primary); border-radius: 6px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--bb-accent); width: 0%; transition: width 0.25s; }
        .progress-label { font-size: 12px; color: var(--bb-muted); white-space: nowrap; }
        .hint-box { background: var(--bb-primary); border-radius: 10px; padding: 12px; margin-bottom: 14px; font-size: 14px; color: var(--bb-muted); line-height: 1.5; display: none; }
        .hint-btn { display: block; width: 100%; padding: 10px; background: none; border: 1px dashed var(--bb-link); color: var(--bb-muted); border-radius: 10px; font-size: 13px; cursor: pointer; margin-top: 10px; font-family: inherit; }
        .hint-btn:hover { border-color: var(--bb-warn); color: var(--bb-warn); }
        .stats-card { font-size: 13px; color: var(--bb-muted); }
        .stats-card .stat-line { margin: 4px 0; }
        .match-items { margin-bottom: 16px; }
        .match-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: 10px; }
        .match-col { background: var(--bb-primary); border: 2px solid var(--bb-link); border-radius: 12px; padding: 10px; min-height: 90px; cursor: pointer; }
        .match-col:hover { border-color: var(--bb-link); }
        .match-col-head { font-weight: 600; font-size: 13px; margin-bottom: 8px; }
        .match-chip { cursor: pointer; user-select: none; }
        .match-chip.sel { outline: 2px solid var(--bb-accent); }
        .match-chip.placed { cursor: default; display: block; margin: 4px 0; }
        .match-chip.ok { background: var(--bb-green); border-color: var(--bb-green2); }
        .match-chip.bad { background: var(--bb-red); border-color: var(--bb-red); }
        .match-chip .x { margin-left: 6px; color: var(--bb-muted); border: none; background: none; cursor: pointer; font-size: 12px; }
        .debug-btn { background: none; border: 1px solid #333; color: #555; border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 12px; font-family: inherit; }
        .debug-btn:hover { border-color: var(--bb-warn); color: var(--bb-warn); }
        .debug-panel { position: fixed; top: 12px; right: 12px; max-height: 70vh; overflow: auto; width: 340px; background: rgba(13, 18, 34, 0.85); border: 1px solid var(--bb-link); border-radius: 10px; padding: 12px; font-size: 11px; line-height: 1.5; color: #9fb3c8; z-index: 1000; display: none; }
        .debug-panel .d-title { color: var(--bb-accent); font-weight: 600; margin-bottom: 6px; }
        .debug-panel .d-row { padding: 2px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        .debug-panel .d-row b { color: var(--bb-text); }
        .debug-panel .d-due { color: var(--bb-warn); }
        @media (max-width: 600px) { .card { padding: 16px; } .question { font-size: 16px; } .chip { font-size: 12px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👑 Императоры России</h1>
            <a href="/">← Назад</a>
        </div>
        <div class="tabs">
            <button class="tab-btn active" id="tab-study" onclick="app.showTab('study')">📚 Изучить</button>
            <button class="tab-btn" id="tab-quiz" onclick="app.showTab('quiz')">🧠 Тренажёр</button>
            <button class="tab-btn" id="tab-match" onclick="app.showTab('match')">🎯 Сопоставление</button>
            <button class="tab-btn" id="tab-chrono" onclick="app.showTab('chrono')">📜 Хронология</button>
        </div>
        <div class="panel active" id="panel-study">
            <div class="mode-row">
                <label>Правители:
                    <select class="algo-select scope-sel" id="scope-select-study" onchange="app.toggleScope(this)">
                        <option value="emperors">5 императоров</option>
                        <option value="all">Все правители (Рюрик–Путин)</option>
                    </select>
                </label>
            </div>
            <div id="study-body"></div>
        </div>
        <div class="panel" id="panel-quiz">
            <div class="progress-row">
                <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
                <span class="progress-label" id="progress-label"></span>
            </div>
            <div class="score" id="quiz-score"></div>
            <div class="mode-row">
                <label>Алгоритм:
                    <select class="algo-select" id="algo-select" onchange="app.toggleAlgo()">
                        <option value="deck">Классика (колода)</option>
                        <option value="flash">Флешки (интервалы)</option>
                        <option value="counter">Счётчик (вероятности)</option>
                    </select>
                </label>
                <label>Правители:
                    <select class="algo-select scope-sel" id="scope-select" onchange="app.toggleScope(this)">
                        <option value="emperors">5 императоров</option>
                        <option value="all">Все правители (Рюрик–Путин)</option>
                    </select>
                </label>
                <label>Варианты:
                    <select class="algo-select" id="opt-count" onchange="app.toggleOptCount()">
                        <option value="5">5 вариантов</option>
                        <option value="all">Все (хронологически)</option>
                    </select>
                </label>
                <label>Вопрос:
                    <select class="algo-select" id="qdir-select" onchange="app.toggleQDir()">
                        <option value="toRuler">Событие → Правитель</option>
                        <option value="fromRuler">Правитель → Событие</option>
                    </select>
                </label>
                <label><input type="checkbox" id="mode-errors" onchange="app.toggleMode()"> Только ошибки</label>
                <button class="reset-btn" onclick="app.resetScore()">Сбросить счёт</button>
                <button class="debug-btn" onclick="app.toggleDebug()">🔧 Дебаг</button>
            </div>
            <div class="debug-panel" id="debug-panel">
                <div class="d-title">Дебаг · данные карточек</div>
                <div id="debug-list"></div>
            </div>
            <div class="card">
                <div class="diff-badge" id="diff-badge"></div>
                <div class="question" id="question">Загрузка...</div>
                <div class="hint-box" id="hint-box"></div>
                <div class="options" id="options"></div>
                <div class="info" id="info"></div>
                <button class="next-btn" id="next-btn">Следующий →</button>
                <button class="hint-btn" id="hint-btn" onclick="app.showHint()">💡 Подсказка</button>
            </div>
            <div class="card stats-card" id="stats-card"></div>
        </div>
        <div class="panel" id="panel-match">
            <div class="mode-row">
                <label>Правители:
                    <select class="algo-select scope-sel" id="scope-select-match" onchange="app.toggleScope(this)">
                        <option value="emperors">5 императоров</option>
                        <option value="all">Все правители (Рюрик–Путин)</option>
                    </select>
                </label>
                <button class="reset-btn" onclick="app.startMatch()">🔄 Новый раунд</button>
                <button class="reset-btn" onclick="app.checkMatch()">✅ Проверить</button>
                <span class="progress-label" id="match-count"></span>
            </div>
            <div class="match-items" id="match-items"></div>
            <div class="match-grid" id="match-columns"></div>
            <div class="info" id="match-info"></div>
        </div>
        <div class="panel" id="panel-chrono">
            <div class="card">
                <div class="question" id="chrono-question">Расставь правителей в хронологическом порядке — нажимай на самого раннего из оставшихся.</div>
                <div class="info" id="chrono-info" style="display:none"></div>
                <div class="options" id="chrono-options"></div>
            </div>
            <div class="card">
                <div class="chip-title">Правильный порядок</div>
                <div class="chip-row" id="chrono-answer"></div>
                <div class="chip-title">Осталось</div>
                <div class="chip-row" id="chrono-left"></div>
            </div>
            <div class="card">
                <div class="chip-title">Твоя последовательность</div>
                <div class="chip-row" id="chrono-placed"></div>
            </div>
            <div class="mode-row">
                <label>Правители:
                    <select class="algo-select scope-sel" id="scope-select-chrono" onchange="app.toggleScope(this)">
                        <option value="emperors">5 императоров</option>
                        <option value="all">Все правители (Рюрик–Путин)</option>
                    </select>
                </label>
                <button class="reset-btn" onclick="app.startChrono()">🔄 Новый раунд</button>
                <button class="reset-btn" onclick="app.checkChrono()">✅ Проверить</button>
                <span class="progress-label" id="chrono-count"></span>
            </div>
        </div>
        <div class="status">модуль подготовки к игре «Имена и события»</div>
    </div>
    <div class="modal-overlay" id="info-modal" onclick="if (event.target === this) app.closeInfo()">
        <div class="modal">
            <div class="m-head">
                <div>
                    <div class="m-tag" id="info-tag"></div>
                    <div class="m-title" id="info-title"></div>
                    <div class="m-emperor" id="info-emperor"></div>
                </div>
                <button class="m-close" onclick="app.closeInfo()">✕</button>
            </div>
            <div class="m-body" id="info-body"></div>
        </div>
    </div>
    <script>
        (function() {
            var DATA = __DATA__;
            var PALETTE = [
                'var(--bb-accent)', 'var(--bb-warn)', 'var(--gh-green)', '#42a5f5', '#ab47bc',
                '#26a69a', '#ff7043', '#8d6e63', '#ec407a', '#7e57c2',
                '#5c6bc0', '#66bb6a', '#ffa726', '#ef5350', '#29b6f6',
                '#9ccc65', '#f06292', '#ba68c8', '#ff8a65', '#4dd0e1',
                '#a1887f', '#d4e157', '#7986cb', '#ffb74d', '#90a4ae',
                '#e57373', '#64b5f6', '#f48fb1', '#81c784', '#ce93d8',
                '#4fc3f7', '#ffd54f', '#b0bec5'
            ];
            var COLORS = {};
            DATA.rulers.forEach(function(r, i) { COLORS[r.id] = PALETTE[i % PALETTE.length]; });
            var emName = {};
            DATA.rulers.forEach(function(e) { emName[e.id] = e.name; });
            var allItems = [];
            DATA.events.forEach(function(ev) {
                allItems.push({type: 'event', text: ev.title, emperor: ev.emperor, info: ev.note, label: 'Событие', importance: ev.importance || 3});
            });
            DATA.persons.forEach(function(p) {
                allItems.push({type: 'person', text: p.name, emperor: p.emperor, info: p.description, label: 'Личность', importance: p.importance || 3});
            });
            var scope = localStorage.getItem('emperors_scope') || 'emperors';
            document.querySelectorAll('.scope-sel').forEach(function(s) { s.value = scope; });
            var optCount = localStorage.getItem('emperors_optcount') || '5';
            document.getElementById('opt-count').value = optCount;
            var qdir = localStorage.getItem('emperors_qdir') || 'toRuler';
            document.getElementById('qdir-select').value = qdir;
            function activeRulerIds() {
                var ids = {};
                (scope === 'all' ? DATA.rulers : DATA.emperors).forEach(function(r) { ids[r.id] = true; });
                return ids;
            }
            function inScope(it) { return activeRulerIds()[it.emperor] === true; }
            function itemsInScope() { return allItems.filter(inScope); }
            var quizScore = 0, quizTotal = 0;
            (function() {
                var s = localStorage.getItem('emperors_score');
                if (s) { var p = s.split('/'); quizScore = parseInt(p[0]) || 0; quizTotal = parseInt(p[1]) || 0; }
            })();
            var wrongItems = [];
            (function() {
                try { wrongItems = JSON.parse(localStorage.getItem('emperors_wrong') || '[]'); } catch(e) { wrongItems = []; }
            })();
            var onlyErrors = false;
            var currentItem = null;
            var pending = [];
            var algo = localStorage.getItem('emperors_algo') || 'flash';
            document.getElementById('algo-select').value = algo;
            var uid = localStorage.getItem('web_user_id') || ('web_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10));
            localStorage.setItem('web_user_id', uid);
            var authToken = localStorage.getItem('web_token') || '';

            function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function(c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
            function shuffleArray(a) { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
            function flashKey(it) { return it.type + '::' + it.text; }
            var flash = {};
            (function() {
                try { flash = JSON.parse(localStorage.getItem('emperors_flash') || '{}'); } catch(e) { flash = {}; }
            })();
            function saveFlashLocal() { localStorage.setItem('emperors_flash', JSON.stringify(flash)); }
            var saveTimer = null;
            function pushFlash() {
                saveFlashLocal();
                if (!authToken) return;
                if (saveTimer) clearTimeout(saveTimer);
                saveTimer = setTimeout(function() {
                    fetch('/api/emperors/progress', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': authToken },
                        body: JSON.stringify({ cards: flash })
                    }).catch(function() {});
                }, 600);
            }
            function recFor(it) {
                var key = flashKey(it);
                return flash[key] || { reps: 0, interval: 0, ease: 2.5, correct: 0, wrong: 0, counter: 0 };
            }
            function recordAnswer(it, correct) {
                var key = flashKey(it);
                var rec = recFor(it);
                rec.counter = (rec.counter || 0) + (correct ? 1 : -1);
                if (correct) {
                    rec.reps = (rec.reps || 0) + 1;
                    rec.correct = (rec.correct || 0) + 1;
                    if (rec.reps === 1) rec.interval = 1;
                    else if (rec.reps === 2) rec.interval = 3;
                    else if (rec.reps === 3) rec.interval = 7;
                    else rec.interval = Math.round((rec.interval || 7) * rec.ease);
                    rec.due = Date.now() + rec.interval * 86400000;
                } else {
                    rec.reps = 0; rec.interval = 0; rec.due = Date.now() + 60000;
                    rec.wrong = (rec.wrong || 0) + 1;
                }
                flash[key] = rec; pushFlash();
            }
            function flashDueCount() {
                var now = Date.now(); var n = 0;
                itemsInScope().forEach(function(it) { var rec = flash[flashKey(it)]; if (!rec || rec.due <= now) n++; });
                return n;
            }
            function pickFlash() {
                var now = Date.now(); var candidates = [];
                itemsInScope().forEach(function(it) {
                    var rec = flash[flashKey(it)];
                    var prio;
                    if (rec && rec.due <= now) prio = 0;
                    else if (!rec) prio = 1;
                    else prio = 2;
                    candidates.push({ it: it, due: rec ? rec.due : 0, prio: prio, importance: it.importance || 3 });
                });
                if (!candidates.length) return null;
                candidates.sort(function(a, b) {
                    if (a.prio !== b.prio) return a.prio - b.prio;
                    if (a.prio === 1 && a.importance !== b.importance) return b.importance - a.importance;
                    return a.due - b.due;
                });
                var prevType = currentItem ? currentItem.type : null;
                var prevEmperor = currentItem ? currentItem.emperor : null;
                for (var i = 0; i < candidates.length; i++) {
                    if (candidates[i].it.type !== prevType) return candidates[i].it;
                }
                for (var j = 0; j < candidates.length; j++) {
                    if (candidates[j].it.emperor !== prevEmperor) return candidates[j].it;
                }
                return candidates[0].it;
            }
            function pickCounter() {
                var items = itemsInScope();
                var weights = items.map(function(it) {
                    var rec = recFor(it);
                    var c = rec.counter || 0;
                    var w = (c <= 0) ? (1 - c) : Math.max(1, 10 - c);
                    return w * (it.importance || 3);
                });
                var total = 0;
                weights.forEach(function(w) { total += w; });
                var r = Math.random() * total;
                for (var i = 0; i < items.length; i++) {
                    r -= weights[i];
                    if (r <= 0) return items[i];
                }
                return items[items.length - 1];
            }
            if (authToken) {
                fetch('/api/emperors/progress', { headers: { 'X-Auth-Token': authToken } })
                    .then(function(r) { return r.json(); })
                    .then(function(d) {
                        if (d && d.cards) {
                            var merged = false;
                            for (var k in d.cards) {
                                if (!flash[k] || d.cards[k].due > (flash[k].due || 0)) { flash[k] = d.cards[k]; merged = true; }
                            }
                            if (merged) { saveFlashLocal(); updateScore(); }
                        }
                    }).catch(function() {});
            }
            var deck = [];
            function buildDeck() {
                deck = shuffleArray(itemsInScope());
                if (wrongItems.length) {
                    deck = shuffleArray(wrongItems.filter(inScope).slice()).concat(deck);
                }
            }
            function saveScore() { localStorage.setItem('emperors_score', quizScore + '/' + quizTotal); }
            function saveWrong() { localStorage.setItem('emperors_wrong', JSON.stringify(wrongItems)); }
            function updateProgressBar() {
                var total = itemsInScope().length;
                var mastered = 0;
                Object.keys(flash).forEach(function(k) { var r = flash[k]; if (r && (r.reps || 0) >= 3) mastered++; });
                var el = document.getElementById('progress-fill');
                var lab = document.getElementById('progress-label');
                if (el) { el.style.width = (total ? (mastered / total * 100) : 0) + '%'; }
                if (lab) { lab.textContent = 'освоено ' + mastered + '/' + total; }
            }
            function renderStatsOld() {
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                var byEmperor = {};
                rulers.forEach(function(e) { byEmperor[e.id] = { wrong: 0, correct: 0 }; });
                Object.keys(flash).forEach(function(k) {
                    var r = flash[k];
                    if (!r) return;
                    var parts = k.split('::');
                    var text = parts.slice(1).join('::');
                    for (var i = 0; i < allItems.length; i++) {
                        if (allItems[i].type === parts[0] && allItems[i].text === text && inScope(allItems[i])) {
                            var em = allItems[i].emperor;
                            if (byEmperor[em]) { byEmperor[em].wrong += r.wrong || 0; byEmperor[em].correct += r.correct || 0; }
                            break;
                        }
                    }
                });
                var totalItems = itemsInScope().length;
                var html = '<div class="chip-title">Статистика</div>';
                html += '<div class="stat-line">Освоено карточек: <b>' + Object.keys(flash).filter(function(k){return (flash[k]||{}).reps>=3;}).length + ' / ' + totalItems + '</b></div>';
                html += '<div class="stat-line">В очереди к повторению: <b>' + flashDueCount() + '</b></div>';
                html += '<div class="chip-title">Топ ошибок по правителям</div>';
                var arr = rulers.map(function(e) { return { id: e.id, wrong: byEmperor[e.id].wrong }; });
                arr.sort(function(a, b) { return b.wrong - a.wrong; });
                arr.forEach(function(a) {
                    html += '<div class="stat-line"><span style="color:' + COLORS[a.id] + '">●</span> ' + esc(emName[a.id]) + ': <b>' + a.wrong + '</b> ошибок</div>';
                });
                document.getElementById('stats-card').innerHTML = html;
            }
function renderDebug() {
                var listEl = document.getElementById('debug-list');
                if (!listEl || document.getElementById('debug-panel').style.display !== 'block') return;
                var rows = [];
                itemsInScope().forEach(function(it) {
                    var rec = flash[flashKey(it)] || {};
                    var due = rec.due || 0;
                    rows.push({
                        key: it.type.charAt(0) + '·' + it.text,
                        emperor: it.emperor,
                        reps: rec.reps || 0,
                        interval: rec.interval || 0,
                        ease: rec.ease != null ? rec.ease.toFixed(1) : '2.5',
                        due: due ? new Date(due).toISOString().slice(0, 16) : '—',
                        correct: rec.correct || 0,
                        wrong: rec.wrong || 0,
                        counter: rec.counter || 0,
                        overdue: due ? due <= Date.now() : true
                    });
                });
                rows.sort(function(a, b) { return (a.overdue ? 0 : 1) - (b.overdue ? 0 : 1); });
                var html = '';
                rows.forEach(function(r) {
                    html += '<div class="d-row"><b>' + esc(r.key) + '</b>' +
                        ' · ' + emName[r.emperor].split(' (')[0] +
                        ' · счётчик=' + r.counter +
                        ' · reps=' + r.reps + ' int=' + r.interval + ' ease=' + r.ease +
                        ' ✓' + r.correct + ' ✗' + r.wrong +
                        ' · <span class="d-due">' + (r.overdue ? '⏰ ' : '') + r.due + '</span></div>';
                });
                listEl.innerHTML = html;
            }
function diffInfo() {
                var pts, level;
                if (scope === 'all' && optCount === 'all') { level = 3; pts = '+2/−1'; }
                else if (scope === 'all' && optCount === '5') { level = 2; pts = '+1/−2'; }
                else { level = 1; pts = '+1/−1'; }
                var stars = '★'.repeat(level) + '☆'.repeat(Math.max(0, 3 - level));
                var hint = [];
                hint.push(scope === 'all' ? 'все правители' : '5 императоров');
                hint.push(optCount === 'all' ? 'все варианты' : '5 вариантов');
                if (qdir === 'fromRuler') hint.push('обратный вопрос');
                return { level: level, stars: stars, label: hint.join(' · '), pts: pts, hint: hint.join(' · ') };
            }
            function updateDiffBadge() {
                var d = diffInfo();
                var el = document.getElementById('diff-badge');
                if (el) el.innerHTML = '<span class="diff-stars">' + d.stars + '</span> <span class="diff-pts">' + d.pts + '</span> <span class="diff-hint">' + d.hint + '</span>';
            }
            function updateScore() {
                var s = 'Счёт: ' + quizScore + ' / ' + quizTotal;
                var lvl = levelInfo();
                s += ' · ' + lvl.name;
                s += ' · ' + diffInfo().pts;
                if (algo === 'flash') s += ' · к изучению: ' + flashDueCount();
                if (algo === 'counter') {
                    var weak = 0;
                    Object.keys(flash).forEach(function(k) { var r = flash[k]; if (r && (r.counter || 0) < 0) weak++; });
                    s += ' · слабых: ' + weak;
                }
                if (onlyErrors) s += ' · режим: только ошибки (' + wrongItems.length + ')';
                var streak = getStreak();
                if (streak.days > 0) s += ' · серия: ' + streak.days + ' дн.';
                document.getElementById('quiz-score').textContent = s;
                updateProgressBar();
                renderStats();
                renderDebug();
            }

            function levelInfo() {
                var thresholds = [['🏅 Новичок', 0], ['🥉 Знаток', 20], ['🥈 Профи', 60], ['🥇 Мастер', 120]];
                for (var i = thresholds.length - 1; i >= 0; i--) {
                    if (quizScore >= thresholds[i][1]) return { name: thresholds[i][0], next: thresholds[i + 1] ? thresholds[i + 1][1] : null };
                }
                return { name: '🏅 Новичок', next: 20 };
            }

            var streakData = null;
            function hubStreakKey() {
                if (!localStorage.getItem('hub_streak') && localStorage.getItem('emperors_streak')) {
                    localStorage.setItem('hub_streak', localStorage.getItem('emperors_streak'));
                    localStorage.removeItem('emperors_streak');
                }
                return 'hub_streak';
            }
            function getStreak() {
                try { streakData = JSON.parse(localStorage.getItem(hubStreakKey()) || 'null'); } catch(e) { streakData = null; }
                if (!streakData || !streakData.day) return { days: 0 };
                var today = new Date();
                var d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
                var last = new Date(streakData.day + 'T00:00:00');
                var diffDays = Math.round((d - last) / 86400000);
                if (diffDays === 0) return { days: streakData.days, today: true };
                return { days: 0 };
            }
            function updateStreak(correct) {
                var today = new Date();
                var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                try { streakData = JSON.parse(localStorage.getItem(hubStreakKey()) || 'null'); } catch(e) { streakData = null; }
                var days = 1;
                if (streakData && streakData.day) {
                    var last = new Date(streakData.day + 'T00:00:00');
                    var d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
                    var diff = Math.round((d - last) / 86400000);
                    if (diff === 0) days = streakData.days;
                    else if (diff === 1) days = (streakData.days || 0) + 1;
                    else days = 1;
                }
                localStorage.setItem(hubStreakKey(), JSON.stringify({ day: dayStr, days: days }));
            }

            function showRegNotice() {
                try {
                    if (sessionStorage.getItem('reg_notice_shown')) return;
                    sessionStorage.setItem('reg_notice_shown', '1');
                    var re = document.getElementById('hub-reg-notice');
                    if (!re) {
                        re = document.createElement('div');
                        re.id = 'hub-reg-notice';
                        re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                        re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                        document.body.appendChild(re);
                    }
                    clearTimeout(re._t);
                    re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
                } catch(e) {}
            }
            function hubTrack(module, actions, events) {
                actions = actions || 1;
                events = events || [];
                var token = localStorage.getItem('web_token') || '';
                var uid = localStorage.getItem('web_user_id') || '';
                try {
                    if (token && uid.indexOf('u') === 0) {
                        fetch('/api/achievements/activity', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                            body: JSON.stringify({ module: module, actions: actions, events: events })
                        }).then(function(r) { return r.json(); }).then(function(d) {
                            if (d && d.unlocked_detail && d.unlocked_detail.length) {
                                var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                                var pe = document.getElementById('hub-popup');
                                if (!pe) {
                                    pe = document.createElement('div');
                                    pe.id = 'hub-popup';
                                    pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                    document.body.appendChild(pe);
                                }
                                pe.innerHTML = '🏆 ' + names.join('<br>');
                                pe.style.display = 'block';
                                clearTimeout(pe._t);
                                pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                            }
                        }).catch(function() {});
                    } else {
                        showRegNotice();
                        var today = new Date();
                        var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                        var acts = {};
                        try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                        acts[dayStr] = (acts[dayStr] || 0) + 1;
                        localStorage.setItem('hub_activity', JSON.stringify(acts));
                    }
                } catch(e) {}
            }

            function renderStats() {
                var el = document.getElementById('stats-card');
                var lvl = levelInfo();
                var html = '<div class="chip-title">Мой прогресс</div>';
                html += '<div>Уровень: <b>' + lvl.name + '</b>' + (lvl.next ? ' · до следующего: ' + (lvl.next - quizScore) + ' очк.' : ' · максимум') + '</div>';
                html += '<div>Правильных подряд: <b>' + (quizTotal ? currentStreakCorrect() : 0) + '</b></div>';
                var streak = getStreak();
                html += '<div>Серия дней: <b>' + (streak.days || 0) + '</b></div>';
                if (authToken) {
                    html += '<div class="chip-title">Достижения</div><div><a class="chip clickable" href="/achievements" style="text-decoration:none">🏆 Смотреть достижения →</a></div>';
                }
                html += '<div class="chip-title">Статистика</div>';
                var totalItems = itemsInScope().length;
                var mastered = itemsInScope().filter(function(it) { return (recFor(it).reps || 0) >= 3; }).length;
                html += '<div>Освоено карточек: <b>' + mastered + ' / ' + totalItems + '</b></div>';
                html += '<div>В очереди к повторению: <b>' + flashDueCount() + '</b></div>';
                var byEmperor = {};
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                rulers.forEach(function(e) { byEmperor[e.id] = { wrong: 0 }; });
                Object.keys(flash).forEach(function(k) {
                    var r = flash[k]; if (!r) return;
                    var parts = k.split('::'); var text = parts.slice(1).join('::');
                    for (var i = 0; i < allItems.length; i++) {
                        if (allItems[i].type === parts[0] && allItems[i].text === text && inScope(allItems[i])) {
                            var em = allItems[i].emperor;
                            if (byEmperor[em]) byEmperor[em].wrong += r.wrong || 0;
                            break;
                        }
                    }
                });
                var arr = rulers.map(function(e) { return { id: e.id, wrong: byEmperor[e.id].wrong }; });
                arr.sort(function(a, b) { return b.wrong - a.wrong; });
                var top = arr.slice(0, 3).filter(function(a) { return a.wrong > 0; });
                if (top.length) {
                    html += '<div class="chip-title">Топ ошибок</div>';
                    top.forEach(function(a) { html += '<div><span style="color:' + COLORS[a.id] + '">●</span> ' + esc(emName[a.id]) + ': <b>' + a.wrong + '</b></div>'; });
                }
                el.innerHTML = html;
            }
            var streakCorrect = 0;
            function currentStreakCorrect() { return streakCorrect; }

            function studyPanel() {
                var html = '';
                html += '<div class="timeline"><div class="timeline-title">🗓 Хронология по эпохам</div>';
                eraGroups().forEach(function(g) {
                    html += '<div class="era"><div class="era-name">' + esc(g.name) + ' <span class="era-years">' + esc(g.years) + '</span></div><div class="era-row">';
                    g.ids.forEach(function(id) {
                        var r = DATA.rulers.filter(function(x) { return x.id === id; })[0];
                        if (!r || (scope === 'emperors' && !DATA.emperors.some(function(x) { return x.id === id; }))) return;
                        html += '<span class="era-chip" style="border-color:' + COLORS[id] + '" onclick="app.showTab(\\'quiz\\')" title="' + esc(r.reign) + '"><span class="era-dot" style="background:' + COLORS[id] + '"></span>' + esc(r.name) + '</span>';
                    });
                    html += '</div></div>';
                });
                html += '</div>';
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                rulers.forEach(function(e) {
                    html += '<div class="card emperor-card" style="border-left-color:' + COLORS[e.id] + '">';
                    html += '<h2>' + e.emoji + ' ' + esc(e.name) + '</h2>';
                    html += '<div class="reign">Правил: ' + esc(e.reign) + '</div>';
                    var events = DATA.events.filter(function(ev) { return ev.emperor === e.id; });
                    var persons = DATA.persons.filter(function(p) { return p.emperor === e.id; });
                    if (events.length) {
                        html += '<div class="chip-title">События</div><div class="chip-row">';
                        events.forEach(function(ev) { html += '<span class="chip clickable" data-type="event" data-text="' + esc(ev.title) + '" onclick="app.showInfo(this)"><small>' + esc(ev.year) + '</small> ' + esc(ev.title) + starRow(ev.importance || 3) + '</span>'; });
                        html += '</div>';
                    }
                    if (persons.length) {
                        html += '<div class="chip-title">Личности</div><div class="chip-row">';
                        persons.forEach(function(p) { html += '<span class="chip clickable" data-type="person" data-text="' + esc(p.name) + '" onclick="app.showInfo(this)">' + esc(p.name) + starRow(p.importance || 3) + '</span>'; });
                        html += '</div>';
                    }
                    html += '</div>';
                });
                document.getElementById('study-body').innerHTML = html;
            }
            function starRow(imp) {
                var s = '';
                for (var i = 0; i < 5; i++) s += (i < imp) ? '★' : '☆';
                return ' <small class="stars">' + s + '</small>';
            }
            function eraGroups() {
                return [
                    { name: 'Древняя Русь', years: '862–1125', ids: ['rurik', 'oleg', 'igor', 'olga', 'svyatoslav', 'vladimir_i', 'yaroslav', 'monomakh'] },
                    { name: 'Удельная Русь', years: '1125–1389', ids: ['dolgoruky', 'nevsky', 'kalita', 'donskoy'] },
                    { name: 'Московское царство', years: '1389–1613', ids: ['ivan_iii', 'ivan_iv', 'godunov'] },
                    { name: 'Романовы', years: '1613–1721', ids: ['mikhail_romanov', 'alexey_mikhailovich'] },
                    { name: 'Российская империя', years: '1721–1917', ids: ['peter_i', 'elizaveta', 'catherine_ii', 'paul_i', 'alexander_i', 'nicholas_i', 'alexander_ii', 'alexander_iii', 'nicholas_ii'] },
                    { name: 'СССР', years: '1917–1991', ids: ['lenin', 'stalin', 'khrushchev', 'brezhnev', 'gorbachev'] },
                    { name: 'Россия', years: '1991–…', ids: ['yeltsin', 'putin'] }
                ];
            }

            function pickItem() {
                if (onlyErrors && wrongItems.length) {
                    return wrongItems[Math.floor(Math.random() * wrongItems.length)];
                }
                if (algo === 'flash') return pickFlash();
                if (algo === 'counter') return pickCounter();
                if (!deck.length) buildDeck();
                return deck.pop();
            }

            function loadQuestion() {
                document.getElementById('info').style.display = 'none';
                document.getElementById('hint-box').style.display = 'none';
                document.getElementById('hint-btn').style.display = 'block';
                document.getElementById('next-btn').style.display = 'none';
                updateDiffBadge();
                currentItem = pickItem();
                if (!currentItem) {
                    document.getElementById('question').textContent = 'Все карточки изучены на сегодня! 🎉 Переключитесь на «Классика» или нажмите «Сбросить счёт».';
                    document.getElementById('options').innerHTML = '';
                    updateScore();
                    return;
                }
                var opts = document.getElementById('options');
                opts.innerHTML = '';
                if (qdir === 'fromRuler') {
                    document.getElementById('question').textContent = 'Что относится к правителю «' + emName[currentItem.emperor] + '»?';
                    var cur = currentItem;
                    var others = allItems.filter(function(it) { return it !== cur && inScope(it); });
                    shuffleArray(others);
                    var list = [cur].concat(others.slice(0, 5));
                    shuffleArray(list);
                    list.forEach(function(it) {
                        var btn = document.createElement('button');
                        btn.className = 'opt-btn';
                        btn.textContent = (it.type === 'event' ? '📅 ' : '👤 ') + it.text;
                        btn.dataset.correct = (it === cur) ? '1' : '0';
                        btn.addEventListener('click', function() { answerClick(btn); });
                        opts.appendChild(btn);
                    });
                    return;
                }
                document.getElementById('question').textContent = 'К какому правителю относится?\\n' + currentItem.label + ': ' + currentItem.text;
                var correct = currentItem.emperor;
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                var list;
                if (optCount === 'all') {
                    list = rulers.slice();
                } else {
                    var pool = rulers.slice();
                    shuffleArray(pool);
                    var correctRuler = null;
                    var distractors = [];
                    for (var i = 0; i < pool.length; i++) {
                        if (pool[i].id === correct) { correctRuler = pool[i]; }
                        else if (distractors.length < 5) { distractors.push(pool[i]); }
                    }
                    list = distractors.slice();
                    if (correctRuler) list.push(correctRuler);
                    shuffleArray(list);
                }
                list.forEach(function(e) {
                    var btn = document.createElement('button');
                    btn.className = 'opt-btn';
                    btn.textContent = e.name + ' (' + e.reign + ')';
                    btn.dataset.emperor = e.id;
                    btn.dataset.correct = (e.id === correct) ? '1' : '0';
                    btn.addEventListener('click', function() { answerClick(btn); });
                    opts.appendChild(btn);
                });
            }

            function answerClick(btn) {
                var btns = document.querySelectorAll('.opt-btn');
                btns.forEach(function(b) { b.disabled = true; });
                var isCorrect = btn.dataset.correct === '1';
                btns.forEach(function(b) {
                    if (b.dataset.correct === '1') b.classList.add('correct');
                    else if (b === btn) b.classList.add('wrong');
                });
                quizTotal++;
                var pts = diffInfo();
                if (isCorrect) {
                    streakCorrect++;
                    quizScore += (pts.level >= 3) ? 2 : 1;
                } else {
                    streakCorrect = 0;
                    quizScore += (pts.level === 2) ? -2 : -1;
                }
                saveScore();
                updateScore();
                var info = document.getElementById('info');
                var lines = [];
                lines.push('<span class="info-label">' + (isCorrect ? '✅ Верно' : '❌ Неверно') + '</span>');
                lines.push('<div><b>' + esc(currentItem.label) + ':</b> ' + esc(currentItem.text) + '</div>');
                if (currentItem.info) lines.push('<div>📎 ' + esc(currentItem.info) + '</div>');
                lines.push('<div>👑 Император: <b>' + esc(emName[currentItem.emperor]) + '</b></div>');
                info.innerHTML = lines.join('');
                info.style.display = 'block';
                var qEl = document.getElementById('question');
                qEl.classList.remove('animate-correct', 'animate-wrong');
                void qEl.offsetWidth;
                if (isCorrect) {
                    qEl.classList.add('animate-correct');
                    btn.classList.add('animate-correct');
                } else {
                    qEl.classList.add('animate-wrong');
                    btn.classList.add('animate-wrong');
                }
                updateStreak(isCorrect);
                hubTrack('emperors', 1);
                if (isCorrect) {
                    wrongItems = wrongItems.filter(function(it) { return it.text !== currentItem.text; });
                } else {
                    if (!wrongItems.some(function(it) { return it.text === currentItem.text; })) wrongItems.push(currentItem);
                    if (deck.indexOf(currentItem) === -1) deck.push(currentItem);
                    shuffleArray(deck);
                }
                recordAnswer(currentItem, isCorrect);
                saveWrong();
                updateScore();
                document.getElementById('hint-btn').style.display = 'none';
                var nextBtn = document.getElementById('next-btn');
                nextBtn.style.display = 'block';
                nextBtn.onclick = loadQuestion;
            }

            var matchState = { pool: [], sel: null };

            function startMatch() {
                matchState.sel = null;
                var poolItems = itemsInScope();
                matchState.pool = shuffleArray(poolItems.slice()).slice(0, 10);
                var items = document.getElementById('match-items');
                items.innerHTML = '';
                matchState.pool.forEach(function(it) {
                    var chip = document.createElement('span');
                    chip.className = 'chip match-chip';
                    chip.textContent = it.text;
                    chip.dataset.key = flashKey(it);
                    chip.onclick = function() { selectMatchChip(chip); };
                    items.appendChild(chip);
                });
                var grid = document.getElementById('match-columns');
                grid.innerHTML = '';
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                rulers.forEach(function(e) {
                    var col = document.createElement('div');
                    col.className = 'match-col';
                    col.dataset.emperor = e.id;
                    col.innerHTML = '<div class="match-col-head" style="color:' + COLORS[e.id] + '">' + esc(e.name) + '</div>';
                    col.onclick = function() { placeMatchChip(col); };
                    grid.appendChild(col);
                });
                document.getElementById('match-count').textContent = 'Карточек: ' + matchState.pool.length;
                document.getElementById('match-info').style.display = 'none';
            }
            function selectMatchChip(chip) {
                if (chip.classList.contains('placed')) return;
                if (matchState.sel) matchState.sel.classList.remove('sel');
                chip.classList.add('sel');
                matchState.sel = chip;
            }
            function placeMatchChip(col) {
                if (!matchState.sel) return;
                var chip = matchState.sel;
                var it = matchState.pool.filter(function(p) { return flashKey(p) === chip.dataset.key; })[0];
                var correct = (it.emperor === col.dataset.emperor);
                var span = document.createElement('span');
                span.className = 'chip match-chip placed' + (correct ? ' ok' : ' bad');
                span.textContent = it.text;
                span.title = it.info || '';
                var x = document.createElement('button');
                x.className = 'x';
                x.textContent = '✕';
                x.onclick = function() { span.remove(); chip.classList.remove('placed'); chip.style.display = 'inline-block'; chip.textContent = it.text; };
                span.appendChild(x);
                if (correct) {
                    chip.classList.add('placed');
                    chip.style.display = 'none';
                } else {
                    chip.classList.remove('sel');
                    chip.textContent = it.text;
                    matchState.sel = null;
                }
                col.appendChild(span);
                checkMatchDone();
            }
            function checkMatchDone() {
                var remaining = matchState.pool.filter(function(p) {
                    return !document.querySelector('.match-chip[data-key="' + CSS.escape(flashKey(p)) + '"].placed');
                });
                if (remaining.length === 0) {
                    var placedOk = document.querySelectorAll('.match-chip.placed.ok').length;
                    var info = document.getElementById('match-info');
                    info.innerHTML = '<span class="info-label">🎉 Готово!</span> Все ' + matchState.pool.length + ' разложены верно.';
                    info.style.display = 'block';
                }
            }
            function checkMatch() {
                var info = document.getElementById('match-info');
                var placedOk = document.querySelectorAll('.match-chip.placed.ok').length;
                var placedBad = document.querySelectorAll('.match-chip.placed.bad').length;
                var left = matchState.pool.length - (placedOk + placedBad);
                info.innerHTML = '<span class="info-label">Результат:</span> верно ' + placedOk + ', ошибок ' + placedBad + ', осталось ' + left + '.';
                info.style.display = 'block';
            }

            var chronoState = { order: [], placed: [] };

            function startChrono() {
                var rulers = (scope === 'all' ? DATA.rulers : DATA.emperors);
                chronoState.order = rulers.slice();
                chronoState.placed = [];
                renderChrono();
            }
            function renderChrono() {
                var opts = document.getElementById('chrono-options');
                opts.innerHTML = '';
                var left = chronoState.order.slice();
                shuffleArray(left);
                left.forEach(function(e) {
                    var btn = document.createElement('button');
                    btn.className = 'opt-btn';
                    btn.textContent = e.name + ' (' + e.reign + ')';
                    btn.style.borderLeftColor = COLORS[e.id];
                    btn.addEventListener('click', function() { chronoPick(e); });
                    opts.appendChild(btn);
                });
                var ans = document.getElementById('chrono-answer');
                ans.innerHTML = '';
                chronoState.order.forEach(function(e) {
                    var chip = document.createElement('span');
                    chip.className = 'chip';
                    chip.style.borderColor = COLORS[e.id];
                    chip.textContent = e.name;
                    ans.appendChild(chip);
                });
                var placed = document.getElementById('chrono-placed');
                placed.innerHTML = '';
                chronoState.placed.forEach(function(e) {
                    var chip = document.createElement('span');
                    chip.className = 'chip';
                    chip.style.borderColor = COLORS[e.id];
                    chip.textContent = e.name;
                    placed.appendChild(chip);
                });
                document.getElementById('chrono-count').textContent = 'Поставлено: ' + chronoState.placed.length + ' / ' + chronoState.order.length;
            }
            function chronoPick(e) {
                var correct = chronoState.order[chronoState.placed.length];
                if (e.id === correct.id) {
                    chronoState.placed.push(e);
                    var info = document.getElementById('chrono-info');
                    info.style.display = 'block';
                    info.innerHTML = '<span class="info-label">✅ Верно</span> ' + esc(e.name) + ' (' + esc(e.reign) + ')';
                    if (chronoState.placed.length === chronoState.order.length) {
                        info.innerHTML = '<span class="info-label">🎉 Готово!</span> Все правители расставлены верно.';
                    }
                    renderChrono();
                } else {
                    var q = document.getElementById('chrono-question');
                    q.classList.remove('animate-wrong');
                    void q.offsetWidth;
                    q.classList.add('animate-wrong');
                    var info = document.getElementById('chrono-info');
                    info.style.display = 'block';
                    info.innerHTML = '<span class="info-label">❌ Неверно</span> Сейчас правит ' + esc(correct.name) + ' (' + esc(correct.reign) + ')';
                }
            }
            function checkChrono() {
                var info = document.getElementById('chrono-info');
                if (chronoState.placed.length === chronoState.order.length) {
                    info.style.display = 'block';
                    info.innerHTML = '<span class="info-label">✅</span> Всё верно, ' + chronoState.placed.length + ' / ' + chronoState.order.length + '.';
                } else {
                    info.style.display = 'block';
                    info.innerHTML = '<span class="info-label">❌</span> Осталось поставить: ' + (chronoState.order.length - chronoState.placed.length) + '. Правильный следующий: ' + esc(chronoState.order[chronoState.placed.length].name) + '.';
                }
            }

            window.app = {
                showTab: function(tab) {
                    var tabs = ['study', 'quiz', 'match', 'chrono'];
                    var ids = { study: ['tab-study', 'panel-study'], quiz: ['tab-quiz', 'panel-quiz'], match: ['tab-match', 'panel-match'], chrono: ['tab-chrono', 'panel-chrono'] };
                    tabs.forEach(function(t) {
                        document.getElementById(ids[t][0]).classList.toggle('active', t === tab);
                        document.getElementById(ids[t][1]).classList.toggle('active', t === tab);
                    });
                    hubTrack('emperors', 0, ['emperors_mode_' + tab]);
                    if (tab === 'quiz') { loadQuestion(); }
                    if (tab === 'match') { startMatch(); }
                    if (tab === 'chrono') { startChrono(); }
                },
                toggleMode: function() {
                    onlyErrors = document.getElementById('mode-errors').checked;
                    updateScore();
                    loadQuestion();
                },
                toggleAlgo: function() {
                    algo = document.getElementById('algo-select').value;
                    localStorage.setItem('emperors_algo', algo);
                    updateScore();
                    loadQuestion();
                },
                toggleScope: function(el) {
                    scope = el.value;
                    localStorage.setItem('emperors_scope', scope);
                    document.querySelectorAll('.scope-sel').forEach(function(s) { s.value = scope; });
                    deck = [];
                    studyPanel();
                    updateScore();
                    loadQuestion();
                    if (document.getElementById('panel-match').classList.contains('active')) startMatch();
                    if (document.getElementById('panel-chrono').classList.contains('active')) startChrono();
                },
                toggleOptCount: function() {
                    optCount = document.getElementById('opt-count').value;
                    localStorage.setItem('emperors_optcount', optCount);
                    updateDiffBadge();
                    loadQuestion();
                },
                toggleQDir: function() {
                    qdir = document.getElementById('qdir-select').value;
                    localStorage.setItem('emperors_qdir', qdir);
                    updateDiffBadge();
                    loadQuestion();
                },
                startChrono: startChrono,
                checkChrono: checkChrono,
                resetScore: function() {
                    quizScore = 0; quizTotal = 0; wrongItems = [];
                    flash = {}; saveFlashLocal();
                    localStorage.removeItem('emperors_flash');
                    if (authToken) {
                        fetch('/api/emperors/progress', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-Auth-Token': authToken },
                            body: JSON.stringify({ cards: {}, reset: true })
                        }).catch(function() {});
                    }
                    saveScore(); saveWrong(); updateScore(); loadQuestion();
                },
                showHint: function() {
                    if (!currentItem) return;
                    var box = document.getElementById('hint-box');
                    box.style.display = 'block';
                    box.textContent = '💡 ' + (currentItem.info || 'Подсказка: вспомни, при каком императоре происходило это событие / жила эта личность.');
                },
                startMatch: startMatch,
                checkMatch: checkMatch,
                toggleDebug: function() {
                    var panel = document.getElementById('debug-panel');
                    panel.style.display = (panel.style.display === 'block') ? 'none' : 'block';
                    if (panel.style.display === 'block') renderDebug();
                },
                showInfo: function(el) {
                    var type = el.getAttribute('data-type');
                    var text = el.getAttribute('data-text');
                    var item = null;
                    if (type === 'event') {
                        for (var i = 0; i < DATA.events.length; i++) {
                            if (DATA.events[i].title === text) { item = DATA.events[i]; break; }
                        }
                    } else {
                        for (var j = 0; j < DATA.persons.length; j++) {
                            if (DATA.persons[j].name === text) { item = DATA.persons[j]; break; }
                        }
                    }
                    if (!item) return;
                    document.getElementById('info-tag').textContent = type === 'event' ? 'Событие' : 'Личность';
                    var imp = item.importance || 3;
                    var stars = '';
                    for (var i = 0; i < 5; i++) stars += (i < imp) ? '★' : '☆';
                    document.getElementById('info-title').textContent = (type === 'event' ? (item.year ? item.year + ' — ' : '') : '') + (type === 'event' ? item.title : item.name);
                    var emp = emName[item.emperor];
                    document.getElementById('info-emperor').innerHTML = emp ? '👑 ' + esc(emp) + ' <span style="color:var(--bb-warn)">' + stars + '</span>' : '';
                    document.getElementById('info-emperor').style.color = COLORS[item.emperor];
                    document.getElementById('info-body').textContent = type === 'event' ? (item.note || 'Описание отсутствует.') : (item.description || 'Описание отсутствует.');
                    document.getElementById('info-modal').classList.add('show');
                },
                closeInfo: function() {
                    document.getElementById('info-modal').classList.remove('show');
                }
            };
            document.addEventListener('keydown', function(e) {
                if (!document.getElementById('panel-quiz').classList.contains('active')) return;
                if (e.key >= '1' && e.key <= '6') {
                    var btns = document.querySelectorAll('.opt-btn');
                    var idx = parseInt(e.key, 10) - 1;
                    if (btns[idx] && !btns[idx].disabled) btns[idx].click();
                } else if (e.key === 'Enter') {
                    var nb = document.getElementById('next-btn');
                    if (nb.style.display === 'block') { nb.click(); }
                }
            });
            studyPanel();
            updateScore();
            loadQuestion();
        })();
    </script>
</body>
</html>""".replace("__DATA__", history_data)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}



@app.route("/math")
def math_page():
    import json
    from core.math.tasks import MATH_TOPICS, task_by_id, tasks_for_topic, get_random_task, get_tasks_by_difficulty

    # Get all topic names for the study tab
    topic_names = {t.id: t.name for t in MATH_TOPICS}

    # Get all task IDs for the trainer
    all_task_ids = []
    for topic in MATH_TOPICS:
        for task in topic.tasks:
            all_task_ids.append(task.id)

    # Build topics data for JavaScript
    topics_data = json.dumps(
        {
            "topics": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "theory": t.theory,
                    "code": list(t.code_examples),
                    "taskCount": len(t.tasks),
                    "tasks": [
                        {
                            "id": task.id,
                            "question": task.question,
                            "hint": task.hint,
                            "answer": task.answer,
                            "explanation": task.explanation,
                            "difficulty": task.difficulty,
                        }
                        for task in t.tasks
                    ],
                }
                for t in MATH_TOPICS
            ],
            "allTaskIds": all_task_ids,
        },
        ensure_ascii=False,
    )

    first_topic_id = list(topic_names.keys())[0] if topic_names else ""

    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Информатика — ОГЭ</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 800px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .header a:hover { color: var(--bb-accent); }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .tab-btn { flex: 1; padding: 12px; background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 15px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .tab-btn:hover { background: var(--bb-link); }
        .tab-btn.active { background: var(--bb-accent); border-color: var(--bb-accent); color: white; }
        .panel { display: none; }
        .panel.active { display: block; }
        .score { text-align: center; color: var(--bb-muted); font-size: 14px; margin-bottom: 16px; }
        .topic-card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
        .topic-card h2 { font-size: 18px; color: var(--bb-accent); margin-bottom: 8px; }
        .topic-card .description { color: var(--bb-muted); font-size: 14px; margin-bottom: 12px; }
        .topic-card .task-count { color: var(--bb-muted); font-size: 12px; }
        .task { background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .task.question { color: var(--bb-text); }
        .task.answer { display: none; color: var(--bb-green3); }
        .task h3 { font-size: 16px; margin-bottom: 8px; }
        .task .hint { color: var(--bb-muted); font-size: 13px; margin-bottom: 8px; }
        .task .explanation { color: var(--bb-muted); font-size: 12px; display: none; }
        .answer-btn { width: 100%; padding: 12px; background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 10px; font-size: 14px; cursor: pointer; margin-top: 8px; }
        .answer-btn.correct { background: var(--bb-green); border-color: var(--bb-green2); }
        .answer-btn.wrong { background: var(--bb-red); border-color: var(--bb-red); }
        .stats { text-align: center; color: var(--bb-muted); margin-top: 24px; font-size: 13px; }
        .hint-box { background: var(--bb-primary); border-radius: 10px; padding: 12px; margin-bottom: 14px; font-size: 14px; color: var(--bb-muted); line-height: 1.5; display: none; }
        .hint-btn { display: block; width: 100%; padding: 10px; background: none; border: 1px dashed var(--bb-link); color: var(--bb-muted); border-radius: 10px; font-size: 13px; cursor: pointer; margin-top: 10x; font-family: inherit; }
        .hint-btn:hover { border-color: var(--bb-warn); color: var(--bb-warn); }
        .next-btn { display: none; width: 100%; padding: 14px; background: var(--bb-accent); color: white; border: none; border-radius: 12px; font-size: 16px; cursor: pointer; margin-top: 16px; font-family: inherit; }
        .next-btn:hover { background: var(--bb-accent2); }
        .mode-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; justify-content: center; flex-wrap: wrap; }
        .mode-row label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: var(--bb-text); cursor: pointer; }
        .diff-select { background: var(--bb-primary); color: var(--bb-text); border: 1px solid var(--bb-link); border-radius: 8px; padding: 6px 10px; font-size: 13px; font-family: inherit; cursor: pointer; }
        .progress-bar { flex: 1; height: 8px; background: var(--bb-primary); border-radius: 6px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--bb-accent); width: 0%; transition: width 0.25s; }
        .progress-label { font-size: 12px; color: var(--bb-muted); white-space: nowrap; }
        .diff-badge { display: flex; align-items: center; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 14px; font-size: 13px; }
        .diff-stars { color: var(--bb-gold); letter-spacing: 1px; font-size: 15px; }
        .diff-pts { background: var(--bb-primary); border: 1px solid var(--bb-link); color: var(--bb-text); border-radius: 8px; padding: 2px 8px; font-weight: 600; }
        .info { background: var(--bb-primary); border-radius: 12px; padding: 16px; margin-top: 16px; font-size: 14px; line-height: 1.5; color: var(--bb-muted); display: none; }
        .info .info-label { color: var(--bb-accent); font-weight: 600; }
        .stats-card {{ font-size: 13px; color: var(--bb-muted); }}
        .stats-card .stat-line {{ margin: 4px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Информатика — ОГЭ</h1>
            <a href="/">← Назад на хаб</a>
        </div>

        <div class="tabs">
            <button class="tab-btn active" data-tab="study">📚 Изучить</button>
            <button class="tab-btn" data-tab="theory">📖 Теория</button>
            <button class="tab-btn" data-tab="trainer">🧠 Тренажер</button>
        </div>

        <!-- Study Tab: Browse topics -->
        <div id="panel-study" class="panel active">
            <div class="score" id="study-score">Тема: —</div>
            <div class="topics-grid" id="topics-grid"></div>
        </div>

        <!-- Theory Tab: Read the lesson theory -->
        <div id="panel-theory" class="panel">
            <div class="score" id="theory-score">Выберите урок</div>
            <div class="topics-grid" id="theory-grid"></div>
        </div>

        <!-- Trainer Tab: Solve problems -->
        <div id="panel-trainer" class="panel">
            <div class="score" id="trainer-score">Балл: 0/<span id="trainer-total">0</span></div>
            <div class="hint-box" id="hint-box">
                <button class="hint-btn" id="hint-btn">Подсказка</button>
            </div>
            <div class="task" id="current-task">
                <h3>Выберите тему и нажмите «Получить задачу»</h3>
            </div>
            <button class="answer-btn" id="answer-btn">Ответить</button>
            <div class="stats" id="stats"></div>
            <button class="next-btn" id="next-btn">Следующая задача</button>
        </div>

    </div>

    <script>
        // Initialize state
        let currentTopic = "__FIRST_TOPIC__";
        let currentTaskIndex = 0;
        let correctStreak = 0;
        let totalSolved = 0;
        let wrongAnswers = 0;
        let hubActivity = {};
        try { hubActivity = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch (e) {}

        // Load topics data
        const topicsData = __TOPICS_DATA__;
        const topicNames = __TOPIC_NAMES__;

        // --- Tab switching ---
        function switchTab(name) {
            document.querySelectorAll('.tab-btn').forEach(function (btn) {
                btn.classList.toggle('active', btn.dataset.tab === name);
            });
            document.getElementById('panel-study').classList.toggle('active', name === 'study');
            document.getElementById('panel-theory').classList.toggle('active', name === 'theory');
            document.getElementById('panel-trainer').classList.toggle('active', name === 'trainer');
            if (name === 'theory') renderTheoryTab();
        }
        document.querySelectorAll('.tab-btn').forEach(function (btn) {
            btn.addEventListener('click', function () { switchTab(btn.dataset.tab); });
        });

        // --- Theory tab: read the lesson summary ---
        function renderTheoryTab() {
            const grid = document.getElementById('theory-grid');
            grid.innerHTML = '';
            topicsData.topics.forEach(function (topic) {
                const card = document.createElement('div');
                card.className = 'topic-card';
                const btn = document.createElement('button');
                btn.className = 'tab-btn';
                btn.textContent = 'Читать конспект';
                btn.addEventListener('click', function () { loadTheory(topic.id); });
                const h2 = document.createElement('h2');
                h2.textContent = topic.name;
                const p1 = document.createElement('p');
                p1.className = 'description';
                p1.textContent = topic.description;
                const p2 = document.createElement('p');
                p2.className = 'task-count';
                p2.textContent = 'Задач в уроке: ' + topic.taskCount;
                card.appendChild(h2);
                card.appendChild(p1);
                card.appendChild(p2);
                card.appendChild(btn);
                grid.appendChild(card);
            });
        }

        function loadTheory(topicId) {
            const topic = topicsData.topics.find(function (t) { return t.id === topicId; });
            if (!topic) return;
            document.getElementById('theory-score').textContent = 'Урок: ' + (topicNames[topicId] || topicId);
            const grid = document.getElementById('theory-grid');
            grid.innerHTML = '';
            const card = document.createElement('div');
            card.className = 'topic-card';
            const h2 = document.createElement('h2');
            h2.textContent = topic.name;
            card.appendChild(h2);
            const p1 = document.createElement('p');
            p1.className = 'description';
            p1.textContent = topic.description;
            card.appendChild(p1);
            const theory = document.createElement('div');
            theory.style.marginTop = '12px';
            theory.style.lineHeight = '1.6';
            theory.style.fontSize = '14px';
            theory.style.color = '#cbd5e1';
            theory.style.whiteSpace = 'pre-wrap';
            theory.textContent = topic.theory || 'Конспект отсутствует.';
            card.appendChild(theory);
            if (topic.code && topic.code.length) {
                const cl = document.createElement('div');
                cl.style.marginTop = '14px';
                topic.code.forEach(function (codeText) {
                    const pre = document.createElement('pre');
                    pre.style.background = 'var(--bb-primary)';
                    pre.style.border = '1px solid var(--bb-link)';
                    pre.style.borderRadius = '10px';
                    pre.style.padding = '12px';
                    pre.style.overflowX = 'auto';
                    pre.style.fontSize = '12px';
                    pre.style.color = '#9be7c4';
                    pre.style.whiteSpace = 'pre';
                    pre.textContent = codeText;
                    cl.appendChild(pre);
                });
                card.appendChild(cl);
            }
            const backBtn = document.createElement('button');
            backBtn.className = 'tab-btn';
            backBtn.style.marginTop = '16px';
            backBtn.textContent = '← Ко всем урокам';
            backBtn.addEventListener('click', renderTheoryTab);
            card.appendChild(backBtn);
            grid.appendChild(card);
        }


        function escapeHtml(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        // --- Study tab: browse topics ---
        function renderStudyTab() {
            const grid = document.getElementById('topics-grid');
            grid.innerHTML = '';
            topicsData.topics.forEach(function (topic) {
                const card = document.createElement('div');
                card.className = 'topic-card';
                const btn = document.createElement('button');
                btn.className = 'tab-btn';
                btn.textContent = 'Открыть';
                btn.addEventListener('click', function () { loadTopic(topic.id); });
                const h2 = document.createElement('h2');
                h2.textContent = topic.name;
                const p1 = document.createElement('p');
                p1.className = 'description';
                p1.textContent = topic.description;
                const p2 = document.createElement('p');
                p2.className = 'task-count';
                p2.textContent = 'Задач: ' + topic.taskCount;
                card.appendChild(h2);
                card.appendChild(p1);
                card.appendChild(p2);
                card.appendChild(btn);
                grid.appendChild(card);
            });
        }

        // Load a specific topic (study tab)
        function loadTopic(topicId) {
            currentTopic = topicId;
            const score = document.getElementById('study-score');
            score.textContent = 'Тема: ' + (topicNames[topicId] || topicId);
            const topic = topicsData.topics.find(function (t) { return t.id === topicId; });
            if (!topic) return;
            const grid = document.getElementById('topics-grid');
            grid.innerHTML = '';
            topic.tasks.forEach(function (task, index) {
                const taskDiv = document.createElement('div');
                taskDiv.className = 'task';
                const h3 = document.createElement('h3');
                h3.textContent = task.question;
                taskDiv.appendChild(h3);
                if (task.hint) {
                    const hint = document.createElement('p');
                    hint.className = 'hint';
                    hint.textContent = '💡 ' + task.hint;
                    taskDiv.appendChild(hint);
                }
                const btn = document.createElement('button');
                btn.className = 'answer-btn';
                btn.textContent = 'Показать ответ';
                btn.addEventListener('click', function () {
                    const ans = document.createElement('p');
                    ans.className = 'task answer';
                    ans.style.display = 'block';
                    ans.style.color = 'var(--bb-green3)';
                    ans.textContent = 'Ответ: ' + task.answer;
                    taskDiv.appendChild(ans);
                    if (task.explanation) {
                        const exp = document.createElement('p');
                        exp.className = 'explanation';
                        exp.style.display = 'block';
                        exp.style.color = '#9ca3af';
                        exp.textContent = 'Пояснение: ' + task.explanation;
                        taskDiv.appendChild(exp);
                    }
                    btn.disabled = true;
                    btn.textContent = '✓ Ответ показан';
                });
                taskDiv.appendChild(btn);
                grid.appendChild(taskDiv);
            });
            const backBtn = document.createElement('button');
            backBtn.className = 'tab-btn';
            backBtn.style.marginTop = '16px';
            backBtn.textContent = '← Ко всем темам';
            backBtn.addEventListener('click', renderStudyTab);
            grid.appendChild(backBtn);
        }

        // --- Trainer tab: random tasks ---
        let trainQueue = [];
        let trainDone = [];

        function shuffle(arr) {
            for (let i = arr.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
            }
            return arr;
        }

        function buildQueue() {
            const topic = topicsData.topics.find(function (t) { return t.id === currentTopic; });
            const tasks = (topic && topic.tasks) || [];
            trainQueue = shuffle(tasks.slice());
            trainDone = [];
            document.getElementById('trainer-total').textContent = trainQueue.length;
            if (!trainQueue.length) {
                document.getElementById('current-task').innerHTML = '<h3>В этой теме нет задач</h3>';
            }
        }

        function showTrainerTask() {
            const box = document.getElementById('current-task');
            box.innerHTML = '';
            if (!trainQueue.length) {
                const fin = document.createElement('h3');
                fin.textContent = '🎉 Все задачи темы пройдены!';
                box.appendChild(fin);
                document.getElementById('next-btn').style.display = 'none';
                const again = document.createElement('button');
                again.className = 'answer-btn';
                again.textContent = 'Пройти ещё раз';
                again.addEventListener('click', function () {
                    buildQueue();
                    showTrainerTask();
                });
                box.appendChild(again);
                return;
            }
            const task = trainQueue[0];
            const h3 = document.createElement('h3');
            h3.textContent = 'Вопрос: ' + task.question;
            box.appendChild(h3);
            if (task.hint) {
                const hint = document.createElement('p');
                hint.className = 'hint';
                hint.textContent = '💡 ' + task.hint;
                box.appendChild(hint);
            }
            const reveal = document.createElement('button');
            reveal.className = 'answer-btn';
            reveal.textContent = 'Показать ответ';
            reveal.addEventListener('click', function () {
                const ans = document.createElement('p');
                ans.className = 'task answer';
                ans.style.display = 'block';
                ans.style.color = 'var(--bb-green3)';
                ans.textContent = 'Ответ: ' + task.answer;
                box.appendChild(ans);
                if (task.explanation) {
                    const exp = document.createElement('p');
                    exp.className = 'explanation';
                    exp.style.display = 'block';
                    exp.style.color = '#9ca3af';
                    exp.textContent = 'Пояснение: ' + task.explanation;
                    box.appendChild(exp);
                }
                totalSolved++;
                correctStreak++;
                trainDone.push(task);
                trainQueue.shift();
                document.getElementById('trainer-score').textContent = 'Решено: ' + totalSolved;
                document.getElementById('next-btn').style.display = 'block';
                reveal.style.display = 'none';
            });
            box.appendChild(reveal);
            document.getElementById('next-btn').style.display = 'none';
        }

        // Trainer UI wiring
        const topicSelect = document.createElement('select');
        topicSelect.className = 'diff-select';
        topicsData.topics.forEach(function (topic) {
            const opt = document.createElement('option');
            opt.value = topic.id;
            opt.textContent = topic.name;
            topicSelect.appendChild(opt);
        });
        const modeRow = document.createElement('div');
        modeRow.className = 'mode-row';
        const lbl = document.createElement('label');
        lbl.textContent = 'Тема: ';
        modeRow.appendChild(lbl);
        modeRow.appendChild(topicSelect);
        const startBtn = document.createElement('button');
        startBtn.className = 'answer-btn';
        startBtn.textContent = 'Начать тренажёр';
        modeRow.appendChild(startBtn);
        document.getElementById('panel-trainer').insertBefore(modeRow, document.getElementById('panel-trainer').firstChild);

        startBtn.addEventListener('click', function () {
            currentTopic = topicSelect.value;
            buildQueue();
            totalSolved = 0;
            correctStreak = 0;
            document.getElementById('trainer-score').textContent = 'Решено: 0';
            showTrainerTask();
        });

        document.getElementById('next-btn').addEventListener('click', function () {
            document.getElementById('next-btn').style.display = 'none';
            showTrainerTask();
        });

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function () {
            renderStudyTab();
            buildQueue();
        });
    </script>
</body>
</html>"""

    html = (html
            .replace("__TOPICS_DATA__", topics_data)
            .replace("__TOPIC_NAMES__", json.dumps(dict(topic_names), ensure_ascii=False))
            .replace("__FIRST_TOPIC__", first_topic_id))
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/achievements")
def achievements_page():
    """Unified achievements & streak page: unlocked and upcoming badges + calendar."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Достижения</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bb-bg); color: var(--bb-text); font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; min-height: 100vh; }
        .container { max-width: 960px; margin: 0 auto; padding: 20px; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .header h1 { font-size: 24px; color: var(--gh-text2); }
        .header a { color: var(--bb-link); text-decoration: none; font-size: 14px; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-link); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
        .stats-row { display: flex; gap: 12px; flex-wrap: wrap; }
        .stat-box { flex: 1; min-width: 140px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 12px; padding: 14px; text-align: center; }
        .stat-box .num { font-size: 28px; font-weight: 700; color: var(--bb-warn); }
        .stat-box .lbl { font-size: 12px; color: #9fb3c8; margin-top: 4px; }
        .section-title { font-size: 14px; color: var(--bb-accent); font-weight: 600; margin: 20px 0 12px; }
        .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
        .cal-cell { aspect-ratio: 1; border-radius: 8px; background: var(--bb-primary); border: 1px solid var(--bb-link); display: flex; align-items: center; justify-content: center; font-size: 11px; color: var(--bb-muted); }
        .cal-cell.active { background: var(--bb-green2); border-color: var(--gh-green); color: var(--gh-text2); font-weight: 600; }
        .cal-cell.today { border-color: var(--bb-warn); }
        .cal-cell.future { opacity: 0.35; }
        .cal-dow { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; margin-bottom: 6px; }
        .cal-dow span { font-size: 11px; color: var(--bb-muted); text-align: center; }
        .ach-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
        .ach-section { margin-bottom: 18px; }
        .ach-sec-title { font-size: 14px; font-weight: 700; color: var(--gh-text2); margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
        .ach-sec-title::before { content: ''; width: 4px; height: 16px; background: var(--bb-warn); border-radius: 2px; }
        .ach-sec-count { font-size: 12px; color: #9fb3c8; font-weight: 400; }
        .ach { background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 12px; padding: 12px; display: flex; gap: 10px; align-items: flex-start; transition: all 0.15s; }
        .ach.locked { opacity: 0.55; }
        .ach .icon { font-size: 26px; flex-shrink: 0; }
        .ach .name { font-weight: 600; font-size: 13px; color: var(--gh-text2); }
        .ach .desc { font-size: 12px; color: #9fb3c8; margin-top: 2px; line-height: 1.4; }
        .ach .module-tag { display: inline-block; font-size: 10px; color: var(--bb-warn); margin-top: 6px; }
        .ach.unlocked { border-color: var(--gh-green); background: var(--gh-green-panel); }
        .ach.unlocked .name::after { content: ' ✓'; color: var(--gh-green); }
        .module-filter { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
        .mf-btn { background: var(--bb-primary); border: 1px solid var(--bb-link); color: #9fb3c8; border-radius: 20px; padding: 6px 14px; cursor: pointer; font-size: 12px; font-family: inherit; }
        .mf-btn.active { background: var(--bb-link); color: var(--gh-text2); border-color: var(--bb-link); }
        .toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: var(--bb-panel); border: 1px solid var(--gh-green); color: var(--gh-text2); padding: 12px 20px; border-radius: 12px; display: none; z-index: 1000; font-size: 14px; box-shadow: 0 6px 24px rgba(0,0,0,0.5); }
        .empty { color: var(--bb-muted); font-size: 14px; padding: 20px; text-align: center; }
        @media (max-width: 600px) { .cal-cell { font-size: 9px; } .ach-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏆 Достижения</h1>
            <a href="/account">← В личный кабинет</a>
        </div>
        <div class="card">
            <div class="stats-row">
                <div class="stat-box"><div class="num" id="stat-unlocked">–</div><div class="lbl">открыто</div></div>
                <div class="stat-box"><div class="num" id="stat-total">–</div><div class="lbl">всего</div></div>
                <div class="stat-box"><div class="num" id="stat-current">–</div><div class="lbl">текущая серия</div></div>
                <div class="stat-box"><div class="num" id="stat-longest">–</div><div class="lbl">макс. серия</div></div>
            </div>
        </div>
        <div class="card">
            <div class="section-title">🔥 Календарь активности (последние 12 недель)</div>
            <div class="cal-dow"><span>Пн</span><span>Вт</span><span>Ср</span><span>Чт</span><span>Пт</span><span>Сб</span><span>Вс</span></div>
            <div class="cal-grid" id="calendar"></div>
        </div>
        <div class="card">
            <div class="section-title">🎖️ Достижения</div>
            <div class="module-filter" id="module-filter"></div>
            <div class="ach-grid" id="ach-grid"></div>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        (function() {
            var token = localStorage.getItem('web_token') || '';
            var uid = localStorage.getItem('web_user_id') || '';
            var toast = document.getElementById('toast');
            function showToast(msg) { toast.textContent = msg; toast.style.display = 'block'; setTimeout(function(){ toast.style.display = 'none'; }, 2600); }
            function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function(c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
            if (!token || uid.indexOf('u') !== 0) {
                document.querySelector('.container').innerHTML = '<div class="card"><div class="empty">Вы не вошли в аккаунт. <a href="/account" style="color:#4a90d9">Войдите</a>, чтобы видеть свои достижения.</div></div>';
                return;
            }
            function renderCalendar(calendar) {
                var active = {};
                calendar.forEach(function(d) { active[d] = true; });
                var today = new Date();
                var start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
                start.setDate(start.getDate() - 82);
                var monday = new Date(start);
                var dow = monday.getDay(); if (dow === 0) dow = 7;
                monday.setDate(monday.getDate() - (dow - 1));
                var html = '';
                var nowStr = function(d){ return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'); };
                for (var d = new Date(monday); d <= new Date(today); d.setDate(d.getDate() + 1)) {
                    var ds = nowStr(d);
                    var cls = 'cal-cell';
                    if (active[ds]) cls += ' active';
                    if (ds === nowStr(today)) cls += ' today';
                    if (d > today) cls += ' future';
                    html += '<div class="' + cls + '">' + d.getDate() + '</div>';
                }
                document.getElementById('calendar').innerHTML = html;
            }
            var modNames = { all: 'Все', trivia: '🧠 Викторина', emperors: '👑 Императоры', reading: '📖 Чтение', verbs: '🔤 Глаголы', chess: '♟️ Шахматы', canon: '📜 Канон', prayer: '🙏 Молитва', gd: '🎮 GD', dnd: '🎲 D&D', system: '⚙️ Система', streak: '🔥 Серии', coins: '💰 Монеты' };
            var modOrder = ['system', 'streak', 'coins', 'trivia', 'emperors', 'reading', 'verbs', 'chess', 'canon', 'prayer', 'gd', 'dnd'];
            function render(data) {
                document.getElementById('stat-unlocked').textContent = data.unlocked_count;
                document.getElementById('stat-total').textContent = data.total_count;
                document.getElementById('stat-current').textContent = data.streak.current;
                document.getElementById('stat-longest').textContent = data.streak.longest;
                renderCalendar(data.calendar);
                var filter = document.getElementById('module-filter');
                filter.innerHTML = '';
                ['all'].concat(modOrder).forEach(function(m) {
                    var b = document.createElement('button');
                    b.className = 'mf-btn' + (m === 'all' ? ' active' : '');
                    b.textContent = modNames[m] || m;
                    b.onclick = function() {
                        document.querySelectorAll('.mf-btn').forEach(function(x){ x.classList.remove('active'); });
                        b.classList.add('active');
                        renderAch(data, m);
                    };
                    filter.appendChild(b);
                });
                renderAch(data, 'all');
            }
            function renderAch(data, module) {
                var grid = document.getElementById('ach-grid');
                grid.innerHTML = '';
                var achEl = function(a) {
                    var el = document.createElement('div');
                    el.className = 'ach' + (a.unlocked ? ' unlocked' : ' locked');
                    el.innerHTML = '<div class="icon">' + (a.icon || '🎖️') + '</div><div><div class="name">' + esc(a.name) + '</div><div class="desc">' + esc(a.desc) + '</div><div class="module-tag">' + (a.unlocked ? '✅ открыто' : '🔒 впереди') + '</div></div>';
                    return el;
                };
                var mods = module === 'all' ? modOrder : [module];
                var any = false;
                mods.forEach(function(m) {
                    var list = data.achievements.filter(function(a){ return a.module === m; });
                    if (!list.length) return;
                    any = true;
                    var sec = document.createElement('div');
                    sec.className = 'ach-section';
                    sec.innerHTML = '<div class="ach-sec-title">' + (modNames[m] || m) + ' <span class="ach-sec-count">' + list.filter(function(a){ return a.unlocked; }).length + '/' + list.length + '</span></div>';
                    var g = document.createElement('div');
                    g.className = 'ach-grid';
                    list.forEach(function(a) { g.appendChild(achEl(a)); });
                    sec.appendChild(g);
                    grid.appendChild(sec);
                });
                if (!any) { grid.innerHTML = '<div class="empty">Нет достижений в этой категории.</div>'; }
            }
            fetch('/api/achievements', { headers: { 'X-Auth-Token': token } })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (d.error) { showToast(d.error); return; }
                    render(d);
                })
                .catch(function() { showToast('Ошибка загрузки'); });
        })();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/emperors/progress", methods=["GET"])
def api_emperors_progress():
    """Load the Emperors module SM-2 progress for the current web user.

    Progress is bound to the account: the uid is resolved from the session
    token, so the same account sees the same progress on any device.
    """
    user = _get_session_user(_auth_token_from_request())
    if not user:
        return jsonify({"cards": {}, "uid": 0})
    uid = _web_user_id("u" + str(user["id"]))
    cards = {}
    if uid:
        try:
            engine = get_db_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT card_key, reps, interval_days, ease, due, correct_count, wrong_count, counter FROM emperors_progress WHERE user_id = :uid"),
                    {"uid": uid},
                ).mappings()
                for r in rows:
                    cards[r["card_key"]] = {
                        "reps": r["reps"],
                        "interval": r["interval_days"],
                        "ease": r["ease"],
                        "due": r["due"],
                        "correct": r["correct_count"],
                        "wrong": r["wrong_count"],
                        "counter": r["counter"],
                    }
        except Exception as exc:
            print(f"[EMPERORS] progress GET error: {exc}")
    return jsonify({"cards": cards, "uid": uid})


@app.route("/api/emperors/progress", methods=["POST"])
def api_emperors_progress_save():
    """Save the Emperors module SM-2 progress for the current web user.

    Progress is bound to the account via the session token; anonymous users
    (no valid token) are not persisted — their progress stays on the device.
    """
    data = request.get_json(silent=True) or {}
    user = _get_session_user(_auth_token_from_request())
    if not user:
        return jsonify({"ok": False, "error": "auth required"}), 401
    uid = _web_user_id("u" + str(user["id"]))
    cards = data.get("cards") or {}
    if not uid:
        return jsonify({"ok": False, "error": "user_id required"}), 400
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            if data.get("reset"):
                conn.execute(text("DELETE FROM emperors_progress WHERE user_id = :uid"), {"uid": uid})
            else:
                for key, rec in cards.items():
                    conn.execute(text(
                        """
                        INSERT INTO emperors_progress (user_id, card_key, reps, interval_days, ease, due, correct_count, wrong_count, counter, updated_at)
                        VALUES (:uid, :key, :reps, :interval, :ease, :due, :correct, :wrong, :counter, :ts)
                        ON CONFLICT (user_id, card_key) DO UPDATE SET
                            reps = EXCLUDED.reps,
                            interval_days = EXCLUDED.interval_days,
                            ease = EXCLUDED.ease,
                            due = EXCLUDED.due,
                            correct_count = EXCLUDED.correct_count,
                            wrong_count = EXCLUDED.wrong_count,
                            counter = EXCLUDED.counter,
                            updated_at = EXCLUDED.updated_at
                        """
                    ), {
                        "uid": uid,
                        "key": key,
                        "reps": int(rec.get("reps", 0)),
                        "interval": int(rec.get("interval", 0)),
                        "ease": float(rec.get("ease", 2.5)),
                        "due": float(rec.get("due", 0)),
                        "correct": int(rec.get("correct", 0)),
                        "wrong": int(rec.get("wrong", 0)),
                        "counter": int(rec.get("counter", 0)),
                        "ts": time.time(),
                    })
        return jsonify({"ok": True, "uid": uid, "saved": len(cards)})
    except Exception as exc:
        print(f"[EMPERORS] progress POST error: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/trivia/question", methods=["POST"])
def api_trivia_question():
    import random
    q = random.choice(_TRIVIA_QUESTIONS)
    correct = q["correct_text"]
    group = q.get("group", "")
    manual = q.get("distractors") or []
    if len(manual) >= 3:
        distractors = random.sample(manual, 3)
    else:
        same = [x["correct_text"] for x in _TRIVIA_QUESTIONS if x.get("group") == group and x["correct_text"] != correct]
        pool = same if len(same) >= 3 else [x["correct_text"] for x in _TRIVIA_QUESTIONS if x["correct_text"] != correct]
        distractors = random.sample(pool, 3)
    options = [correct] + distractors
    random.shuffle(options)
    correct_index = options.index(correct)
    session = {"options": options, "correct_index": correct_index, "explanation": q["explanation"]}
    session_id = secrets.token_hex(6)
    _TRIVIA_SESSIONS[session_id] = session
    return jsonify({"id": q["id"], "session_id": session_id, "text": q["text"], "options": options, "correct_index": correct_index})


@app.route("/api/trivia/answer", methods=["POST"])
def api_trivia_answer():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or data.get("question_id")
    answer_idx = data.get("answer_index")
    session = _TRIVIA_SESSIONS.get(session_id)
    if not session:
        return jsonify({"correct": False, "correct_text": "", "explanation": "Вопрос не найден или устарел."})
    correct_index = session["correct_index"]
    is_correct = (
        isinstance(answer_idx, int)
        and not isinstance(answer_idx, bool)
        and 0 <= answer_idx < len(session["options"])
        and answer_idx == correct_index
    )
    return jsonify({"correct": is_correct, "correct_text": session["options"][correct_index], "explanation": session["explanation"]})


# ── Daily Prayer ──────────────────────────────────────────────────────────
# Молитвы импортируются из core.canon.prayers (source of truth).


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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 500px; width: 100%; text-align: center; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; justify-content: center; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 32px 24px; margin-bottom: 16px; }
        .prayer-icon { font-size: 64px; margin-bottom: 16px; }
        .prayer-text { font-size: 20px; line-height: 1.6; color: #f0e6d0; font-style: italic; margin: 20px 0; padding: 16px; border-left: 3px solid var(--bb-accent); text-align: left; }
        .prayer-amen { font-size: 16px; color: var(--bb-accent); margin-top: 12px; }
        .btn { display: inline-flex; align-items: center; gap: 8px; padding: 14px 32px; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .btn-primary { background: var(--bb-accent); color: var(--gh-text2); }
        .btn-primary:hover { background: var(--bb-accent2); }
        .btn-secondary { background: var(--bb-primary); color: var(--bb-text); }
        .btn-secondary:hover { background: var(--bb-link); }
        .subtext { font-size: 14px; color: var(--bb-muted); margin-top: 16px; }
        .prayer-emoji { font-size: 48px; margin-bottom: 8px; }
        .cooldown-msg { font-size: 18px; color: var(--bb-warn); margin: 20px 0; }
        .back-link { display: inline-block; color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-top: 16px; }
        .back-link:hover { color: var(--bb-accent); }
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
        var USER_ID = localStorage.getItem('web_user_id');
        if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10); localStorage.setItem('web_user_id', USER_ID); }
        function showRegNotice() {
            try {
                if (sessionStorage.getItem('reg_notice_shown')) return;
                sessionStorage.setItem('reg_notice_shown', '1');
                var re = document.getElementById('hub-reg-notice');
                if (!re) {
                    re = document.createElement('div');
                    re.id = 'hub-reg-notice';
                    re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                    re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                    document.body.appendChild(re);
                }
                clearTimeout(re._t);
                re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
            } catch(e) {}
        }
        function hubTrack(module, actions) {
            actions = actions || 1;
            var token = localStorage.getItem('web_token') || '';
            var uid = localStorage.getItem('web_user_id') || '';
            try {
                if (token && uid.indexOf('u') === 0) {
                    fetch('/api/achievements/activity', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                        body: JSON.stringify({ module: module, actions: actions })
                    }).then(function(r) { return r.json(); }).then(function(d) {
                        if (d && d.unlocked_detail && d.unlocked_detail.length) {
                            var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                            var pe = document.getElementById('hub-popup');
                            if (!pe) {
                                pe = document.createElement('div');
                                pe.id = 'hub-popup';
                                pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                document.body.appendChild(pe);
                            }
                            pe.innerHTML = '🏆 ' + names.join('<br>');
                            pe.style.display = 'block';
                            clearTimeout(pe._t);
                            pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                        }
                    }).catch(function() {});
                } else {
                    showRegNotice();
                    var today = new Date();
                    var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                    var acts = {};
                    try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                    acts[dayStr] = (acts[dayStr] || 0) + 1;
                    localStorage.setItem('hub_activity', JSON.stringify(acts));
                }
            } catch(e) {}
        }
        function showHubPopup(names) {
            var pe = document.getElementById('hub-popup');
            if (!pe) {
                pe = document.createElement('div');
                pe.id = 'hub-popup';
                pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                document.body.appendChild(pe);
            }
            pe.innerHTML = '🏆 ' + names.join('<br>');
            pe.style.display = 'block';
            clearTimeout(pe._t);
            pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
        }
        function getPrayer() {
            var btn = document.getElementById('get-btn');
            btn.disabled = true;
            btn.textContent = '🙏 Загрузка...';
            var token = localStorage.getItem('web_token') || '';
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/daily_prayer');
            xhr.setRequestHeader('Content-Type', 'application/json');
            if (token) { xhr.setRequestHeader('X-Auth-Token', token); }
            xhr.onload = function() {
                try {
                    var r = JSON.parse(xhr.responseText);
                    if (r.error) { document.getElementById('prayer-content').innerHTML = '<p style="color:var(--bb-accent)">'+r.error+'</p>'; btn.style.display='none'; return; }
                    document.getElementById('prayer-content').innerHTML = '<div class="prayer-text">"'+r.prayer+'"</div>';
                    if (r.already) {
                        document.getElementById('subtext').textContent = 'Вы уже получали сегодняшнюю молитву. Возвращайтесь завтра!';
                        btn.style.display = 'none';
                    } else {
                        document.getElementById('subtext').textContent = 'Молитва на сегодня';
                        btn.textContent = '🙏 Ещё';
                        btn.disabled = false;
                        var uid = localStorage.getItem('web_user_id') || '';
                        if (token && uid.indexOf('u') === 0) {
                            if (r.unlocked_detail && r.unlocked_detail.length) {
                                showHubPopup(r.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; }));
                            }
                        } else {
                            hubTrack('prayer', 1);
                        }
                    }
                } catch(e) { document.getElementById('prayer-content').innerHTML = '<p style="color:var(--bb-accent)">Ошибка загрузки.</p>'; }
            };
            xhr.onerror = function() { document.getElementById('prayer-content').innerHTML = '<p style="color:var(--bb-accent)">Ошибка сети.</p>'; };
            xhr.send(JSON.stringify({user_id: USER_ID}));
        }
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


def _prayer_for_day(user_key, day: str) -> str:
    """Deterministic prayer choice per user+date (stable for the whole day)."""
    if not _PRAYERS:
        return ""
    return _PRAYERS[hash((str(user_key or ""), day)) % len(_PRAYERS)]


@app.route("/api/daily_prayer", methods=["POST"])
def api_daily_prayer():
    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id", "")
    uid = _web_user_id(user_id_raw)
    today = date.today().isoformat()
    already = False
    unlocked_detail = []
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
                web_uid = _require_web_user()
                if web_uid:
                    _record_activity(conn, web_uid, "prayer", 1)
                    newly = _check_web_achievements(conn, web_uid)
                    conn.commit()
                    unlocked_detail = [
                        {
                            "code": code,
                            "icon": ACHIEVEMENTS[code]["icon"],
                            "name": ACHIEVEMENTS[code]["name"],
                        }
                        for code in newly
                    ]
            else:
                already = True
    except Exception as exc:
        print(f"[DAILY_PRAYER] error: {exc}")
    return jsonify({
        "prayer": _prayer_for_day(uid, today),
        "already": already,
        "unlocked_detail": unlocked_detail,
    })


# ── Achievements Module ────────────────────────────────────────────────────
# Единая система достижений и серий по всему порталу.

def _require_web_user():
    """Resolve the current web user id (web_users.id) or None."""
    user = _get_session_user(_auth_token_from_request())
    if not user:
        return None
    return user["id"]


@app.route("/api/achievements/activity", methods=["POST"])
def api_achievements_activity():
    """Record a user activity in a module and return newly unlocked achievements."""
    uid = _require_web_user()
    if not uid:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(silent=True) or {}
    module = str(data.get("module", "")).strip() or "system"
    actions = int(data.get("actions", 1) or 1)
    if actions < 1:
        actions = 1
    events = data.get("events") or []
    if isinstance(events, str):
        events = [events]
    try:
        with get_db_engine().connect() as conn:
            streak, longest, total = _record_activity(conn, uid, module, actions)
            _record_events(conn, uid, events)
            newly = _check_web_achievements(conn, uid)
            conn.commit()
        return jsonify({
            "ok": True,
            "streak": {"current": streak, "longest": longest, "total_days": total},
            "unlocked": newly,
            "unlocked_detail": [
                {
                    "code": code,
                    "icon": ACHIEVEMENTS[code]["icon"],
                    "name": ACHIEVEMENTS[code]["name"],
                }
                for code in newly
            ],
        })
    except Exception as exc:
        print(f"[ACHIEVEMENTS] activity error: {exc}")
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route("/api/achievements", methods=["GET"])
def api_achievements_list():
    """Return the full achievement registry with unlock state, streak and calendar."""
    uid = _require_web_user()
    if not uid:
        return jsonify({"error": "auth required"}), 401
    try:
        with get_db_engine().connect() as conn:
            streak_row = _get_streak_row(conn, uid)
            unlocked_rows = conn.execute(
                text("SELECT code FROM web_achievements WHERE user_id = :user_id"),
                {"user_id": uid},
            ).mappings().all()
            day_rows = conn.execute(
                text("SELECT DISTINCT day FROM web_activity_log WHERE user_id = :user_id ORDER BY day"),
                {"user_id": uid},
            ).mappings().all()
            module_rows = conn.execute(
                text("SELECT DISTINCT module FROM web_activity_log WHERE user_id = :user_id"),
                {"user_id": uid},
            ).mappings().all()
        unlocked = {r["code"] for r in unlocked_rows}
        active_days = [r["day"] for r in day_rows]
        modules = sorted({r["module"] for r in module_rows})
        achievements = [
            {
                "code": code,
                "icon": a["icon"],
                "name": a["name"],
                "desc": a["desc"],
                "module": a["module"],
                "unlocked": code in unlocked,
            }
            for code, a in ACHIEVEMENTS.items()
        ]
        return jsonify({
            "ok": True,
            "achievements": achievements,
            "unlocked_count": len(unlocked),
            "total_count": len(ACHIEVEMENTS),
            "streak": {
                "current": streak_row["current_streak"] if streak_row else 0,
                "longest": streak_row["longest_streak"] if streak_row else 0,
                "total_days": streak_row["total_active_days"] if streak_row else 0,
            },
            "calendar": active_days,
            "modules": modules,
        })
    except Exception as exc:
        print(f"[ACHIEVEMENTS] list error: {exc}")
        return jsonify({"ok": False, "error": "server error"}), 500


# ── Canon Module ──────────────────────────────────────────────────────────
# Полный текст канона и структурированные данные из core.canon (source of truth).

def _canon_doc_effective() -> str:
    """Текст канона: БД-overlay (canon_doc) или файл canon.md."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT content FROM canon_doc ORDER BY id DESC LIMIT 1")
            ).mappings().first()
            if row:
                return row["content"]
    except Exception as exc:
        print(f"[CANON] doc effective fallback: {exc}")
    return load_canon_text()


@app.route("/canon")
def canon_page():
    canon_text = _canon_doc_effective()
    version = CANON_VERSION
    body_html = render_markdown(canon_text) if canon_text else "<p>Текст канона недоступен.</p>"

    # Произведения: пробуем БД (approved + content + id), фолбэк — статика.
    _db_works: list[dict] = []
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, title, kind, author, date, canon_level, url, content,
                           (audio_data IS NOT NULL) AS has_audio, COALESCE(view_count, 0) AS view_count
                    FROM canon_works WHERE status = 'approved' ORDER BY id
                """),
            ).mappings().all()
            _db_works = [dict(r) for r in rows]
            for w in _db_works:
                w["has_audio"] = bool(w.get("has_audio"))
    except Exception as exc:
        print(f"[CANON] page works db fallback: {exc}")
    if not _db_works:
        _db_works = [
            {
                "id": idx,
                "title": w.title,
                "kind": w.kind,
                "author": w.author,
                "date": w.date,
                "canon_level": w.canon_level,
                "url": w.url,
                "content": "",
                "has_audio": False,
                "view_count": 0,
            }
            for idx, w in enumerate(CANON_WORKS)
        ]
    works_json = json.dumps(_db_works, ensure_ascii=False).replace("</", "<\\/")
    terms_json = json.dumps(
        [
            {"term": t.term, "definition": t.definition, "source": t.source}
            for t in GLOSSARY_TERMS
        ],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Канон — LTHub</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text2); padding: 24px; }}
        .container {{ max-width: 860px; width: 100%; margin: 0 auto; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; color: var(--gh-accent); }}
        .header a {{ color: var(--gh-muted); text-decoration: none; font-size: 14px; }}
        .header a:hover {{ color: var(--gh-accent); }}
        .meta {{ color: var(--gh-muted); font-size: 13px; margin-bottom: 20px; }}
        .tabs {{ display: flex; gap: 4px; border-bottom: 1px solid var(--gh-border); margin-bottom: 24px; flex-wrap: wrap; }}
        .tab {{ padding: 10px 18px; cursor: pointer; color: var(--gh-muted); border-radius: 8px 8px 0 0; font-size: 14px; user-select: none; background: none; border: none; font-family: inherit; }}
        .tab:hover {{ color: var(--gh-text2); background: var(--gh-panel); }}
        .tab.active {{ color: var(--gh-text2); background: var(--gh-border); font-weight: 600; }}
        .panel {{ display: none; }}
        .panel.active {{ display: block; }}
        .canon-body {{ background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 28px; line-height: 1.65; font-size: 15px; overflow-wrap: anywhere; }}
        .canon-body h1, .canon-body h2, .canon-body h3, .canon-body h4 {{ color: var(--gh-accent); margin: 18px 0 8px; }}
        .canon-body h3 {{ font-size: 17px; }}
        .canon-body p {{ margin: 10px 0; }}
        .canon-body ul {{ margin: 8px 0 8px 22px; }}
        .canon-body li {{ margin: 4px 0; }}
        .canon-body blockquote {{ border-left: 3px solid var(--gh-accent); background: var(--gh-bg); padding: 8px 16px; margin: 12px 0; border-radius: 0 8px 8px 0; color: var(--gh-muted); }}
        .canon-body hr {{ border: none; border-top: 1px solid var(--gh-border); margin: 20px 0; }}
        .canon-body a {{ color: var(--gh-accent); text-decoration: none; }}
        .canon-body a:hover {{ text-decoration: underline; }}
        .filters {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }}
        .filters label {{ font-size: 13px; color: var(--gh-muted); }}
        .filters select {{ background: var(--gh-border); color: var(--gh-text2); border: 1px solid var(--gh-border); border-radius: 8px; padding: 6px 10px; font-size: 13px; font-family: inherit; }}
        .works-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        @media (max-width: 620px) {{ .works-grid {{ grid-template-columns: 1fr; }} }}
        .work-card {{ background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 10px; padding: 16px; }}
        .work-card h4 {{ font-size: 15px; color: var(--gh-text2); margin-bottom: 6px; }}
        .work-card .work-meta {{ font-size: 13px; color: var(--gh-muted); }}
        .work-card a {{ color: var(--gh-accent); font-size: 13px; text-decoration: none; }}
        .work-card a:hover {{ text-decoration: underline; }}
        .badge {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; margin-left: 6px; vertical-align: middle; }}
        .badge-high {{ color: var(--gh-accent); background: var(--bb-accent2); }}
        .badge-medium {{ color: var(--gh-warn); background: #3a2f07; }}
        .badge-low {{ color: var(--gh-red); background: #5c0f12; }}
        .badge-archive {{ color: var(--gh-muted); background: var(--gh-border); }}
        .search {{ width: 100%; background: var(--gh-border); color: var(--gh-text2); border: 1px solid var(--gh-border); border-radius: 8px; padding: 10px 14px; font-size: 14px; margin-bottom: 16px; font-family: inherit; }}
        .term {{ background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; }}
        .term h4 {{ color: var(--gh-accent); font-size: 15px; margin-bottom: 4px; }}
        .term p {{ font-size: 14px; color: var(--gh-text); }}
        .term .term-source {{ font-size: 12px; color: var(--gh-muted); margin-top: 6px; }}
        .count {{ color: var(--gh-muted); font-size: 13px; margin-bottom: 12px; }}
        .back-link {{ display: inline-block; color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-top: 24px; }}
        .back-link:hover {{ color: var(--gh-accent); }}
        .action-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }}
        .btn {{ display: inline-block; padding: 8px 16px; border-radius: 8px; font-size: 13px; border: none; cursor: pointer; text-decoration: none; font-family: inherit; }}
        .btn-primary {{ background: var(--gh-accent); color: var(--gh-text2); }}
        .btn-primary:hover {{ background: var(--bb-link); }}
        .btn-secondary {{ background: var(--gh-border); color: var(--gh-text); }}
        .btn-secondary:hover {{ background: var(--gh-border); }}
        .btn-success {{ background: var(--gh-green); color: var(--gh-text2); }}
        .btn-success:hover {{ background: var(--gh-green); }}
        .work-actions {{ margin-top: 10px; }}
        .work-actions a {{ margin-right: 10px; }}
        .empty {{ color: var(--gh-muted); text-align: center; padding: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📖 Канон вселенной Олеговируса и LTL-паразита</h1>
            <a href="/">← На главную</a>
        </div>
        <div class="meta">Версия: {version}</div>
        <div class="action-bar">
            <a class="btn btn-primary" href="/canon/request">📩 Отправить заявку на канонизацию</a>
            <span id="admin-actions"></span>
        </div>
        <div class="tabs">
            <button class="tab active" data-tab="text">📜 Полный текст</button>
            <button class="tab" data-tab="works">🎵 Произведения</button>
            <button class="tab" data-tab="glossary">🧩 Глоссарий</button>
        </div>
        <div class="panel active" id="panel-text">
            <div class="canon-body">{body_html}</div>
        </div>
        <div class="panel" id="panel-works">
            <input class="search" id="works-search" type="text" placeholder="Поиск по названию или автору..." oninput="renderWorks()">
            <div class="filters">
                <label for="level-filter">Уровень:</label>
                <select id="level-filter" onchange="renderWorks()">
                    <option value="all">Все</option>
                    <option value="high">🔵 Высокий</option>
                    <option value="medium">🟡 Средний</option>
                    <option value="low">🔴 Неканон</option>
                    <option value="archive">🗄 Архив</option>
                </select>
                <label for="kind-filter">Тип:</label>
                <select id="kind-filter" onchange="renderWorks()">
                    <option value="all">Все</option>
                    <option value="track">🎵 Треки</option>
                    <option value="article">📜 Статьи</option>
                    <option value="archive">🗄 Архив</option>
                </select>
                <span class="count" id="works-count"></span>
            </div>
            <div class="works-grid" id="works-grid"></div>
        </div>
        <div class="panel" id="panel-glossary">
            <input class="search" id="glossary-search" type="text" placeholder="Поиск по глоссарию..." oninput="renderGlossary(this.value)">
            <div id="glossary-list"></div>
        </div>
        <a class="back-link" href="/">← На главную</a>
    </div>
    <script>
        var LEVEL_LABELS = {{ 'high': ['🔵', 'Высокий', 'badge-high'], 'medium': ['🟡', 'Средний', 'badge-medium'], 'low': ['🔴', 'Неканон', 'badge-low'], 'archive': ['🗄', 'Архив', 'badge-archive'] }};
        var ALL_WORKS = {works_json};
        var ALL_TERMS = {terms_json};

        var tabs = document.querySelectorAll('.tab');
        var panels = {{ 'text': document.getElementById('panel-text'), 'works': document.getElementById('panel-works'), 'glossary': document.getElementById('panel-glossary') }};

        function esc(s) {{ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {{ return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[c]; }}); }}

        function safeUrl(u) {{ try {{ var x = new URL(u, window.location.origin); return (x.protocol === 'http:' || x.protocol === 'https:' || x.protocol === 'tg:') ? x.href : '#'; }} catch(e) {{ return '#'; }} }}
        tabs.forEach(function(t) {{ t.addEventListener('click', function() {{
            tabs.forEach(function(x) {{ x.classList.remove('active'); }});
            Object.keys(panels).forEach(function(k) {{ panels[k].classList.remove('active'); }});
            t.classList.add('active');
            panels[t.dataset.tab].classList.add('active');
            if (t.dataset.tab === 'glossary') {{
                var token = localStorage.getItem('web_token') || '';
                var uid = localStorage.getItem('web_user_id') || '';
                if (token && uid.indexOf('u') === 0) {{
                    fetch('/api/achievements/activity', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json', 'X-Auth-Token': token }},
                        body: JSON.stringify({{ module: 'canon', actions: 0, events: ['canon_terms'] }})
                    }}).catch(function() {{}});
                }}
            }}
        }}); }});

        function renderWorks() {{
            var level = document.getElementById('level-filter').value;
            var kind = document.getElementById('kind-filter').value;
            var q = (document.getElementById('works-search').value || '').toLowerCase().trim();
            var list = ALL_WORKS.filter(function(w) {{
                if (level !== 'all' && w.canon_level !== level) return false;
                if (kind !== 'all' && w.kind !== kind) return false;
                if (q) {{
                    var hay = ((w.title || '') + ' ' + (w.author || '')).toLowerCase();
                    if (hay.indexOf(q) === -1) return false;
                }}
                return true;
            }});
            document.getElementById('works-count').textContent = list.length + ' из ' + ALL_WORKS.length;
            var grid = document.getElementById('works-grid');
            grid.innerHTML = '';
            if (list.length === 0) {{
                grid.innerHTML = '<div class="empty">Ничего не найдено</div>';
                return;
            }}
            list.forEach(function(w) {{
                var meta = [w.author, w.date].filter(Boolean).join(', ');
                var views = (w.view_count || 0) > 0 ? ' · 👁 ' + w.view_count : '';
                var badge = LEVEL_LABELS[w.canon_level] || ['', w.canon_level, ''];
                var link = w.url ? ' <a href="' + safeUrl(w.url) + '" target="_blank" rel="noopener noreferrer">открыть ↗</a>' : '';
                var card = document.createElement('div');
                card.className = 'work-card';
                var readLink = '<a class="btn btn-primary" style="padding:4px 12px;font-size:12px;" href="/canon/work/' + w.id + '">📖 Читать</a>';
                var audioLink = '';
                if (w.kind === 'track' && w.has_audio) {{
                    audioLink = '<a class="btn btn-secondary" style="padding:4px 12px;font-size:12px;" href="/canon/work/' + w.id + '#audio">🎧 Слушать</a>';
                }}
                card.innerHTML = '<h4>' + badge[0] + ' ' + esc(w.title) + '<span class="badge ' + badge[2] + '">' + badge[1] + '</span></h4>' +
                    '<div class="work-meta">' + esc(meta) + views + link + '</div>' +
                    '<div class="work-actions">' + readLink + audioLink + '</div>';
                grid.appendChild(card);
            }});
        }}
        renderWorks();

        function renderGlossary(q) {{
            var query = (q || '').toLowerCase().trim();
            var list = ALL_TERMS.filter(function(t) {{
                if (!query) return true;
                return t.term.toLowerCase().indexOf(query) !== -1 || t.definition.toLowerCase().indexOf(query) !== -1;
            }});
            var container = document.getElementById('glossary-list');
            container.innerHTML = '';
            list.forEach(function(t) {{
                var div = document.createElement('div');
                div.className = 'term';
                div.innerHTML = '<h4>' + esc(t.term) + '</h4><p>' + esc(t.definition) + '</p>' +
                    (t.source ? '<div class="term-source">Источник: ' + esc(t.source) + '</div>' : '');
                container.appendChild(div);
            }});
        }}
        renderGlossary('');

        function loadAdminActions() {{
            var token = localStorage.getItem('web_token');
            if (!token) return;
            fetch('/api/auth/me', {{ headers: {{ 'Authorization': 'Bearer ' + token }} }})
                .then(function(r) {{ return r.json(); }})
                .then(function(u) {{
                    if (u && u.is_admin) {{
                        var box = document.getElementById('admin-actions');
                        box.innerHTML = '<a class="btn btn-secondary" href="/admin/canon">🛠 Модерация и редактирование канона</a>';
                    }}
                }}).catch(function() {{}});
        }}
        loadAdminActions();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/canon/text")
def api_canon_text():
    canon_text = load_canon_text()
    if not canon_text:
        return jsonify({"error": "Текст канона недоступен"}), 404
    return jsonify({"text": canon_text, "version": CANON_VERSION})


@app.route("/api/canon/works")
def api_canon_works():
    level = request.args.get("level", "all")
    kind = request.args.get("kind", "all")

    # Пытаемся читать из БД (approved-произведения, включая content).
    try:
        with get_db_engine().connect() as conn:
            sql = ("SELECT id, title, kind, author, date, canon_level, url, content, "
                   "audio_name, audio_mime, audio_size, COALESCE(view_count, 0) AS view_count, "
                   "(audio_data IS NOT NULL) AS has_audio "
                   "FROM canon_works WHERE status = 'approved'")
            params: dict = {}
            if level != "all":
                sql += " AND canon_level = :level"
                params["level"] = level
            if kind != "all":
                sql += " AND kind = :kind"
                params["kind"] = kind
            sql += " ORDER BY id"
            rows = conn.execute(text(sql), params).mappings().all()
        works = [dict(r) for r in rows]
        for w in works:
            w["has_audio"] = bool(w.get("has_audio"))
        return jsonify({"works": works, "total": len(works)})
    except Exception as exc:
        print(f"[CANON] works db fallback: {exc}")

    # Фолбэк — статический перечень из core.canon (без content).
    works = [
        {
            "id": idx,
            "title": w.title,
            "kind": w.kind,
            "author": w.author,
            "date": w.date,
            "canon_level": w.canon_level,
            "url": w.url,
            "content": "",
            "audio_name": None,
            "audio_mime": None,
            "audio_size": None,
            "view_count": 0,
            "has_audio": False,
        }
        for idx, w in enumerate(CANON_WORKS)
        if (level == "all" or w.canon_level == level)
        and (kind == "all" or w.kind == kind)
    ]
    return jsonify({"works": works, "total": len(works)})


@app.route("/api/canon/work/<int:work_id>")
def api_canon_work_detail(work_id):
    """Полный текст одной канонической работы."""
    try:
        with get_db_engine().begin() as conn:
            row = conn.execute(
                text("""
                    SELECT id, title, kind, author, date, canon_level, url, content, status,
                           audio_name, audio_mime, audio_size,
                           COALESCE(view_count, 0) AS view_count,
                           (audio_data IS NOT NULL) AS has_audio
                    FROM canon_works WHERE id = :wid
                """),
                {"wid": work_id},
            ).mappings().first()
            if row and row["status"] == "approved":
                conn.execute(
                    text("UPDATE canon_works SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :wid"),
                    {"wid": work_id},
                )
        if not row or row["status"] != "approved":
            return jsonify({"error": "Произведение не найдено"}), 404
        detail = dict(row)
        detail["has_audio"] = bool(detail.get("has_audio"))
        return jsonify(detail)
    except Exception as exc:
        print(f"[CANON] work detail error: {exc}")

    # Фолбэк на статику (id совпадает с порядковым номером из core.canon).
    try:
        work = CANON_WORKS[work_id]
    except IndexError:
        return jsonify({"error": "Произведение не найдено"}), 404
    return jsonify({
        "id": work_id,
        "title": work.title,
        "kind": work.kind,
        "author": work.author,
        "date": work.date,
        "canon_level": work.canon_level,
        "url": work.url,
        "content": "",
        "status": "approved",
        "audio_name": None,
        "audio_mime": None,
        "audio_size": None,
        "view_count": 0,
        "has_audio": False,
    })


@app.route("/api/canon/documents")
def api_canon_documents():
    """Эффективный текст канона: БД-overlay (canon_doc) или файл canon.md."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT content, updated_at FROM canon_doc ORDER BY id DESC LIMIT 1")
            ).mappings().first()
        if row:
            return jsonify({
                "text": row["content"],
                "version": CANON_VERSION,
                "source": "db",
                "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
            })
    except Exception as exc:
        print(f"[CANON] doc overlay error: {exc}")
    return jsonify({
        "text": load_canon_text(),
        "version": CANON_VERSION,
        "source": "file",
        "updated_at": None,
    })


@app.route("/api/canon/request", methods=["POST"])
def api_canon_request_submit():
    """Подать заявку на канонизацию (только зарегистрированный пользователь)."""
    user = _get_session_user(_auth_token_from_request())
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    content = (data.get("content") or "").strip()
    canon_level = (data.get("canon_level") or "").strip() or "medium"
    kind = (data.get("kind") or "").strip() or "track"
    url = (data.get("url") or "").strip()
    date = (data.get("date") or "").strip()

    if not title or not author:
        return jsonify({"error": "Укажите название и автора произведения"}), 400
    if len(title) > 200:
        return jsonify({"error": "Название слишком длинное"}), 400
    if len(author) > 100:
        return jsonify({"error": "Автор слишком длинный (макс. 100 символов)"}), 400
    if len(url) > 500:
        return jsonify({"error": "Ссылка слишком длинная (макс. 500 символов)"}), 400
    if not content:
        return jsonify({"error": "Вставьте полный текст произведения"}), 400
    if len(content) > 5000:
        return jsonify({"error": "Текст слишком длинный (макс. 5000 символов)"}), 400
    if canon_level not in ("high", "medium", "low", "archive"):
        return jsonify({"error": "Некорректный уровень канонизации"}), 400
    if kind not in ("track", "article", "archive"):
        return jsonify({"error": "Некорректный тип произведения"}), 400

    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO canon_requests
                        (user_id, title, kind, author, date, canon_level, url, content)
                    VALUES (:uid, :t, :k, :a, :d, :l, :u, :c)
                """),
                {
                    "uid": user.get("id"),
                    "t": title,
                    "k": kind,
                    "a": author,
                    "d": date or None,
                    "l": canon_level,
                    "u": url or None,
                    "c": content,
                },
            )
            conn.commit()
    except Exception as exc:
        print(f"[CANON] request submit error: {exc}")
        return jsonify({"error": "Не удалось отправить заявку"}), 500
    return jsonify({"ok": True})


# ── Admin Canon Moderation ────────────────────────────────────────────────

@app.route("/api/admin/canon/requests")
def api_admin_canon_requests():
    """Список заявок на канонизацию (только админ)."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    status = (request.args.get("status") or "").strip()
    try:
        with get_db_engine().connect() as conn:
            if status:
                rows = conn.execute(
                    text("""
                        SELECT r.*, w.login AS requester
                        FROM canon_requests r
                        LEFT JOIN web_users w ON w.id = r.user_id
                        WHERE r.status = :s
                        ORDER BY r.created_at DESC LIMIT 200
                    """),
                    {"s": status},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text("""
                        SELECT r.*, w.login AS requester
                        FROM canon_requests r
                        LEFT JOIN web_users w ON w.id = r.user_id
                        ORDER BY (r.status = 'pending') DESC, r.created_at DESC LIMIT 200
                    """),
                ).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            for key in ("created_at", "reviewed_at"):
                if d.get(key):
                    d[key] = str(d[key])[:19]
            items.append(d)
        return jsonify({"count": len(items), "items": items})
    except Exception as exc:
        print(f"[CANON] admin requests error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/canon/requests/<int:req_id>/approve", methods=["POST"])
def api_admin_canon_request_approve(req_id):
    """Одобрить заявку → произведение попадает в canon_works (approved)."""
    user = _admin_require()
    if not user:
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM canon_requests WHERE id = :rid AND status = 'pending'"),
                {"rid": req_id},
            ).mappings().first()
            if not row:
                return jsonify({"error": "Заявка не найдена или уже обработана"}), 404
            conn.execute(
                text("""
                    INSERT INTO canon_works (title, kind, author, date, canon_level, url, content, status, submitted_by)
                    VALUES (:t, :k, :a, :d, :l, :u, :c, 'approved', :sb)
                """),
                {
                    "t": row["title"],
                    "k": row["kind"],
                    "a": row["author"],
                    "d": row["date"],
                    "l": row["canon_level"],
                    "u": row["url"],
                    "c": row["content"],
                    "sb": row["user_id"],
                },
            )
            conn.execute(
                text("""
                    UPDATE canon_requests
                    SET status = 'approved', reviewer_id = :rv, review_note = :note, reviewed_at = NOW()
                    WHERE id = :id
                """),
                {"rv": user.get("id"), "note": (data.get("review_note") or "")[:500] or None, "id": req_id},
            )
            conn.commit()
    except Exception as exc:
        print(f"[CANON] approve error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/api/admin/canon/requests/<int:req_id>/reject", methods=["POST"])
def api_admin_canon_request_reject(req_id):
    """Отклонить заявку с комментарием."""
    user = _admin_require()
    if not user:
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    try:
        with get_db_engine().connect() as conn:
            conn.execute(
                text("""
                    UPDATE canon_requests
                    SET status = 'rejected', reviewer_id = :rv, review_note = :note, reviewed_at = NOW()
                    WHERE id = :id AND status = 'pending'
                """),
                {"rv": user.get("id"), "note": (data.get("review_note") or "")[:500] or None, "id": req_id},
            )
            conn.commit()
    except Exception as exc:
        print(f"[CANON] reject error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/api/admin/canon/works/<int:work_id>", methods=["PUT"])
def api_admin_canon_work_update(work_id):
    """Редактирование произведения (метаданные + полный текст)."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title:
        return jsonify({"error": "Название обязательно"}), 400
    if len(title) > 300:
        return jsonify({"error": "Название слишком длинное (макс. 300 символов)"}), 400
    if len(author := (data.get("author") or "").strip()) > 100:
        return jsonify({"error": "Автор слишком длинный (макс. 100 символов)"}), 400
    if len(url := (data.get("url") or "").strip()) > 500:
        return jsonify({"error": "Ссылка слишком длинная (макс. 500 символов)"}), 400
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("""
                    UPDATE canon_works
                    SET title = :t, kind = :k, author = :a, date = :d, canon_level = :l,
                        url = :u, content = :c, updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": work_id,
                    "t": title,
                    "k": (data.get("kind") or "").strip() or "track",
                    "a": author,
                    "d": (data.get("date") or "").strip() or None,
                    "l": (data.get("canon_level") or "").strip() or "medium",
                    "u": url or None,
                    "c": content,
                },
            )
            conn.commit()
            if result.rowcount == 0:
                return jsonify({"error": "Произведение не найдено"}), 404
    except Exception as exc:
        print(f"[CANON] update work error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


# ── Canon Audio (upload / delete / stream) ──────────────────────────────────

_MAX_AUDIO_BYTES = 4 * 1024 * 1024  # ~лимит тела запроса Vercel (4.5MB)
_ALLOWED_AUDIO_MIME = {"audio/mpeg", "audio/mp3", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac"}


def _canon_audio_mime(filename: str) -> str | None:
    """Guess audio MIME by extension; None for unsupported files."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return {
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "oga": "audio/ogg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
    }.get(ext)


@app.route("/api/admin/canon/works/<int:work_id>/audio", methods=["POST"])
def api_admin_canon_work_audio_upload(work_id):
    """Загрузка аудиофайла для трека (multipart/form-data, только админ)."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    upload = request.files.get("audio") or request.files.get("file")
    if not upload:
        return jsonify({"error": "Файл не передан (поле audio)"}), 400
    filename = (upload.filename or "").strip()
    mime = _canon_audio_mime(filename) or (upload.mimetype or "")
    if mime not in _ALLOWED_AUDIO_MIME:
        return jsonify({"error": "Недопустимый формат аудио (mp3/ogg/wav/m4a/aac)"}), 400
    data = upload.read()
    if not data:
        return jsonify({"error": "Пустой файл"}), 400
    if len(data) > _MAX_AUDIO_BYTES:
        return jsonify({"error": "Файл слишком большой (макс. 4 МБ)"}), 400
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("""
                    UPDATE canon_works
                    SET audio_data = :a, audio_name = :n, audio_mime = :m, audio_size = :s, updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "a": data,
                    "n": filename[:255] or "audio",
                    "m": mime,
                    "s": len(data),
                    "id": work_id,
                },
            )
            conn.commit()
            if result.rowcount == 0:
                return jsonify({"error": "Произведение не найдено"}), 404
    except Exception as exc:
        print(f"[CANON] audio upload error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True, "audio_name": filename[:255] or "audio", "audio_mime": mime, "audio_size": len(data)})


@app.route("/api/admin/canon/works/<int:work_id>/audio", methods=["DELETE"])
def api_admin_canon_work_audio_delete(work_id):
    """Удаление аудиофайла трека (только админ)."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("""
                    UPDATE canon_works
                    SET audio_data = NULL, audio_name = NULL, audio_mime = NULL, audio_size = NULL, updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": work_id},
            )
            conn.commit()
            if result.rowcount == 0:
                return jsonify({"error": "Произведение не найдено"}), 404
    except Exception as exc:
        print(f"[CANON] audio delete error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/api/canon/work/<int:work_id>/audio")
def api_canon_work_audio(work_id):
    """Потоковая отдача аудиофайла трека."""
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT audio_data, audio_mime, audio_name, status
                    FROM canon_works WHERE id = :wid
                """),
                {"wid": work_id},
            ).mappings().first()
    except Exception as exc:
        print(f"[CANON] audio stream error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    if not row or row["status"] != "approved" or not row["audio_data"]:
        return jsonify({"error": "Аудио не найдено"}), 404
    mime = row["audio_mime"] or "audio/mpeg"
    name = row["audio_name"] or "audio"
    return (row["audio_data"], 200, {
        "Content-Type": mime,
        "Content-Disposition": f'inline; filename="{_html_escape(name)}"',
        "Cache-Control": "public, max-age=86400",
    })


@app.route("/api/admin/canon/works", methods=["GET"])
def api_admin_canon_works_list():
    """Список всех произведений (включая pending/rejected) для редактора."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, title, kind, author, date, canon_level, url, status
                    FROM canon_works ORDER BY id
                """),
            ).mappings().all()
        return jsonify({"count": len(rows), "items": [dict(r) for r in rows]})
    except Exception as exc:
        print(f"[CANON] admin works list error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500


@app.route("/api/admin/canon/doc", methods=["GET"])
def api_admin_canon_doc_get():
    """Текущий текст канона для редактирования admin-ом."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            row = conn.execute(
                text("SELECT content FROM canon_doc ORDER BY id DESC LIMIT 1")
            ).mappings().first()
        content = row["content"] if row else load_canon_text()
        return jsonify({"content": content, "source": "db" if row else "file"})
    except Exception as exc:
        print(f"[CANON] admin doc get error: {exc}")
        return jsonify({"content": load_canon_text(), "source": "file"})


@app.route("/api/admin/canon/doc", methods=["PUT"])
def api_admin_canon_doc_put():
    """Сохранить административную правку текста канона (БД-overlay)."""
    user = _admin_require()
    if not user:
        return jsonify({"error": "Нет доступа"}), 403
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "Контент пуст"}), 400
    if len(content) > 60000:
        return jsonify({"error": "Текст слишком длинный"}), 400
    try:
        with get_db_engine().connect() as conn:
            existing = conn.execute(text("SELECT id FROM canon_doc ORDER BY id DESC LIMIT 1")).mappings().first()
            if existing:
                conn.execute(
                    text("UPDATE canon_doc SET content = :c, updated_by = :u, updated_at = NOW() WHERE id = :id"),
                    {"c": content, "u": user.get("id"), "id": existing["id"]},
                )
            else:
                conn.execute(
                    text("INSERT INTO canon_doc (content, updated_by) VALUES (:c, :u)"),
                    {"c": content, "u": user.get("id")},
                )
            conn.commit()
    except Exception as exc:
        print(f"[CANON] admin doc put error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/api/admin/canon/doc", methods=["DELETE"])
def api_admin_canon_doc_delete():
    """Сбросить overlay — каноном снова становится файл canon.md."""
    if not _admin_require():
        return jsonify({"error": "Нет доступа"}), 403
    try:
        with get_db_engine().connect() as conn:
            conn.execute(text("DELETE FROM canon_doc"))
            conn.commit()
    except Exception as exc:
        print(f"[CANON] admin doc delete error: {exc}")
        return jsonify({"error": "Ошибка сервера"}), 500
    return jsonify({"ok": True})


@app.route("/api/canon/glossary")
def api_canon_glossary():
    query = (request.args.get("q") or "").lower().strip()
    terms = [
        {"term": t.term, "definition": t.definition, "source": t.source}
        for t in GLOSSARY_TERMS
        if not query or query in t.term.lower() or query in t.definition.lower()
    ]
    return jsonify({"terms": terms, "total": len(terms)})


@app.route("/api/canon/search")
def api_canon_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": [], "total": 0})
    results = find_canon(query, limit=5)
    return jsonify({"results": results, "total": len(results)})


# ── Canon Work Page ──────────────────────────────────────────────────────

@app.route("/canon/work/<int:work_id>")
def canon_work_page(work_id):
    """Страница с полным текстом одного канонического произведения."""
    try:
        with get_db_engine().begin() as conn:
            row = conn.execute(
                text("""
                    SELECT id, title, kind, author, date, canon_level, url, content, status,
                           audio_name, audio_mime, audio_size, COALESCE(view_count, 0) AS view_count
                    FROM canon_works WHERE id = :wid
                """),
                {"wid": work_id},
            ).mappings().first()
            if row and row["status"] == "approved":
                conn.execute(
                    text("UPDATE canon_works SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :wid"),
                    {"wid": work_id},
                )
    except Exception as exc:
        print(f"[CANON] work page db error: {exc}")
        row = None

    if not row or row["status"] != "approved":
        # Фолбэк на статику.
        try:
            w = CANON_WORKS[work_id]
        except IndexError:
            return "Произведение не найдено", 404
        work = {
            "id": work_id,
            "title": w.title,
            "kind": w.kind,
            "author": w.author,
            "date": w.date,
            "canon_level": w.canon_level,
            "url": w.url,
            "content": "",
            "audio_name": None,
            "audio_mime": None,
            "audio_size": None,
            "view_count": 0,
        }
    else:
        work = dict(row)
        work["has_audio"] = True if work.get("audio_size") or work.get("audio_name") else False
    has_audio = bool(work.get("has_audio")) and work["kind"] == "track"

    level_label = {
        "high": ("🔵", "Высокий канон"),
        "medium": ("🟡", "Средний канон"),
        "low": ("🔴", "Неканон"),
        "archive": ("🗄", "Архив"),
    }.get(work["canon_level"], ("", work["canon_level"]))
    kind_label = {
        "track": "🎵 Трек",
        "article": "📜 Статья",
        "archive": "🗄 Архив",
    }.get(work["kind"], work["kind"])
    content_html = render_markdown(work["content"]) if work["content"] else (
        "<p><em>Текст произведения пока не добавлен. "
        "Ссылка на оригинал открывается ниже, если доступна.</em></p>"
    )
    audio_html = ""
    if has_audio:
        audio_html = f"""
        <div class="audio-card" id="audio">
            <h3>🎧 Аудиозапись трека</h3>
            <audio controls preload="metadata" src="/api/canon/work/{work['id']}/audio"></audio>
            <div class="audio-meta">{_html_escape(work.get('audio_name') or 'audio')} · {format_bytes(work.get('audio_size') or 0)}</div>
        </div>"""
    meta = [work["author"], work["date"]]
    meta = " · ".join(x for x in meta if x)

    # Следующее/предыдущее произведение.
    nav_html = ""
    try:
        with get_db_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT id, title FROM canon_works WHERE status = 'approved' ORDER BY id")
            ).mappings().all()
        ids = [r["id"] for r in rows]
    except Exception:
        ids = list(range(len(CANON_WORKS)))
    if work_id in ids:
        idx = ids.index(work_id)
        prev_id = ids[idx - 1] if idx > 0 else None
        next_id = ids[idx + 1] if idx + 1 < len(ids) else None
        if prev_id is not None:
            nav_html += f'<a class="btn btn-secondary" href="/canon/work/{prev_id}">← Назад</a> '
        nav_html += '<a class="btn btn-secondary" href="/canon">← К списку</a> '
        if next_id is not None:
            nav_html += f'<a class="btn btn-secondary" href="/canon/work/{next_id}">Вперёд →</a>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_html_escape(work['title'])} — Канон — LTHub</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text2); padding: 24px; }}
        .container {{ max-width: 860px; width: 100%; margin: 0 auto; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
        .header h1 {{ font-size: 24px; color: var(--gh-accent); }}
        .header a {{ color: var(--gh-muted); text-decoration: none; font-size: 14px; }}
        .header a:hover {{ color: var(--gh-accent); }}
        .badge {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; }}
        .badge-high {{ color: var(--gh-accent); background: var(--bb-accent2); }}
        .badge-medium {{ color: var(--gh-warn); background: #3a2f07; }}
        .badge-low {{ color: var(--gh-red); background: #5c0f12; }}
        .badge-archive {{ color: var(--gh-muted); background: var(--gh-border); }}
        .meta {{ color: var(--gh-muted); font-size: 14px; margin-bottom: 24px; }}
        .content {{ background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 28px; line-height: 1.7; font-size: 15px; overflow-wrap: anywhere; white-space: pre-wrap; }}
        .content p {{ margin: 8px 0; }}
        .audio-card {{ background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
        .audio-card h3 {{ color: var(--gh-text2); font-size: 16px; margin-bottom: 12px; }}
        .audio-card audio {{ width: 100%; }}
        .audio-card .audio-meta {{ color: var(--gh-muted); font-size: 12px; margin-top: 10px; }}
        .section-title {{ color: var(--gh-accent); font-size: 15px; margin: 24px 0 8px; }}
        .source-link {{ display: inline-block; margin-top: 20px; color: var(--gh-accent); text-decoration: none; font-size: 14px; }}
        .source-link:hover {{ text-decoration: underline; }}
        .nav {{ margin-top: 24px; display: flex; gap: 8px; flex-wrap: wrap; }}
        .back-link {{ display: inline-block; color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-top: 24px; }}
        .back-link:hover {{ color: var(--gh-accent); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📖 {_html_escape(work['title'])}</h1>
            <a href="/canon">← Канон</a>
        </div>
        <div class="meta">
            {kind_label} · {meta or 'Автор неизвестен'}
            <span class="badge badge-{work['canon_level']}">{level_label[1]}</span>
            {('<span style="color:var(--gh-muted);">👁 ' + str(work.get('view_count') or 0) + '</span>') if (work.get('view_count') or 0) > 0 else ''}
        </div>
        {audio_html}
        {('<div class="section-title">📜 Текст</div>' if work['kind'] == 'article' and not has_audio else '')}
        <div class="content">{content_html}</div>
{"<a class='source-link' href='" + _html_escape(work['url']) + "' target='_blank' rel='noopener noreferrer'>↗ Открыть оригинал в Telegram</a>" if work.get("url") else ""}
        <div class="nav">{nav_html}</div>
    </div>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ── Canon Request Page ───────────────────────────────────────────────────

@app.route("/canon/request")
def canon_request_page():
    """Форма заявки на канонизацию (требуется авторизация)."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Заявка на канонизацию — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text2); padding: 24px; }
        .container { max-width: 760px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--gh-accent); }
        .header a { color: var(--gh-muted); text-decoration: none; font-size: 14px; }
        .field { margin-bottom: 16px; }
        .field label { display: block; color: var(--gh-muted); font-size: 13px; margin-bottom: 6px; }
        .field input, .field select, .field textarea {
            width: 100%; padding: 12px; border: 1px solid var(--gh-border); border-radius: 8px;
            background: var(--gh-panel); color: var(--gh-text2); font-size: 15px; font-family: inherit; box-sizing: border-box;
        }
        .field textarea { min-height: 200px; resize: vertical; }
        .field input:focus, .field textarea:focus, .field select:focus { outline: none; border-color: var(--gh-accent); }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; background: var(--gh-green); color: var(--gh-text2); font-size: 15px; font-family: inherit; cursor: pointer; }
        .btn:hover { background: var(--gh-green); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .msg { margin-top: 12px; font-size: 14px; }
        .msg.error { color: var(--gh-red); }
        .msg.ok { color: var(--bb-green); }
        .hint { color: var(--gh-muted); font-size: 12px; margin-top: 4px; }
        .login-required { background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 24px; text-align: center; }
        .login-required a { color: var(--gh-accent); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📩 Заявка на канонизацию</h1>
            <a href="/canon">← Канон</a>
        </div>
        <div id="guest">
            <div class="login-required">
                <p>Чтобы отправить заявку, войдите в аккаунт.</p>
                <p style="margin-top:12px;"><a href="/login">Войти</a> · <a href="/register">Зарегистрироваться</a></p>
            </div>
        </div>
        <form id="req-form" style="display:none;">
            <div class="row">
                <div class="field">
                    <label for="f-title">Название произведения *</label>
                    <input id="f-title" maxlength="200" placeholder="Например: Тень агента (V.2)">
                </div>
                <div class="field">
                    <label for="f-author">Автор (участник/ник) *</label>
                    <input id="f-author" placeholder="LucasTeam, Рома, Олег...">
                </div>
            </div>
            <div class="row">
                <div class="field">
                    <label for="f-kind">Тип</label>
                    <select id="f-kind">
                        <option value="track">🎵 Трек</option>
                        <option value="article">📜 Статья</option>
                        <option value="archive">🗄 Архив</option>
                    </select>
                </div>
                <div class="field">
                    <label for="f-level">Предлагаемый уровень</label>
                    <select id="f-level">
                        <option value="high">🔵 Высокий</option>
                        <option value="medium" selected>🟡 Средний</option>
                        <option value="low">🔴 Низкий (неканон)</option>
                        <option value="archive">🗄 Архив</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div class="field">
                    <label for="f-date">Дата</label>
                    <input id="f-date" placeholder="напр. 24.04.2026">
                </div>
                <div class="field">
                    <label for="f-url">Ссылка (t.me)</label>
                    <input id="f-url" placeholder="https://t.me/lucasteamgroup/...">
                </div>
            </div>
            <div class="field">
                <label for="f-content">Полный текст *</label>
                <textarea id="f-content" maxlength="5000" placeholder="Вставьте текст трека или статьи..."></textarea>
                <div class="hint">Максимум 5000 символов. Текст должен соответствовать правилам канона (Блок 1).</div>
            </div>
            <button class="btn" id="send-btn" type="button" onclick="sendRequest()">📩 Отправить заявку</button>
            <div class="msg" id="req-msg"></div>
        </form>
    </div>
    <script>
        (function() {
            var token = localStorage.getItem('web_token');
            if (token) {
                document.getElementById('req-form').style.display = 'block';
                document.getElementById('guest').style.display = 'none';
            }
        })();
        function sendRequest() {
            var token = localStorage.getItem('web_token');
            if (!token) { document.getElementById('req-msg').className = 'msg error'; document.getElementById('req-msg').textContent = 'Не авторизован — войдите.'; return; }
            var data = {
                title: document.getElementById('f-title').value.trim(),
                author: document.getElementById('f-author').value.trim(),
                kind: document.getElementById('f-kind').value,
                canon_level: document.getElementById('f-level').value,
                date: document.getElementById('f-date').value.trim(),
                url: document.getElementById('f-url').value.trim(),
                content: document.getElementById('f-content').value.trim()
            };
            var btn = document.getElementById('send-btn');
            btn.disabled = true;
            fetch('/api/canon/request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                body: JSON.stringify(data)
            }).then(function(r) { return r.json().then(function(j) { return {ok: r.ok, j: j}; }); })
              .then(function(r) {
                var msg = document.getElementById('req-msg');
                msg.className = r.ok ? 'msg ok' : 'msg error';
                msg.textContent = r.ok ? '✅ Заявка отправлена! Администратор рассмотрит её.' : (r.j.error || 'Ошибка');
                if (r.ok) { document.getElementById('req-form').reset(); }
                btn.disabled = false;
              }).catch(function() { var msg = document.getElementById('req-msg'); msg.className = 'msg error'; msg.textContent = 'Ошибка сети'; btn.disabled = false; });
        }
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# ── Admin Canon Page ─────────────────────────────────────────────────────

@app.route("/admin/canon")
def admin_canon_page():
    """Панель модерации заявок и редактирования канона (доступ — через API)."""
    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Модерация канона — LTHub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--gh-bg); min-height: 100vh; color: var(--gh-text); padding: 20px; }
        .container { max-width: 1000px; width: 100%; margin: 0 auto; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; color: var(--gh-accent); }
        .header a { color: var(--gh-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 10px 16px; border: 1px solid var(--gh-border); border-radius: 10px; background: var(--gh-panel); color: var(--gh-muted); font-size: 14px; font-family: inherit; cursor: pointer; }
        .tab:hover { border-color: var(--gh-accent); color: var(--gh-text); }
        .tab.active { background: var(--gh-accent); border-color: var(--gh-accent); color: var(--gh-text2); }
        .panel { display: none; }
        .panel.active { display: block; }
        .card { background: var(--gh-panel); border: 1px solid var(--gh-border); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
        .card h3 { color: var(--gh-text2); margin-bottom: 8px; }
        .meta { color: var(--gh-muted); font-size: 13px; margin-bottom: 8px; }
        .content-preview { background: var(--gh-bg); border: 1px solid var(--gh-border); border-radius: 8px; padding: 12px; font-size: 13px; white-space: pre-wrap; max-height: 140px; overflow-y: auto; margin-bottom: 12px; }
        .btn { padding: 8px 16px; border: none; border-radius: 8px; font-size: 13px; font-family: inherit; cursor: pointer; margin-right: 8px; }
        .btn-success { background: var(--gh-green); color: var(--gh-text2); }
        .btn-danger { background: var(--gh-red); color: var(--gh-text2); }
        .btn-secondary { background: var(--gh-border); color: var(--gh-text); }
        textarea, input, select { width: 100%; padding: 10px; border: 1px solid var(--gh-border); border-radius: 8px; background: var(--gh-bg); color: var(--gh-text); font-size: 14px; font-family: inherit; box-sizing: border-box; margin-bottom: 10px; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; }
        .badge-pending { background: var(--bb-elev); color: var(--gh-warn); border: 1px solid var(--bb-border); }
        .badge-approved { background: var(--bb-elev); color: var(--bb-green); border: 1px solid var(--bb-border); }
        .badge-rejected { background: var(--bb-elev); color: var(--gh-red); border: 1px solid var(--bb-border); }
        .msg { color: var(--bb-green); margin-top: 8px; }
        .msg.error { color: var(--gh-red); }
        .empty { color: var(--gh-muted); text-align: center; padding: 24px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛠 Модерация канона</h1>
            <a href="/canon">← Канон</a>
        </div>
        <div class="tabs">
            <button class="tab active" data-tab="requests">📩 Заявки</button>
            <button class="tab" data-tab="works">📚 Произведения</button>
            <button class="tab" data-tab="doc">📄 Документ канона</button>
        </div>
        <div class="panel active" id="panel-requests">
            <div class="card" id="requests-list"><div class="empty">Загрузка...</div></div>
        </div>
        <div class="panel" id="panel-works">
            <div class="card" id="works-list"><div class="empty">Загрузка...</div></div>
        </div>
        <div class="panel" id="panel-doc">
            <div class="card">
                <h3>Текст канона (перезаписывает файл canon.md)</h3>
                <textarea id="doc-content" rows="20"></textarea>
                <button class="btn btn-success" onclick="saveDoc()">Сохранить</button>
                <button class="btn btn-danger" onclick="resetDoc()">Сбросить к файлу</button>
                <div class="msg" id="doc-msg"></div>
            </div>
        </div>
    </div>
    <script>
        var TOKEN = localStorage.getItem('web_token');
        function authH() { return { 'Authorization': 'Bearer ' + (TOKEN || ''), 'Content-Type': 'application/json' }; }

        var tabs = document.querySelectorAll('.tab');
        var panels = { 'requests': document.getElementById('panel-requests'), 'works': document.getElementById('panel-works'), 'doc': document.getElementById('panel-doc') };
        tabs.forEach(function(t) { t.addEventListener('click', function() {
            tabs.forEach(function(x) { x.classList.remove('active'); });
            Object.keys(panels).forEach(function(k) { panels[k].classList.remove('active'); });
            t.classList.add('active'); panels[t.dataset.tab].classList.add('active');
        }); });

        function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function(c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

        function loadRequests() {
            fetch('/api/admin/canon/requests', { headers: authH() }).then(function(r) { return r.json(); }).then(function(d) {
                var box = document.getElementById('requests-list');
                if (d.error) { box.innerHTML = '<div class="empty" style="color:var(--gh-red)">Нет доступа: ' + esc(d.error) + '</div>'; return; }
                if (!d.items || !d.items.length) { box.innerHTML = '<div class="empty">Заявок нет.</div>'; return; }
                box.innerHTML = '';
                d.items.forEach(function(rr) {
                    var div = document.createElement('div');
                    div.className = 'card';
                    div.innerHTML = '<div class="meta">#' + rr.id + ' · ' + esc(rr.requester || '?') + ' · ' +
                        '<span class="badge badge-' + rr.status + '">' + rr.status + '</span></div>' +
                        '<h3>' + esc(rr.title) + '</h3>' +
                        '<div class="meta">' + esc(rr.author || '') + ' · ' + esc(rr.canon_level || '') + ' · ' + esc(rr.kind || '') + '</div>' +
                        '<div class="content-preview">' + esc(rr.content || '').substring(0, 600) + '</div>' +
                        (rr.url ? '<div class="meta">🔗 ' + esc(rr.url) + '</div>' : '') +
                        (rr.review_note ? '<div class="meta">📝 ' + esc(rr.review_note) + '</div>' : '') +
                        (rr.status === 'pending' ?
                            '<button class="btn btn-success" onclick="decide(' + rr.id + ", 'approve'" + ')">✅ Одобрить</button>' +
                            '<button class="btn btn-danger" onclick="decide(' + rr.id + ", 'reject'" + ')">❌ Отклонить</button>' : '');
                    box.appendChild(div);
                });
            });
        }

        function decide(id, action) {
            fetch('/api/admin/canon/requests/' + id + '/' + action, { method: 'POST', headers: authH(), body: '{}' })
              .then(function(r) { return r.json(); }).then(function(j) {
                if (j.error) { alert(j.error); } else { loadRequests(); }
              });
        }

        function loadWorks() {
            fetch('/api/admin/canon/works', { headers: authH() }).then(function(r) { return r.json(); }).then(function(d) {
                var box = document.getElementById('works-list');
                if (d.error) { box.innerHTML = '<div class="empty" style="color:var(--gh-red)">Нет доступа: ' + esc(d.error) + '</div>'; return; }
                if (!d.items || !d.items.length) { box.innerHTML = '<div class="empty">Нет произведений.</div>'; return; }
                box.innerHTML = '';
                d.items.forEach(function(w) {
                    var div = document.createElement('div');
                    div.className = 'card';
                    div.id = 'work-' + w.id;
                    div.innerHTML = '<h3>' + esc(w.title) + ' <span class="badge badge-' + w.status + '">' + w.status + '</span></h3>' +
                        '<div class="meta">' + esc(w.author || '') + ' · ' + esc(w.canon_level || '') + ' · ' + esc(w.kind || '') + '</div>' +
                        '<button class="btn btn-secondary" onclick="editWork(' + w.id + ')">✏️ Редактировать</button>' +
                        '<button class="btn btn-secondary" onclick="viewWork(' + w.id + ')">👁 Посмотреть</button>';
                    box.appendChild(div);
                });
            });
        }

        function viewWork(id) { window.open('/canon/work/' + id, '_blank'); }

        function editWork(id) {
            var div = document.getElementById('work-' + id);
            fetch('/api/canon/work/' + id, { headers: authH() }).then(function(r) { return r.json(); }).then(function(w) {
                var audioHtml = '';
                if (w.kind === 'track') {
                    audioHtml = '<div class="card" style="margin-top:10px;padding:10px;border:1px solid var(--gh-border);border-radius:8px;">' +
                        '<strong>🎧 Аудио трека</strong>' +
                        (w.has_audio ? ' <span class="badge badge-approved" style="margin-left:6px;">загружено: ' + esc(w.audio_name || '') + '</span>' : '') +
                        '<div style="margin-top:8px;">' +
                        '<input type="file" id="we-audio-file" accept="audio/*"> ' +
                        '<button class="btn btn-success" onclick="uploadAudio(' + id + ')">⬆️ Загрузить</button> ' +
                        (w.has_audio ? '<button class="btn btn-danger" onclick="removeAudio(' + id + ')">🗑 Удалить</button>' : '') +
                        '</div></div>';
                }
                div.innerHTML = '<h3>✏️ ' + esc(w.title) + '</h3>' +
                    '<label>Название</label><input id="we-title" value="' + esc(w.title) + '">' +
                    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">' +
                    '<div><label>Автор</label><input id="we-author" value="' + esc(w.author || '') + '"></div>' +
                    '<div><label>Уровень</label><select id="we-level"><option value="high"' + (w.canon_level=='high'?' selected':'') + '>Высокий</option><option value="medium"' + (w.canon_level=='medium'?' selected':'') + '>Средний</option><option value="low"' + (w.canon_level=='low'?' selected':'') + '>Неканон</option><option value="archive"' + (w.canon_level=='archive'?' selected':'') + '>Архив</option></select></div>' +
                    '</div>' +
                    '<label>Тип</label><select id="we-kind"><option value="track"' + (w.kind=='track'?' selected':'') + '>Трек</option><option value="article"' + (w.kind=='article'?' selected':'') + '>Статья</option><option value="archive"' + (w.kind=='archive'?' selected':'') + '>Архив</option></select>' +
                    '<label>Дата</label><input id="we-date" value="' + esc(w.date || '') + '">' +
                    '<label>Ссылка</label><input id="we-url" value="' + esc(w.url || '') + '">' +
                    '<label>Полный текст</label><textarea id="we-content" rows="10">' + esc(w.content || '') + '</textarea>' +
                    audioHtml +
                    '<button class="btn btn-success" onclick="saveWork(' + id + ')">💾 Сохранить</button>' +
                    '<button class="btn btn-secondary" onclick="loadWorks()">Отмена</button>' +
                    '<div class="msg" id="work-msg"></div>';
            });
        }

        function uploadAudio(id) {
            var fileInput = document.getElementById('we-audio-file');
            var file = fileInput && fileInput.files && fileInput.files[0];
            if (!file) { alert('Выберите файл'); return; }
            var fd = new FormData();
            fd.append('audio', file);
            fetch('/api/admin/canon/works/' + id + '/audio', { method: 'POST', headers: { 'Authorization': 'Bearer ' + (TOKEN || '') }, body: fd })
              .then(function(r) { return r.json(); }).then(function(j) {
                  var msg = document.getElementById('work-msg');
                  if (j.ok) { msg.textContent = '✅ Аудио загружено'; loadWorks(); } else { msg.textContent = j.error || 'Ошибка'; msg.className = 'msg error'; }
              });
        }

        function removeAudio(id) {
            if (!confirm('Удалить аудио трека?')) return;
            fetch('/api/admin/canon/works/' + id + '/audio', { method: 'DELETE', headers: authH() })
              .then(function(r) { return r.json(); }).then(function(j) {
                  var msg = document.getElementById('work-msg');
                  if (j.ok) { msg.textContent = '✅ Аудио удалено'; loadWorks(); } else { msg.textContent = j.error || 'Ошибка'; msg.className = 'msg error'; }
              });
        }

        function saveWork(id) {
            var payload = { title: document.getElementById('we-title').value, author: document.getElementById('we-author').value,
                canon_level: document.getElementById('we-level').value, kind: document.getElementById('we-kind').value,
                date: document.getElementById('we-date').value, url: document.getElementById('we-url').value,
                content: document.getElementById('we-content').value };
            fetch('/api/admin/canon/works/' + id, { method: 'PUT', headers: authH(), body: JSON.stringify(payload) })
              .then(function(r) { return r.json(); }).then(function(j) {
                  var msg = document.getElementById('work-msg');
                  if (j.ok) { msg.textContent = '✅ Сохранено'; loadWorks(); } else { msg.textContent = j.error || 'Ошибка'; msg.className = 'msg error'; }
              });
        }

        function saveDoc() {
            var content = document.getElementById('doc-content').value;
            fetch('/api/admin/canon/doc', { method: 'PUT', headers: authH(), body: JSON.stringify({ content: content }) })
              .then(function(r) { return r.json(); }).then(function(j) {
                  var msg = document.getElementById('doc-msg'); msg.className = j.ok ? 'msg' : 'msg error';
                  msg.textContent = j.ok ? '✅ Сохранено' : (j.error || 'Ошибка');
              });
        }

        function resetDoc() {
            if (!confirm('Сбросить правку текста канона к файлу canon.md?')) return;
            fetch('/api/admin/canon/doc', { method: 'DELETE', headers: authH() }).then(function(r) { return r.json(); }).then(function(j) {
                if (j.ok) { loadDoc(); } else { alert(j.error || 'Ошибка'); }
            });
        }

        function loadDoc() {
            fetch('/api/admin/canon/doc', { headers: authH() }).then(function(r) { return r.json(); }).then(function(d) {
                if (d.error) { alert('Нет доступа: ' + d.error); return; }
                document.getElementById('doc-content').value = d.content || '';
            });
        }

        loadRequests(); loadWorks(); loadDoc();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


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
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bb-bg); min-height: 100vh; color: var(--bb-text); padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { max-width: 700px; width: 100%; }
        .header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; color: var(--bb-accent); }
        .header a { color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-left: auto; }
        .card { background: var(--bb-panel); border: 1px solid var(--bb-primary); border-radius: 16px; padding: 24px; margin-bottom: 16px; }
        .card h2 { font-size: 18px; margin-bottom: 16px; }
        .role-card { display: block; padding: 20px; cursor: pointer; text-align: center; }
        .role-card:hover { border-color: var(--bb-accent); }
        .role-card .icon { font-size: 48px; margin-bottom: 8px; }
        .role-card .label { font-size: 18px; font-weight: 600; }
        .role-card .desc { font-size: 14px; color: var(--bb-muted); margin-top: 4px; }
        label { display: block; font-size: 14px; color: var(--bb-muted); margin-bottom: 4px; margin-top: 14px; }
        label:first-of-type { margin-top: 0; }
        input, textarea, select { width: 100%; padding: 12px; background: var(--bb-primary); border: 1px solid var(--bb-link); border-radius: 8px; font-size: 15px; color: var(--bb-text); font-family: inherit; }
        input:focus, textarea:focus { outline: none; border-color: var(--bb-accent); }
        textarea { min-height: 60px; resize: vertical; }
        .radio-group { display: flex; gap: 16px; margin-top: 4px; }
        .radio-group label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: var(--bb-text); cursor: pointer; margin: 0; }
        .btn { display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; font-family: inherit; transition: background 0.15s; }
        .btn-primary { background: var(--bb-accent); color: white; }
        .btn-primary:hover { background: var(--bb-accent2); }
        .btn-secondary { background: var(--bb-primary); color: var(--bb-text); }
        .btn-secondary:hover { background: var(--bb-link); }
        .btn-full { width: 100%; justify-content: center; margin-top: 16px; }
        .btn-sm { padding: 8px 16px; font-size: 13px; }
        .verbs-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        .verbs-table th { text-align: left; padding: 10px 12px; font-size: 13px; color: var(--bb-muted); border-bottom: 1px solid var(--bb-primary); text-transform: uppercase; letter-spacing: 0.5px; }
        .verbs-table td { padding: 10px 12px; border-bottom: 1px solid var(--bb-primary); font-size: 15px; }
        .verbs-table input { background: transparent; border: none; border-bottom: 2px solid var(--bb-link); padding: 4px 0; font-size: 15px; color: var(--bb-text); width: 100%; border-radius: 0; }
        .verbs-table input:focus { border-bottom-color: var(--bb-accent); outline: none; }
        .verbs-table .filled { color: var(--gh-green); font-weight: 600; }
        .verbs-table .correct { color: var(--gh-green); }
        .verbs-table .wrong { color: var(--bb-accent); }
        .result-summary { text-align: center; padding: 20px; }
        .result-summary .score { font-size: 36px; color: var(--bb-accent); font-weight: bold; }
        .result-summary .label { font-size: 14px; color: var(--bb-muted); margin-top: 4px; }
        .back-link { display: inline-block; color: var(--bb-muted); text-decoration: none; font-size: 14px; margin-top: 16px; cursor: pointer; }
        .back-link:hover { color: var(--bb-accent); }
        .hidden { display: none; }
        .share-link { background: var(--bb-primary); border-radius: 8px; padding: 12px; font-size: 14px; word-break: break-all; margin-top: 12px; display: flex; align-items: center; gap: 8px; }
        .share-link code { color: var(--gh-green); flex: 1; }
        .btn-copy { padding: 6px 12px; background: var(--bb-accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; white-space: nowrap; }
        .btn-copy:hover { background: var(--bb-accent2); }
        .btn-copy.copied { background: var(--gh-green); }
        .ex-list { display: flex; flex-direction: column; gap: 10px; }
        .ex-item { display: flex; justify-content: space-between; align-items: center; padding: 14px; background: var(--bb-primary); border-radius: 8px; cursor: pointer; }
        .ex-item:hover { background: var(--bb-link); }
        .ex-item .ex-id { font-weight: 600; color: var(--bb-accent); }
        .ex-item .ex-meta { font-size: 13px; color: var(--bb-muted); }
        .student-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--bb-primary); }
        .student-row:last-child { border: none; }
        .student-name { font-weight: 600; }
        .student-score { color: var(--gh-green); }
        .error-text { color: var(--bb-accent); text-align: center; padding: 20px; }
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
            var USER_ID = localStorage.getItem('web_user_id');
            if (!USER_ID) { USER_ID = 'web_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10); localStorage.setItem('web_user_id', USER_ID); }
            var studentName = localStorage.getItem('verbs_name') || '';
            var content = document.getElementById('content');

            var token = localStorage.getItem('web_token');
            var uid = localStorage.getItem('web_user_id');
            if (token && (!studentName || !localStorage.getItem('verbs_name_from_profile'))) {
                fetch('/api/auth/me', {headers: {'X-Auth-Token': token}})
                    .then(function(r) { return r.json(); })
                    .then(function(p) {
                        if (!p.error && p.display_name) {
                            studentName = p.display_name;
                            localStorage.setItem('verbs_name', p.display_name);
                            localStorage.setItem('verbs_name_from_profile', '1');
                        }
                    })
                    .catch(function() {});
            }

            function render(html) { content.innerHTML = html; }

            function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function(c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

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

            function showRegNotice() {
                try {
                    if (sessionStorage.getItem('reg_notice_shown')) return;
                    sessionStorage.setItem('reg_notice_shown', '1');
                    var re = document.getElementById('hub-reg-notice');
                    if (!re) {
                        re = document.createElement('div');
                        re.id = 'hub-reg-notice';
                        re.style.cssText = 'position:fixed;top:70px;right:20px;z-index:100000;background:var(--bb-bg);border:1px solid var(--gh-warn);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;';
                        re.innerHTML = '📝 Зарегистрируйтесь, чтобы сохранить прогресс <a href="/account" style="color:var(--gh-warn);font-weight:700;">Зарегистрироваться</a><button onclick="this.parentNode.remove()" style="float:right;cursor:pointer;border:none;background:none;color:#aaa;font-size:16px;line-height:1;">✕</button>';
                        document.body.appendChild(re);
                    }
                    clearTimeout(re._t);
                    re._t = setTimeout(function() { re.style.display = 'none'; }, 6000);
                } catch(e) {}
            }
            function hubTrack(module, actions) {
                actions = actions || 1;
                var token = localStorage.getItem('web_token') || '';
                var uid = localStorage.getItem('web_user_id') || '';
                try {
                    if (token && uid.indexOf('u') === 0) {
                        fetch('/api/achievements/activity', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
                            body: JSON.stringify({ module: module, actions: actions })
                        }).then(function(r) { return r.json(); }).then(function(d) {
                            if (d && d.unlocked_detail && d.unlocked_detail.length) {
                                var names = d.unlocked_detail.map(function(a) { return a.icon + ' ' + a.name; });
                                var pe = document.getElementById('hub-popup');
                                if (!pe) {
                                    pe = document.createElement('div');
                                    pe.id = 'hub-popup';
                                    pe.style.cssText = 'position:fixed;top:20px;right:20px;z-index:100000;background:var(--gh-green-panel);border:1px solid var(--gh-green);color:var(--gh-text2);padding:12px 16px;border-radius:12px;font-size:14px;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:320px;display:none;';
                                    document.body.appendChild(pe);
                                }
                                pe.innerHTML = '🏆 ' + names.join('<br>');
                                pe.style.display = 'block';
                                clearTimeout(pe._t);
                                pe._t = setTimeout(function() { pe.style.display = 'none'; }, 5000);
                            }
                        }).catch(function() {});
                    } else {
                        showRegNotice();
                        var today = new Date();
                        var dayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
                        var acts = {};
                        try { acts = JSON.parse(localStorage.getItem('hub_activity') || '{}'); } catch(e) { acts = {}; }
                        acts[dayStr] = (acts[dayStr] || 0) + 1;
                        localStorage.setItem('hub_activity', JSON.stringify(acts));
                    }
                } catch(e) {}
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
                    xhr.timeout = 30000;
                    xhr.ontimeout = function() { render('<div class="card error-text">\\u0421\\u0435\\u0440\\u0432\\u0435\\u0440 \\u043d\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u0438\\u043b. \\u041f\\u043e\\u043f\\u0440\\u043e\\u0431\\u0443\\u0439\\u0442\\u0435 \\u0435\\u0449\\u0451.</div><button class="back-link" onclick="app.createExercise()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); };
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+esc(r.error)+'</div><button class="back-link" onclick="app.createExercise()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            // show preview with tasks
                            var h = '<div class="card"><h2>\\ud83d\\udccb \\u041f\\u0440\\u0435\\u0434\\u043f\\u0440\\u043e\\u0441\\u043c\\u043e\\u0442\\u0440</h2>';
                            h += '<p style="color:#888;font-size:13px;margin-bottom:8px">\\u041f\\u0440\\u0430\\u0432\\u0438\\u043b\\u044c\\u043d\\u044b\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u044b (\\u043f\\u0440\\u043e\\u0432\\u0435\\u0440\\u044c\\u0442\\u0435 AI):</p>';
                            h += '<table class="verbs-table preview-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            (r.tasks || []).forEach(function(t) {
                                h += '<tr><td>'+esc(t.inf||'')+'</td><td>'+esc(t.past||'')+'</td><td>'+esc(t.pp||'')+'</td></tr>';
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
                        '<p style="margin:12px 0;color:#888">ID: <strong style="color:var(--bb-accent)">'+exId+'</strong></p>' +
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
                    xhr.timeout = 20000;
                    xhr.ontimeout = function() { render('<div class="card error-text">\\u0421\\u0435\\u0440\\u0432\\u0435\\u0440 \\u043d\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u0438\\u043b.</div>'); };
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
                    xhr.timeout = 20000;
                    xhr.ontimeout = function() { render('<div class="card error-text">\\u0421\\u0435\\u0440\\u0432\\u0435\\u0440 \\u043d\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u0438\\u043b.</div><button class="back-link" onclick="app.myExercises()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); };
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+esc(r.error)+'</div><button class="back-link" onclick="app.myExercises()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            var h = '<div class="card"><h2>\\u0417\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 #'+esc(exId)+'</h2>';
                            if (!r.submissions || !r.submissions.length) { h += '<p style="color:#888">\\u041f\\u043e\\u043a\\u0430 \\u043d\\u0435\\u0442 \\u0440\\u0435\\u0448\\u0435\\u043d\\u0438\\u0439.</p>'; }
                            else {
                                r.submissions.forEach(function(s) {
                                    h += '<div class="student-row"><span class="student-name">'+esc(s.name)+'</span><span class="student-score">'+esc(s.score)+'/'+esc(s.total)+'</span></div>';
                                    s.errors.forEach(function(e) {
                                        h += '<div style="font-size:13px;color:var(--bb-accent);padding:2px 0 2px 20px;">\\u2716 '+esc(e)+'</div>';
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
                    xhr.timeout = 20000;
                    xhr.ontimeout = function() { render('<div class="card error-text">\\u0421\\u0435\\u0440\\u0432\\u0435\\u0440 \\u043d\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u0438\\u043b.</div><button class="back-link" onclick="app.studentEnterId()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); };
                    xhr.onload = function() {
                        try {
                            var ex = JSON.parse(xhr.responseText);
                            if (ex.error) { render('<div class="card error-text">'+esc(ex.error)+'</div><button class="back-link" onclick="app.studentEnterId()">\\u2190 \\u041d\\u0430\\u0437\\u0430\\u0434</button>'); return; }
                            var h = '<div class="card"><h2>\\u0417\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435 #'+esc(ex.id)+'</h2><table class="verbs-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            ex.tasks.forEach(function(t, i) {
                                h += '<tr><td>'+(t.inf ? '<span class="filled">'+esc(t.inf)+'</span>' : '<input id="i'+i+'i" placeholder="..." data-idx="'+i+'" data-field="inf">')+'</td>';
                                h += '<td>'+(t.past ? '<span class="filled">'+esc(t.past)+'</span>' : '<input id="i'+i+'p" placeholder="..." data-idx="'+i+'" data-field="past">')+'</td>';
                                h += '<td>'+(t.pp ? '<span class="filled">'+esc(t.pp)+'</span>' : '<input id="i'+i+'pp" placeholder="..." data-idx="'+i+'" data-field="pp">')+'</td></tr>';
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
                    xhr.timeout = 20000;
                    xhr.ontimeout = function() { render('<div class="card error-text">\\u0421\\u0435\\u0440\\u0432\\u0435\\u0440 \\u043d\\u0435 \\u043e\\u0442\\u0432\\u0435\\u0442\\u0438\\u043b.</div>'); };
                    xhr.onload = function() {
                        try {
                            var r = JSON.parse(xhr.responseText);
                            if (r.error) { render('<div class="card error-text">'+esc(r.error)+'</div>'); return; }
                            var h = '<div class="card"><div class="result-summary"><div class="score">'+esc(r.score)+'/'+esc(r.total)+'</div><div class="label">\\u043f\\u0440\\u0430\\u0432\\u0438\\u043b\\u044c\\u043d\\u044b\\u0445</div></div></div>';
                            h += '<div class="card"><table class="verbs-table"><tr><th>Infinitive</th><th>Past Simple</th><th>Past Participle</th></tr>';
                            r.details.forEach(function(d) {
                                h += '<tr><td class="'+(d.inf_correct?'correct':'wrong')+'">'+esc(d.inf||'')+'</td><td class="'+(d.past_correct?'correct':'wrong')+'">'+esc(d.past||'')+'</td><td class="'+(d.pp_correct?'correct':'wrong')+'">'+esc(d.pp||'')+'</td></tr>';
                            });
                            h += '</table></div><button class="btn btn-primary btn-full" onclick="app.studentEnterId()">\\ud83d\\udccb \\u041d\\u043e\\u0432\\u043e\\u0435 \\u0437\\u0430\\u0434\\u0430\\u043d\\u0438\\u0435</button>';
                            render(h);
                            hubTrack('verbs', 1);
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
        VERB_GEN_LOCK.pop(uid, None)
        return jsonify({"error": "AI не смог сгенерировать задание. Проверьте глаголы и попробуйте ещё раз."}), 503
    ex_id = random.randint(100000, 999999)
    while _load_verb_exercise(ex_id) is not None:
        ex_id = random.randint(100000, 999999)
    try:
        ex_data = {"id": ex_id, "teacher_id": uid, "verbs": verbs, "task_count": count, "mode": mode, "wishes": wishes, "tasks": tasks}
        _save_verb_exercise(ex_data)
    except Exception as exc:
        VERB_GEN_LOCK.pop(uid, None)
        print(f"[VERBS] save exercise error: {exc}")
        return jsonify({"error": "Не удалось сохранить задание. Попробуйте ещё раз."}), 500
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

        reply_msg_id = (reply_to or {}).get("message_id")
        reply_from = (reply_to or {}).get("from", {}) or {}

        if reply_to and is_parsing_trigger:
            replied_text = reply_to.get("text") or reply_to.get("caption", "")

            # Security: only parse messages coming from a bot (game bot), not from a user.
            # Prevents awarding coins to an arbitrary profile by replying to a user message.
            if not reply_from.get("is_bot"):
                _record_parsing_result(
                    user_id, "not_bot", 0, 0, "unknown", replied_text or "", False,
                    chat_id=chat_id, message_id=reply_msg_id,
                )
                send_telegram_message(
                    chat_id,
                    "❌ Парсинг доступен только в ответ на сообщение игрового бота (GD Cards, Гуся Cards, Shmalala, Чайометр, BunkerRP).",
                )
                return jsonify({"ok": True})

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

                recorded = _record_parsing_result(
                    target_user_id, game, amount, coins, parsed.get("type", "balance"), replied_text, True,
                    chat_id=chat_id, message_id=reply_msg_id,
                )
                if not recorded:
                    send_telegram_message(chat_id, "ℹ️ Это сообщение уже было распарсено ранее.")
                    return jsonify({"ok": True})

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
                _record_parsing_result(
                    user_id, "unknown", 0, 0, "unknown", replied_text or "", False,
                    chat_id=chat_id, message_id=reply_msg_id,
                )
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
            
            import asyncio
            question = asyncio.run(trivia_questions.generate_trivia_question())
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
                            "🎯 **Викторина по канону** отправлена!\nОтветьте на опрос выше. Правильный ответ даст +10 монет.",
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
                "⚠️ Для ответа нажмите на кнопку с вариантом ниже. Правильный ответ даст +10 монет.",
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
                "`/chess_link DrNykterstein`\n\n"
                f"[🌐 Веб-версия шахмат](https://bank-bot-ruby.vercel.app/chess?user_id={user_id})"
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
                                "Теперь можно использовать шахматные команды LTHub.\n\n"
                                f"[🌐 Открыть веб-версию](https://bank-bot-ruby.vercel.app/chess?user_id={user_id})"
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
                # Check cooldown (max 1 puzzle per day)
                remaining = _puzzle_cooldown_remaining_hours(user_id)
                if remaining is not None:
                    send_telegram_message(
                        chat_id,
                        f"⏳ Пожалуйста, подождите {remaining:.1f} ч. до следующей задачи.",
                    )
                    return jsonify({"ok": True})
                
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
                                if i >= initial_ply + 1:
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
                        "created_at": time.time(),
                    }
                    
                    board_image_url = f"https://lichess1.org/export/fen.gif?fen={fen.replace(' ', '_')}&theme=brown&piece=cburnett"
                    
                    turn = "Белых" if (initial_ply + 1) % 2 == 0 else "Чёрных"
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
            if time.time() - pending.get("created_at", 0) > 1800:
                _PENDING_PUZZLES.pop(user_id, None)
                send_telegram_message(chat_id, "⏰ Задача устарела. Загрузите новую: /puzzle")
                return jsonify({"ok": True})
            solution = pending["solution"]
            # Handle both string and list formats
            if isinstance(solution, list):
                solution_moves = solution
            else:
                solution_moves = solution.split()
            
            if solution_moves and user_move == solution_moves[0].lower():
                # Correct move — award coins
                _PENDING_PUZZLES.pop(user_id, None)
                update_user_coins(user_id, 5, datetime.utcnow())
                send_telegram_message(
                    chat_id,
                    f"✅ **Правильно!**\n\nХод: `{solution_moves[0]}`\n💰 +5 монет",
                    parse_mode="Markdown",
                )
            else:
                # Wrong move — show correct solution
                correct = solution_moves[0] if solution_moves else "?"
                _PENDING_PUZZLES.pop(user_id, None)
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
                    prayer = _prayer_for_day(user_id, today)
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
                    f"🙏 Молитва на сегодня:\n\n_{prayer}_",
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
        canon_content = load_canon_text()[:5000]
        
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


# Lazy DB/BOT_ID init: get_db_engine() creates tables on first call;
# _load_bot_id() is called on demand in the webhook handler.

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

        def _fallback_segments(src_text: str) -> list | None:
            """Deterministic fallback: split endings of long Russian words."""
            endings_pool = (
                "ами", "ями", "ого", "его", "ому", "ему", "ими", "ыми",
                "ая", "ое", "ые", "ий", "ый", "ой", "ее", "ие",
                "ым", "ом", "ах", "ях", "ев", "ов", "ам", "ям",
                "у", "ю", "ы", "и", "а", "я", "о", "е",
            )
            tokens = re.split(r'(\s+)', src_text)
            segments = []
            buf = ""
            blanks = 0
            for tok in tokens:
                if not re.search(r'[А-Яа-яЁё]', tok):
                    buf += tok
                    continue
                m = re.match(r'^([^А-Яа-яЁё]*)([А-Яа-яЁё]{5,})([^А-Яа-яЁё]*)$', tok)
                if not m:
                    buf += tok
                    continue
                pre, word, post = m.groups()
                split = None
                for end in endings_pool:
                    if word.endswith(end) and len(word) - len(end) >= 3:
                        split = (word[:-len(end)], end)
                        break
                if not split:
                    buf += tok
                    continue
                stem, ending = split
                if buf or pre:
                    segments.append(["t", buf + pre])
                segments.append(["b", stem, ending])
                blanks += 1
                buf = post
            if buf:
                segments.append(["t", buf])
            return segments if blanks >= 2 else None

        def _parse_endings_json(raw: str) -> list | None:
            cleaned = raw.strip()
            if not cleaned:
                return None
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            try:
                data = json.loads(cleaned)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    segs = data.get("segments", [])
                    return segs if isinstance(segs, list) else None
                return None
            except json.JSONDecodeError:
                pass
            for pat in [r'\[.*\{.*"[tb]".*\}\]', r'\{.*"segments"\s*:\s*\[.*\]\}']:
                m = re.search(pat, cleaned, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group())
                        if isinstance(data, list):
                            return data
                        if isinstance(data, dict):
                            return data.get("segments", [])
                        return None
                    except json.JSONDecodeError:
                        pass
            return None

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

        def _normalize_segments(segs: list) -> list | None:
            if not segs:
                return None
            filtered = []
            for seg in segs:
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
            if sum(1 for s in filtered if s[0] == 'b') < 2:
                return None
            return filtered

        ai_filtered = _normalize_segments(_parse_endings_json(ai_text))

        if ai_filtered:
            return jsonify({"ok": True, "segments": ai_filtered, "original": text})

        # AI unavailable or returned unusable data -> deterministic fallback
        if not ai_text or not ai_text.strip():
            print("[ENDINGS] AI вернул пустой ответ")
        elif ai_text.startswith("❌"):
            print(f"[ENDINGS] AI недоступен: {ai_text}")
        else:
            print("[ENDINGS] Не удалось получить корректные сегменты от AI")

        fallback = _fallback_segments(text)
        if fallback:
            return jsonify({
                "ok": True,
                "segments": fallback,
                "original": text,
                "fallback": True,
                "notice": "AI временно недоступен — упражнение создано автоматически.",
            })

        return jsonify({"ok": False, "error": "Не удалось создать упражнение. Попробуйте другой текст или повторите ещё раз."})

    except Exception as e:
        print(f"[ENDINGS] Error: {e}")
        return jsonify({"ok": False, "error": "Внутренняя ошибка при создании упражнения. Попробуйте ещё раз."})


# ── Family Circle (медиация) ──────────────────────────────────────

def _family_cipher():
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _family_encrypt(value: str) -> str:
    cipher = _family_cipher()
    if cipher is None:
        return value
    return cipher.encrypt(value.encode()).decode()


def _family_decrypt(token: str) -> str:
    cipher = _family_cipher()
    if cipher is None:
        return token
    try:
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        return token


def _family_hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()


def _family_check_password(password: str, stored: str) -> bool:
    if not stored or ":" not in stored:
        return False
    salt, hsh = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == hsh


def _family_gen_room_id() -> str:
    engine = get_db_engine()
    while True:
        rid = str(random.randint(100000, 999999))
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id FROM rooms WHERE id = :rid"), {"rid": rid}).fetchone()
        if not row:
            return rid


def _family_gen_password(length: int = 5) -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(length))


def _family_create_room(name: str, creator_name: str) -> dict:
    engine = get_db_engine()
    rid = _family_gen_room_id()
    creator_display = (creator_name or "").strip() or "Я"
    raw_password = _family_gen_password()
    member_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO rooms (id, name, created_at, status, participants_total, spoke_count) "
            "VALUES (:id, :name, :ts, 'active', 1, 0)"
        ), {"id": rid, "name": name, "ts": datetime.now(timezone.utc)})
        conn.execute(text(
            "INSERT INTO members (id, room_id, display_name, password_hash, finished, created_at) "
            "VALUES (:id, :rid, :name, :hash, FALSE, :ts)"
        ), {"id": member_id, "rid": rid, "name": creator_display, "hash": _family_hash_password(raw_password),
            "ts": datetime.now(timezone.utc)})
    members = [m for m in _family_room_members(rid)]
    return {
        "room_id": rid,
        "your_name": creator_display,
        "your_password": raw_password,
        "invite_link": f"/family/room?room_id={rid}",
        "members": members,
    }


def _family_join_room(room_id: str, member_name: str) -> dict:
    engine = get_db_engine()
    name = (member_name or "").strip()
    if not name:
        raise ValueError("Укажите имя участника")
    with engine.connect() as conn:
        room = conn.execute(text("SELECT id FROM rooms WHERE id = :rid"), {"rid": room_id}).fetchone()
    if not room:
        raise ValueError("Комната не найдена")
    existing = _family_member_by_name(room_id, name)
    if existing:
        return {"ok": True, "your_password": None, "is_new": False}
    raw_password = _family_gen_password()
    member_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO members (id, room_id, display_name, password_hash, finished, created_at) "
            "VALUES (:id, :rid, :name, :hash, FALSE, :ts)"
        ), {"id": member_id, "rid": room_id, "name": name, "hash": _family_hash_password(raw_password),
            "ts": datetime.now(timezone.utc)})
        conn.execute(text(
            "UPDATE rooms SET participants_total = participants_total + 1 WHERE id = :rid"
        ), {"rid": room_id})
    return {"ok": True, "your_password": raw_password, "is_new": True}


def _family_get_room(room_id: str) -> dict | None:
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, name, status, participants_total, spoke_count FROM rooms WHERE id = :rid"
        ), {"rid": room_id}).mappings().first()
    if not row:
        return None
    return dict(row)


def _family_room_members(room_id: str) -> list[str]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT display_name FROM members WHERE room_id = :rid ORDER BY created_at"
        ), {"rid": room_id}).scalars().all()
    return list(rows)


def _family_member_by_name(room_id: str, name: str) -> dict | None:
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id, display_name, password_hash, finished FROM members "
            "WHERE room_id = :rid AND display_name = :name"
        ), {"rid": room_id, "name": name}).mappings().first()
    return dict(row) if row else None


def _family_verify_member(room_id: str, name: str, password: str) -> dict | None:
    member = _family_member_by_name(room_id, name)
    if not member:
        return None
    if not _family_check_password(password, member["password_hash"]):
        return None
    return member


def _family_room_messages(room_id: str) -> list[dict]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT m.content, m.response, mem.display_name FROM messages m "
            "JOIN members mem ON mem.id = m.member_id "
            "WHERE mem.room_id = :rid ORDER BY m.created_at"
        ), {"rid": room_id}).mappings().all()
    result = []
    for r in rows:
        result.append({
            "content": _family_decrypt(r["content"]),
            "response": _family_decrypt(r["response"]) if r["response"] else None,
            "member_name": r["display_name"],
        })
    return result


def _family_create_message(member_id: str, content: str, response: str | None,
                           intent_type: str | None, needs_extracted: list | None) -> None:
    engine = get_db_engine()
    msg_id = str(uuid.uuid4())
    needs_str = None
    if needs_extracted:
        needs_str = _family_encrypt(json.dumps(needs_extracted, ensure_ascii=False))
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO messages (id, member_id, content, response, intent_type, needs_extracted, created_at) "
            "VALUES (:id, :mid, :content, :response, :intent, :needs, :ts)"
        ), {
            "id": msg_id,
            "mid": member_id,
            "content": _family_encrypt(content),
            "response": _family_encrypt(response) if response else None,
            "intent": intent_type,
            "needs": needs_str,
            "ts": datetime.now(timezone.utc),
        })


def _family_add_need(room_id: str, need_text: str, member_id: str | None = None) -> None:
    engine = get_db_engine()
    need_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO needs (id, room_id, need_text, member_id, created_at) "
            "VALUES (:id, :rid, :text, :mid, :ts)"
        ), {"id": need_id, "rid": room_id, "text": need_text, "mid": member_id,
            "ts": datetime.now(timezone.utc)})


def _family_room_needs_text(room_id: str) -> str:
    engine = get_db_engine()
    with engine.connect() as conn:
        needs = conn.execute(text(
            "SELECT need_text FROM needs WHERE room_id = :rid ORDER BY created_at"
        ), {"rid": room_id}).scalars().all()
    if not needs:
        return "Пока нет зафиксированных потребностей."
    return "\n".join(f"- {n}" for n in needs)


def _family_finish_member(member: dict) -> None:
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE members SET finished = TRUE WHERE id = :id"), {"id": member["id"]})


def _family_count_spoken(room_id: str) -> int:
    engine = get_db_engine()
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT COUNT(*) FROM members WHERE room_id = :rid AND finished"
        ), {"rid": room_id}).scalar() or 0


def _family_save_report(room_id: str, report_text: str) -> None:
    engine = get_db_engine()
    report_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO final_reports (id, room_id, report_text, created_at) "
            "VALUES (:id, :rid, :text, :ts)"
        ), {"id": report_id, "rid": room_id, "text": report_text,
            "ts": datetime.now(timezone.utc)})


def _family_get_report(room_id: str) -> str | None:
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT report_text FROM final_reports WHERE room_id = :rid ORDER BY created_at DESC LIMIT 1"
        ), {"rid": room_id}).mappings().first()
    return row["report_text"] if row else None


def _family_build_system_prompt(room_name: str, member_names: list[str], spoke_count: int, needs_map: str) -> str:
    if spoke_count < 2:
        advice_rule = "Запрещено давать советы «скажи другому» или «поговори с ним/ней». Фокус только на переживаниях и потребностях самого участника."
        micro_step_allowed = "запрещено"
    else:
        advice_rule = "Советы допустимы, но с оговоркой: «Это только предварительная мысль — у меня нет полной картины, пока другие участники не высказались»."
        micro_step_allowed = "разрешено"
    participants_list = "\n".join(f"- {n}" for n in member_names)
    return f"""Ты — профессиональный семейный медиатор. Твоя задача — вести приватный диалог с одним участником конфликта. Ты не судья, не адвокат, а нейтральный помощник.

## Контекст
Комната: {room_name}
Участники:
{participants_list}

## Правила диалога
1. Проявляй эмпатию, признавай чувства собеседника.
2. Не оценивай, кто прав, кто виноват.
3. Помогай сформулировать мысли без обвинений в адрес других участников.
4. Если слышишь обвинения («он всегда...», «она никогда...», «они не понимают...») — мягко трансформируй их в потребности. Например: «Я слышу, что тебе важно быть услышанным» или «Похоже, для тебя ценна предсказуемость».
5. Делай паузы и уточняй: «Правильно ли я понимаю, что...», «Что для тебя самое важное в этой ситуации?»
6. При запросе на конкретное действие — предложи микро-шаг, который участник может сделать сам (не через другого человека).

## Ограничения
- {advice_rule}
- Не придумывай факты, не упоминай имена других участников без необходимости.
- Никаких диагнозов и профессиональных психологических терминов.

## Структура ответа
1. Краткое признание чувств/ситуации (1-2 предложения).
2. Если нужно — уточняющий вопрос или переформулирование.
3. Если участник просит совет — микро-шаг (только если {micro_step_allowed}).
4. **Обязательно в конце** добавь JSON-блок с классификацией:
{{"intent_type": "emotion" | "action" | "analysis"}}
- emotion: участник делится чувствами, переживаниями
- action: участник просит совета, хочет что-то сделать
- analysis: участник анализирует ситуацию, ищет причину

## Потребности комнаты
Уже выявленные потребности (анонимно):
{needs_map}

Если заметишь новую потребность — мягко добавь её в общую карту, сформулировав как позитивную ценность."""


def _family_build_synthesis_prompt(needs_map: str) -> str:
    return f"""Ты — профессиональный семейный медиатор. Твоя задача — на основе анонимного списка потребностей участников конфликта составить структурированный отчёт, который поможет семье найти общий язык.

## Входные данные
Список потребностей (каждая потребность — это сформулированная ценность, а не претензия):
{needs_map}

## Формат отчёта (строго соблюдай разделы)

### 1. Общая картина конфликта
- Опиши ключевые темы, которые волнуют участников (без имён, без обвинений).
- Укажи, какие сферы жизни затронуты (быт, финансы, воспитание, общение и т.д.).

### 2. Общие ценности (что объединяет)
- Выдели 2-4 ценности, которые прослеживаются у всех или большинства участников.
- Примеры: забота, стабильность, уважение, честность, предсказуемость.
- Покажи, что у участников больше общего, чем кажется.

### 3. Конкретные шаги
- 3-5 практических действий, которые семья может обсудить и внедрить.
- Каждый шаг должен быть конкретным: «раз в неделю собираться за ужином», «вести общий календарь», «установить время тишины».
- Шаги должны учитывать потребности из списка.

### 4. Рекомендации по диалогу
- 2-3 примера фраз, которые помогут начать сложный разговор без обвинений.
- Например: «Я чувствую себя одиноко, когда мы не ужинаем вместе. Можем попробовать хотя бы по воскресеньям?»

## Стиль
- Тёплый, поддерживающий, без осуждения.
- На русском языке, простыми словами.
- Без психологических ярлыков."""


def _family_chat_dialog(system_prompt: str, user_message: str, history: list[dict] | None) -> tuple[str, str | None]:
    parts = [system_prompt]
    if history:
        for h in history:
            parts.append(f"{h['role']}: {h['content']}")
    parts.append(user_message)
    full_prompt = "\n\n".join(parts)
    ai_text = call_ai_api(full_prompt, max_tokens=1024)
    if ai_text.startswith("❌"):
        return "AI временно недоступен. Пожалуйста, попробуйте ещё раз через несколько минут.", None

    intent_type = None
    json_match = re.search(r'\{("intent_type"\s*:\s*"[^"]+")\}', ai_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads("{" + json_match.group(1) + "}")
            intent_type = parsed.get("intent_type")
        except json.JSONDecodeError:
            pass
        ai_text = re.sub(r'\s*\{("intent_type"\s*:\s*"[^"]+")\}\s*$', '', ai_text).strip()
    return ai_text, intent_type


def _family_generate_synthesis(system_prompt: str) -> str:
    ai_text = call_ai_api(system_prompt + "\n\nСгенерируй финальный отчёт на основе данных выше.", max_tokens=1024)
    if ai_text.startswith("❌"):
        return "Не удалось сгенерировать отчёт. Попробуйте позже."
    return ai_text


def _family_extract_needs(response_text: str) -> list[str]:
    needs = []
    lower = response_text.lower()
    patterns = [
        r'(?:тебе\s+)?важно\s+(.+)',
        r'(?:похоже|кажется|вижу),?\s+(?:что\s+)?(?:для\s+)?(?:тебя|тебе)\s+(.+?)(?:[.?!]|$)',
        r'(?:ценность|потребность|ценно)\s+(?:—\s+)?(.+?)(?:[.?!]|$)',
    ]
    for pattern in patterns:
        for m in re.findall(pattern, lower):
            need = m.strip().rstrip(".,!?")
            if len(need) > 10 and need not in needs:
                needs.append(need)
    return needs


# ── Family Circle: API ────────────────────────────────────────────

@app.route("/api/family/rooms", methods=["POST"])
def api_family_rooms_create():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    creator_name = (data.get("creator_name") or "").strip()
    if not name:
        return jsonify({"error": "Укажите название комнаты"}), 400
    try:
        result = _family_create_room(name, creator_name)
        return jsonify(result)
    except Exception as exc:
        print(f"[FAMILY] create room error: {exc}")
        return jsonify({"error": "Ошибка при создании комнаты"}), 500


@app.route("/api/family/rooms/join", methods=["POST"])
def api_family_rooms_join():
    data = request.get_json() or {}
    room_id = (data.get("room_id") or "").strip()
    member_name = (data.get("member_name") or "").strip()
    try:
        result = _family_join_room(room_id, member_name)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as exc:
        print(f"[FAMILY] join room error: {exc}")
        return jsonify({"error": "Ошибка при входе в комнату"}), 500


@app.route("/api/family/rooms/<room_id>", methods=["GET"])
def api_family_rooms_get(room_id):
    room = _family_get_room(room_id)
    if not room:
        return jsonify({"error": "Комната не найдена"}), 404
    room["members"] = _family_room_members(room_id)
    return jsonify(room)


@app.route("/api/family/rooms/<room_id>", methods=["DELETE"])
def api_family_rooms_delete(room_id):
    data = request.get_json(silent=True) or {}
    member_name = (data.get("member_name") or "").strip()
    password = (data.get("password") or "").strip()
    member = _family_verify_member(room_id, member_name, password)
    if not member:
        return jsonify({"error": "Неверное имя участника или пароль"}), 403
    engine = get_db_engine()
    with engine.connect() as conn:
        creator = conn.execute(
            text("SELECT id FROM members WHERE room_id = :rid ORDER BY created_at ASC LIMIT 1"),
            {"rid": room_id},
        ).fetchone()
    if not creator or creator["id"] != member["id"]:
        return jsonify({"error": "Удалить комнату может только её создатель"}), 403
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM rooms WHERE id = :rid"), {"rid": room_id})
    if result.rowcount == 0:
        return jsonify({"error": "Комната не найдена"}), 404
    return jsonify({"ok": True})


@app.route("/api/family/chat/send", methods=["POST"])
def api_family_chat_send():
    data = request.get_json() or {}
    room_id = (data.get("room_id") or "").strip()
    member_name = (data.get("member_name") or "").strip()
    password = (data.get("password") or "").strip()
    message = (data.get("message") or "").strip()

    member = _family_verify_member(room_id, member_name, password)
    if not member:
        return jsonify({"error": "Неверное имя участника или пароль"}), 403
    if member["finished"]:
        return jsonify({"error": "Вы уже завершили диалог"}), 400

    room = _family_get_room(room_id)
    if not room or room["status"] != "active":
        return jsonify({"error": "Комната недоступна"}), 400

    needs_text = _family_room_needs_text(room_id)
    member_names = _family_room_members(room_id)
    system_prompt = _family_build_system_prompt(room["name"], member_names, room["spoke_count"], needs_text)

    history = []
    for msg in _family_room_messages(room_id):
        history.append({"role": "user", "content": f"{msg['member_name']}: {msg['content']}"})
        if msg["response"]:
            history.append({"role": "assistant", "content": msg["response"]})

    current_message = f"{member_name}: {message}"
    response_text, intent_type = _family_chat_dialog(system_prompt, current_message, history)

    needs_found = _family_extract_needs(response_text)
    for need_text in needs_found:
        _family_add_need(room_id, need_text, member["id"])

    _family_create_message(
        member["id"], message,
        response=response_text,
        intent_type=intent_type,
        needs_extracted=[{"need": n} for n in needs_found] if needs_found else None,
    )

    return jsonify({"response": response_text, "intent_type": intent_type})


@app.route("/api/family/chat/finish", methods=["POST"])
def api_family_chat_finish():
    data = request.get_json() or {}
    room_id = (data.get("room_id") or "").strip()
    member_name = (data.get("member_name") or "").strip()
    password = (data.get("password") or "").strip()

    member = _family_verify_member(room_id, member_name, password)
    if not member:
        return jsonify({"error": "Неверное имя участника или пароль"}), 403
    if member["finished"]:
        return jsonify({"error": "Вы уже завершили диалог"}), 400

    _family_finish_member(member)
    room = _family_get_room(room_id)
    if room:
        new_count = _family_count_spoken(room_id)
        with get_db_engine().begin() as conn:
            conn.execute(text("UPDATE rooms SET spoke_count = :c WHERE id = :rid"), {"c": new_count, "rid": room_id})
    return jsonify({"ok": True})


@app.route("/api/family/report/generate", methods=["POST"])
def api_family_report_generate():
    data = request.get_json() or {}
    room_id = (data.get("room_id") or "").strip()
    member_name = (data.get("member_name") or "").strip()
    password = (data.get("password") or "").strip()

    member = _family_verify_member(room_id, member_name, password)
    if not member:
        return jsonify({"error": "Неверное имя участника или пароль"}), 403

    room = _family_get_room(room_id)
    if not room or room["status"] != "active":
        return jsonify({"error": "Комната недоступна"}), 400

    existing = _family_get_report(room_id)
    if existing:
        return jsonify({"report_text": existing})

    needs_text = _family_room_needs_text(room_id)
    prompt = _family_build_synthesis_prompt(needs_text)
    report_text = _family_generate_synthesis(prompt)

    _family_save_report(room_id, report_text)
    return jsonify({"report_text": report_text})


# ── Family Circle: страницы ───────────────────────────────────────

_FAMILY_STYLE = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, -apple-system, Arial, sans-serif; background: var(--bb-bg); color: var(--bb-text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; }
.container { max-width: 640px; width: 100%; padding: 24px 16px; }
h1 { font-size: 28px; color: var(--bb-text); margin-bottom: 4px; }
.subtitle { color: var(--bb-muted); margin-bottom: 24px; font-size: 14px; }
.card { background: var(--bb-panel); border: 1px solid var(--bb-border); border-radius: 16px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.10); margin-bottom: 16px; }
.card h2 { font-size: 18px; color: var(--bb-text); margin-bottom: 12px; }
label { display: block; font-size: 13px; color: var(--bb-muted); margin-bottom: 6px; margin-top: 12px; }
label:first-of-type { margin-top: 0; }
input, select, textarea { width: 100%; padding: 10px 12px; border: 1px solid var(--bb-border); border-radius: 8px; font-size: 15px; font-family: inherit; background: var(--bb-elev); color: var(--bb-text); transition: border-color 0.2s; }
input:focus, select:focus, textarea:focus { outline: none; border-color: var(--bb-primary); background: var(--bb-elev); }
textarea { resize: vertical; min-height: 80px; }
button { display: inline-block; padding: 10px 20px; background: var(--bb-primary); color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 500; cursor: pointer; transition: background 0.2s; margin-top: 12px; }
button:hover { background: var(--bb-accent2); }
button:disabled { background: var(--bb-dim); cursor: not-allowed; }
button.secondary { background: var(--bb-elev); color: var(--bb-muted); }
button.secondary:hover { background: var(--bb-border); }
button.danger { background: var(--bb-red); color: #fff; }
button.danger:hover { background: var(--bb-red); filter: brightness(0.9); }
.error { color: var(--bb-red); font-size: 13px; margin-top: 8px; }
.success { color: var(--bb-green); font-size: 13px; margin-top: 8px; }
.chat-log { max-height: 400px; overflow-y: auto; padding: 12px; background: var(--bb-elev); border: 1px solid var(--bb-border); border-radius: 12px; margin-bottom: 12px; }
.msg { margin-bottom: 12px; padding: 10px 14px; border-radius: 12px; max-width: 85%; font-size: 14px; line-height: 1.5; }
.msg.user { background: var(--bb-elev); color: var(--bb-text); margin-left: auto; border-bottom-right-radius: 4px; }
.msg.ai { background: var(--bb-elev); color: var(--bb-text); border: 1px solid var(--bb-border); border-bottom-left-radius: 4px; }
.msg .label { font-size: 11px; font-weight: 600; color: var(--bb-muted); margin-bottom: 4px; }
.typing { font-style: italic; color: var(--bb-muted); font-size: 13px; padding: 8px 0; }
.chat-input-row { display: flex; gap: 8px; }
.chat-input-row input { flex: 1; }
.password-list { background: var(--bb-elev); border: 1px solid var(--bb-border); border-radius: 8px; padding: 12px; margin-top: 12px; font-size: 13px; }
.password-list .entry { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--bb-border); }
.password-list .entry:last-child { border-bottom: none; }
.password-list .name { font-weight: 500; }
.password-list .pass { color: var(--bb-primary); font-family: monospace; font-size: 14px; }
.report-section { margin-bottom: 16px; }
.report-section h3 { font-size: 16px; color: var(--bb-text); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid var(--bb-border); }
.report-section p, .report-section li { font-size: 14px; line-height: 1.6; color: var(--bb-muted); }
.report-section ul { padding-left: 20px; }
.report-section li { margin-bottom: 4px; }
.info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--bb-border); font-size: 14px; }
.info-row:last-child { border-bottom: none; }
.info-label { color: var(--bb-muted); }
.info-value { font-weight: 500; }
.nav { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.nav a { color: var(--bb-link); text-decoration: none; font-size: 13px; }
.nav a:hover { text-decoration: underline; }
.back-link { display: inline-block; margin-top: 8px; color: var(--bb-muted); text-decoration: none; font-size: 13px; }
.back-link:hover { text-decoration: underline; }
"""

_FAMILY_JS_UTILS = """
var API = window.location.origin + '/api/family';
function $(id) { return document.getElementById(id); }
function showError(id, msg) { var el = $(id); if (el) { el.textContent = msg; el.style.display = msg ? 'block' : 'none'; } }
function hide(el) { if (el) el.style.display = 'none'; }
function show(el, display) { if (el) el.style.display = display || 'block'; }
function store(key, val) { try { sessionStorage.setItem('fc_' + key, val); } catch(e) {} }
function load(key) { try { return sessionStorage.getItem('fc_' + key); } catch(e) { return null; } }
function api(method, path, body) {
    return new Promise(function(resolve, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open(method, API + path);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.timeout = 20000;
        xhr.ontimeout = function() { reject(new Error('Сервер не ответил. Попробуйте ещё раз.')); };
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== 4) return;
            var data = {};
            try { data = JSON.parse(xhr.responseText); } catch(e) {}
            if (xhr.status >= 200 && xhr.status < 300) { resolve(data); }
            else { reject(new Error(data.error || data.detail || 'Ошибка сервера')); }
        };
        xhr.onerror = function() { reject(new Error('Сетевая ошибка')); };
        xhr.send(body ? JSON.stringify(body) : null);
    });
}
"""


@app.route("/family")
def family_page():
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Circle — Создать комнату</title>
    <style>{_FAMILY_STYLE}</style>
</head>
<body>
    <div class="container">
        <h1>🫂 Family Circle</h1>
        <p class="subtitle">Асинхронная семейная медиация с ИИ-помощником</p>

        <div class="card">
            <h2>Создать комнату</h2>
            <label for="roomName">Название</label>
            <input id="roomName" type="text" placeholder="Например: Семейный совет" maxlength="255">
            <label for="creatorName">Ваше имя</label>
            <input id="creatorName" type="text" placeholder="Ваше имя" maxlength="100">
            <button id="createBtn">Создать комнату</button>
            <div id="createError" class="error"></div>
        </div>

        <div id="resultCard" class="card" style="display:none;">
            <h2>Комната создана</h2>
            <p id="roomIdDisplay"></p>
            <p id="inviteLink" style="margin-top:8px;"></p>
            <div id="passwordDisplay" class="password-list"></div>
            <button id="goToRoomBtn" class="secondary" style="margin-top:12px;">Перейти в комнату</button>
        </div>

        <div class="nav" style="margin-top:16px;">
            <a href="/family/room">Войти в существующую комнату</a>
        </div>
    </div>

    <script>
{_FAMILY_JS_UTILS}
    (function() {{
        var createBtn = $('createBtn');
        if (!createBtn) return;
        createBtn.addEventListener('click', function() {{
            var name = $('roomName').value.trim() || 'Семейный совет';
            var creator = $('creatorName').value.trim() || 'Я';
            showError('createError', '');
            createBtn.disabled = true;
            createBtn.textContent = 'Создаём...';
            api('POST', '/rooms', {{ name: name, creator_name: creator }})
                .then(function(data) {{
                    $('roomIdDisplay').textContent = 'ID комнаты: ' + data.room_id;
                    $('inviteLink').innerHTML = 'Ссылка: <a href="' + data.invite_link + '">' + window.location.origin + data.invite_link + '</a>';
                    var passDiv = $('passwordDisplay');
                    passDiv.innerHTML = '<h3 style="font-size:14px;margin-bottom:8px;">Ваш пароль (сохраните его!):</h3>';
                    passDiv.innerHTML += '<div class="entry"><span class="name">' + data.your_name + '</span><span class="pass">' + data.your_password + '</span></div>';
                    show($('resultCard'));
                    $('goToRoomBtn').onclick = function() {{ window.location.href = '/family/room?room_id=' + data.room_id; }};
                }})
                .catch(function(err) {{
                    showError('createError', err.message);
                }})
                .then(function() {{
                    createBtn.disabled = false;
                    createBtn.textContent = 'Создать комнату';
                }});
        }});
    }})();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/family/room")
def family_room_page():
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Circle — Комната</title>
    <style>{_FAMILY_STYLE}</style>
</head>
<body>
    <div class="container">
        <h1>🫂 Family Circle</h1>
        <p class="subtitle" id="roomSubtitle">Комната</p>

        <div class="nav">
            <a href="/family">Создать комнату</a>
            <a href="/family/result">Отчёт</a>
        </div>

        <div id="loginCard" class="card">
            <h2>Вход в комнату</h2>
            <label for="roomIdInput">ID комнаты</label>
            <input id="roomIdInput" type="text" placeholder="Вставьте ID комнаты">
            <label for="memberSelect">Ваше имя</label>
            <select id="memberSelect"></select>
            <p id="memberSelectHint" style="font-size:12px;color:#aaa;margin-top:4px;">Сначала введите ID комнаты</p>
            <label for="passwordInput">Пароль</label>
            <input id="passwordInput" type="password" placeholder="Пароль участника">
            <button id="loginBtn">Войти</button>
            <div id="loginError" class="error"></div>
            <div style="margin-top:16px;padding-top:16px;border-top:1px solid #eee;">
                <label for="joinName">Новый участник? Введите имя</label>
                <input id="joinName" type="text" placeholder="Имя для входа">
                <button id="joinBtn" class="secondary">Присоединиться к комнате</button>
                <div id="joinInfo" class="success"></div>
            </div>
        </div>

        <div id="chatCard" class="card" style="display:none;">
            <div id="roomInfo"></div>
            <div id="chatLog" class="chat-log"></div>
            <div id="typing" class="typing" style="display:none;">✏️ ИИ печатает...</div>
            <div class="chat-input-row">
                <input id="messageInput" type="text" placeholder="Напишите сообщение..." maxlength="5000">
                <button id="sendBtn">Отправить</button>
            </div>
            <div id="chatError" class="error"></div>

            <div style="margin-top:16px;padding-top:16px;border-top:1px solid #eee;">
                <button id="finishBtn" class="danger">Завершить диалог</button>
                <p style="font-size:12px;color:#aaa;margin-top:4px;">После завершения вы больше не сможете писать в этой комнате</p>
            </div>

            <div style="margin-top:12px;">
                <button id="reportBtn" class="secondary">📄 Посмотреть отчёт</button>
                <p id="reportReady" style="font-size:12px;color:var(--bb-green2);margin-top:4px;display:none;">✅ Отчёт готов!</p>
            </div>
        </div>
    </div>

    <script>
{_FAMILY_JS_UTILS}
    (function() {{
        var loginBtn = $('loginBtn');
        if (!loginBtn) return;

        var urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('room_id')) {{
            $('roomIdInput').value = urlParams.get('room_id');
            loadRoomInfo(urlParams.get('room_id'));
        }}

        $('roomIdInput').addEventListener('change', function() {{
            var rid = $('roomIdInput').value.trim();
            if (rid) loadRoomInfo(rid);
        }});

        var savedRoom = load('room_id');
        var savedName = load('member_name');
        var savedPass = load('password');
        if (savedRoom && savedName && savedPass) {{
            $('roomIdInput').value = savedRoom;
            loadRoomInfo(savedRoom, savedName, savedPass);
        }}

        function loadRoomInfo(roomId, autoName, autoPass) {{
            api('GET', '/rooms/' + roomId)
                .then(function(data) {{
                    $('roomSubtitle').textContent = 'Комната: ' + data.name;
                    var sel = $('memberSelect');
                    sel.innerHTML = '';
                    data.members.forEach(function(m) {{
                        var opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        sel.appendChild(opt);
                    }});
                    if (autoName && data.members.indexOf(autoName) !== -1) {{
                        sel.value = autoName;
                        $('passwordInput').value = autoPass || '';
                        tryLogin();
                    }}
                }})
                .catch(function(err) {{
                    showError('loginError', 'Не удалось загрузить комнату: ' + err.message);
                }});
        }}

        loginBtn.addEventListener('click', tryLogin);

        function tryLogin() {{
            var roomId = $('roomIdInput').value.trim();
            var memberName = $('memberSelect').value;
            var password = $('passwordInput').value.trim();
            if (!roomId || !memberName || !password) {{
                showError('loginError', 'Заполните все поля');
                return;
            }}
            showError('loginError', '');
            loginBtn.disabled = true;
            api('GET', '/rooms/' + roomId)
                .then(function(data) {{
                    if (data.members.indexOf(memberName) === -1) throw new Error('Участник не найден в этой комнате');
                    store('room_id', roomId);
                    store('member_name', memberName);
                    store('password', password);
                    $('roomSubtitle').textContent = 'Комната: ' + data.name;
                    $('roomInfo').innerHTML = '';
                    var infoHtml = ''
                        + '<div class="info-row"><span class="info-label">Статус</span><span class="info-value">' + (data.status === 'active' ? 'Активна' : data.status) + '</span></div>'
                        + '<div class="info-row"><span class="info-label">Высказалось</span><span class="info-value">' + data.spoke_count + '/' + data.participants_total + '</span></div>'
                        + '<div class="info-row"><span class="info-label">Участники</span><span class="info-value">' + data.members.map(escapeHtml).join(', ') + '</span></div>';
                    $('roomInfo').innerHTML = infoHtml;
                    hide($('loginCard'));
                    show($('chatCard'));
                    $('messageInput').focus();
                }})
                .catch(function(err) {{
                    showError('loginError', err.message);
                }})
                .then(function() {{
                    loginBtn.disabled = false;
                }});
        }}

        $('joinBtn').addEventListener('click', function() {{
            var roomId = $('roomIdInput').value.trim();
            var name = $('joinName').value.trim();
            if (!roomId || !name) {{ showError('loginError', 'Введите ID комнаты и имя'); return; }}
            showError('loginError', '');
            $('joinBtn').disabled = true;
            api('POST', '/rooms/join', {{ room_id: roomId, member_name: name }})
                .then(function(data) {{
                    $('joinInfo').textContent = data.is_new ? ('Вы вошли! Пароль: ' + data.your_password) : 'Участник уже есть. Введите пароль ниже.';
                    loadRoomInfo(roomId);
                }})
                .catch(function(err) {{
                    showError('loginError', err.message);
                }})
                .then(function() {{
                    $('joinBtn').disabled = false;
                }});
        }});

        var sendBtn = $('sendBtn');
        var msgInput = $('messageInput');
        var chatLog = $('chatLog');
        var typing = $('typing');

        msgInput.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendBtn.click(); }}
        }});

        sendBtn.addEventListener('click', function() {{
            var text = msgInput.value.trim();
            if (!text) return;
            var roomId = load('room_id'), memberName = load('member_name'), password = load('password');
            if (!roomId || !memberName || !password) {{ showError('chatError', 'Сессия потеряна. Войдите заново.'); return; }}
            showError('chatError', '');
            sendBtn.disabled = true; msgInput.disabled = true;
            addMessage('user', memberName, text);
            msgInput.value = '';
            show(typing);
            api('POST', '/chat/send', {{ room_id: roomId, member_name: memberName, password: password, message: text }})
                .then(function(data) {{
                    hide(typing);
                    addMessage('ai', 'Медиатор', data.response);
                }})
                .catch(function(err) {{
                    hide(typing);
                    showError('chatError', err.message);
                }})
                .then(function() {{
                    sendBtn.disabled = false; msgInput.disabled = false; msgInput.focus();
                }});
        }});

        function addMessage(type, label, text) {{
            var div = document.createElement('div');
            div.className = 'msg ' + type;
            div.innerHTML = '<div class="label">' + escapeHtml(label) + '</div>' + escapeHtml(text);
            chatLog.appendChild(div);
            chatLog.scrollTop = chatLog.scrollHeight;
        }}
        function escapeHtml(text) {{ var d = document.createElement('div'); d.textContent = text; return d.innerHTML; }}

        $('finishBtn').addEventListener('click', function() {{
            if (!confirm('Вы уверены, что хотите завершить диалог? После этого вы не сможете писать в этой комнате.')) return;
            var roomId = load('room_id'), memberName = load('member_name'), password = load('password');
            api('POST', '/chat/finish', {{ room_id: roomId, member_name: memberName, password: password }})
                .then(function() {{
                    sendBtn.disabled = true; msgInput.disabled = true;
                    $('finishBtn').disabled = true; $('finishBtn').textContent = '✓ Диалог завершён';
                    showError('chatError', '');
                    show($('reportReady'));
                }})
                .catch(function(err) {{ showError('chatError', err.message); }});
        }});

        $('reportBtn').addEventListener('click', function() {{
            var roomId = load('room_id'), memberName = load('member_name'), password = load('password');
            window.location.href = '/family/result?room_id=' + roomId + '&name=' + encodeURIComponent(memberName) + '&pass=' + encodeURIComponent(password);
        }});
    }})();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/family/result")
def family_result_page():
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Family Circle — Отчёт</title>
    <style>{_FAMILY_STYLE}</style>
</head>
<body>
    <div class="container">
        <h1>🫂 Family Circle</h1>
        <p class="subtitle">Финальный отчёт медиации</p>

        <div class="nav">
            <a href="/family">Создать комнату</a>
            <a href="/family/room">Войти в комнату</a>
        </div>

        <div class="card">
            <h2>Получить отчёт</h2>
            <label for="roomIdInput">ID комнаты</label>
            <input id="roomIdInput" type="text" placeholder="ID комнаты">
            <label for="memberSelect">Ваше имя</label>
            <select id="memberSelect"></select>
            <label for="passwordInput">Пароль</label>
            <input id="passwordInput" type="password" placeholder="Пароль участника">
            <button id="getReportBtn">Получить отчёт</button>
            <div id="reportError" class="error"></div>
        </div>

        <div id="reportCard" class="card" style="display:none;">
            <h2 id="reportTitle">Отчёт</h2>
            <div id="reportContent"></div>
            <button id="printBtn" class="secondary" style="margin-top:16px;">🖨️ Распечатать</button>
        </div>
    </div>

    <script>
{_FAMILY_JS_UTILS}
    (function() {{
        var getReportBtn = $('getReportBtn');
        if (!getReportBtn) return;

        var urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('room_id') && urlParams.get('name') && urlParams.get('pass')) {{
            $('roomIdInput').value = urlParams.get('room_id');
            loadMembers(urlParams.get('room_id'), urlParams.get('name'), urlParams.get('pass'));
        }}

        $('roomIdInput').addEventListener('change', function() {{
            var rid = $('roomIdInput').value.trim();
            if (rid) loadMembers(rid);
        }});

        function loadMembers(roomId, autoName, autoPass) {{
            api('GET', '/rooms/' + roomId)
                .then(function(data) {{
                    var sel = $('memberSelect');
                    sel.innerHTML = '';
                    data.members.forEach(function(m) {{
                        var opt = document.createElement('option');
                        opt.value = m;
                        opt.textContent = m;
                        sel.appendChild(opt);
                    }});
                    if (autoName) {{
                        sel.value = autoName;
                        $('passwordInput').value = autoPass || '';
                        fetchReport();
                    }}
                }})
                .catch(function(err) {{ showError('reportError', err.message); }});
        }}

        getReportBtn.addEventListener('click', fetchReport);

        function fetchReport() {{
            var roomId = $('roomIdInput').value.trim();
            var memberName = $('memberSelect').value;
            var password = $('passwordInput').value.trim();
            if (!roomId || !memberName || !password) {{ showError('reportError', 'Заполните все поля'); return; }}
            showError('reportError', '');
            getReportBtn.disabled = true;
            getReportBtn.textContent = 'Генерируем...';
            api('POST', '/report/generate', {{ room_id: roomId, member_name: memberName, password: password }})
                .then(function(data) {{
                    $('reportTitle').textContent = 'Отчёт по комнате';
                    $('reportContent').innerHTML = formatReport(data.report_text);
                    show($('reportCard'));
                }})
                .catch(function(err) {{ showError('reportError', err.message); }})
                .then(function() {{ getReportBtn.disabled = false; getReportBtn.textContent = 'Получить отчёт'; }});
        }}

        function escapeHtml(text) {{ var d = document.createElement('div'); d.textContent = text; return d.innerHTML; }}

        function formatReport(text) {{
            var html = escapeHtml(text)
                .replace(/### \\d+\\.\\s+(.+)/g, '</div><div class="report-section"><h3>$1</h3>')
                .replace(/- (.+)/g, '<li>$1</li>')
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/\\n/g, '<br>');
            html = html.replace(/<li>/g, '<ul><li>');
            html = html.replace(/<\\/li>(?![\\s\\S]*?<\\/li>)/g, '</li></ul>');
            return '<div class="report-section" style="margin-top:0;">' + html + '</div>';
        }}

        $('printBtn').addEventListener('click', function() {{ window.print(); }});
    }})();
    </script>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


# Vercel handler
handler = app
application = app
