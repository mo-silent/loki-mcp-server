"""Integration tests for MCP protocol compliance."""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from mcp import types

from app.config import LokiConfig
from app.server import LokiMCPServer


class TestMCPProtocolCompliance:
    """Test MCP protocol compliance."""
    
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear label cache before each test."""
        from app.tools.get_labels import clear_label_cache
        clear_label_cache()
    
    @pytest.fixture
    def mock_config(self) -> LokiConfig:
        """Create a mock Loki configuration for testing."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=3
        )
    
    @pytest.fixture
    def server(self, mock_config: LokiConfig) -> LokiMCPServer:
        """Create a test server instance."""
        return LokiMCPServer(mock_config)
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, server: LokiMCPServer):
        """Test that server initializes correctly."""
        assert server.config.url == "http://localhost:3100"
        assert server.server is not None
        assert server.server.name == "loki-mcp-server"
    
    @pytest.mark.asyncio
    async def test_list_tools_functionality(self, server: LokiMCPServer):
        """Test that tools can be listed through the server."""
        # Test that the server has the list_tools handler registered
        assert hasattr(server.server, 'list_tools')
        
        # We can't easily test the handler directly without setting up the full MCP protocol,
        # but we can verify that our tools are properly defined
        from app.tools.query_logs import create_query_logs_tool
        from app.tools.search_logs import create_search_logs_tool
        from app.tools.get_labels import create_get_labels_tool
        
        # Test tool creation
        query_tool = create_query_logs_tool()
        search_tool = create_search_logs_tool()
        labels_tool = create_get_labels_tool()
        
        # Verify tool properties
        tools = [query_tool, search_tool, labels_tool]
        tool_names = [tool.name for tool in tools]
        
        assert "query_logs" in tool_names
        assert "search_logs" in tool_names
        assert "get_labels" in tool_names
        
        # Verify tool schemas
        for tool in tools:
            assert tool.name
            assert tool.description
            assert tool.inputSchema
            assert isinstance(tool.inputSchema, dict)
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"
    
    @pytest.mark.asyncio
    async def test_query_logs_tool_schema(self, server: LokiMCPServer):
        """Test query_logs tool schema compliance."""
        from app.tools.query_logs import create_query_logs_tool
        
        query_tool = create_query_logs_tool()
        
        schema = query_tool.inputSchema
        assert "properties" in schema
        assert "required" in schema
        assert "query" in schema["required"]
        assert "query" in schema["properties"]
        
        # Verify query parameter schema
        query_prop = schema["properties"]["query"]
        assert query_prop["type"] == "string"
        assert "description" in query_prop
        assert query_prop["minLength"] == 1
    
    @pytest.mark.asyncio
    async def test_search_logs_tool_schema(self, server: LokiMCPServer):
        """Test search_logs tool schema compliance."""
        from app.tools.search_logs import create_search_logs_tool
        
        search_tool = create_search_logs_tool()
        
        schema = search_tool.inputSchema
        assert "properties" in schema
        assert "required" in schema
        assert "keywords" in schema["required"]
        assert "keywords" in schema["properties"]
        
        # Verify keywords parameter schema
        keywords_prop = schema["properties"]["keywords"]
        assert keywords_prop["type"] == "array"
        assert keywords_prop["items"]["type"] == "string"
        assert keywords_prop["minItems"] == 1
    
    @pytest.mark.asyncio
    async def test_get_labels_tool_schema(self, server: LokiMCPServer):
        """Test get_labels tool schema compliance."""
        from app.tools.get_labels import create_get_labels_tool
        
        labels_tool = create_get_labels_tool()
        
        schema = labels_tool.inputSchema
        assert "properties" in schema
        # get_labels has no required parameters
        assert schema.get("required", []) == []
    
    @pytest.mark.asyncio
    @patch('app.tools.query_logs.EnhancedLokiClient')
    async def test_tool_handler_methods(self, mock_client_class, server: LokiMCPServer):
        """Test tool handler methods directly."""
        # Mock the Loki client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock response
        mock_response = {
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
        mock_client.query_range.return_value = mock_response
        
        # Test query_logs handler directly
        result = await server._handle_query_logs({"query": "{job=\"test\"}"})
        assert result.status == "success"
        assert result.total_entries == 1
        assert "Test log message" in result.entries[0]["line"]
    
    @pytest.mark.asyncio
    @patch('app.tools.search_logs.EnhancedLokiClient')
    async def test_search_logs_handler(self, mock_client_class, server: LokiMCPServer):
        """Test search_logs handler directly."""
        # Mock the Loki client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock response
        mock_response = {
            "data": {
                "resultType": "streams",
                "result": [
                    {
                        "stream": {"job": "test", "level": "error"},
                        "values": [
                            ["1640995200000000000", "Error occurred in test"]
                        ]
                    }
                ]
            }
        }
        mock_client.query_range.return_value = mock_response
        
        # Test search_logs handler directly
        result = await server._handle_search_logs({"keywords": ["error"]})
        assert result.status == "success"
        assert result.total_entries == 1
        assert "Error occurred in test" in result.entries[0]["line"]
    
    @pytest.mark.asyncio
    @patch('app.tools.get_labels.EnhancedLokiClient')
    async def test_get_labels_handler(self, mock_client_class, server: LokiMCPServer):
        """Test get_labels handler directly."""
        # Mock the Loki client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock response
        mock_client.label_names.return_value = ["job", "level", "instance"]
        
        # Test get_labels handler directly
        result = await server._handle_get_labels({})
        assert result.status == "success"
        assert result.total_count == 3
        assert "job" in result.labels
        assert "level" in result.labels
        assert "instance" in result.labels
    
    @pytest.mark.asyncio
    async def test_parameter_validation_error(self, server: LokiMCPServer):
        """Test parameter validation error handling."""
        from pydantic import ValidationError
        
        # Test with invalid parameters (missing required query)
        try:
            await server._handle_query_logs({})
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected
    
    @pytest.mark.asyncio
    @patch('app.tools.query_logs.EnhancedLokiClient')
    async def test_execution_error_handling(self, mock_client_class, server: LokiMCPServer):
        """Test tool execution error handling."""
        # Mock the Loki client to raise an exception
        mock_client_class.side_effect = Exception("Connection failed")
        
        # Test that the handler returns an error result instead of raising
        result = await server._handle_query_logs({"query": "{job=\"test\"}"})
        assert result.status == "error"
        assert "Connection failed" in result.error
    
    @pytest.mark.asyncio
    async def test_result_formatting_empty_results(self, server: LokiMCPServer):
        """Test formatting of empty results."""
        from app.tools.query_logs import QueryLogsResult
        
        empty_result = QueryLogsResult(
            status="success",
            result_type="streams",
            entries=[],
            total_entries=0,
            query="{job=\"test\"}",
            time_range={"start": None, "end": None}
        )
        
        formatted = server._format_tool_result(empty_result)
        assert "No log entries found matching the criteria" in formatted
    
    @pytest.mark.asyncio
    async def test_result_formatting_error_results(self, server: LokiMCPServer):
        """Test formatting of error results."""
        from app.tools.query_logs import QueryLogsResult
        
        error_result = QueryLogsResult(
            status="error",
            result_type="error",
            entries=[],
            total_entries=0,
            query="{job=\"test\"}",
            time_range={"start": None, "end": None},
            error="Connection timeout"
        )
        
        formatted = server._format_tool_result(error_result)
        assert "Error: Connection timeout" in formatted
    
    @pytest.mark.asyncio
    async def test_result_formatting_large_results(self, server: LokiMCPServer):
        """Test formatting of large result sets."""
        from app.tools.query_logs import QueryLogsResult
        
        # Create 15 mock entries
        entries = []
        for i in range(15):
            entries.append({
                "timestamp": f"2024-01-01T00:00:{i:02d}Z",
                "line": f"Log message {i}",
                "labels": {"job": "test", "instance": f"server-{i}"}
            })
        
        large_result = QueryLogsResult(
            status="success",
            result_type="streams",
            entries=entries,
            total_entries=15,
            query="{job=\"test\"}",
            time_range={"start": None, "end": None}
        )
        
        formatted = server._format_tool_result(large_result)
        assert "Found 15 log entries" in formatted
        assert "... and 5 more entries" in formatted
        # Should only show first 10 entries
        assert "Log message 9" in formatted
        assert "Log message 10" not in formatted