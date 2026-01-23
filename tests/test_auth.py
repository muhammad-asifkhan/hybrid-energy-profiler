"""
Unit tests for energymon.auth module.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energymon.auth import hash_password, verify_password, authenticate, init_users


class TestAuth(unittest.TestCase):
    """Test authentication functions."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = 'test_password'
        hashed = hash_password(password)
        self.assertIsInstance(hashed, str)
        self.assertIn(':', hashed)  # Should contain salt:hash
    
    def test_verify_password(self):
        """Test password verification."""
        password = 'test_password'
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password('wrong_password', hashed))
    
    def test_authenticate_default_user(self):
        """Test authentication with default users."""
        init_users()
        # Test with default admin user
        self.assertTrue(authenticate('admin', 'admin123'))
        self.assertFalse(authenticate('admin', 'wrong_password'))
        self.assertFalse(authenticate('nonexistent', 'password'))


if __name__ == '__main__':
    unittest.main()
