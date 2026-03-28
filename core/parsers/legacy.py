"""Адаптеры обратной совместимости для старого интерфейса парсеров.

Предоставляет датаклассы и классы парсеров с интерфейсом parse(message),
совместимым с оригинальным src/parsers.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Union

from .base import ParserError
from .shmalala import ShmalalaFishingParser, ShmalalaKarmaParser
from .truemafia import TrueMafiaProfileParser, TrueMafiaGameEndParser
from .bunkerrp import BunkerRPProfileParser, BunkerRPGameEndParser


# ---------------------------------------------------------------------------
# Датаклассы (обратная совместимость)
# ---------------------------------------------------------------------------

@dataclass
class ParsedProfile:
    """Structured data from profile message."""
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
    karma: Decimal
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
    """Structured data from BunkerRP game end message."""
    winners: list
    game: str = "Bunker RP"


@dataclass
class ParsedBunkerProfile:
    """Structured data from BunkerRP profile message."""
    player_name: str
    money: Decimal
    game: str = "Bunker RP"


# ---------------------------------------------------------------------------
# Базовый класс (обратная совместимость)
# ---------------------------------------------------------------------------

class MessageParser(ABC):
    """Abstract base for message parsers."""

    @abstractmethod
    def parse(self, message: str) -> Union[ParsedProfile, ParsedAccrual]:
        """Parse message into structured data."""
        pass


# ---------------------------------------------------------------------------
# Адаптеры парсеров
# ---------------------------------------------------------------------------

class ProfileParser(MessageParser):
    """Parses profile messages to extract player name and orbs."""

    def parse(self, message: str) -> ParsedProfile:
        """Extract player name and orbs balance from profile message.

        Args:
            message: Raw profile message text

        Returns:
            ParsedProfile with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        player_name = None
        for line in lines:
            if "ПРОФИЛЬ" in line:
                parts = line.split("ПРОФИЛЬ")
                if len(parts) > 1 and parts[1].strip():
                    player_name = parts[1].strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in profile message")

        orbs = None
        for line in lines:
            if "Орбы:" in line:
                parts = line.split("Орбы:")
                if len(parts) > 1:
                    value_part = parts[1].strip().split()[0]
                    try:
                        orbs = Decimal(value_part)
                    except Exception:
                        raise ParserError(f"Invalid orbs value: {value_part}")
                    break

        if orbs is None:
            raise ParserError("Orbs field not found in profile message")

        return ParsedProfile(player_name=player_name, orbs=orbs)


class AccrualParser(MessageParser):
    """Parses accrual messages to extract player name and points."""

    def parse(self, message: str) -> ParsedAccrual:
        """Extract player name and points from accrual message.

        Args:
            message: Raw accrual message text

        Returns:
            ParsedAccrual with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        # Extract player name
        player_name = None
        for line in lines:
            if "Игрок:" in line:
                parts = line.split("Игрок:")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in accrual message")

        # Extract points
        points = None
        for line in lines:
            if "Очки:" in line:
                parts = line.split("Очки:")
                if len(parts) > 1:
                    value_part = parts[1].strip()
                    if not value_part.startswith("+"):
                        raise ParserError("Points field does not contain a plus sign and number")
                    try:
                        points = Decimal(value_part[1:].strip())
                    except Exception:
                        raise ParserError(f"Invalid points value: {value_part}")
                    break

        if points is None:
            raise ParserError("Points field not found in accrual message")

        return ParsedAccrual(player_name=player_name, points=points)


class FishingParser(MessageParser):
    """Parses Shmalala fishing messages to extract player name and coins."""

    def __init__(self):
        self._inner = ShmalalaFishingParser()

    def parse(self, message: str) -> ParsedFishing:
        """Extract player name and coins from fishing message.

        Args:
            message: Raw fishing message text

        Returns:
            ParsedFishing with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        player_name = None
        for line in lines:
            if "Рыбак:" in line:
                parts = line.split("Рыбак:")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in fishing message")

        coins = None
        for line in lines:
            if "Монеты:" in line and "+" in line:
                parts = line.split("Монеты:")
                if len(parts) > 1:
                    value_part = parts[1].strip()
                    if value_part.startswith("+"):
                        coin_str = value_part[1:].split("(")[0].strip()
                        try:
                            coins = Decimal(coin_str)
                        except Exception:
                            raise ParserError(f"Invalid coins value: {coin_str}")
                        break

        if coins is None:
            raise ParserError("Coins field not found in fishing message")

        return ParsedFishing(player_name=player_name, coins=coins)


