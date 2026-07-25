"""D&D AI Master for Vercel runtime.

Uses the same DB schema as the main bot but with Vercel-compatible
patterns (requests, raw SQL, send_telegram_message).
"""

import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


# ── helpers (mirror api/index.py patterns) ─────────────────────────

_DND_ENGINE = None


def get_db_engine():
    global _DND_ENGINE
    if _DND_ENGINE is not None:
        return _DND_ENGINE
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]
    if not database_url:
        database_url = "sqlite:///data/bot.db"
    _DND_ENGINE = create_engine(
        database_url,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=60,
        connect_args={"connect_timeout": 10},
    )
    return _DND_ENGINE


def send_tg(chat_id: int, text: str, parse_mode: str = "HTML",
            reply_markup: dict = None) -> None:
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token or not chat_id:
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=5,
        )
    except Exception as e:
        print(f"[DND] send error: {e}")


# ── dice parser ────────────────────────────────────────────────────

DICE_RE = re.compile(r"(\d*)[dк](\d+)([+-]\d+)?")


def parse_dice(text: str) -> Optional[dict]:
    m = DICE_RE.search(text)
    if not m:
        return None
    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    if sides not in {4, 6, 8, 10, 12, 20, 100}:
        return None
    return {"count": count, "sides": sides, "modifier": mod}


# ── AI call (Groq + HF fallback) ──────────────────────────────────

def call_ai(prompt: str, max_tokens: int = 800) -> str:
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.8,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            print(f"[DND] Groq error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[DND] Groq exception: {e}")

    hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
    if hf_token:
        try:
            resp = requests.post(
                "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-0.5B-Instruct",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={
                    "inputs": prompt,
                    "parameters": {"max_new_tokens": max_tokens, "temperature": 0.7},
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get("generated_text", "").strip()
            print(f"[DND] HF error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[DND] HF exception: {e}")

    return "🌌 Мастер задумался... Попробуйте ещё раз."


# ── DB helpers ─────────────────────────────────────────────────────

def _fetch_one(sql: str, params: dict = None) -> Optional[dict]:
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None


def _fetch_all(sql: str, params: dict = None) -> list[dict]:
    engine = get_db_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]


def _execute(sql: str, params: dict = None) -> None:
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


# ── session management ─────────────────────────────────────────────

def find_active_session(telegram_id: int) -> Optional[dict]:
    db_uid = _resolve_user_id(telegram_id)
    return _fetch_one(
        "SELECT * FROM dnd_sessions WHERE master_id = :uid AND status = 'active' LIMIT 1",
        {"uid": db_uid},
    ) or _fetch_one(
        """SELECT s.* FROM dnd_sessions s
           JOIN dnd_characters c ON c.session_id = s.id
           WHERE c.player_id = :uid AND s.status = 'active'
           LIMIT 1""",
        {"uid": db_uid},
    )


def session_summary(session: dict) -> str:
    chars = _fetch_all(
        "SELECT * FROM dnd_characters WHERE session_id = :sid AND is_active = TRUE",
        {"sid": session["id"]},
    )
    log_count = _fetch_one(
        "SELECT COUNT(*) as cnt FROM dnd_session_logs WHERE session_id = :sid",
        {"sid": session["id"]},
    )
    count = log_count["cnt"] if log_count else 0

    char_lines = []
    for c in chars:
        hp = f"❤️ {c['hit_points']}/{c['max_hit_points']}" if c.get('hit_points') else "❤️ ?"
        ac = f"🛡️ КБ {c['armor_class']}" if c.get('armor_class') else ""
        char_lines.append(f"  • <b>{c['name']}</b> ({c['character_class']}, ур.{c['level']}) {hp} {ac}")

    scene = session.get("current_scene") or "Новая игра"
    book = "Да" if session.get("book_content") else "Нет"
    last = session.get("last_ai_response", "")
    last_block = f"\n💬 <b>Последнее событие:</b>\n{last[:300]}" if last else ""

    text = (
        f"▶️ <b>{session['name']}</b> (#{session['id']})\n\n"
        f"📖 Сцена: {scene}\n"
        f"📝 Событий в логе: {count}\n"
        f"📚 Книга: {book}\n"
    )
    if char_lines:
        text += "\n👥 <b>Персонажи:</b>\n" + "\n".join(char_lines)
    text += last_block
    return text


# ── AI Master prompts ──────────────────────────────────────────────

def build_prompt(session: dict, action_text: str) -> str:
    sys_prompt = session.get("ai_system_prompt") or (
        "Ты — мастер подземелий (Game Master) D&D. Отвечай на русском языке. "
        "Не более 800 символов. Опиши ситуацию, дай игрокам варианты действий. "
        "Учитывай их предыдущие решения и состояние персонажей."
    )
    parts = [f"Инструкция: {sys_prompt}"]

    ctx = session.get("context_summary") or ""
    if ctx and len(ctx) > 3000:
        ctx = ctx[:3000]
    if ctx:
        parts.append(f"\nКонтекст книги/сцены:\n{ctx}")

    scene = session.get("current_scene") or ""
    if scene and len(scene) > 2000:
        scene = scene[:2000]
    if scene:
        parts.append(f"\nТекущая сцена:\n{scene}")

    chars = _fetch_all(
        "SELECT * FROM dnd_characters WHERE session_id = :sid AND is_active = TRUE",
        {"sid": session["id"]},
    )
    if chars:
        cl = ["\nАктивные персонажи:"]
        for c in chars:
            info = f"{c['name']} ({c['character_class']}, ур. {c['level']})"
            if c.get("hit_points"):
                info += f", ХП: {c['hit_points']}/{c['max_hit_points']}"
            if c.get("armor_class"):
                info += f", КБ: {c['armor_class']}"
            cl.append(f" - {info}")
        parts.append("\n".join(cl))

    recent = _fetch_all(
        "SELECT sl.*, c.name as char_name FROM dnd_session_logs sl "
        "LEFT JOIN dnd_characters c ON c.id = sl.character_id "
        "WHERE sl.session_id = :sid ORDER BY sl.created_at DESC LIMIT 8",
        {"sid": session["id"]},
    )
    if recent:
        rl = ["\nИстория последних действий:"]
        for e in reversed(recent):
            prefix = {"player_action": "👤", "ai_response": "🤖",
                      "dice_roll": "🎲", "system": "⚙️"}.get(e["message_type"], "•")
            name = e.get("char_name") or "Игрок"
            rl.append(f"{prefix} {name}: {(e['content'] or '')[:200]}")
        parts.append("\n".join(rl))

    fixes = _fetch_all(
        "SELECT * FROM dnd_fixes WHERE session_id = :sid AND applied = TRUE ORDER BY created_at DESC LIMIT 5",
        {"sid": session["id"]},
    )
    if fixes:
        fl = ["\nЗапомненные исправления:"]
        for f in reversed(fixes):
            fl.append(f"- Игрок: \"{f['original_context']}\" -> Поправка: {f['correction']}")
        parts.append("\n".join(fl))

    parts.append(f"\nДействие игрока:\n{action_text}")
    parts.append("\n(Ответь на русском, не более 800 символов. Опиши ситуацию и дай варианты действий.)")
    return "\n".join(parts)


# ── public handlers called from api/index.py ───────────────────────

def _resolve_user_id(telegram_id: int) -> int:
    """Return users.id for a telegram_id, creating a minimal row if needed."""
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM users WHERE telegram_id = :tid"),
            {"tid": telegram_id},
        ).mappings().first()
        if row:
            return row["id"]
        result = conn.execute(
            text("INSERT INTO users (telegram_id) VALUES (:tid) RETURNING id"),
            {"tid": telegram_id},
        )
        conn.commit()
        return result.mappings().first()["id"]


