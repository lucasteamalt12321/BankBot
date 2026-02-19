#!/usr/bin/env python3
"""
Property-based tests for AccrualParser.
Feature: message-parsing-system

Tests Properties 9-11 from the design document:
- Property 9: Accrual Parser Extraction
- Property 10: Accrual Parser Error on Malformed Points
- Property 11: Accrual Parser Field Isolation
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

from src.parsers import AccrualParser, ParserError, ParsedAccrual


class TestAccrualParserProperties(unittest.TestCase):
    """Property-based tests for AccrualParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = AccrualParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
            blacklist_characters='\n\r'
        )),
        points=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_9_accrual_parser_extraction(self, player_name, points):
        """
        Feature: message-parsing-system, Property 9: Accrual Parser Extraction
        
        For any valid accrual message with a player name and points value, 
        parsing should extract both the player name and the numeric points value correctly.
        
        **Validates: Requirements 3.1, 3.2, 3.4**
        """
        # Assume player name doesn't contain parsing markers to avoid conflicts
        assume("Игрок:" not in player_name)
        assume("Очки:" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct a valid accrual message
        message = f"""🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: {player_name}
───────────────
Карта: "Test Card"
Описание: Test description
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +{points}
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert extraction is correct
        self.assertIsInstance(result, ParsedAccrual)
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.points, points)
        self.assertEqual(result.game, "GD Cards")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        points_value=st.one_of(
            st.text(min_size=1, max_size=20, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll'),  # Only letters
            )),
            st.just(""),  # Empty string
            st.just("-5"),  # Negative without plus
            st.just("5"),  # Positive without plus
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_10_accrual_parser_error_on_malformed_points(self, player_name, points_value):
        """
        Feature: message-parsing-system, Property 10: Accrual Parser Error on Malformed Points
        
        For any accrual message where "Очки:" does not contain a plus sign and number, 
        the parser should raise a ParserError.
        
        **Validates: Requirements 3.3**
        """
        # Assume valid player name
        assume("Игрок:" not in player_name)
        assume("Очки:" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct message with malformed points field (no plus sign or invalid format)
        message = f"""🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: {player_name}
───────────────
Очки: {points_value}
───────────────"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate the issue
        error_msg = str(context.exception)
        self.assertTrue(
            "does not contain a plus sign and number" in error_msg or
            "Invalid points value" in error_msg,
            f"Expected error about malformed points, got: {error_msg}"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        points=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        ),
        extra_fields_before=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=20, alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters='\n\r:'
                )),
                st.text(min_size=1, max_size=50, alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters='\n\r'
                ))
            ),
            min_size=0,
            max_size=3
        ),
        extra_fields_after=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=20, alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters='\n\r:'
                )),
                st.text(min_size=1, max_size=50, alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters='\n\r'
                ))
            ),
            min_size=0,
            max_size=3
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_11_accrual_parser_field_isolation(self, player_name, points,
                                                         extra_fields_before, extra_fields_after):
        """
        Feature: message-parsing-system, Property 11: Accrual Parser Field Isolation
        
        For any accrual message, adding or removing fields other than player name 
        and "Очки:" should not affect the extracted values.
        
        **Validates: Requirements 3.5**
        """
        # Assume valid inputs
        assume("Игрок:" not in player_name)
        assume("Очки:" not in player_name)
        assume(player_name.strip() != "")
        
        # Ensure extra fields don't interfere with parsing
        for field_name, field_value in extra_fields_before + extra_fields_after:
            assume("Игрок" not in field_name and "Игрок:" not in field_value)
            assume("Очки" not in field_name)
            assume("Очки:" not in field_value)  # Ensure field values don't contain "Очки:"
            assume("+" not in field_value or "Очки" not in field_value)  # Avoid confusion
        
        # Construct message with extra fields before and after Очки
        message_lines = ["🃏 НОВАЯ КАРТА 🃏", "───────────────"]
        message_lines.append(f"Игрок: {player_name}")
        message_lines.append("───────────────")
        
        # Add extra fields before Очки
        for field_name, field_value in extra_fields_before:
            message_lines.append(f"{field_name}: {field_value}")
        
        # Add the Очки field
        message_lines.append(f"Очки: +{points}")
        
        # Add extra fields after Очки
        for field_name, field_value in extra_fields_after:
            message_lines.append(f"{field_name}: {field_value}")
        
        message_lines.append("───────────────")
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that only player name and points are extracted correctly
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.points, points)
        self.assertEqual(result.game, "GD Cards")
        
        # Verify that the result only has the expected fields
        self.assertIsInstance(result, ParsedAccrual)
        self.assertTrue(hasattr(result, 'player_name'))
        self.assertTrue(hasattr(result, 'points'))
        self.assertTrue(hasattr(result, 'game'))
    
    def test_accrual_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Property 9: Basic extraction
        message1 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TestPlayer
───────────────
Очки: +5
───────────────"""
        result1 = self.parser.parse(message1)
        self.assertEqual(result1.player_name, "TestPlayer")
        self.assertEqual(result1.points, Decimal("5"))
        
        # Property 10: Malformed points (no plus sign)
        message2 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player2
───────────────
Очки: 10
───────────────"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message2)
        self.assertIn("does not contain a plus sign", str(context.exception))
        
        # Property 10: Malformed points (invalid value)
        message3 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player3
───────────────
Очки: +abc
───────────────"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message3)
        self.assertIn("Invalid points value", str(context.exception))
        
        # Property 11: Field isolation
        message4 = """🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: Player4
───────────────
Карта: "Test Card"
Описание: Test description
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────"""
        result4 = self.parser.parse(message4)
        self.assertEqual(result4.player_name, "Player4")
        self.assertEqual(result4.points, Decimal("3"))


if __name__ == '__main__':
    unittest.main()
