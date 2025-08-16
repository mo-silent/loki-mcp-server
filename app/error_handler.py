"""Comprehensive error handling for the Loki MCP server."""

import asyncio
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union
from dataclasses import dataclass
from urllib.parse import urlparse

import structlog
import httpx

from .loki_client import (
    LokiClientError, 
    LokiConnectionError, 
    LokiAuthenticationError, 
    LokiQueryError, 
    LokiRateLimitError
)

logger = structlog.get_logger(__name__)

logger = structlog.get_logger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur in the Loki MCP server."""
    CONFIGURATION = "configuration"
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    QUERY = "query"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    operation: str
    parameters: Optional[Dict[str, Any]] = None
    attempt: int = 1
    max_attempts: int = 3
    start_time: Optional[float] = None
    loki_url: Optional[str] = None


@dataclass
class ErrorInfo:
    """Structured error information."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    suggestion: str
    details: Optional[str] = None
    retry_after: Optional[int] = None
    should_retry: bool = False
    user_actionable: bool = True


class ErrorClassifier:
    """Classifies errors and provides structured error information."""
    
    @staticmethod
    def classify_error(
        error: Exception, 
        context: Optional[ErrorContext] = None
    ) -> ErrorInfo:
        """
        Classify an error and return structured error information.
        
        Args:
            error: The exception to classify
            context: Optional context information
            
        Returns:
            Structured error information
        """
        # Handle Loki-specific errors
        if isinstance(error, LokiAuthenticationError):
            return ErrorInfo(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.HIGH,
                message="Authentication failed",
                suggestion="Check your Loki credentials (username/password or bearer token)",
                details=str(error),
                should_retry=False,
                user_actionable=True
            )
        
        elif isinstance(error, LokiRateLimitError):
            return ErrorInfo(
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.MEDIUM,
                message="Rate limit exceeded",
                suggestion="Reduce request frequency or wait before retrying",
                details=str(error),
                retry_after=60,  # Default retry after 1 minute
                should_retry=True,
                user_actionable=True
            )
        
        elif isinstance(error, LokiQueryError):
            return ErrorInfo(
                category=ErrorCategory.QUERY,
                severity=ErrorSeverity.MEDIUM,
                message="Query execution failed",
                suggestion="Check your LogQL syntax and query parameters",
                details=str(error),
                should_retry=False,
                user_actionable=True
            )
        
        elif isinstance(error, LokiConnectionError):
            return ErrorInfo(
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                message="Failed to connect to Loki",
                suggestion="Check Loki URL and network connectivity",
                details=str(error),
                should_retry=True,
                user_actionable=True
            )
        
        # Handle HTTP-specific errors
        elif isinstance(error, httpx.TimeoutException):
            return ErrorInfo(
                category=ErrorCategory.TIMEOUT,
                severity=ErrorSeverity.MEDIUM,
                message="Request timed out",
                suggestion="Check network connectivity or increase timeout setting",
                details=f"Request timed out after {getattr(error, 'timeout', 'unknown')} seconds",
                should_retry=True,
                user_actionable=True
            )
        
        elif isinstance(error, httpx.ConnectError):
            return ErrorInfo(
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                message="Connection failed",
                suggestion="Verify Loki server is running and URL is correct",
                details=str(error),
                should_retry=True,
                user_actionable=True
            )
        
        elif isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code == 401:
                return ErrorInfo(
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.HIGH,
                    message="Authentication required",
                    suggestion="Provide valid credentials for Loki access",
                    details=f"HTTP {status_code}: {error.response.text}",
                    should_retry=False,
                    user_actionable=True
                )
            elif status_code == 403:
                return ErrorInfo(
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.HIGH,
                    message="Access forbidden",
                    suggestion="Check user permissions for Loki access",
                    details=f"HTTP {status_code}: {error.response.text}",
                    should_retry=False,
                    user_actionable=True
                )
            elif status_code == 429:
                return ErrorInfo(
                    category=ErrorCategory.RATE_LIMIT,
                    severity=ErrorSeverity.MEDIUM,
                    message="Too many requests",
                    suggestion="Wait before making more requests",
                    details=f"HTTP {status_code}: {error.response.text}",
                    retry_after=ErrorClassifier._extract_retry_after(error.response),
                    should_retry=True,
                    user_actionable=True
                )
            elif 500 <= status_code < 600:
                return ErrorInfo(
                    category=ErrorCategory.CONNECTION,
                    severity=ErrorSeverity.HIGH,
                    message="Server error",
                    suggestion="Loki server is experiencing issues, try again later",
                    details=f"HTTP {status_code}: {error.response.text}",
                    should_retry=True,
                    user_actionable=False
                )
            else:
                return ErrorInfo(
                    category=ErrorCategory.QUERY,
                    severity=ErrorSeverity.MEDIUM,
                    message=f"HTTP error {status_code}",
                    suggestion="Check request parameters and try again",
                    details=f"HTTP {status_code}: {error.response.text}",
                    should_retry=False,
                    user_actionable=True
                )
        
        # Handle validation errors
        elif hasattr(error, '__class__') and 'ValidationError' in error.__class__.__name__:
            return ErrorInfo(
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                message="Parameter validation failed",
                suggestion="Check parameter types and values",
                details=str(error),
                should_retry=False,
                user_actionable=True
            )
        
        # Handle configuration errors
        elif hasattr(error, '__class__') and 'ConfigurationError' in error.__class__.__name__:
            return ErrorInfo(
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.CRITICAL,
                message="Configuration error",
                suggestion="Check environment variables and configuration settings",
                details=str(error),
                should_retry=False,
                user_actionable=True
            )
        
        # Generic error handling
        else:
            return ErrorInfo(
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.MEDIUM,
                message="Unexpected error occurred",
                suggestion="Check logs for more details and try again",
                details=str(error),
                should_retry=True,
                user_actionable=False
            )
    
    @staticmethod
    def _extract_retry_after(response: httpx.Response) -> Optional[int]:
        """Extract retry-after header from HTTP response."""
        retry_after = response.headers.get('retry-after')
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return None


