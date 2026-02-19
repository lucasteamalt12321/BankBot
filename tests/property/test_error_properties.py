"""Property-based tests for error handling.

Tests Properties 24, 25, 26 from the message-parsing-system design:
- Property 24: Parse Error Preserves Balances
- Property 25: Missing Field Error Message
- Property 26: Error Recovery
"""

import tempfile
import os
from datetime import datetime
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock

from src.message_processor import MessageProcessor
from src.classifier import MessageClassifier
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from src.balance_manager import BalanceManager
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger


# Strategies for generating test data
player_names = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    whitelist_characters=' _-'
))

# Positive decimal values for balances (0 to 10000 with 2 decimal places)
balance_values = st.decimals(
    min_value=0,
    max_value=10000,
    places=2,
    allow_nan=False,
    allow_infinity=False
)


def create_message_processor(repository):
    """Helper function to create a MessageProcessor with all dependencies."""
    classifier = MessageClassifier()
    profile_parser = ProfileParser()
    accrual_parser = AccrualParser()
    fishing_parser = FishingParser()
    karma_parser = KarmaParser()
    mafia_game_end_parser = MafiaGameEndParser()
    mafia_profile_parser = MafiaProfileParser()
    bunker_game_end_parser = BunkerGameEndParser()
    bunker_profile_parser = BunkerProfileParser()
    
    coefficient_provider = CoefficientProvider({
        "GD Cards": 2,
        "Shmalala": 1,
        "Shmalala Karma": 10,
        "True Mafia": 15,
        "Bunker RP": 20
    })
    
    mock_logger = Mock()
    audit_logger = AuditLogger(mock_logger)
    
    balance_manager = BalanceManager(repository, coefficient_provider, audit_logger)
    idempotency_checker = IdempotencyChecker(repository)
    
    return MessageProcessor(
        classifier=classifier,
        profile_parser=profile_parser,
        accrual_parser=accrual_parser,
        fishing_parser=fishing_parser,
        karma_parser=karma_parser,
        mafia_game_end_parser=mafia_game_end_parser,
        mafia_profile_parser=mafia_profile_parser,
        bunker_game_end_parser=bunker_game_end_parser,
        bunker_profile_parser=bunker_profile_parser,
        balance_manager=balance_manager,
        idempotency_checker=idempotency_checker,
        logger=audit_logger
    )


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names,
    initial_balance=balance_values
)
def test_property_24_parse_error_preserves_balances(player_name, initial_balance):
    """
    Feature: message-parsing-system, Property 24: Parse Error Preserves Balances
    
    For any malformed message that cannot be parsed, attempting to process it 
    should raise an error and should NOT modify any balance values in the database.
    
    Validates: Requirements 19.1
    """
    # Normalize player name
    player_name = player_name.strip()
    
    # Assume valid player name
    assume(player_name != "")
    assume("ПРОФИЛЬ" not in player_name)
    assume("Орбы:" not in player_name)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # Initialize user with some balance
        user = repository.get_or_create_user(player_name)
        repository.update_user_balance(user.user_id, initial_balance)
        repository.create_bot_balance(
            user_id=user.user_id,
            game="GD Cards",
            last_balance=Decimal("100"),
            current_bot_balance=Decimal("50")
        )
        
        # Get initial state
        initial_bank_balance = repository.get_or_create_user(player_name).bank_balance
        initial_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        initial_last_balance = initial_bot_balance.last_balance
        initial_current_bot_balance = initial_bot_balance.current_bot_balance
        
        # Create a malformed profile message (missing Орбы field)
        malformed_message = f"""ПРОФИЛЬ {player_name}
Другие поля: есть
Но Орбы: отсутствует правильный формат"""
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        # Act - attempt to process malformed message
        try:
            processor.process_message(malformed_message, timestamp)
            # If no error was raised, fail the test
            assert False, "Expected ParserError to be raised for malformed message"
        except ParserError:
            # Expected error - this is correct behavior
            pass
        
        # Assert - balances should remain unchanged
        user_after = repository.get_or_create_user(player_name)
        bot_balance_after = repository.get_bot_balance(user.user_id, "GD Cards")
        
        assert user_after.bank_balance == initial_bank_balance, \
            f"Bank balance should not change after parse error: {initial_bank_balance} vs {user_after.bank_balance}"
        assert bot_balance_after.last_balance == initial_last_balance, \
            f"Last balance should not change after parse error: {initial_last_balance} vs {bot_balance_after.last_balance}"
        assert bot_balance_after.current_bot_balance == initial_current_bot_balance, \
            f"Current bot balance should not change after parse error: {initial_current_bot_balance} vs {bot_balance_after.current_bot_balance}"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names
)
def test_property_25_missing_field_error_message_profile_orbs(player_name):
    """
    Feature: message-parsing-system, Property 25: Missing Field Error Message
    
    For any message missing a required field, the parser should raise an error 
    that specifically indicates which field is missing.
    
    This test checks for missing "Орбы:" field in profile messages.
    
    Validates: Requirements 19.2
    """
    # Normalize player name
    player_name = player_name.strip()
    
    # Assume valid player name
    assume(player_name != "")
    assume("ПРОФИЛЬ" not in player_name)
    
    # Arrange
    parser = ProfileParser()
    
    # Create a profile message missing the Орбы field
    message_missing_orbs = f"""ПРОФИЛЬ {player_name}
Другие поля: присутствуют
Но нет Орбы"""
    
    # Act & Assert
    try:
        parser.parse(message_missing_orbs)
        assert False, "Expected ParserError for missing Орбы field"
    except ParserError as e:
        # Verify the error message specifically mentions the missing field
        error_message = str(e).lower()
        assert "orbs" in error_message or "орбы" in error_message, \
            f"Error message should mention missing 'Орбы' field, got: {e}"


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names
)
def test_property_25_missing_field_error_message_accrual_points(player_name):
    """
    Feature: message-parsing-system, Property 25: Missing Field Error Message
    
    For any message missing a required field, the parser should raise an error 
    that specifically indicates which field is missing.
    
    This test checks for missing "Очки:" field in accrual messages.
    
    Validates: Requirements 19.2
    """
    # Normalize player name
    player_name = player_name.strip()
    
    # Assume valid player name
    assume(player_name != "")
    assume("Игрок:" not in player_name)
    
    # Arrange
    parser = AccrualParser()
    
    # Create an accrual message missing the Очки field
    message_missing_points = f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player_name}
