"""Unit tests for MafiaProfileParser.

Tests the parsing of True Mafia profile messages to extract player name and money.
"""

import pytest
from decimal import Decimal
from src.parsers import MafiaProfileParser, ParsedMafiaProfile, ParserError


class TestMafiaProfileParser:
    """Test suite for MafiaProfileParser."""

    @pytest.fixture
    def parser(self):
        """Create a MafiaProfileParser instance."""
        return MafiaProfileParser()

    def test_parse_basic_profile(self, parser):
        """Test parsing a basic profile message."""
        message = """👤 LucasTeam Luke

💵 Деньги: 930
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert isinstance(result, ParsedMafiaProfile)
        assert result.player_name == "LucasTeam Luke"
        assert result.money == Decimal("930")
        assert result.game == "True Mafia"

    def test_parse_player_name_extraction(self, parser):
        """Test that player name is correctly extracted from 👤 line."""
        message = """👤 Tidal Wave

💵 Деньги: 10
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 1"""

        result = parser.parse(message)

        assert result.player_name == "Tidal Wave"
        assert result.money == Decimal("10")

    def test_parse_player_name_with_spaces(self, parser):
        """Test parsing player names with multiple spaces."""
        message = """👤 Player Name With Spaces

💵 Деньги: 500
💎 Камни: 5

🛡 Защита: 1
📂 Документы: 2
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "Player Name With Spaces"
        assert result.money == Decimal("500")

    def test_parse_player_name_with_special_characters(self, parser):
        """Test parsing player names with special characters."""
        message = """👤 Player.Name_123

💵 Деньги: 1000
💎 Камни: 10

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 1"""

        result = parser.parse(message)

        assert result.player_name == "Player.Name_123"
        assert result.money == Decimal("1000")

    def test_parse_russian_player_name(self, parser):
        """Test parsing player names in Russian."""
        message = """👤 Игрок Русский

💵 Деньги: 250
💎 Камни: 3

🛡 Защита: 0
📂 Документы: 1
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "Игрок Русский"
        assert result.money == Decimal("250")

    def test_parse_decimal_money_value(self, parser):
        """Test parsing decimal money values."""
        message = """👤 TestPlayer

💵 Деньги: 123.45
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "TestPlayer"
        assert result.money == Decimal("123.45")

    def test_parse_zero_money(self, parser):
        """Test parsing profile with zero money."""
        message = """👤 NewPlayer

💵 Деньги: 0
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "NewPlayer"
        assert result.money == Decimal("0")

    def test_parse_large_money_value(self, parser):
        """Test parsing large money values."""
        message = """👤 RichPlayer

💵 Деньги: 999999
💎 Камни: 100

🛡 Защита: 10
📂 Документы: 5
🎎 Активная роль: 1"""

        result = parser.parse(message)

        assert result.player_name == "RichPlayer"
        assert result.money == Decimal("999999")

    def test_parse_handles_extra_whitespace(self, parser):
        """Test that parser handles extra whitespace correctly."""
        message = """👤    ExtraSpaces   

💵 Деньги:    100   
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "ExtraSpaces"
        assert result.money == Decimal("100")

    def test_parse_ignores_other_fields(self, parser):
        """Test that parser ignores other fields in the message."""
        message = """👤 IgnoreOthers

💵 Деньги: 500
💎 Камни: 10
🛡 Защита: 5
📂 Документы: 3
🎎 Активная роль: 1
🏆 Побед: 50
💀 Поражений: 20"""

        result = parser.parse(message)

        assert result.player_name == "IgnoreOthers"
        assert result.money == Decimal("500")

    def test_parse_missing_player_name_raises_error(self, parser):
        """Test that missing player name raises ParserError."""
        message = """💵 Деньги: 100
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_missing_money_field_raises_error(self, parser):
        """Test that missing money field raises ParserError."""
        message = """👤 TestPlayer

💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Money field not found" in str(exc_info.value)

    def test_parse_invalid_money_value_raises_error(self, parser):
        """Test that invalid money value raises ParserError."""
        message = """👤 TestPlayer

💵 Деньги: invalid
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Invalid money value" in str(exc_info.value)

    def test_parse_empty_player_name_raises_error(self, parser):
        """Test that empty player name raises ParserError."""
        message = """👤 

💵 Деньги: 100
💎 Камни: 0

🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_player_name_on_first_occurrence(self, parser):
        """Test that parser uses the first occurrence of 👤."""
        message = """👤 FirstPlayer

💵 Деньги: 100
💎 Камни: 0

👤 SecondPlayer should be ignored
🛡 Защита: 0
📂 Документы: 0
🎎 Активная роль: 0"""

        result = parser.parse(message)

        assert result.player_name == "FirstPlayer"
        assert result.money == Decimal("100")
