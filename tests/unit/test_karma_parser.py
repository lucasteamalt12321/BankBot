"""Unit tests for KarmaParser class."""

import pytest
from decimal import Decimal
from src.parsers import KarmaParser, ParserError, ParsedKarma


class TestKarmaParser:
    """Test suite for KarmaParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = KarmaParser()

    def test_parse_valid_karma_message(self):
        """Test parsing a valid karma message from examples."""
        message = """Лайк! Вы повысили рейтинг пользователя Никита .
Теперь его рейтинг: 11 ❤️"""

        result = self.parser.parse(message)

        assert isinstance(result, ParsedKarma)
        assert result.player_name == "Никита"
        assert result.karma == Decimal("1")
        assert result.game == "Shmalala Karma"

    def test_parse_karma_message_second_example(self):
        """Test parsing the second karma message from examples."""
        message = """Лайк! Вы повысили рейтинг пользователя LucasTeam Luke.
Теперь его рейтинг: 8 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "LucasTeam Luke"
        assert result.karma == Decimal("1")
        assert result.game == "Shmalala Karma"

    def test_parse_karma_always_returns_one(self):
        """Test that karma is always 1 regardless of displayed rating."""
        message = """Лайк! Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 999 ❤️"""

        result = self.parser.parse(message)

        # Karma should always be 1, not 999
        assert result.karma == Decimal("1")

    def test_parse_karma_ignores_rating_field(self):
        """Test that the 'Теперь его рейтинг:' field is ignored."""
        message1 = """Лайк! Вы повысили рейтинг пользователя Player1.
Теперь его рейтинг: 5 ❤️"""

        message2 = """Лайк! Вы повысили рейтинг пользователя Player2.
Теперь его рейтинг: 100 ❤️"""

        result1 = self.parser.parse(message1)
        result2 = self.parser.parse(message2)

        # Both should have karma = 1
        assert result1.karma == Decimal("1")
        assert result2.karma == Decimal("1")

    def test_parse_karma_missing_player_name(self):
        """Test that parser raises error when player name is missing."""
        message = """Теперь его рейтинг: 11 ❤️"""

        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_karma_with_simple_name(self):
        """Test parsing karma message with simple player name."""
        message = """Лайк! Вы повысили рейтинг пользователя Alice.
Теперь его рейтинг: 5 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "Alice"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_username_format(self):
        """Test parsing karma message with @username format."""
        message = """Лайк! Вы повысили рейтинг пользователя @username123.
Теперь его рейтинг: 7 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "@username123"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_special_characters_in_name(self):
        """Test parsing karma message with special characters in player name."""
        message = """Лайк! Вы повысили рейтинг пользователя Player_123-Test.
Теперь его рейтинг: 10 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "Player_123-Test"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_whitespace_in_name(self):
        """Test parsing karma message with whitespace in player name."""
        message = """Лайк! Вы повысили рейтинг пользователя John Doe.
Теперь его рейтинг: 15 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "John Doe"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_trailing_spaces(self):
        """Test parsing karma message with trailing spaces in player name."""
        message = """Лайк! Вы повысили рейтинг пользователя Никита   .
Теперь его рейтинг: 11 ❤️"""

        result = self.parser.parse(message)

        # Should strip trailing spaces
        assert result.player_name == "Никита"
        assert result.karma == Decimal("1")

    def test_parse_karma_minimal_message(self):
        """Test parsing minimal valid karma message."""
        message = """Лайк! Вы повысили рейтинг пользователя MinimalUser."""

        result = self.parser.parse(message)

        assert result.player_name == "MinimalUser"
        assert result.karma == Decimal("1")

    def test_parse_karma_without_rating_line(self):
        """Test parsing karma message without the rating line."""
        message = """Лайк! Вы повысили рейтинг пользователя TestUser."""

        result = self.parser.parse(message)

        assert result.player_name == "TestUser"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_extra_lines(self):
        """Test parsing karma message with extra lines."""
        message = """Лайк! Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 20 ❤️
Дополнительная информация
Еще одна строка"""

        result = self.parser.parse(message)

        assert result.player_name == "TestPlayer"
        assert result.karma == Decimal("1")

    def test_parse_karma_game_field(self):
        """Test that game field is correctly set to 'Shmalala Karma'."""
        message = """Лайк! Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 10 ❤️"""

        result = self.parser.parse(message)

        assert result.game == "Shmalala Karma"

    def test_parse_karma_returns_decimal_type(self):
        """Test that karma value is returned as Decimal type."""
        message = """Лайк! Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 10 ❤️"""

        result = self.parser.parse(message)

        assert isinstance(result.karma, Decimal)
        assert result.karma == Decimal("1")

    def test_parse_karma_with_cyrillic_name(self):
        """Test parsing karma message with Cyrillic characters in name."""
        message = """Лайк! Вы повысили рейтинг пользователя Олег Чекмарев.
Теперь его рейтинг: 17 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "Олег Чекмарев"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_mixed_language_name(self):
        """Test parsing karma message with mixed language characters."""
        message = """Лайк! Вы повысили рейтинг пользователя Иван Smith.
Теперь его рейтинг: 12 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "Иван Smith"
        assert result.karma == Decimal("1")

    def test_parse_karma_with_emoji_in_name(self):
        """Test parsing karma message with emoji in player name."""
        message = """Лайк! Вы повысили рейтинг пользователя Player🎮.
Теперь его рейтинг: 5 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "Player🎮"
        assert result.karma == Decimal("1")

    def test_parse_karma_malformed_message(self):
        """Test that parser raises error for malformed message."""
        message = """Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 10 ❤️"""

        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_karma_empty_message(self):
        """Test that parser raises error for empty message."""
        message = ""

        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)

        assert "Player name not found" in str(exc_info.value)

    def test_parse_karma_with_zero_rating(self):
        """Test parsing karma message with zero rating (karma still 1)."""
        message = """Лайк! Вы повысили рейтинг пользователя NewPlayer.
Теперь его рейтинг: 0 ❤️"""

        result = self.parser.parse(message)

        assert result.player_name == "NewPlayer"
        # Karma is always 1, regardless of rating
        assert result.karma == Decimal("1")
