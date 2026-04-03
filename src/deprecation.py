"""
Deprecation utilities for marking code as deprecated.
"""
import warnings
from functools import wraps
from typing import Callable, TypeVar, Any

F = TypeVar('F', bound=Callable[..., Any])


def deprecated(reason: str, removal_date: str, alternative: str = None) -> Callable[[F], F]:
    """
    Decorator to mark functions, classes, or methods as deprecated.
    
    Args:
        reason: Explanation of why the code is deprecated
        removal_date: Date when the code will be removed (format: YYYY-MM-DD)
        alternative: Optional suggestion for what to use instead
    
    Example:
        @deprecated(
            reason="Use src.parsers instead",
            removal_date="2025-06-01",
            alternative="src.parsers.ProfileParser"
        )
        def old_function():
            pass
    """
    def decorator(obj: F) -> F:
        # Get the name of the deprecated object
        name = getattr(obj, '__name__', repr(obj))
        
        # Build the warning message
        msg = f"{name} is deprecated: {reason}. Will be removed on {removal_date}"
        if alternative:
            msg += f". Use {alternative} instead"
        
        # For classes
        if isinstance(obj, type):
            original_init = obj.__init__
            
            @wraps(original_init)
            def new_init(self, *args, **kwargs):
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                original_init(self, *args, **kwargs)
            
            obj.__init__ = new_init
            return obj
        
        # For functions and methods
        @wraps(obj)
        def wrapper(*args, **kwargs):
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return obj(*args, **kwargs)
        
        return wrapper
    
    return decorator


def deprecated_module(reason: str, removal_date: str, alternative: str = None):
    """
    Mark an entire module as deprecated by calling this at module level.
    
    Args:
        reason: Explanation of why the module is deprecated
        removal_date: Date when the module will be removed (format: YYYY-MM-DD)
        alternative: Optional suggestion for what to use instead
    
    Example:
        # At the top of a module file
        from src.deprecation import deprecated_module
        deprecated_module(
            reason="Use src.parsers instead",
            removal_date="2025-06-01",
            alternative="src.parsers"
        )
    """
    import inspect
    
    # Get the calling module's name
    frame = inspect.currentframe().f_back
    module_name = frame.f_globals.get('__name__', 'unknown')
    
    # Build the warning message
    msg = f"Module {module_name} is deprecated: {reason}. Will be removed on {removal_date}"
    if alternative:
        msg += f". Use {alternative} instead"
    
    warnings.warn(msg, DeprecationWarning, stacklevel=2)
