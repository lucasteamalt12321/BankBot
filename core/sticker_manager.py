"""
StickerManager class for Advanced Telegram Bot Features
Implements sticker access management with time-based permissions and automatic cleanup
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import User, ScheduledTask
from core.advanced_models import CleanupResult, StickerAccessError
import structlog

logger = structlog.get_logger()


class StickerManager:
    """
    Manages sticker access permissions and automatic cleanup for the advanced bot features
    Implements Requirements 2.1, 2.2, 2.3, 2.4, 2.5 from the advanced features specification
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize StickerManager with database session
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    async def grant_unlimited_access(self, user_id: int, duration_hours: int = 24) -> None:
        """
        Grant unlimited sticker access to a user for specified duration
        
        Args:
            user_id: Telegram user ID to grant access to
            duration_hours: Duration in hours for unlimited access (default: 24)
            
        Raises:
            StickerAccessError: If user not found or database error occurs
            
        Validates: Requirements 2.1, 2.2
        """
        try:
            logger.info("Granting unlimited sticker access", user_id=user_id, duration_hours=duration_hours)
            
            # Get user from database
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                raise StickerAccessError(
                    user_id=user_id,
                    message=f"User with ID {user_id} not found in database"
                )
            
            # Set unlimited access flag and expiration time
            user.sticker_unlimited = True
            user.sticker_unlimited_until = datetime.utcnow() + timedelta(hours=duration_hours)
            
            # Commit the changes
            self.db.commit()
            
            logger.info(
                "Unlimited sticker access granted successfully",
                user_id=user_id,
                username=user.username,
                expires_at=user.sticker_unlimited_until,
                duration_hours=duration_hours
            )
            
        except StickerAccessError:
            # Re-raise StickerAccessError as-is
            raise
        except Exception as e:
            logger.error("Error granting unlimited sticker access", error=str(e), user_id=user_id)
            self.db.rollback()
            raise StickerAccessError(
                user_id=user_id,
                message=f"Database error while granting access: {str(e)}"
            )
    
    async def check_access(self, user_id: int) -> bool:
        """
        Check if user has unlimited sticker access and it hasn't expired
        
        Args:
            user_id: Telegram user ID to check access for
            
        Returns:
            True if user has valid unlimited access, False otherwise
            
        Validates: Requirements 2.3
        """
        try:
            logger.debug("Checking sticker access", user_id=user_id)
            
            # Get user from database
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning("User not found for access check", user_id=user_id)
                return False
            
            # Check if unlimited access is enabled
            if not user.sticker_unlimited:
                logger.debug("User does not have unlimited sticker access", user_id=user_id)
                return False
            
            # Check if access has expired
            current_time = datetime.utcnow()
            if user.sticker_unlimited_until and current_time >= user.sticker_unlimited_until:
                logger.info("Sticker access expired, revoking access", user_id=user_id, expired_at=user.sticker_unlimited_until)
                
                # Automatically revoke expired access
                user.sticker_unlimited = False
                user.sticker_unlimited_until = None
                self.db.commit()
                
                return False
            
            logger.debug(
                "User has valid unlimited sticker access",
                user_id=user_id,
                expires_at=user.sticker_unlimited_until
            )
            
            return True
            
        except Exception as e:
            logger.error("Error checking sticker access", error=str(e), user_id=user_id)
            return False
    
    async def cleanup_expired_stickers(self) -> int:
        """
        Clean up expired sticker access for all users
        This method is designed to be called by background tasks
        
        Returns:
            Number of users whose access was cleaned up
            
        Validates: Requirements 2.4, 12.2
        """
        try:
            logger.info("Starting cleanup of expired sticker access")
            
            current_time = datetime.utcnow()
            
            # Find all users with expired sticker access
            expired_users = self.db.query(User).filter(
                User.sticker_unlimited == True,
                User.sticker_unlimited_until <= current_time
            ).all()
            
            cleanup_count = 0
            
            for user in expired_users:
                try:
                    logger.info(
                        "Cleaning up expired sticker access",
                        user_id=user.telegram_id,
                        username=user.username,
                        expired_at=user.sticker_unlimited_until
                    )
                    
                    # Revoke unlimited access
                    user.sticker_unlimited = False
                    user.sticker_unlimited_until = None
                    
                    cleanup_count += 1
                    
                except Exception as user_error:
                    logger.error(
                        "Error cleaning up individual user",
                        error=str(user_error),
                        user_id=user.telegram_id
                    )
                    continue
            
            # Commit all changes
            if cleanup_count > 0:
                self.db.commit()
                logger.info(f"Cleaned up expired sticker access for {cleanup_count} users")
            else:
                logger.debug("No expired sticker access found to clean up")
            
            return cleanup_count
            
        except Exception as e:
            logger.error("Error during sticker access cleanup", error=str(e))
            self.db.rollback()
            return 0
    
    async def auto_delete_sticker(self, message_id: int, delay_minutes: int = 2) -> None:
        """
        Schedule automatic deletion of a sticker message after specified delay
        This method is used when users don't have unlimited access
        
        Args:
            message_id: Telegram message ID of the sticker to delete
            delay_minutes: Delay in minutes before deletion (default: 2)
            
        Validates: Requirements 2.5
        """
        try:
            logger.info("Scheduling sticker auto-deletion", message_id=message_id, delay_minutes=delay_minutes)
            
            # Calculate deletion time
            delete_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            # Create scheduled task for sticker deletion
            scheduled_task = ScheduledTask(
                user_id=None,  # System task, not user-specific
                message_id=message_id,
                chat_id=0,  # Will be set by the calling context
                task_type="auto_delete_sticker",
                execute_at=delete_at,
                task_data={
                    "message_id": message_id,
                    "delay_minutes": delay_minutes,
                    "scheduled_at": datetime.utcnow().isoformat()
                }
            )
            
            self.db.add(scheduled_task)
            self.db.commit()
            
            logger.info(
                "Sticker auto-deletion scheduled successfully",
                message_id=message_id,
                delete_at=delete_at,
                task_id=scheduled_task.id
            )
            
        except Exception as e:
            logger.error("Error scheduling sticker auto-deletion", error=str(e), message_id=message_id)
            self.db.rollback()
    
    def get_user_sticker_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get detailed sticker access status for a user
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dictionary with sticker access details
        """
        try:
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                return {
                    "found": False,
                    "has_unlimited": False,
                    "expires_at": None,
                    "is_expired": True
                }
            
            current_time = datetime.utcnow()
            is_expired = (
                user.sticker_unlimited_until is not None and 
                current_time >= user.sticker_unlimited_until
            )
            
            return {
                "found": True,
                "has_unlimited": user.sticker_unlimited,
                "expires_at": user.sticker_unlimited_until.isoformat() if user.sticker_unlimited_until else None,
                "is_expired": is_expired,
                "time_remaining": (
                    str(user.sticker_unlimited_until - current_time) 
                    if user.sticker_unlimited_until and not is_expired 
                    else None
                )
            }
            
        except Exception as e:
            logger.error("Error getting user sticker status", error=str(e), user_id=user_id)
            return {
                "found": False,
                "has_unlimited": False,
                "expires_at": None,
                "is_expired": True,
                "error": str(e)
            }
    
    async def revoke_access(self, user_id: int) -> bool:
        """
        Manually revoke unlimited sticker access for a user
        
        Args:
            user_id: Telegram user ID to revoke access from
            
        Returns:
            True if access was revoked successfully, False otherwise
        """
        try:
            logger.info("Manually revoking sticker access", user_id=user_id)
            
            user = self.db.query(User).filter(User.telegram_id == user_id).first()
            if not user:
                logger.warning("User not found for access revocation", user_id=user_id)
                return False
            
            # Revoke access
            user.sticker_unlimited = False
            user.sticker_unlimited_until = None
            
            self.db.commit()
            
            logger.info("Sticker access revoked successfully", user_id=user_id, username=user.username)
            return True
            
        except Exception as e:
            logger.error("Error revoking sticker access", error=str(e), user_id=user_id)
            self.db.rollback()
            return False
    
    def get_all_users_with_access(self) -> List[Dict[str, Any]]:
        """
        Get all users who currently have unlimited sticker access
        
        Returns:
            List of dictionaries with user access information
        """
        try:
            users_with_access = self.db.query(User).filter(
                User.sticker_unlimited == True
            ).all()
            
            result = []
            current_time = datetime.utcnow()
            
            for user in users_with_access:
                is_expired = (
                    user.sticker_unlimited_until is not None and 
                    current_time >= user.sticker_unlimited_until
                )
                
                result.append({
                    "user_id": user.telegram_id,
                    "username": user.username,
                    "expires_at": user.sticker_unlimited_until.isoformat() if user.sticker_unlimited_until else None,
                    "is_expired": is_expired,
                    "time_remaining": (
                        str(user.sticker_unlimited_until - current_time) 
                        if user.sticker_unlimited_until and not is_expired 
                        else None
                    )
                })
            
            return result
            
        except Exception as e:
            logger.error("Error getting users with sticker access", error=str(e))
            return []