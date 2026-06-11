"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import asyncio
import hmac
import os
import random
import re
import sys
from datetime import datetime
from flask import Flask, jsonify, request
import requests
from sqlalchemy import create_engine, text

app = Flask(__name__)

# Webhook secret
_raw_webhook_secret = os.getenv("WEBHOOK_SECRET") or ""
WEBHOOK_SECRET = _raw_webhook_secret if _raw_webhook_secret else "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266"
print(f"[STARTUP] WEBHOOK_SECRET length: {len(WEBHOOK_SECRET)}, first 10 chars: {WEBHOOK_SECRET[:10]}")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_RESPONSE_MODE = "short"
CHAT_RESPONSE_MODES: dict[int, str] = {}
DB_ENGINE = None
_GD_SUBMIT_STATE: dict[int, dict] = {}
_GD_MODERATE_STATE: dict[int, int] = {}
_GD_APPROVE_STATE: dict[int, dict] = {}  # user_id -> {sub_id, level_name, username}


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
            normalize_database_url(database_url), pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
    _ensure_gd_tables(DB_ENGINE)
    return DB_ENGINE


def _ensure_gd_tables(engine):
    """Create GD module tables if they don't exist (preserves existing data)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS levels (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0
                )
            """))
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


def call_ai_api(prompt: str, max_tokens: int = 150) -> str:
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
                "temperature": 0.8,
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
                text("SELECT * FROM levels ORDER BY position ASC LIMIT :lim"),
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


