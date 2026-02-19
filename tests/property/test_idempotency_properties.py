"""Property-based tests for idempotency."""

import tempfile
import os
from datetime import datetime
from decimal import Decimal
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.message_processor import MessageProcessor
from src.classifier import MessageClassifier
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser
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
    points=balance_values
)
def test_property_19_idempotency_accrual_message(player_name, points):
    """
    Feature: message-parsing-system, Property 19: Idempotency
    
    For any message, processing it twice with the same message ID should result 
    in balance changes only on the first processing; the second processing should 
    be skipped entirely.
    
    Validates: Requirements 15.1, 15.2, 15.3
    """
    from hypothesis import assume
    
    # Normalize player name (parsers strip whitespace)
    player_name = player_name.strip()
    
    # Assume valid player name (not empty, doesn't contain markers)
    assume(player_name != "")
    assume("Игрок:" not in player_name)
    assume("Очки:" not in player_name)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # Create an accrual message
        message = f"""🃏 НОВАЯ КАРТА 🃏
Игрок: {player_name}
Очки: +{points}"""
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        # Act - process the message the first time
        processor.process_message(message, timestamp)
        
        # Get balances after first processing
        user = repository.get_or_create_user(player_name)
        first_bank_balance = user.bank_balance
        first_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        first_current_bot_balance = first_bot_balance.current_bot_balance if first_bot_balance else Decimal(0)
        
        # Act - process the same message again with the same timestamp
        processor.process_message(message, timestamp)
        
        # Assert - balances should remain unchanged after second processing
        user = repository.get_or_create_user(player_name)
        second_bank_balance = user.bank_balance
        second_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        second_current_bot_balance = second_bot_balance.current_bot_balance if second_bot_balance else Decimal(0)
        
        assert second_bank_balance == first_bank_balance, \
            f"Bank balance should not change on duplicate processing: {first_bank_balance} vs {second_bank_balance}"
        assert second_current_bot_balance == first_current_bot_balance, \
            f"Bot balance should not change on duplicate processing: {first_current_bot_balance} vs {second_current_bot_balance}"
        
        # Verify the expected values from first processing
        expected_bank_balance = points * 2  # GD Cards coefficient is 2
        assert first_bank_balance == expected_bank_balance, \
            f"First processing should have set bank balance to {expected_bank_balance}"
        assert first_current_bot_balance == points, \
            f"First processing should have set bot balance to {points}"
        
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
    player_name=player_names,
    orbs=balance_values
)
def test_property_19_idempotency_profile_message(player_name, orbs):
    """
    Feature: message-parsing-system, Property 19: Idempotency
    
    For any profile message, processing it twice with the same message ID should 
    result in balance changes only on the first processing; the second processing 
    should be skipped entirely.
    
    Validates: Requirements 15.1, 15.2, 15.3
    """
    from hypothesis import assume
    
    # Normalize player name (parsers strip whitespace)
    player_name = player_name.strip()
    
    # Assume valid player name (not empty, doesn't contain markers)
    assume(player_name != "")
    assume("ПРОФИЛЬ" not in player_name)
    assume("Орбы:" not in player_name)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # Create a profile message
        message = f"""ПРОФИЛЬ {player_name}
Орбы: {orbs}
Другие поля: игнорируются"""
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        # Act - process the message the first time
        processor.process_message(message, timestamp)
        
        # Get balances after first processing
        user = repository.get_or_create_user(player_name)
        first_bank_balance = user.bank_balance
        first_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        # Bot balance should exist after first processing
        assert first_bot_balance is not None, "Bot balance should be created after first processing"
        first_last_balance = first_bot_balance.last_balance
        
        # Act - process the same message again with the same timestamp
        processor.process_message(message, timestamp)
        
        # Assert - balances should remain unchanged after second processing
        user = repository.get_or_create_user(player_name)
        second_bank_balance = user.bank_balance
        second_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        second_last_balance = second_bot_balance.last_balance
        
        assert second_bank_balance == first_bank_balance, \
            f"Bank balance should not change on duplicate processing: {first_bank_balance} vs {second_bank_balance}"
        assert second_last_balance == first_last_balance, \
            f"Last balance should not change on duplicate processing: {first_last_balance} vs {second_last_balance}"
        
        # Verify the expected values from first processing (first profile should not change bank balance)
        assert first_bank_balance == Decimal(0), \
            "First profile processing should not change bank balance"
        assert first_last_balance == orbs, \
            f"First profile processing should set last_balance to {orbs}"
        
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
    player_name=player_names,
    initial_orbs=balance_values,
    new_orbs=balance_values
)
def test_property_19_idempotency_profile_update_with_delta(player_name, initial_orbs, new_orbs):
    """
    Feature: message-parsing-system, Property 19: Idempotency
    
    For any profile update message with a delta, processing it twice with the same 
    message ID should result in balance changes only on the first processing; the 
    second processing should be skipped entirely.
    
    Validates: Requirements 15.1, 15.2, 15.3
    """
    from hypothesis import assume
    
    # Normalize player name (parsers strip whitespace)
    player_name = player_name.strip()
    
    # Assume valid player name (not empty, doesn't contain markers)
    assume(player_name != "")
    assume("ПРОФИЛЬ" not in player_name)
    assume("Орбы:" not in player_name)
    
    # Arrange - create fresh components for each test with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name
    
    try:
        repository = SQLiteRepository(test_db_path)
        processor = create_message_processor(repository)
        
        # First, initialize with a profile
        initial_message = f"""ПРОФИЛЬ {player_name}
Орбы: {initial_orbs}"""
        initial_timestamp = datetime(2024, 1, 15, 10, 0, 0)
        processor.process_message(initial_message, initial_timestamp)
        
        # Create a second profile message with different orbs
        update_message = f"""ПРОФИЛЬ {player_name}
Орбы: {new_orbs}"""
        update_timestamp = datetime(2024, 1, 15, 11, 0, 0)
        
        # Act - process the update message the first time
        processor.process_message(update_message, update_timestamp)
        
        # Get balances after first processing
        user = repository.get_or_create_user(player_name)
        first_bank_balance = user.bank_balance
        first_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        
        # Bot balance should exist after processing
        assert first_bot_balance is not None, "Bot balance should exist after processing"
        first_last_balance = first_bot_balance.last_balance
        
        # Act - process the same update message again with the same timestamp
        processor.process_message(update_message, update_timestamp)
        
        # Assert - balances should remain unchanged after second processing
        user = repository.get_or_create_user(player_name)
        second_bank_balance = user.bank_balance
        second_bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
        second_last_balance = second_bot_balance.last_balance
        
        assert second_bank_balance == first_bank_balance, \
            f"Bank balance should not change on duplicate processing: {first_bank_balance} vs {second_bank_balance}"
        assert second_last_balance == first_last_balance, \
            f"Last balance should not change on duplicate processing: {first_last_balance} vs {second_last_balance}"
        
        # Verify the expected values from first processing
        delta = new_orbs - initial_orbs
        expected_bank_balance = delta * 2  # GD Cards coefficient is 2
        assert first_bank_balance == expected_bank_balance, \
            f"First processing should have set bank balance to {expected_bank_balance} (delta {delta} * 2)"
        assert first_last_balance == new_orbs, \
            f"First processing should have updated last_balance to {new_orbs}"
        
        # Close the database connection before cleanup
        repository.conn.close()
    finally:
        # Clean up temporary database
        if os.path.exists(test_db_path):
            try:
                os.unlink(test_db_path)
            except PermissionError:
                pass  # Ignore cleanup errors on Windows
