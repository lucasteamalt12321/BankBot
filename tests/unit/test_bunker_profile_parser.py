"""Unit tests for BunkerProfileParser.

Tests the parsing of BunkerRP profile messages to extract player name and money.
"""

import pytest
from decimal import Decimal
from src.parsers import BunkerProfileParser, ParsedBunkerProfile, ParserError


class TestBunkerProfileParser:
    """Test suite for BunkerProfileParser."""

    @pytest.fixture
    def parser(self):
        """Create a BunkerProfileParser instance."""
        return BunkerProfileParser()

    def test_parse_basic_profile(self, parser):
        """Test parsing a basic profile message."""
        message = """👤 LucasTeam

💵 Деньги: 300
💎 Кристаллики: 0

Экстры:
🛡 Защита от изгнания: 0
🃏 Вторая карта действий: 0

🎯 Побед: 7 (с финалом: 1)
🎲 Всего игр: 16 (с финалом: 1)"""

        result = parser.parse(message)

        assert isinstance(result, ParsedBunkerProfile)
        assert result.player_name == "LucasTeam"
        assert result.money == Decimal("300")
        assert result.game == "Bunker RP"

    def test_parse_player_name_extraction(self, parser):
        """Test that player name is correctly extracted from 👤 line."""
        message = """👤 Tidal Wave

💵 Деньги: 10
💎 Кристаллики: 0

🎯 Побед: 1"""

        result = parser.parse(message)

        assert result.player_name == "Tidal Wave"
        assert result.money == Decimal("10")

    def test_parse_player_name_with_spaces(self, parser):
        """Test parsing player names with multiple spaces."""
        message = """👤 Player Name With Spaces

💵 Деньги: 500
💎 Кристаллики: 5

🎯 Побед: 10"""

        result = parser.parse(message)

        assert result.player_name == "Player Name With Spaces"
        assert result.money == Decimal("500")

    def test_parse_player_name_with_special_characters(self, parser):
        """Test parsing player names with special characters."""
        message = """👤 Player.Name_123

💵 Деньги: 1000
💎 Кристаллики: 10

🎯 Побед: 5"""

        result = parser.parse(message)

        assert result.player_name == "Player.Name_123"
        assert result.money == Decimal("1000")

    def test_parse_russian_player_name(self, parser):
        """Test parsing player names in Russian."""
        message = """👤 Игрок Русский

💵 Деньги: 250
💎 Кристаллики: 3

🎯 Побед: 2"""

        result = parser.parse(message)

        assert result.player_name == "Игрок Русский"
        assert result.money == Decimal("250")

    def test_parse_decimal_money_value(self, parser):
        """Test parsing decimal money values."""
        message = """👤 TestPlayer

💵 Деньги: 123.45
💎 Кристаллики: 0

🎯 Побед: 0"""

        result = parser.parse(message)

        assert result.player_name == "TestPlayer"
        assert result.money == Decimal("123.45")

    def test_parse_zero_money(self, parser):
        """Test parsing profile with zero money."""
        message = """👤 NewPlayer

💵 Деньги: 0
💎 Кристаллики: 0

🎯 Побед: 0"""

        result = parser.parse(message)

        assert result.player_name == "NewPlayer"
        assert result.money == Decimal("0")

    def test_parse_large_money_value(self, parser):
        """Test parsing large money values."""
        message = """👤 RichPlayer

💵 Деньги: 999999
💎 Кристаллики: 100

🎯 Побед: 50"""

        result = parser.parse(message)

        assert result.player_name == "RichPlayer"
        assert result.money == Decimal("999999")

    def test_parse_handles_extra_whitespace(self, parser):
        """Test that parser handles extra whitespace correctly."""
        message = """👤    ExtraSpaces   

💵 Деньги:    100   
💎 Кристаллики: 0

🎯 Побед: 0"""

        result = parser.parse(message)

        assert result.player_name == "ExtraSpaces"
        assert result.money == Decimal("100")

    def test_parse_ignores_other_fields(self, parser):
        """Test that parser ignores other fields in the message."""
        message = """👤 IgnoreOthers

💵 Деньги: 500
💎 Кристаллики: 10
🛡 Защита от изгнания: 5
🃏 Вторая карта действий: 3
🎯 Побед: 15 (с финалом: 5)
🎲 Всего игр: 30 (с финалом: 5)"""

        result = parser.parse(message)

        assert result.player_name == "IgnoreOthers"
        assert result.money == Decimal("500")

    def test_parse_missing_player_name_raises_error(self, parser):
        """Test that missing player name raises ParserError."""
        message = """💵 Деньги: 100
💎 Кристаллики: 0

🎯 Побед: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_missing_money_field_raises_error(self, parser):
        """Test that missing money field raises ParserError."""
        message = """👤 TestPlayer

💎 Кристаллики: 0

🎯 Побед: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Money field not found" in str(exc_info.value)

    def test_parse_invalid_money_value_raises_error(self, parser):
        """Test that invalid money value raises ParserError."""
        message = """👤 TestPlayer

💵 Деньги: invalid
💎 Кристаллики: 0

🎯 Побед: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Invalid money value" in str(exc_info.value)

    def test_parse_empty_player_name_raises_error(self, parser):
        """Test that empty player name raises ParserError."""
        message = """👤 

💵 Деньги: 100
💎 Кристаллики: 0

🎯 Побед: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_player_name_on_first_occurrence(self, parser):
        """Test that parser uses the first occurrence of 👤."""
        message = """👤 FirstPlayer

💵 Деньги: 100
💎 Кристаллики: 0

👤 SecondPlayer should be ignored
🎯 Побед: 0"""

        result = parser.parse(message)

        assert result.player_name == "FirstPlayer"
        assert result.money == Decimal("100")
