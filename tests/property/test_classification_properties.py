#!/usr/bin/env python3
"""
Property-based tests for MessageClassifier consistency.
Feature: message-parsing-system

Tests Properties 1-4 from the design document:
- Property 1: Profile Message Classification
- Property 2: Accrual Message Classification  
- Property 3: Unknown Message Classification
- Property 4: Case-Sensitive Classification
"""

import unittest
import sys
import os

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

from src.classifier import MessageClassifier, MessageType


class TestClassificationProperties(unittest.TestCase):
    """Property-based tests for MessageClassifier consistency."""

    def setUp(self):
        """Setup test classifier."""
        self.classifier = MessageClassifier()

    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        prefix=st.text(min_size=0, max_size=100),
        suffix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_1_profile_message_classification(self, prefix, suffix):
        """
        Feature: message-parsing-system, Property 1: Profile Message Classification
        
        For any message text, if the message contains the exact string "ПРОФИЛЬ" 
        and "Орбы:", then the classifier should identify it as a GD Cards Profile message type.
        
        **Validates: Requirements 1.1**
        """
        # Construct message with both required markers
        message = f"{prefix}ПРОФИЛЬ{suffix}\nОрбы: 100"

        # Classify the message
        result = self.classifier.classify(message)

        # Assert it's classified as GD Cards Profile
        self.assertEqual(result, MessageType.GDCARDS_PROFILE,
                        "Message with 'ПРОФИЛЬ' and 'Орбы:' should be classified as GDCARDS_PROFILE")

    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        prefix=st.text(min_size=0, max_size=100),
        suffix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_2_accrual_message_classification(self, prefix, suffix):
        """
        Feature: message-parsing-system, Property 2: Accrual Message Classification
        
        For any message text, if the message contains the exact string "🃏 НОВАЯ КАРТА 🃏",
        then the classifier should identify it as a GD Cards Accrual message type.
        
        **Validates: Requirements 1.2**
        """
        # Assume the message doesn't contain profile markers (to avoid priority conflicts)
        assume("ПРОФИЛЬ" not in prefix and "ПРОФИЛЬ" not in suffix)
        assume("Орбы:" not in prefix and "Орбы:" not in suffix)

        # Construct message with accrual marker
        message = f"{prefix}🃏 НОВАЯ КАРТА 🃏{suffix}"

        # Classify the message
        result = self.classifier.classify(message)

        # Assert it's classified as GD Cards Accrual
        self.assertEqual(result, MessageType.GDCARDS_ACCRUAL,
                        "Message with '🃏 НОВАЯ КАРТА 🃏' should be classified as GDCARDS_ACCRUAL")

    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        message_text=st.text(min_size=0, max_size=200)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_3_unknown_message_classification(self, message_text):
        """
        Feature: message-parsing-system, Property 3: Unknown Message Classification
        
        For any message text that contains none of the game markers, 
        the classifier should identify it as Unknown message type.
        
        **Validates: Requirements 1.9**
        """
        # Assume message doesn't contain any game markers
        assume("ПРОФИЛЬ" not in message_text)
        assume("🃏 НОВАЯ КАРТА 🃏" not in message_text)
        assume("🎣 [Рыбалка] 🎣" not in message_text)
        assume("[Самые богатые в этом чате]" not in message_text)
        assume("Лайк! Вы повысили рейтинг пользователя" not in message_text)
        assume("[Самые крутые по Карме в этом чате]" not in message_text)
        assume("Игра окончена!" not in message_text)
        assume("Победители:" not in message_text)
        assume("💎 Камни:" not in message_text)
        assume("🎎 Активная роль:" not in message_text)
        assume("Прошли в бункер:" not in message_text)
        assume("💎 Кристаллики:" not in message_text)
        assume("🎯 Побед:" not in message_text)
        assume("💵 Деньги:" not in message_text)

        # Classify the message
        result = self.classifier.classify(message_text)

        # Assert it's classified as Unknown
        self.assertEqual(result, MessageType.UNKNOWN,
                        "Message without game markers should be classified as UNKNOWN")

    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        prefix=st.text(min_size=0, max_size=100),
        suffix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_4_case_sensitive_profile_classification(self, prefix, suffix):
        """
        Feature: message-parsing-system, Property 4: Case-Sensitive Classification (Profile)
        
        For any message text with case variations of the key phrases (e.g., "профиль", "ПРОФІЛЬ"),
        the classifier should NOT identify them as Profile messages.
        
        **Validates: Requirements 1.10**
        """
        # Test lowercase version
        message_lower = f"{prefix}профиль{suffix}\nорбы: 100"
        result_lower = self.classifier.classify(message_lower)
        self.assertNotEqual(result_lower, MessageType.GDCARDS_PROFILE,
                           "Lowercase 'профиль' should NOT be classified as GDCARDS_PROFILE")

        # Test mixed case version
        message_mixed = f"{prefix}Профиль{suffix}\nОрбы: 100"
        result_mixed = self.classifier.classify(message_mixed)
        self.assertNotEqual(result_mixed, MessageType.GDCARDS_PROFILE,
                           "Mixed case 'Профиль' should NOT be classified as GDCARDS_PROFILE")

    @unittest.skipIf(not HYPOTHESIS_AVAILABLE, "Hypothesis not available")
    @given(
        prefix=st.text(min_size=0, max_size=100),
        suffix=st.text(min_size=0, max_size=100)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_4_case_sensitive_game_end_classification(self, prefix, suffix):
        """
        Feature: message-parsing-system, Property 4: Case-Sensitive Classification (Game End)
        
        For any message text with case variations of "Игра окончена!" and "Победители:",
        the classifier should NOT identify them as True Mafia game end messages.
        
        **Validates: Requirements 1.10**
        """
        # Test lowercase version
        message_lower = f"{prefix}игра окончена!{suffix}\nпобедители:\nPlayer1"
        result_lower = self.classifier.classify(message_lower)
        self.assertNotEqual(result_lower, MessageType.TRUEMAFIA_GAME_END,
                           "Lowercase 'игра окончена!' should NOT be classified as TRUEMAFIA_GAME_END")

        # Test mixed case version
        message_mixed = f"{prefix}ИГРА ОКОНЧЕНА!{suffix}\nПОБЕДИТЕЛИ:\nPlayer1"
        result_mixed = self.classifier.classify(message_mixed)
        self.assertNotEqual(result_mixed, MessageType.TRUEMAFIA_GAME_END,
                           "Uppercase 'ИГРА ОКОНЧЕНА!' should NOT be classified as TRUEMAFIA_GAME_END")

    def test_classification_without_hypothesis(self):
        """Fallback test when Hypothesis is not available."""
        if HYPOTHESIS_AVAILABLE:
            self.skipTest("Hypothesis is available, using property-based tests")

        # Property 1: Profile classification
        message_profile = "Test ПРОФИЛЬ User\nОрбы: 100"
        self.assertEqual(self.classifier.classify(message_profile), MessageType.GDCARDS_PROFILE)

        # Property 2: Accrual classification
        message_accrual = "Test 🃏 НОВАЯ КАРТА 🃏 message"
        self.assertEqual(self.classifier.classify(message_accrual), MessageType.GDCARDS_ACCRUAL)

        # Property 3: Unknown classification
        message_unknown = "This is just a random message"
        self.assertEqual(self.classifier.classify(message_unknown), MessageType.UNKNOWN)

        # Property 4: Case sensitivity
        message_lower = "профиль User\nорбы: 100"
        self.assertNotEqual(self.classifier.classify(message_lower), MessageType.GDCARDS_PROFILE)


if __name__ == '__main__':
    unittest.main()
