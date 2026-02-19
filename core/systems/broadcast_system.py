"""
BroadcastSystem - Advanced message broadcasting for Telegram bot
Implements async message delivery with batch processing and error handling
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.error import TelegramError, BadRequest, Forbidden

from database.database import User
from core.models.advanced_models import BroadcastResult, NotificationResult, BroadcastError
from utils.admin.admin_system import AdminSystem

logger = logging.getLogger(__name__)


class BroadcastSystem:
    """
    Advanced broadcast system for sending messages to multiple users
    Implements Requirements 3.1, 4.2, 4.4, 8.1, 8.4
    """
    
    def __init__(self, db: Session, bot: Bot, admin_system: AdminSystem = None):
        """
        Initialize BroadcastSystem
        
        Args:
            db: Database session
            bot: Telegram bot instance
            admin_system: Admin system for privilege checking
        """
        self.db = db
        self.bot = bot
        self.admin_system = admin_system
        self.batch_size = 50  # Default batch size for processing
        self.rate_limit_delay = 0.15  # Delay between messages to respect rate limits
        self.max_retries = 3  # Maximum retry attempts for failed sends
    
    async def broadcast_to_all(self, message: str, sender_id: int) -> BroadcastResult:
        """
        Broadcast message to all registered users (Requirement 8.1)
        
        Args:
            message: Message text to broadcast
            sender_id: ID of the user sending the broadcast
            
        Returns:
            BroadcastResult: Results of the broadcast operation
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Starting broadcast to all users from sender {sender_id}")
            
            # Get all registered users
            all_users = self.db.query(User).filter(User.telegram_id.isnot(None)).all()
            
            if not all_users:
                return BroadcastResult(
                    total_users=0,
                    successful_sends=0,
                    failed_sends=0,
                    errors=["No registered users found"],
                    completion_message="No users to broadcast to",
                    execution_time=time.time() - start_time
                )
            
            # Prepare message with sender info
            sender_user = self.db.query(User).filter(User.telegram_id == sender_id).first()
            sender_name = sender_user.first_name if sender_user and sender_user.first_name else f"User #{sender_id}"
            
            formatted_message = f"📢 <b>Объявление от {sender_name}:</b>\n\n{message}"
            
            # Process broadcast in batches
            result = await self._process_broadcast_batches(
                users=all_users,
                message=formatted_message,
                sender_id=sender_id
            )
            
            # Add execution time
            result.execution_time = time.time() - start_time
            
            logger.info(f"Broadcast completed: {result.successful_sends}/{result.total_users} successful")
            return result
            
        except Exception as e:
            logger.error(f"Error in broadcast_to_all: {e}")
            raise BroadcastError(f"Failed to broadcast message: {str(e)}")
    
    async def mention_all_users(self, message: str, sender_id: int) -> BroadcastResult:
        """
        Broadcast message with @mention tags to all users (Requirement 4.2)
        
        Args:
            message: Message text to broadcast
            sender_id: ID of the user sending the broadcast
            
        Returns:
            BroadcastResult: Results of the broadcast operation
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Starting mention-all broadcast from sender {sender_id}")
            
            # Get all registered users
            all_users = self.db.query(User).filter(User.telegram_id.isnot(None)).all()
            
            if not all_users:
                return BroadcastResult(
                    total_users=0,
                    successful_sends=0,
                    failed_sends=0,
                    errors=["No registered users found"],
                    completion_message="No users to mention",
                    execution_time=time.time() - start_time
                )
            
            # Get sender info
            sender_user = self.db.query(User).filter(User.telegram_id == sender_id).first()
            sender_name = sender_user.first_name if sender_user and sender_user.first_name else f"User #{sender_id}"
            
            # Create mention list (limit to avoid message length issues)
            mentions = []
            for user in all_users[:50]:  # Limit mentions to avoid telegram limits
                if user.username:
                    mentions.append(f"@{user.username}")
                elif user.first_name:
                    mentions.append(f"[{user.first_name}](tg://user?id={user.telegram_id})")
                else:
                    mentions.append(f"[User](tg://user?id={user.telegram_id})")
            
            # Format message with mentions
            mention_text = " ".join(mentions)
            formatted_message = f"📢 <b>Сообщение от {sender_name} для всех:</b>\n\n{message}\n\n{mention_text}"
            
            # Process broadcast in batches
            result = await self._process_broadcast_batches(
                users=all_users,
                message=formatted_message,
                sender_id=sender_id,
                use_markdown=True
            )
            
            # Add execution time
            result.execution_time = time.time() - start_time
            
            logger.info(f"Mention-all broadcast completed: {result.successful_sends}/{result.total_users} successful")
            return result
            
        except Exception as e:
            logger.error(f"Error in mention_all_users: {e}")
            raise BroadcastError(f"Failed to mention all users: {str(e)}")
    
    async def notify_admins(self, notification: str, sender_id: int = None, purchase_info: dict = None) -> NotificationResult:
        """
        Send notification to all administrators (Requirement 3.1, 3.2, 3.3, 3.4)
        
        Args:
            notification: Notification message
            sender_id: ID of the user who triggered the notification (optional)
            purchase_info: Dictionary with purchase details for admin item notifications
            
        Returns:
            NotificationResult: Results of the notification operation
        """
        try:
            logger.info(f"Sending admin notification from sender {sender_id}")
            
            # Get all admin users from database
            admin_users = self.db.query(User).filter(
                User.is_admin == True,
                User.telegram_id.isnot(None)
            ).all()
            
            # Fallback admin user IDs if no admins in database (Requirement 3.3)
            from src.config import settings
            fallback_admin_ids = [settings.ADMIN_TELEGRAM_ID]  # LucasTeamLuke
            
            if not admin_users:
                # Try to get fallback admin users
                admin_users = self.db.query(User).filter(
                    User.telegram_id.in_(fallback_admin_ids)
                ).all()
                
                if not admin_users:
                    logger.warning("No admin users found for notification")
                    return NotificationResult(
                        success=False,
                        message="No admin users found",
                        notified_admins=0,
                        failed_notifications=0
                    )
            
            # Format notification message with purchase information (Requirement 3.2)
            formatted_notification = self._format_admin_notification(
                notification, sender_id, purchase_info
            )
            
            # Send notifications to all admins
            successful_sends = 0
            failed_sends = 0
            errors = []
            
            for admin_user in admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=admin_user.telegram_id,
                        text=formatted_notification,
                        parse_mode='HTML'
                    )
                    successful_sends += 1
                    logger.debug(f"Notification sent to admin {admin_user.telegram_id}")
                    
                    # Rate limiting
                    await asyncio.sleep(self.rate_limit_delay)
                    
                except Exception as e:
                    failed_sends += 1
                    error_msg = f"Failed to notify admin {admin_user.telegram_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            success = successful_sends > 0
            message = f"Notified {successful_sends} administrators"
            if failed_sends > 0:
                message += f", {failed_sends} failed"
            
            logger.info(f"Admin notification completed: {successful_sends} successful, {failed_sends} failed")
            
            return NotificationResult(
                success=success,
                message=message,
                notified_admins=successful_sends,
                failed_notifications=failed_sends
            )
            
        except Exception as e:
            logger.error(f"Error in notify_admins: {e}")
            return NotificationResult(
                success=False,
                message=f"Failed to send admin notifications: {str(e)}",
                notified_admins=0,
                failed_notifications=len(admin_users) if 'admin_users' in locals() else 0
            )
    
    def _format_admin_notification(self, notification: str, sender_id: int = None, purchase_info: dict = None) -> str:
        """
        Format admin notification message with proper structure (Requirement 3.2)
        
        Args:
            notification: Base notification message
            sender_id: ID of the user who triggered the notification
            purchase_info: Dictionary with purchase details
            
        Returns:
            Formatted notification message
        """
        try:
            from datetime import datetime
            
            # Base notification header
            if purchase_info:
                header = "🛒 <b>Уведомление о покупке админ-товара</b>"
            else:
                header = "🔔 <b>Уведомление для администраторов</b>"
            
            # Get sender information (Requirement 3.2)
            sender_info = ""
            if sender_id:
                sender_user = self.db.query(User).filter(User.telegram_id == sender_id).first()
                if sender_user:
                    sender_info = f"👤 <b>Пользователь:</b> {sender_user.first_name or 'Unknown'}"
                    if sender_user.username:
                        sender_info += f" (@{sender_user.username})"
                    sender_info += f"\n🆔 <b>ID:</b> {sender_id}"
                    if sender_user.balance is not None:
                        sender_info += f"\n💰 <b>Баланс:</b> {sender_user.balance}"
                else:
                    sender_info = f"👤 <b>Пользователь ID:</b> {sender_id}"
            
            # Add timestamp (Requirement 3.2)
            timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            time_info = f"⏰ <b>Время:</b> {timestamp}"
            
            # Add purchase information if available
            purchase_details = ""
            if purchase_info:
                item_name = purchase_info.get('item_name', 'Unknown')
                item_price = purchase_info.get('item_price', 'Unknown')
                purchase_id = purchase_info.get('purchase_id', 'Unknown')
                
                purchase_details = f"\n\n🛍️ <b>Детали покупки:</b>"
                purchase_details += f"\n📦 <b>Товар:</b> {item_name}"
                purchase_details += f"\n💵 <b>Цена:</b> {item_price}"
                purchase_details += f"\n🔢 <b>ID покупки:</b> {purchase_id}"
            
            # Combine all parts
            parts = [header]
            if sender_info:
                parts.append(sender_info)
            parts.append(time_info)
            if purchase_details:
                parts.append(purchase_details)
            if notification and notification.strip():
                parts.append(f"\n📝 <b>Сообщение:</b>\n{notification}")
            
            return "\n\n".join(parts)
            
        except Exception as e:
            logger.error(f"Error formatting admin notification: {e}")
            # Fallback to simple format
            return f"🔔 <b>Уведомление для администраторов</b>\n\n{notification}"
    
    async def _process_broadcast_batches(
        self, 
        users: List[User], 
        message: str, 
        sender_id: int,
        use_markdown: bool = False
    ) -> BroadcastResult:
        """
        Process broadcast in batches with async delivery (Requirement 4.4)
        
        Args:
            users: List of users to send message to
            message: Message to send
            sender_id: ID of sender
            use_markdown: Whether to use markdown parsing
            
        Returns:
            BroadcastResult: Results of the broadcast operation
        """
        total_users = len(users)
        successful_sends = 0
        failed_sends = 0
        errors = []
        
        # Process users in batches
        for i in range(0, total_users, self.batch_size):
            batch = users[i:i + self.batch_size]
            logger.debug(f"Processing batch {i//self.batch_size + 1}: {len(batch)} users")
            
            # Create tasks for concurrent sending within batch
            tasks = []
            for user in batch:
                if user.telegram_id:
                    task = self._send_message_with_retry(
                        user.telegram_id, 
                        message, 
                        use_markdown
                    )
                    tasks.append(task)
            
            # Execute batch concurrently
            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        failed_sends += 1
                        errors.append(str(result))
                    elif result:
                        successful_sends += 1
                    else:
                        failed_sends += 1
                        errors.append("Unknown error in message sending")
            
            # Rate limiting between batches
            if i + self.batch_size < total_users:
                await asyncio.sleep(1.0)  # Longer delay between batches
        
        completion_message = f"Broadcast completed: {successful_sends} successful, {failed_sends} failed"
        
        return BroadcastResult(
            total_users=total_users,
            successful_sends=successful_sends,
            failed_sends=failed_sends,
            errors=errors[:10],  # Limit error list to avoid memory issues
            completion_message=completion_message
        )
    
    async def _send_message_with_retry(
        self, 
        chat_id: int, 
        message: str, 
        use_markdown: bool = False
    ) -> bool:
        """
        Send message with retry logic (Requirement 4.5, 8.5)
        
        Args:
            chat_id: Telegram chat ID
            message: Message to send
            use_markdown: Whether to use markdown parsing
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                parse_mode = 'Markdown' if use_markdown else 'HTML'
                
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
                
                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay)
                return True
                
            except Forbidden:
                # User blocked the bot - don't retry
                logger.debug(f"User {chat_id} has blocked the bot")
                return False
                
            except BadRequest as e:
                # Bad request - don't retry
                logger.warning(f"Bad request for user {chat_id}: {e}")
                return False
                
            except TelegramError as e:
                # Other telegram errors - retry
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.warning(f"Telegram error for user {chat_id}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to send message to user {chat_id} after {self.max_retries} attempts: {e}")
                    return False
                    
            except Exception as e:
                # Unexpected errors - retry
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Unexpected error for user {chat_id}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Unexpected error sending to user {chat_id} after {self.max_retries} attempts: {e}")
                    return False
        
        return False
    
    def set_batch_size(self, batch_size: int):
        """Set the batch size for processing broadcasts"""
        if batch_size > 0:
            self.batch_size = batch_size
            logger.info(f"Broadcast batch size set to {batch_size}")
    
    def set_rate_limit_delay(self, delay: float):
        """Set the rate limit delay between messages"""
        if delay >= 0:
            self.rate_limit_delay = delay
            logger.info(f"Rate limit delay set to {delay}s")
    
    def set_max_retries(self, max_retries: int):
        """Set the maximum number of retry attempts"""
        if max_retries >= 0:
            self.max_retries = max_retries
            logger.info(f"Max retries set to {max_retries}")
    
    def get_admin_user_ids(self) -> List[int]:
        """
        Get list of all admin user IDs (Requirement 3.3)
        
        Returns:
            List of admin user Telegram IDs
        """
        try:
            admin_users = self.db.query(User).filter(
                User.is_admin == True,
                User.telegram_id.isnot(None)
            ).all()
            
            admin_ids = [user.telegram_id for user in admin_users]
            
            # Add fallback admin IDs if no admins found in database
            from src.config import settings
            fallback_admin_ids = [settings.ADMIN_TELEGRAM_ID]  # LucasTeamLuke
            if not admin_ids:
                admin_ids = fallback_admin_ids
            
            logger.info(f"Retrieved {len(admin_ids)} admin user IDs")
            return admin_ids
            
        except Exception as e:
            logger.error(f"Error getting admin user IDs: {e}")
            from src.config import settings
            return [settings.ADMIN_TELEGRAM_ID]  # Fallback
    
    def add_admin_user(self, user_id: int) -> bool:
        """
        Add a user to the admin list (Requirement 3.3)
        
        Args:
            user_id: Telegram user ID to add as admin
            
        Returns:
            True if user was added successfully, False otherwise
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return False
            
            if user.is_admin:
                logger.info(f"User {user_id} is already an admin")
                return True
            
            user.is_admin = True
            self.db.commit()
            
            logger.info(f"User {user_id} added as admin")
            return True
            
        except Exception as e:
            logger.error(f"Error adding admin user {user_id}: {e}")
            self.db.rollback()
            return False
    
    def remove_admin_user(self, user_id: int) -> bool:
        """
        Remove a user from the admin list (Requirement 3.3)
        
        Args:
            user_id: Telegram user ID to remove from admin
            
        Returns:
            True if user was removed successfully, False otherwise
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return False
            
            if not user.is_admin:
                logger.info(f"User {user_id} is not an admin")
                return True
            
            user.is_admin = False
            self.db.commit()
            
            logger.info(f"User {user_id} removed from admin")
            return True
            
        except Exception as e:
            logger.error(f"Error removing admin user {user_id}: {e}")
            self.db.rollback()
            return False
    
    async def send_purchase_confirmation(self, user_id: int, purchase_info: dict) -> bool:
        """
        Send purchase confirmation to the user (Requirement 3.4)
        
        Args:
            user_id: Telegram user ID who made the purchase
            purchase_info: Dictionary with purchase details
            
        Returns:
            True if confirmation was sent successfully, False otherwise
        """
        try:
            # Format confirmation message
            item_name = purchase_info.get('item_name', 'Unknown')
            item_price = purchase_info.get('item_price', 'Unknown')
            purchase_id = purchase_info.get('purchase_id', 'Unknown')
            
            confirmation_message = (
                f"✅ <b>Покупка подтверждена!</b>\n\n"
                f"📦 <b>Товар:</b> {item_name}\n"
                f"💵 <b>Цена:</b> {item_price}\n"
                f"🔢 <b>ID покупки:</b> {purchase_id}\n\n"
                f"🔔 Администраторы уведомлены о вашей покупке."
            )
            
            await self.bot.send_message(
                chat_id=user_id,
                text=confirmation_message,
                parse_mode='HTML'
            )
            
            logger.info(f"Purchase confirmation sent to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending purchase confirmation to user {user_id}: {e}")
            return False