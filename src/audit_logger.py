"""Audit logging for balance operations."""

import logging
from decimal import Decimal


class AuditLogger:
    """Logs all balance operations for audit trail."""
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize audit logger with Python logger.
        
        Args:
            logger: Python logging.Logger instance
        """
        self.logger = logger
    
    def log_profile_init(self, player: str, game: str, initial_balance: Decimal) -> None:
        """
        Log first-time profile initialization.
        
        Args:
            player: Player name
            game: Game name
            initial_balance: Initial balance value
        """
        self.logger.info(
            f"Profile initialized - Player: {player}, Game: {game}, "
            f"Initial balance: {initial_balance}"
        )
    
    def log_profile_update(
        self,
        player: str,
        game: str,
        old_balance: Decimal,
        new_balance: Decimal,
        delta: Decimal,
        bank_change: Decimal,
        coefficient: int
    ) -> None:
        """
        Log profile balance update.
        
        Args:
            player: Player name
            game: Game name
            old_balance: Previous balance value
            new_balance: New balance value
            delta: Balance change (new - old)
            bank_change: Change to bank balance
            coefficient: Game coefficient applied
        """
        self.logger.info(
            f"Profile updated - Player: {player}, Game: {game}, "
            f"Balance: {old_balance} → {new_balance} (Δ{delta}), "
            f"Bank change: {bank_change} (coef: {coefficient})"
        )
    
    def log_accrual(
        self,
        player: str,
        game: str,
        points: Decimal,
        bank_change: Decimal,
        coefficient: int
    ) -> None:
        """
        Log accrual processing.
        
        Args:
            player: Player name
            game: Game name
            points: Points awarded
            bank_change: Change to bank balance
            coefficient: Game coefficient applied
        """
        self.logger.info(
            f"Accrual processed - Player: {player}, Game: {game}, "
            f"Points: +{points}, Bank change: +{bank_change} (coef: {coefficient})"
        )
    
    def log_error(self, error: Exception, context: str) -> None:
        """
        Log error with context.
        
        Args:
            error: Exception that occurred
            context: Context description (e.g., "parsing", "processing")
        """
        self.logger.error(f"Error in {context}: {str(error)}", exc_info=True)
