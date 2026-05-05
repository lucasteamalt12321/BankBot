"""Bridge state manager — persists and restores last forwarded message IDs."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog

from database.connection import get_connection

logger = structlog.get_logger()


@dataclass
class BridgeState:
    """Snapshot of bridge forwarding state."""

    last_tg_msg_id: int = 0
    last_vk_msg_id: int = 0


def load_state(db_path: Optional[str] = None) -> BridgeState:
    """Load bridge state from DB. Raises RuntimeError if DB unavailable.

    Args:
        db_path: Optional path to SQLite database file.

    Returns:
        BridgeState with last forwarded message IDs.

    Raises:
        RuntimeError: If the database is unavailable or migration 004 not applied.
    """
    try:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT last_tg_msg_id, last_vk_msg_id FROM bridge_state WHERE id=1"
            ).fetchone()
            if row:
                return BridgeState(
                    last_tg_msg_id=row[0],
                    last_vk_msg_id=row[1],
                )
            return BridgeState()
        finally:
            conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(
            f"Bridge: не удалось загрузить состояние из БД: {e}. "
            "Убедитесь, что БД доступна и миграция 004 применена."
        ) from e


def save_tg_msg_id(msg_id: int, db_path: Optional[str] = None) -> None:
    """Update last_tg_msg_id after successful TG→VK forward.

    Args:
        msg_id: Telegram message ID that was successfully forwarded.
        db_path: Optional path to SQLite database file.
    """
    _update_state("last_tg_msg_id", msg_id, db_path)


def save_vk_msg_id(msg_id: int, db_path: Optional[str] = None) -> None:
    """Update last_vk_msg_id after successful VK→TG forward.

    Args:
        msg_id: VK message ID that was successfully forwarded.
        db_path: Optional path to SQLite database file.
    """
    _update_state("last_vk_msg_id", msg_id, db_path)


def _update_state(field: str, value: int, db_path: Optional[str]) -> None:
    """Write a single field of bridge_state (id=1) to the database.

    Args:
        field: Column name to update ('last_tg_msg_id' or 'last_vk_msg_id').
        value: New integer value for the column.
        db_path: Optional path to SQLite database file.
    """
    try:
        conn = get_connection(db_path)
        try:
            conn.execute(
                f"UPDATE bridge_state SET {field}=?, updated_at=? WHERE id=1",  # noqa: S608
                (value, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            logger.debug("Bridge state updated", field=field, value=value)
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Failed to save bridge state", field=field, error=str(e))