class KarmaParser(MessageParser):
    """Parses Shmalala karma messages to extract player name.

    Karma accrual is always +1 regardless of the displayed total rating.
    """

    def __init__(self):
        self._inner = ShmalalaKarmaParser()

    def parse(self, message: str) -> ParsedKarma:
        """Extract player name from karma message.

        Args:
            message: Raw karma message text

        Returns:
            ParsedKarma with extracted data (karma is always 1)

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        player_name = None
        for line in lines:
            if "Лайк! Вы повысили рейтинг пользователя" in line:
                parts = line.split("пользователя")
                if len(parts) > 1:
                    player_name = parts[1].strip().rstrip('.').strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in karma message")

        return ParsedKarma(player_name=player_name, karma=Decimal("1"))


class MafiaGameEndParser(MessageParser):
    """Parses True Mafia game end messages to extract winners."""

    def __init__(self):
        self._inner = TrueMafiaGameEndParser()

    def parse(self, message: str) -> ParsedMafiaWinners:
        """Extract winner names from game end message.

        Args:
            message: Raw game end message text

        Returns:
            ParsedMafiaWinners with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        result = self._inner.parse(message)
        if result is None:
            raise ParserError("No winners found in mafia game end message")
        return ParsedMafiaWinners(winners=result.winners)


class MafiaProfileParser(MessageParser):
    """Parses True Mafia profile messages to extract player name and money."""

    def __init__(self):
        self._inner = TrueMafiaProfileParser()

    def parse(self, message: str) -> ParsedMafiaProfile:
        """Extract player name and money from profile message.

        Args:
            message: Raw profile message text

        Returns:
            ParsedMafiaProfile with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        player_name = None
        for line in lines:
            if "👤" in line:
                parts = line.split("👤")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in mafia profile message")

        money = None
        for line in lines:
            if "💵 Деньги:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    money_str = parts[1].strip()
                    try:
                        money = Decimal(money_str)
                    except Exception:
                        raise ParserError(f"Invalid money value: {money_str}")
                    break

        if money is None:
            raise ParserError("Money field not found in mafia profile message")

        return ParsedMafiaProfile(player_name=player_name, money=money)


class BunkerGameEndParser(MessageParser):
    """Parses BunkerRP game end messages to extract winners."""

    def __init__(self):
        self._inner = BunkerRPGameEndParser()

    def parse(self, message: str) -> ParsedBunkerWinners:
        """Extract winner names from game end message.

        Args:
            message: Raw game end message text

        Returns:
            ParsedBunkerWinners with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        result = self._inner.parse(message)
        if result is None:
            raise ParserError("No winners found in bunker game end message")
        return ParsedBunkerWinners(winners=result.winners)


class BunkerProfileParser(MessageParser):
    """Parses BunkerRP profile messages to extract player name and money."""

    def __init__(self):
        self._inner = BunkerRPProfileParser()

    def parse(self, message: str) -> ParsedBunkerProfile:
        """Extract player name and money from profile message.

        Args:
            message: Raw profile message text

        Returns:
            ParsedBunkerProfile with extracted data

        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')

        player_name = None
        for line in lines:
            if "👤" in line:
                parts = line.split("👤")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break

        if not player_name:
            raise ParserError("Player name not found in bunker profile message")

        money = None
        for line in lines:
            if "💵 Деньги:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    money_str = parts[1].strip()
                    try:
                        money = Decimal(money_str)
                    except Exception:
                        raise ParserError(f"Invalid money value: {money_str}")
                    break

        if money is None:
            raise ParserError("Money field not found in bunker profile message")

        return ParsedBunkerProfile(player_name=player_name, money=money)
