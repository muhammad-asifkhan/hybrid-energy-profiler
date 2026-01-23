"""
logger.py: Structured logging system for Hybrid Energy Profiler.

Provides:
- File logging with rotation
- Console logging
- Structured JSON logging (optional)
- Configurable log levels
"""
import logging
import logging.handlers
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Import config (will be available after config is initialized)
try:
    from energymon.config import get_config
    _config = get_config()
except ImportError:
    _config = None

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
        
        return json.dumps(log_data)


def setup_logger(name: str = 'energymon', 
                 log_dir: Optional[str] = None,
                 level: Optional[str] = None,
                 console_output: Optional[bool] = None,
                 use_json: bool = False) -> logging.Logger:
    """
    Set up logger with file and console handlers.
    
    Args:
        name: Logger name
        log_dir: Directory for log files (uses config if None)
        level: Log level (uses config if None)
        console_output: Enable console output (uses config if None)
        use_json: Use JSON formatting for file logs
    
    Returns:
        Configured logger instance
    """
    # Get configuration if available
    if _config:
        if log_dir is None:
            log_dir = _config.get('logging', 'log_dir', default='logs')
        if level is None:
            level = _config.get('logging', 'level', default='INFO')
        if console_output is None:
            console_output = _config.get('logging', 'console_output', default=True)
        max_file_size = _config.get('logging', 'max_file_size_mb', default=10)
        backup_count = _config.get('logging', 'backup_count', default=5)
    else:
        # Defaults if config not available
        if log_dir is None:
            log_dir = 'logs'
        if level is None:
            level = 'INFO'
        if console_output is None:
            console_output = True
        max_file_size = 10
        backup_count = 5
    
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # File handler with rotation
    log_file = log_path / 'energymon.log'
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_file_size * 1024 * 1024,  # Convert MB to bytes
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    
    # Choose formatter
    if use_json:
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'energymon') -> logging.Logger:
    """
    Get logger instance (creates if doesn't exist).
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Setup if not already configured
        return setup_logger(name)
    return logger


# Convenience functions for common logging operations
def log_metric_collection(logger: logging.Logger, process_count: int, 
                         duration: float, errors: int = 0) -> None:
    """Log metric collection completion."""
    logger.info(
        f"Metric collection completed: {process_count} processes in {duration:.2f}s",
        extra={
            'event_type': 'metric_collection',
            'process_count': process_count,
            'duration_seconds': duration,
            'duration_ms': duration * 1000,
            'errors': errors
        }
    )


def log_error(logger: logging.Logger, error: Exception, 
              context: Optional[Dict[str, Any]] = None) -> None:
    """Log error with context."""
    extra = {
        'event_type': 'error',
        'error_type': type(error).__name__,
        'error_message': str(error)
    }
    if context:
        extra['context'] = context
    
    logger.error(f"Error occurred: {error}", extra=extra, exc_info=True)


def log_performance(logger: logging.Logger, operation: str, 
                   duration: float, **kwargs) -> None:
    """Log performance metrics."""
    logger.debug(
        f"Performance: {operation} took {duration:.3f}s",
        extra={
            'event_type': 'performance',
            'operation': operation,
            'duration_seconds': duration,
            **kwargs
        }
    )


# Global logger instance
_logger_instance: Optional[logging.Logger] = None

def get_default_logger() -> logging.Logger:
    """Get default logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = setup_logger()
    return _logger_instance
