"""Unified configuration system using Pydantic Settings.

Расширяет базовую конфигурацию src/config.py полями Bridge-модуля.
Поддерживает окружения: dev, prod, test через APP_ENV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Настройки приложения BankBot с Bridge-модулем.

    Все параметры читаются из переменных окружения или .env-файла.
    При BRIDGE_ENABLED=true обязателен непустой VK_TOKEN.

    Attributes:
        BOT_TOKEN: Токен Telegram-бота.
        APP_ENV: Окружение запуска (dev / prod / test).
        ADMIN_TELEGRAM_ID: Telegram ID администратора.
        BRIDGE_ENABLED: Включить Bridge TG ↔ VK.
        BRIDGE_TG_CHAT_ID: ID Telegram-чата для Bridge.
        VK_TOKEN: Токен VK API (обязателен при BRIDGE_ENABLED=true).
        VK_PEER_ID: peer_id VK-чата для Bridge.
        BRIDGE_ADMIN_CHAT_ID: Telegram ID чата для уведомлений Bridge (опционально).
        DATABASE_URL: URL подключения к базе данных.
        DB_POOL_MIN: Минимальный размер пула соединений.
        DB_POOL_MAX: Максимальный размер пула соединений.
        DB_POOL_TIMEOUT: Таймаут ожидания соединения из пула (сек).
        LOG_LEVEL: Уровень логирования.
    """

    # Telegram
    BOT_TOKEN: str = Field(default="")
    APP_ENV: Literal["dev", "prod", "test"] = Field(default="dev")
    ADMIN_TELEGRAM_ID: int = Field(default=0)

    # Bridge
    BRIDGE_ENABLED: bool = Field(default=False)
    BRIDGE_TG_CHAT_ID: int = Field(default=0)
    VK_TOKEN: str = Field(default="")
    VK_PEER_ID: int = Field(default=0)
    BRIDGE_ADMIN_CHAT_ID: Optional[int] = Field(default=None)

    # Database
    DATABASE_URL: str = Field(default="sqlite:///data/bot.db")
    DB_POOL_MIN: int = Field(default=2)
    DB_POOL_MAX: int = Field(default=10)
    DB_POOL_TIMEOUT: int = Field(default=30)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    @model_validator(mode="after")
    def validate_bridge_config(self) -> "BotSettings":
        """Проверяет, что VK_TOKEN задан при включённом Bridge.

        Returns:
            Экземпляр настроек после валидации.

        Raises:
            ValueError: Если BRIDGE_ENABLED=true и VK_TOKEN пуст.
        """
        if self.BRIDGE_ENABLED and not self.VK_TOKEN:
            raise ValueError(
                "VK_TOKEN обязателен когда BRIDGE_ENABLED=true. "
                "Укажите VK_TOKEN в переменных окружения или .env-файле."
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_bot_settings() -> BotSettings:
    """Возвращает экземпляр настроек с учётом текущего окружения.

    Порядок поиска .env-файла:
    1. ``config/.env.{APP_ENV}`` (например, ``config/.env.prod``)
    2. ``config/.env``
    3. Только переменные окружения (без файла)

    Returns:
        Экземпляр BotSettings с загруженной конфигурацией.
    """
    import os

    env = os.getenv("APP_ENV", "dev")
    env_specific = Path(f"config/.env.{env}")
    env_default = Path("config/.env")

    if env_specific.exists():
        return BotSettings(_env_file=str(env_specific))
    if env_default.exists():
        return BotSettings(_env_file=str(env_default))
    return BotSettings()


bot_settings = get_bot_settings()
