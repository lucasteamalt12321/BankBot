"""
Pytest configuration for test suite.
Sets up test environment before any imports.
"""
import os
import sys

# Set test environment BEFORE any imports
os.environ["ENV"] = "test"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
