"""Unit tests for FishingParser class."""

import pytest
from decimal import Decimal
from src.parsers import FishingParser, ParserError, ParsedFishing


class TestFishingParser:
    """Test suite for FishingParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = FishingParser()
    
    def test_parse_valid_fishing_message(self):
        """Test parsing a valid fishing message."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: Crazy Time
Улов: Золотая рыбка
Монеты: +5 (225)💰"""
        
        result = self.parser.parse(message)
        
        assert isinstance(result, ParsedFishing)
        assert result.player_name == "Crazy Time"
        assert result.coins == Decimal("5")
        assert result.game == "Shmalala"
    
    def test_parse_fishing_with_decimal_coins(self):
        """Test parsing fishing message with decimal coins value."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Обычная рыба
Монеты: +12.5 (100.5)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "TestPlayer"
        assert result.coins == Decimal("12.5")
    
    def test_parse_fishing_with_username(self):
        """Test parsing fishing message with @username format."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: @username123
Улов: Редкая рыба
Монеты: +50 (150)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "@username123"
        assert result.coins == Decimal("50")
    
    def test_parse_fishing_missing_player_name(self):
        """Test that parser raises error when player name is missing."""
        message = """🎣 [Рыбалка] 🎣

Улов: Золотая рыбка
Монеты: +5 (225)💰"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Player name not found" in str(exc_info.value)
    
    def test_parse_fishing_missing_coins_field(self):
        """Test that parser raises error when Монеты field is missing."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Coins field not found" in str(exc_info.value)
    
    def test_parse_fishing_invalid_coins_value(self):
        """Test that parser raises error when coins value is malformed."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: +invalid (225)💰"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Invalid coins value" in str(exc_info.value)
    
    def test_parse_fishing_extracts_accrual_not_total(self):
        """Test that parser extracts only the accrual amount, not the total in parentheses."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: +75 (1000)💰"""
        
        result = self.parser.parse(message)
        
        # Should extract 75 (accrual), not 1000 (total)
        assert result.coins == Decimal("75")
    
    def test_parse_fishing_preserves_decimal_precision(self):
        """Test that decimal precision is preserved."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: +123.456789 (500)💰"""
        
        result = self.parser.parse(message)
        
        assert result.coins == Decimal("123.456789")
        # Verify precision is maintained
        assert str(result.coins) == "123.456789"
    
    def test_parse_fishing_with_large_coins_value(self):
        """Test parsing fishing message with large coins value."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: RichFisher
Улов: Легендарная рыба
Монеты: +999999.99 (1000000)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "RichFisher"
        assert result.coins == Decimal("999999.99")
    
    def test_parse_fishing_with_special_characters_in_name(self):
        """Test parsing fishing message with special characters in player name."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: Player_123-Test
Улов: Обычная рыба
Монеты: +42 (100)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "Player_123-Test"
        assert result.coins == Decimal("42")
    
    def test_parse_fishing_with_whitespace_variations(self):
        """Test parsing fishing message with various whitespace patterns."""
        message = """🎣 [Рыбалка] 🎣

Рыбак:    PlayerWithSpaces   
Улов: Обычная рыба
Монеты:    +100    (500)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "PlayerWithSpaces"
        assert result.coins == Decimal("100")
    
    def test_parse_fishing_minimal_message(self):
        """Test parsing minimal valid fishing message."""
        message = """🎣 [Рыбалка] 🎣
Рыбак: MinimalFisher
Монеты: +5 (10)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "MinimalFisher"
        assert result.coins == Decimal("5")
    
    def test_parse_fishing_with_integer_coins(self):
        """Test parsing fishing message with integer coins (no decimal point)."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: IntegerFisher
Улов: Обычная рыба
Монеты: +100 (500)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "IntegerFisher"
        assert result.coins == Decimal("100")
        # Verify it's still a Decimal type
        assert isinstance(result.coins, Decimal)
    
    def test_parse_fishing_without_plus_sign(self):
        """Test that parser raises error when coins field doesn't have plus sign."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: 75 (225)💰"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Coins field not found" in str(exc_info.value)
    
    def test_parse_fishing_with_zero_coins(self):
        """Test parsing fishing message with zero coins value."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: UnluckyFisher
Улов: Ничего
Монеты: +0 (100)💰"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "UnluckyFisher"
        assert result.coins == Decimal("0")
    
    def test_parse_fishing_ignores_other_fields(self):
        """Test that parser ignores all other fields."""
        message = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Редкость: Легендарная
Вес: 5 кг
Монеты: +50 (500)💰
Опыт: +10"""
        
        result = self.parser.parse(message)
        
        # Should only extract player name and coins
        assert result.player_name == "TestPlayer"
        assert result.coins == Decimal("50")
        # Other fields should not be in the result
        assert not hasattr(result, 'catch')
        assert not hasattr(result, 'rarity')
        assert not hasattr(result, 'weight')
