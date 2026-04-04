"""Rate limiting middleware for command protection."""

import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
import structlog

logger = structlog.get_logger()


class RateLimitMiddleware:
    """Middleware for rate limiting user commands."""

    def __init__(self, max_commands: int = 10, window_seconds: int = 60):
        """
        Args:
            max_commands: Maximum commands per window
            window_seconds: Time window in seconds
        """
        self.max_commands = max_commands
        self.window_seconds = window_seconds
        self._user_commands = defaultdict(list)

    async def __call__(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Check if user is within rate limit.

        Returns:
            True if allowed, False if rate limited
        """
        if not update.effective_user:
            return True

        user_id = update.effective_user.id
        now = time.time()

        # Clean old entries
        self._user_commands[user_id] = [
            t for t in self._user_commands[user_id] if now - t < self.window_seconds
        ]

        # Check rate limit
        if len(self._user_commands[user_id]) >= self.max_commands:
            await update.message.reply_text(
                "⏳ Слишком много команд. Попробуйте позже."
            )
            logger.warning("Rate limit exceeded", user_id=user_id)
            return False

        # Record command
        self._user_commands[user_id].append(now)
        return True


rate_limit_middleware = RateLimitMiddleware()
