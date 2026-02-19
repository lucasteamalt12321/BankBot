#!/usr/bin/env python3
"""
Property-based tests for BunkerProfileParser.
Feature: message-parsing-system

Tests properties for BunkerRP profile message parsing:
- Player name and money extraction correctness
- Decimal precision preservation
- Missing field error handling
- Field isolation (other fields don't affect extraction)
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

from src.parsers import BunkerProfileParser, ParserError, ParsedBunkerProfile


# Strategy for generating valid player names
player_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
        blacklist_characters='\n\r👤💵💎🎯:'  # Exclude newlines and special markers
    )
)

# Strategy for generating valid money values
money_strategy = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("999999"),
    allow_nan=False,
    allow_infinity=False,
    places=2
)


class TestBunkerProfileParserProperties(unittest.TestCase):
    """Property-based tests for BunkerProfileParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = BunkerProfileParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_profile_parser_extraction(self, player_name, money):
        """
        Feature: message-parsing-system, Property: Profile Parser Extraction
        
        For any valid BunkerRP profile message with a player name and money value,
        parsing should extract both the player name and the numeric money value correctly.
        
        **Validates: Requirements 9.1, 9.2**
        """
        # Ensure player name is valid (non-empty after strip)
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct a valid profile message
        message = f"""👤 {player_name}

💵 Деньги: {money}
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert extraction is correct
        self.assertIsInstance(result, ParsedBunkerProfile)
        self.assertEqual(result.player_name, player_name)
        self.assertEqual(result.money, money)
        self.assertEqual(result.game, "Bunker RP")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_decimal_precision_preservation(self, player_name, money):
        """
        Feature: message-parsing-system, Property: Decimal Precision Preservation
        
        For any BunkerRP profile message with a decimal money value, parsing then
        converting back to string should preserve the decimal precision (no rounding errors).
        
        **Validates: Requirements 9.4**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct message with decimal money value
        message = f"""👤 {player_name}

💵 Деньги: {money}
💎 Кристаллики: 5

🎯 Побед: 1"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert decimal precision is preserved
        self.assertEqual(result.money, money)
        # Converting back to string should match
        self.assertEqual(str(result.money), str(money))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_missing_money_field_error(self, player_name):
        """
        Feature: message-parsing-system, Property: Profile Parser Error on Missing Field
        
        For any BunkerRP profile message missing the "💵 Деньги:" field, the parser
        should raise a ParserError indicating incomplete data.
        
        **Validates: Requirements 9.3**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct message without money field
        message = f"""👤 {player_name}

💎 Кристаллики: 10

🎯 Побед: 0"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate missing money field
        self.assertIn("Money field not found", str(context.exception))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        money=money_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_missing_player_name_error(self, money):
        """
        Feature: message-parsing-system, Property: Missing Player Name Error
        
        For any BunkerRP profile message missing the player name (👤 field),
        the parser should raise a ParserError.
        
        **Validates: Requirements 9.1**
        """
        # Construct message without player name
        message = f"""💵 Деньги: {money}
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate missing player name
        self.assertIn("Player name not found", str(context.exception))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy,
        crystals=st.integers(min_value=0, max_value=1000),
        wins=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_field_isolation(self, player_name, money, crystals, wins):
        """
        Feature: message-parsing-system, Property: Profile Parser Field Isolation
        
        For any BunkerRP profile message, adding or removing fields other than
        player name and "💵 Деньги:" should not affect the extracted values.
        
        **Validates: Requirements 9.5**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct message with various field values
        message = f"""👤 {player_name}

💵 Деньги: {money}
💎 Кристаллики: {crystals}

🎯 Побед: {wins}"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert only player name and money are extracted
        self.assertEqual(result.player_name, player_name)
        self.assertEqual(result.money, money)
        
        # Now construct message with minimal fields
        minimal_message = f"""👤 {player_name}

💵 Деньги: {money}"""
        
        # Parse minimal message
        minimal_result = self.parser.parse(minimal_message)
        
        # Assert extraction is the same
        self.assertEqual(minimal_result.player_name, player_name)
        self.assertEqual(minimal_result.money, money)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        invalid_money=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                blacklist_categories=('Nd',),  # Exclude digits
                blacklist_characters='.-'  # Exclude decimal point and minus
            )
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_invalid_money_value_error(self, player_name, invalid_money):
        """
        Feature: message-parsing-system, Property: Invalid Money Value Error
        
        For any BunkerRP profile message with an invalid (non-numeric) money value,
        the parser should raise a ParserError indicating invalid money value.
        
        **Validates: Requirements 9.4**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Ensure invalid_money is truly invalid (not parseable as Decimal)
        try:
            Decimal(invalid_money)
            assume(False)  # Skip if it's actually valid
        except:
            pass  # Good, it's invalid
        
        # Construct message with invalid money value
        message = f"""👤 {player_name}

