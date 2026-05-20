"""Unified configuration system using Pydantic Settings.

This is the canonical configuration for BankBot project.
All other config modules (common/config.py, config/settings.py) should import from here.

Usage:
    from src.config import settings, bot_settings
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Normalize DB URL aliases accepted by cloud providers."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _prepare_database_env() -> None:
    """Allow POSTGRES_URL/SUPABASE_DB_URL as production aliases for DATABASE_URL."""
    if os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = normalize_database_url(os.environ["DATABASE_URL"])
        return

    for alias in ("POSTGRES_URL", "SUPABASE_DB_URL"):
        if os.getenv(alias):
            os.environ["DATABASE_URL"] = normalize_database_url(os.environ[alias])
            return


class Settings(BaseSettings):
    """Application settings with validation.

    All settings can be configured via environment variables.
    Supports multiple environments (development, test, staging, production).
    Loads from environment-specific .env files based on ENV variable.

    Environment file loading order:
    1. config/.env.shared
    2. config/.env.{ENV}.shared
    3. config/.env.local
    4. config/.env.{ENV}.local
    5. config/.env (legacy fallback)
    6. .env in project root
    """

    # Telegram
    BOT_TOKEN: str
    BOT_TOKEN_BRIDGE: str = ""

    # Environment
    ENV: str = Field(default="development")
    APP_ENV: Literal["dev", "prod", "test"] = Field(default="dev")

    # Administrator
    ADMIN_TELEGRAM_ID: int
    ADMIN_CHAT_ID: Optional[int] = None

    # Database
    DATABASE_URL: str
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

    # Parsing
    PARSING_ENABLED: bool = Field(default=False)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: Optional[str] = Field(default=None)

    # Proxy
    PROXY_URL: Optional[str] = Field(default=None)
    TELEGRAM_BASE_URL: str = Field(default="https://api.telegram.org/bot/")

    # Notifications
    NTFY_ENABLED: bool = Field(default=True)
    NTFY_BASE_URL: str = Field(default="https://ntfy.sh")
    NTFY_TOPIC: str = Field(default="lucasteam_bankbot_2091908459")
    NTFY_TAGS: str = Field(default="loud_speaker,bank")
    NTFY_TIMEOUT_SECONDS: int = Field(default=10)
    ADB_NOTIFICATIONS_ENABLED: bool = Field(default=False)
    ADB_PATH: str = Field(default="adb")
    ADB_DEVICE_SERIAL: str = Field(default="")

    # Background Tasks
    TASK_CHECK_INTERVAL: int = Field(default=300)

    # Bot Configuration
    BOT_NAME: str = Field(default="LucasTeam Bot")
    BOT_USERNAME: str = Field(default="")

    # Feature Flags
    SHOP_ENABLED: bool = Field(default=True)
    GAMES_ENABLED: bool = Field(default=True)
    ACHIEVEMENTS_ENABLED: bool = Field(default=True)
    SOCIAL_FEATURES_ENABLED: bool = Field(default=True)
    DND_SYSTEM_ENABLED: bool = Field(default=False)
    PARSING_CHECK_INTERVAL: int = Field(default=60)

    # Performance
    CACHE_ENABLED: bool = Field(default=False)
    CACHE_BACKEND: Literal["memory", "redis"] = Field(default="memory")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CACHE_TTL: int = Field(default=3600)

    # Development
    DEBUG: bool = Field(default=False)
    TEST_MODE: bool = Field(default=False)

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        """Validate that BOT_TOKEN is not empty."""
        if not v:
            raise ValueError("BOT_TOKEN cannot be empty")
        return v

    @field_validator("ADMIN_TELEGRAM_ID")
    @classmethod
    def validate_admin_id(cls, v: int) -> int:
        """Validate ADMIN_TELEGRAM_ID range."""
        if v <= 0:
            raise ValueError(
                f"ADMIN_TELEGRAM_ID must be a positive integer. Received: {v}"
            )
        max_telegram_id = 0xFFFFFFFFFF
        if v > max_telegram_id:
            raise ValueError(
                f"ADMIN_TELEGRAM_ID exceeds Telegram's maximum user ID ({max_telegram_id}). "
                f"Received: {v}"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate DATABASE_URL is not empty and has valid format."""
        if not v:
            raise ValueError("DATABASE_URL cannot be empty")
        return normalize_database_url(v)

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate LOG_LEVEL is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return v_upper

    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate ENV is one of the allowed values."""
        allowed = ["development", "test", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENV must be one of {allowed}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_bridge_config(self) -> "Settings":
        """Validate VK_TOKEN is set when BRIDGE_ENABLED=true."""
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


BotSettings = Settings


def get_settings() -> Settings:
    """Get settings instance with environment-specific configuration.

    Loads from environment-specific .env file based on ENV variable.
    """
    _prepare_database_env()
    env = os.getenv("ENV", os.getenv("APP_ENV", "development"))
    env_map = {"dev": "development", "prod": "production"}
    env = env_map.get(env, env)

    candidates = [
        Path("config/.env.shared"),
        Path(f"config/.env.{env}.shared"),
        Path("config/.env.local"),
        Path(f"config/.env.{env}.local"),
        Path("config/.env"),
        Path(".env"),
    ]
    env_files = [str(path) for path in candidates if path.exists()]
    return _create_settings_with_env_file(env_files or None)


def _create_settings_with_env_file(env_file: str | list[str] | None) -> Settings:
    """Create Settings instance with specified env file."""
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from typing import ClassVar

    class DynamicSettings(BaseSettings):
        BOT_TOKEN: str
        BOT_TOKEN_BRIDGE: str = ""
        ENV: str = "development"
        APP_ENV: Literal["dev", "prod", "test"] = "dev"
        ADMIN_TELEGRAM_ID: int
        ADMIN_CHAT_ID: Optional[int] = None
        DATABASE_URL: str
        DB_POOL_MIN: int = 2
        DB_POOL_MAX: int = 10
        DB_POOL_TIMEOUT: int = 30
        BRIDGE_ENABLED: bool = False
        BRIDGE_TG_CHAT_ID: int = 0
        TG_CHANNEL_ID: int = 0
        VK_TOKEN: str = ""
        VK_PEER_ID: int = 0
        VK_GROUP_ID: int = 0
        BRIDGE_ADMIN_CHAT_ID: Optional[int] = None
        PARSING_ENABLED: bool = False
        LOG_LEVEL: str = "INFO"
        LOG_FILE: Optional[str] = None
        PROXY_URL: Optional[str] = None
        TELEGRAM_BASE_URL: str = "https://api.telegram.org/bot/"
        NTFY_ENABLED: bool = True
        NTFY_BASE_URL: str = "https://ntfy.sh"
        NTFY_TOPIC: str = "lucasteam_bankbot_2091908459"
        NTFY_TAGS: str = "loud_speaker,bank"
        NTFY_TIMEOUT_SECONDS: int = 10
        ADB_NOTIFICATIONS_ENABLED: bool = False
        ADB_PATH: str = "adb"
        ADB_DEVICE_SERIAL: str = ""
        TASK_CHECK_INTERVAL: int = 300
        BOT_NAME: str = "LucasTeam Bot"
        BOT_USERNAME: str = ""
        SHOP_ENABLED: bool = True
        GAMES_ENABLED: bool = True
        ACHIEVEMENTS_ENABLED: bool = True
        SOCIAL_FEATURES_ENABLED: bool = True
        DND_SYSTEM_ENABLED: bool = False
        PARSING_CHECK_INTERVAL: int = 60
        CACHE_ENABLED: bool = False
        CACHE_BACKEND: Literal["memory", "redis"] = "memory"
        REDIS_URL: str = "redis://localhost:6379/0"
        CACHE_TTL: int = 3600
        DEBUG: bool = False
        TEST_MODE: bool = False

        model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
            env_file=env_file,
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )

        @field_validator("BOT_TOKEN")
        @classmethod
        def validate_bot_token(cls, v: str) -> str:
            if not v:
                raise ValueError("BOT_TOKEN cannot be empty")
            return v

        @field_validator("ADMIN_TELEGRAM_ID")
        @classmethod
        def validate_admin_id(cls, v: int) -> int:
            if v <= 0:
                raise ValueError(
                    f"ADMIN_TELEGRAM_ID must be a positive integer. Received: {v}"
                )
            max_telegram_id = 0xFFFFFFFFFF
            if v > max_telegram_id:
                raise ValueError(
                    f"ADMIN_TELEGRAM_ID exceeds Telegram's maximum user ID ({max_telegram_id}). "
                    f"Received: {v}"
                )
            return v

        @field_validator("DATABASE_URL")
        @classmethod
        def validate_database_url(cls, v: str) -> str:
            if not v:
                raise ValueError("DATABASE_URL cannot be empty")
            return normalize_database_url(v)

        @field_validator("LOG_LEVEL")
        @classmethod
        def validate_log_level(cls, v: str) -> str:
            allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            v_upper = v.upper()
            if v_upper not in allowed:
                raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
            return v_upper

        @field_validator("ENV")
        @classmethod
        def validate_env(cls, v: str) -> str:
            allowed = ["development", "test", "staging", "production"]
            if v not in allowed:
                raise ValueError(f"ENV must be one of {allowed}, got '{v}'")
            return v

        @model_validator(mode="after")
        def validate_bridge_config(self) -> "DynamicSettings":
            if self.BRIDGE_ENABLED and not self.VK_TOKEN:
                raise ValueError(
                    "VK_TOKEN обязателен когда BRIDGE_ENABLED=true. "
                    "Укажите VK_TOKEN в переменных окружения или .env-файле."
                )
            return self

    return DynamicSettings()


def get_bot_settings() -> Settings:
    """Alias for get_settings() for Bridge module compatibility."""
    return get_settings()


class _LazySettings:
    """Lazy settings proxy that loads on first attribute access."""

    _instance: "Settings | None" = None

    def _load(self) -> "Settings":
        if self._instance is None:
            self._instance = get_settings()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __setattr__(self, name: str, value):
        if name == "_instance":
            super().__setattr__(name, value)
        else:
            setattr(self._load(), name, value)

    def __dir__(self):
        return dir(self._load())

    def __repr__(self):
        return f"_LazySettings({self._load()!r})"


settings: "Settings" = _LazySettings()  # type: ignore[assignment]
bot_settings = settings


TRANSACTION_SECURITY: dict = {
    "max_single_amount": 10000,
    "max_hourly_transactions": 100,
}


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
    """Update currency rate in memory."""
    if game in ADVANCED_CURRENCY_CONFIG:
        ADVANCED_CURRENCY_CONFIG[game]["base_rate"] = new_rate
        return True
    return False


def get_currency_config() -> dict:
    """Get current currency configuration."""
    return ADVANCED_CURRENCY_CONFIG.copy()
