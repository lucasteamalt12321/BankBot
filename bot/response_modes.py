"""Shared short/long/watch response mode helpers for Telegram replies."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from telegram import Message

from database.database import ResponseModeSetting, SessionLocal


SHORT_MODE_MAX_CHARS = 650
SHORT_MODE_MAX_LINES = 10
WATCH_MODE_MAX_CHARS = 180
WATCH_MODE_MAX_LINES = 4
SUPPORTED_RESPONSE_MODES = {"short", "long", "watch"}
WATCH_TEMPLATES_HINT = "Часы: ОК, Да, Спасибо, Спасибо нет, Великолепно, Спасибо еще раз, Скоро увидимся, Скоро буду, Я занят(а), Нет."

_user_modes: dict[int, str] = {}
_global_mode: str | None = None
_reply_text_patch_installed = False
_original_reply_text: Any = None


def set_user_mode(user_id: int | None, mode: str) -> None:
    """Persist selected response mode for a Telegram user."""
    if user_id is None:
        return
    if mode not in SUPPORTED_RESPONSE_MODES:
        raise ValueError(f"Unsupported response mode: {mode}")
    _user_modes[user_id] = mode
    _save_user_mode(user_id, mode)


def set_all_user_modes(mode: str) -> None:
    """Set the default response mode for everyone and update known users."""
    global _global_mode
    if mode not in SUPPORTED_RESPONSE_MODES:
        raise ValueError(f"Unsupported response mode: {mode}")
    _global_mode = mode
    for user_id in list(_user_modes):
        _user_modes[user_id] = mode
    _save_global_mode(mode)


def get_user_mode(user_id: int | None) -> str | None:
    """Return explicitly selected response mode for a Telegram user."""
    if user_id is None:
        return None
    if user_id not in _user_modes:
        persisted_mode = _load_user_mode(user_id)
        if persisted_mode:
            _user_modes[user_id] = persisted_mode
    return _user_modes.get(user_id)


def get_default_user_mode(user_id: int | None) -> str:
    """Return selected mode or environment-specific default mode."""
    global _global_mode
    if _global_mode is None:
        _global_mode = _load_global_mode()
    return get_user_mode(user_id) or _global_mode or ("short" if os.environ.get("SPACE_ID") else "long")


def _load_user_mode(user_id: int) -> str | None:
    """Load a user's persisted response mode, if DB is available."""
    try:
        db = SessionLocal()
        try:
            result = db.execute(
                text(
                    """
                    SELECT mode
                    FROM response_mode_settings
                    WHERE telegram_id = :telegram_id AND is_global = false
                    """
                ),
                {"telegram_id": user_id},
            ).mappings().first()
        finally:
            db.close()
    except Exception:
        return None

    mode = result["mode"] if result else None
    return mode if mode in SUPPORTED_RESPONSE_MODES else None


