"""Integration test for MessageProcessor with full pipeline."""

import pytest
from datetime import datetime
from decimal import Decimal
import tempfile
import os

from src.message_processor import MessageProcessor
from src.classifier import MessageClassifier
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from src.balance_manager import BalanceManager
from src.coefficient_provider import CoefficientProvider
from src.repository import SQLiteRepository
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger
import logging


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def message_processor(temp_db):
    """Create a fully wired MessageProcessor with real components."""
    # Set up repository
    repository = SQLiteRepository(temp_db)
    
    # Set up coefficient provider
    coefficients = {"GD Cards": 2}
    coefficient_provider = CoefficientProvider(coefficients)
    
    # Set up logger
    logger = logging.getLogger("test_processor")
    logger.setLevel(logging.INFO)
    audit_logger = AuditLogger(logger)
    
    # Set up balance manager
    balance_manager = BalanceManager(repository, coefficient_provider, audit_logger)
    
    # Set up classifier and parsers
    classifier = MessageClassifier()
    profile_parser = ProfileParser()
    accrual_parser = AccrualParser()
    fishing_parser = FishingParser()
    karma_parser = KarmaParser()
    mafia_game_end_parser = MafiaGameEndParser()
    mafia_profile_parser = MafiaProfileParser()
    bunker_game_end_parser = BunkerGameEndParser()
    bunker_profile_parser = BunkerProfileParser()
    
    # Set up idempotency checker
    idempotency_checker = IdempotencyChecker(repository)
    
    # Create processor
    processor = MessageProcessor(
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
    
    yield processor, repository
    
    # Clean up: close database connection
    repository.conn.close()


def test_process_profile_message_full_flow(message_processor):
    """Test processing a profile message through the full pipeline."""
    processor, repository = message_processor
    
    # Process first profile message
    message = """ПРОФИЛЬ TestPlayer
Орбы: 100.5"""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    processor.process_message(message, timestamp)
    
    # Verify user was created
    user = repository.get_or_create_user("TestPlayer")
    assert user.user_name == "TestPlayer"
    assert user.bank_balance == Decimal("0")  # First parse doesn't change bank balance
    
    # Verify bot balance was initialized
    bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
    assert bot_balance is not None
    assert bot_balance.last_balance == Decimal("100.5")
    assert bot_balance.current_bot_balance == Decimal("0")


def test_process_accrual_message_full_flow(message_processor):
    """Test processing an accrual message through the full pipeline."""
    processor, repository = message_processor
    
    # Process accrual message
    message = """(🃏 НОВАЯ КАРТА 🃏
Игрок: TestPlayer
Очки: +5"""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    processor.process_message(message, timestamp)
    
    # Verify user was created
    user = repository.get_or_create_user("TestPlayer")
    assert user.user_name == "TestPlayer"
    assert user.bank_balance == Decimal("10")  # 5 * coefficient(2)
    
    # Verify bot balance was created
    bot_balance = repository.get_bot_balance(user.user_id, "GD Cards")
    assert bot_balance is not None
    assert bot_balance.current_bot_balance == Decimal("5")


def test_idempotency_prevents_duplicate_processing(message_processor):
    """Test that duplicate messages are not processed twice."""
    processor, repository = message_processor
    
    message = """(🃏 НОВАЯ КАРТА 🃏
Игрок: TestPlayer
Очки: +5"""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    # Process message first time
    processor.process_message(message, timestamp)
    
    # Get initial balance
    user = repository.get_or_create_user("TestPlayer")
    initial_balance = user.bank_balance
    
    # Process same message again
    processor.process_message(message, timestamp)
    
    # Verify balance didn't change
    user = repository.get_or_create_user("TestPlayer")
    assert user.bank_balance == initial_balance


def test_parser_error_rolls_back_transaction(message_processor):
    """Test that parser errors roll back the transaction."""
    processor, repository = message_processor
    
    # Malformed profile message (missing Орбы field)
    message = """ПРОФИЛЬ TestPlayer
Some other field"""
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    # Should raise ParserError
    with pytest.raises(ParserError):
        processor.process_message(message, timestamp)
    
    # Verify no user was created (transaction rolled back)
    cursor = repository.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM user_balances")
    count = cursor.fetchone()[0]
    assert count == 0


def test_unknown_message_type_raises_error(message_processor):
    """Test that unknown message types raise ParserError."""
    processor, repository = message_processor
    
    message = "Some random message without markers"
    timestamp = datetime(2024, 1, 1, 12, 0, 0)
    
    # Should raise ParserError
    with pytest.raises(ParserError, match="Unknown message type"):
        processor.process_message(message, timestamp)
