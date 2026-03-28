"""Models package for the application."""

from src.models.parsing_rule import ParsingRule

# Import models from src/models.py to avoid import conflicts
# This allows both "from src.models import BotBalance" and 
# "from src.models.parsing_rule import ParsingRule" to work
import sys
import os

# Get the parent directory (src/)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
models_file = os.path.join(parent_dir, 'models.py')

# Import from models.py if it exists
if os.path.exists(models_file):
    import importlib.util
    spec = importlib.util.spec_from_file_location("_models_file", models_file)
    if spec and spec.loader:
        _models_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_models_module)
        
        # Export the models
        BotBalance = _models_module.BotBalance
        UserBalance = _models_module.UserBalance
        MessageType = _models_module.MessageType
        
        __all__ = ["ParsingRule", "BotBalance", "UserBalance", "MessageType"]
else:
    __all__ = ["ParsingRule"]
