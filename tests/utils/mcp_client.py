"""Test utilities for MCP client simulation."""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, Mock

from mcp import types

from app.config import LokiConfig
from app.server import LokiMCPServer


class MockMCPClient:
    """Mock MCP client for testing server interactions."""
    
    def __init__(self, server: LokiMCPServer):
        """Initialize mock client with server instance."""
        self.server = server
        self.session_id = "test-session-123"
        self.capabilities = {
            "tools": {"listChanged": True},
            "resources": {"subscribe": True, "listChanged": True}
        }
    
    async def list_tools(self) -> List[types.Tool]:
        """List available tools from the server."""
        # Create a mock request to get tools
        from mcp.types import ListToolsRequest
        request = ListToolsRequest()
        
        # Use the server's request handlers
        try:
            # Access the list_tools handler through the server's request handlers
            for handler_name, handler in self.server.server.request_handlers.items():
                if "tools/list" in handler_name:
                    result = await handler(request)
                    return result.tools if hasattr(result, 'tools') else []
            
            # Fallback: manually create tools list
            from app.tools.query_logs import create_query_logs_tool
            from app.tools.search_logs import create_search_logs_tool
            from app.tools.get_labels import create_get_labels_tool
            
            tools = [
                create_query_logs_tool(),
                create_search_logs_tool(),
                create_get_labels_tool()
            ]
            
            # Convert to MCP types.Tool format
            mcp_tools = []
            for tool in tools:
                mcp_tool = types.Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.inputSchema
                )
                mcp_tools.append(mcp_tool)
            
            return mcp_tools
        except Exception:
            return []
    
    async def call_tool(
        self, 
        name: str, 
        arguments: Optional[Dict[str, Any]] = None
    ) -> List[types.TextContent]:
        """Call a tool on the server."""
        # Create a mock request to call tool
        from mcp.types import CallToolRequest
        request = CallToolRequest(
            method="tools/call",
            params={
                "name": name,
                "arguments": arguments or {}
            }
        )
        
        try:
            # Use the server's request handlers
            for handler_name, handler in self.server.server.request_handlers.items():
                if "tools/call" in handler_name:
                    result = await handler(request)
                    return result.content if hasattr(result, 'content') else []
            
            # Fallback: directly call the server's tool handlers
            if name == "query_logs":
                result = await self.server._handle_query_logs(arguments or {})
            elif name == "search_logs":
                result = await self.server._handle_search_logs(arguments or {})
            elif name == "get_labels":
                result = await self.server._handle_get_labels(arguments or {})
            else:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Unknown tool: {name}"
                )]
            
            # Format the result
            formatted_result = self.server._format_tool_result(result)
            return [types.TextContent(
                type="text",
                text=formatted_result
            )]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize the client session."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": self.capabilities,
            "serverInfo": {
                "name": "loki-mcp-server",
                "version": "0.1.0"
            }
        }


class MockLokiServer:
    """Mock Loki server for integration testing."""
    
    def __init__(self, port: int = 3100):
        """Initialize mock Loki server."""
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.responses = {}
        self.request_log = []
        self.is_running = False
    
    def set_response(self, endpoint: str, method: str, response: Dict[str, Any]):
        """Set a mock response for a specific endpoint."""
        key = f"{method}:{endpoint}"
        self.responses[key] = response
    
    def set_error_response(self, endpoint: str, method: str, status_code: int, error_data: Dict[str, Any]):
        """Set an error response for a specific endpoint."""
        key = f"{method}:{endpoint}"
        self.responses[key] = {
            "status_code": status_code,
            "data": error_data
        }
    
    def get_request_log(self) -> List[Dict[str, Any]]:
        """Get log of all requests made to the mock server."""
        return self.request_log.copy()
    
    def clear_request_log(self):
        """Clear the request log."""
        self.request_log.clear()
    
    async def start(self):
        """Start the mock server."""
        self.is_running = True
        # In a real implementation, this would start an HTTP server
        # For testing, we'll just mark it as running
    
    async def stop(self):
        """Stop the mock server."""
        self.is_running = False
        self.responses.clear()
        self.request_log.clear()


