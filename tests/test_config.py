"""
Unit tests for energymon.config module.
"""
import unittest
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energymon.config import Config


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / 'test_config.json'
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.config_path.exists():
            self.config_path.unlink()
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config(str(self.config_path))
        self.assertEqual(config.get('dashboard', 'port'), 5000)
        self.assertEqual(config.get('collection', 'interval'), 5.0)
        self.assertFalse(config.get('dashboard', 'debug'))
    
    def test_config_from_file(self):
        """Test loading configuration from file."""
        test_config = {
            'dashboard': {
                'port': 8080,
                'debug': True
            }
        }
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        config = Config(str(self.config_path))
        self.assertEqual(config.get('dashboard', 'port'), 8080)
        self.assertTrue(config.get('dashboard', 'debug'))
    
    def test_config_get_nested(self):
        """Test getting nested configuration values."""
        config = Config(str(self.config_path))
        weights = config.get('energy_model', 'weights')
        self.assertIsInstance(weights, dict)
        self.assertIn('cpu', weights)
        self.assertEqual(weights['cpu'], 0.6)
    
    def test_config_get_default(self):
        """Test getting config with default value."""
        config = Config(str(self.config_path))
        value = config.get('nonexistent', 'key', default='default_value')
        self.assertEqual(value, 'default_value')
    
    def test_config_set(self):
        """Test setting configuration values."""
        config = Config(str(self.config_path))
        config.set('dashboard', 'port', 9000)
        self.assertEqual(config.get('dashboard', 'port'), 9000)
    
    def test_config_save(self):
        """Test saving configuration to file."""
        config = Config(str(self.config_path))
        config.set('dashboard', 'port', 7000)
        config.save()
        
        # Reload and verify
        new_config = Config(str(self.config_path))
        self.assertEqual(new_config.get('dashboard', 'port'), 7000)


if __name__ == '__main__':
    unittest.main()
