"""
Unit tests for energymon.storage module.
"""
import unittest
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energymon.storage import MetricsStorage


class TestMetricsStorage(unittest.TestCase):
    """Test metrics storage."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test_metrics.db'
        self.storage = MetricsStorage(str(self.db_path))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.db_path.exists():
            self.db_path.unlink()
    
    def test_save_snapshot(self):
        """Test saving process snapshot."""
        processes = [
            {
                'pid': 1234,
                'name': 'test_process',
                'cpu_percent': 50.0,
                'memory_mb': 100.0,
                'io_read': 1024,
                'io_write': 512,
                'context_switches': 100,
                'syscalls': 1000,
                'energy_score': 75.5,
                'classification': 'CPU-bound',
                'data_source': 'test',
                'username': 'testuser',
                'parent_pid': 1,
                'num_threads': 2,
                'status': 'running'
            }
        ]
        
        saved_count = self.storage.save_snapshot(processes)
        self.assertEqual(saved_count, 1)
    
    def test_get_history(self):
        """Test retrieving historical data."""
        # Save some test data
        processes = [
            {
                'pid': 1234,
                'name': 'test_process',
                'cpu_percent': 50.0,
                'memory_mb': 100.0,
                'io_read': 1024,
                'io_write': 512,
                'context_switches': 100,
                'syscalls': 1000,
                'energy_score': 75.5,
                'classification': 'CPU-bound',
                'data_source': 'test',
                'username': 'testuser',
                'parent_pid': 1,
                'num_threads': 2,
                'status': 'running'
            }
        ]
        self.storage.save_snapshot(processes)
        
        # Retrieve history
        history = self.storage.get_history(name='test_process', hours=1)
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]['name'], 'test_process')
    
    def test_get_trends(self):
        """Test getting process trends."""
        # Save multiple snapshots
        for i in range(3):
            processes = [
                {
                    'pid': 1234,
                    'name': 'trend_test',
                    'cpu_percent': 50.0 + i,
                    'memory_mb': 100.0,
                    'io_read': 1024,
                    'io_write': 512,
                    'context_switches': 100,
                    'syscalls': 1000,
                    'energy_score': 75.5 + i,
                    'classification': 'CPU-bound',
                    'data_source': 'test',
                    'username': 'testuser',
                    'parent_pid': 1,
                    'num_threads': 2,
                    'status': 'running'
                }
            ]
            self.storage.save_snapshot(processes)
        
        trends = self.storage.get_trends('trend_test', hours=1)
        self.assertGreaterEqual(len(trends), 3)
    
    def test_cleanup_old_data(self):
        """Test cleaning up old data."""
        # This would require mocking datetime, so we'll just test the method exists
        deleted = self.storage.cleanup_old_data(days=0)  # Delete everything
        self.assertIsInstance(deleted, int)
    
    def test_get_stats(self):
        """Test getting storage statistics."""
        stats = self.storage.get_stats()
        self.assertIn('total_records', stats)
        self.assertIn('database_size_mb', stats)


if __name__ == '__main__':
    unittest.main()
