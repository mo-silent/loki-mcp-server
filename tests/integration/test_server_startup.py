"""Integration test for server startup and basic functionality."""

import asyncio
import os
from unittest.mock import patch

import pytest

from app.config import LokiConfig
from app.server import create_server


class TestServerStartup:
    """Test server startup and basic functionality."""
    
    @pytest.fixture
    def mock_config(self) -> LokiConfig:
        """Create a mock Loki configuration for testing."""
        return LokiConfig(
            url="http://localhost:3100",
            timeout=30,
            max_retries=3
        )
    
    @pytest.mark.asyncio
    async def test_create_server_with_config(self, mock_config: LokiConfig):
        """Test creating server with provided config."""
        server = await create_server(mock_config)
        
        assert server is not None
        assert server.config.url == "http://localhost:3100"
        assert server.server.name == "loki-mcp-server"
    
    @pytest.mark.asyncio
    async def test_create_server_from_environment(self):
        """Test creating server from environment variables."""
        # Set environment variable
        os.environ['LOKI_URL'] = 'http://test.example.com:3100'
        
        try:
            server = await create_server()
            
            assert server is not None
            assert server.config.url == "http://test.example.com:3100"
            assert server.server.name == "loki-mcp-server"
        finally:
            # Clean up environment
            if 'LOKI_URL' in os.environ:
                del os.environ['LOKI_URL']
    
    @pytest.mark.asyncio
    async def test_server_capabilities(self, mock_config: LokiConfig):
        """Test that server has proper capabilities."""
        server = await create_server(mock_config)
        
        # Test that server has the expected methods
        assert hasattr(server.server, 'list_tools')
        assert hasattr(server.server, 'call_tool')
        assert hasattr(server.server, 'run')
        assert hasattr(server.server, 'get_capabilities')
        
        # Test capabilities
        from mcp.server import NotificationOptions
        capabilities = server.server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={}
        )
        assert capabilities is not None
    
    @pytest.mark.asyncio
    async def test_server_run_setup(self, mock_config: LokiConfig):
        """Test that server run method can be called (but don't actually run it)."""
        server = await create_server(mock_config)
        
        # Test that run method exists and can be called with invalid transport
        # This will raise an error but proves the method works
        with pytest.raises(ValueError, match="Unsupported transport type"):
            await server.run("invalid_transport")
    
    @pytest.mark.asyncio
    @patch('mcp.server.stdio.stdio_server')
    async def test_server_stdio_transport_setup(self, mock_stdio_server, mock_config: LokiConfig):
        """Test that server can be set up with stdio transport."""
        # Mock the stdio server context manager
        mock_stdio_server.return_value.__aenter__.return_value = (None, None)
        mock_stdio_server.return_value.__aexit__.return_value = None
        
        server = await create_server(mock_config)
        
        # Mock the server run method to avoid actually running
        with patch.object(server.server, 'run') as mock_run:
            mock_run.return_value = None
            
            # This should not raise an error
            await server.run("stdio")
            
            # Verify that stdio_server was called
            mock_stdio_server.assert_called_once()
            
            # Verify that server.run was called with the expected parameters
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            kwargs = mock_run.call_args[1]
            
            # Should have read_stream, write_stream, and InitializationOptions
            assert len(args) == 3
            assert args[0] is None  # read_stream (mocked)
            assert args[1] is None  # write_stream (mocked)
            
            # Check InitializationOptions
            init_options = args[2]
            assert init_options.server_name == "loki-mcp-server"
            assert init_options.server_version == "0.1.0"
            assert init_options.capabilities is not None