class BackoffStrategy:
    """Implements various backoff strategies for retries."""
    
    @staticmethod
    def exponential_backoff(
        attempt: int, 
        base_delay: float = 1.0, 
        max_delay: float = 60.0,
        jitter: bool = True
    ) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Whether to add random jitter
            
        Returns:
            Delay in seconds
        """
        import random
        
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        if jitter:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    @staticmethod
    def linear_backoff(
        attempt: int, 
        base_delay: float = 1.0, 
        max_delay: float = 60.0
    ) -> float:
        """
        Calculate linear backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds
        """
        return min(base_delay * (attempt + 1), max_delay)
    
    @staticmethod
    def fixed_backoff(delay: float = 5.0) -> float:
        """
        Return fixed delay.
        
        Args:
            delay: Fixed delay in seconds
            
        Returns:
            Delay in seconds
        """
        return delay


class ErrorHandler:
    """Main error handler with retry logic and user-friendly messaging."""
    
    def __init__(self, max_retries: int = 3, enable_circuit_breaker: bool = True):
        """
        Initialize error handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            enable_circuit_breaker: Whether to enable circuit breaker pattern
        """
        self.max_retries = max_retries
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self.error_stats = ErrorStatistics()
    
    async def handle_with_retry(
        self,
        operation: callable,
        context: ErrorContext,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute operation with retry logic and error handling.
        
        Args:
            operation: Async function to execute
            context: Error context information
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Operation result
            
        Raises:
            Exception: Final exception after all retries exhausted
        """
        context.start_time = time.time()
        last_error = None
        
        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            raise LokiConnectionError("Circuit breaker is open - too many recent failures")
        
        for attempt in range(context.max_attempts):
            context.attempt = attempt + 1
            
            try:
                logger.debug(
                    "Executing operation",
                    operation=context.operation,
                    attempt=context.attempt,
                    max_attempts=context.max_attempts
                )
                
                result = await operation(*args, **kwargs)
                
                # Success - reset circuit breaker
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                
                # Record success statistics
                duration = time.time() - context.start_time
                self.error_stats.record_success(context.operation, duration)
                
                return result
                
            except Exception as error:
                last_error = error
                error_info = ErrorClassifier.classify_error(error, context)
                
                # Record error statistics
                self.error_stats.record_error(context.operation, error_info.category)
                
                # Log the error
                logger.warning(
                    "Operation failed",
                    operation=context.operation,
                    attempt=context.attempt,
                    error_category=error_info.category.value,
                    error_message=error_info.message,
                    should_retry=error_info.should_retry,
                    error=str(error)
                )
                
                # Check if we should retry
                if not error_info.should_retry or attempt == context.max_attempts - 1:
                    # Record failure in circuit breaker
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure()
                    
                    # Enhance error with user-friendly information
                    enhanced_error = self._create_enhanced_error(error, error_info, context)
                    raise enhanced_error
                
                # Calculate backoff delay
                if error_info.retry_after:
                    delay = error_info.retry_after
                elif error_info.category == ErrorCategory.RATE_LIMIT:
                    delay = BackoffStrategy.linear_backoff(attempt, 30.0, 300.0)
                else:
                    delay = BackoffStrategy.exponential_backoff(attempt)
                
                logger.info(
                    "Retrying operation after delay",
                    operation=context.operation,
                    attempt=context.attempt,
                    delay=delay,
                    error_category=error_info.category.value
                )
                
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        if last_error:
            raise last_error
    
    def _create_enhanced_error(
        self, 
        original_error: Exception, 
        error_info: ErrorInfo, 
        context: ErrorContext
    ) -> Exception:
        """
        Create an enhanced error with user-friendly information.
        
        Args:
            original_error: Original exception
            error_info: Classified error information
            context: Error context
            
        Returns:
            Enhanced exception
        """
        # Create user-friendly error message
        message_parts = [error_info.message]
        
        if error_info.suggestion:
            message_parts.append(f"Suggestion: {error_info.suggestion}")
        
        if error_info.details:
            message_parts.append(f"Details: {error_info.details}")
        
        if context.attempt > 1:
            message_parts.append(f"Failed after {context.attempt} attempts")
        
        enhanced_message = ". ".join(message_parts)
        
        # Create appropriate exception type
        if error_info.category == ErrorCategory.AUTHENTICATION:
            return LokiAuthenticationError(enhanced_message)
        elif error_info.category == ErrorCategory.RATE_LIMIT:
            return LokiRateLimitError(enhanced_message)
        elif error_info.category == ErrorCategory.QUERY:
            return LokiQueryError(enhanced_message)
        elif error_info.category == ErrorCategory.CONNECTION:
            return LokiConnectionError(enhanced_message)
        else:
            return LokiClientError(enhanced_message)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring."""
        stats = self.error_stats.get_statistics()
        
        if self.circuit_breaker:
            stats["circuit_breaker"] = self.circuit_breaker.get_status()
        
        return stats


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self, 
        failure_threshold: int = 5, 
        recovery_timeout: int = 60,
        success_threshold: int = 3
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Number of successes needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half-open"
                self.success_count = 0
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == "half-open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = "closed"
                self.failure_count = 0
        elif self.state == "closed":
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == "closed" and self.failure_count >= self.failure_threshold:
            self.state = "open"
        elif self.state == "half-open":
            self.state = "open"
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute()
        }


class ErrorStatistics:
    """Tracks error statistics for monitoring and debugging."""
    
    def __init__(self):
        """Initialize error statistics."""
        self.operation_stats: Dict[str, Dict[str, Any]] = {}
        self.error_counts: Dict[str, int] = {}
        self.start_time = time.time()
    
    def record_success(self, operation: str, duration: float) -> None:
        """Record successful operation."""
        if operation not in self.operation_stats:
            self.operation_stats[operation] = {
                "success_count": 0,
                "error_count": 0,
                "total_duration": 0.0,
                "avg_duration": 0.0
            }
        
        stats = self.operation_stats[operation]
        stats["success_count"] += 1
        stats["total_duration"] += duration
        stats["avg_duration"] = stats["total_duration"] / stats["success_count"]
    
    def record_error(self, operation: str, error_category: ErrorCategory) -> None:
        """Record error for operation."""
        if operation not in self.operation_stats:
            self.operation_stats[operation] = {
                "success_count": 0,
                "error_count": 0,
                "total_duration": 0.0,
                "avg_duration": 0.0
            }
        
        self.operation_stats[operation]["error_count"] += 1
        
        category_key = error_category.value
        self.error_counts[category_key] = self.error_counts.get(category_key, 0) + 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "operation_stats": self.operation_stats.copy(),
            "error_counts_by_category": self.error_counts.copy(),
            "total_operations": sum(
                stats["success_count"] + stats["error_count"] 
                for stats in self.operation_stats.values()
            ),
            "total_errors": sum(self.error_counts.values())
        }