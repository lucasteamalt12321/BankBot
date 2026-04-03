"""Общий модуль логирования для всех ботов проекта.

Использование:
    from common.logging import setup_logging, get_logger

    setup_logging(json=True)
    logger = get_logger(__name__)
"""

import logging
import os
import structlog


def setup_logging(level: str = "INFO", json: bool = False) -> None:
    """Настраивает логирование для приложения.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json: Если True, выводит логи в JSON формате (для продакшена).
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json or os.getenv("LOG_JSON", "false").lower() == "true":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Возвращает structlog-логгер для указанного модуля.

    Args:
        name: Имя модуля (обычно __name__).

    Returns:
        Настроенный structlog BoundLogger.
    """
    return structlog.get_logger(name)
