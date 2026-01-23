"""
Unit tests for energymon.alerts module.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energymon.alerts import AlertRule, AlertManager


class TestAlerts(unittest.TestCase):
    """Test alerting system."""
    
    def test_alert_rule_trigger(self):
        """Test alert rule triggering."""
        rule = AlertRule(
            name='test_rule',
            condition=lambda procs: len(procs) > 0,
            severity='warning',
            message_template='Test alert: {total_processes} processes'
        )
        
        processes = [{'pid': 1, 'name': 'test', 'energy_score': 50}]
        alert = rule.check(processes)
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert['rule'], 'test_rule')
        self.assertEqual(alert['severity'], 'warning')
    
    def test_alert_rule_no_trigger(self):
        """Test alert rule not triggering."""
        rule = AlertRule(
            name='test_rule',
            condition=lambda procs: len(procs) > 10,
            severity='warning'
        )
        
        processes = [{'pid': 1, 'name': 'test'}]
        alert = rule.check(processes)
        
        self.assertIsNone(alert)
    
    def test_alert_manager(self):
        """Test alert manager."""
        manager = AlertManager()
        
        # Test with high energy process
        processes = [
            {
                'pid': 1,
                'name': 'high_energy',
                'energy_score': 600,  # Above threshold
                'cpu_percent': 50,
                'memory_mb': 100
            }
        ]
        
        alerts = manager.check_alerts(processes)
        # Should trigger high_energy_process rule
        self.assertGreater(len(alerts), 0)
    
    def test_alert_history(self):
        """Test alert history."""
        manager = AlertManager()
        processes = [{'pid': 1, 'name': 'test', 'energy_score': 600}]
        
        manager.check_alerts(processes)
        history = manager.get_recent_alerts(limit=10)
        
        self.assertGreater(len(history), 0)


if __name__ == '__main__':
    unittest.main()
