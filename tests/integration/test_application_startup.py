"""Integration tests for application startup and CLI functionality."""

import asyncio
import os
import signal
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.main import validate_startup, parse_arguments, GracefulShutdown
from app.config import LokiConfig, ConfigurationError


class TestApplicationStartup:
    """Test application startup functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_startup_success(self):
        """Test successful startup validation."""
        config = LokiConfig(url="http://localhost:3100")
        
        with patch('app.loki_client.LokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.label_names.return_value = ["job", "instance"]
            mock_client_class.return_value = mock_client
            
            result = await validate_startup(config)
            
            assert result is True
            mock_client.label_names.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_startup_connection_warning(self):
        """Test startup validation with connection warning but success."""
        config = LokiConfig(url="http://localhost:3100")
        
        with patch('app.loki_client.LokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.label_names.side_effect = Exception("Connection failed")
            mock_client_class.return_value = mock_client
            
            result = await validate_startup(config)
            
            # Should still return True but log warning
            assert result is True
            mock_client.label_names.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_startup_failure(self):
        """Test startup validation failure."""
        config = LokiConfig(url="http://localhost:3100")
        
        with patch('app.loki_client.LokiClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Critical error")
            
            result = await validate_startup(config)
            
            assert result is False


class TestCLIArgumentParsing:
    """Test command-line argument parsing."""
    
    def test_parse_arguments_defaults(self):
        """Test parsing with default arguments."""
        with patch('sys.argv', ['loki-mcp-server']):
            args = parse_arguments()
            
            assert args.transport == "stdio"
            assert args.validate_only is False
            assert args.log_level == "INFO"
    
    def test_parse_arguments_custom(self):
        """Test parsing with custom arguments."""
        with patch('sys.argv', [
            'loki-mcp-server',
            '--transport', 'stdio',
            '--validate-only',
            '--log-level', 'DEBUG'
        ]):
            args = parse_arguments()
            
            assert args.transport == "stdio"
            assert args.validate_only is True
            assert args.log_level == "DEBUG"
    
    def test_parse_arguments_version(self):
        """Test version argument."""
        with patch('sys.argv', ['loki-mcp-server', '--version']):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            
            assert exc_info.value.code == 0
    
    def test_parse_arguments_help(self):
        """Test help argument."""
        with patch('sys.argv', ['loki-mcp-server', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                parse_arguments()
            
            assert exc_info.value.code == 0


class TestGracefulShutdown:
    """Test graceful shutdown functionality."""
    
    def test_graceful_shutdown_init(self):
        """Test graceful shutdown initialization."""
        shutdown = GracefulShutdown()
        
        assert shutdown.shutdown_event is not None
        assert not shutdown.shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_signal(self):
        """Test graceful shutdown signal handling."""
        shutdown = GracefulShutdown()
        
        # Simulate signal
        shutdown._signal_handler(signal.SIGTERM, None)
        
        # Should complete immediately since event is set
        await asyncio.wait_for(shutdown.wait_for_shutdown(), timeout=0.1)
        
        assert shutdown.shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout(self):
        """Test graceful shutdown timeout."""
        shutdown = GracefulShutdown()
        
        # Should timeout since no signal is sent
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(shutdown.wait_for_shutdown(), timeout=0.1)


class TestCLIIntegration:
    """Test CLI integration with subprocess."""
    
    def test_cli_help_output(self):
        """Test CLI help output."""
        result = subprocess.run(
            [sys.executable, '-m', 'app.main', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Loki MCP Server' in result.stdout
        assert 'Environment Variables:' in result.stdout
        assert 'LOKI_URL' in result.stdout
    
    def test_cli_version_output(self):
        """Test CLI version output."""
        result = subprocess.run(
            [sys.executable, '-m', 'app.main', '--version'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'loki-mcp-server 0.1.0' in result.stdout


if __name__ == "__main__":
    pytest.main([__file__])