"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import hmac
import os
from datetime import datetime
from flask import Flask, jsonify, request
import requests
from sqlalchemy import create_engine, text

app = Flask(__name__)

# Webhook secret
WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET", "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266"
)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_RESPONSE_MODE = "short"
CHAT_RESPONSE_MODES: dict[int, str] = {}
DB_ENGINE = None


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
            normalize_database_url(database_url), pool_pre_ping=True
        )
    return DB_ENGINE


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
        return {
            "username": lichess_username.strip(),
            "title": title if isinstance(title, str) and title else None,
            "online": bool(payload.get("online", False)),
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


def parse_gdcards_message(text: str) -> dict | None:
    """Parse GDcards message and extract orbs."""
    import re

    if not text:
        return None

    # Check if this is a GDcards message (has card emoji and orbs)
    if "🃏" not in text and "GDcards" not in text:
        return None

    # Parse orbs: 🤩 Орбы: +5
    orbs_match = re.search(r"🤩 Орбы:\s*\+(\d+)", text)
    if not orbs_match:
        return None

    orbs = int(orbs_match.group(1))

    # Parse player: Игрок: LucasTeam
    player_match = re.search(r"Игрок:\s*(.+)", text)
    player = player_match.group(1).strip() if player_match else "Неизвестно"

    # Parse card: Карта: TopZeraYT
    card_match = re.search(r"Карта:\s*(.+)", text)
    card = card_match.group(1).strip() if card_match else "Неизвестно"

    return {
        "game": "GDcards",
        "orbs": orbs,
        "player": player,
        "card": card,
        "coins": orbs * 2,  # Курс GDcards 2:1
    }


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
/short — краткие ответы
/long — полный режим для себя
/long_all — полный режим для всех"""


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

    # Process Telegram commands supported by the Vercel webhook runtime.
    try:
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user = message.get("from", {})
        user_id = user.get("id", chat_id)
        name = user.get("first_name") or user.get("username") or "LucasTeam"
        command = normalize_command(text)

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
            parsed = parse_gdcards_message(replied_text)

            if parsed and chat_id:
                # Add coins to user balance
                coins = parsed["coins"]
                description = (
                    f"Парсинг {parsed['game']}: +{parsed['orbs']} orbs (курс 2:1)"
                )

                if add_user_balance(user_id, coins, description):
                    send_telegram_message(
                        chat_id,
                        f"✅ Начислено {coins} очков за {parsed['card']}\n({parsed['game']}: {parsed['orbs']} orbs × 2)",
                    )
                else:
                    send_telegram_message(chat_id, "❌ Ошибка начисления")
                return jsonify({"ok": True})
            elif chat_id:
                send_telegram_message(
                    chat_id,
                    "❌ Не удалось распарсить сообщение (поддерживается только GDcards)",
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
        elif command == "/ai" or command == "/ask":
            if not chat_id:
                return jsonify({"ok": True})
            args = text.split(maxsplit=1)
            if len(args) < 2:
                send_telegram_message(
                    chat_id,
                    "Использование: /ai <вопрос>\nПример: /ai Что такое олеговирус?",
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
                "🤖 AI команды:\n\n"
                "/ai <вопрос> — задать вопрос AI\n"
                "/chat <персонаж> <текст> — диалог с персонажем\n"
                "/generate_prayer — сгенерировать молитву\n"
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
                    "• чай — божественный мудрец",
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
        elif command == "/generate_prayer" and chat_id:
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

        # Trivia command
        elif command == "/trivia" and chat_id:
            # Simple trivia - generate question with AI
            prompt = (
                "Создай простой вопрос-викторину на тему олеговируса или LucasTeam Lore. "
                "Формат: вопрос с 4 вариантами ответа (A, B, C, D). "
                "Укажи правильный ответ в конце."
            )
            question = call_ai_api(prompt, max_tokens=200)
            send_telegram_message(chat_id, f"🎯 Викторина:\n\n{question}")

        # ============================================================================
        # Chess Module Commands
        # ============================================================================
        
        elif command == "/chess" and chat_id:
            help_text = (
                "♟ **Шахматный модуль BankBot**\n\n"
                "**Доступные команды:**\n"
                "`/chess_link <ник>` — привязать Lichess аккаунт\n"
                "`/chess_rating` — показать рейтинги\n"
                "`/chess_stats` — показать статистику\n"
                "`/puzzle` — решить шахматную задачу\n\n"
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
                        # For now, just show basic info (ratings need additional API call)
                        title_prefix = f"{lichess_user['title']} " if lichess_user.get("title") else ""
                        online_text = "🟢 онлайн" if lichess_user.get("online") else "⚫ оффлайн"
                        
                        rating_msg = (
                            f"♟ **Рейтинги {title_prefix}{lichess_user['username']}**\n\n"
                            f"Статус: {online_text}\n\n"
                            "📊 Подробные рейтинги скоро будут добавлены..."
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
                        
                        stats_msg = (
                            f"♟ **Статистика {title_prefix}{lichess_user['username']}**\n\n"
                            "📈 Детальная статистика скоро будет добавлена..."
                        )
                        send_telegram_message(chat_id, stats_msg, parse_mode="Markdown")
                except Exception as exc:
                    print(f"Error fetching stats: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки статистики. Попробуйте позже.",
                    )
        
        # /puzzle command
        elif command == "/puzzle" and chat_id:
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
                        game = puzzle_data.get("game", {})
                        
                        puzzle_id = puzzle.get("id", "unknown")
                        rating = puzzle.get("rating", "?")
                        themes = ", ".join(puzzle.get("themes", [])[:3])
                        puzzle_url_link = f"https://lichess.org/training/{puzzle_id}"
                        
                        puzzle_msg = (
                            f"🧩 **Шахматная задача дня**\n\n"
                            f"Рейтинг: {rating}\n"
                            f"Темы: {themes}\n\n"
                            f"[Открыть на Lichess]({puzzle_url_link})\n\n"
                            "Решите задачу на Lichess и вернитесь сюда!"
                        )
                        send_telegram_message(chat_id, puzzle_msg, parse_mode="Markdown")
                    else:
                        send_telegram_message(
                            chat_id,
                            "❌ Не удалось загрузить задачу. Попробуйте позже.",
                        )
                except Exception as exc:
                    print(f"Error fetching puzzle: {exc}")
                    send_telegram_message(
                        chat_id,
                        "❌ Ошибка загрузки задачи. Попробуйте позже.",
                    )
    
    except Exception as e:
        print(f"Error processing update: {e}")

    return jsonify({"ok": True})


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
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
            timeout=10,
        )
        return jsonify(
            {
                "status": "success",
                "telegram_accessible": True,
                "status_code": response.status_code,
                "response": response.json(),
            }
        )
    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "telegram_accessible": False,
                "error": str(e),
            }
        )


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


# Vercel handler
handler = app
application = app
