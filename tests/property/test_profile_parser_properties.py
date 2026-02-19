#!/usr/bin/env python3
"""
Property-based tests for ProfileParser.
Feature: message-parsing-system

Tests Properties 5-8 from the design document:
- Property 5: Profile Parser Extraction
- Property 6: Decimal Precision Preservation
- Property 7: Profile Parser Error on Missing Field
- Property 8: Profile Parser Field Isolation
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

from src.parsers import ProfileParser, ParserError, ParsedProfile


class TestProfileParserProperties(unittest.TestCase):
    """Property-based tests for ProfileParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = ProfileParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
            blacklist_characters='\n\r'
        )),
        orbs=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_5_profile_parser_extraction(self, player_name, orbs):
        """
        Feature: message-parsing-system, Property 5: Profile Parser Extraction
        
        For any valid profile message with a player name and orbs value, 
        parsing should extract both the player name and the numeric orbs value correctly.
        
        **Validates: Requirements 2.1, 2.2**
        """
        # Assume player name doesn't contain "ПРОФИЛЬ" or "Орбы:" to avoid parsing conflicts
        assume("ПРОФИЛЬ" not in player_name)
        assume("Орбы:" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct a valid profile message
        message = f"""ПРОФИЛЬ {player_name}
───────────────
ID: 8685 (23.08.2025)
Ник: {player_name}
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: {orbs} (#342)
Клан: TestClan (#50)
───────────────"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert extraction is correct
        self.assertIsInstance(result, ParsedProfile)
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.orbs, orbs)
        self.assertEqual(result.game, "GD Cards")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        orbs=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=6  # Fixed decimal places up to 6
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_6_decimal_precision_preservation(self, player_name, orbs):
        """
        Feature: message-parsing-system, Property 6: Decimal Precision Preservation
        
        For any profile message with a decimal orbs value, parsing then converting 
        back to string should preserve the decimal precision (no rounding errors).
        
        **Validates: Requirements 2.3**
        """
        # Assume valid player name
        assume("ПРОФИЛЬ" not in player_name)
        assume("Орбы:" not in player_name)
        assume(player_name.strip() != "")
        
        # Store original string representation
        orbs_str = str(orbs)
        
        # Construct message with decimal orbs
        message = f"""ПРОФИЛЬ {player_name}
───────────────
Орбы: {orbs_str} (#100)
───────────────"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Convert back to string and verify precision is preserved
        result_str = str(result.orbs)
        
        # The parsed value should equal the original Decimal
        self.assertEqual(result.orbs, orbs)
        
        # String representation should match (accounting for trailing zeros)
        # Decimal("10.50") == Decimal("10.5") but str() may differ
        # So we compare the actual Decimal values
        self.assertEqual(Decimal(result_str), Decimal(orbs_str))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        extra_fields=st.lists(
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
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_7_profile_parser_error_on_missing_orbs_field(self, player_name, extra_fields):
        """
        Feature: message-parsing-system, Property 7: Profile Parser Error on Missing Field
        
        For any profile message missing the "Орбы:" field, the parser should raise 
        a ParserError indicating incomplete data.
        
        **Validates: Requirements 2.4**
        """
        # Assume valid player name
        assume("ПРОФИЛЬ" not in player_name)
        assume("Орбы:" not in player_name)
        assume(player_name.strip() != "")
        
        # Ensure extra fields don't contain "Орбы:"
        for field_name, field_value in extra_fields:
            assume("Орбы" not in field_name)
            assume("Орбы:" not in field_value)
        
        # Construct message WITHOUT "Орбы:" field
        message_lines = [f"ПРОФИЛЬ {player_name}", "───────────────"]
        
        # Add extra fields (but not Орбы:)
        for field_name, field_value in extra_fields:
            message_lines.append(f"{field_name}: {field_value}")
        
        message_lines.append("───────────────")
        message = "\n".join(message_lines)
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate missing Orbs field
        self.assertIn("Orbs field not found", str(context.exception))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        orbs=st.decimals(
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
    def test_property_8_profile_parser_field_isolation(self, player_name, orbs, 
                                                        extra_fields_before, extra_fields_after):
        """
        Feature: message-parsing-system, Property 8: Profile Parser Field Isolation
        
        For any profile message, adding or removing fields other than player name 
        and "Орбы:" should not affect the extracted values.
        
        **Validates: Requirements 2.5**
        """
        # Assume valid inputs
        assume("ПРОФИЛЬ" not in player_name)
        assume("Орбы:" not in player_name)
        assume(player_name.strip() != "")
        
        # Ensure extra fields don't interfere with parsing
        for field_name, field_value in extra_fields_before + extra_fields_after:
            assume("ПРОФИЛЬ" not in field_name and "ПРОФИЛЬ" not in field_value)
            assume("Орбы" not in field_name)
            assume("Орбы:" not in field_value)  # Ensure field values don't contain "Орбы:"
        
        # Construct message with extra fields before and after Орбы
        message_lines = [f"ПРОФИЛЬ {player_name}", "───────────────"]
        
        # Add extra fields before Орбы
        for field_name, field_value in extra_fields_before:
            message_lines.append(f"{field_name}: {field_value}")
        
        # Add the Орбы field
        message_lines.append(f"Орбы: {orbs} (#342)")
        
        # Add extra fields after Орбы
        for field_name, field_value in extra_fields_after:
            message_lines.append(f"{field_name}: {field_value}")
        
        message_lines.append("───────────────")
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that only player name and orbs are extracted correctly
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.orbs, orbs)
        self.assertEqual(result.game, "GD Cards")
        
        # Verify that the result only has the expected fields
        self.assertIsInstance(result, ParsedProfile)
        self.assertTrue(hasattr(result, 'player_name'))
        self.assertTrue(hasattr(result, 'orbs'))
        self.assertTrue(hasattr(result, 'game'))
    
    def test_profile_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Property 5: Basic extraction
        message1 = """ПРОФИЛЬ TestPlayer
───────────────
Орбы: 100.50 (#100)
───────────────"""
        result1 = self.parser.parse(message1)
        self.assertEqual(result1.player_name, "TestPlayer")
        self.assertEqual(result1.orbs, Decimal("100.50"))
        
        # Property 6: Decimal precision
        message2 = """ПРОФИЛЬ Player2
───────────────
Орбы: 123.456789 (#1)
───────────────"""
        result2 = self.parser.parse(message2)
        self.assertEqual(result2.orbs, Decimal("123.456789"))
        self.assertEqual(str(result2.orbs), "123.456789")
        
        # Property 7: Missing Orbs field
        message3 = """ПРОФИЛЬ Player3
───────────────
Очки: 100
───────────────"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message3)
        self.assertIn("Orbs field not found", str(context.exception))
        
        # Property 8: Field isolation
        message4 = """ПРОФИЛЬ Player4
───────────────
ID: 12345
Ник: Player4
Очки: 500
Орбы: 75 (#50)
Клан: TestClan
───────────────"""
        result4 = self.parser.parse(message4)
        self.assertEqual(result4.player_name, "Player4")
        self.assertEqual(result4.orbs, Decimal("75"))


if __name__ == '__main__':
    unittest.main()
