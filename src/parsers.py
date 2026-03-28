"""Message parsing components for the message parsing system.

Re-exports all parser classes and data types from the unified core/parsers package.
Maintained for backward compatibility — all implementations live in core/parsers/.
"""

from core.parsers import (
    ParserError,
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
    "ParserError",
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
