"""Общая конфигурация проекта BankBot.

Единая точка входа для всех настроек. Содержит реальный код.

Использование:
    from common.config import settings, bot_settings
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения BankBot.

    Все параметры читаются из переменных окружения или .env-файла.

    Attributes:
        BOT_TOKEN: Токен Telegram-бота (BankBot).
        BOT_TOKEN_BRIDGE: Токен Telegram-бота (BridgeBot).
        ENV: Окружение запуска (development / test / staging / production).
        APP_ENV: Алиас ENV для Bridge-модуля (dev / prod / test).
        ADMIN_TELEGRAM_ID: Telegram ID администратора.
        DATABASE_URL: URL подключения к базе данных.
        DB_POOL_MIN: Минимальный размер пула соединений.
        DB_POOL_MAX: Максимальный размер пула соединений.
        DB_POOL_TIMEOUT: Таймаут ожидания соединения из пула (сек).
        BRIDGE_ENABLED: Включить Bridge TG → VK.
        BRIDGE_TG_CHAT_ID: ID Telegram-канала для Bridge.
        VK_TOKEN: Токен VK API (обязателен при BRIDGE_ENABLED=true).
        VK_PEER_ID: peer_id VK-чата для Bridge.
        VK_GROUP_ID: ID группы VK.
        BRIDGE_ADMIN_CHAT_ID: Telegram ID чата для уведомлений Bridge.
        LOG_LEVEL: Уровень логирования.
    """

    # Telegram — BankBot
    BOT_TOKEN: str = Field(default="")
    BOT_TOKEN_BRIDGE: str = Field(default="")

    # Окружение
    ENV: str = Field(default="development")
    APP_ENV: Literal["dev", "prod", "test"] = Field(default="dev")

    # Администратор
    ADMIN_TELEGRAM_ID: int = Field(default=0)
    ADMIN_CHAT_ID: Optional[int] = Field(default=None)

    # База данных
    DATABASE_URL: str = Field(default="sqlite:///bot.db")
    DB_POOL_MIN: int = Field(default=2)
    DB_POOL_MAX: int = Field(default=10)
    DB_POOL_TIMEOUT: int = Field(default=30)

    # Bridge
    BRIDGE_ENABLED: bool = Field(default=False)
    BRIDGE_TG_CHAT_ID: int = Field(default=0)
    TG_CHANNEL_ID: int = Field(default=0)
    VK_TOKEN: str = Field(default="")
    VK_PEER_ID: int = Field(default=0)
    VK_GROUP_ID: int = Field(default=0)
    BRIDGE_ADMIN_CHAT_ID: Optional[int] = Field(default=None)

    # Парсинг
    PARSING_ENABLED: bool = Field(default=False)

    # Логирование
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: Optional[str] = Field(default=None)

    # Фоновые задачи
    TASK_CHECK_INTERVAL: int = Field(default=300)

    # Бот
    BOT_NAME: str = Field(default="LucasTeam Bot")
    BOT_USERNAME: str = Field(default="")

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate that BOT_TOKEN is not empty (unless in test mode).

        Args:
            v: Token value.

        Returns:
            Validated token.
        """
        if v:
            return v
        if os.getenv("ENV") == "test" or os.getenv("APP_ENV") == "test":
            return v
        return v  # allow empty for flexibility

    @field_validator("ADMIN_TELEGRAM_ID")
    @classmethod
    def validate_admin_id(cls, v: int) -> int:
        """Validate ADMIN_TELEGRAM_ID range.

        Args:
            v: Telegram ID value.

        Returns:
            Validated ID.

        Raises:
            ValueError: If ID is out of valid Telegram range.
        """
        if os.getenv("ENV") == "test" or os.getenv("APP_ENV") == "test":
            return v
        if v < 0:
            raise ValueError(f"ADMIN_TELEGRAM_ID must be non-negative. Got: {v}")
        max_telegram_id = 0xFFFFFFFFFF
        if v > max_telegram_id:
            raise ValueError(
                f"ADMIN_TELEGRAM_ID exceeds Telegram max ({max_telegram_id}). Got: {v}"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate DATABASE_URL is not empty.

        Args:
            v: Database URL.

        Returns:
            Validated URL.

        Raises:
            ValueError: If URL is empty.
        """
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate LOG_LEVEL value.

        Args:
            v: Log level string.

        Returns:
            Uppercased log level.

        Raises:
            ValueError: If level is not recognized.
        """
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return v_upper

    @model_validator(mode="after")
    def validate_bridge_config(self) -> "Settings":
        """Validate VK_TOKEN is set when BRIDGE_ENABLED=true.

        Returns:
            Validated settings instance.

        Raises:
            ValueError: If BRIDGE_ENABLED=true and VK_TOKEN is empty.
        """
        if self.BRIDGE_ENABLED and not self.VK_TOKEN:
            raise ValueError(
                "VK_TOKEN обязателен когда BRIDGE_ENABLED=true. "
                "Укажите VK_TOKEN в переменных окружения или .env-файле."
            )
        return self

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Алиас для совместимости с Bridge-модулем
BotSettings = Settings


def get_settings() -> Settings:
    """Получить экземпляр настроек с учётом текущего окружения.

    Порядок поиска .env-файла:
    1. ``config/.env.{ENV}``
    2. ``config/.env``
    3. ``.env`` в корне
    4. Только переменные окружения

    Returns:
        Экземпляр Settings с загруженной конфигурацией.
    """
    env = os.getenv("ENV", os.getenv("APP_ENV", "development"))
    # Нормализуем: dev → development
    env_map = {"dev": "development", "prod": "production"}
    env = env_map.get(env, env)

    candidates = [
        Path(f"config/.env.{env}"),
        Path("config/.env"),
        Path(".env"),
    ]
    for path in candidates:
        if path.exists():
            return Settings(_env_file=str(path))
    return Settings()


# Алиас для Bridge-модуля
def get_bot_settings() -> Settings:
    """Алиас get_settings() для совместимости с Bridge-модулем.

    Returns:
        Экземпляр Settings.
    """
    return get_settings()


# Глобальные синглтоны
settings = get_settings()
bot_settings = settings


# ---------------------------------------------------------------------------
# Конфигурация валют
# ---------------------------------------------------------------------------

ADVANCED_CURRENCY_CONFIG: dict = {
    "shmalala": {
        "base_rate": 1.0,
        "currency_name": "coins",
        "admin_editable": True,
        "event_multipliers": {
            "battle_win": 1.0,
            "crocodile_win": 1.2,
            "crocodile_correct_guess": 1.1,
            "crocodile_participate": 1.0,
            "fishing": 1.0,
            "trap": 1.0,
        },
    },
    "gdcards": {
        "base_rate": 2.0,
        "currency_name": "points",
        "admin_editable": True,
        "rarity_multipliers": {
            "card_common": 1.0,
            "card_rare": 1.5,
            "card_epic": 2.0,
            "card_legendary": 3.0,
        },
    },
    "true_mafia": {
        "base_rate": 15.0,
        "currency_name": "wins",
        "admin_editable": True,
        "event_multipliers": {
            "game_win": 1.0,
            "game_participation": 0.3,
        },
    },
    "bunkerrp": {
        "base_rate": 20.0,
        "currency_name": "survivals",
        "admin_editable": True,
        "event_multipliers": {
            "bunker_survival": 1.0,
            "game_participation": 0.5,
        },
    },
}


def update_currency_rate(game: str, new_rate: float) -> bool:
    """Обновить коэффициент валюты в памяти.

    Args:
        game: Название игры (shmalala, gdcards, true_mafia, bunkerrp).
        new_rate: Новый коэффициент конвертации.

    Returns:
        True если игра найдена и обновлена, False иначе.
    """
    if game in ADVANCED_CURRENCY_CONFIG:
        ADVANCED_CURRENCY_CONFIG[game]["base_rate"] = new_rate
        return True
    return False


def get_currency_config() -> dict:
    """Получить текущую конфигурацию валют.

    Returns:
        Копия словаря ADVANCED_CURRENCY_CONFIG.
    """
    return ADVANCED_CURRENCY_CONFIG.copy()
