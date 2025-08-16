"""Logging configuration for the Loki MCP server."""

import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory


def configure_logging(
    level: str = "INFO",
    format_json: bool = False,
    include_timestamp: bool = True,
    include_caller: bool = False,
    extra_processors: Optional[list] = None
) -> None:
    """
    Configure structured logging for the Loki MCP server.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_json: Whether to output logs in JSON format
        include_timestamp: Whether to include timestamps in logs
        include_caller: Whether to include caller information
        extra_processors: Additional log processors
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )
    
    # Build processor chain
    processors = []
    
    # Add timestamp if requested
    if include_timestamp:
        processors.append(structlog.stdlib.add_log_level)
        processors.append(structlog.stdlib.add_logger_name)
        processors.append(structlog.processors.TimeStamper(fmt="ISO"))
    
    # Add caller information if requested
    if include_caller:
        processors.append(structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ))
    
    # Add custom processors
    if extra_processors:
        processors.extend(extra_processors)
    
    # Add error handling processors
    processors.extend([
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.format_exc_info,
    ])
    
    # Choose output format
    if format_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_error_context_processor():
    """
    Create a processor that adds error context to log entries.
    
    Returns:
        Log processor function
    """
    def add_error_context(logger, method_name, event_dict):
        """Add error context information to log entries."""
        # Add error categorization for error-level logs
        if method_name in ('error', 'critical', 'exception'):
            if 'error' in event_dict:
                error = event_dict['error']
                
                # Try to categorize the error
                if 'connection' in str(error).lower():
                    event_dict['error_category'] = 'connection'
                elif 'auth' in str(error).lower():
                    event_dict['error_category'] = 'authentication'
                elif 'rate' in str(error).lower() and 'limit' in str(error).lower():
                    event_dict['error_category'] = 'rate_limit'
                elif 'timeout' in str(error).lower():
                    event_dict['error_category'] = 'timeout'
                elif 'query' in str(error).lower() or 'logql' in str(error).lower():
                    event_dict['error_category'] = 'query'
                else:
                    event_dict['error_category'] = 'unknown'
        
        return event_dict
    
    return add_error_context


def get_performance_processor():
    """
    Create a processor that adds performance metrics to log entries.
    
    Returns:
        Log processor function
    """
    def add_performance_metrics(logger, method_name, event_dict):
        """Add performance metrics to log entries."""
        # Add duration formatting for operations with duration
        if 'duration' in event_dict:
            duration = event_dict['duration']
            if isinstance(duration, (int, float)):
                if duration < 1:
                    event_dict['duration_formatted'] = f"{duration*1000:.1f}ms"
                else:
                    event_dict['duration_formatted'] = f"{duration:.2f}s"
        
        # Add operation timing categories
        if 'operation' in event_dict and 'duration' in event_dict:
            duration = event_dict['duration']
            if isinstance(duration, (int, float)):
                if duration < 0.1:
                    event_dict['performance_category'] = 'fast'
                elif duration < 1.0:
                    event_dict['performance_category'] = 'normal'
                elif duration < 5.0:
                    event_dict['performance_category'] = 'slow'
                else:
                    event_dict['performance_category'] = 'very_slow'
        
        return event_dict
    
    return add_performance_metrics


def get_security_processor():
    """
    Create a processor that sanitizes sensitive information from logs.
    
    Returns:
        Log processor function
    """
    def sanitize_sensitive_data(logger, method_name, event_dict):
        """Remove or mask sensitive information from log entries."""
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'auth', 'credential',
            'bearer_token', 'api_key', 'access_token', 'refresh_token'
        }
        
        def sanitize_dict(d):
            """Recursively sanitize dictionary values."""
            if not isinstance(d, dict):
                return d
            
            sanitized = {}
            for key, value in d.items():
                key_lower = key.lower()
                
                # Check if key contains sensitive information
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    if value:
                        sanitized[key] = "***REDACTED***"
                    else:
                        sanitized[key] = value
                elif isinstance(value, dict):
                    sanitized[key] = sanitize_dict(value)
                elif isinstance(value, str) and len(value) > 20:
                    # Check if string looks like a token (long alphanumeric string)
                    if value.replace('-', '').replace('_', '').isalnum():
                        sanitized[key] = f"{value[:8]}***REDACTED***"
                    else:
                        sanitized[key] = value
                else:
                    sanitized[key] = value
            
            return sanitized
        
        # Sanitize the entire event dict
        return sanitize_dict(event_dict)
    
    return sanitize_sensitive_data


class StructuredLogger:
    """Enhanced structured logger with error handling context."""
    
    def __init__(self, name: str):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
        """
        self.logger = structlog.get_logger(name)
    
    def log_operation_start(
        self, 
        operation: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Log the start of an operation and return context.
        
        Args:
            operation: Operation name
            **kwargs: Additional context
            
        Returns:
            Operation context for tracking
        """
        import time
        
        context = {
            'operation': operation,
            'start_time': time.time(),
            **kwargs
        }
        
        self.logger.info(
            "Operation started",
            **context
        )
        
        return context
    
    def log_operation_success(
        self, 
        context: Dict[str, Any], 
        result_summary: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log successful completion of an operation.
        
        Args:
            context: Operation context from log_operation_start
            result_summary: Optional summary of results
            **kwargs: Additional context
        """
        import time
        
        duration = time.time() - context['start_time']
        
        log_data = {
            **context,
            'duration': duration,
            'status': 'success',
            **kwargs
        }
        
        if result_summary:
            log_data['result_summary'] = result_summary
        
        self.logger.info(
            "Operation completed successfully",
            **log_data
        )
    
    def log_operation_error(
        self, 
        context: Dict[str, Any], 
        error: Exception,
        **kwargs
    ) -> None:
        """
        Log failed completion of an operation.
        
        Args:
            context: Operation context from log_operation_start
            error: Exception that occurred
            **kwargs: Additional context
        """
        import time
        
        duration = time.time() - context['start_time']
        
        log_data = {
            **context,
            'duration': duration,
            'status': 'error',
            'error': str(error),
            'error_type': type(error).__name__,
            **kwargs
        }
        
        self.logger.error(
            "Operation failed",
            **log_data
        )
    
    def log_retry_attempt(
        self, 
        operation: str, 
        attempt: int, 
        max_attempts: int,
        error: Exception,
        delay: float,
        **kwargs
    ) -> None:
        """
        Log retry attempt information.
        
        Args:
            operation: Operation being retried
            attempt: Current attempt number
            max_attempts: Maximum number of attempts
            error: Error that triggered retry
            delay: Delay before retry
            **kwargs: Additional context
        """
        self.logger.warning(
            "Operation failed, retrying",
            operation=operation,
            attempt=attempt,
            max_attempts=max_attempts,
            error=str(error),
            error_type=type(error).__name__,
            retry_delay=delay,
            **kwargs
        )
    
    def log_circuit_breaker_event(
        self, 
        event: str, 
        operation: str,
        **kwargs
    ) -> None:
        """
        Log circuit breaker events.
        
        Args:
            event: Circuit breaker event (open, close, half_open)
            operation: Operation affected
            **kwargs: Additional context
        """
        self.logger.warning(
            "Circuit breaker event",
            circuit_breaker_event=event,
            operation=operation,
            **kwargs
        )


def setup_default_logging(level: Optional[str] = None) -> None:
    """
    Set up default logging configuration for the Loki MCP server.
    
    Args:
        level: Optional log level override
    """
    import os
    
    # Get configuration from environment or parameter
    log_level = (level or os.getenv('LOKI_LOG_LEVEL', 'INFO')).upper()
    log_format = os.getenv('LOKI_LOG_FORMAT', 'console').lower()
    
    # For MCP stdio transport, disable logging to avoid interfering with JSON communication
    if os.getenv('MCP_STDIO_MODE') == '1' or '--stdio' in sys.argv or 'stdio' in sys.argv:
        # Configure minimal logging that outputs to stderr only
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stderr,
            level=logging.CRITICAL
        )
        
        # Configure structlog with minimal processors that don't output to stdout
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                lambda logger, method_name, event_dict: ""  # Drop all log output
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return
    
    # Configure logging
    configure_logging(
        level=log_level,
        format_json=(log_format == 'json'),
        include_timestamp=True,
        include_caller=(log_level == 'DEBUG'),
        extra_processors=[
            get_error_context_processor(),
            get_performance_processor(),
            get_security_processor()
        ]
    )