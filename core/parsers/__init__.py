"""
Unified parsing system for all games
"""

from .base import (
    BaseParser,
    ParseResult,
    ProfileResult,
    AccrualResult,
    GameEndResult,
    ParserError
)

from .registry import (
    ParserRegistry,
    get_registry,
    parse_message
)

# Backward compatibility with old simple_parser
from .simple_parser import (
    ParsedFishing,
    ParsedCard,
    ParsedProfile,
    ParsedOrbDrop,
    SimpleShmalalaParser,
    parse_game_message,
    parse_shmalala_message,
    parse_card_message,
    parse_fishing_message
)

__all__ = [
    # New unified system
    'BaseParser',
    'ParseResult',
    'ProfileResult',
    'AccrualResult',
    'GameEndResult',
    'ParserError',
    'ParserRegistry',
    'get_registry',
    'parse_message',
    
    # Old system (backward compatibility)
    'ParsedFishing',
    'ParsedCard',
    'ParsedProfile',
    'ParsedOrbDrop',
    'SimpleShmalalaParser',
    'parse_game_message',
    'parse_shmalala_message',
    'parse_card_message',
    'parse_fishing_message',
]
