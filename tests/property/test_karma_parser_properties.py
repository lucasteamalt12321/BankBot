#!/usr/bin/env python3
"""
Property-based tests for KarmaParser.
Feature: message-parsing-system

Tests properties for Shmalala karma message parsing from the design document.
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

from src.parsers import KarmaParser, ParserError, ParsedKarma


class TestKarmaParserProperties(unittest.TestCase):
    """Property-based tests for KarmaParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = KarmaParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
            blacklist_characters='\n\r'
        ))
    )
    @settings(max_examples=100, deadline=None)
    def test_karma_parser_extraction(self, player_name):
        """
        Feature: message-parsing-system, Karma Parser Extraction
        
        For any valid karma message with a player name, parsing should extract 
        the player name correctly.
        
        **Validates: Requirements 5.1**
        """
        # Assume player name doesn't contain parsing markers to avoid conflicts
        assume("пользователя" not in player_name)
        assume("Лайк!" not in player_name)
        assume(player_name.strip() != "")
        # The parser strips trailing dots, so we need to account for that
        expected_name = player_name.strip().rstrip('.').strip()
        assume(expected_name != "")  # After stripping dots, name must not be empty
        
        # Construct a valid karma message
        message = f"""Лайк! Вы повысили рейтинг пользователя {player_name}.
Теперь его рейтинг: 10 ❤️"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert extraction is correct (with trailing dots removed)
        self.assertIsInstance(result, ParsedKarma)
        self.assertEqual(result.player_name, expected_name)
        self.assertEqual(result.game, "Shmalala Karma")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        displayed_rating=st.integers(min_value=2, max_value=999999)
    )
    @settings(max_examples=100, deadline=None)
    def test_karma_always_one(self, player_name, displayed_rating):
        """
        Feature: message-parsing-system, Karma Always One
        
        The parser should always treat karma accruals as +1, regardless of 
        the displayed total rating in the message.
        
        **Validates: Requirements 5.2**
        """
        # Assume valid inputs
        assume("пользователя" not in player_name)
        assume("Лайк!" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct message with any displayed rating (always > 1)
        message = f"""Лайк! Вы повысили рейтинг пользователя {player_name}.
Теперь его рейтинг: {displayed_rating} ❤️"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that karma is always 1, regardless of displayed rating
        self.assertEqual(result.karma, Decimal("1"))
        # Verify it's not equal to the displayed rating (which is always > 1)
        self.assertNotEqual(result.karma, Decimal(str(displayed_rating)))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        ))
    )
    @settings(max_examples=100, deadline=None)
    def test_karma_parser_error_on_missing_player_name(self, player_name):
        """
        Feature: message-parsing-system, Karma Parser Error on Missing Player Name
        
        For any karma message where the player name cannot be extracted, 
        the parser should raise a ParserError.
        
        **Validates: Requirements 5.3**
        """
        # Construct message without the required marker
        message = f"""Теперь его рейтинг: 10 ❤️"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate the issue
        error_msg = str(context.exception)
        self.assertIn("Player name not found", error_msg)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        displayed_rating=st.integers(min_value=0, max_value=999999)
    )
    @settings(max_examples=100, deadline=None)
    def test_karma_parser_ignores_rating_field(self, player_name, displayed_rating):
        """
        Feature: message-parsing-system, Karma Parser Ignores Rating Field
        
        The parser should ignore the "Теперь его рейтинг:" field value and 
        always return karma as 1.
        
        **Validates: Requirements 5.4**
        """
        # Assume valid inputs
        assume("пользователя" not in player_name)
        assume("Лайк!" not in player_name)
        assume(player_name.strip() != "")
        # The parser strips trailing dots, so we need to account for that
        expected_name = player_name.strip().rstrip('.').strip()
        assume(expected_name != "")  # After stripping dots, name must not be empty
        
        # Construct message with rating field
        message = f"""Лайк! Вы повысили рейтинг пользователя {player_name}.
