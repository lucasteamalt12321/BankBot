"""Legacy adapter classes for backward compatibility with src/parsers.py.

All implementations live here and delegate to unified parsers where possible.
Do not use these classes in new code — use core/parsers/unified.py instead.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

import structlog

# Direct module imports to avoid circular dependency through __init__.py
from core.parsers.base import ParserError
from core.parsers.truemafia import TrueMafiaGameEndParser
from core.parsers.bunkerrp import BunkerRPGameEndParser

logger = structlog.get_logger()

__all__ = [
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


# ---------------------------------------------------------------------------
# Legacy dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ParsedProfile:
    """Structured data from GD Cards profile message."""

    player_name: str
    orbs: Decimal
    game: str = "GD Cards"


@dataclass
class ParsedAccrual:
    """Structured data from accrual message."""

    player_name: str
    points: Decimal
    game: str = "GD Cards"


@dataclass
class ParsedFishing:
    """Structured data from Shmalala fishing message."""

    player_name: str
    coins: Decimal
    game: str = "Shmalala"


@dataclass
class ParsedKarma:
    """Structured data from Shmalala karma message."""

    player_name: str
    karma: Decimal = field(default_factory=lambda: Decimal("1"))
    game: str = "Shmalala Karma"


@dataclass
class ParsedMafiaWinners:
    """Structured data from True Mafia game end message."""

    winners: list
    game: str = "True Mafia"


@dataclass
class ParsedMafiaProfile:
    """Structured data from True Mafia profile message."""

    player_name: str
    money: Decimal
    game: str = "True Mafia"


@dataclass
class ParsedBunkerWinners:
    """Structured data from Bunker RP game end message."""

    winners: list
    game: str = "Bunker RP"


@dataclass
class ParsedBunkerProfile:
    """Structured data from Bunker RP profile message."""

    player_name: str
    money: Decimal
    game: str = "Bunker RP"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class MessageParser(ABC):
    """Abstract base for message parsers."""

    @abstractmethod
    def parse(self, message: str) -> Union[ParsedProfile, ParsedAccrual]:
        """Parse message into structured data."""


# ---------------------------------------------------------------------------
# Concrete parsers
# ---------------------------------------------------------------------------

class ProfileParser(MessageParser):
    """Parses GD Cards profile messages to extract player name and orbs."""

    def parse(self, message: str) -> ParsedProfile:
        """Extract player name and orbs from GD Cards profile message.

        Args:
            message: Raw message text.

        Returns:
            ParsedProfile with extracted data.

        Raises:
            ParserError: If required fields are missing or invalid.
        """
        lines = message.splitlines()
        player_name: Optional[str] = None
        orbs: Optional[Decimal] = None

        for line in lines:
            stripped = line.strip()
            # Extract player name from ПРОФИЛЬ line
            if "ПРОФИЛЬ" in stripped or "Профиль" in stripped:
                keyword = "ПРОФИЛЬ" if "ПРОФИЛЬ" in stripped else "Профиль"
                after = stripped.split(keyword, 1)[1].strip().replace("─", "").strip()
                if after:
                    player_name = after
            # Extract orbs
            if stripped.startswith("Орбы:") or stripped.startswith("Орбы :"):
                sep = "Орбы :" if "Орбы :" in stripped else "Орбы:"
                raw = stripped.split(sep, 1)[1].strip()
                num_str = raw.split()[0] if raw.split() else ""
                try:
                    orbs = Decimal(num_str)
                except (InvalidOperation, IndexError):
                    raise ParserError(f"Invalid orbs value: {num_str!r}")

        if player_name is None:
            raise ParserError("Player name not found in profile message")
        if orbs is None:
            raise ParserError("Orbs field not found in profile message")

        return ParsedProfile(player_name=player_name, orbs=orbs, game="GD Cards")


class AccrualParser(MessageParser):
    """Parses GD Cards accrual messages to extract player name and points."""

    def parse(self, message: str) -> ParsedAccrual:
        """Extract player name and points from accrual message.

        Args:
            message: Raw message text.

        Returns:
            ParsedAccrual with extracted data.

        Raises:
            ParserError: If required fields are missing or invalid.
        """
        lines = message.splitlines()
        player_name: Optional[str] = None
        points: Optional[Decimal] = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Игрок:"):
                player_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Очки:"):
                raw = stripped.split(":", 1)[1].strip()
                if "+" not in raw:
                    raise ParserError(
                        f"Points field does not contain a plus sign and number: {raw!r}"
                    )
                num_str = raw.split("+", 1)[1].strip().split()[0]
                try:
                    points = Decimal(num_str)
                except (InvalidOperation, IndexError):
                    raise ParserError(f"Invalid points value: {num_str!r}")

        if player_name is None:
            raise ParserError("Player name not found in accrual message")
        if points is None:
            raise ParserError("Points field not found in accrual message")

        return ParsedAccrual(player_name=player_name, points=points, game="GD Cards")


class FishingParser(MessageParser):
    """Parses Shmalala fishing messages to extract player name and coins."""

    def parse(self, message: str) -> ParsedFishing:
        """Extract player name and coins from fishing message.

        Args:
            message: Raw message text.

        Returns:
            ParsedFishing with extracted data.

        Raises:
            ParserError: If required fields are missing or invalid.
        """
        lines = message.splitlines()
        player_name: Optional[str] = None
        coins: Optional[Decimal] = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Рыбак:"):
                player_name = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Монеты:"):
                raw = stripped.split(":", 1)[1].strip()
                if "+" not in raw:
                    raise ParserError(
                        f"Coins field not found or missing plus sign: {raw!r}"
                    )
                num_str = raw.split("+", 1)[1].strip().split()[0].rstrip("(")
                try:
                    coins = Decimal(num_str)
                except (InvalidOperation, IndexError):
                    raise ParserError(f"Invalid coins value: {num_str!r}")

        if player_name is None:
            raise ParserError("Player name not found in fishing message")
        if coins is None:
            raise ParserError("Coins field not found in fishing message")

        return ParsedFishing(player_name=player_name, coins=coins, game="Shmalala")


class KarmaParser(MessageParser):
    """Parses Shmalala karma messages to extract player name."""

    def parse(self, message: str) -> ParsedKarma:
        """Extract player name from karma message.

        Args:
            message: Raw message text.

        Returns:
            ParsedKarma with extracted data.

        Raises:
            ParserError: If player name is not found.
        """
        player_name: Optional[str] = None
        trigger = "Лайк! Вы повысили рейтинг пользователя"

        for line in message.splitlines():
            if trigger in line:
                after = line.split(trigger, 1)[1].strip()
                # Remove trailing dot and spaces
                after = after.rstrip(".").strip()
                if after:
                    player_name = after
                break

        if player_name is None:
            raise ParserError("Player name not found in karma message")

        return ParsedKarma(player_name=player_name, karma=Decimal("1"), game="Shmalala Karma")


class MafiaGameEndParser(MessageParser):
    """Parses True Mafia game end messages to extract winners."""

    def __init__(self) -> None:
        self._impl = TrueMafiaGameEndParser()

    def parse(self, message: str) -> ParsedMafiaWinners:
        """Extract winners list from True Mafia game end message.

        Args:
            message: Raw message text.

        Returns:
            ParsedMafiaWinners with extracted data.

        Raises:
            ParserError: If no winners found.
        """
        result = self._impl.parse(message)
        if result is None:
            raise ParserError("Failed to parse mafia game end message")
        return ParsedMafiaWinners(winners=result.winners, game=result.game)


class MafiaProfileParser(MessageParser):
    """Parses True Mafia profile messages to extract player name and money."""

    def parse(self, message: str) -> ParsedMafiaProfile:
        """Extract player name and money from True Mafia profile message.

        Args:
            message: Raw message text.

        Returns:
            ParsedMafiaProfile with extracted data.

        Raises:
            ParserError: If required fields are missing or invalid.
        """
        lines = message.splitlines()
        player_name: Optional[str] = None
        money: Optional[Decimal] = None

        for line in lines:
            stripped = line.strip()
            if "👤" in stripped and player_name is None:
                after = stripped.split("👤", 1)[1].strip()
                if after:
                    player_name = after
            if stripped.startswith("💵 Деньги:"):
                raw = stripped.split(":", 1)[1].strip()
                num_str = raw.split()[0] if raw.split() else ""
                try:
                    money = Decimal(num_str)
                except (InvalidOperation, IndexError):
                    raise ParserError(f"Invalid money value: {num_str!r}")

        if player_name is None:
            raise ParserError("Player name not found in mafia profile message")
        if money is None:
            raise ParserError("Money field not found in mafia profile message")

        return ParsedMafiaProfile(player_name=player_name, money=money, game="True Mafia")


class BunkerGameEndParser(MessageParser):
    """Parses BunkerRP game end messages to extract winners."""

    def __init__(self) -> None:
        self._impl = BunkerRPGameEndParser()

    def parse(self, message: str) -> ParsedBunkerWinners:
        """Extract winners list from Bunker RP game end message.

        Args:
            message: Raw message text.

        Returns:
            ParsedBunkerWinners with extracted data.

        Raises:
            ParserError: If no winners found.
        """
        result = self._impl.parse(message)
        if result is None:
            raise ParserError("Failed to parse bunker game end message")
        return ParsedBunkerWinners(winners=result.winners, game=result.game)


class BunkerProfileParser(MessageParser):
    """Parses BunkerRP profile messages to extract player name and money."""

    def parse(self, message: str) -> ParsedBunkerProfile:
        """Extract player name and money from Bunker RP profile message.

        Args:
            message: Raw message text.

        Returns:
            ParsedBunkerProfile with extracted data.

        Raises:
            ParserError: If required fields are missing or invalid.
        """
        lines = message.splitlines()
        player_name: Optional[str] = None
        money: Optional[Decimal] = None

        for line in lines:
            stripped = line.strip()
            if "👤" in stripped and player_name is None:
                after = stripped.split("👤", 1)[1].strip()
                if after:
                    player_name = after
            if stripped.startswith("💵 Деньги:"):
                raw = stripped.split(":", 1)[1].strip()
                num_str = raw.split()[0] if raw.split() else ""
                try:
                    money = Decimal(num_str)
                except (InvalidOperation, IndexError):
                    raise ParserError(f"Invalid money value: {num_str!r}")

        if player_name is None:
            raise ParserError("Player name not found in bunker profile message")
        if money is None:
            raise ParserError("Money field not found in bunker profile message")

        return ParsedBunkerProfile(player_name=player_name, money=money, game="Bunker RP")
