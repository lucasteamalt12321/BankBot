#!/usr/bin/env python3
"""
Property-based tests for FishingParser.
Feature: message-parsing-system

Tests properties for Shmalala fishing message parsing from the design document.
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

from src.parsers import FishingParser, ParserError, ParsedFishing


class TestFishingParserProperties(unittest.TestCase):
    """Property-based tests for FishingParser."""
    
    def setUp(self):
        """Setup test parser."""
        self.parser = FishingParser()
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
            blacklist_characters='\n\r'
        )),
        coins=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_fishing_parser_extraction(self, player_name, coins):
        """
        Feature: message-parsing-system, Fishing Parser Extraction
        
        For any valid fishing message with a player name and coins value, 
        parsing should extract both the player name and the numeric coins value correctly.
        
        **Validates: Requirements 4.1, 4.2**
        """
        # Assume player name doesn't contain parsing markers to avoid conflicts
        assume("Рыбак:" not in player_name)
        assume("Монеты:" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct a valid fishing message
        total_coins = coins + Decimal("100")  # Simulate total balance
        message = f"""🎣 [Рыбалка] 🎣

Рыбак: {player_name}
Улов: Золотая рыбка
Монеты: +{coins} ({total_coins})💰"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert extraction is correct
        self.assertIsInstance(result, ParsedFishing)
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.coins, coins)
        self.assertEqual(result.game, "Shmalala")
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        coins=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.99"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        ),
        total_coins=st.decimals(
            min_value=Decimal("100"),
            max_value=Decimal("1000000"),
            allow_nan=False,
            allow_infinity=False,
            places=2
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_fishing_parser_extracts_accrual_not_total(self, player_name, coins, total_coins):
        """
        Feature: message-parsing-system, Fishing Parser Accrual Extraction
        
        The parser should extract only the accrual amount (after +), 
        not the total in parentheses.
        
        **Validates: Requirements 4.3**
        """
        # Assume valid inputs
        assume("Рыбак:" not in player_name)
        assume("Монеты:" not in player_name)
        assume(player_name.strip() != "")
        # Ensure coins and total_coins are different to test extraction
        assume(coins != total_coins)
        
        # Construct message with both accrual and total
        message = f"""🎣 [Рыбалка] 🎣

Рыбак: {player_name}
Улов: Обычная рыба
Монеты: +{coins} ({total_coins})💰"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that only the accrual amount is extracted, not the total
        self.assertEqual(result.coins, coins)
        self.assertNotEqual(result.coins, total_coins)
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        coins_value=st.one_of(
            st.text(min_size=1, max_size=20, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll'),  # Only letters
            )),
            st.just(""),  # Empty string
            st.just("-5"),  # Negative without plus
            st.just("5"),  # Positive without plus
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_fishing_parser_error_on_malformed_coins(self, player_name, coins_value):
        """
        Feature: message-parsing-system, Fishing Parser Error on Malformed Coins
        
        For any fishing message where "Монеты:" does not contain a plus sign and number, 
        the parser should raise a ParserError.
        
        **Validates: Requirements 4.4**
        """
        # Assume valid player name
        assume("Рыбак:" not in player_name)
        assume("Монеты:" not in player_name)
        assume(player_name.strip() != "")
        
        # Construct message with malformed coins field (no plus sign or invalid format)
        message = f"""🎣 [Рыбалка] 🎣

Рыбак: {player_name}
Улов: Золотая рыбка
Монеты: {coins_value} (100)💰"""
        
        # Parsing should raise ParserError
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message)
        
        # Error message should indicate the issue
        error_msg = str(context.exception)
        self.assertTrue(
            "Coins field not found" in error_msg or
            "Invalid coins value" in error_msg,
            f"Expected error about malformed coins, got: {error_msg}"
        )
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        player_name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters='\n\r'
        )),
        coins=st.decimals(
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
    def test_fishing_parser_field_isolation(self, player_name, coins,
                                            extra_fields_before, extra_fields_after):
        """
        Feature: message-parsing-system, Fishing Parser Field Isolation
        
        For any fishing message, adding or removing fields other than player name 
        and "Монеты:" should not affect the extracted values.
        """
        # Assume valid inputs
        assume("Рыбак:" not in player_name)
        assume("Монеты:" not in player_name)
        assume(player_name.strip() != "")
        
        # Ensure extra fields don't interfere with parsing
        for field_name, field_value in extra_fields_before + extra_fields_after:
            assume("Рыбак" not in field_name and "Рыбак:" not in field_value)
            assume("Монеты" not in field_name)
            assume("Монеты:" not in field_value)
            assume("+" not in field_value or "Монеты" not in field_value)
        
        # Construct message with extra fields before and after Монеты
        message_lines = ["🎣 [Рыбалка] 🎣", ""]
        message_lines.append(f"Рыбак: {player_name}")
        
        # Add extra fields before Монеты
        for field_name, field_value in extra_fields_before:
            message_lines.append(f"{field_name}: {field_value}")
        
        # Add the Монеты field
        total_coins = coins + Decimal("100")
        message_lines.append(f"Монеты: +{coins} ({total_coins})💰")
        
        # Add extra fields after Монеты
        for field_name, field_value in extra_fields_after:
            message_lines.append(f"{field_name}: {field_value}")
        
        message = "\n".join(message_lines)
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert that only player name and coins are extracted correctly
        self.assertEqual(result.player_name, player_name.strip())
        self.assertEqual(result.coins, coins)
        self.assertEqual(result.game, "Shmalala")
        
        # Verify that the result only has the expected fields
        self.assertIsInstance(result, ParsedFishing)
        self.assertTrue(hasattr(result, 'player_name'))
        self.assertTrue(hasattr(result, 'coins'))
        self.assertTrue(hasattr(result, 'game'))
    
    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        coins=st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("999999.999999"),
            allow_nan=False,
            allow_infinity=False,
            places=6
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_fishing_parser_preserves_decimal_precision(self, coins):
        """
        Feature: message-parsing-system, Fishing Parser Decimal Precision
        
        For any fishing message with a decimal coins value, 
        parsing then converting back to string should preserve the decimal precision.
        
        **Validates: Requirements 4.5**
        """
        # Construct message with decimal coins
        message = f"""🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: +{coins} (1000)💰"""
        
        # Parse the message
        result = self.parser.parse(message)
        
        # Assert decimal precision is preserved
        self.assertEqual(result.coins, coins)
        self.assertEqual(str(result.coins), str(coins))
    
    def test_fishing_parser_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")
        
        # Basic extraction
        message1 = """🎣 [Рыбалка] 🎣

Рыбак: TestPlayer
Улов: Золотая рыбка
Монеты: +5 (225)💰"""
        result1 = self.parser.parse(message1)
        self.assertEqual(result1.player_name, "TestPlayer")
        self.assertEqual(result1.coins, Decimal("5"))
        
        # Extracts accrual not total
        message2 = """🎣 [Рыбалка] 🎣

Рыбак: Player2
Улов: Обычная рыба
Монеты: +75 (1000)💰"""
        result2 = self.parser.parse(message2)
        self.assertEqual(result2.coins, Decimal("75"))
        self.assertNotEqual(result2.coins, Decimal("1000"))
        
        # Malformed coins (no plus sign)
        message3 = """🎣 [Рыбалка] 🎣

Рыбак: Player3
Улов: Золотая рыбка
Монеты: 10 (100)💰"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message3)
        self.assertIn("Coins field not found", str(context.exception))
        
        # Malformed coins (invalid value)
        message4 = """🎣 [Рыбалка] 🎣

Рыбак: Player4
Улов: Золотая рыбка
Монеты: +abc (100)💰"""
        with self.assertRaises(ParserError) as context:
            self.parser.parse(message4)
        self.assertIn("Invalid coins value", str(context.exception))
        
        # Field isolation
        message5 = """🎣 [Рыбалка] 🎣

Рыбак: Player5
Улов: Золотая рыбка
Редкость: Легендарная
Вес: 5 кг
Монеты: +50 (500)💰
Опыт: +10"""
        result5 = self.parser.parse(message5)
        self.assertEqual(result5.player_name, "Player5")
        self.assertEqual(result5.coins, Decimal("50"))


if __name__ == '__main__':
    unittest.main()
