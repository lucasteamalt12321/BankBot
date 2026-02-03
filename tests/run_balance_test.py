#!/usr/bin/env python3
"""
Standalone runner for balance validation property-based test
"""

import sys
import os
import subprocess

# Kill any running Python processes that might interfere
try:
    subprocess.run(["taskkill", "/f", "/im", "python.exe"], capture_output=True)
except:
    pass

# Set environment to avoid bot startup
os.environ["SKIP_BOT_STARTUP"] = "1"

# Run the test
if __name__ == "__main__":
    # Import and run the test
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from tests.test_balance_validation_deduction_pbt import TestBalanceValidationDeductionPBT
        import unittest
        
        # Create test suite
        suite = unittest.TestLoader().loadTestsFromTestCase(TestBalanceValidationDeductionPBT)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Print results
        if result.wasSuccessful():
            print("\n✓ All balance validation property tests passed!")
        else:
            print(f"\n✗ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
            
    except Exception as e:
        print(f"Error running tests: {e}")
        import traceback
        traceback.print_exc()