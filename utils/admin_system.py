"""
DEPRECATED: This module has been moved to utils.admin.admin_system

This compatibility shim will be removed in a future version.
Please update your imports to:
    from utils.admin.admin_system import ...
"""

import warnings

warnings.warn(
    "Importing from utils.admin_system is deprecated. "
    "Use utils.admin.admin_system instead. "
    "This compatibility layer will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from the new location for backward compatibility
from utils.admin.admin_system import *  # noqa: F401, F403
