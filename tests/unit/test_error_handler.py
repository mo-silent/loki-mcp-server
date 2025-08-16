"""Unit tests for error handling functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
import pytest
import httpx

from app.error_handler import (
    ErrorCategory,
    ErrorSeverity,
    ErrorContext,
    ErrorInfo,
    ErrorClassifier,
    BackoffStrategy,
    ErrorHandler,
    CircuitBreaker,
    ErrorStatistics
)
from app.loki_client import (
    LokiClientError,
    LokiConnectionError,
    LokiAuthenticationError,
    LokiQueryError,
    LokiRateLimitError
)


class TestErrorClassifier:
    """Test error classification functionality."""
    
    def test_classify_authentication_error(self):
        """Test classification of authentication errors."""
        error = LokiAuthenticationError("Invalid credentials")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.severity == ErrorSeverity.HIGH
        assert "Authentication failed" in error_info.message
        assert "credentials" in error_info.suggestion.lower()
        assert not error_info.should_retry
        assert error_info.user_actionable
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        error = LokiRateLimitError("Too many requests")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.RATE_LIMIT
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert "Rate limit exceeded" in error_info.message
        assert "reduce request frequency" in error_info.suggestion.lower()
        assert error_info.should_retry
        assert error_info.retry_after == 60
    
    def test_classify_query_error(self):
        """Test classification of query errors."""
        error = LokiQueryError("Invalid LogQL syntax")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.QUERY
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert "Query execution failed" in error_info.message
        assert "LogQL syntax" in error_info.suggestion
        assert not error_info.should_retry
    
    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        error = LokiConnectionError("Connection refused")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.CONNECTION
        assert error_info.severity == ErrorSeverity.HIGH
        assert "Failed to connect" in error_info.message
        assert "network connectivity" in error_info.suggestion.lower()
        assert error_info.should_retry
    
    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        error = httpx.TimeoutException("Request timed out")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.TIMEOUT
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert "Request timed out" in error_info.message
        assert "network connectivity" in error_info.suggestion.lower()
        assert error_info.should_retry
    
    def test_classify_http_status_errors(self):
        """Test classification of HTTP status errors."""
        # Mock response for 401
        response_401 = Mock()
        response_401.status_code = 401
        response_401.text = "Unauthorized"
        error_401 = httpx.HTTPStatusError("401", request=Mock(), response=response_401)
        
        error_info = ErrorClassifier.classify_error(error_401)
        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert not error_info.should_retry
        
        # Mock response for 429
        response_429 = Mock()
        response_429.status_code = 429
        response_429.text = "Too Many Requests"
        response_429.headers = {"retry-after": "30"}
        error_429 = httpx.HTTPStatusError("429", request=Mock(), response=response_429)
        
        error_info = ErrorClassifier.classify_error(error_429)
        assert error_info.category == ErrorCategory.RATE_LIMIT
        assert error_info.should_retry
        
        # Mock response for 500
        response_500 = Mock()
        response_500.status_code = 500
        response_500.text = "Internal Server Error"
        error_500 = httpx.HTTPStatusError("500", request=Mock(), response=response_500)
        
        error_info = ErrorClassifier.classify_error(error_500)
        assert error_info.category == ErrorCategory.CONNECTION
        assert error_info.should_retry
    
    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        # Mock a validation error
        error = Mock()
        error.__class__.__name__ = "ValidationError"
        error.__str__ = lambda self: "Invalid parameter value"
        
        error_info = ErrorClassifier.classify_error(error)
        assert error_info.category == ErrorCategory.VALIDATION
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert not error_info.should_retry
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        error = ValueError("Some unexpected error")
        error_info = ErrorClassifier.classify_error(error)
        
        assert error_info.category == ErrorCategory.UNKNOWN
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert "Unexpected error" in error_info.message
        assert error_info.should_retry


class TestBackoffStrategy:
    """Test backoff strategy implementations."""
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        # Test basic exponential growth
        delay_0 = BackoffStrategy.exponential_backoff(0, base_delay=1.0, jitter=False)
        delay_1 = BackoffStrategy.exponential_backoff(1, base_delay=1.0, jitter=False)
        delay_2 = BackoffStrategy.exponential_backoff(2, base_delay=1.0, jitter=False)
        
        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0
        
        # Test max delay cap
        delay_high = BackoffStrategy.exponential_backoff(10, base_delay=1.0, max_delay=60.0, jitter=False)
        assert delay_high == 60.0
        
        # Test jitter adds randomness
        delay_jitter_1 = BackoffStrategy.exponential_backoff(1, base_delay=1.0, jitter=True)
        delay_jitter_2 = BackoffStrategy.exponential_backoff(1, base_delay=1.0, jitter=True)
        
        # With jitter, delays should be different (with high probability)
        # and within expected range
        assert 1.5 <= delay_jitter_1 <= 2.5  # 2.0 ± 25%
        assert 1.5 <= delay_jitter_2 <= 2.5
    
    def test_linear_backoff(self):
        """Test linear backoff calculation."""
        delay_0 = BackoffStrategy.linear_backoff(0, base_delay=2.0)
        delay_1 = BackoffStrategy.linear_backoff(1, base_delay=2.0)
        delay_2 = BackoffStrategy.linear_backoff(2, base_delay=2.0)
        
        assert delay_0 == 2.0
        assert delay_1 == 4.0
        assert delay_2 == 6.0
        
        # Test max delay cap
        delay_high = BackoffStrategy.linear_backoff(100, base_delay=2.0, max_delay=10.0)
        assert delay_high == 10.0
    
    def test_fixed_backoff(self):
        """Test fixed backoff calculation."""
        delay = BackoffStrategy.fixed_backoff(5.0)
        assert delay == 5.0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        assert cb.state == "closed"
        assert cb.can_execute()
        assert cb.failure_count == 0
    
    def test_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        # Record failures up to threshold
        for i in range(3):
            cb.record_failure()
            if i < 2:
                assert cb.state == "closed"
            else:
                assert cb.state == "open"
                assert not cb.can_execute()
    
    def test_recovery_timeout(self):
        """Test circuit breaker recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert not cb.can_execute()
        
        # Wait for recovery timeout
        time.sleep(1.1)
        assert cb.can_execute()
        assert cb.state == "half-open"
    
    def test_half_open_success(self):
        """Test circuit breaker closes after successful recovery."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, success_threshold=2)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        
        # Wait and enter half-open
        time.sleep(1.1)
        assert cb.can_execute()
        assert cb.state == "half-open"
        
        # Record successes to close circuit
        cb.record_success()
        assert cb.state == "half-open"
        cb.record_success()
        assert cb.state == "closed"
    
    def test_half_open_failure(self):
        """Test circuit breaker reopens on failure during recovery."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        
        # Wait and enter half-open
        time.sleep(1.1)
        assert cb.can_execute()
        assert cb.state == "half-open"
        
        # Failure during half-open should reopen circuit
        cb.record_failure()
        assert cb.state == "open"
        assert not cb.can_execute()
    
    def test_get_status(self):
        """Test circuit breaker status reporting."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        status = cb.get_status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["can_execute"] is True
        
        cb.record_failure()
        status = cb.get_status()
        assert status["failure_count"] == 1


class TestErrorStatistics:
    """Test error statistics tracking."""
    
    def test_record_success(self):
        """Test recording successful operations."""
        stats = ErrorStatistics()
        
        stats.record_success("query_logs", 1.5)
        stats.record_success("query_logs", 2.0)
        
        operation_stats = stats.get_statistics()["operation_stats"]["query_logs"]
        assert operation_stats["success_count"] == 2
        assert operation_stats["error_count"] == 0
        assert operation_stats["avg_duration"] == 1.75
    
    def test_record_error(self):
        """Test recording error operations."""
        stats = ErrorStatistics()
        
        stats.record_error("query_logs", ErrorCategory.CONNECTION)
        stats.record_error("search_logs", ErrorCategory.AUTHENTICATION)
        
        statistics = stats.get_statistics()
        assert statistics["operation_stats"]["query_logs"]["error_count"] == 1
        assert statistics["error_counts_by_category"]["connection"] == 1
        assert statistics["error_counts_by_category"]["authentication"] == 1
        assert statistics["total_errors"] == 2
    
    def test_get_statistics(self):
        """Test comprehensive statistics reporting."""
        stats = ErrorStatistics()
        
        stats.record_success("query_logs", 1.0)
        stats.record_error("query_logs", ErrorCategory.TIMEOUT)
        
        statistics = stats.get_statistics()
        
        assert "uptime_seconds" in statistics
        assert "operation_stats" in statistics
        assert "error_counts_by_category" in statistics
        assert "total_operations" in statistics
        assert "total_errors" in statistics
        
        assert statistics["total_operations"] == 2
        assert statistics["total_errors"] == 1


class TestErrorHandler:
    """Test error handler with retry logic."""
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler for testing."""
        return ErrorHandler(max_retries=3, enable_circuit_breaker=False)
    
    @pytest.fixture
    def error_context(self):
        """Create error context for testing."""
        return ErrorContext(
            operation="test_operation",
            parameters={"param1": "value1"},
            max_attempts=3
        )
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, error_handler, error_context):
        """Test successful operation without retries."""
        async def successful_operation():
            return {"result": "success"}
        
        result = await error_handler.handle_with_retry(
            successful_operation,
            error_context
        )
        
        assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self, error_handler, error_context):
        """Test retry logic for retryable errors."""
        call_count = 0
        
        async def failing_then_succeeding_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LokiConnectionError("Connection failed")
            return {"result": "success"}
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await error_handler.handle_with_retry(
                failing_then_succeeding_operation,
                error_context
            )
        
        assert result == {"result": "success"}
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self, error_handler, error_context):
        """Test no retry for non-retryable errors."""
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise LokiAuthenticationError("Invalid credentials")
        
        with pytest.raises(LokiAuthenticationError):
            await error_handler.handle_with_retry(
                failing_operation,
                error_context
            )
        
        assert call_count == 1  # Should not retry
    
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, error_handler, error_context):
        """Test behavior when max retries are exhausted."""
        call_count = 0
        
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise LokiConnectionError("Connection failed")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(LokiConnectionError):
                await error_handler.handle_with_retry(
                    always_failing_operation,
                    error_context
                )
        
        assert call_count == 3  # Should try max_attempts times
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test error handler with circuit breaker enabled."""
        error_handler = ErrorHandler(max_retries=2, enable_circuit_breaker=True)
        error_context = ErrorContext(
            operation="test_operation",
            max_attempts=3
        )
        
        async def failing_operation():
            raise LokiConnectionError("Connection failed")
        
        # First few calls should fail normally
        with patch('asyncio.sleep', new_callable=AsyncMock):
            for _ in range(5):  # Trigger circuit breaker
                with pytest.raises(LokiConnectionError):
                    await error_handler.handle_with_retry(
                        failing_operation,
                        error_context
                    )
        
        # Next call should fail due to circuit breaker
        with pytest.raises(LokiConnectionError) as exc_info:
            await error_handler.handle_with_retry(
                failing_operation,
                error_context
            )
        
        assert "Circuit breaker is open" in str(exc_info.value)
    
    def test_get_error_statistics(self, error_handler):
        """Test error statistics retrieval."""
        stats = error_handler.get_error_statistics()
        
        assert "uptime_seconds" in stats
        assert "operation_stats" in stats
        assert "error_counts_by_category" in stats
        assert "total_operations" in stats
        assert "total_errors" in stats


class TestErrorContext:
    """Test error context functionality."""
    
    def test_error_context_creation(self):
        """Test error context creation and attributes."""
        context = ErrorContext(
            operation="test_op",
            parameters={"key": "value"},
            attempt=2,
            max_attempts=5,
            loki_url="http://localhost:3100"
        )
        
        assert context.operation == "test_op"
        assert context.parameters == {"key": "value"}
        assert context.attempt == 2
        assert context.max_attempts == 5
        assert context.loki_url == "http://localhost:3100"
    
    def test_error_context_defaults(self):
        """Test error context with default values."""
        context = ErrorContext(operation="test_op")
        
        assert context.operation == "test_op"
        assert context.parameters is None
        assert context.attempt == 1
        assert context.max_attempts == 3
        assert context.start_time is None
        assert context.loki_url is None


class TestErrorInfo:
    """Test error info structure."""
    
    def test_error_info_creation(self):
        """Test error info creation and attributes."""
        error_info = ErrorInfo(
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            message="Auth failed",
            suggestion="Check credentials",
            details="Invalid token",
            retry_after=30,
            should_retry=False,
            user_actionable=True
        )
        
        assert error_info.category == ErrorCategory.AUTHENTICATION
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.message == "Auth failed"
        assert error_info.suggestion == "Check credentials"
        assert error_info.details == "Invalid token"
        assert error_info.retry_after == 30
        assert error_info.should_retry is False
        assert error_info.user_actionable is True
    
    def test_error_info_defaults(self):
        """Test error info with default values."""
        error_info = ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.LOW,
            message="Some error",
            suggestion="Try again"
        )
        
        assert error_info.details is None
        assert error_info.retry_after is None
        assert error_info.should_retry is False
        assert error_info.user_actionable is True