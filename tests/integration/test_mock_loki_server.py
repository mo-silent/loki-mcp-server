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
        mock_server.set_response(
            "/loki/api/v1/query_range",
            "GET",
            SAMPLE_QUERY_RANGE_RESPONSE
        )
        
        mock_request = AsyncMock(return_value=SAMPLE_QUERY_RANGE_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(config) as client:
                result = await client.query_range(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z"
                )
                
                assert result["status"] == "success"
                assert result["data"]["resultType"] == "streams"
                assert len(result["data"]["result"]) == 2
                
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
        
        mock_request = AsyncMock(return_value=SAMPLE_QUERY_INSTANT_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
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
        
        mock_request = AsyncMock(return_value=SAMPLE_LABELS_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
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
        
        mock_request = AsyncMock(return_value=SAMPLE_LABEL_VALUES_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
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
        async with LokiClient(config) as client:
            # Create an explicit async mock that doesn't use AsyncMock internally
            async def mock_make_request(*args, **kwargs):
                raise LokiQueryError("Invalid query syntax")
            
            client._make_request = mock_make_request
            with pytest.raises(LokiQueryError, match="Invalid query syntax"):
                await client.query_range(
                    query='{job="web-server"!}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z"
                )
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, config, mock_server):
        """Test connection error handling."""
        async with LokiClient(config) as client:
            # Create an explicit async mock that doesn't use AsyncMock internally
            async def mock_make_request(*args, **kwargs):
                raise LokiConnectionError("Connection refused")
            
            client._make_request = mock_make_request
            with pytest.raises(LokiConnectionError, match="Connection refused"):
                await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, config, mock_server):
        """Test that connection errors are properly raised (retry not implemented yet)."""
        import requests
        with patch('asyncio.to_thread', side_effect=requests.exceptions.ConnectionError("Temporary failure")) as mock_to_thread:
            
            async with LokiClient(config) as client:
                with pytest.raises(LokiConnectionError, match="Temporary failure"):
                    await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, config):
        """Test rate limiting functionality."""
        config.rate_limit_requests = 2
        config.rate_limit_period = 1
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_QUERY_INSTANT_RESPONSE
        with patch('asyncio.to_thread', return_value=mock_response) as mock_to_thread:
            async with LokiClient(config) as client:
                start_time = asyncio.get_event_loop().time()
                
                await client.query_instant(query='{job="test1"}')
                await client.query_instant(query='{job="test2"}')
                await client.query_instant(query='{job="test3"}')
                
                end_time = asyncio.get_event_loop().time()
                
                assert end_time - start_time >= 0.9
                assert mock_to_thread.call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, config, mock_server):
        """Test handling of concurrent requests."""
        mock_request = AsyncMock(return_value=SAMPLE_QUERY_INSTANT_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(config) as client:
                tasks = [client.query_instant(query=f'{{job="test{i}"}}') for i in range(5)]
                results = await asyncio.gather(*tasks)
                
                for result in results:
                    assert result["status"] == "success"
                
                assert mock_request.call_count == 5
    
    @pytest.mark.asyncio
    async def test_large_response_handling(self, config, mock_server):
        """Test handling of large responses."""
        large_response = generate_large_log_dataset(1000)
        
        mock_request = AsyncMock(return_value=large_response)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(config) as client:
                result = await client.query_range(
                    query='{job="web-server"}',
                    start="2024-01-01T00:00:00Z",
                    end="2024-01-01T01:00:00Z",
                    limit=1000
                )
                
                assert result["status"] == "success"
                assert result["data"]["resultType"] == "streams"
                assert len(result["data"]["result"]) > 1
                total_entries = sum(len(stream["values"]) for stream in result["data"]["result"])
                assert total_entries == 1000
    
    @pytest.mark.asyncio
    async def test_authentication_scenarios(self, mock_server):
        """Test different authentication scenarios."""
        basic_auth_config = LokiConfig(
            url="http://localhost:3100",
            username="admin",
            password="secret"
        )
        
        mock_request = AsyncMock(return_value=SAMPLE_LABELS_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(basic_auth_config) as client:
                await client.label_names()
                assert client._session.auth is not None
        
        bearer_config = LokiConfig(
            url="http://localhost:3100",
            bearer_token="test-token-123"
        )
        
        mock_request = AsyncMock(return_value=SAMPLE_LABELS_RESPONSE)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(bearer_config) as client:
                await client.label_names()
                assert "Authorization" in client._session.headers
                assert client._session.headers["Authorization"] == "Bearer test-token-123"
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, config):
        """Test timeout handling."""
        config.timeout = 0.1
        
        import requests
        with patch('asyncio.to_thread', side_effect=requests.exceptions.Timeout("Request timed out")):
            
            async with LokiClient(config) as client:
                with pytest.raises(LokiConnectionError, match="timed out"):
                    await client.query_instant(query='{job="web-server"}')
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self, config, mock_server):
        """Test handling of empty responses."""
        empty_response = {
            "status": "success",
            "data": {"resultType": "streams", "result": []}
        }
        
        mock_request = AsyncMock(return_value=empty_response)
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
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
        mock_request = AsyncMock(return_value={"invalid": "response"})
        with patch('app.loki_client.LokiClient._make_request', mock_request):
            
            async with LokiClient(config) as client:
                result = await client.query_instant(query='{job="web-server"}')
                assert result == {"invalid": "response"}
