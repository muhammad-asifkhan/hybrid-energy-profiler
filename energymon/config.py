"""
config.py: Configuration management for Hybrid Energy Profiler.

Supports configuration from:
1. Default values (hardcoded)
2. config.json file
3. Environment variables (highest priority)
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

class Config:
    """Configuration manager with support for file and environment variable overrides."""
    
    def __init__(self, config_path: str = 'config.json'):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.config_path = Path(config_path)
        self.defaults = self._get_defaults()
        self.config = self._load_config()
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            'collection': {
                'interval': 5.0,
                'min_cpu': 0.0,
                'min_memory': 0.0,
                'max_processes': 1000,
                'use_interval_measurement': True,
                'interval_duration': 0.1
            },
            'energy_model': {
                'weights': {
                    'cpu': 0.6,
                    'io': 0.3,
                    'memory': 0.1,
                    'context_switches': 0.2,
                    'syscalls': 0.1
                },
                'adaptive': True
            },
            'dashboard': {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'auto_refresh_interval': 5,
                'max_processes_display': 1000
            },
            'storage': {
                'enabled': True,
                'db_path': 'data/metrics.db',
                'retention_days': 30,
                'save_interval': 60  # Save snapshot every N seconds
            },
            'logging': {
                'level': 'INFO',
                'log_dir': 'logs',
                'max_file_size_mb': 10,
                'backup_count': 5,
                'console_output': True
            },
            'security': {
                'require_auth': False,
                'api_rate_limit': 100,  # requests per minute
                'allowed_hosts': ['*']
            },
            'output': {
                'exports_dir': 'output/exports',
                'graphs_dir': 'output/graphs',
                'data_dir': 'data'
            }
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file and environment variables.
        
        Priority: Environment variables > config.json > defaults
        """
        config = self._deep_copy_dict(self.defaults)
        
        # Load from file if exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    config = self._merge_dicts(config, file_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Warning: Failed to load config file {self.config_path}: {e}")
                print("   Using defaults and environment variables only")
        
        # Override with environment variables
        config = self._apply_env_overrides(config)
        
        return config
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config."""
        env_mappings = {
            'ENERGYMON_INTERVAL': ('collection', 'interval'),
            'ENERGYMON_PORT': ('dashboard', 'port'),
            'ENERGYMON_DEBUG': ('dashboard', 'debug'),
            'ENERGYMON_LOG_LEVEL': ('logging', 'level'),
            'ENERGYMON_HOST': ('dashboard', 'host'),
            'ENERGYMON_DB_PATH': ('storage', 'db_path'),
            'ENERGYMON_RETENTION_DAYS': ('storage', 'retention_days'),
            'ENERGYMON_STORAGE_ENABLED': ('storage', 'enabled'),
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion
                if key in ['port', 'interval', 'retention_days', 'max_file_size_mb', 
                          'backup_count', 'api_rate_limit', 'save_interval',
                          'max_processes', 'max_processes_display']:
                    try:
                        config[section][key] = int(value) if '.' not in value else float(value)
                    except ValueError:
                        print(f"⚠️  Warning: Invalid value for {env_var}: {value}")
                elif key == 'debug' or key == 'enabled' or key == 'require_auth' or key == 'console_output':
                    config[section][key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    config[section][key] = value
        
        return config
    
    def _merge_dicts(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries."""
        result = self._deep_copy_dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    def _deep_copy_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of a dictionary."""
        return json.loads(json.dumps(d))
    
    def get(self, *keys, default: Any = None) -> Any:
        """
        Get config value using dot notation.
        
        Args:
            *keys: Path to config value (e.g., 'dashboard', 'port')
            default: Default value if key not found
        
        Returns:
            Config value or default
        
        Examples:
            config.get('dashboard', 'port')  # Returns 5000
            config.get('collection', 'interval')  # Returns 5.0
        """
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, *keys: str, value: Any) -> None:
        """
        Set config value using dot notation.
        
        Args:
            *keys: Path to config value
            value: Value to set
        
        Examples:
            config.set('dashboard', 'port', 8080)
        """
        config_ref = self.config
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]
        config_ref[keys[-1]] = value
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save current config to file.
        
        Args:
            path: Optional path to save config (defaults to config_path)
        """
        save_path = Path(path) if path else self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(save_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"⚠️  Warning: Failed to save config to {save_path}: {e}")
    
    def reload(self) -> None:
        """Reload configuration from file and environment."""
        self.config = self._load_config()
    
    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(config_path={self.config_path}, sections={list(self.config.keys())})"


# Global config instance
_config_instance: Optional[Config] = None

def get_config(config_path: str = 'config.json') -> Config:
    """
    Get global config instance (singleton pattern).
    
    Args:
        config_path: Path to config file (only used on first call)
    
    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
