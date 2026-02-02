# admin_middleware.py - Admin system middleware and decorators
import functools
import logging
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes
from utils.simple_db import register_user, get_user_by_id, is_admin, init_database

logger = logging.getLogger(__name__)

def ensure_user_registered(func: Callable) -> Callable:
    """Decorator to ensure user is registered before processing any command/message"""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        
        # Skip if user is a bot
        if user.is_bot:
            return await func(self, update, context, *args, **kwargs)
        
        # Check if user exists in admin system
        existing_user = get_user_by_id(user.id)
        
        if not existing_user:
            # Register new user transparently
            username = user.username
            first_name = user.first_name
            
            success = register_user(user.id, username, first_name)
            if success:
                logger.info(f"Auto-registered user {user.id} (@{username}, {first_name})")
            else:
                logger.error(f"Failed to auto-register user {user.id}")
        
        # Continue with original function
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper

def admin_required(func: Callable) -> Callable:
    """Decorator to require admin privileges for command execution"""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        
        # Check admin status
        if not is_admin(user.id):
            await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
            return
        
        # Continue with original function
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper

class AutoRegistrationMiddleware:
    """Middleware class for automatic user registration"""
    
    def __init__(self):
        # Initialize database on middleware creation
        try:
            init_database()
        except Exception as e:
            logger.error(f"Failed to initialize admin database: {e}")
    
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process any message/command for automatic user registration"""
        user = update.effective_user
        
        # Skip if user is a bot
        if user.is_bot:
            return
        
        # Check if user exists in admin system
        existing_user = get_user_by_id(user.id)
        
        if not existing_user:
            # Register new user transparently
            username = user.username
            first_name = user.first_name
            
            success = register_user(user.id, username, first_name)
            if success:
                logger.info(f"Auto-registered user {user.id} (@{username}, {first_name})")
            else:
                logger.error(f"Failed to auto-register user {user.id}")

# Global middleware instance
auto_registration_middleware = AutoRegistrationMiddleware()