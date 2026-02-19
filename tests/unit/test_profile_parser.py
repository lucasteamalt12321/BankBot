"""Unit tests for ProfileParser class."""

import pytest
from decimal import Decimal
from src.parsers import ProfileParser, ParserError, ParsedProfile


class TestProfileParser:
    """Test suite for ProfileParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ProfileParser()
    
    def test_parse_valid_profile_message(self):
        """Test parsing a valid profile message."""
        message = """GDcards, [12.02.2026 15:55]
ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 10 (#342)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
        
        result = self.parser.parse(message)
        
        assert isinstance(result, ParsedProfile)
        assert result.player_name == "LucasTeam"
        assert result.orbs == Decimal("10")
        assert result.game == "GD Cards"
    
    def test_parse_profile_with_decimal_orbs(self):
        """Test parsing profile with decimal orbs value."""
        message = """ПРОФИЛЬ TestPlayer
───────────────
Орбы: 727.4 (#100)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "TestPlayer"
        assert result.orbs == Decimal("727.4")
    
    def test_parse_profile_missing_player_name(self):
        """Test that parser raises error when player name is missing."""
        message = """ПРОФИЛЬ
───────────────
Орбы: 10 (#342)
───────────────"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Player name not found" in str(exc_info.value)
    
    def test_parse_profile_missing_orbs_field(self):
        """Test that parser raises error when Орбы field is missing."""
        message = """ПРОФИЛЬ TestPlayer
───────────────
Очки: 364 (#701)
───────────────"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Orbs field not found" in str(exc_info.value)
    
    def test_parse_profile_invalid_orbs_value(self):
        """Test that parser raises error when orbs value is malformed."""
        message = """ПРОФИЛЬ TestPlayer
───────────────
Орбы: invalid (#342)
───────────────"""
        
        with pytest.raises(ParserError) as exc_info:
            self.parser.parse(message)
        
        assert "Invalid orbs value" in str(exc_info.value)
    
    def test_parse_profile_preserves_decimal_precision(self):
        """Test that decimal precision is preserved."""
        message = """ПРОФИЛЬ TestPlayer
───────────────
Орбы: 123.456789 (#1)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.orbs == Decimal("123.456789")
        # Verify precision is maintained
        assert str(result.orbs) == "123.456789"
    
    def test_parse_profile_ignores_other_fields(self):
        """Test that parser ignores all other fields."""
        message = """ПРОФИЛЬ TestPlayer
───────────────
ID: 8685 (23.08.2025)
Ник: TestPlayer
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 50 (#342)
Клан: TestClan (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
        
        result = self.parser.parse(message)
        
        # Should only extract player name and orbs
        assert result.player_name == "TestPlayer"
        assert result.orbs == Decimal("50")
        # Other fields should not be in the result
        assert not hasattr(result, 'id')
        assert not hasattr(result, 'clan')
    
    def test_parse_profile_with_zero_orbs(self):
        """Test parsing profile with zero orbs value."""
        message = """ПРОФИЛЬ NewPlayer
───────────────
Орбы: 0 (#999)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "NewPlayer"
        assert result.orbs == Decimal("0")
    
    def test_parse_profile_with_large_orbs_value(self):
        """Test parsing profile with large orbs value."""
        message = """ПРОФИЛЬ RichPlayer
───────────────
Орбы: 999999.99 (#1)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "RichPlayer"
        assert result.orbs == Decimal("999999.99")
    
    def test_parse_profile_with_special_characters_in_name(self):
        """Test parsing profile with special characters in player name."""
        message = """ПРОФИЛЬ Player_123-Test
───────────────
Орбы: 42 (#100)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "Player_123-Test"
        assert result.orbs == Decimal("42")
    
    def test_parse_profile_with_whitespace_variations(self):
        """Test parsing profile with various whitespace patterns."""
        message = """ПРОФИЛЬ    PlayerWithSpaces   
───────────────
Орбы:    100    (#50)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "PlayerWithSpaces"
        assert result.orbs == Decimal("100")
    
    def test_parse_profile_minimal_message(self):
        """Test parsing minimal valid profile message."""
        message = """ПРОФИЛЬ MinimalPlayer
Орбы: 5"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "MinimalPlayer"
        assert result.orbs == Decimal("5")
    
    def test_parse_profile_with_integer_orbs(self):
        """Test parsing profile with integer orbs (no decimal point)."""
        message = """ПРОФИЛЬ IntegerPlayer
───────────────
Орбы: 100 (#50)
───────────────"""
        
        result = self.parser.parse(message)
        
        assert result.player_name == "IntegerPlayer"
        assert result.orbs == Decimal("100")
        # Verify it's still a Decimal type
        assert isinstance(result.orbs, Decimal)
