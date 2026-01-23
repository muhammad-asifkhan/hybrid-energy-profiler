"""
Unit tests for energymon.model module.
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energymon.model import compute_energy_score, classify_process


class TestEnergyModel(unittest.TestCase):
    """Test energy score computation."""
    
    def test_compute_energy_score_cpu_bound(self):
        """Test energy score for CPU-bound process."""
        metric = {
            'cpu_percent': 80.0,
            'memory_mb': 50.0,
            'io_read': 0,
            'io_write': 0,
            'context_switches': 100,
            'syscalls': 1000
        }
        score = compute_energy_score(metric)
        self.assertGreater(score, 0)
        self.assertGreater(score, 40)  # CPU should dominate
    
    def test_compute_energy_score_io_bound(self):
        """Test energy score for I/O-bound process."""
        metric = {
            'cpu_percent': 10.0,
            'memory_mb': 100.0,
            'io_read': 100 * 1024 * 1024,  # 100MB
            'io_write': 50 * 1024 * 1024,  # 50MB
            'context_switches': 200,
            'syscalls': 2000
        }
        score = compute_energy_score(metric)
        self.assertGreater(score, 0)
    
    def test_compute_energy_score_memory_bound(self):
        """Test energy score for memory-bound process."""
        metric = {
            'cpu_percent': 15.0,
            'memory_mb': 2048.0,  # 2GB
            'io_read': 10 * 1024 * 1024,
            'io_write': 5 * 1024 * 1024,
            'context_switches': 150,
            'syscalls': 1500
        }
        score = compute_energy_score(metric)
        self.assertGreater(score, 0)
    
    def test_compute_energy_score_adaptive(self):
        """Test adaptive weight adjustment."""
        metric = {
            'cpu_percent': 90.0,
            'memory_mb': 10.0,
            'io_read': 0,
            'io_write': 0,
            'context_switches': 50,
            'syscalls': 500
        }
        score_adaptive = compute_energy_score(metric, adaptive=True)
        score_fixed = compute_energy_score(metric, adaptive=False)
        # Adaptive should give higher weight to CPU for CPU-bound processes
        self.assertGreaterEqual(score_adaptive, score_fixed * 0.9)  # Allow some variance
    
    def test_compute_energy_score_empty(self):
        """Test energy score with empty/zero metrics."""
        metric = {
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'io_read': 0,
            'io_write': 0,
            'context_switches': 0,
            'syscalls': 0
        }
        score = compute_energy_score(metric)
        self.assertEqual(score, 0.0)


class TestProcessClassification(unittest.TestCase):
    """Test process classification."""
    
    def test_classify_cpu_bound(self):
        """Test classification of CPU-bound process."""
        metric = {
            'cpu_percent': 90.0,
            'memory_mb': 10.0,
            'io_read': 0,
            'io_write': 0,
            'context_switches': 50
        }
        classification = classify_process(metric)
        self.assertEqual(classification, 'CPU-bound')
    
    def test_classify_io_bound(self):
        """Test classification of I/O-bound process."""
        metric = {
            'cpu_percent': 5.0,
            'memory_mb': 50.0,
            'io_read': 200 * 1024 * 1024,  # 200MB
            'io_write': 150 * 1024 * 1024,  # 150MB
            'context_switches': 100
        }
        classification = classify_process(metric)
        self.assertEqual(classification, 'IO-bound')
    
    def test_classify_memory_bound(self):
        """Test classification of memory-bound process."""
        metric = {
            'cpu_percent': 10.0,
            'memory_mb': 3072.0,  # 3GB
            'io_read': 10 * 1024 * 1024,
            'io_write': 5 * 1024 * 1024,
            'context_switches': 100
        }
        classification = classify_process(metric)
        self.assertEqual(classification, 'Memory-bound')
    
    def test_classify_context_heavy(self):
        """Test classification of context-heavy process."""
        metric = {
            'cpu_percent': 20.0,
            'memory_mb': 100.0,
            'io_read': 10 * 1024 * 1024,
            'io_write': 5 * 1024 * 1024,
            'context_switches': 10000  # Very high
        }
        classification = classify_process(metric)
        self.assertEqual(classification, 'Context-heavy')
    
    def test_classify_balanced(self):
        """Test classification of balanced process."""
        metric = {
            'cpu_percent': 30.0,
            'memory_mb': 512.0,
            'io_read': 50 * 1024 * 1024,
            'io_write': 50 * 1024 * 1024,
            'context_switches': 500
        }
        classification = classify_process(metric)
        # Should be balanced or one of the mixed types
        self.assertIn(classification, ['Balanced', 'CPU-IO-Mixed', 'Resource-Heavy'])
    
    def test_classify_idle(self):
        """Test classification of idle process."""
        metric = {
            'cpu_percent': 0.1,
            'memory_mb': 5.0,
            'io_read': 0,
            'io_write': 0,
            'context_switches': 10
        }
        classification = classify_process(metric)
        self.assertEqual(classification, 'Idle')


if __name__ == '__main__':
    unittest.main()
