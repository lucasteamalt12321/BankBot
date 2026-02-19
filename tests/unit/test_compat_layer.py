"""
Unit tests for the compatibility layer (utils/compat.py)

This test verifies that deprecated imports still work with proper warnings.
"""
import unittest
import warnings
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestCompatibilityLayer(unittest.TestCase):
    """Test the compatibility layer for deprecated imports"""
    
    def test_admin_system_import_with_warning(self):
        """Test that importing AdminSystem from utils.compat triggers deprecation warning"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import from compatibility layer
            from utils.compat import AdminSystem
            
            # Verify at least one warning was issued
            self.assertGreaterEqual(len(w), 1)
            # Check that at least one is a DeprecationWarning about admin_system
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            self.assertGreater(len(deprecation_warnings), 0)
            self.assertIn("admin_system is deprecated", str(deprecation_warnings[0].message))
            
            # Verify the class is actually usable
            self.assertIsNotNone(AdminSystem)
    
    def test_simple_db_functions_import_with_warning(self):
        """Test that importing simple_db functions triggers deprecation warning"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import from compatibility layer
            from utils.compat import get_user_by_id, get_db_connection
            
            # Verify warnings were issued (one per import)
            self.assertGreaterEqual(len(w), 2)
            for warning in w:
                self.assertTrue(issubclass(warning.category, DeprecationWarning))
                self.assertIn("simple_db is deprecated", str(warning.message))
            
            # Verify the functions are actually usable
            self.assertIsNotNone(get_user_by_id)
            self.assertIsNotNone(get_db_connection)
    
    def test_register_user_wrapper(self):
        """Test that register_user wrapper function is available"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import from compatibility layer
            from utils.compat import register_user
            
            # Verify warning was issued
            self.assertGreaterEqual(len(w), 1)
            
            # Verify the function is callable
            self.assertTrue(callable(register_user))
    
    def test_init_database_wrapper(self):
        """Test that init_database wrapper function is available"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import from compatibility layer
            from utils.compat import init_database
            
            # Verify warning was issued
            self.assertGreaterEqual(len(w), 1)
            
            # Verify the function is callable
            self.assertTrue(callable(init_database))
    
    def test_exception_classes_import(self):
        """Test that exception classes can be imported from compat layer"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Import exception classes
            from utils.compat import (
                PermissionError,
                UserNotFoundError,
                InsufficientBalanceError
            )
            
            # Verify warnings were issued
            self.assertGreaterEqual(len(w), 3)
            
            # Verify the classes are actually exception classes
            self.assertTrue(issubclass(PermissionError, Exception))
            self.assertTrue(issubclass(UserNotFoundError, Exception))
            self.assertTrue(issubclass(InsufficientBalanceError, Exception))
    
    def test_invalid_import_raises_error(self):
        """Test that importing non-existent attributes raises ImportError"""
        with self.assertRaises(ImportError):
            from utils.compat import NonExistentFunction


if __name__ == '__main__':
    unittest.main()
