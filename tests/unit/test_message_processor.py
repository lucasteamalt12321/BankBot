"""Unit tests for MessageProcessor."""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from src.message_processor import MessageProcessor
from src.classifier import MessageClassifier, MessageType
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError, ParsedProfile, ParsedAccrual
)
from src.balance_manager import BalanceManager
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger


class TestProcessMessage:
    """Test process_message() method with full error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = Mock(spec=MessageClassifier)
        self.profile_parser = Mock(spec=ProfileParser)
        self.accrual_parser = Mock(spec=AccrualParser)
        self.fishing_parser = Mock(spec=FishingParser)
        self.karma_parser = Mock(spec=KarmaParser)
        self.mafia_game_end_parser = Mock(spec=MafiaGameEndParser)
        self.mafia_profile_parser = Mock(spec=MafiaProfileParser)
        self.bunker_game_end_parser = Mock(spec=BunkerGameEndParser)
        self.bunker_profile_parser = Mock(spec=BunkerProfileParser)
        self.balance_manager = Mock(spec=BalanceManager)
        self.balance_manager.repository = Mock()
        self.idempotency_checker = Mock(spec=IdempotencyChecker)
        self.logger = Mock(spec=AuditLogger)
        self.logger.logger = Mock()
        
        self.processor = MessageProcessor(
            classifier=self.classifier,
            profile_parser=self.profile_parser,
            accrual_parser=self.accrual_parser,
            fishing_parser=self.fishing_parser,
            karma_parser=self.karma_parser,
            mafia_game_end_parser=self.mafia_game_end_parser,
            mafia_profile_parser=self.mafia_profile_parser,
            bunker_game_end_parser=self.bunker_game_end_parser,
            bunker_profile_parser=self.bunker_profile_parser,
            balance_manager=self.balance_manager,
            idempotency_checker=self.idempotency_checker,
            logger=self.logger
        )
    
    def test_process_profile_message_success(self):
        """Test successful processing of a profile message."""
        # Arrange
        message = "ПРОФИЛЬ TestPlayer\nОрбы: 100.5"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.GDCARDS_PROFILE
        parsed_profile = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"))
        self.profile_parser.parse.return_value = parsed_profile
        
        # Act
        self.processor.process_message(message, timestamp)
        
        # Assert
        self.idempotency_checker.generate_message_id.assert_called_once_with(message, timestamp)
        self.idempotency_checker.is_processed.assert_called_once_with(message_id)
        self.balance_manager.repository.begin_transaction.assert_called_once()
        self.classifier.classify.assert_called_once_with(message)
        self.profile_parser.parse.assert_called_once_with(message)
        self.balance_manager.process_profile.assert_called_once_with(parsed_profile)
        self.idempotency_checker.mark_processed.assert_called_once_with(message_id)
        self.balance_manager.repository.commit_transaction.assert_called_once()
        self.balance_manager.repository.rollback_transaction.assert_not_called()
    
    def test_process_accrual_message_success(self):
        """Test successful processing of an accrual message."""
        # Arrange
        message = "(🃏 НОВАЯ КАРТА 🃏\nИгрок: TestPlayer\nОчки: +5"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.GDCARDS_ACCRUAL
        parsed_accrual = ParsedAccrual(player_name="TestPlayer", points=Decimal("5"))
        self.accrual_parser.parse.return_value = parsed_accrual
        
        # Act
        self.processor.process_message(message, timestamp)
        
        # Assert
        self.classifier.classify.assert_called_once_with(message)
        self.accrual_parser.parse.assert_called_once_with(message)
        self.balance_manager.process_accrual.assert_called_once_with(parsed_accrual)
        self.idempotency_checker.mark_processed.assert_called_once_with(message_id)
        self.balance_manager.repository.commit_transaction.assert_called_once()
    
    def test_duplicate_message_skipped(self):
        """Test that duplicate messages are skipped without processing."""
        # Arrange
        message = "ПРОФИЛЬ TestPlayer\nОрбы: 100.5"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = True
        
        # Act
        self.processor.process_message(message, timestamp)
        
        # Assert
        self.logger.logger.info.assert_called_once()
        self.balance_manager.repository.begin_transaction.assert_not_called()
        self.classifier.classify.assert_not_called()
        self.balance_manager.repository.commit_transaction.assert_not_called()
    
    def test_unknown_message_type_raises_parser_error(self):
        """Test that unknown message type raises ParserError and rolls back."""
        # Arrange
        message = "Some random message"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.UNKNOWN
        
        # Act & Assert
        with pytest.raises(ParserError, match="Unknown message type"):
            self.processor.process_message(message, timestamp)
        
        self.balance_manager.repository.begin_transaction.assert_called_once()
        self.balance_manager.repository.rollback_transaction.assert_called_once()
        self.logger.log_error.assert_called_once()
        self.balance_manager.repository.commit_transaction.assert_not_called()
        self.idempotency_checker.mark_processed.assert_not_called()
    
    def test_parser_error_rolls_back_transaction(self):
        """Test that ParserError during parsing rolls back transaction."""
        # Arrange
        message = "ПРОФИЛЬ TestPlayer"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.GDCARDS_PROFILE
        self.profile_parser.parse.side_effect = ParserError("Orbs field not found")
        
        # Act & Assert
        with pytest.raises(ParserError, match="Orbs field not found"):
            self.processor.process_message(message, timestamp)
        
        self.balance_manager.repository.rollback_transaction.assert_called_once()
        self.logger.log_error.assert_called_once()
        args = self.logger.log_error.call_args[0]
        assert isinstance(args[0], ParserError)
        assert args[1] == "parsing"
        self.balance_manager.repository.commit_transaction.assert_not_called()
    
    def test_value_error_rolls_back_transaction(self):
        """Test that ValueError (e.g., missing coefficient) rolls back transaction."""
        # Arrange
        message = "ПРОФИЛЬ TestPlayer\nОрбы: 100.5"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.GDCARDS_PROFILE
        parsed_profile = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"))
        self.profile_parser.parse.return_value = parsed_profile
        self.balance_manager.process_profile.side_effect = ValueError("No coefficient for game")
        
        # Act & Assert
        with pytest.raises(ValueError, match="No coefficient for game"):
            self.processor.process_message(message, timestamp)
        
        self.balance_manager.repository.rollback_transaction.assert_called_once()
        self.logger.log_error.assert_called_once()
        args = self.logger.log_error.call_args[0]
        assert isinstance(args[0], ValueError)
        assert args[1] == "configuration"
        self.balance_manager.repository.commit_transaction.assert_not_called()
    
    def test_generic_exception_rolls_back_transaction(self):
        """Test that generic Exception rolls back transaction."""
        # Arrange
        message = "ПРОФИЛЬ TestPlayer\nОрбы: 100.5"
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        message_id = "test_message_id"
        
        self.idempotency_checker.generate_message_id.return_value = message_id
        self.idempotency_checker.is_processed.return_value = False
        self.classifier.classify.return_value = MessageType.GDCARDS_PROFILE
        parsed_profile = ParsedProfile(player_name="TestPlayer", orbs=Decimal("100.5"))
        self.profile_parser.parse.return_value = parsed_profile
        self.balance_manager.process_profile.side_effect = Exception("Database connection failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Database connection failed"):
            self.processor.process_message(message, timestamp)
        
        self.balance_manager.repository.rollback_transaction.assert_called_once()
        self.logger.log_error.assert_called_once()
        args = self.logger.log_error.call_args[0]
        assert isinstance(args[0], Exception)
        assert args[1] == "processing"
        self.balance_manager.repository.commit_transaction.assert_not_called()
