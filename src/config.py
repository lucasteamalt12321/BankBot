"""Unified configuration system using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings with validation.
    
    All settings can be configured via environment variables.
    Supports multiple environments (development, test, staging, production).
    Loads from environment-specific .env files based on ENV variable.
    
    Environment file loading order:
    1. config/.env.{ENV} (e.g., .env.production)
    2. config/.env (fallback for backward compatibility)
    """
    
    # Environment
    ENV: str = Field(default="development")
    
    # Bot Configuration
    BOT_TOKEN: str
    ADMIN_TELEGRAM_ID: int
    
    # Database
    DATABASE_URL: str
    
    # Parsing
    PARSING_ENABLED: bool = Field(default=False)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: Optional[str] = Field(default=None)
    
    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, v):
        """Validate that BOT_TOKEN is not empty."""
        if not v or v == "":
            raise ValueError("BOT_TOKEN cannot be empty")
        return v
    
    @field_validator("ADMIN_TELEGRAM_ID")
    @classmethod
    def validate_admin_id(cls, v):
        """
        Validate that ADMIN_TELEGRAM_ID is a positive integer within Telegram's valid range.
        
        Telegram user IDs range from 1 to 0xffffffffff (1,099,511,627,775).
        Reference: https://core.telegram.org/api/bots/ids
        """
        if v <= 0:
            raise ValueError(
                "ADMIN_TELEGRAM_ID must be a positive integer. "
                f"Received: {v}"
            )
        
        # Telegram's maximum user ID is 0xffffffffff (1,099,511,627,775)
        max_telegram_id = 0xffffffffff
        if v > max_telegram_id:
            raise ValueError(
                f"ADMIN_TELEGRAM_ID exceeds Telegram's maximum user ID ({max_telegram_id}). "
                f"Received: {v}"
            )
        
        return v
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v):
        """Validate that DATABASE_URL is not empty."""
        if not v or v == "":
            raise ValueError("DATABASE_URL cannot be empty")
        return v
    
    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v):
        """Validate that ENV is one of the allowed values."""
        allowed = ["development", "test", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENV must be one of {allowed}, got '{v}'")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Validate that LOG_LEVEL is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return v_upper
    
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


def get_settings() -> Settings:
    """
    Get settings instance with environment-specific configuration.
    
    Loads from environment-specific .env file based on ENV variable.
    """
    # Get ENV from environment or use default
    env = os.getenv("ENV", "development")
    
    # Determine which .env files to load
    env_file_path = Path(f"config/.env.{env}")
    default_env_path = Path("config/.env")
    
    # Use environment-specific file if it exists, otherwise fall back to default
    if env_file_path.exists():
        return Settings(_env_file=str(env_file_path))
    elif default_env_path.exists():
        return Settings(_env_file=str(default_env_path))
    else:
        return Settings()


# Singleton instance
settings = get_settings()


# Конфигурация валют (теперь с возможностью динамического изменения)
ADVANCED_CURRENCY_CONFIG = {
    'shmalala': {
        'base_rate': 1.0,
        'currency_name': 'coins',
        'admin_editable': True,
        'event_multipliers': {
            'battle_win': 1.0,
            'crocodile_win': 1.2,
            'crocodile_correct_guess': 1.1,
            'crocodile_participate': 1.0,
            'fishing': 1.0,
            'trap': 1.0
        }
    },
    'gdcards': {
        'base_rate': 2.0,
        'currency_name': 'points',
        'admin_editable': True,
        'rarity_multipliers': {
            'card_common': 1.0,
            'card_rare': 1.5,
            'card_epic': 2.0,
            'card_legendary': 3.0
        }
    },
    'true_mafia': {
        'base_rate': 15.0,
        'currency_name': 'wins',
        'admin_editable': True,
        'event_multipliers': {
            'game_win': 1.0,
            'game_participation': 0.3
        }
    },
    'bunkerrp': {
        'base_rate': 20.0,
        'currency_name': 'survivals',
        'admin_editable': True,
        'event_multipliers': {
            'bunker_survival': 1.0,
            'game_participation': 0.5
        }
    }
}


def update_currency_rate(game: str, new_rate: float) -> bool:
    """Обновление коэффициента валюты (в памяти)"""
    if game in ADVANCED_CURRENCY_CONFIG:
        ADVANCED_CURRENCY_CONFIG[game]['base_rate'] = new_rate
        return True
    return False


def get_currency_config() -> dict:
    """Получение текущей конфигурации валют"""
    return ADVANCED_CURRENCY_CONFIG.copy()
