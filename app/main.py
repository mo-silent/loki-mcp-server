"""Main entry point for the Loki MCP server."""

import argparse
import asyncio
import os
import signal
import sys
from typing import Optional

import structlog

from .logging_config import setup_default_logging


class GracefulShutdown:
    """Handle graceful shutdown of the server."""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        if sys.platform != "win32":
            # Unix-like systems
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._signal_handler)
        else:
            # Windows
            signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger = structlog.get_logger(__name__)
        logger.info("Shutdown signal received", signal=signum)
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()


async def validate_startup(config) -> bool:
    """
    Validate server startup conditions and perform health checks.
    
    Args:
        config: Loki configuration
        
    Returns:
        True if validation passes, False otherwise
    """
    logger = structlog.get_logger(__name__)
    logger.info("Performing startup validation")
    
    try:
        # Test Loki connectivity
        from .loki_client import LokiClient
        
        client = LokiClient(config)
        
        # Perform a simple health check query
        logger.info("Testing Loki connectivity", loki_url=config.url)
        
        # Try to get label names as a health check
        try:
            await client.label_names()
            logger.info("Loki connectivity test passed")
        except Exception as e:
            logger.warning(
                "Loki connectivity test failed - server will start but may not function properly",
                error=str(e),
                suggestion="Verify LOKI_URL and authentication credentials"
            )
            # Don't fail startup for connectivity issues - allow server to start
            # and handle connection errors at runtime
        
        logger.info("Startup validation completed successfully")
        return True
        
    except Exception as e:
        logger.error("Startup validation failed", error=str(e))
        return False


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Loki MCP Server - Model Context Protocol server for Grafana Loki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  LOKI_URL                 Loki server URL (required)
  LOKI_USERNAME           Username for basic authentication
  LOKI_PASSWORD           Password for basic authentication  
  LOKI_BEARER_TOKEN       Bearer token for authentication
  LOKI_TIMEOUT            Request timeout in seconds (default: 30)
  LOKI_MAX_RETRIES        Maximum retry attempts (default: 3)
  LOKI_RATE_LIMIT_REQUESTS Rate limit requests per period (default: 100)
  LOKI_RATE_LIMIT_PERIOD  Rate limit period in seconds (default: 60)

Examples:
  # Start server with environment variables
  export LOKI_URL=http://localhost:3100
  loki-mcp-server
  
  # Start with custom transport
  loki-mcp-server --transport stdio
  
  # Validate configuration without starting
  loki-mcp-server --validate-only
        """
    )
    
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport type for MCP communication (default: stdio)"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration and connectivity, then exit"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="loki-mcp-server 0.1.0"
    )
    
    return parser.parse_args()


async def main() -> None:
    """Main entry point for the Loki MCP server."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging with specified level
    setup_default_logging(level=args.log_level)
    logger = structlog.get_logger(__name__)
    
    logger.info(
        "Starting Loki MCP Server",
        version="0.1.0",
        transport=args.transport,
        log_level=args.log_level
    )
    
    try:
        from .server import create_server
        from .config import load_config, ConfigurationError
        
        # Load and validate configuration
        try:
            config = load_config()
            logger.info(
                "Configuration loaded successfully",
                loki_url=config.url,
                has_auth=bool(config.username or config.bearer_token),
                timeout=config.timeout,
                max_retries=config.max_retries
            )
        except ConfigurationError as e:
            logger.error("Configuration error", error=str(e))
            sys.exit(1)
        
        # Perform startup validation and health checks
        if not await validate_startup(config):
            logger.error("Startup validation failed")
            sys.exit(1)
        
        # If validate-only flag is set, exit after validation
        if args.validate_only:
            logger.info("Configuration and connectivity validation completed successfully")
            sys.exit(0)
        
        # Set up graceful shutdown handling
        shutdown_handler = GracefulShutdown()
        
        # Create server
        server = await create_server(config)
        logger.info("Server created successfully")
        
        # Run server with graceful shutdown
        server_task = asyncio.create_task(server.run(args.transport))
        shutdown_task = asyncio.create_task(shutdown_handler.wait_for_shutdown())
        
        logger.info("Server started successfully", transport=args.transport)
        
        # Wait for either server completion or shutdown signal
        done, pending = await asyncio.wait(
            [server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Check if server task completed with an exception
        if server_task in done:
            try:
                await server_task
            except Exception as e:
                logger.error("Server task failed", error=str(e))
                raise
        
        logger.info("Server shutdown completed")
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via keyboard interrupt")
    except ConfigurationError as e:
        logger.error("Configuration error", error=str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("Server failed to start", error=str(e))
        sys.exit(1)


def cli_main() -> None:
    """CLI entry point that handles asyncio setup."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle KeyboardInterrupt at the top level to avoid stack trace
        pass
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    cli_main()