#!/usr/bin/env python3
"""
Property-based tests for BunkerGameEndParser.
Feature: message-parsing-system

Tests properties for BunkerRP game end message parsing:
- Winner extraction correctness
- Missing winners error handling
- Parsing stops at "Не прошли в бункер:" section
"""

import unittest
import sys
import os
from decimal import Decimal

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from hypothesis import given, strategies as st, settings, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    print("Warning: Hypothesis not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "hypothesis"])
        from hypothesis import given, strategies as st, settings, assume
        HYPOTHESIS_AVAILABLE = True
    except Exception as e:
        print(f"Failed to install Hypothesis: {e}")
        HYPOTHESIS_AVAILABLE = False

from src.parsers import BunkerGameEndParser, ParserError, ParsedBunkerWinners


# Strategy for generating valid player names
player_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
        blacklist_characters='\n\r.'  # Exclude newlines and period (used as separator)
    )
)


class TestBunkerGameEndParserProperties(unittest.TestCase):
    """Property-based tests for BunkerGameEndParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = BunkerGameEndParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        winners=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_winner_extraction_correctness(self, winners):
        """
        Feature: message-parsing-system, Property: Winner Extraction Correctness
        
        For any valid game end message with winner names, parsing should extract 
        all winner names correctly.
        
        **Validates: Requirements 8.1, 8.2**
        """
        # Ensure all winner names are valid (non-empty after strip)
        winners = [w.strip() for w in winners if w.strip()]
        assume(len(winners) > 0)
        
        # Ensure no winner name contains the separator or section markers
        for winner in winners:
            assume(". " not in winner)
            assume("Прошли в бункер:" not in winner)
            assume("Не прошли в бункер:" not in winner)
        
        # Construct a valid game end message
        message_lines = [
            "Прошли в бункер:"
        ]
        
        # Add winner lines with numbering
        for idx, winner in enumerate(winners, start=1):
            message_lines.append(f"{idx}. {winner}")
        
        # Add losers section
        message_lines.extend([
            "",
            "Не прошли в бункер:",
            "1. Loser1",
            "2. Loser2"
        ])
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert all winners are extracted correctly
        self.assertIsInstance(result, ParsedBunkerWinners)
        self.assertEqual(result.game, "Bunker RP")
        self.assertEqual(len(result.winners), len(winners))
        
        # Check that all winners are present
        for winner in winners:
            self.assertIn(winner, result.winners)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        losers=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_missing_winners_raises_error(self, losers):
        """
        Feature: message-parsing-system, Property: Missing Winners Error
        
        For any game end message with no winners in the "Прошли в бункер:" section,
        the parser should raise a ParserError.
        
        **Validates: Requirements 8.4**
        """
        # Ensure all loser names are valid
        losers = [l.strip() for l in losers if l.strip()]
        assume(len(losers) > 0)
        
        # Ensure no loser name contains problematic strings
        for loser in losers:
            assume(". " not in loser)
            assume("Прошли в бункер:" not in loser)
            assume("Не прошли в бункер:" not in loser)
        
        # Construct message with empty winners section
        message_lines = [
            "Прошли в бункер:",
            "",
            "Не прошли в бункер:"
        ]
        
        # Add loser lines
        for idx, loser in enumerate(losers, start=1):
            message_lines.append(f"{idx}. {loser}")
        
        message = "\n".join(message_lines)
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate no winners found
        self.assertIn("No winners found", str(context.exception))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        winners=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=5
        ),
        losers=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_parsing_stops_at_losers_section(self, winners, losers):
        """
        Feature: message-parsing-system, Property: Parsing Stops at Losers Section
        
        For any game end message, parsing should stop extracting winners when 
        reaching the "Не прошли в бункер:" section. Players in that section 
        should NOT be included in the winners list.
        
        **Validates: Requirements 8.3**
        """
        # Ensure all names are valid
        winners = [w.strip() for w in winners if w.strip()]
        losers = [l.strip() for l in losers if l.strip()]
        assume(len(winners) > 0)
        assume(len(losers) > 0)
        
        # Ensure no name contains problematic strings
        for name in winners + losers:
            assume(". " not in name)
            assume("Прошли в бункер:" not in name)
            assume("Не прошли в бункер:" not in name)
        
        # Ensure winners and losers are distinct
        assume(len(set(winners) & set(losers)) == 0)
        
        # Construct message with both winners and losers
        message_lines = [
            "Прошли в бункер:"
        ]
        
        # Add winner lines
        for idx, winner in enumerate(winners, start=1):
            message_lines.append(f"{idx}. {winner}")
        
        # Add losers section
        message_lines.extend([
            "",
            "Не прошли в бункер:"
        ])
        
        # Add loser lines
        for idx, loser in enumerate(losers, start=1):
            message_lines.append(f"{idx}. {loser}")
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert only winners are extracted, not losers
        self.assertEqual(len(result.winners), len(winners))
        
        for winner in winners:
            self.assertIn(winner, result.winners)
        
        for loser in losers:
            self.assertNotIn(loser, result.winners)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        winners=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=5
        ),
        extra_whitespace_before=st.integers(min_value=0, max_value=10),
        extra_whitespace_after=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_whitespace_handling(self, winners, 
                                          extra_whitespace_before, extra_whitespace_after):
        """
        Feature: message-parsing-system, Property: Whitespace Handling
        
        For any game end message with extra whitespace around player names,
        parsing should correctly extract trimmed player names.
        
        **Validates: Requirements 8.2**
        """
        # Ensure all winner names are valid
        winners = [w.strip() for w in winners if w.strip()]
        assume(len(winners) > 0)
        
        # Ensure no winner name contains problematic strings
        for winner in winners:
            assume(". " not in winner)
            assume("Прошли в бункер:" not in winner)
            assume("Не прошли в бункер:" not in winner)
        
        # Construct message with extra whitespace
        message_lines = [
            "Прошли в бункер:"
        ]
        
        # Add winner lines with extra whitespace
        for idx, winner in enumerate(winners, start=1):
            ws_before = " " * extra_whitespace_before
            ws_after = " " * extra_whitespace_after
            message_lines.append(f"{ws_before}{idx}. {winner}{ws_after}")
        
        message_lines.extend([
            "",
            "Не прошли в бункер:",
            "1. Loser"
        ])
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert all winners are extracted with trimmed names
        self.assertEqual(len(result.winners), len(winners))
        
        for winner in winners:
            self.assertIn(winner, result.winners)
            # Ensure no extra whitespace in extracted names
            for extracted_winner in result.winners:
                self.assertEqual(extracted_winner, extracted_winner.strip())
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        winners=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_parsing_consistency(self, winners):
        """
        Feature: message-parsing-system, Property: Parsing Consistency
        
        For any valid game end message, parsing the same message multiple times
        should always produce the same result.
        
        **Validates: Requirements 8.1, 8.2**
        """
        # Ensure all winner names are valid
        winners = [w.strip() for w in winners if w.strip()]
        assume(len(winners) > 0)
        
        # Ensure no winner name contains problematic strings
        for winner in winners:
            assume(". " not in winner)
            assume("Прошли в бункер:" not in winner)
            assume("Не прошли в бункер:" not in winner)
        
        # Construct a valid game end message
        message_lines = [
            "Прошли в бункер:"
        ]
        
        for idx, winner in enumerate(winners, start=1):
            message_lines.append(f"{idx}. {winner}")
        
        message_lines.extend([
            "",
            "Не прошли в бункер:",
            "1. Loser"
        ])
        
        message = "\n".join(message_lines)
        
        # Parse the message multiple times
        result1 = self.parser.parse(message)
        result2 = self.parser.parse(message)
        result3 = self.parser.parse(message)
        
        # Assert all results are identical
        self.assertEqual(result1.winners, result2.winners)
        self.assertEqual(result2.winners, result3.winners)
        self.assertEqual(result1.game, result2.game)
        self.assertEqual(result2.game, result3.game)
    
    def test_bunker_game_end_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Property: Winner extraction
        message1 = """Прошли в бункер:
1. Player1
2. Player2

Не прошли в бункер:
1. Loser1"""
        
        result1 = self.parser.parse(message1)
        self.assertEqual(len(result1.winners), 2)
        self.assertIn("Player1", result1.winners)
        self.assertIn("Player2", result1.winners)
        
        # Property: Missing winners error
        message2 = """Прошли в бункер:

Не прошли в бункер:
1. Loser1"""
        
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message2)
        self.assertIn("No winners found", str(context.exception))
        
        # Property: Parsing stops at losers section
        message3 = """Прошли в бункер:
1. Winner1

Не прошли в бункер:
1. Loser1
2. Loser2"""
        
        result3 = self.parser.parse(message3)
        self.assertEqual(len(result3.winners), 1)
        self.assertIn("Winner1", result3.winners)
        self.assertNotIn("Loser1", result3.winners)
        self.assertNotIn("Loser2", result3.winners)


if __name__ == '__main__':
    unittest.main()
