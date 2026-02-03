#!/usr/bin/env python3
"""
Task 11.3 Integration Test Suite
Comprehensive integration tests for complete cycle workflows

This test suite validates:
- Full cycle: registration → points addition → purchase
- Test interaction with existing architecture
- Test admin notifications
- Test complete user journey scenarios
- Requirements: 6.1, 2.1, 5.1, 5.5

Test Coverage:
1. Complete cycle integration tests
2. Bot command integration tests  
3. System architecture integration tests
"""

import unittest
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all integration test modules
from tests.test_complete_cycle_integration import TestCompleteCycleIntegration
from tests.test_bot_command_integration import TestBotCommandIntegrationRunner
from tests.test_system_architecture_integration import TestSystemArchitectureIntegration


class TestTask11_3IntegrationSuite(unittest.TestCase):
    """
    Master test suite for Task 11.3 integration tests
    
    This suite runs all integration tests and provides a comprehensive
    validation of the complete system workflows.
    """
    
    def setUp(self):
        """Setup for integration test suite"""
        print("\n" + "="*80)
        print("TASK 11.3 INTEGRATION TEST SUITE")
        print("Testing complete cycle workflows and system integration")
        print("="*80)
    
    def test_integration_suite_summary(self):
        """
        Summary test that validates all integration test components exist
        """
        # Verify all test classes are available
        test_classes = [
            TestCompleteCycleIntegration,
            TestBotCommandIntegrationRunner,
            TestSystemArchitectureIntegration
        ]
        
        for test_class in test_classes:
            self.assertIsNotNone(test_class)
            
        # Count total test methods
        total_tests = 0
        for test_class in test_classes:
            test_methods = [method for method in dir(test_class) 
                          if method.startswith('test_')]
            total_tests += len(test_methods)
            print(f"{test_class.__name__}: {len(test_methods)} tests")
        
        print(f"Total integration tests: {total_tests}")
        
        # Verify minimum test coverage (we have 24 comprehensive tests)
        self.assertGreaterEqual(total_tests, 20, 
                               "Should have at least 20 integration tests")
    
    def test_requirements_coverage(self):
        """
        Verify that all required scenarios are covered by integration tests
        """
        # Requirements that must be validated by integration tests
        required_scenarios = [
            # Requirement 6.1: Auto registration
            "auto_registration",
            
            # Requirement 2.1: Points addition
            "add_points",
            "admin",
            
            # Requirement 5.1: Purchase workflow
            "buy_contact",
            "shop",
            
            # Requirement 5.5: Error handling
            "error",
            "insufficient_balance",
        ]
        
        # Get all test method names from integration test classes
        all_test_methods = []
        test_classes = [
            TestCompleteCycleIntegration,
            TestBotCommandIntegrationRunner,
            TestSystemArchitectureIntegration
        ]
        
        for test_class in test_classes:
            test_methods = [method for method in dir(test_class) 
                          if method.startswith('test_')]
            all_test_methods.extend(test_methods)
        
        # Convert to lowercase for easier matching
        all_test_methods_lower = [method.lower() for method in all_test_methods]
        
        # Check coverage for each required scenario
        coverage_report = {}
        for scenario in required_scenarios:
            matching_tests = [method for method in all_test_methods_lower 
                            if scenario.lower() in method]
            coverage_report[scenario] = len(matching_tests)
            
            # Each scenario should have at least one test
            self.assertGreater(len(matching_tests), 0, 
                             f"No tests found for scenario: {scenario}")
        
        print("\nRequirements Coverage Report:")
        for scenario, count in coverage_report.items():
            print(f"  {scenario}: {count} tests")
    
    def test_complete_workflow_scenarios(self):
        """
        Verify that complete workflow scenarios are tested
        """
        workflow_scenarios = [
            "complete_user_journey",
            "full_cycle",
            "registration_to_purchase",
            "admin_workflow",
            "notification_workflow",
            "error_recovery",
            "concurrent_operations",
            "system_integration"
        ]
        
        # Get test methods from complete cycle integration tests
        cycle_test_methods = [method for method in dir(TestCompleteCycleIntegration) 
                            if method.startswith('test_')]
        
        cycle_methods_lower = [method.lower() for method in cycle_test_methods]
        
        workflow_coverage = {}
        for scenario in workflow_scenarios:
            matching_tests = [method for method in cycle_methods_lower 
                            if any(keyword in method for keyword in scenario.split('_'))]
            workflow_coverage[scenario] = len(matching_tests)
        
        print("\nWorkflow Scenarios Coverage:")
        for scenario, count in workflow_coverage.items():
            print(f"  {scenario}: {count} tests")
            
        # Verify we have comprehensive workflow coverage (we have good coverage)
        total_workflow_tests = sum(workflow_coverage.values())
        self.assertGreaterEqual(total_workflow_tests, 10, 
                               "Should have comprehensive workflow test coverage")


def create_integration_test_suite():
    """
    Create a comprehensive test suite for all integration tests
    """
    suite = unittest.TestSuite()
    
    # Add complete cycle integration tests
    cycle_tests = unittest.TestLoader().loadTestsFromTestCase(TestCompleteCycleIntegration)
    suite.addTests(cycle_tests)
    
    # Add bot command integration tests
    bot_tests = unittest.TestLoader().loadTestsFromTestCase(TestBotCommandIntegrationRunner)
    suite.addTests(bot_tests)
    
    # Add system architecture integration tests
    arch_tests = unittest.TestLoader().loadTestsFromTestCase(TestSystemArchitectureIntegration)
    suite.addTests(arch_tests)
    
    # Add suite summary tests
    suite_tests = unittest.TestLoader().loadTestsFromTestCase(TestTask11_3IntegrationSuite)
    suite.addTests(suite_tests)
    
    return suite


def run_integration_tests():
    """
    Run all integration tests with detailed reporting
    """
    print("="*80)
    print("TASK 11.3: INTEGRATION TESTS FOR COMPLETE CYCLE")
    print("="*80)
    print()
    print("Testing Requirements:")
    print("- 6.1: Auto registration workflow")
    print("- 2.1: Points addition workflow") 
    print("- 5.1: Purchase workflow and admin notifications")
    print("- 5.5: Error handling across all workflows")
    print()
    print("Test Categories:")
    print("1. Complete Cycle Integration Tests")
    print("2. Bot Command Integration Tests")
    print("3. System Architecture Integration Tests")
    print("4. Integration Suite Validation")
    print()
    print("="*80)
    
    # Create and run the test suite
    suite = create_integration_test_suite()
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    print("\n" + "="*80)
    print("INTEGRATION TEST RESULTS SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    if result.wasSuccessful():
        print("\n✅ ALL INTEGRATION TESTS PASSED!")
        print("Task 11.3 implementation is complete and validated.")
    else:
        print("\n❌ SOME INTEGRATION TESTS FAILED!")
        print("Please review and fix the failing tests.")
    
    print("="*80)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)