Другие поля: есть"""
    
    # Act & Assert
    try:
        parser.parse(message_missing_points)
        assert False, "Expected ParserError for missing Очки field"
    except ParserError as e:
        # Verify the error message specifically mentions the missing field
        error_message = str(e).lower()
        assert "points" in error_message or "очки" in error_message, \
            f"Error message should mention missing 'Очки' field, got: {e}"


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player_name=player_names
)
def test_property_25_missing_field_error_message_profile_player_name(player_name):
    """
    Feature: message-parsing-system, Property 25: Missing Field Error Message
    
    For any message missing a required field, the parser should raise an error 
    that specifically indicates which field is missing.
    
    This test checks for missing player name in profile messages.
    
    Validates: Requirements 19.2
    """
    # Arrange
    parser = ProfileParser()
    
    # Create a profile message missing the player name
    message_missing_name = """ПРОФИЛЬ
Орбы: 100
Другие поля: есть"""
    
    # Act & Assert
    try:
        parser.parse(message_missing_name)
        assert False, "Expected ParserError for missing player name"
    except ParserError as e:
        # Verify the error message specifically mentions the missing field
        error_message = str(e).lower()
        assert "player" in error_message or "name" in error_message or "имя" in error_message, \
            f"Error message should mention missing player name, got: {e}"


@settings(deadline=None)  # Disable deadline for database operations
@given(
    valid_player=player_names,
    valid_points=balance_values,
    malformed_player=player_names
)
def test_property_26_error_recovery_mixed_messages(valid_player, valid_points, malformed_player):
    """
    Feature: message-parsing-system, Property 26: Error Recovery
    
    For any sequence of messages where some are malformed, the system should 
    successfully process all valid messages and raise errors only for the 
    malformed ones, without crashing.
    
    Validates: Requirements 19.5
    """
    # Normalize player names
    valid_player = valid_player.strip()
    malformed_player = malformed_player.strip()
    
    # Assume valid player names and that they are different
    assume(valid_player != "")
    assume(malformed_player != "")
    assume(valid_player != malformed_player)  # Ensure different players
    assume("Игрок:" not in valid_player)
    assume("Очки:" not in valid_player)
    assume("Игрок:" not in malformed_player)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # Create a sequence of messages: valid, malformed, valid
        messages = [
            # Valid message 1
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {valid_player}
Очки: +{valid_points}""", datetime(2024, 1, 15, 10, 0, 0), True),
            
            # Malformed message (missing Очки field)
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {malformed_player}
Другие поля: есть""", datetime(2024, 1, 15, 10, 30, 0), False),
            
            # Valid message 2
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {valid_player}
Очки: +{valid_points}""", datetime(2024, 1, 15, 11, 0, 0), True),
        ]
        
        # Act - process all messages
        errors_raised = []
        for message, timestamp, should_succeed in messages:
            try:
                processor.process_message(message, timestamp)
                if not should_succeed:
                    # If we expected an error but didn't get one, record it
                    errors_raised.append(None)
            except ParserError as e:
                if should_succeed:
                    # If we didn't expect an error but got one, fail
                    assert False, f"Unexpected error for valid message: {e}"
                else:
                    # Expected error for malformed message
                    errors_raised.append(e)
            except Exception as e:
                # System should not crash with unexpected exceptions
                assert False, f"System crashed with unexpected exception: {e}"
        
        # Assert - verify that:
        # 1. Valid messages were processed successfully
        user = repository.get_or_create_user(valid_player)
        bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        # Two valid messages with same points should result in 2 * points in bot balance
        expected_bot_balance = valid_points * 2
        expected_bank_balance = expected_bot_balance * 2  # GD Cards coefficient is 2
        
        assert bot_balance is not None, "Bot balance should be created for valid messages"
        assert bot_balance.current_bot_balance == expected_bot_balance, \
            f"Bot balance should be {expected_bot_balance} after processing 2 valid messages, got {bot_balance.current_bot_balance}"
        assert user.bank_balance == expected_bank_balance, \
            f"Bank balance should be {expected_bank_balance}, got {user.bank_balance}"
        
        # 2. Malformed message raised an error
        assert len(errors_raised) == 1, "Should have raised exactly one error for malformed message"
        assert errors_raised[0] is not None, "Error should have been raised for malformed message"
        
        # 3. Malformed message did not create any balance for malformed_player
        malformed_user = repository.get_or_create_user(malformed_player)
        malformed_bot_balance = repository.get_bot_balance(malformed_user.user_id, "GD Cards")
        
        # Malformed message should not have created any balance
        assert malformed_bot_balance is None, \
            "Malformed message should not create bot balance"
        assert malformed_user.bank_balance == Decimal(0), \
            "Malformed message should not modify bank balance"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows


