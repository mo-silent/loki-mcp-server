"""Simple integration tests that work with the current implementation."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from app.config import LokiConfig
from app.server import LokiMCPServer
from ..fixtures.sample_logs import (
    SAMPLE_QUERY_RANGE_RESPONSE,
    SAMPLE_QUERY_INSTANT_RESPONSE,
    SAMPLE_LABELS_RESPONSE,
    SAMPLE_LABEL_VALUES_RESPONSE,
    TIME_RANGES
)


class TestSimpleIntegration:
    """Simple integration tests."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=2
        )
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, config):
        """Test server initialization."""
        server = LokiMCPServer(config)
        
        assert server.config == config
        assert server.server is not None
        assert server.server.name == "loki-mcp-server"
    
    @pytest.mark.asyncio
    async def test_query_logs_handler_direct(self, config):
        """Test query_logs handler directly."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Test the handler directly
            result = await server._handle_query_logs({
                "query": '{job="web-server"}',
                "start": TIME_RANGES["last_hour"]["start"],
                "end": TIME_RANGES["last_hour"]["end"],
                "limit": 100
            })
            
            assert result.status == "success"
            assert result.total_entries > 0
            assert len(result.entries) > 0
            
            # Verify the mock was called
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_logs_handler_direct(self, config):
        """Test search_logs handler directly."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Test the handler directly
            result = await server._handle_search_logs({
                "keywords": ["error", "failed"],
                "start": TIME_RANGES["last_hour"]["start"],
                "end": TIME_RANGES["last_hour"]["end"],
                "limit": 50
            })
            
            assert result.status == "success"
            assert result.total_entries > 0
            assert len(result.entries) > 0
            
            # Verify the mock was called
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_labels_handler_direct(self, config):
        """Test get_labels handler directly."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABELS_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Test the handler directly
            result = await server._handle_get_labels({})
            
            assert result.status == "success"
            assert result.total_count > 0
            assert len(result.labels) > 0
            assert "job" in result.labels
            
            # Verify the mock was called
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_label_values_handler_direct(self, config):
        """Test get_labels handler with label_name directly."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_LABEL_VALUES_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Test the handler directly
            result = await server._handle_get_labels({"label_name": "level"})
            
            assert result.status == "success"
            assert result.total_count > 0
            assert len(result.labels) > 0
            assert "error" in result.labels
            
            # Verify the mock was called
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_handlers(self, config):
        """Test error handling in handlers."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.side_effect = Exception("Connection failed")
            
            server = LokiMCPServer(config)
            
            # Test query_logs error handling
            result = await server._handle_query_logs({
                "query": '{job="web-server"}'
            })
            
            assert result.status == "error"
            assert "Connection failed" in result.error
    
    @pytest.mark.asyncio
    async def test_parameter_validation_in_handlers(self, config):
        """Test parameter validation in handlers."""
        server = LokiMCPServer(config)
        
        # Test missing required parameters
        with pytest.raises(Exception):  # Should raise ValidationError
            await server._handle_query_logs({})
        
        # Test invalid parameter types
        with pytest.raises(Exception):  # Should raise ValidationError
            await server._handle_query_logs({"query": 123})
    
    @pytest.mark.asyncio
    async def test_result_formatting(self, config):
        """Test result formatting."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Get a result from the handler
            result = await server._handle_query_logs({
                "query": '{job="web-server"}',
                "start": TIME_RANGES["last_hour"]["start"],
                "end": TIME_RANGES["last_hour"]["end"]
            })
            
            # Test formatting
            formatted = server._format_tool_result(result)
            
            assert isinstance(formatted, str)
            assert len(formatted) > 0
            assert "Found" in formatted
            assert "log entries" in formatted
    
    @pytest.mark.asyncio
    async def test_empty_results_formatting(self, config):
        """Test formatting of empty results."""
        empty_response = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": []
            }
        }
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = empty_response
            
            server = LokiMCPServer(config)
            
            # Get empty result
            result = await server._handle_query_logs({
                "query": '{job="nonexistent"}',
                "start": TIME_RANGES["last_hour"]["start"],
                "end": TIME_RANGES["last_hour"]["end"]
            })
            
            # Test formatting
            formatted = server._format_tool_result(result)
            
            assert isinstance(formatted, str)
            assert "No log entries found matching the criteria" in formatted
    
    @pytest.mark.asyncio
    async def test_concurrent_handler_calls(self, config):
        """Test concurrent handler calls."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            # Make concurrent calls
            tasks = []
            for i in range(5):
                task = server._handle_query_logs({
                    "query": f'{{job="service-{i}"}}',
                    "start": TIME_RANGES["last_hour"]["start"],
                    "end": TIME_RANGES["last_hour"]["end"]
                })
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            # All should succeed
            for result in results:
                assert result.status == "success"
                assert result.total_entries > 0
            
            # Should have made 5 calls
            assert mock_request.call_count == 5
    
    @pytest.mark.asyncio
    async def test_large_response_handling(self, config):
        """Test handling of large responses."""
        from ..fixtures.sample_logs import generate_large_log_dataset
        
        large_response = generate_large_log_dataset(1000)
        
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = large_response
            
            server = LokiMCPServer(config)
            
            # Handle large response
            result = await server._handle_query_logs({
                "query": '{job="web-server"}',
                "start": TIME_RANGES["last_day"]["start"],
                "end": TIME_RANGES["last_day"]["end"],
                "limit": 1000
            })
            
            assert result.status == "success"
            assert result.total_entries == 1000
            
            # Test formatting (should truncate for display)
            formatted = server._format_tool_result(result)
            assert "Found 1000 log entries" in formatted
            assert "... and 990 more entries" in formatted
    
    @pytest.mark.asyncio
    async def test_different_time_ranges(self, config):
        """Test different time range formats."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            time_formats = [
                ("2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"),  # RFC3339
                ("1704067200", "1704070800"),  # Unix timestamp
                ("now-1h", "now"),  # Relative time
            ]
            
            for start, end in time_formats:
                result = await server._handle_query_logs({
                    "query": '{job="web-server"}',
                    "start": start,
                    "end": end
                })
                
                assert result.status == "success"
                assert result.total_entries > 0
    
    @pytest.mark.asyncio
    async def test_different_query_types(self, config):
        """Test different LogQL query types."""
        with patch('app.loki_client.LokiClient._make_request') as mock_request:
            mock_request.return_value = SAMPLE_QUERY_RANGE_RESPONSE
            
            server = LokiMCPServer(config)
            
            queries = [
                '{job="web-server"}',  # Basic label selector
                '{job="web-server"} |= "error"',  # Line filter
                '{job="web-server"} |~ "user.*failed"',  # Regex filter
                'rate({job="web-server"}[5m])',  # Metric query
                'count_over_time({job="web-server"}[1h])',  # Aggregation
            ]
            
            for query in queries:
                result = await server._handle_query_logs({
                    "query": query,
                    "start": TIME_RANGES["last_hour"]["start"],
                    "end": TIME_RANGES["last_hour"]["end"]
                })
                
                assert result.status == "success"
                assert result.total_entries >= 0  # Some queries might return 0 results