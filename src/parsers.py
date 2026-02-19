"""Message parsing components for the message parsing system.

This module provides the base classes and exceptions for parsing game-related
messages. It defines the abstract interface that all message parsers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


class ParserError(Exception):
    """Raised when parsing fails."""
    pass


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
    winners: list  # List of player names
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
    winners: list  # List of player names
    game: str = "Bunker RP"


@dataclass
class ParsedBunkerProfile:
    """Structured data from BunkerRP profile message."""
    player_name: str
    money: Decimal
    game: str = "Bunker RP"


class MessageParser(ABC):
    """Abstract base for message parsers."""
    
    @abstractmethod
    def parse(self, message: str) -> ParsedProfile | ParsedAccrual:
        """Parse message into structured data."""
        pass


class ProfileParser(MessageParser):
    """Parses profile messages to extract player name and orbs."""
    
    def parse(self, message: str) -> ParsedProfile:
        """
        Extract player name and orbs balance from profile message.
        
        Args:
            message: Raw profile message text
            
        Returns:
            ParsedProfile with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        # Extract player name from first line after "ПРОФИЛЬ"
        player_name = None
        for line in lines:
            if "ПРОФИЛЬ" in line:
                # Player name is on the same line after "ПРОФИЛЬ"
                parts = line.split("ПРОФИЛЬ")
                if len(parts) > 1 and parts[1].strip():
                    player_name = parts[1].strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in profile message")
        
        # Extract orbs value
        orbs = None
        for line in lines:
            if "Орбы:" in line:
                # Extract number after "Орбы:"
                parts = line.split("Орбы:")
                if len(parts) > 1:
                    # Extract numeric value (may include decimal and rank info)
                    value_part = parts[1].strip().split()[0]  # Get first token
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
        """
        Extract player name and points from accrual message.
        
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
                    # Check if it contains a plus sign
                    if not value_part.startswith("+"):
                        raise ParserError("Points field does not contain a plus sign and number")
                    try:
                        # Extract numeric value after the plus sign
                        points = Decimal(value_part[1:].strip())
                    except Exception:
                        raise ParserError(f"Invalid points value: {value_part}")
                    break
        
        if points is None:
            raise ParserError("Points field not found in accrual message")
        
        return ParsedAccrual(player_name=player_name, points=points)



class FishingParser(MessageParser):
    """Parses Shmalala fishing messages to extract player name and coins."""
    
    def parse(self, message: str) -> ParsedFishing:
        """
        Extract player name and coins from fishing message.
        
        Args:
            message: Raw fishing message text
            
        Returns:
            ParsedFishing with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        # Extract player name from "Рыбак:" field
        player_name = None
        for line in lines:
            if "Рыбак:" in line:
                parts = line.split("Рыбак:")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in fishing message")
        
        # Extract coins from "Монеты: +" field
        coins = None
        for line in lines:
            if "Монеты:" in line and "+" in line:
                parts = line.split("Монеты:")
                if len(parts) > 1:
                    value_part = parts[1].strip()
                    if value_part.startswith("+"):
                        # Extract number before the parenthesis
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
    The "Теперь его рейтинг:" field is ignored as per requirements.
    """
    
    def parse(self, message: str) -> ParsedKarma:
        """
        Extract player name from karma message.
        
        Args:
            message: Raw karma message text
            
        Returns:
            ParsedKarma with extracted data (karma is always 1)
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        # Extract player name from "Лайк! Вы повысили рейтинг пользователя" line
        player_name = None
        for line in lines:
            if "Лайк! Вы повысили рейтинг пользователя" in line:
                parts = line.split("пользователя")
                if len(parts) > 1:
                    # Remove trailing dot and spaces
                    player_name = parts[1].strip().rstrip('.').strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in karma message")
        
        # Karma accrual is always +1 (ignore the "Теперь его рейтинг:" field value)
        return ParsedKarma(player_name=player_name, karma=Decimal("1"))


class MafiaGameEndParser(MessageParser):
    """Parses True Mafia game end messages to extract winners."""
    
    def parse(self, message: str) -> ParsedMafiaWinners:
        """
        Extract winner names from game end message.
        
        Args:
            message: Raw game end message text
            
        Returns:
            ParsedMafiaWinners with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        winners = []
        in_winners_section = False
        
        for line in lines:
            if "Победители:" in line:
                in_winners_section = True
                continue
            elif "Остальные участники:" in line:
                in_winners_section = False
                break
            
            if in_winners_section and line.strip():
                # Extract player name before the dash
                if " - " in line:
                    player_name = line.split(" - ")[0].strip()
                    if player_name:
                        winners.append(player_name)
        
        if not winners:
            raise ParserError("No winners found in mafia game end message")
        
        return ParsedMafiaWinners(winners=winners)


class MafiaProfileParser(MessageParser):
    """Parses True Mafia profile messages to extract player name and money."""
    
    def parse(self, message: str) -> ParsedMafiaProfile:
        """
        Extract player name and money from profile message.
        
        Args:
            message: Raw profile message text
            
        Returns:
            ParsedMafiaProfile with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        # Extract player name from first line with 👤
        player_name = None
        for line in lines:
            if "👤" in line:
                parts = line.split("👤")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in mafia profile message")
        
        # Extract money from "💵 Деньги:" field
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
    
    def parse(self, message: str) -> ParsedBunkerWinners:
        """
        Extract winner names from game end message.
        
        Args:
            message: Raw game end message text
            
        Returns:
            ParsedBunkerWinners with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        winners = []
        in_winners_section = False
        
        for line in lines:
            if "Прошли в бункер:" in line:
                in_winners_section = True
                continue
            elif "Не прошли в бункер:" in line:
                in_winners_section = False
                break
            
            if in_winners_section:
                # Lines starting with numbers are player entries
                line_stripped = line.strip()
                if line_stripped and line_stripped[0].isdigit() and ". " in line_stripped:
                    # Extract player name after the number
                    player_name = line_stripped.split(". ", 1)[1].strip()
                    if player_name:
                        winners.append(player_name)
        
        if not winners:
            raise ParserError("No winners found in bunker game end message")
        
        return ParsedBunkerWinners(winners=winners)


class BunkerProfileParser(MessageParser):
    """Parses BunkerRP profile messages to extract player name and money."""
    
    def parse(self, message: str) -> ParsedBunkerProfile:
        """
        Extract player name and money from profile message.
        
        Args:
            message: Raw profile message text
            
        Returns:
            ParsedBunkerProfile with extracted data
            
        Raises:
            ParserError: If required fields are missing or malformed
        """
        lines = message.strip().split('\n')
        
        # Extract player name from first line with 👤
        player_name = None
        for line in lines:
            if "👤" in line:
                parts = line.split("👤")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in bunker profile message")
        
        # Extract money from "💵 Деньги:" field
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