def cmd_dnd_start(telegram_id: int, chat_id: int, args: str) -> str:
    db_user_id = _resolve_user_id(telegram_id)
    existing = find_active_session(telegram_id)
    if existing:
        return (f"❌ У вас уже есть активная сессия \"{existing['name']}\" (#{existing['id']}).\n"
                f"Сначала завершите её: /dnd_stop")

    name = args if args else f"Кампания #{telegram_id % 10000}"
    _execute(
        "INSERT INTO dnd_sessions (master_id, name, status, started_at) "
        "VALUES (:uid, :name, 'active', :now)",
        {"uid": db_user_id, "name": name, "now": datetime.now(timezone.utc)},
    )

    return (
        f"🎲 <b>D&D сессия запущена!</b>\n\n"
        f"Название: {name}\n\n"
        f"📖 <b>Как играть:</b>\n"
        f"• Просто пиши действия — бот поймёт\n"
        f"• Кидай кубики: <code>d20</code>, <code>2d6+3</code>\n"
        f"• Загрузи книгу: отправь PDF/DOCX/TXT\n\n"
        f"🛑 Остановить: /dnd_stop\n"
        f"📊 Статус: /dnd_status\n"
        f"✏️ Исправить: /dnd_fix <текст>"
    )


def cmd_dnd_stop(user_id: int, chat_id: int) -> str:
    session = find_active_session(user_id)
    if not session:
        return "❌ Нет активной D&D сессии."
    _execute(
        "UPDATE dnd_sessions SET status = 'paused', paused_at = :now WHERE id = :sid",
        {"sid": session["id"], "now": datetime.now(timezone.utc)},
    )
    return "⏸ <b>Сессия приостановлена.</b> Прогресс сохранён. Продолжить: /dnd_start"


def cmd_dnd_status(user_id: int, chat_id: int) -> str:
    session = find_active_session(user_id)
    if not session:
        return "📭 Нет активных D&D сессий. Используйте /dnd_start"
    return session_summary(session)


