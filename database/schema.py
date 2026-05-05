"""Schema management helpers.

Primary path: apply Alembic migrations to keep runtime schema aligned with models.
Fallback path: create missing tables from metadata if Alembic is unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from database.database import create_tables

logger = logging.getLogger(__name__)


def ensure_schema_up_to_date(config_path: str = "alembic.ini") -> None:
    """Bring database schema to the latest revision.

    Args:
        config_path: Path to Alembic config file.
    """
    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning("Alembic config not found, falling back to create_tables")
        create_tables()
        return

    try:
        alembic_cfg = Config(str(config_file))
        command.upgrade(alembic_cfg, "head")
        logger.info("Database schema upgraded to latest Alembic revision")
    except Exception as exc:
        logger.warning(
            "Alembic upgrade failed, falling back to create_tables", exc_info=exc
        )
        create_tables()
