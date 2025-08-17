"""Unit tests for query_logs tool."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.tools.query_logs import (
    QueryLogsParams,
    QueryLogsResult,
    query_logs_tool,
    _format_loki_response,
    create_query_logs_tool
)
from app.config import LokiConfig
from app.loki_client import LokiClientError


@pytest.fixture
def mock_config():
    """Create a mock Loki configuration."""
    return LokiConfig(
        url="http://localhost:3100",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def sample_loki_response():
    """Sample Loki API response."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "job": "test-app",
                        "level": "info"
                    },
                    "values": [
                        ["1640995200000000000", "This is a test log message"],
                        ["1640995100000000000", "Another test log message"]
                    ]
                }
            ]
        }
    }


class TestQueryLogsParams:
    """Test QueryLogsParams validation."""
    
    def test_valid_params(self):
        """Test valid parameter creation."""
        params = QueryLogsParams(
            query='{job="test"}',
            start="2023-01-01T00:00:00Z",
            end="2023-01-01T01:00:00Z",
            limit=50,
            direction="forward"
        )
        
        assert params.query == '{job="test"}'
        assert params.start == "2023-01-01T00:00:00Z"
        assert params.end == "2023-01-01T01:00:00Z"
        assert params.limit == 50
        assert params.direction == "forward"
    
    def test_default_values(self):
        """Test default parameter values."""
        params = QueryLogsParams(query='{job="test"}')
        
        assert params.query == '{job="test"}'
        assert params.start is None
        assert params.end is None
        assert params.limit == 100
        assert params.direction == "backward"
    
    def test_invalid_direction(self):
        """Test invalid direction validation."""
        with pytest.raises(ValueError, match="Direction must be"):
            QueryLogsParams(query='{job="test"}', direction="invalid")
    
    def test_empty_query(self):
        """Test empty query validation."""
        with pytest.raises(ValueError):
            QueryLogsParams(query="")
    
    def test_limit_bounds(self):
        """Test limit boundary validation."""
        # Valid limits
        QueryLogsParams(query='{job="test"}', limit=1)
        QueryLogsParams(query='{job="test"}', limit=5000)
        
        # Invalid limits
        with pytest.raises(ValueError):
            QueryLogsParams(query='{job="test"}', limit=0)
        
        with pytest.raises(ValueError):
            QueryLogsParams(query='{job="test"}', limit=5001)


class TestFormatLokiResponse:
    """Test Loki response formatting."""
    
    def test_format_streams_response(self, sample_loki_response):
        """Test formatting of streams response."""
        formatted = _format_loki_response(sample_loki_response)
        
        assert len(formatted) == 2
        
        # Check first entry (should be sorted by timestamp, newest first)
        entry = formatted[0]
        assert "timestamp" in entry
        assert "timestamp_ns" in entry
        assert "line" in entry
        assert "labels" in entry
        
        assert entry["timestamp_ns"] == "1640995200000000000"
        assert entry["line"] == "This is a test log message"
        assert entry["labels"]["job"] == "test-app"
        assert entry["labels"]["level"] == "info"
        
        # Verify timestamp conversion
        expected_time = datetime.fromtimestamp(
            1640995200, tz=timezone.utc
        ).isoformat()
        assert entry["timestamp"] == expected_time
    
    def test_format_empty_response(self):
        """Test formatting of empty response."""
        empty_response = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": []
            }
        }
        
        formatted = _format_loki_response(empty_response)
        assert formatted == []
    
    def test_format_malformed_response(self):
        """Test formatting of malformed response."""
        malformed_response = {}
        formatted = _format_loki_response(malformed_response)
        assert formatted == []
    
    def test_timestamp_sorting(self):
        """Test that entries are sorted by timestamp (newest first)."""
        response = {
            "data": {
                "result": [
                    {
                        "stream": {"job": "test"},
                        "values": [
                            ["1640995100000000000", "Older message"],
                            ["1640995200000000000", "Newer message"],
                            ["1640995150000000000", "Middle message"]
                        ]
                    }
                ]
            }
        }
        
        formatted = _format_loki_response(response)
        
        assert len(formatted) == 3
        assert formatted[0]["line"] == "Newer message"
        assert formatted[1]["line"] == "Middle message"
        assert formatted[2]["line"] == "Older message"


@pytest.mark.asyncio
class TestQueryLogsTool:
    """Test query_logs_tool function."""
    
    async def test_successful_range_query(self, mock_config, sample_loki_response):
        """Test successful range query execution."""
        params = QueryLogsParams(
            query='{job="test"}',
            start="1h",
            end="now",
            limit=100
        )
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_range.return_value = sample_loki_response
            
            result = await query_logs_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.result_type == "streams"
            assert result.total_entries == 2
            assert result.query == '{job="test"}'
            assert result.time_range["start"] == "1h"
            assert result.time_range["end"] == "now"
            assert result.error is None
            
            # Verify client was called correctly with converted times
            mock_client.query_range.assert_called_once()
            call_args = mock_client.query_range.call_args
            assert call_args[1]["query"] == '{job="test"}'
            assert call_args[1]["start"].endswith('Z')  # Should be RFC3339 format
            assert call_args[1]["end"].endswith('Z')    # Should be RFC3339 format
            assert call_args[1]["limit"] == 100
            assert call_args[1]["direction"] == "backward"
    
    async def test_successful_query_without_time_range(self, mock_config, sample_loki_response):
        """Test successful query execution without explicit time range."""
        params = QueryLogsParams(query='{job="test"}')
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_range.return_value = sample_loki_response
            
            result = await query_logs_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.total_entries == 2
            
            # Verify range query was called with default time range
            mock_client.query_range.assert_called_once()
            call_args = mock_client.query_range.call_args
            assert call_args[1]["query"] == '{job="test"}'
            assert call_args[1]["start"].endswith('Z')  # Should be RFC3339 format
            assert call_args[1]["end"].endswith('Z')    # Should be RFC3339 format
    
    async def test_loki_client_error(self, mock_config):
        """Test handling of Loki client errors."""
        params = QueryLogsParams(query='{job="test"}')
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_range.side_effect = LokiClientError("Connection failed")
            
            result = await query_logs_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.total_entries == 0
            assert result.error == "Connection failed"
    
    async def test_unexpected_error(self, mock_config):
        """Test handling of unexpected errors."""
        params = QueryLogsParams(query='{job="test"}')
        
        with patch('app.tools.query_logs.EnhancedLokiClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")
            
            result = await query_logs_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.total_entries == 0
            assert "Unexpected error" in result.error


class TestCreateQueryLogsTool:
    """Test MCP tool creation."""
    
    def test_tool_creation(self):
        """Test that tool is created with correct schema."""
        tool = create_query_logs_tool()
        
        assert tool.name == "query_logs"
        assert "LogQL" in tool.description
        
        # Check schema structure
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "start" in schema["properties"]
        assert "end" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "direction" in schema["properties"]
        
        # Check required fields
        assert schema["required"] == ["query"]
        
        # Check query field
        query_field = schema["properties"]["query"]
        assert query_field["type"] == "string"
        assert query_field["minLength"] == 1
        
        # Check limit field
        limit_field = schema["properties"]["limit"]
        assert limit_field["type"] == "integer"
        assert limit_field["minimum"] == 1
        assert limit_field["maximum"] == 5000
        assert limit_field["default"] == 100
        
        # Check direction field
        direction_field = schema["properties"]["direction"]
        assert direction_field["type"] == "string"
        assert direction_field["enum"] == ["forward", "backward"]
        assert direction_field["default"] == "backward"