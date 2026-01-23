#!/usr/bin/env python3
"""
Test runner for Hybrid Energy Profiler.

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py test_model   # Run specific test module
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def run_tests(test_module=None):
    """Run tests."""
    if test_module:
        # Run specific test module
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(f'tests.test_{test_module}')
    else:
        # Run all tests
        loader = unittest.TestLoader()
        start_dir = os.path.dirname(__file__)
        suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    test_module = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_tests(test_module))