💵 Деньги: {invalid_money}
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate invalid money value
        self.assertIn("Invalid money value", str(context.exception))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy,
        extra_whitespace_before=st.integers(min_value=0, max_value=10),
        extra_whitespace_after=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_whitespace_handling(self, player_name, money, 
                                         extra_whitespace_before, extra_whitespace_after):
        """
        Feature: message-parsing-system, Property: Whitespace Handling
        
        For any BunkerRP profile message with extra whitespace around player name
        or money value, parsing should correctly extract trimmed values.
        
        **Validates: Requirements 9.1, 9.2**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct message with extra whitespace
        ws_before = " " * extra_whitespace_before
        ws_after = " " * extra_whitespace_after
        
        message = f"""👤{ws_before} {player_name}{ws_after}

💵 Деньги:{ws_before} {money}{ws_after}
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert values are correctly trimmed
        self.assertEqual(result.player_name, player_name)
        self.assertEqual(result.money, money)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_first_occurrence_used(self, player_name, money):
        """
        Feature: message-parsing-system, Property: First Occurrence Used
        
        For any BunkerRP profile message with multiple occurrences of 👤 or
        💵 Деньги:, the parser should use the first occurrence.
        
        **Validates: Requirements 9.1, 9.2**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct message with duplicate markers
        message = f"""👤 {player_name}

💵 Деньги: {money}
💎 Кристаллики: 0

👤 SecondPlayer should be ignored
💵 Деньги: 999999
🎯 Побед: 0"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert first occurrence is used
        self.assertEqual(result.player_name, player_name)
        self.assertEqual(result.money, money)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=player_name_strategy,
        money=money_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_property_parsing_consistency(self, player_name, money):
        """
        Feature: message-parsing-system, Property: Parsing Consistency
        
        For any valid BunkerRP profile message, parsing the same message multiple times
        should always produce the same result.
        
        **Validates: Requirements 9.1, 9.2**
        """
        # Ensure player name is valid
        player_name = player_name.strip()
        assume(len(player_name) > 0)
        
        # Construct a valid profile message
        message = f"""👤 {player_name}

💵 Деньги: {money}
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        # Parse the message multiple times
        result1 = self.parser.parse(message)
        result2 = self.parser.parse(message)
        result3 = self.parser.parse(message)
        
        # Assert all results are identical
        self.assertEqual(result1.player_name, result2.player_name)
        self.assertEqual(result2.player_name, result3.player_name)
        self.assertEqual(result1.money, result2.money)
        self.assertEqual(result2.money, result3.money)
        self.assertEqual(result1.game, result2.game)
        self.assertEqual(result2.game, result3.game)
    
    def test_bunker_profile_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Property: Profile parser extraction
        message1 = """👤 TestPlayer

💵 Деньги: 500
💎 Кристаллики: 10

🎯 Побед: 5"""
        
        result1 = self.parser.parse(message1)
        self.assertEqual(result1.player_name, "TestPlayer")
        self.assertEqual(result1.money, Decimal("500"))
        self.assertEqual(result1.game, "Bunker RP")
        
        # Property: Decimal precision preservation
        message2 = """👤 Player2

💵 Деньги: 123.45
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        result2 = self.parser.parse(message2)
        self.assertEqual(result2.money, Decimal("123.45"))
        self.assertEqual(str(result2.money), "123.45")
        
        # Property: Missing money field error
        message3 = """👤 Player3

💎 Кристаллики: 10

🎯 Побед: 1"""
        
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message3)
        self.assertIn("Money field not found", str(context.exception))
        
        # Property: Missing player name error
        message4 = """💵 Деньги: 100
💎 Кристаллики: 0

🎯 Побед: 0"""
        
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message4)
        self.assertIn("Player name not found", str(context.exception))
        
        # Property: Field isolation
        message5 = """👤 Player5

💵 Деньги: 750
💎 Кристаллики: 20

🎯 Побед: 10"""
        
        result5 = self.parser.parse(message5)
        self.assertEqual(result5.player_name, "Player5")
        self.assertEqual(result5.money, Decimal("750"))
        
        minimal_message5 = """👤 Player5

💵 Деньги: 750"""
        
        minimal_result5 = self.parser.parse(minimal_message5)
        self.assertEqual(minimal_result5.player_name, "Player5")
        self.assertEqual(minimal_result5.money, Decimal("750"))


if __name__ == '__main__':
    unittest.main()
