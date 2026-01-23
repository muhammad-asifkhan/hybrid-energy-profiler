"""
alerts.py: Alerting system for Hybrid Energy Profiler.

Provides:
- Configurable alert rules
- Real-time anomaly detection
- Alert history
- Notification system (future: email, webhooks)
"""
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from energymon.config import get_config
from energymon.logger import get_logger

config = get_config()
logger = get_logger('energymon.alerts')


class AlertRule:
    """Represents a single alert rule."""
    
    def __init__(self, name: str, condition: Callable, severity: str = 'warning',
                 message_template: Optional[str] = None, action: Optional[Callable] = None):
        """
        Initialize alert rule.
        
        Args:
            name: Rule name
            condition: Function that takes processes list and returns True if alert should trigger
            severity: Alert severity ('info', 'warning', 'critical')
            message_template: Template for alert message (can use {variables})
            action: Optional function to call when alert triggers
        """
        self.name = name
        self.condition = condition
        self.severity = severity
        self.message_template = message_template or f"Alert: {name}"
        self.action = action
        self.trigger_count = 0
        self.last_triggered = None
    
    def check(self, processes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Check if rule should trigger.
        
        Args:
            processes: List of process dictionaries
        
        Returns:
            Alert dict if triggered, None otherwise
        """
        try:
            if self.condition(processes):
                self.trigger_count += 1
                self.last_triggered = datetime.now()
                
                # Generate message
                message = self._generate_message(processes)
                
                alert = {
                    'rule': self.name,
                    'severity': self.severity,
                    'message': message,
                    'timestamp': datetime.now().isoformat(),
                    'trigger_count': self.trigger_count
                }
                
                # Execute action if provided
                if self.action:
                    try:
                        self.action(alert, processes)
                    except Exception as e:
                        logger.error(f"Alert action failed for rule '{self.name}': {e}")
                
                logger.warning(f"Alert triggered: {self.name} - {message}")
                return alert
        except Exception as e:
            logger.error(f"Error checking alert rule '{self.name}': {e}")
        
        return None
    
    def _generate_message(self, processes: List[Dict[str, Any]]) -> str:
        """Generate alert message from template."""
        # Extract common variables for template
        high_energy = [p for p in processes if p.get('energy_score', 0) > 100]
        top_process = processes[0] if processes else None
        
        context = {
            'high_energy_count': len(high_energy),
            'total_processes': len(processes),
            'top_process_name': top_process.get('name', 'N/A') if top_process else 'N/A',
            'top_process_energy': top_process.get('energy_score', 0) if top_process else 0
        }
        
        try:
            return self.message_template.format(**context)
        except KeyError:
            return self.message_template


class AlertManager:
    """Manages alert rules and checks."""
    
    def __init__(self):
        """Initialize alert manager with default rules."""
        self.rules: List[AlertRule] = []
        self.alert_history: List[Dict[str, Any]] = []
        self.max_history = 100
        self._init_default_rules()
    
    def _init_default_rules(self) -> None:
        """Initialize default alert rules."""
        # High energy process alert
        self.add_rule(AlertRule(
            name='high_energy_process',
            condition=lambda procs: any(p.get('energy_score', 0) > 500 for p in procs),
            severity='critical',
            message_template='Critical: Process {top_process_name} has very high energy consumption ({top_process_energy:.2f} mJ/s)'
        ))
        
        # Multiple high energy processes
        self.add_rule(AlertRule(
            name='multiple_high_energy',
            condition=lambda procs: len([p for p in procs if p.get('energy_score', 0) > 100]) >= 5,
            severity='warning',
            message_template='Warning: {high_energy_count} processes consuming high energy (>100 mJ/s)'
        ))
        
        # CPU-bound process spike
        self.add_rule(AlertRule(
            name='cpu_spike',
            condition=lambda procs: any(p.get('cpu_percent', 0) > 90 and p.get('energy_score', 0) > 200 for p in procs),
            severity='warning',
            message_template='Warning: High CPU usage detected - {top_process_name} using {top_process_energy:.2f} mJ/s'
        ))
        
        # Memory-bound process
        self.add_rule(AlertRule(
            name='high_memory_usage',
            condition=lambda procs: any(p.get('memory_mb', 0) > 2048 for p in procs),  # > 2GB
            severity='info',
            message_template='Info: Process {top_process_name} using high memory ({top_process_energy:.2f} mJ/s)'
        ))
        
        logger.info(f"Initialized {len(self.rules)} default alert rules")
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add alert rule."""
        self.rules.append(rule)
        logger.debug(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, name: str) -> bool:
        """Remove alert rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                logger.debug(f"Removed alert rule: {name}")
                return True
        return False
    
    def check_alerts(self, processes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Check all rules against current processes.
        
        Args:
            processes: List of process dictionaries
        
        Returns:
            List of triggered alerts
        """
        alerts = []
        
        for rule in self.rules:
            alert = rule.check(processes)
            if alert:
                alerts.append(alert)
                self.alert_history.append(alert)
                
                # Limit history size
                if len(self.alert_history) > self.max_history:
                    self.alert_history.pop(0)
        
        return alerts
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts from history."""
        return self.alert_history[-limit:]
    
    def get_rule_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all rules."""
        return [
            {
                'name': rule.name,
                'severity': rule.severity,
                'trigger_count': rule.trigger_count,
                'last_triggered': rule.last_triggered.isoformat() if rule.last_triggered else None
            }
            for rule in self.rules
        ]
    
    def clear_history(self) -> None:
        """Clear alert history."""
        self.alert_history.clear()
        logger.info("Alert history cleared")


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None

def get_alert_manager() -> AlertManager:
    """Get global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
