#!/usr/bin/env python3
"""
Property-based tests for MafiaGameEndParser.
Feature: message-parsing-system

Tests properties for True Mafia game end message parsing:
- Winner extraction correctness
- Missing winners error handling
- Parsing stops at "Остальные участники:" section
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

from src.parsers import MafiaGameEndParser, ParserError, ParsedMafiaWinners


# Strategy for generating valid player names
player_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
        blacklist_characters='\n\r-'  # Exclude newlines and dash (used as separator)
    )
)


class TestMafiaGameEndParserProperties(unittest.TestCase):
    """Property-based tests for MafiaGameEndParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = MafiaGameEndParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        winners=st.lists(
            player_name_strategy,
            min_size=1,
            max_size=10
        ),
        role=st.sampled_from([
            "👨🏼 Мирный житель",
            "🤵🏻 Дон",
            "👨🏼‍⚕️ Доктор",
            "🕵️ Комиссар",
            "👨🏼‍💼 Мафия"
        ])
    )
    @settings(max_examples=100, deadline=None)
    def test_property_winner_extraction_correctness(self, winners, role):
        """
        Feature: message-parsing-system, Property: Winner Extraction Correctness
        
        For any valid game end message with winner names, parsing should extract 
        all winner names correctly.
        
        **Validates: Requirements 6.1, 6.2**
        """
        # Ensure all winner names are valid (non-empty after strip)
        winners = [w.strip() for w in winners if w.strip()]
        assume(len(winners) > 0)
        
        # Ensure no winner name contains the separator or section markers
        for winner in winners:
            assume(" - " not in winner)
            assume("Победители:" not in winner)
            assume("Остальные участники:" not in winner)
        
        # Construct a valid game end message
        message_lines = [
            "Игра окончена!",
            "Победили: Мирные жители",
            "",
            "Победители:"
        ]
        
        # Add winner lines
        for winner in winners:
            message_lines.append(f"    {winner} - {role}")
        
        # Add other participants section
        message_lines.extend([
            "",
            "Остальные участники:",
            "    Loser1 - 🤵🏻 Дон",
            "    Loser2 - 👨🏼‍💼 Мафия"
        ])
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert all winners are extracted correctly
        self.assertIsInstance(result, ParsedMafiaWinners)
        self.assertEqual(result.game, "True Mafia")
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
        ),
        role=st.sampled_from([
            "👨🏼 Мирный житель",
            "🤵🏻 Дон",
            "👨🏼‍⚕️ Доктор",
            "🕵️ Комиссар",
            "👨🏼‍💼 Мафия"
        ])
    )
    @settings(max_examples=100, deadline=None)
    def test_property_missing_winners_raises_error(self, losers, role):
        """
        Feature: message-parsing-system, Property: Missing Winners Error
        
        For any game end message with no winners in the "Победители:" section,
        the parser should raise a ParserError.
        
        **Validates: Requirements 6.4**
        """
        # Ensure all loser names are valid
        losers = [l.strip() for l in losers if l.strip()]
        assume(len(losers) > 0)
        
        # Ensure no loser name contains problematic strings
        for loser in losers:
            assume(" - " not in loser)
            assume("Победители:" not in loser)
            assume("Остальные участники:" not in loser)
        
        # Construct message with empty winners section
        message_lines = [
            "Игра окончена!",
            "Победили: Мирные жители",
            "",
            "Победители:",
            "",
            "Остальные участники:"
        ]
        
        # Add loser lines
        for loser in losers:
            message_lines.append(f"    {loser} - {role}")
        
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
        ),
        winner_role=st.sampled_from([
            "👨🏼 Мирный житель",
            "🤵🏻 Дон",
            "👨🏼‍⚕️ Доктор"
        ]),
        loser_role=st.sampled_from([
            "🤵🏻 Дон",
            "👨🏼‍💼 Мафия",
            "👨🏼 Мирный житель"
        ])
    )
    @settings(max_examples=100, deadline=None)
    def test_property_parsing_stops_at_other_participants(self, winners, losers, 
                                                           winner_role, loser_role):
        """
        Feature: message-parsing-system, Property: Parsing Stops at Other Participants
        
        For any game end message, parsing should stop extracting winners when 
        reaching the "Остальные участники:" section. Players in that section 
        should NOT be included in the winners list.
        
        **Validates: Requirements 6.3**
        """
        # Ensure all names are valid
        winners = [w.strip() for w in winners if w.strip()]
        losers = [l.strip() for l in losers if l.strip()]
        assume(len(winners) > 0)
        assume(len(losers) > 0)
        
        # Ensure no name contains problematic strings
        for name in winners + losers:
            assume(" - " not in name)
            assume("Победители:" not in name)
            assume("Остальные участники:" not in name)
        
        # Ensure winners and losers are distinct
        assume(len(set(winners) & set(losers)) == 0)
        
        # Construct message with both winners and losers
        message_lines = [
            "Игра окончена!",
            "Победили: Мирные жители",
            "",
            "Победители:"
        ]
        
        # Add winner lines
        for winner in winners:
            message_lines.append(f"    {winner} - {winner_role}")
        
        # Add other participants section
        message_lines.extend([
            "",
            "Остальные участники:"
        ])
        
        # Add loser lines
        for loser in losers:
            message_lines.append(f"    {loser} - {loser_role}")
        
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
        role=st.sampled_from([
            "👨🏼 Мирный житель",
            "🤵🏻 Дон",
            "👨🏼‍⚕️ Доктор"
        ]),
        extra_whitespace_before=st.integers(min_value=0, max_value=10),
        extra_whitespace_after=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_whitespace_handling(self, winners, role, 
                                          extra_whitespace_before, extra_whitespace_after):
        """
        Feature: message-parsing-system, Property: Whitespace Handling
        
        For any game end message with extra whitespace around player names,
        parsing should correctly extract trimmed player names.
        
        **Validates: Requirements 6.2**
        """
        # Ensure all winner names are valid
        winners = [w.strip() for w in winners if w.strip()]
        assume(len(winners) > 0)
        
        # Ensure no winner name contains problematic strings
        for winner in winners:
            assume(" - " not in winner)
            assume("Победители:" not in winner)
            assume("Остальные участники:" not in winner)
        
        # Construct message with extra whitespace
        message_lines = [
            "Игра окончена!",
            "Победили: Мирные жители",
            "",
            "Победители:"
        ]
        
        # Add winner lines with extra whitespace
        for winner in winners:
            ws_before = " " * extra_whitespace_before
            ws_after = " " * extra_whitespace_after
            message_lines.append(f"{ws_before}    {winner}{ws_after} - {role}")
        
        message_lines.extend([
            "",
            "Остальные участники:",
            "    Loser - 🤵🏻 Дон"
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
    
    def test_mafia_game_end_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Property: Winner extraction
        message1 = """Игра окончена!
Победили: Мирные жители

Победители:
    Player1 - 👨🏼 Мирный житель
    Player2 - 👨🏼 Мирный житель

Остальные участники:
    Loser1 - 🤵🏻 Дон"""
        
        result1 = self.parser.parse(message1)
        self.assertEqual(len(result1.winners), 2)
        self.assertIn("Player1", result1.winners)
        self.assertIn("Player2", result1.winners)
        
        # Property: Missing winners error
        message2 = """Игра окончена!
Победили: Мирные жители

Победители:

Остальные участники:
    Loser1 - 🤵🏻 Дон"""
        
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message2)
        self.assertIn("No winners found", str(context.exception))
        
        # Property: Parsing stops at other participants
        message3 = """Игра окончена!
Победили: Мирные жители

Победители:
    Winner1 - 👨🏼 Мирный житель

Остальные участники:
    Loser1 - 🤵🏻 Дон
    Loser2 - 👨🏼‍💼 Мафия"""
        
        result3 = self.parser.parse(message3)
        self.assertEqual(len(result3.winners), 1)
        self.assertIn("Winner1", result3.winners)
        self.assertNotIn("Loser1", result3.winners)
        self.assertNotIn("Loser2", result3.winners)


if __name__ == '__main__':
    unittest.main()
