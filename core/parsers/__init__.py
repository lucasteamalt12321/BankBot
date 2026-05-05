"""
Unified parsing system for all games
"""

from .base import (
    BaseParser,
    ParseResult,
    ProfileResult,
    AccrualResult,
    GameEndResult,
    ParserError,
)

from .registry import (
    ParserRegistry,
    get_registry,
    parse_message,
)

# Unified parser — единая точка входа для всех форматов
from .unified import UnifiedParser, parse as parse_unified

# Backward compatibility with old simple_parser
from .simple_parser import (
    ParsedCard,
    ParsedOrbDrop,
    SimpleShmalalaParser,
    parse_game_message,
    parse_shmalala_message,
    parse_card_message,
    parse_fishing_message,
)

# Legacy adapter classes (src/parsers.py compatibility)
from .legacy import (
    MessageParser,
    ParsedProfile,
    ParsedAccrual,
    ParsedFishing,
    ParsedKarma,
    ParsedMafiaWinners,
    ParsedMafiaProfile,
    ParsedBunkerWinners,
    ParsedBunkerProfile,
    ProfileParser,
    AccrualParser,
    FishingParser,
    KarmaParser,
    MafiaGameEndParser,
    MafiaProfileParser,
    BunkerGameEndParser,
    BunkerProfileParser,
)

__all__ = [
    # New unified system
    "BaseParser",
    "ParseResult",
    "ProfileResult",
    "AccrualResult",
    "GameEndResult",
    "ParserError",
    "ParserRegistry",
    "get_registry",
    "parse_message",
    # Unified parser (single entry point)
    "UnifiedParser",
    "parse_unified",
    # Old simple_parser (backward compatibility)
    "ParsedCard",
    "ParsedOrbDrop",
    "SimpleShmalalaParser",
    "parse_game_message",
    "parse_shmalala_message",
    "parse_card_message",
    "parse_fishing_message",
    # Legacy adapter classes (src/parsers.py compatibility)
    "MessageParser",
    "ParsedProfile",
    "ParsedAccrual",
    "ParsedFishing",
    "ParsedKarma",
    "ParsedMafiaWinners",
    "ParsedMafiaProfile",
    "ParsedBunkerWinners",
    "ParsedBunkerProfile",
    "ProfileParser",
    "AccrualParser",
    "FishingParser",
    "KarmaParser",
    "MafiaGameEndParser",
    "MafiaProfileParser",
    "BunkerGameEndParser",
    "BunkerProfileParser",
]