@settings(deadline=None)  # Disable deadline for database operations
@given(
    player1=player_names,
    player2=player_names,
    player3=player_names,
    points1=balance_values,
    points2=balance_values,
    points3=balance_values
)
def test_property_26_error_recovery_continues_after_multiple_errors(
    player1, player2, player3, points1, points2, points3
):
    """
    Feature: message-parsing-system, Property 26: Error Recovery
    
    For any sequence of messages with multiple malformed messages, the system 
    should continue processing and successfully handle all valid messages without 
    crashing, even after encountering multiple errors.
    
    Validates: Requirements 19.5
    """
    # Normalize player names
    player1 = player1.strip()
    player2 = player2.strip()
    player3 = player3.strip()
    
    # Assume valid player names and that they are all different
    assume(player1 != "")
    assume(player2 != "")
    assume(player3 != "")
    assume(player1 != player2)
    assume(player1 != player3)
    assume(player2 != player3)
    assume("Игрок:" not in player1)
    assume("Игрок:" not in player2)
    assume("Игрок:" not in player3)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # Create a sequence: valid, malformed, malformed, valid, malformed, valid
        messages = [
            # Valid message 1
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player1}
Очки: +{points1}""", datetime(2024, 1, 15, 10, 0, 0), True, player1),
            
            # Malformed message 1 (missing Очки)
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player2}
Нет очков""", datetime(2024, 1, 15, 10, 10, 0), False, player2),
            
            # Malformed message 2 (missing player name)
            (f"""🃏 НОВАЯ КАРТА 🃏
Очки: +100""", datetime(2024, 1, 15, 10, 20, 0), False, None),
            
            # Valid message 2
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player2}
Очки: +{points2}""", datetime(2024, 1, 15, 10, 30, 0), True, player2),
            
            # Malformed message 3 (unknown message type)
            (f"""Какое-то сообщение без маркеров""", datetime(2024, 1, 15, 10, 40, 0), False, None),
            
            # Valid message 3
            (f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player3}
Очки: +{points3}""", datetime(2024, 1, 15, 10, 50, 0), True, player3),
        ]
        
        # Act - process all messages
        valid_count = 0
        error_count = 0
        
        for message, timestamp, should_succeed, player in messages:
            try:
                processor.process_message(message, timestamp)
                if should_succeed:
                    valid_count += 1
                else:
                    # Expected error but didn't get one
                    assert False, f"Expected error for malformed message but processing succeeded"
            except (ParserError, Exception) as e:
                if should_succeed:
                    # Unexpected error for valid message
                    assert False, f"Unexpected error for valid message: {e}"
                else:
                    # Expected error for malformed message
                    error_count += 1
        
        # Assert - verify that:
        # 1. All valid messages were processed
        assert valid_count == 3, f"Should have processed 3 valid messages, got {valid_count}"
        
        # 2. All malformed messages raised errors
        assert error_count == 3, f"Should have raised 3 errors for malformed messages, got {error_count}"
        
        # 3. Each valid player has correct balance
        user1 = repository.get_or_create_user(player1)
        bot_balance1 = repository.get_bot_balance(user1.user_id, "GD Cards")
        assert bot_balance1 is not None
        assert bot_balance1.current_bot_balance == points1
        
        user2 = repository.get_or_create_user(player2)
        bot_balance2 = repository.get_bot_balance(user2.user_id, "GD Cards")
        assert bot_balance2 is not None
        assert bot_balance2.current_bot_balance == points2
        
        user3 = repository.get_or_create_user(player3)
        bot_balance3 = repository.get_bot_balance(user3.user_id, "GD Cards")
        assert bot_balance3 is not None
        assert bot_balance3.current_bot_balance == points3
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows
