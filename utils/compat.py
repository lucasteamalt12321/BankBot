"""
Compatibility layer for deprecated imports.

This module provides backward compatibility for code that imports from old locations.
All import paths have been reorganized for better structure.

Deprecated import paths:
- utils.config -> use src.config instead
- utils.core.config -> use src.config instead
- utils.admin_system -> use utils.admin.admin_system instead
- utils.simple_db -> use utils.database.simple_db instead

These imports will trigger DeprecationWarning when used.
"""

import warnings


def _warn_deprecated_config_import(old_path: str):
    """Issue a deprecation warning for old config imports."""
    warnings.warn(
        f"Importing from {old_path} is deprecated. "
        f"Use 'from src.config import settings' instead. "
        f"Old config files will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3
    )


# Re-export admin_system with deprecation warning
def _warn_admin_system_import():
    """Issue a deprecation warning for admin_system imports."""
    warnings.warn(
        "Importing from utils.admin_system is deprecated. "
        "Use 'from utils.admin.admin_system import AdminSystem' instead. "
        "This compatibility layer will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3
    )


# Re-export simple_db with deprecation warning
def _warn_simple_db_import():
    """Issue a deprecation warning for simple_db imports."""
    warnings.warn(
        "Importing from utils.simple_db is deprecated. "
        "Use 'from utils.database.simple_db import ...' instead. "
        "Note: simple_db module itself is deprecated. Consider using utils.admin.admin_system.AdminSystem. "
        "This compatibility layer will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3
    )


# Lazy imports to avoid circular dependencies and only warn when actually used
def __getattr__(name):
    """
    Lazy attribute access for backward compatibility.
    This allows old imports to work while issuing deprecation warnings.
    """
    # Handle admin_system imports
    if name == 'AdminSystem':
        _warn_admin_system_import()
        from utils.admin.admin_system import AdminSystem
        return AdminSystem
    elif name == 'admin_required':
        _warn_admin_system_import()
        from utils.admin.admin_system import admin_required
        return admin_required
    elif name == 'PermissionError':
        _warn_admin_system_import()
        from utils.admin.admin_system import PermissionError
        return PermissionError
    elif name == 'UserNotFoundError':
        _warn_admin_system_import()
        from utils.admin.admin_system import UserNotFoundError
        return UserNotFoundError
    elif name == 'InsufficientBalanceError':
        _warn_admin_system_import()
        from utils.admin.admin_system import InsufficientBalanceError
        return InsufficientBalanceError
    
    # Handle simple_db imports
    elif name == 'get_db_connection':
        _warn_simple_db_import()
        from utils.database.simple_db import get_db_connection
        return get_db_connection
    elif name == 'get_user_by_id':
        _warn_simple_db_import()
        from utils.database.simple_db import get_user_by_id
        return get_user_by_id
    elif name == 'get_user_by_username':
        _warn_simple_db_import()
        from utils.database.simple_db import get_user_by_username
        return get_user_by_username
    elif name == 'update_user_balance':
        _warn_simple_db_import()
        from utils.database.simple_db import update_user_balance
        return update_user_balance
    elif name == 'get_internal_user_id':
        _warn_simple_db_import()
        from utils.database.simple_db import get_internal_user_id
        return get_internal_user_id
    elif name == 'add_transaction':
        _warn_simple_db_import()
        from utils.database.simple_db import add_transaction
        return add_transaction
    elif name == 'get_users_count':
        _warn_simple_db_import()
        from utils.database.simple_db import get_users_count
        return get_users_count
    elif name == 'DB_PATH':
        _warn_simple_db_import()
        from utils.database.simple_db import DB_PATH
        return DB_PATH
    
    # Handle legacy standalone function imports that should use AdminSystem
    elif name == 'register_user':
        _warn_simple_db_import()
        # Provide a wrapper function for backward compatibility
        def register_user(user_id: int, username: str = None, first_name: str = None) -> bool:
            """Wrapper for AdminSystem.register_user for backward compatibility"""
            from utils.admin.admin_system import AdminSystem
            admin_system = AdminSystem()
            return admin_system.register_user(user_id, username, first_name)
        return register_user
    
    elif name == 'init_database':
        _warn_simple_db_import()
        # Provide a no-op function since database is initialized by database.connection
        def init_database():
            """No-op function for backward compatibility. Database is auto-initialized."""
            from database.connection import get_connection
            # Just ensure connection works
            conn = get_connection()
            conn.close()
            return True
        return init_database
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
