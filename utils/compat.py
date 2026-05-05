"""Compatibility layer for deprecated imports.

This module provides backward compatibility for code that imports from old locations.
All import paths have been reorganized for better structure.

Deprecated import paths:
- utils.config -> use src.config instead
- utils.admin_system -> use utils.admin.admin_system instead
- utils.simple_db -> use utils.database.simple_db instead

These imports will trigger DeprecationWarning when used.
"""

import warnings


def _warn_deprecated_config_import(old_path: str) -> None:
    """Issue a deprecation warning for old config imports."""
    warnings.warn(
        f"Importing from {old_path} is deprecated. "
        f"Use 'from src.config import settings' instead. "
        f"Old config files will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3,
    )


def _warn_admin_system_import() -> None:
    """Issue a deprecation warning for admin_system imports."""
    warnings.warn(
        "Importing from utils.admin_system is deprecated. "
        "Use 'from utils.admin.admin_system import AdminSystem' instead. "
        "This compatibility layer will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3,
    )


def _warn_simple_db_import() -> None:
    """Issue a deprecation warning for simple_db imports."""
    warnings.warn(
        "Importing from utils.simple_db is deprecated. "
        "Use 'from utils.database.simple_db import ...' instead. "
        "Note: simple_db module itself is deprecated. "
        "Consider using utils.admin.admin_system.AdminSystem. "
        "This compatibility layer will be removed in version 2.0.0 (April 2026).",
        DeprecationWarning,
        stacklevel=3,
    )


def __getattr__(name: str):
    """Lazy attribute access for backward compatibility.

    Allows old imports to work while issuing deprecation warnings.
    """
    # admin_system exports
    if name == "AdminSystem":
        _warn_admin_system_import()
        from utils.admin.admin_system import AdminSystem
        return AdminSystem
    if name == "admin_required":
        _warn_admin_system_import()
        from utils.admin.admin_system import admin_required
        return admin_required
    if name == "PermissionError":
        _warn_admin_system_import()
        from utils.admin.admin_system import PermissionError  # noqa: A001
        return PermissionError
    if name == "UserNotFoundError":
        _warn_admin_system_import()
        from utils.admin.admin_system import UserNotFoundError
        return UserNotFoundError
    if name == "InsufficientBalanceError":
        _warn_admin_system_import()
        from utils.admin.admin_system import InsufficientBalanceError
        return InsufficientBalanceError

    # simple_db exports
    if name == "get_db_connection":
        _warn_simple_db_import()
        from utils.database.simple_db import get_db_connection
        return get_db_connection
    if name == "get_user_by_id":
        _warn_simple_db_import()
        from utils.database.simple_db import get_user_by_id
        return get_user_by_id
    if name == "get_user_by_username":
        _warn_simple_db_import()
        from utils.database.simple_db import get_user_by_username
        return get_user_by_username
    if name == "update_user_balance":
        _warn_simple_db_import()
        from utils.database.simple_db import update_user_balance
        return update_user_balance
    if name == "get_internal_user_id":
        _warn_simple_db_import()
        from utils.database.simple_db import get_internal_user_id
        return get_internal_user_id
    if name == "add_transaction":
        _warn_simple_db_import()
        from utils.database.simple_db import add_transaction
        return add_transaction
    if name == "get_users_count":
        _warn_simple_db_import()
        from utils.database.simple_db import get_users_count
        return get_users_count
    if name == "DB_PATH":
        _warn_simple_db_import()
        from utils.database.simple_db import DB_PATH
        return DB_PATH

    # Legacy standalone functions
    if name == "register_user":
        _warn_simple_db_import()

        def register_user(user_id: int, username: str = None, first_name: str = None) -> bool:
            """Wrapper for AdminSystem.register_user for backward compatibility."""
            from utils.admin.admin_system import AdminSystem
            admin_system = AdminSystem()
            return admin_system.register_user(user_id, username, first_name)

        return register_user

    if name == "init_database":
        _warn_simple_db_import()

        def init_database() -> bool:
            """No-op for backward compatibility. Database is auto-initialized."""
            from database.connection import get_connection
            conn = get_connection()
            conn.close()
            return True

        return init_database

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
