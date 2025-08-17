"""Tool for executing LogQL queries."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import structlog
from mcp import Tool
from pydantic import BaseModel, Field, field_validator

from ..enhanced_client import EnhancedLokiClient
from ..loki_client import LokiClientError
from ..config import LokiConfig
from ..time_utils import get_time_range

logger = structlog.get_logger(__name__)


class QueryLogsParams(BaseModel):
    """Parameters for the query_logs tool."""
    
    query: str = Field(
        description="LogQL query string to execute against Loki",
        min_length=1
    )
    start: Optional[str] = Field(
        default=None,
        description="Start time for query range (ISO format, Unix timestamp, or relative time like '5m')"
    )
    end: Optional[str] = Field(
        default=None,
        description="End time for query range (ISO format, Unix timestamp, or relative time like '1h')"
    )
    limit: Optional[int] = Field(
        default=100,
        description="Maximum number of log entries to return",
        ge=1,
        le=5000
    )
    direction: str = Field(
        default="backward",
        description="Query direction: 'forward' or 'backward'"
    )
    
    @field_validator('direction')
    @classmethod
    def validate_direction(cls, v):
        if v not in ['forward', 'backward']:
            raise ValueError("Direction must be 'forward' or 'backward'")
        return v


class QueryLogsResult(BaseModel):
    """Result from query_logs tool."""
    
    status: str
    result_type: str
    entries: List[Dict[str, Any]]
    total_entries: int
    query: str
    time_range: Dict[str, Optional[str]]
    error: Optional[str] = None


async def query_logs_tool(
    params: QueryLogsParams,
    config: LokiConfig
) -> QueryLogsResult:
    """
    Execute a LogQL query against Loki and return formatted results.
    
    Args:
        params: Query parameters
        config: Loki configuration
        
    Returns:
        Formatted query results
    """
    logger.info("Executing LogQL query", query=params.query)
    
    try:
        async with EnhancedLokiClient(config) as client:
            # Always use range queries with proper time conversion
            start_time, end_time = get_time_range(params.start, params.end)
            
            response = await client.query_range(
                query=params.query,
                start=start_time,
                end=end_time,
                limit=params.limit,
                direction=params.direction
            )
            
            # Format the response
            formatted_entries = _format_loki_response(response)
            
            return QueryLogsResult(
                status="success",
                result_type=response.get("data", {}).get("resultType", "streams"),
                entries=formatted_entries,
                total_entries=len(formatted_entries),
                query=params.query,
                time_range={
                    "start": params.start,
                    "end": params.end
                }
            )
            
    except LokiClientError as e:
        logger.error("Loki client error", error=str(e), query=params.query)
        return QueryLogsResult(
            status="error",
            result_type="error",
            entries=[],
            total_entries=0,
            query=params.query,
            time_range={
                "start": params.start,
                "end": params.end
            },
            error=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in query_logs", error=str(e), query=params.query)
        return QueryLogsResult(
            status="error",
            result_type="error",
            entries=[],
            total_entries=0,
            query=params.query,
            time_range={
                "start": params.start,
                "end": params.end
            },
            error=f"Unexpected error: {str(e)}"
        )


def _format_loki_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Format Loki API response into a consistent structure.
    
    Args:
        response: Raw response from Loki API
        
    Returns:
        List of formatted log entries
    """
    formatted_entries = []
    
    data = response.get("data", {})
    result = data.get("result", [])
    
    for stream in result:
        stream_labels = stream.get("stream", {})
        values = stream.get("values", [])
        
        for value in values:
            if len(value) >= 2:
                timestamp_ns = value[0]
                log_line = value[1]
                
                # Convert nanosecond timestamp to readable format
                timestamp_s = int(timestamp_ns) / 1_000_000_000
                readable_time = datetime.fromtimestamp(
                    timestamp_s, 
                    tz=timezone.utc
                ).isoformat()
                
                formatted_entry = {
                    "timestamp": readable_time,
                    "timestamp_ns": timestamp_ns,
                    "line": log_line,
                    "labels": stream_labels
                }
                
                formatted_entries.append(formatted_entry)
    
    # Sort by timestamp (newest first for backward direction)
    formatted_entries.sort(
        key=lambda x: int(x["timestamp_ns"]), 
        reverse=True
    )
    
    return formatted_entries


def create_query_logs_tool() -> Tool:
    """Create the MCP tool definition for query_logs."""
    return Tool(
        name="query_logs",
        description="Execute LogQL queries against Grafana Loki to retrieve log entries",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "LogQL query string to execute against Loki",
                    "minLength": 1
                },
                "start": {
                    "type": "string",
                    "description": "Start time for query range (ISO format, Unix timestamp, or relative time like '5m')"
                },
                "end": {
                    "type": "string", 
                    "description": "End time for query range (ISO format, Unix timestamp, or relative time like '1h')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log entries to return",
                    "minimum": 1,
                    "maximum": 5000,
                    "default": 100
                },
                "direction": {
                    "type": "string",
                    "description": "Query direction: 'forward' or 'backward'",
                    "enum": ["forward", "backward"],
                    "default": "backward"
                }
            },
            "required": ["query"]
        }
    )