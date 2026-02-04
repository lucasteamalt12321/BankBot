"""
Message Monitoring Middleware for Advanced Telegram Bot Features
Implements middleware to intercept group messages and integrate with MessageParser
"""

import os
import sys
from typing import Optional, Dict, Any, List
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session
import structlog

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db
from core.message_parser import MessageParser
from core.advanced_models import ParsedTransaction, ParsingError
import asyncio

logger = structlog.get_logger()


class MessageMonitoringMiddleware:
    """
    Middleware to intercept group messages and process them with MessageParser
    Implements Requirements 5.1, 5.4 from the advanced features specification
    """
    
    def __init__(self):
        """Initialize the middleware"""
        self.message_parser: Optional[MessageParser] = None
        self.enabled = True
        self.processed_messages = set()  # Track processed messages to avoid duplicates
        
    def _get_message_parser(self, db_session: Session) -> MessageParser:
        """Get or create MessageParser instance"""
        if self.message_parser is None:
            self.message_parser = MessageParser(db_session)
        return self.message_parser
    
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[ParsedTransaction]:
        """
        Process incoming message through the monitoring middleware
        
        Args:
            update: Telegram update object
            context: Bot context
            
        Returns:
            ParsedTransaction if message was parsed successfully, None otherwise
            
        Validates: Requirements 5.1, 5.4
        """
        if not self.enabled:
            return None
            
        try:
            # Extract message information
            message = update.message
            if not message or not message.text:
                return None
            
            user = update.effective_user
            chat = update.effective_chat
            
            # Skip messages from bots (except external game bots we want to parse)
            if user.is_bot and not self._is_external_game_bot(message):
                return None
            
            # Create unique message identifier to avoid duplicate processing
            message_id = f"{chat.id}_{message.message_id}_{hash(message.text[:100])}"
            if message_id in self.processed_messages:
                logger.debug("Message already processed, skipping", message_id=message_id)
                return None
            
            # Add to processed messages (keep only last 1000 to prevent memory issues)
            self.processed_messages.add(message_id)
            if len(self.processed_messages) > 1000:
                # Remove oldest entries (simple approach - clear half)
                old_messages = list(self.processed_messages)[:500]
                for old_msg in old_messages:
                    self.processed_messages.discard(old_msg)
            
            # Log message for monitoring
            logger.info(
                "Processing message through monitoring middleware",
                chat_id=chat.id,
                chat_type=chat.type,
                user_id=user.id,
                message_preview=message.text[:100],
                is_bot=user.is_bot
            )
            
            # Only process messages in groups or from external bots
            if chat.type not in ["group", "supergroup"] and not self._is_external_game_bot(message):
                logger.debug("Skipping non-group message from non-game bot")
                return None
            
            # Check if message is from a configured external bot
            if not self._should_process_message(message):
                logger.debug("Message does not match processing criteria")
                return None
            
            # Get database session and process with MessageParser
            db = next(get_db())
            try:
                message_parser = self._get_message_parser(db)
                
                # Create message object for parser
                parsed_transaction = await message_parser.parse_message(message)
                
                if parsed_transaction:
                    logger.info(
                        "Message successfully parsed by middleware",
                        user_id=parsed_transaction.user_id,
                        source_bot=parsed_transaction.source_bot,
                        original_amount=parsed_transaction.original_amount,
                        converted_amount=parsed_transaction.converted_amount
                    )
                    
                    # Send notification to chat about successful parsing
                    await self._send_parsing_notification(update, context, parsed_transaction)
                    
                    return parsed_transaction
                else:
                    logger.debug("Message did not match any parsing patterns")
                    return None
                    
            except ParsingError as e:
                logger.error(
                    "Parsing error in middleware",
                    error=str(e),
                    chat_id=chat.id,
                    message_preview=message.text[:100]
                )
                return None
            except Exception as e:
                logger.error(
                    "Unexpected error in message processing middleware",
                    error=str(e),
                    chat_id=chat.id,
                    user_id=user.id
                )
                return None
            finally:
                db.close()
                
        except Exception as e:
            logger.error(
                "Critical error in message monitoring middleware",
                error=str(e),
                update_type=type(update).__name__
            )
            return None
    
    def _is_external_game_bot(self, message) -> bool:
        """
        Check if message is from an external game bot we want to monitor
        
        Args:
            message: Telegram message object
            
        Returns:
            True if message is from a configured external bot
        """
        if not message.from_user or not message.from_user.is_bot:
            return False
        
        # Check bot username or message content patterns
        bot_username = message.from_user.username
        message_text = message.text or ""
        
        # Known external game bot usernames
        external_bot_usernames = [
            'shmalala_bot',
            'gdcards_bot',
            'truemafia_bot',
            'bunkerrp_bot'
        ]
        
        if bot_username and bot_username.lower() in [name.lower() for name in external_bot_usernames]:
            return True
        
        # Check message content patterns for bot identification
        bot_patterns = [
            'Shmalala',
            'Шмалала', 
            'GDcards',
            'Монеты: +',
            'Очки: +',
            '🎣 [Рыбалка] 🎣',
            '🃏 НОВАЯ КАРТА 🃏',
            '[Игра Крокодил]'
        ]
        
        return any(pattern in message_text for pattern in bot_patterns)
    
    def _should_process_message(self, message) -> bool:
        """
        Determine if message should be processed based on content and source
        
        Args:
            message: Telegram message object
            
        Returns:
            True if message should be processed
        """
        if not message.text:
            return False
        
        message_text = message.text
        
        # Check for currency patterns that indicate external bot messages
        currency_patterns = [
            r'Монеты:\s*\+\d+',
            r'Очки:\s*\+\d+',
            r'💰\s*\+?\d+',
            r'💎\s*\+?\d+',
            r'⭐\s*\+?\d+'
        ]
        
        import re
        for pattern in currency_patterns:
            if re.search(pattern, message_text):
                return True
        
        # Check for game-specific content patterns
        game_patterns = [
            '🎣 [Рыбалка] 🎣',
            '🃏 НОВАЯ КАРТА 🃏',
            '[Игра Крокодил]',
            'Игрок:',
            'Рыбак:',
            'Карта:',
            'Редкость:',
            'Победил(а)',
            'угадал(а) слово'
        ]
        
        return any(pattern in message_text for pattern in game_patterns)
    
    async def _send_parsing_notification(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                       parsed_transaction: ParsedTransaction) -> None:
        """
        Send notification about successful parsing to the chat
        
        Args:
            update: Telegram update object
            context: Bot context
            parsed_transaction: Successfully parsed transaction
        """
        try:
            if parsed_transaction.converted_amount > 0:
                # Create notification message
                notification_text = (
                    f"💫 Обнаружена игровая активность!\n"
                    f"🎮 Источник: {parsed_transaction.source_bot}\n"
                    f"💰 Начислено: {parsed_transaction.converted_amount} монет\n"
                    f"👤 Пользователь ID: {parsed_transaction.user_id}"
                )
                
                # Send notification with a delay to avoid spam
                await asyncio.sleep(1)
                await update.message.reply_text(notification_text)
                
                logger.info(
                    "Parsing notification sent",
                    chat_id=update.effective_chat.id,
                    transaction_id=parsed_transaction.id
                )
        except Exception as e:
            logger.error(
                "Failed to send parsing notification",
                error=str(e),
                transaction_id=getattr(parsed_transaction, 'id', 'unknown')
            )
    
    def enable(self) -> None:
        """Enable message monitoring"""
        self.enabled = True
        logger.info("Message monitoring middleware enabled")
    
    def disable(self) -> None:
        """Disable message monitoring"""
        self.enabled = False
        logger.info("Message monitoring middleware disabled")
    
    def is_enabled(self) -> bool:
        """Check if middleware is enabled"""
        return self.enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get middleware statistics
        
        Returns:
            Dictionary with middleware statistics
        """
        return {
            'enabled': self.enabled,
            'processed_messages_count': len(self.processed_messages),
            'parser_initialized': self.message_parser is not None
        }
    
    def clear_processed_messages(self) -> None:
        """Clear the processed messages cache"""
        self.processed_messages.clear()
        logger.info("Processed messages cache cleared")


# Global middleware instance
message_monitoring_middleware = MessageMonitoringMiddleware()


async def process_message_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[ParsedTransaction]:
    """
    Convenience function to process messages through the global middleware instance
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        ParsedTransaction if successful, None otherwise
    """
    return await message_monitoring_middleware.process_message(update, context)


def get_middleware_instance() -> MessageMonitoringMiddleware:
    """
    Get the global middleware instance
    
    Returns:
        MessageMonitoringMiddleware instance
    """
    return message_monitoring_middleware