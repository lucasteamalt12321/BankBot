"""Message processing pipeline orchestrator."""

from datetime import datetime
from decimal import Decimal

from src.classifier import MessageClassifier, MessageType
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from src.balance_manager import BalanceManager
from src.idempotency import IdempotencyChecker
from src.audit_logger import AuditLogger


class MessageProcessor:
    """Main orchestrator for message processing."""
    
    def __init__(
        self,
        classifier: MessageClassifier,
        profile_parser: ProfileParser,
        accrual_parser: AccrualParser,
        fishing_parser: FishingParser,
        karma_parser: KarmaParser,
        mafia_game_end_parser: MafiaGameEndParser,
        mafia_profile_parser: MafiaProfileParser,
        bunker_game_end_parser: BunkerGameEndParser,
        bunker_profile_parser: BunkerProfileParser,
        balance_manager: BalanceManager,
        idempotency_checker: IdempotencyChecker,
        logger: AuditLogger
    ):
        """
        Initialize MessageProcessor with all dependencies.
        
        Args:
            classifier: MessageClassifier for determining message type
            profile_parser: ProfileParser for parsing GD Cards profile messages
            accrual_parser: AccrualParser for parsing GD Cards accrual messages
            fishing_parser: FishingParser for parsing Shmalala fishing messages
            karma_parser: KarmaParser for parsing Shmalala karma messages
            mafia_game_end_parser: MafiaGameEndParser for parsing True Mafia game end messages
            mafia_profile_parser: MafiaProfileParser for parsing True Mafia profile messages
            bunker_game_end_parser: BunkerGameEndParser for parsing BunkerRP game end messages
            bunker_profile_parser: BunkerProfileParser for parsing BunkerRP profile messages
            balance_manager: BalanceManager for processing balance updates
            idempotency_checker: IdempotencyChecker for preventing duplicate processing
            logger: AuditLogger for audit trail logging
        """
        self.classifier = classifier
        self.profile_parser = profile_parser
        self.accrual_parser = accrual_parser
        self.fishing_parser = fishing_parser
        self.karma_parser = karma_parser
        self.mafia_game_end_parser = mafia_game_end_parser
        self.mafia_profile_parser = mafia_profile_parser
        self.bunker_game_end_parser = bunker_game_end_parser
        self.bunker_profile_parser = bunker_profile_parser
        self.balance_manager = balance_manager
        self.idempotency_checker = idempotency_checker
        self.logger = logger
    
    def process_message(self, message: str, timestamp: datetime) -> None:
        """
        Process a message end-to-end with full error handling.
        
        Args:
            message: Raw message text
            timestamp: Message timestamp
            
        Raises:
            ParserError: If parsing fails
            ValueError: If configuration is missing
            Exception: For other processing errors
        """
        # Generate message ID for idempotency
        message_id = self.idempotency_checker.generate_message_id(message, timestamp)
        
        # Check if message was already processed
        if self.idempotency_checker.is_processed(message_id):
            self.logger.logger.info(f"Skipping duplicate message: {message_id}")
            return
        
        try:
            # Begin database transaction
            self.balance_manager.repository.begin_transaction()
            
            # Classify message type
            message_type = self.classifier.classify(message)
            
            # If UNKNOWN type, raise ParserError
            if message_type == MessageType.UNKNOWN:
                raise ParserError("Unknown message type")
            
            # Parse and process based on message type
            if message_type == MessageType.GDCARDS_PROFILE:
                parsed = self.profile_parser.parse(message)
                self.balance_manager.process_profile(parsed)
            
            elif message_type == MessageType.GDCARDS_ACCRUAL:
                parsed = self.accrual_parser.parse(message)
                self.balance_manager.process_accrual(parsed)
            
            elif message_type == MessageType.SHMALALA_FISHING:
                parsed = self.fishing_parser.parse(message)
                self.balance_manager.process_fishing(parsed)
            
            elif message_type == MessageType.SHMALALA_KARMA:
                parsed = self.karma_parser.parse(message)
                self.balance_manager.process_karma(parsed)
            
            elif message_type == MessageType.TRUEMAFIA_GAME_END:
                parsed = self.mafia_game_end_parser.parse(message)
                # True Mafia winners get 10 money each
                self.balance_manager.process_game_winners(
                    winners=parsed.winners,
                    game=parsed.game,
                    fixed_amount=Decimal("10")
                )
            
            elif message_type == MessageType.TRUEMAFIA_PROFILE:
                parsed = self.mafia_profile_parser.parse(message)
                self.balance_manager.process_mafia_profile(parsed)
            
            elif message_type == MessageType.BUNKERRP_GAME_END:
                parsed = self.bunker_game_end_parser.parse(message)
                # BunkerRP winners get 30 money each
                self.balance_manager.process_game_winners(
                    winners=parsed.winners,
                    game=parsed.game,
                    fixed_amount=Decimal("30")
                )
            
            elif message_type == MessageType.BUNKERRP_PROFILE:
                parsed = self.bunker_profile_parser.parse(message)
                self.balance_manager.process_bunker_profile(parsed)
            
            # Mark message as processed
            self.idempotency_checker.mark_processed(message_id)
            
            # Commit transaction
            self.balance_manager.repository.commit_transaction()
            
        except ParserError as e:
            # Rollback transaction
            self.balance_manager.repository.rollback_transaction()
            # Log error with context
            self.logger.log_error(e, "parsing")
            # Re-raise the exception
            raise
        except ValueError as e:
            # Rollback transaction
            self.balance_manager.repository.rollback_transaction()
            # Log error with context
            self.logger.log_error(e, "configuration")
            # Re-raise the exception
            raise
        except Exception as e:
            # Rollback transaction
            self.balance_manager.repository.rollback_transaction()
            # Log error with context
            self.logger.log_error(e, "processing")
            # Re-raise the exception
            raise
