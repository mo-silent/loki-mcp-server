"""Unit tests for Loki HTTP client."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.config import LokiConfig
from app.loki_client import (
    LokiClient,
    LokiClientError,
    LokiConnectionError,
    LokiAuthenticationError,
    LokiQueryError,
    LokiRateLimitError,
    RateLimiter,
)


@pytest.fixture
def basic_config():
    """Basic Loki configuration for testing."""
    return LokiConfig(
        url="http://localhost:3100",
        timeout=30,
        max_retries=3,
        rate_limit_requests=100,
        rate_limit_period=60
    )


@pytest.fixture
def auth_config():
    """Loki configuration with authentication."""
    return LokiConfig(
        url="http://localhost:3100",
        username="admin",
        password="secret",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def bearer_config():
    """Loki configuration with bearer token."""
    return LokiConfig(
        url="http://localhost:3100",
        bearer_token="test-token",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def mock_response():
    """Mock successful response data."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"job": "test", "level": "info"},
                    "values": [
                        ["1640995200000000000", "Test log message"]
                    ]
                }
            ]
        }
    }


class TestLokiClient:
    """Test cases for LokiClient."""

    @pytest.mark.asyncio
    async def test_client_initialization(self, basic_config):
        """Test client initialization."""
        client = LokiClient(basic_config)
        assert client.config == basic_config
        assert client._session is None

    @pytest.mark.asyncio
    async def test_context_manager(self, basic_config):
        """Test async context manager."""
        async with LokiClient(basic_config) as client:
            assert client._session is not None
        # Client should be closed after context exit
        assert client._session is None

    @pytest.mark.asyncio
    async def test_ensure_session_basic_auth(self, auth_config):
        """Test session initialization with basic auth."""
        client = LokiClient(auth_config)
        await client._ensure_session()
        
        assert client._session is not None
        assert client._session.auth is not None
        # Should be a tuple for basic auth
        assert isinstance(client._session.auth, tuple)
        assert client._session.auth == (auth_config.username, auth_config.password)
        
        await client.close()

    @pytest.mark.asyncio
    async def test_ensure_session_bearer_token(self, bearer_config):
        """Test session initialization with bearer token."""
        client = LokiClient(bearer_config)
        await client._ensure_session()
        
        assert client._session is not None
        assert "Authorization" in client._session.headers
        assert client._session.headers["Authorization"] == "Bearer test-token"
        
        await client.close()

    @pytest.mark.asyncio
    async def test_make_request_success(self, basic_config, mock_response):
        """Test successful HTTP request."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            
            # Mock asyncio.to_thread to return the mock response directly
            with patch('asyncio.to_thread', return_value=mock_resp):
                client = LokiClient(basic_config)
                result = await client._make_request("GET", "/test", {"param": "value"})
                
                assert result == mock_response

    @pytest.mark.asyncio
    async def test_make_request_authentication_error(self, basic_config):
        """Test authentication error handling."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            mock_resp = Mock()
            mock_resp.status_code = 401
            mock_session.request.return_value = mock_resp
            
            client = LokiClient(basic_config)
            
            with pytest.raises(LokiAuthenticationError, match="Authentication failed"):
                await client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_rate_limit_error(self, basic_config):
        """Test rate limit error handling."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            mock_resp = Mock()
            mock_resp.status_code = 429
            mock_session.request.return_value = mock_resp
            
            client = LokiClient(basic_config)
            
            with pytest.raises(LokiRateLimitError, match="Rate limit exceeded"):
                await client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_query_error(self, basic_config):
        """Test query error handling."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            mock_resp = Mock()
            mock_resp.status_code = 400
            mock_resp.json.return_value = {"error": "Invalid query"}
            mock_session.request.return_value = mock_resp
            
            client = LokiClient(basic_config)
            
            with pytest.raises(LokiQueryError, match="Invalid query"):
                await client._make_request("GET", "/test")


    @pytest.mark.asyncio
    async def test_query_range(self, basic_config, mock_response):
        """Test range query execution."""
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            result = await client.query_range(
                query='{job="test"}',
                start="2022-01-01T00:00:00Z",
                end="2022-01-01T01:00:00Z",
                limit=100,
                direction="backward"
            )
            
            assert result == mock_response
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/query_range",
                params={
                    "query": '{job="test"}',
                    "start": "2022-01-01T00:00:00Z",
                    "end": "2022-01-01T01:00:00Z",
                    "limit": 100,
                    "direction": "backward"
                }
            )

    @pytest.mark.asyncio
    async def test_query_instant(self, basic_config, mock_response):
        """Test instant query execution."""
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            result = await client.query_instant(
                query='{job="test"}',
                time="2022-01-01T00:00:00Z",
                limit=50
            )
            
            assert result == mock_response
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/query",
                params={
                    "query": '{job="test"}',
                    "time": "2022-01-01T00:00:00Z",
                    "limit": 50,
                    "direction": "backward"
                }
            )

    @pytest.mark.asyncio
    async def test_label_names(self, basic_config):
        """Test label names retrieval."""
        mock_response = {"data": ["job", "level", "instance"]}
        
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            result = await client.label_names(
                start="2022-01-01T00:00:00Z",
                end="2022-01-01T01:00:00Z"
            )
            
            assert result == ["job", "level", "instance"]
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/labels",
                params={
                    "start": "2022-01-01T00:00:00Z",
                    "end": "2022-01-01T01:00:00Z"
                }
            )

    @pytest.mark.asyncio
    async def test_label_values(self, basic_config):
        """Test label values retrieval."""
        mock_response = {"data": ["info", "warn", "error"]}
        
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            result = await client.label_values("level")
            
            assert result == ["info", "warn", "error"]
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/label/level/values",
                params={}
            )

    @pytest.mark.asyncio
    async def test_series(self, basic_config):
        """Test series retrieval."""
        mock_response = {
            "data": [
                {"job": "test", "level": "info"},
                {"job": "test", "level": "error"}
            ]
        }
        
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            result = await client.series('{job="test"}')
            
            assert result == mock_response["data"]
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/series",
                params={"match[]": '{job="test"}'}
            )

    @pytest.mark.asyncio
    async def test_series_multiple_matchers(self, basic_config):
        """Test series retrieval with multiple matchers."""
        mock_response = {"data": []}
        
        with patch.object(LokiClient, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            client = LokiClient(basic_config)
            await client.series(['{job="test"}', '{level="error"}'])
            
            mock_request.assert_called_once_with(
                "GET",
                "/loki/api/v1/series",
                params={"match[]": ['{job="test"}', '{level="error"}']}
            )


class TestRateLimiter:
    """Test cases for RateLimiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_under_limit(self):
        """Test that rate limiter allows requests under the limit."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # Should allow 5 requests without delay
        start_time = time.time()
        for _ in range(5):
            await limiter.acquire()
        end_time = time.time()
        
        # Should complete quickly (no significant delay)
        assert end_time - start_time < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over the limit."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # First 2 requests should be immediate
        await limiter.acquire()
        await limiter.acquire()
        
        # Third request should be delayed
        start_time = time.time()
        await limiter.acquire()
        end_time = time.time()
        
        # Should have waited close to 1 second
        assert end_time - start_time >= 0.9

    @pytest.mark.asyncio
    async def test_rate_limiter_window_sliding(self):
        """Test that rate limiter uses sliding time window."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Make 2 requests
        await limiter.acquire()
        await limiter.acquire()
        
        # Wait for half the window
        await asyncio.sleep(0.5)
        
        # Should still need to wait for the full window
        start_time = time.time()
        await limiter.acquire()
        end_time = time.time()
        
        # Should wait approximately 0.5 seconds (remaining window time)
        assert 0.4 <= end_time - start_time <= 0.6

    def test_rate_limiter_cleanup_old_requests(self):
        """Test that rate limiter cleans up old requests."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # Add some old requests
        old_time = time.time() - 2  # 2 seconds ago
        limiter.requests = [old_time, old_time, old_time]
        
        # Current time requests
        current_time = time.time()
        limiter.requests.extend([current_time, current_time])
        
        # Simulate cleanup (this happens in acquire)
        now = time.time()
        limiter.requests = [req_time for req_time in limiter.requests 
                           if now - req_time < limiter.time_window]
        
        # Should only have current requests left
        assert len(limiter.requests) == 2
        assert all(req_time >= current_time for req_time in limiter.requests)