class MCPTestClient:
    """Test client for end-to-end MCP testing."""
    
    def __init__(self, config: Optional[LokiConfig] = None):
        """Initialize test client."""
        self.config = config or LokiConfig(url="http://localhost:3100")
        self.server = None
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.server = LokiMCPServer(self.config)
        self.client = MockMCPClient(self.server)
        await self.client.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            self.client = None
        if self.server:
            self.server = None
    
    async def list_tools(self) -> List[types.Tool]:
        """List available tools."""
        return await self.client.list_tools()
    
    async def call_tool(
        self, 
        name: str, 
        arguments: Optional[Dict[str, Any]] = None
    ) -> List[types.TextContent]:
        """Call a tool."""
        return await self.client.call_tool(name, arguments)
    
    async def query_logs(
        self,
        query: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[types.TextContent]:
        """Convenience method for query_logs tool."""
        args = {"query": query}
        if start:
            args["start"] = start
        if end:
            args["end"] = end
        if limit:
            args["limit"] = limit
        
        return await self.call_tool("query_logs", args)
    
    async def search_logs(
        self,
        keywords: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[types.TextContent]:
        """Convenience method for search_logs tool."""
        args = {"keywords": keywords}
        if start:
            args["start"] = start
        if end:
            args["end"] = end
        if limit:
            args["limit"] = limit
        
        return await self.call_tool("search_logs", args)
    
    async def get_labels(
        self,
        label_name: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> List[types.TextContent]:
        """Convenience method for get_labels tool."""
        args = {}
        if label_name:
            args["label_name"] = label_name
        if start:
            args["start"] = start
        if end:
            args["end"] = end
        
        return await self.call_tool("get_labels", args)


def create_mock_loki_responses():
    """Create a set of standard mock responses for testing."""
    from ..fixtures.sample_logs import (
        SAMPLE_QUERY_RANGE_RESPONSE,
        SAMPLE_QUERY_INSTANT_RESPONSE,
        SAMPLE_LABELS_RESPONSE,
        SAMPLE_LABEL_VALUES_RESPONSE,
        SAMPLE_SERIES_RESPONSE,
        SAMPLE_ERROR_RESPONSES
    )
    
    return {
        "query_range_success": SAMPLE_QUERY_RANGE_RESPONSE,
        "query_instant_success": SAMPLE_QUERY_INSTANT_RESPONSE,
        "labels_success": SAMPLE_LABELS_RESPONSE,
        "label_values_success": SAMPLE_LABEL_VALUES_RESPONSE,
        "series_success": SAMPLE_SERIES_RESPONSE,
        "invalid_query_error": SAMPLE_ERROR_RESPONSES["invalid_query"],
        "auth_error": SAMPLE_ERROR_RESPONSES["authentication_error"],
        "rate_limit_error": SAMPLE_ERROR_RESPONSES["rate_limit_error"]
    }


async def simulate_concurrent_requests(
    client: MCPTestClient,
    tool_calls: List[Dict[str, Any]],
    max_concurrent: int = 10
) -> List[Any]:
    """Simulate concurrent tool calls for performance testing."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def make_call(call_info):
        async with semaphore:
            return await client.call_tool(
                call_info["name"],
                call_info.get("arguments")
            )
    
    tasks = [make_call(call) for call in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)


def assert_tool_response_format(response: List[types.TextContent]):
    """Assert that a tool response has the correct format."""
    assert isinstance(response, list)
    assert len(response) > 0
    
    for content in response:
        assert isinstance(content, types.TextContent)
        assert content.type == "text"
        assert isinstance(content.text, str)
        assert len(content.text) > 0


def extract_response_text(response: List[types.TextContent]) -> str:
    """Extract text content from MCP response."""
    if not response:
        return ""
    return response[0].text


def assert_successful_response(response: List[types.TextContent]):
    """Assert that a response indicates success."""
    text = extract_response_text(response)
    assert not text.startswith("Error:")
    assert "Found" in text or "No" in text  # Either found results or no results


def assert_error_response(response: List[types.TextContent], expected_error: Optional[str] = None):
    """Assert that a response indicates an error."""
    text = extract_response_text(response)
    assert text.startswith("Error:")
    if expected_error:
        assert expected_error in text