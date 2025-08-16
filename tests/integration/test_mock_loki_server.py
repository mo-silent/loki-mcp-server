"""Integration tests with mock Loki server."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
import pytest

from app.config import LokiConfig
from app.loki_client import LokiClient, LokiConnectionError, LokiQueryError
from ..fixtures.sample_logs import (
    SAMPLE_QUERY_RANGE_RESPONSE,
    SAMPLE_QUERY_INSTANT_RESPONSE,
    SAMPLE_LABELS_RESPONSE,
    SAMPLE_LABEL_VALUES_RESPONSE,
    SAMPLE_ERROR_RESPONSES,
    generate_large_log_dataset
)
from ..utils.mcp_client import MockLokiServer, create_mock_loki_responses


class TestMockLokiServerIntegration:
    """Test integration with mock Loki server."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=2
        )
    
    @pytest.fixture
    def mock_server(self):
        """Mock Loki server fixture."""
        return MockLokiServer(port=3100)
    
    @pytest.mark.asyncio
    async def test_successful_query_range(self, config, mock_server):
        """Test successful range query with mock server."""
        # Setup mock response
        mock_server.set_response(
            "/loki/api/v1/query_range",
            "GET",
            SAMPLE_QUERY_RANGE_RESPONSE
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            async with LokiClient(config) as client:
                result = await client.query_range(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z"
                )
                
                assert result["status"] == "success"
                assert result["data"]["resultType"] == "streams"
                assert len(result["data"]["result"]) == 2
                
                # Verify request was made with correct parameters
                mock_request.assert_called_once_with(
                    "GET",
                    "/loki/api/v1/query_range",
                    params={
                        "query": '{job="web-server"}',
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T01:00:00Z",
                        "direction": "backward"
                    }
                )
    
    @pytest.mark.asyncio
    async def test_successful_query_instant(self, config, mock_server):
        """Test successful instant query with mock server."""
        mock_server.set_response(
            "/loki/api/v1/query",
            "GET",
            SAMPLE_QUERY_INSTANT_RESPONSE
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_INSTANT_RESPONSE
            
            async with LokiClient(config) as client:
                result = await client.query_instant(
                    query='{job="web-server"} |= "error"',
                    limit=50
                )
                
                assert result["status"] == "success"
                assert result["data"]["resultType"] == "streams"
                assert len(result["data"]["result"]) == 1
                
                mock_request.assert_called_once_with(
                    "GET",
                    "/loki/api/v1/query",
                    params={
                        "query": '{job="web-server"} |= "error"',
                        "limit": 50,
                        "direction": "backward"
                    }
                )
    
    @pytest.mark.asyncio
    async def test_successful_label_names(self, config, mock_server):
        """Test successful label names retrieval."""
        mock_server.set_response(
            "/loki/api/v1/labels",
            "GET",
            SAMPLE_LABELS_RESPONSE
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            async with LokiClient(config) as client:
                result = await client.label_names()
                
                assert result == ["job", "level", "instance", "__name__"]
                
                mock_request.assert_called_once_with(
                    "GET",
                    "/loki/api/v1/labels",
                    params={}
                )
    
    @pytest.mark.asyncio
    async def test_successful_label_values(self, config, mock_server):
        """Test successful label values retrieval."""
        mock_server.set_response(
            "/loki/api/v1/label/level/values",
            "GET",
            SAMPLE_LABEL_VALUES_RESPONSE
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABEL_VALUES_RESPONSE
            
            async with LokiClient(config) as client:
                result = await client.label_values("level")
                
                assert result == ["info", "warn", "error", "debug"]
                
                mock_request.assert_called_once_with(
                    "GET",
                    "/loki/api/v1/label/level/values",
                    params={}
                )
    
    @pytest.mark.asyncio
    async def test_query_error_handling(self, config, mock_server):
        """Test query error handling."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = LokiQueryError("Invalid query syntax")
            
            async with LokiClient(config) as client:
                with pytest.raises(LokiQueryError, match="Invalid query syntax"):
                    await client.query_range(
                        query='{job="web-server"!}',  # Invalid syntax
                        start="2024-01-01T00:00:00Z",
                        end="2024-01-01T01:00:00Z"
                    )
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, config, mock_server):
        """Test connection error handling."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = LokiConnectionError("Connection refused")
            
            async with LokiClient(config) as client:
                with pytest.raises(LokiConnectionError, match="Connection refused"):
                    await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, config, mock_server):
        """Test that connection errors are properly raised (retry not implemented yet)."""
        with patch('asyncio.to_thread') as mock_to_thread:
            # Simulate connection error
            import requests
            mock_to_thread.side_effect = requests.exceptions.ConnectionError("Temporary failure")
            
            async with LokiClient(config) as client:
                # This should fail with connection error
                with pytest.raises(LokiConnectionError, match="Temporary failure"):
                    await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, config):
        """Test rate limiting functionality."""
        # Set very low rate limits for testing
        config.rate_limit_requests = 2
        config.rate_limit_period = 1
        
        # Mock the actual HTTP request, not the _make_request method
        # This way the rate limiter still works
        with patch('asyncio.to_thread') as mock_to_thread:
            # Create a mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = SAMPLE_QUERY_INSTANT_RESPONSE
            mock_to_thread.return_value = mock_response
            
            async with LokiClient(config) as client:
                # First two requests should be immediate
                start_time = asyncio.get_event_loop().time()
                
                await client.query_instant(query='{job="test1"}')
                await client.query_instant(query='{job="test2"}')
                
                # Third request should be rate limited
                await client.query_instant(query='{job="test3"}')
                
                end_time = asyncio.get_event_loop().time()
                
                # Should have taken at least 1 second due to rate limiting
                assert end_time - start_time >= 0.9
                assert mock_to_thread.call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, config, mock_server):
        """Test handling of concurrent requests."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_INSTANT_RESPONSE
            
            async with LokiClient(config) as client:
                # Make 5 concurrent requests
                tasks = []
                for i in range(5):
                    task = client.query_instant(query=f'{{job="test{i}"}}')
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                
                # All requests should succeed
                for result in results:
                    assert result["status"] == "success"
                
                assert mock_request.call_count == 5
    
    @pytest.mark.asyncio
    async def test_large_response_handling(self, config, mock_server):
        """Test handling of large responses."""
        large_response = generate_large_log_dataset(1000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = large_response
            
            async with LokiClient(config) as client:
                result = await client.query_range(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z",
                    limit=1000
                )
                
                assert result["status"] == "success"
                assert result["data"]["resultType"] == "streams"
                
                # Should have multiple streams
                assert len(result["data"]["result"]) > 1
                
                # Count total entries across all streams
                total_entries = sum(
                    len(stream["values"]) 
                    for stream in result["data"]["result"]
                )
                assert total_entries == 1000
    
    @pytest.mark.asyncio
    async def test_authentication_scenarios(self, mock_server):
        """Test different authentication scenarios."""
        # Test basic auth
        basic_auth_config = LokiConfig(
            url="http://localhost:3100",
            username="admin",
            password="secret"
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            async with LokiClient(basic_auth_config) as client:
                await client.label_names()
                # Verify session was configured with basic auth
                assert client._session.auth is not None
        
        # Test bearer token auth
        bearer_config = LokiConfig(
            url="http://localhost:3100",
            bearer_token="test-token-123"
        )
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            async with LokiClient(bearer_config) as client:
                await client.label_names()
                # Verify session was configured with bearer token
                assert "Authorization" in client._session.headers
                assert client._session.headers["Authorization"] == "Bearer test-token-123"
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, config):
        """Test timeout handling."""
        # Set short timeout for testing
        config.timeout = 0.1
        
        # Mock the actual HTTP request to simulate timeout
        with patch('asyncio.to_thread') as mock_to_thread:
            # Simulate a timeout exception
            import requests
            mock_to_thread.side_effect = requests.exceptions.Timeout("Request timed out")
            
            async with LokiClient(config) as client:
                with pytest.raises(LokiConnectionError, match="timed out"):
                    await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self, config, mock_server):
        """Test handling of empty responses."""
        empty_response = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": []
            }
        }
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = empty_response
            
            async with LokiClient(config) as client:
                result = await client.query_range(
                    query='{job="nonexistent"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z"
                )
                
                assert result["status"] == "success"
                assert result["data"]["result"] == []
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, config, mock_server):
        """Test handling of malformed responses."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            # Return malformed response
            mock_request.return_value = {"invalid": "response"}
            
            async with LokiClient(config) as client:
                result = await client.query_instant(query='{job="web-server"}')
                
                # Should still return the response even if malformed
                assert result == {"invalid": "response"}