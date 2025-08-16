"""Main MCP server implementation."""

import asyncio
from typing import Any, Dict, List, Optional, Sequence

import structlog
from mcp import types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from pydantic import ValidationError

from .config import LokiConfig, ConfigurationError
from .tools.query_logs import query_logs_tool, create_query_logs_tool, QueryLogsParams
from .tools.search_logs import search_logs_tool, create_search_logs_tool, SearchLogsParams
from .tools.get_labels import get_labels_tool, create_get_labels_tool, GetLabelsParams
from .error_handler import ErrorClassifier, ErrorContext, ErrorCategory

logger = structlog.get_logger(__name__)


class LokiMCPServer:
    """Main MCP server for Loki integration."""
    
    def __init__(self, config: LokiConfig):
        """
        Initialize the Loki MCP server.
        
        Args:
            config: Loki configuration
        """
        self.config = config
        self.server = Server("loki-mcp-server")
        self._setup_handlers()
        
        logger.info("Loki MCP Server initialized", loki_url=config.url)
    
    def _setup_handlers(self) -> None:
        """Set up MCP server handlers."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """Handle tool discovery requests."""
            logger.debug("Listing available tools")
            
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
            
            logger.info("Tools listed", tool_count=len(mcp_tools))
            return mcp_tools
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, 
            arguments: Optional[Dict[str, Any]] = None
        ) -> List[types.TextContent]:
            """
            Handle tool execution requests.
            
            Args:
                name: Tool name to execute
                arguments: Tool arguments
                
            Returns:
                Tool execution results
            """
            logger.info("Tool called", tool_name=name, arguments=arguments)
            
            if arguments is None:
                arguments = {}
            
            try:
                # Route to appropriate tool handler
                if name == "query_logs":
                    result = await self._handle_query_logs(arguments)
                elif name == "search_logs":
                    result = await self._handle_search_logs(arguments)
                elif name == "get_labels":
                    result = await self._handle_get_labels(arguments)
                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error("Unknown tool requested", tool_name=name)
                    return [types.TextContent(
                        type="text",
                        text=f"Error: {error_msg}"
                    )]
                
                # Format successful result
                return [types.TextContent(
                    type="text",
                    text=self._format_tool_result(result)
                )]
                
            except ValidationError as e:
                error_info = ErrorClassifier.classify_error(e)
                error_msg = self._format_error_message(error_info, name, arguments)
                logger.error("Parameter validation failed", tool_name=name, error=str(e))
                return [types.TextContent(
                    type="text",
                    text=error_msg
                )]
            except Exception as e:
                error_info = ErrorClassifier.classify_error(e)
                error_msg = self._format_error_message(error_info, name, arguments)
                logger.error("Tool execution failed", tool_name=name, error=str(e))
                return [types.TextContent(
                    type="text",
                    text=error_msg
                )]
    
    async def _handle_query_logs(self, arguments: Dict[str, Any]) -> Any:
        """Handle query_logs tool execution."""
        try:
            params = QueryLogsParams(**arguments)
            result = await query_logs_tool(params, self.config)
            logger.info("Query logs completed", status=result.status, entries=result.total_entries)
            return result
        except ValidationError as e:
            logger.error("Query logs parameter validation failed", error=str(e))
            raise
        except Exception as e:
            logger.error("Query logs execution failed", error=str(e))
            raise
    
    async def _handle_search_logs(self, arguments: Dict[str, Any]) -> Any:
        """Handle search_logs tool execution."""
        try:
            params = SearchLogsParams(**arguments)
            result = await search_logs_tool(params, self.config)
            logger.info("Search logs completed", status=result.status, entries=result.total_entries)
            return result
        except ValidationError as e:
            logger.error("Search logs parameter validation failed", error=str(e))
            raise
        except Exception as e:
            logger.error("Search logs execution failed", error=str(e))
            raise
    
    async def _handle_get_labels(self, arguments: Dict[str, Any]) -> Any:
        """Handle get_labels tool execution."""
        try:
            params = GetLabelsParams(**arguments)
            result = await get_labels_tool(params, self.config)
            logger.info("Get labels completed", status=result.status, labels=result.total_count)
            return result
        except ValidationError as e:
            logger.error("Get labels parameter validation failed", error=str(e))
            raise
        except Exception as e:
            logger.error("Get labels execution failed", error=str(e))
            raise
    
    def _format_error_message(
        self, 
        error_info: Any, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> str:
        """
        Format error message with user-friendly information.
        
        Args:
            error_info: Classified error information
            tool_name: Name of the tool that failed
            arguments: Tool arguments
            
        Returns:
            Formatted error message
        """
        message_parts = [f"Error in {tool_name}:"]
        
        if hasattr(error_info, 'message'):
            message_parts.append(error_info.message)
        else:
            message_parts.append(str(error_info))
        
        if hasattr(error_info, 'suggestion') and error_info.suggestion:
            message_parts.append(f"\nSuggestion: {error_info.suggestion}")
        
        if hasattr(error_info, 'details') and error_info.details:
            message_parts.append(f"\nDetails: {error_info.details}")
        
        # Add context-specific suggestions
        if hasattr(error_info, 'category'):
            if error_info.category == ErrorCategory.AUTHENTICATION:
                message_parts.append(
                    "\nPlease check your LOKI_USERNAME/LOKI_PASSWORD or LOKI_BEARER_TOKEN environment variables."
                )
            elif error_info.category == ErrorCategory.CONNECTION:
                message_parts.append(
                    "\nPlease verify your LOKI_URL environment variable and ensure Loki is accessible."
                )
            elif error_info.category == ErrorCategory.RATE_LIMIT:
                message_parts.append(
                    "\nConsider reducing the frequency of requests or increasing rate limits in configuration."
                )
            elif error_info.category == ErrorCategory.VALIDATION:
                message_parts.append(
                    f"\nPlease check the parameters: {list(arguments.keys())}"
                )
        
        return " ".join(message_parts)
    
    def _format_tool_result(self, result: Any) -> str:
        """
        Format tool result for MCP response.
        
        Args:
            result: Tool execution result
            
        Returns:
            Formatted result string
        """
        try:
            # Convert result to dict if it's a Pydantic model
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
            else:
                result_dict = result
            
            # Format based on result type
            if result_dict.get("status") == "error":
                return f"Error: {result_dict.get('error', 'Unknown error')}"
            
            # Format successful results based on tool type
            if "entries" in result_dict:
                # Query or search results
                entries = result_dict["entries"]
                total = result_dict["total_entries"]
                
                if total == 0:
                    return "No log entries found matching the criteria."
                
                # Format entries for display
                formatted_entries = []
                for entry in entries[:10]:  # Limit display to first 10 entries
                    timestamp = entry.get("timestamp", "Unknown time")
                    line = entry.get("line", "")
                    labels = entry.get("labels", {})
                    
                    # Format labels for display
                    label_str = ", ".join([f"{k}={v}" for k, v in labels.items()])
                    
                    formatted_entry = f"[{timestamp}] {label_str}: {line}"
                    formatted_entries.append(formatted_entry)
                
                result_text = f"Found {total} log entries:\n\n" + "\n".join(formatted_entries)
                
                if total > 10:
                    result_text += f"\n\n... and {total - 10} more entries"
                
                return result_text
            
            elif "labels" in result_dict:
                # Label results
                labels = result_dict["labels"]
                total = result_dict["total_count"]
                label_type = result_dict.get("label_type", "labels")
                label_name = result_dict.get("label_name")
                
                if total == 0:
                    if label_name:
                        return f"No values found for label '{label_name}'"
                    else:
                        return "No labels found"
                
                if label_name:
                    result_text = f"Found {total} values for label '{label_name}':\n\n"
                else:
                    result_text = f"Found {total} label names:\n\n"
                
                # Display labels (limit to first 50)
                display_labels = labels[:50]
                result_text += "\n".join(display_labels)
                
                if total > 50:
                    result_text += f"\n\n... and {total - 50} more {label_type}"
                
                return result_text
            
            else:
                # Generic result formatting
                return str(result_dict)
                
        except Exception as e:
            logger.error("Failed to format tool result", error=str(e))
            return f"Tool completed but failed to format result: {e}"
    
    async def run(self, transport_type: str = "stdio") -> None:
        """
        Run the MCP server.
        
        Args:
            transport_type: Transport type (stdio, sse, etc.)
        """
        logger.info("Starting Loki MCP server", transport=transport_type)
        
        try:
            if transport_type == "stdio":
                from mcp.server.stdio import stdio_server
                async with stdio_server() as (read_stream, write_stream):
                    await self.server.run(
                        read_stream,
                        write_stream,
                        InitializationOptions(
                            server_name="loki-mcp-server",
                            server_version="0.1.0",
                            capabilities=self.server.get_capabilities(
                                notification_options=NotificationOptions(),
                                experimental_capabilities={}
                            )
                        )
                    )
            else:
                raise ValueError(f"Unsupported transport type: {transport_type}")
                
        except Exception as e:
            logger.error("Server run failed", error=str(e))
            raise


async def create_server(config: Optional[LokiConfig] = None) -> LokiMCPServer:
    """
    Create and configure a Loki MCP server.
    
    Args:
        config: Optional Loki configuration. If not provided, loads from environment.
        
    Returns:
        Configured LokiMCPServer instance
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    if config is None:
        from .config import load_config
        config = load_config()
    
    server = LokiMCPServer(config)
    logger.info("Loki MCP server created successfully")
    return server