Теперь его рейтинг: {displayed_rating} ❤️"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that the rating field is ignored
        self.assertEqual(result.karma, Decimal("1"))
        # Verify the player name was extracted correctly (with trailing dots removed)
        self.assertEqual(result.player_name, expected_name)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        displayed_rating=st.integers(min_value=0, max_value=999999),
        extra_lines_before=st.lists(
            st.text(min_size=1, max_size=100, alphabet=st.characters(
                blacklist_categories=('Cs', 'Cc'),
                blacklist_characters='\n\r'
            )),
            min_size=0,
            max_size=3
        ),
        extra_lines_after=st.lists(
            st.text(min_size=1, max_size=100, alphabet=st.characters(
                blacklist_categories=('Cs', 'Cc'),
                blacklist_characters='\n\r'
            )),
            min_size=0,
            max_size=3
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_karma_parser_field_isolation(self, player_name, displayed_rating,
                                          extra_lines_before, extra_lines_after):
        """
        Feature: message-parsing-system, Karma Parser Field Isolation
        
        For any karma message, adding or removing fields other than the player name 
        extraction line should not affect the extracted values.
        """
        # Assume valid inputs
        assume("пользователя" not in player_name)
        assume("Лайк!" not in player_name)
        assume(player_name.strip() != "")
        # The parser strips trailing dots, so we need to account for that
        expected_name = player_name.strip().rstrip('.').strip()
        assume(expected_name != "")  # After stripping dots, name must not be empty
        
        # Ensure extra lines don't interfere with parsing
        for line in extra_lines_before + extra_lines_after:
            assume("Лайк! Вы повысили рейтинг пользователя" not in line)
        
        # Construct message with extra lines before and after
        message_lines = []
        
        # Add extra lines before
        message_lines.extend(extra_lines_before)
        
        # Add the main karma line
        message_lines.append(f"Лайк! Вы повысили рейтинг пользователя {player_name}.")
        message_lines.append(f"Теперь его рейтинг: {displayed_rating} ❤️")
        
        # Add extra lines after
        message_lines.extend(extra_lines_after)
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that player name is extracted correctly (with trailing dots removed)
        self.assertEqual(result.player_name, expected_name)
        self.assertEqual(result.karma, Decimal("1"))
        self.assertEqual(result.game, "Shmalala Karma")
        
        # Verify that the result only has the expected fields
        self.assertIsInstance(result, ParsedKarma)
        self.assertTrue(hasattr(result, 'player_name'))
        self.assertTrue(hasattr(result, 'karma'))
        self.assertTrue(hasattr(result, 'game'))
    
    def test_karma_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Basic extraction
        message1 = """Лайк! Вы повысили рейтинг пользователя TestPlayer.
Теперь его рейтинг: 10 ❤️"""
        result1 = self.parser.parse(message1)
        self.assertEqual(result1.player_name, "TestPlayer")
        self.assertEqual(result1.karma, Decimal("1"))
        
        # Karma always 1 regardless of rating
        message2 = """Лайк! Вы повысили рейтинг пользователя Player2.
Теперь его рейтинг: 999 ❤️"""
        result2 = self.parser.parse(message2)
        self.assertEqual(result2.karma, Decimal("1"))
        self.assertNotEqual(result2.karma, Decimal("999"))
        
        # Missing player name
        message3 = """Теперь его рейтинг: 10 ❤️"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message3)
        self.assertIn("Player name not found", str(context.exception))
        
        # Ignores rating field
        message4 = """Лайк! Вы повысили рейтинг пользователя Player4.
Теперь его рейтинг: 5000 ❤️"""
        result4 = self.parser.parse(message4)
        self.assertEqual(result4.karma, Decimal("1"))
        self.assertEqual(result4.player_name, "Player4")
        
        # Field isolation with extra lines
        message5 = """Дополнительная информация
Лайк! Вы повысили рейтинг пользователя Player5.
Теперь его рейтинг: 20 ❤️
Еще одна строка"""
        result5 = self.parser.parse(message5)
        self.assertEqual(result5.player_name, "Player5")
        self.assertEqual(result5.karma, Decimal("1"))


if __name__ == '__main__':
    unittest.main()