def _load_global_mode() -> str | None:
    """Load persisted global response mode, if DB is available."""
    try:
        db = SessionLocal()
        try:
            result = db.execute(
                text(
                    """
                    SELECT mode
                    FROM response_mode_settings
                    WHERE is_global = true
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
        finally:
            db.close()
    except Exception:
        return None

    mode = result["mode"] if result else None
    return mode if mode in SUPPORTED_RESPONSE_MODES else None


def _save_user_mode(user_id: int, mode: str) -> None:
    """Save a user's selected response mode with DB fallback disabled on errors."""
    try:
        db = SessionLocal()
        try:
            dialect = db.bind.dialect.name
            values = {
                "telegram_id": user_id,
                "mode": mode,
                "is_global": False,
                "updated_at": datetime.utcnow(),
            }
            if dialect == "postgresql":
                db.execute(
                    text(
                        """
                        INSERT INTO response_mode_settings (telegram_id, mode, is_global, updated_at)
                        VALUES (:telegram_id, :mode, false, :updated_at)
                        ON CONFLICT (telegram_id)
                        DO UPDATE SET mode = EXCLUDED.mode, is_global = false, updated_at = EXCLUDED.updated_at
                        """
                    ),
                    values,
                )
            elif dialect == "sqlite":
                statement = sqlite_insert(ResponseModeSetting).values(**values)
                db.execute(
                    statement.on_conflict_do_update(
                        index_elements=["telegram_id"],
                        set_={
                            "mode": statement.excluded.mode,
                            "is_global": False,
                            "updated_at": statement.excluded.updated_at,
                        },
                    )
                )
            else:
                existing = db.query(ResponseModeSetting).filter_by(telegram_id=user_id).first()
                if existing:
                    existing.mode = mode
                    existing.is_global = False
                    existing.updated_at = datetime.utcnow()
                else:
                    db.add(ResponseModeSetting(**values))
            db.commit()
        finally:
            db.close()
    except Exception:
        return


def _save_global_mode(mode: str) -> None:
    """Save global response mode with DB fallback disabled on errors."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM response_mode_settings WHERE is_global = true"))
            db.add(
                ResponseModeSetting(
                    telegram_id=None,
                    mode=mode,
                    is_global=True,
                    updated_at=datetime.utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        return


def compact_reply_text(text: str, user_id: int | None) -> str:
    """Compact long bot replies for users in short or watch mode."""
    mode = get_default_user_mode(user_id)
    if mode == "watch":
        return _watch_reply_text(text)
    if mode != "short":
        return text
    if not isinstance(text, str):
        return text

    plain_text = _strip_html(text)
    lines = [line.strip() for line in plain_text.splitlines() if line.strip()]
    if len(plain_text) <= SHORT_MODE_MAX_CHARS and len(lines) <= SHORT_MODE_MAX_LINES:
        return text

    compact_lines: list[str] = []
    current_length = 0
    for line in lines:
        normalized_line = _compact_line(line)
        if not normalized_line:
            continue
        projected_length = current_length + len(normalized_line) + 1
        if projected_length > SHORT_MODE_MAX_CHARS - 80:
            break
        compact_lines.append(normalized_line)
        current_length = projected_length
        if len(compact_lines) >= SHORT_MODE_MAX_LINES:
            break

    if not compact_lines:
        compact_lines = [plain_text[: SHORT_MODE_MAX_CHARS - 90].rstrip()]

    return "\n".join(compact_lines).rstrip() + "\n\n… /long — полный ответ."


def _watch_reply_text(text: str) -> str:
    """Return an ultra-short reply suitable for a watch screen."""
    if not isinstance(text, str):
        return text

    plain_text = _strip_html(text)
    lines = [_compact_line(line) for line in plain_text.splitlines() if line.strip()]
    compact_lines: list[str] = []
    current_length = 0
    for line in lines:
        if not line:
            continue
        projected_length = current_length + len(line) + 1
        if projected_length > WATCH_MODE_MAX_CHARS - 20:
            break
        compact_lines.append(line)
        current_length = projected_length
        if len(compact_lines) >= WATCH_MODE_MAX_LINES:
            break

    if not compact_lines:
        compact_lines = [plain_text[: WATCH_MODE_MAX_CHARS - 20].rstrip()]

    return "\n".join(compact_lines).rstrip() + "\n… /short /long"


def install_reply_text_short_mode_patch() -> None:
    """Patch telegram.Message.reply_text to apply short mode globally."""
    global _reply_text_patch_installed, _original_reply_text
    if _reply_text_patch_installed:
        return

    _original_reply_text = Message.reply_text

    async def reply_text_with_mode(self: Message, text: str, *args: Any, **kwargs: Any) -> Any:
        user_id = self.from_user.id if self.from_user else None
        compacted_text = compact_reply_text(text, user_id)
        if compacted_text != text:
            # Compaction strips tags, so sending as plain text avoids invalid HTML.
            kwargs["parse_mode"] = None
        return await _original_reply_text(self, compacted_text, *args, **kwargs)

    Message.reply_text = reply_text_with_mode
    _reply_text_patch_installed = True


def _strip_html(text: str) -> str:
    """Convert simple HTML-formatted bot messages to plain text for compact mode."""
    return re.sub(r"<[^>]+>", "", text)


def _compact_line(line: str) -> str:
    """Shorten noisy whitespace in a single response line."""
    return " ".join(line.split())
