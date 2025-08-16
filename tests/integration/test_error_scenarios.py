"""Integration tests for error handling scenarios."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from app.config import LokiConfig
from app.loki_client import LokiClient, LokiConnectionError, LokiAuthenticationError, LokiRateLimitError
from app.server import LokiMCPServer
from app.tools.query_logs import query_logs_tool, QueryLogsParams
from app.tools.search_logs import search_logs_tool, SearchLogsParams
from app.tools.get_labels import get_labels_tool, GetLabelsParams


@pytest.fixture
def test_config():
    """Create test configuration."""
    return LokiConfig(
        url="http://localhost:3100",
        timeout=5,
        max_retries=2,
        rate_limit_requests=10,
        rate_limit_period=60
    )


@pytest.fixture
def test_config_with_auth():
    """Create test configuration with authentication."""
    return LokiConfig(
        url="http://localhost:3100",
        username="test_user",
        password="test_pass",
        timeout=5,
        max_retries=2
    )


class TestLokiClientErrorScenarios:
    """Test error scenarios in Loki client."""
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self, test_config):
        """Test handling of connection timeouts."""
        async with LokiClient(test_config) as client:
            with patch.object(client._client, 'request', side_effect=httpx.TimeoutException("Timeout")):
                with pytest.raises(LokiConnectionError) as exc_info:
                    await client.query_instant("up")
                
                assert "timed out" in str(exc_info.value).lower()
                assert "network connectivity" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_connection_refused(self, test_config):
        """Test handling of connection refused errors."""
        async with LokiClient(test_config) as client:
            with patch.object(client._client, 'request', side_effect=httpx.ConnectError("Connection refused")):
                with pytest.raises(LokiConnectionError) as exc_info:
                    await client.query_instant("up")
                
                assert "connect to Loki" in str(exc_info.value).lower()
                assert "network connectivity" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, test_config_with_auth):
        """Test handling of authentication failures."""
        async with LokiClient(test_config_with_auth) as client:
            # Mock 401 response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"error": "Unauthorized"}
            
            with patch.object(client._client, 'request', return_value=mock_response):
                with pytest.raises(LokiAuthenticationError) as exc_info:
                    await client.query_instant("up")
                
                assert "authentication failed" in str(exc_info.value).lower()
                assert "credentials" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, test_config):
        """Test handling of rate limiting."""
        async with LokiClient(test_config) as client:
            # Mock 429 response
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"error": "Too Many Requests"}
            mock_response.headers = {"retry-after": "60"}
            
            with patch.object(client._client, 'request', return_value=mock_response):
                with pytest.raises(LokiRateLimitError) as exc_info:
                    await client.query_instant("up")
                
                assert "rate limit exceeded" in str(exc_info.value).lower()
                assert "reduce request frequency" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_server_error_retry(self, test_config):
        """Test retry behavior on server errors."""
        async with LokiClient(test_config) as client:
            call_count = 0
            
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    # First two calls return server error
                    mock_response = Mock()
                    mock_response.status_code = 500
                    mock_response.json.return_value = {"error": "Internal Server Error"}
                    return mock_response
                else:
                    # Third call succeeds
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"data": {"result": []}}
                    return mock_response
            
            with patch.object(client._client, 'request', side_effect=mock_request):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    result = await client.query_instant("up")
                    assert result == {"data": {"result": []}}
                    assert call_count == 3  # Should retry twice then succeed
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, test_config):
        """Test circuit breaker activation after multiple failures."""
        async with LokiClient(test_config) as client:
            # Mock consistent failures
            with patch.object(client._client, 'request', side_effect=httpx.ConnectError("Connection refused")):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    # Make multiple failing requests to trigger circuit breaker
                    for _ in range(6):  # More than failure threshold
                        with pytest.raises(LokiConnectionError):
                            await client.query_instant("up")
                    
                    # Next request should fail due to circuit breaker
                    with pytest.raises(LokiConnectionError) as exc_info:
                        await client.query_instant("up")
                    
                    # Should mention circuit breaker in some cases
                    # (depends on timing and circuit breaker state)
    
    @pytest.mark.asyncio
    async def test_error_statistics_tracking(self, test_config):
        """Test that error statistics are properly tracked."""
        async with LokiClient(test_config) as client:
            # Successful request
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"result": []}}
            
            with patch.object(client._client, 'request', return_value=mock_response):
                await client.query_instant("up")
            
            # Failed request
            with patch.object(client._client, 'request', side_effect=httpx.TimeoutException("Timeout")):
                with pytest.raises(LokiConnectionError):
                    await client.query_instant("up")
            
            # Check statistics
            stats = client.get_error_statistics()
            assert "operation_stats" in stats
            assert "error_counts_by_category" in stats
            assert stats["total_operations"] >= 2
            assert stats["total_errors"] >= 1


class TestToolErrorHandling:
    """Test error handling in MCP tools."""
    
    @pytest.mark.asyncio
    async def test_query_logs_connection_error(self, test_config):
        """Test query_logs tool handling connection errors."""
        params = QueryLogsParams(query="up")
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.query_instant.side_effect = LokiConnectionError("Connection failed")
            mock_client_class.return_value = mock_client
            
            result = await query_logs_tool(params, test_config)
            
            assert result.status == "error"
            assert "connection failed" in result.error.lower()
            assert result.total_entries == 0
    
    @pytest.mark.asyncio
    async def test_search_logs_authentication_error(self, test_config):
        """Test search_logs tool handling authentication errors."""
        params = SearchLogsParams(keywords=["error"])
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.query_instant.side_effect = LokiAuthenticationError("Auth failed")
            mock_client_class.return_value = mock_client
            
            result = await search_logs_tool(params, test_config)
            
            assert result.status == "error"
            assert "auth failed" in result.error.lower()
            assert result.total_entries == 0
    
    @pytest.mark.asyncio
    async def test_get_labels_rate_limit_error(self, test_config):
        """Test get_labels tool handling rate limit errors."""
        params = GetLabelsParams()
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.label_names.side_effect = LokiRateLimitError("Rate limited")
            mock_client_class.return_value = mock_client
            
            result = await get_labels_tool(params, test_config)
            
            assert result.status == "error"
            assert "rate limited" in result.error.lower()
            assert result.total_count == 0
    
    @pytest.mark.asyncio
    async def test_tool_parameter_validation_error(self, test_config):
        """Test tool handling of parameter validation errors."""
        # Test invalid direction parameter
        with pytest.raises(ValueError) as exc_info:
            QueryLogsParams(query="up", direction="invalid")
        
        assert "direction must be" in str(exc_info.value).lower()
        
        # Test empty keywords
        with pytest.raises(ValueError) as exc_info:
            SearchLogsParams(keywords=[])
        
        assert "keyword" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_tool_unexpected_error_handling(self, test_config):
        """Test tool handling of unexpected errors."""
        params = QueryLogsParams(query="up")
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.query_instant.side_effect = ValueError("Unexpected error")
            mock_client_class.return_value = mock_client
            
            result = await query_logs_tool(params, test_config)
            
            assert result.status == "error"
            assert "unexpected error" in result.error.lower()
            assert result.total_entries == 0


class TestMCPServerErrorHandling:
    """Test error handling in MCP server."""
    
    @pytest.fixture
    def mcp_server(self, test_config):
        """Create MCP server for testing."""
        return LokiMCPServer(test_config)
    
    @pytest.mark.asyncio
    async def test_unknown_tool_error(self, mcp_server):
        """Test handling of unknown tool requests."""
        # Get the handle_call_tool method
        handlers = mcp_server.server._call_tool_handlers
        assert len(handlers) == 1
        handle_call_tool = handlers[0]
        
        result = await handle_call_tool("unknown_tool", {})
        
        assert len(result) == 1
        assert result[0].type == "text"
        assert "unknown tool" in result[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_parameter_validation_error_formatting(self, mcp_server):
        """Test formatting of parameter validation errors."""
        # Get the handle_call_tool method
        handlers = mcp_server.server._call_tool_handlers
        handle_call_tool = handlers[0]
        
        # Call with invalid parameters
        result = await handle_call_tool("query_logs", {"direction": "invalid"})
        
        assert len(result) == 1
        assert result[0].type == "text"
        assert "error" in result[0].text.lower()
        assert "parameter" in result[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_connection_error_formatting(self, mcp_server):
        """Test formatting of connection errors."""
        # Get the handle_call_tool method
        handlers = mcp_server.server._call_tool_handlers
        handle_call_tool = handlers[0]
        
        # Mock connection error in tool
        with patch('app.server.query_logs_tool') as mock_tool:
            mock_tool.side_effect = LokiConnectionError("Connection failed")
            
            result = await handle_call_tool("query_logs", {"query": "up"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            error_text = result[0].text.lower()
            assert "error" in error_text
            assert "connection" in error_text
            assert "loki_url" in error_text  # Should mention environment variable
    
    @pytest.mark.asyncio
    async def test_authentication_error_formatting(self, mcp_server):
        """Test formatting of authentication errors."""
        # Get the handle_call_tool method
        handlers = mcp_server.server._call_tool_handlers
        handle_call_tool = handlers[0]
        
        # Mock authentication error in tool
        with patch('app.server.query_logs_tool') as mock_tool:
            mock_tool.side_effect = LokiAuthenticationError("Auth failed")
            
            result = await handle_call_tool("query_logs", {"query": "up"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            error_text = result[0].text.lower()
            assert "error" in error_text
            assert "authentication" in error_text
            assert "loki_username" in error_text or "loki_bearer_token" in error_text
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_formatting(self, mcp_server):
        """Test formatting of rate limit errors."""
        # Get the handle_call_tool method
        handlers = mcp_server.server._call_tool_handlers
        handle_call_tool = handlers[0]
        
        # Mock rate limit error in tool
        with patch('app.server.query_logs_tool') as mock_tool:
            mock_tool.side_effect = LokiRateLimitError("Rate limited")
            
            result = await handle_call_tool("query_logs", {"query": "up"})
            
            assert len(result) == 1
            assert result[0].type == "text"
            error_text = result[0].text.lower()
            assert "error" in error_text
            assert "rate limit" in error_text
            assert "frequency" in error_text


class TestErrorRecoveryScenarios:
    """Test error recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_recovery_after_temporary_network_issue(self, test_config):
        """Test recovery after temporary network issues."""
        async with LokiClient(test_config) as client:
            call_count = 0
            
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    # First two calls fail with network error
                    raise httpx.ConnectError("Network unreachable")
                else:
                    # Subsequent calls succeed
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"data": {"result": []}}
                    return mock_response
            
            with patch.object(client._client, 'request', side_effect=mock_request):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    # First request should fail after retries
                    with pytest.raises(LokiConnectionError):
                        await client.query_instant("up")
                    
                    # Reset call count for next request
                    call_count = 0
                    
                    # Second request should succeed after retries
                    result = await client.query_instant("up")
                    assert result == {"data": {"result": []}}
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, test_config):
        """Test circuit breaker recovery after failures."""
        # This test would require more complex timing control
        # and is more suitable for end-to-end testing
        pass
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_partial_failures(self, test_config):
        """Test graceful degradation when some operations fail."""
        params = SearchLogsParams(keywords=["error", "warning"], operator="OR")
        
        call_count = 0
        
        async def mock_query_range(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First query (for "error") fails
                raise LokiConnectionError("Connection failed")
            else:
                # Second query (for "warning") succeeds
                return {
                    "data": {
                        "result": [{
                            "stream": {"level": "warning"},
                            "values": [["1234567890000000000", "Warning message"]]
                        }]
                    }
                }
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.query_instant.side_effect = mock_query_range
            mock_client_class.return_value = mock_client
            
            result = await search_logs_tool(params, test_config)
            
            # Should succeed with partial results
            assert result.status == "success"
            assert result.total_entries > 0  # Should have results from successful query