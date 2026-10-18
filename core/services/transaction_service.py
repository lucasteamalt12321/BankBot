"""Shim: re-export из bank_bot/services/transaction_service.py."""
from bank_bot.services.transaction_service import TransactionService

__all__ = ["TransactionService"]
