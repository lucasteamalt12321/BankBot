"""Database connection module with connection pooling support."""

import os
import sqlite3
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

# --- SQLAlchemy pooled engine ---

_engine = None


def _get_pool_settings() -> dict:
    """Read pool settings from config/settings.py if available.

    Returns:
        Dict with SQLAlchemy pool configuration parameters.
    """
    try:
        from config.settings import bot_settings

        return {
            "pool_size": bot_settings.DB_POOL_MIN,
            "max_overflow": bot_settings.DB_POOL_MAX - bot_settings.DB_POOL_MIN,
            "pool_timeout": bot_settings.DB_POOL_TIMEOUT,
            "pool_pre_ping": True,
        }
    except Exception:
        return {"pool_size": 2, "max_overflow": 8, "pool_timeout": 30, "pool_pre_ping": True}


def create_pooled_engine(db_url: Optional[str] = None):
    """Create SQLAlchemy engine with QueuePool.

    For SQLite uses StaticPool with check_same_thread=False.
    For other databases uses QueuePool with settings from Config.

    Args:
        db_url: SQLAlchemy database URL. Defaults to sqlite:///data/bot.db.

    Returns:
        SQLAlchemy Engine with connection pooling.
    """
    if db_url is None:
        try:
            from config.settings import bot_settings

            db_url = bot_settings.DATABASE_URL
        except Exception:
            db_url = f"sqlite:///{DB_PATH}"

    pool_kwargs = _get_pool_settings()

    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=pool_kwargs["pool_pre_ping"],
        )

    return create_engine(db_url, poolclass=QueuePool, **pool_kwargs)


def get_pooled_engine():
    """Get or create the global pooled engine (lazy init).

    Returns:
        Global SQLAlchemy Engine instance.
    """
    global _engine
    if _engine is None:
        _engine = create_pooled_engine()
    return _engine


async def close_pool(engine=None) -> None:
    """Dispose the connection pool (called during graceful shutdown).

    Args:
        engine: SQLAlchemy engine to dispose. Uses global _engine if None.
    """
    global _engine
    target = engine or _engine
    if target is not None:
        target.dispose()
        if engine is None:
            _engine = None


# --- Legacy sqlite3 API (backward compatibility) ---


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get raw sqlite3 connection (legacy API).

    Args:
        db_path: Path to SQLite database file.

    Returns:
        sqlite3.Connection with row_factory set.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_connection_with_foreign_keys(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get sqlite3 connection with foreign keys enabled.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        sqlite3.Connection with foreign keys ON.
    """
    conn = get_connection(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Alias for get_connection() for backward compatibility.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        sqlite3.Connection.
    """
    return get_connection(db_path)
