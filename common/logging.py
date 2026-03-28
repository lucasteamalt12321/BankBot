"""Общий модуль логирования для всех ботов проекта.

Использование:
    from common.logging import get_logger

    logger = get_logger(__name__)
"""

import logging
import structlog


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Возвращает structlog-логгер для указанного модуля.

    Args:
        name: Имя модуля (обычно __name__).

    Returns:
        Настроенный structlog BoundLogger.
    """
    return structlog.get_logger(name)


def setup_logging(level: str = "INFO") -> None:
    """Настраивает базовое логирование для приложения.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