def add_gd_level(name: str, position: int) -> int | None:
    try:
        with get_db_engine().connect() as conn:
            result = conn.execute(
                text("INSERT INTO levels (name, position) VALUES (:nm, :pos) RETURNING id"),
                {"nm": name, "pos": position},
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
    headers = {"Accept": "application/json", "User-Agent": "BankBot/ChessModule"}
    
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
        return {
            "username": lichess_username.strip(),
            "title": title if isinstance(title, str) and title else None,
            "online": online,
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


def normalize_command(text: str | None) -> str:
    """Return command without bot mention and arguments."""

    if not text:
        return ""
    first_token = text.strip().split(maxsplit=1)[0]
    return first_token.split("@", maxsplit=1)[0].lower()


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
    match = re.search(r"(.+?), ты выпил\(а\)\s*([\d.]+)\s*л\..*?всего\s*[-–]\s*([\d.]+)\s*л", text, re.IGNORECASE)
    if not match:
        return None
    player = match.group(1).strip()
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
        raise RuntimeError("BOT_TOKEN is not configured")

    payload = {"chat_id": chat_id, "text": text}
    payload.update(extra_payload)
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()


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

    return f"""[BANK] LucasTeam BankBot
Привет, {name}!
Регистрация: ✅ Пользователь уже зарегистрирован
ID: {user_id}

Основное:
/balance — баланс
/profile — профиль
/stats — статистика
/reading_trainer — тренажёр чтения
/trivia — викторина
/short — краткие ответы
/long — полный режим для себя
/long_all — полный режим для всех

Разделы:
/chess — шахматы
/ai — искусственный интеллект
/gd — geometry dash
/shop — магазин
/admin — админка"""


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
    return jsonify({"service": "BankBot", "status": "ok", "platform": "vercel"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "platform": "vercel"})


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


# ── Vercel trivia (no external imports) ──────────────────────────────────

_TRIVIA_QUESTIONS: list[dict] = [
    {"id": 1, "group": "rules", "text": "Как согласно высокому канону правил именования вселенной разрешено называть в творчестве реального Олега?", "correct_text": "Олег или Степан"},
    {"id": 2, "group": "rules", "text": "Что из перечисленного является строго ЗАПРЕЩЁННОЙ темой в каноническом творчестве?", "correct_text": "Внешность и медицинские диагнозы реальных людей"},
    {"id": 3, "group": "rules", "text": "Какой уровень канонизации требует обязательного одобрения и Луки, и Олега?", "correct_text": "Высокий канон (🔵)"},
    {"id": 4, "group": "tracks", "text": "Какой трек является первым документом вселенной Олеговируса?", "correct_text": "«Рома» (Олег, 11 декабря 2025)"},
    {"id": 5, "group": "tracks", "text": "В каком треке впервые прозвучал термин «олеговирус»?", "correct_text": "«Олег, как ты задолбал» (Лука, 26 декабря 2025)"},
    {"id": 6, "group": "tracks", "text": "Кто из сторонних участников первым внёс вклад в мифологию, написав трек «Олеговирус»?", "correct_text": "Рома"},
    {"id": 7, "group": "tracks", "text": "Какая статья впервые дала Олеговирусу научное описание с антигенами KHM и POST?", "correct_text": "«Olegovirus checkmarevus» (Лука, апрель 2026)"},
    {"id": 8, "group": "tracks", "text": "Почему трек «Вирус LucasTeamLuke» признан неканоничным?", "correct_text": "Нарушает именование (LucasTeamLuke) и упоминает внешность"},
    {"id": 9, "group": "tracks", "text": "Какая статья Олега описывает LTL-паразита с синдромами СГД и СНЧ, но требует переработки из-за внешности?", "correct_text": "«LukasTeamLuke sp. nov.» (средний канон, 🟡)"},
    {"id": 10, "group": "tracks", "text": "В каких отношениях состоят олеговирус и LTL-паразит согласно статье «Olegovirus checkmarevus»?", "correct_text": "Союзничество-конкурентство"},
    {"id": 11, "group": "tracks", "text": "Какой трек Ромы впервые сводит обоих агентов (олеговирус и LTL-паразита) в одном пространстве?", "correct_text": "«Тень агента (V.2)» (апрель 2026)"},
    {"id": 12, "group": "candy", "text": "Какая базовая награда конфетами за прохождение Nine Circles?", "correct_text": "1 конфета за 2% прохождения"},
    {"id": 13, "group": "candy", "text": "Сколько конфет полагается за 1% на сложных партах (61-70%) Nine Circles?", "correct_text": "1 конфета за 1% прохождения"},
    {"id": 14, "group": "candy", "text": "Кто такой «Хранитель конфет» в конфетной экономике?", "correct_text": "Лука (отказался от своей награды в 28 конфет)"},
    {"id": 15, "group": "candy", "text": "Сколько конфет получил Рома после «инфляции счастья» (умножение на 1.5, округление вверх)?", "correct_text": "16 конфет"},
    {"id": 16, "group": "tea", "text": "Каким священным выражением заканчиваются молитвы в Чайной религии (Teaology)?", "correct_text": "eight-nine"},
    {"id": 17, "group": "tea", "text": "Кто автор и создатель Чайной религии (Teaology)?", "correct_text": "Лука (LucasTeam, 27 апреля 2026)"},
    {"id": 18, "group": "tracks", "text": "Какой трек Луки стал первым «бытовым» произведением в каноне (3 мая 2026)?", "correct_text": "«Восемь километров (походный дневник)»"},
    {"id": 19, "group": "ltrs", "text": "Какие координаты (хаос; экспрессивность) у Луки в рейтинге LTRS?", "correct_text": "(10; 46) — ритуальный экспрессив"},
    {"id": 20, "group": "ltrs", "text": "Кто в рейтинге LTRS имеет тип личности «мемный экспрессив»?", "correct_text": "Рома (23; 26)"},
    {"id": 21, "group": "glossary", "text": "Что такое «антиген KHM» в терминологии Олеговируса?", "correct_text": "Реакция «закатывание глаз» у окружающих"},
    {"id": 22, "group": "glossary", "text": "Что в глоссарии канона означает термин «Парадокс ожидания»?", "correct_text": "Бронь парта сгорает, его проходит Хранитель конфет"},
    {"id": 23, "group": "glossary", "text": "Кто в глоссарии LTRS определяется как «Пассивный изолят»?", "correct_text": "Саша (15; 14)"},
]


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

_AI_QUESTIONS_FALLBACK_PROMPT = """Ты — генератор викторин. Придумай вопрос на тему "Команды и возможности банковского бота BankBot".
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
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user = message.get("from", {})
        user_id = user.get("id", chat_id)
        name = user.get("first_name") or user.get("username") or "LucasTeam"
        command = normalize_command(text)

        print(f"[WEBHOOK] command='{command}' text='{text[:50]}' user_id={user_id} chat_id={chat_id}")

        # Check for parsing trigger (reply to game bot with "Парсинг" or /parse or /parsing)
        reply_to = message.get("reply_to_message")
        is_parsing_trigger = (
            text and text.lower().strip() in ["парсинг", "parsing"]
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
                args = text.split()[1:] if len(text.split()) > 1 else []
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
                args = text.split()[1:] if len(text.split()) > 1 else []
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
                args = text.split()[1:] if len(text.split()) > 1 else []
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
            args = text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(
                    chat_id,
                    "**🤖 AI Module**\n\n"
                    "/ai <вопрос> — задать вопрос AI\n"
                    "/ask <вопрос> — алиас /ai\n"
                    "/ai_help — показать эту справку\n"
                    "/chat <персонаж> <текст> — диалог с персонажем\n"
                    "/generate_prayer или /pray — сгенерировать молитву\n"
                    "/ask_canon <вопрос> — вопрос по канону\n\n"
                    "Пример: /ai Что такое олеговирус?",
                )
            else:
                question = args[1]
                if len(question) < 3:
                    send_telegram_message(chat_id, "❌ Вопрос слишком короткий")
                else:
                    prompt = f"Ты помощник, отвечающий кратко и по делу. Вопрос пользователя: {question}\n\nОтветь в 2-3 предложениях."
                    answer = call_ai_api(prompt, max_tokens=200)
                    send_telegram_message(chat_id, answer)
        elif command == "/ai_help" and chat_id:
            send_telegram_message(
                chat_id,
                "🤖 **AI Module**\n\n"
                "/ai <вопрос> — задать вопрос AI\n"
                "/ask <вопрос> — алиас /ai\n"
                "/ai_help — показать эту справку\n"
                "/chat <персонаж> <текст> — диалог с персонажем\n"
                "/generate_prayer или /pray — сгенерировать молитву\n"
                "/ask_canon <вопрос> — вопрос по канону",
            )
        elif command == "/chat" and chat_id:
            args = text.split(maxsplit=2)
            if len(args) < 3:
                send_telegram_message(
                    chat_id,
                    "Использование: /chat <персонаж> <текст>\n\n"
                    "Доступные персонажи:\n"
                    "• олеговирус — навязчивое существо\n"
                    "• чай — божественный мудрец\n\n"
                    "Пример: /chat олеговирус привет!",
                )
            else:
                character = args[1].lower()
                user_text = args[2]

                if character == "олеговирус":
                    prompt = (
                        f"Ты — олеговирус, существо, которое постоянно издаёт звуки 'кхм-кхм', "
                        f"любит придираться к чужим текстам. Ответь кратко (1-2 предложения). "
                        f"Пользователь сказал: {user_text}"
                    )
                elif character == "чай":
                    prompt = (
                        f"Ты — верховный божественный Чай, воплощение покоя и мудрости. "
                        f"Говори вдохновляюще, используй слова 'настой', 'eight-nine'. "
                        f"Ответь кратко (1-2 предложения). Пользователь сказал: {user_text}"
                    )
                else:
                    send_telegram_message(
                        chat_id, f"❌ Неизвестный персонаж: {character}"
                    )
                    prompt = None

                if prompt:
                    answer = call_ai_api(prompt)
                    send_telegram_message(chat_id, answer)
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
            args = text.split(maxsplit=1)
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
            args = text.split(maxsplit=1)
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
                "♟ **Шахматный модуль BankBot**\n\n"
                "**Доступные команды:**\n"
                "`/chess_link <ник>` — привязать Lichess аккаунт\n"
                "`/chess_rating` — показать рейтинги\n"
                "`/chess_stats` — показать статистику\n"
                "`/puzzle` или `/chess_puzzle` — решить шахматную задачу\n\n"
                "**Пример:**\n"
                "`/chess_link DrNykterstein`"
            )
            send_telegram_message(chat_id, help_text, parse_mode="Markdown")
        
        # /chess_link <username>
        elif command == "/chess_link" and chat_id:
            args = text.split()[1:] if text else []
            
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
                                "Теперь можно использовать шахматные команды BankBot."
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
                            rating_parts.append(f"⚡ **Молния:** {perfs['blitz'].get('rating', '?')} ({perfs['blitz'].get('games', 0)} игр)")
                        if "rapid" in perfs:
                            rating_parts.append(f"⏱️ **Быстрая:** {perfs['rapid'].get('rating', '?')} ({perfs['rapid'].get('games', 0)} игр)")
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
                            stats_parts.append(f"⚡ **Молния:** {perfs['blitz'].get('rating', '?')} ({perfs['blitz'].get('games', 0)} игр)")
                        if "rapid" in perfs:
                            stats_parts.append(f"⏱️ **Быстрая:** {perfs['rapid'].get('rating', '?')} ({perfs['rapid'].get('games', 0)} игр)")
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
            account = get_chess_account(user_id)
            if not account:
                send_telegram_message(
                    chat_id,
                    "❌ Сначала привяжите Lichess аккаунт: `/chess_link <ник>`",
                    parse_mode="Markdown",
                )
            else:
                # Check cooldown (max 1 puzzle per day)
                now = datetime.utcnow()
                coins_data = get_user_coins(user_id)
                
                if coins_data and coins_data.get("last_puzzle_at"):
                    last_puzzle = coins_data["last_puzzle_at"]
                    from datetime import timedelta
                    if now - last_puzzle < timedelta(hours=24):
                        remaining = 24 - (now - last_puzzle).total_seconds() / 3600
                        send_telegram_message(
                            chat_id,
                            f"⏳ Пожалуйста, подождите {remaining:.1f} часов до следующей задачи.",
                        )
                        return jsonify({"ok": True})
                
                send_telegram_message(
                    chat_id,
                    "🧩 Загружаю задачу...",
                )
                
                try:
                    # Fetch daily puzzle from Lichess
                    puzzle_url = f"{LICHESS_API_BASE_URL}/puzzle/daily"
                    headers = {"Accept": "application/json", "User-Agent": "BankBot/ChessModule"}
                    response = requests.get(puzzle_url, headers=headers, timeout=LICHESS_TIMEOUT_SECONDS)
                    
                    if response.status_code == 200:
                        puzzle_data = response.json()
                        puzzle = puzzle_data.get("puzzle", {})
                        
                        puzzle_id = puzzle.get("id", "unknown")
                        rating = puzzle.get("rating", "?")
                        fen = puzzle.get("fen", "")
                        themes = ", ".join(puzzle.get("themes", [])[:3])
                        puzzle_url_link = f"https://lichess.org/training/{puzzle_id}"
                        
                        # Send board image using Lichess board export
                        # Format: https://lichess1.org/export/fen.gif?fen=<FEN>&theme=brown&piece=cburnett
                        board_image_url = f"https://lichess1.org/export/fen.gif?fen={fen.replace(' ', '_')}&theme=brown&piece=cburnett"
                        
                        puzzle_msg = (
                            f"🧩 **Шахматная задача дня**\n\n"
                            f"Рейтинг: {rating}\n"
                            f"Темы: {themes}\n\n"
                            f"Ваш ход!"
                        )
                        
                        # Send photo with caption
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
                                # Fallback to text message if image fails
                                print(f"Error sending photo: status={photo_response.status_code}, response={photo_response.text}")
                                send_telegram_message(chat_id, puzzle_msg + f"\n\n[Открыть на Lichess]({puzzle_url_link})", parse_mode="Markdown")
                        except Exception as photo_exc:
                            print(f"Error sending photo: {photo_exc}")
                            send_telegram_message(chat_id, puzzle_msg + f"\n\n[Открыть на Lichess]({puzzle_url_link})", parse_mode="Markdown")
                            photo_exc_occurred = True
                        else:
                            photo_exc_occurred = False
                    else:
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось загрузить задачу. Попробуйте позже.",
                        )
                        photo_exc_occurred = True
                    
                    # Award puzzle reward (5 coins, cooldown tracking) if photo sent successfully
                    if not photo_exc_occurred and photo_response.status_code == 200:
                        update_user_coins(user_id, 5, now)
                        send_telegram_message(
                            chat_id,
                            f"💰 Вы получили 5 монет за участие!\nБаланс: {coins_data['balance'] + 5 if coins_data else 5} монет",
                        )
                except Exception as exc:
                    print(f"Error fetching puzzle: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки задачи. Попробуйте позже.",
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

            # If message has photo/video but no pending submission, tell user
            if message.get("photo") or message.get("video") or message.get("document"):
                send_telegram_message(
                    chat_id,
                    "❌ Не найдена ожидающая заявка. Сначала используйте `/submit <название уровня>`, затем отправьте фото/видео.",
                    parse_mode="Markdown",
                )
                return jsonify({"ok": True})

            # GD approve — position input
            approve_state = _GD_APPROVE_STATE.get(user_id)
            if approve_state:
                text_stripped = text.strip() if text else ""
                try:
                    position = int(text_stripped)
                    if position < 1:
                        send_telegram_message(chat_id, "❌ Позиция должна быть положительным числом.")
                        return jsonify({"ok": True})
                    sub_id = approve_state["sub_id"]
                    level_name = approve_state["level_name"]
                    # Add level to levels table
                    level_id = add_gd_level(level_name, position)
                    if not level_id:
                        send_telegram_message(chat_id, f"❌ Ошибка при добавлении уровня **{level_name}** в топ.", parse_mode="Markdown")
                    else:
                        # Approve submission
                        if approve_gd_submission_db(sub_id, user_id):
                            send_telegram_message(
                                chat_id,
                                f"✅ Заявка #{sub_id} подтверждена!\n"
                                f"🏆 Уровень **{level_name}** добавлен в топ на позицию **#{position}**.",
                                parse_mode="Markdown",
                            )
                        else:
                            send_telegram_message(chat_id, f"❌ Ошибка подтверждения заявки #{sub_id}.")
                    _GD_APPROVE_STATE.pop(user_id, None)
                except ValueError:
                    send_telegram_message(chat_id, "❌ Пожалуйста, введите число — позицию в топе.")
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
            args = text.split()[1:] if text else []
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

        # /gd_level <id или название>
        elif command == "/gd_level" and chat_id:
            args = text.split()[1:] if text else []
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

        # /gd_leaderboard — GD уровень топ
        elif command == "/gd_leaderboard" and chat_id:
            try:
                levels = get_gd_leaderboard(20)
                if not levels:
                    send_telegram_message(chat_id, "📊 Топ уровней пуст. Администратор ещё не добавил уровни.")
                else:
                    lines = ["🏆 **Geometry Dash — Топ-20 уровней**\n"]
                    for lv in levels:
                        cnt = get_gd_completions_count(lv["id"])
                        score = 101 - lv["position"]
                        lines.append(f"**#{lv['position']}** {lv['name']}\n   💪 Сложность: {score}/100\n   ✅ Прохождений: {cnt}")
                    lines.append("\n_Используйте /my_stats для просмотра своей статистики_")
                    send_telegram_message(chat_id, "\n".join(lines), parse_mode="Markdown")
            except Exception as exc:
                print(f"leaderboard error: {exc}")
                send_telegram_message(chat_id, "❌ Ошибка при загрузке топа уровней.")

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

        # /player_stats @username
        elif command == "/player_stats" and chat_id:
            args = text.split()[1:] if text else []
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

        # /submit <level_name>
        elif command == "/submit" and chat_id:
            args = text.split(maxsplit=1)
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
                args = text.split()
                if len(args) < 3:
                    send_telegram_message(chat_id, "❌ Использование: `/add_level <название> <позиция>`\nПример: `/add_level Tartarus 1`", parse_mode="Markdown")
                else:
                    try:
                        pos = int(args[-1])
                        name = " ".join(args[1:-1])
                        if add_gd_level(name, pos):
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
                args = text.split()
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

    except Exception as e:
        print(f"Error processing update: {e}")
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
                return
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
                return
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
                return
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
    import json as _json
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
    """Generate reading text and questions using AI API."""
    try:
        import requests
        import json
        import random

        # Try Groq first, then HF as fallback
        groq_key = os.getenv("GROQ_API_KEY")
        hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")

        print(f"Groq key available: {bool(groq_key)}")
        print(f"HF Token available: {bool(hf_token)}")

        if not groq_key and not hf_token:
            print("No API keys, using fallback")
            fallback_sets = get_fallback_sets()
            return jsonify(random.choice(fallback_sets))

        # Simplified prompt for better results
        prompt = """Напиши короткую историю для ребёнка 7 лет.

История должна быть про животное или семью.
Используй простые слова.
6 коротких предложений.

Потом напиши 3 простых вопроса по истории.

Пример:
Жил кот Барсик. Он любил молоко. Мама кормила кота. Барсик мурлыкал. Он спал на диване. Кот был добрый.

Вопросы:
1. Как звали кота?
2. Что любил кот?
3. Где спал кот?

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
        questions = []
        for line in questions_section[:3]:
            # Remove numbering
            line = line.lstrip("123.").strip()
            if "?" in line:
                questions.append({"question": line, "answer": "ответ"})

        # Ensure we have 3 questions
        while len(questions) < 3:
            questions.append({"question": "Что было в истории?", "answer": "ответ"})

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
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}&secret_token={secret}&allowed_updates=message&allowed_updates=callback_query", timeout=10)
        return jsonify({"set": r.json(), "url": webhook_url, "bot_token_set": bool(BOT_TOKEN)})
    except Exception as e:
        return jsonify({"error": str(e), "url": webhook_url})

# Initialize database tables on cold start
try:
    engine = get_db_engine()
    _ensure_gd_tables(engine)
    print("[INIT] GD tables initialized successfully")
except Exception as init_exc:
    print(f"[INIT] GD table init failed: {init_exc}")

# Debug endpoint to test submissions table
@app.route("/api/debug_db", methods=["GET"])
def debug_db():
    """Debug database and GD tables."""
    import json as _json
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


# Vercel handler
handler = app
application = app
