"""
Error handler middleware for the Telegram bot.

This module provides comprehensive error handling for all bot operations,
including logging, user notifications, and admin alerts.

Validates: Requirements 6.1-6.4
"""

import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError

from src.config import settings
from src.logging_config import get_logger

logger = get_logger("error_handler")


class ErrorHandlerMiddleware:
    """
    Middleware for handling errors in Telegram bot operations.
    
    This class provides:
    - Comprehensive error logging with full stack traces
    - User-friendly error messages
    - Admin notifications for critical errors
    - Different handling strategies for different error types
    
    Usage:
        error_handler = ErrorHandlerMiddleware()
        application.add_error_handler(error_handler.handle_error)
    """
    
    def __init__(self, notify_admin: bool = True):
        """
        Initialize the error handler middleware.
        
        Args:
            notify_admin: Whether to send notifications to admin for critical errors
        """
        self.notify_admin = notify_admin
        self.logger = logger
    
    async def handle_error(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle errors that occur during message processing.
        
        This method is called automatically by python-telegram-bot when an error occurs.
        It logs the error, notifies the user, and alerts administrators if necessary.
        
        Args:
            update: The update that caused the error (may be None)
            context: The context object containing error information
        """
        error = context.error
        
        # Log the error with full stack trace
        self.logger.exception(
            f"Error processing update: {error}",
            extra={
                "update": update.to_dict() if update else None,
                "error_type": type(error).__name__
            }
        )
        
        # Determine error severity and user message
        user_message = self._get_user_message(error)
        is_critical = self._is_critical_error(error)
        
        # Send user-friendly message if possible
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(user_message)
            except Exception as e:
                self.logger.error(f"Failed to send error message to user: {e}")
        
        # Notify admin for critical errors
        if is_critical and self.notify_admin:
            await self._notify_admin(update, error, context)
    
    def _get_user_message(self, error: Exception) -> str:
        """
        Get a user-friendly error message based on the error type.
        
        Args:
            error: The exception that occurred
            
        Returns:
            A user-friendly error message
        """
        if isinstance(error, BadRequest):
            return (
                "❌ Не удалось обработать запрос. "
                "Пожалуйста, проверьте правильность команды и попробуйте снова."
            )
        elif isinstance(error, Forbidden):
            return (
                "❌ У бота нет прав для выполнения этого действия. "
                "Пожалуйста, проверьте настройки бота."
            )
        elif isinstance(error, NetworkError):
            return (
                "❌ Проблема с сетевым соединением. "
                "Пожалуйста, попробуйте позже."
            )
        elif isinstance(error, TelegramError):
            return (
                "❌ Произошла ошибка при взаимодействии с Telegram. "
                "Пожалуйста, попробуйте позже."
            )
        else:
            return (
                "❌ Произошла ошибка при обработке команды. "
                "Администраторы уже уведомлены."
            )
    
    def _is_critical_error(self, error: Exception) -> bool:
        """
        Determine if an error is critical and requires admin notification.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error is critical, False otherwise
        """
        # Network errors and Telegram API errors are usually not critical
        if isinstance(error, (NetworkError, BadRequest, Forbidden)):
            return False
        
        # All other errors are considered critical
        return True
    
    async def _notify_admin(
        self,
        update: Optional[Update],
        error: Exception,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Send a notification to the administrator about a critical error.
        
        Args:
            update: The update that caused the error (may be None)
            error: The exception that occurred
            context: The context object
        """
        if not settings.ADMIN_TELEGRAM_ID:
            self.logger.warning("ADMIN_TELEGRAM_ID not configured, skipping admin notification")
            return
        
        try:
            # Build error notification message
            error_message = self._build_admin_message(update, error)
            
            # Send notification to admin
            await context.bot.send_message(
                chat_id=settings.ADMIN_TELEGRAM_ID,
                text=error_message,
                parse_mode='HTML'
            )
            
            self.logger.info(f"Admin notification sent for error: {type(error).__name__}")
            
        except Exception as e:
            self.logger.error(f"Failed to send admin notification: {e}")
    
    def _build_admin_message(self, update: Optional[Update], error: Exception) -> str:
        """
        Build a detailed error message for the administrator.
        
        Args:
            update: The update that caused the error (may be None)
            error: The exception that occurred
            
        Returns:
            A formatted error message for the admin
        """
        message_parts = [
            "⚠️ <b>Critical Error in Bot</b>",
            "",
            f"<b>Error Type:</b> {type(error).__name__}",
            f"<b>Error Message:</b> {str(error)}",
        ]
        
        if update:
            if update.effective_user:
                message_parts.extend([
                    "",
                    "<b>User Information:</b>",
                    f"User ID: {update.effective_user.id}",
                    f"Username: @{update.effective_user.username or 'N/A'}",
                    f"Full Name: {update.effective_user.full_name}",
                ])
            
            if update.effective_message:
                message_text = update.effective_message.text or update.effective_message.caption or "N/A"
                # Truncate long messages
                if len(message_text) > 200:
                    message_text = message_text[:200] + "..."
                
                message_parts.extend([
                    "",
                    "<b>Message:</b>",
                    f"{message_text}",
                ])
            
            if update.effective_chat:
                message_parts.extend([
                    "",
                    "<b>Chat Information:</b>",
                    f"Chat ID: {update.effective_chat.id}",
                    f"Chat Type: {update.effective_chat.type}",
                ])
        
        return "\n".join(message_parts)


def create_error_handler(notify_admin: bool = True) -> ErrorHandlerMiddleware:
    """
    Factory function to create an error handler middleware instance.
    
    Args:
        notify_admin: Whether to send notifications to admin for critical errors
        
    Returns:
        An initialized ErrorHandlerMiddleware instance
    """
    return ErrorHandlerMiddleware(notify_admin=notify_admin)
