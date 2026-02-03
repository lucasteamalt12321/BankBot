#!/usr/bin/env python3
"""
Test runner for Task 11.3 integration tests
"""

import sys
import os
import subprocess

def run_test_file(test_file):
    """Run a single test file and return success status"""
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True, cwd='.')
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        print(f"{'✅ PASSED' if success else '❌ FAILED'}: {test_file}")
        return success
        
    except Exception as e:
        print(f"❌ ERROR running {test_file}: {e}")
        return False

def main():
    """Run all integration tests for task 11.3"""
    print("🚀 Running Task 11.3 Integration Tests")
    print("Testing: Full cycle integration, message formats, edge cases, bot commands")
    
    test_files = [
        "tests/test_full_cycle_integration.py",
        "tests/test_message_formats_unit.py", 
        "tests/test_edge_cases_unit.py",
        "tests/test_bot_command_integration.py"
    ]
    
    results = []
    for test_file in test_files:
        if os.path.exists(test_file):
            success = run_test_file(test_file)
            results.append((test_file, success))
        else:
            print(f"❌ Test file not found: {test_file}")
            results.append((test_file, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("INTEGRATION TEST SUMMARY")
    print('='*60)
    
    passed = 0
    total = len(results)
    
    for test_file, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_file}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} test files passed")
    
    if passed == total:
        print("🎉 All integration tests PASSED! Task 11.3 is complete.")
        return True
    else:
        print("⚠️ Some integration tests FAILED. Please check the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)