"""Idempotency checking for message processing."""

import hashlib
from datetime import datetime

from src.repository import DatabaseRepository


class IdempotencyChecker:
    """Prevents duplicate message processing."""
    
    def __init__(self, repository: DatabaseRepository):
        """
        Initialize with database repository.
        
        Args:
            repository: DatabaseRepository instance for storing message IDs
        """
        self.repository = repository
    
    def generate_message_id(self, message: str, timestamp: datetime) -> str:
        """
        Generate unique ID for a message.
        
        Args:
            message: Message content
            timestamp: Message timestamp
            
        Returns:
            Unique message identifier as hexadecimal string
        """
        content = f"{message}{timestamp.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def is_processed(self, message_id: str) -> bool:
        """
        Check if message was already processed.
        
        Args:
            message_id: Unique message identifier
            
        Returns:
            True if message was already processed, False otherwise
        """
        return self.repository.message_id_exists(message_id)
    
    def mark_processed(self, message_id: str) -> None:
        """
        Mark message as processed.
        
        Args:
            message_id: Unique message identifier
        """
        self.repository.store_message_id(message_id)
