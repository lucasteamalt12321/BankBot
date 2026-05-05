"""Unit tests for AccrualParser."""

import pytest
from decimal import Decimal
from src.parsers import AccrualParser, ParserError, ParsedAccrual


def test_parse_valid_accrual_message():
    """Test parsing a valid accrual message from the examples."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: LucasTeam
───────────────
Карта: "Zodiac"
Описание: Коллаб от Bianox, сместивший Crimson Planet с первой строчки сложнейших уровней. Хак-верифнут xander556, верифнут Technical'ом.
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────
Эта карта есть у: 1255 игроков
Лимит карт сегодня: 1 из 8"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert isinstance(result, ParsedAccrual)
    assert result.player_name == "LucasTeam"
    assert result.points == Decimal("3")
    assert result.game == "GD Cards"


def test_parse_accrual_with_decimal_points():
    """Test parsing accrual message with decimal points value."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: +2.5"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "TestPlayer"
    assert result.points == Decimal("2.5")


def test_parse_accrual_second_example():
    """Test parsing the second accrual message from examples."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: CrazyTimeI
───────────────
Карта: "Sevvend Clubstep"
Описание: Один из немногих сложный уровней от cherry, который нравится большинству игроков своим геймплеем. Верифицирован игроком Vorten.
Категория: Демоны
───────────────
Редкость: Редкая (4/64) (30.0%) 🔵
Очки: +2
Орбы за дроп: +5
Коллекция: 6/213 карт
───────────────
Эта карта есть у: 1530 игроков
Лимит карт сегодня: 1 из 8"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "CrazyTimeI"
    assert result.points == Decimal("2")


def test_parse_missing_player_name():
    """Test that missing player name raises ParserError."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Очки: +3"""

    parser = AccrualParser()
    with pytest.raises(ParserError, match="Player name not found"):
        parser.parse(message)


def test_parse_missing_points_field():
    """Test that missing points field raises ParserError."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────"""

    parser = AccrualParser()
    with pytest.raises(ParserError, match="Points field not found"):
        parser.parse(message)


def test_parse_points_without_plus_sign():
    """Test that points field without plus sign raises ParserError."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: 3"""

    parser = AccrualParser()
    with pytest.raises(ParserError, match="does not contain a plus sign and number"):
        parser.parse(message)


def test_parse_invalid_points_value():
    """Test that invalid points value raises ParserError."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: +abc"""

    parser = AccrualParser()
    with pytest.raises(ParserError, match="Invalid points value"):
        parser.parse(message)


def test_parse_points_with_negative_value():
    """Test parsing points with negative value (should work as it starts with +)."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: +0"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.points == Decimal("0")


def test_parse_accrual_preserves_decimal_precision():
    """Test that decimal precision is preserved for points."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: PrecisionPlayer
───────────────
Очки: +123.456789"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.points == Decimal("123.456789")
    assert str(result.points) == "123.456789"


def test_parse_accrual_with_large_points_value():
    """Test parsing accrual with large points value."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: HighScorer
───────────────
Очки: +999999.99"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "HighScorer"
    assert result.points == Decimal("999999.99")


def test_parse_accrual_with_special_characters_in_name():
    """Test parsing accrual with special characters in player name."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player_123-Test
───────────────
Очки: +5"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "Player_123-Test"
    assert result.points == Decimal("5")


def test_parse_accrual_with_whitespace_variations():
    """Test parsing accrual with various whitespace patterns."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок:    PlayerWithSpaces   
───────────────
Очки:    +100   """

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "PlayerWithSpaces"
    assert result.points == Decimal("100")


def test_parse_accrual_minimal_message():
    """Test parsing minimal valid accrual message."""
    message = """Игрок: MinimalPlayer
Очки: +3"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "MinimalPlayer"
    assert result.points == Decimal("3")


def test_parse_accrual_ignores_other_fields():
    """Test that parser ignores all other fields in accrual message."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Карта: "Test Card"
Описание: Some description
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────
Эта карта есть у: 1255 игроков
Лимит карт сегодня: 1 из 8"""

    parser = AccrualParser()
    result = parser.parse(message)

    # Should only extract player name and points
    assert result.player_name == "TestPlayer"
    assert result.points == Decimal("3")
    # Other fields should not be in the result
    assert not hasattr(result, 'card')
    assert not hasattr(result, 'rarity')


def test_parse_accrual_with_integer_points():
    """Test parsing accrual with integer points (no decimal point)."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: IntegerPlayer
───────────────
Очки: +10"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.player_name == "IntegerPlayer"
    assert result.points == Decimal("10")
    # Verify it's still a Decimal type
    assert isinstance(result.points, Decimal)


def test_parse_accrual_game_field():
    """Test that game field is correctly set to 'GD Cards'."""
    message = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: +5"""

    parser = AccrualParser()
    result = parser.parse(message)

    assert result.game == "GD Cards"