def cmd_dnd_roll(user_id: int, chat_id: int, args: str) -> Optional[str]:
    if not args:
        return ("❌ Используйте: /dnd_roll <кубик> [цель]\n"
                "Примеры:\n  /dnd_roll d20\n  /dnd_roll 2d6+3\n"
                '  /dnd_roll d20 "Проверка восприятия"')

    parts = args.split(maxsplit=1)
    dice_str = parts[0]
    purpose = parts[1] if len(parts) > 1 else ""

    parsed = parse_dice(dice_str)
    if not parsed:
        return "❌ Неверный формат кубика. Доступны: d4, d6, d8, d10, d12, d20, d100"

    total = sum(random.randint(1, parsed["sides"]) for _ in range(parsed["count"]))
    total += parsed["modifier"]
    dice_label = f"{parsed['count']}d{parsed['sides']}"
    if parsed["modifier"]:
        sign = "+" if parsed["modifier"] > 0 else ""
        dice_label += f"{sign}{parsed['modifier']}"

    session = find_active_session(user_id)
    comment = ""
    if session:
        _execute(
            "INSERT INTO dnd_session_logs (session_id, player_id, message_type, content) "
            "VALUES (:sid, :uid, 'dice_roll', :content)",
            {"sid": session["id"], "uid": user_id,
             "content": f"{dice_label}: {total}{' (' + purpose + ')' if purpose else ''}"},
        )
        prompt = build_prompt(session, f"Бросок кубика: {dice_label} = {total} (прокомментируй)")
        ai_answer = call_ai(prompt)
        comment = f"\n\n{ai_answer}"
        _execute(
            "UPDATE dnd_sessions SET last_ai_response = :resp WHERE id = :sid",
            {"resp": ai_answer[:800], "sid": session["id"]},
        )

    return f"🎲 <b>Бросок</b>\nКубик: {dice_label}{' — ' + purpose if purpose else ''}\n<b>Итог: {total}</b>{comment}"


def cmd_dnd_fix(user_id: int, chat_id: int, fix_text: str) -> str:
    session = find_active_session(user_id)
    if not session:
        return "❌ Нет активной D&D сессии."

    last_log = _fetch_one(
        "SELECT content FROM dnd_session_logs WHERE session_id = :sid ORDER BY created_at DESC LIMIT 1",
        {"sid": session["id"]},
    )
    original = last_log["content"] if last_log else ""

    _execute(
        "INSERT INTO dnd_fixes (session_id, player_id, original_context, correction) "
        "VALUES (:sid, :uid, :orig, :corr)",
        {"sid": session["id"], "uid": user_id, "orig": original, "corr": fix_text},
    )
    return f"✅ Исправление запомнено: {fix_text}"


def cmd_dnd(user_id: int, chat_id: int) -> str:
    return (
        "🎲 <b>D&D ИИ-Мастер</b>\n\n"
        "<b>Команды:</b>\n"
        "  /dnd_start [название] — начать сессию\n"
        "  /dnd_stop — приостановить\n"
        "  /dnd_status — сводка\n"
        "  /dnd_roll <кубик> [цель] — бросок\n"
        "  /dnd_fix <текст> — исправить ИИ\n\n"
        "<b>Как играть:</b>\n"
        "  • Просто пиши что делаешь — бот поймёт\n"
        "  • Кидай кубики: <code>d20</code>, <code>2d6+3</code>\n"
        "  • Загрузи книгу приключения (PDF/DOCX/TXT)\n\n"
        "🤖 ИИ: Groq (LLaMA 3.1) + HF fallback"
    )


# ── free-form message handler ─────────────────────────────────────

def handle_free_text(user_id: int, chat_id: int, text: str) -> Optional[str]:
    session = find_active_session(user_id)
    if not session:
        return None  # not in D&D mode, let other handlers process it

    msg_type = "action"
    parsed = parse_dice(text)
    if parsed:
        msg_type = "dice"
        total = sum(random.randint(1, parsed["sides"]) for _ in range(parsed["count"]))
        total += parsed["modifier"]
        dice_label = f"{parsed['count']}d{parsed['sides']}"
        if parsed["modifier"]:
            sign = "+" if parsed["modifier"] > 0 else ""
            dice_label += f"{sign}{parsed['modifier']}"
        _execute(
            "INSERT INTO dnd_session_logs (session_id, player_id, message_type, content) "
            "VALUES (:sid, :uid, 'dice_roll', :content)",
            {"sid": session["id"], "uid": user_id,
             "content": f"{dice_label}: {total}"},
        )

    prompt = build_prompt(session, text)
    answer = call_ai(prompt)

    _execute(
        "INSERT INTO dnd_session_logs (session_id, player_id, message_type, content, ai_context) "
        "VALUES (:sid, :uid, 'player_action', :content, :ctx)",
        {"sid": session["id"], "uid": user_id, "content": text, "ctx": prompt},
    )
    _execute(
        "INSERT INTO dnd_session_logs (session_id, player_id, message_type, content) "
        "VALUES (:sid, :uid, 'ai_response', :content)",
        {"sid": session["id"], "uid": user_id, "content": answer},
    )
    _execute(
        "UPDATE dnd_sessions SET last_ai_response = :resp WHERE id = :sid",
        {"resp": answer[:800], "sid": session["id"]},
    )

    return answer
