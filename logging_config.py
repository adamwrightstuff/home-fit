"""
Logging configuration for HomeFit API
Provides structured logging for production monitoring
"""

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'location'):
            log_entry['location'] = record.location
        if hasattr(record, 'lat'):
            log_entry['lat'] = record.lat
        if hasattr(record, 'lon'):
            log_entry['lon'] = record.lon
        if hasattr(record, 'pillar_name'):
            log_entry['pillar_name'] = record.pillar_name
        if hasattr(record, 'response_time'):
            log_entry['response_time'] = record.response_time
        if hasattr(record, 'error_type'):
            log_entry['error_type'] = record.error_type
        if hasattr(record, 'api_name'):
            log_entry['api_name'] = record.api_name
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON formatting for structured logs
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Set our application logger level
    logging.getLogger("homefit").setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"homefit.{name}")


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)


def log_api_call(logger: logging.Logger, api_name: str, endpoint: str, 
                 request_id: str = None, **kwargs):
    """
    Log an API call with structured data.
    
    Args:
        logger: Logger instance
        api_name: Name of the API being called
        endpoint: API endpoint
        request_id: Optional request ID for tracing
        **kwargs: Additional fields to log
    """
    extra = {
        "api_name": api_name,
        "endpoint": endpoint,
        **kwargs
    }
    if request_id:
        extra["request_id"] = request_id
    
    logger.info(f"API call to {api_name}: {endpoint}", extra=extra)


def log_pillar_calculation(logger: logging.Logger, pillar_name: str, 
                          score: float, confidence: float = None,
                          request_id: str = None, **kwargs):
    """
    Log a pillar score calculation.
    
    Args:
        logger: Logger instance
        pillar_name: Name of the pillar
        score: Calculated score
        confidence: Confidence level (0-100)
        request_id: Optional request ID for tracing
        **kwargs: Additional fields to log
    """
    extra = {
        "pillar_name": pillar_name,
        "score": score,
        **kwargs
    }
    if confidence is not None:
        extra["confidence"] = confidence
    if request_id:
        extra["request_id"] = request_id
    
    logger.info(f"Pillar {pillar_name} calculated: {score:.1f}/100", extra=extra)


def log_error(logger: logging.Logger, error_type: str, message: str,
              request_id: str = None, **kwargs):
    """
    Log an error with structured data.
    
    Args:
        logger: Logger instance
        error_type: Type of error (e.g., "api_error", "timeout", "validation")
        message: Error message
        request_id: Optional request ID for tracing
        **kwargs: Additional fields to log
    """
    extra = {
        "error_type": error_type,
        **kwargs
    }
    if request_id:
        extra["request_id"] = request_id
    
    logger.error(message, extra=extra)


def log_performance(logger: logging.Logger, operation: str, duration: float,
                   request_id: str = None, **kwargs):
    """
    Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Name of the operation
        duration: Duration in seconds
        request_id: Optional request ID for tracing
        **kwargs: Additional fields to log
    """
    extra = {
        "operation": operation,
        "duration": duration,
        **kwargs
    }
    if request_id:
        extra["request_id"] = request_id
    
    logger.info(f"Performance: {operation} took {duration:.2f}s", extra=extra)
