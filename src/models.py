"""Data models for balance tracking."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class MessageType(Enum):
    """Enum representing all supported message types across 5 games."""
    # GD Cards
    GDCARDS_PROFILE = "gdcards_profile"
    GDCARDS_ACCRUAL = "gdcards_accrual"
    
    # Shmalala
    SHMALALA_FISHING = "shmalala_fishing"
    SHMALALA_FISHING_TOP = "shmalala_fishing_top"
    SHMALALA_KARMA = "shmalala_karma"
    SHMALALA_KARMA_TOP = "shmalala_karma_top"
    
    # True Mafia
    TRUEMAFIA_GAME_END = "truemafia_game_end"
    TRUEMAFIA_PROFILE = "truemafia_profile"
    
    # BunkerRP
    BUNKERRP_GAME_END = "bunkerrp_game_end"
    BUNKERRP_PROFILE = "bunkerrp_profile"
    
    UNKNOWN = "unknown"


@dataclass
class BotBalance:
    """Bot balance record for a player in a specific game."""
    user_id: str
    game: str
    last_balance: Decimal
    current_bot_balance: Decimal


@dataclass
class UserBalance:
    """User's general bank balance."""
    user_id: str
    user_name: str
    bank_balance: Decimal
