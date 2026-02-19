"""
DEPRECATED: This module has been moved to utils.database.simple_db

This compatibility shim will be removed in a future version.
Please update your imports to:
    from utils.database.simple_db import ...
"""

import warnings

warnings.warn(
    "Importing from utils.simple_db is deprecated. "
    "Use utils.database.simple_db instead. "
    "This compatibility layer will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from the new location for backward compatibility
from utils.database.simple_db import *  # noqa: F401, F403
