"""Unit tests for ParsedProfile and ParsedAccrual dataclasses."""

import pytest
from decimal import Decimal
from src.parsers import ParsedProfile, ParsedAccrual


class TestParsedProfile:
    """Tests for ParsedProfile dataclass."""
    
    def test_parsed_profile_creation(self):
        """Test creating a ParsedProfile with all fields."""
        profile = ParsedProfile(
            player_name="TestPlayer",
            orbs=Decimal("727.4"),
            game="GD Cards"
        )
        
        assert profile.player_name == "TestPlayer"
        assert profile.orbs == Decimal("727.4")
        assert profile.game == "GD Cards"
    
    def test_parsed_profile_default_game(self):
        """Test that game defaults to 'GD Cards'."""
        profile = ParsedProfile(
            player_name="TestPlayer",
            orbs=Decimal("100.5")
        )
        
        assert profile.game == "GD Cards"
    
    def test_parsed_profile_decimal_precision(self):
        """Test that Decimal type preserves precision."""
        profile = ParsedProfile(
            player_name="TestPlayer",
            orbs=Decimal("123.456789")
        )
        
        assert profile.orbs == Decimal("123.456789")
        assert str(profile.orbs) == "123.456789"
    
    def test_parsed_profile_integer_orbs(self):
        """Test ParsedProfile with integer orbs value."""
        profile = ParsedProfile(
            player_name="TestPlayer",
            orbs=Decimal("500")
        )
        
        assert profile.orbs == Decimal("500")


class TestParsedAccrual:
    """Tests for ParsedAccrual dataclass."""
    
    def test_parsed_accrual_creation(self):
        """Test creating a ParsedAccrual with all fields."""
        accrual = ParsedAccrual(
            player_name="TestPlayer",
            points=Decimal("5.5"),
            game="GD Cards"
        )
        
        assert accrual.player_name == "TestPlayer"
        assert accrual.points == Decimal("5.5")
        assert accrual.game == "GD Cards"
    
    def test_parsed_accrual_default_game(self):
        """Test that game defaults to 'GD Cards'."""
        accrual = ParsedAccrual(
            player_name="TestPlayer",
            points=Decimal("10")
        )
        
        assert accrual.game == "GD Cards"
    
    def test_parsed_accrual_decimal_precision(self):
        """Test that Decimal type preserves precision."""
        accrual = ParsedAccrual(
            player_name="TestPlayer",
            points=Decimal("2.123456")
        )
        
        assert accrual.points == Decimal("2.123456")
        assert str(accrual.points) == "2.123456"
    
    def test_parsed_accrual_integer_points(self):
        """Test ParsedAccrual with integer points value."""
        accrual = ParsedAccrual(
            player_name="TestPlayer",
            points=Decimal("3")
        )
        
        assert accrual.points == Decimal("3")
