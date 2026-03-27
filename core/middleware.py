"""Centralized error handling middleware."""

import structlog
from typing import Callable, Any
from functools import wraps

logger = structlog.get_logger()

def handle_errors(func: Callable) -> Callable:
    """
    Decorator for centralized error handling.
    
    Catches exceptions and logs them with appropriate context.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(
                "Error in middleware",
                function=func.__name__,
                error=str(e),
                args=args,
                kwargs=kwargs
            )
            raise
    return wrapper

class ErrorHandlerMiddleware:
    """Middleware class for error handling in handlers."""
    
    def __init__(self, handler_func: Callable):
        self.handler_func = handler_func
    
    async def __call__(self, *args, **kwargs):
        try:
            return await self.handler_func(*args, **kwargs)
        except Exception as e:
            logger.error(
                "Handler error",
                handler=self.handler_func.__name__,
                error=str(e),
                args=args,
                kwargs=kwargs
            )
            # Re-raise to allow upstream handling
            raise