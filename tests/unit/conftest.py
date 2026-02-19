"""
Pytest configuration for unit tests.
Sets up environment variables before any imports happen.
"""

import os
import pytest

# Set required environment variables before any imports
os.environ.setdefault('BOT_TOKEN', 'test_token_12345')
os.environ.setdefault('ADMIN_TELEGRAM_ID', '123456789')
os.environ.setdefault('DATABASE_URL', 'sqlite:///test.db')
os.environ.setdefault('ENV', 'test')
