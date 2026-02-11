"""
Unit tests for card message parsing functionality
Tests the integration of parsing_script.py logic
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.parsers.simple_parser import (
    SimpleShmalalaParser,
    parse_card_message,
    parse_game_message,
    ParsedCard
)


class TestCardParser:
    """Test suite for card message parsing"""
    
    def test_parse_valid_card_message(self):
        """Test parsing a valid card message"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @test_player
Карта: Легендарная
Очки: +150
Редкость: Epic"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert isinstance(result, ParsedCard)
        assert result.player_name == "@test_player"
        assert result.points == 150
    
    def test_parse_card_message_with_spaces(self):
        """Test parsing card message with extra spaces"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок:    @player_with_spaces   
Очки:   +   200   """
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.player_name == "@player_with_spaces"
        assert result.points == 200
    
    def test_parse_card_message_minimal(self):
        """Test parsing minimal card message"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @minimal
Очки: +1"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.player_name == "@minimal"
        assert result.points == 1
    
    def test_parse_card_message_large_points(self):
        """Test parsing card message with large points"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @rich_player
Очки: +9999"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.points == 9999
    
    def test_parse_invalid_card_message_no_header(self):
        """Test parsing message without card header"""
        message = """Игрок: @test
Очки: +100"""
        
        result = parse_card_message(message)
        
        assert result is None
    
    def test_parse_invalid_card_message_no_player(self):
        """Test parsing card message without player"""
        message = """🃏 НОВАЯ КАРТА 🃏
Очки: +100"""
        
        result = parse_card_message(message)
        
        assert result is None
    
    def test_parse_invalid_card_message_no_points(self):
        """Test parsing card message without points"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @test"""
        
        result = parse_card_message(message)
        
        assert result is None
    
    def test_parse_card_message_invalid_points_format(self):
        """Test parsing card message with invalid points format"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @test
Очки: +abc"""
        
        result = parse_card_message(message)
        
        assert result is None
    
    def test_parse_card_with_parser_class(self):
        """Test parsing using parser class directly"""
        parser = SimpleShmalalaParser()
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @direct_test
Очки: +500"""
        
        result = parser.parse_card_message(message)
        
        assert result is not None
        assert result.player_name == "@direct_test"
        assert result.points == 500


class TestUniversalParser:
    """Test suite for universal game message parsing"""
    
    def test_parse_game_message_card(self):
        """Test universal parser with card message"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @player
Очки: +100"""
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'card'
        assert result['user'] == '@player'
        assert result['amount'] == 100
    
    def test_parse_game_message_fishing(self):
        """Test universal parser with fishing message"""
        message = """🎣 [Рыбалка] 🎣
Рыбак: @fisher
Монеты: +50 (500)💰"""
        
        result = parse_game_message(message)
        
        assert result is not None
        assert result['type'] == 'fishing'
        assert result['user'] == '@fisher'
        assert result['amount'] == 50
    
    def test_parse_game_message_unknown(self):
        """Test universal parser with unknown message"""
        message = "Random message without game markers"
        
        result = parse_game_message(message)
        
        assert result is None
    
    def test_parse_game_message_returns_data(self):
        """Test that universal parser returns full data object"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @test
Очки: +200"""
        
        result = parse_game_message(message)
        
        assert result is not None
        assert 'data' in result
        assert isinstance(result['data'], ParsedCard)
        assert result['data'].points == 200


class TestCardParserEdgeCases:
    """Test edge cases for card parser"""
    
    def test_parse_card_multiline_player_name(self):
        """Test parsing with player name containing special characters"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @player_123_test
Очки: +100"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.player_name == "@player_123_test"
    
    def test_parse_card_zero_points(self):
        """Test parsing card with zero points"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @zero
Очки: +0"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.points == 0
    
    def test_parse_card_extra_lines(self):
        """Test parsing card message with extra information lines"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @player
Карта: Супер карта
Редкость: Legendary
Очки: +300
Бонус: x2
Описание: Очень редкая карта"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.player_name == "@player"
        assert result.points == 300
    
    def test_parse_card_raw_message_stored(self):
        """Test that raw message is stored in result"""
        message = """🃏 НОВАЯ КАРТА 🃏
Игрок: @test
Очки: +100"""
        
        result = parse_card_message(message)
        
        assert result is not None
        assert result.raw_message is not None
        assert len(result.raw_message) <= 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
