"""Unit tests for MafiaGameEndParser.

Tests the parsing of True Mafia game end messages to extract winner names.
"""

import pytest
from decimal import Decimal
from src.parsers import MafiaGameEndParser, ParsedMafiaWinners, ParserError


class TestMafiaGameEndParser:
    """Test suite for MafiaGameEndParser."""
    
    @pytest.fixture
    def parser(self):
        """Create a MafiaGameEndParser instance."""
        return MafiaGameEndParser()
    
    def test_parse_single_winner(self, parser):
        """Test parsing a game end message with a single winner."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Player1 - 👨🏼 Мирный житель 

Остальные участники: 
    Player2 - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert isinstance(result, ParsedMafiaWinners)
        assert result.game == "True Mafia"
        assert len(result.winners) == 1
        assert result.winners[0] == "Player1"
    
    def test_parse_multiple_winners(self, parser):
        """Test parsing a game end message with multiple winners."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    LucasTeam Luke - 👨🏼 Мирный житель 
    Tidal Wave - 👨🏼 Мирный житель 

Остальные участники: 
    Crazy Time - 👨🏼‍⚕️ Доктор 
    . - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert isinstance(result, ParsedMafiaWinners)
        assert result.game == "True Mafia"
        assert len(result.winners) == 2
        assert "LucasTeam Luke" in result.winners
        assert "Tidal Wave" in result.winners
    
    def test_parse_stops_at_other_participants(self, parser):
        """Test that parsing stops at 'Остальные участники:' section."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Winner1 - 👨🏼 Мирный житель 
    Winner2 - 👨🏼 Мирный житель 

Остальные участники: 
    Loser1 - 🤵🏻 Дон 
    Loser2 - 👨🏼‍⚕️ Доктор"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 2
        assert "Winner1" in result.winners
        assert "Winner2" in result.winners
        assert "Loser1" not in result.winners
        assert "Loser2" not in result.winners
    
    def test_parse_extracts_name_before_dash(self, parser):
        """Test that player names are extracted before the ' - ' separator."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Player Name With Spaces - 👨🏼 Мирный житель 

Остальные участники: 
    Other - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 1
        assert result.winners[0] == "Player Name With Spaces"
    
    def test_parse_handles_extra_whitespace(self, parser):
        """Test that parser handles extra whitespace correctly."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
       Player1    -    👨🏼 Мирный житель    
    Player2 - 👨🏼 Мирный житель 

Остальные участники: 
    Other - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 2
        assert "Player1" in result.winners
        assert "Player2" in result.winners
    
    def test_parse_ignores_empty_lines(self, parser):
        """Test that parser ignores empty lines in winners section."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 

    Player1 - 👨🏼 Мирный житель 

    Player2 - 👨🏼 Мирный житель 

Остальные участники: 
    Other - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 2
        assert "Player1" in result.winners
        assert "Player2" in result.winners
    
    def test_parse_missing_winners_section_raises_error(self, parser):
        """Test that missing winners section raises ParserError."""
        message = """Игра окончена! 
Победили: Мирные жители 

Остальные участники: 
    Player1 - 🤵🏻 Дон"""
        
        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)
        
        assert "No winners found" in str(exc_info.value)
    
    def test_parse_empty_winners_section_raises_error(self, parser):
        """Test that empty winners section raises ParserError."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 

Остальные участники: 
    Player1 - 🤵🏻 Дон"""
        
        with pytest.raises(ParserError) as exc_info:
            parser.parse(message)
        
        assert "No winners found" in str(exc_info.value)
    
    def test_parse_no_dash_separator_skips_line(self, parser):
        """Test that lines without ' - ' separator are skipped."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Player1 - 👨🏼 Мирный житель 
    InvalidLine
    Player2 - 👨🏼 Мирный житель 

Остальные участники: 
    Other - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 2
        assert "Player1" in result.winners
        assert "Player2" in result.winners
        assert "InvalidLine" not in result.winners
    
    def test_parse_without_other_participants_section(self, parser):
        """Test parsing when 'Остальные участники:' section is missing."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Player1 - 👨🏼 Мирный житель 
    Player2 - 👨🏼 Мирный житель"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 2
        assert "Player1" in result.winners
        assert "Player2" in result.winners
    
    def test_parse_special_characters_in_names(self, parser):
        """Test parsing player names with special characters."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    Player.Name - 👨🏼 Мирный житель 
    Player_123 - 👨🏼 Мирный житель 
    Игрок Русский - 👨🏼 Мирный житель 

Остальные участники: 
    Other - 🤵🏻 Дон"""
        
        result = parser.parse(message)
        
        assert len(result.winners) == 3
        assert "Player.Name" in result.winners
        assert "Player_123" in result.winners
        assert "Игрок Русский" in result.winners
    
    def test_parse_real_world_example(self, parser):
        """Test parsing with a real-world example message."""
        message = """Игра окончена! 
Победили: Мирные жители 

Победители: 
    LucasTeam Luke - 👨🏼 Мирный житель 
    Tidal Wave - 👨🏼 Мирный житель 

Остальные участники: 
    Crazy Time - 👨🏼‍⚕️ Доктор 
    . - 🤵🏻 Дон 

Игра длилась: 2 мин. 35 сек."""
        
        result = parser.parse(message)
        
        assert isinstance(result, ParsedMafiaWinners)
        assert result.game == "True Mafia"
        assert len(result.winners) == 2
        assert "LucasTeam Luke" in result.winners
        assert "Tidal Wave" in result.winners
        assert "Crazy Time" not in result.winners
        assert "." not in result.winners
