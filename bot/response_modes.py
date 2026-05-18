"""Shared short/long response mode helpers for Telegram replies."""

from __future__ import annotations

import os
import re
from typing import Any

from telegram import Message


SHORT_MODE_MAX_CHARS = 650
SHORT_MODE_MAX_LINES = 10

_user_modes: dict[int, str] = {}
_reply_text_patch_installed = False
_original_reply_text: Any = None


def set_user_mode(user_id: int | None, mode: str) -> None:
    """Persist selected response mode for a Telegram user in memory."""
    if user_id is None:
        return
    if mode not in {"short", "long"}:
        raise ValueError(f"Unsupported response mode: {mode}")
    _user_modes[user_id] = mode


def get_user_mode(user_id: int | None) -> str | None:
    """Return explicitly selected response mode for a Telegram user."""
    if user_id is None:
        return None
    return _user_modes.get(user_id)


def get_default_user_mode(user_id: int | None) -> str:
    """Return selected mode or environment-specific default mode."""
    return get_user_mode(user_id) or ("short" if os.environ.get("SPACE_ID") else "long")


def compact_reply_text(text: str, user_id: int | None) -> str:
    """Compact long bot replies for users in short mode."""
    if get_default_user_mode(user_id) != "short":
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
