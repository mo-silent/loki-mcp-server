"""Tool for keyword-based log searching."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import structlog
from mcp import Tool
from pydantic import BaseModel, Field, field_validator

from ..enhanced_client import EnhancedLokiClient
from ..loki_client import LokiClientError
from ..config import LokiConfig
from ..query_builder import LogQLQueryBuilder

logger = structlog.get_logger(__name__)


class SearchLogsParams(BaseModel):
    """Parameters for the search_logs tool."""
    
    keywords: List[str] = Field(
        description="List of keywords to search for in log messages",
        min_length=1
    )
    labels: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional label filters as key-value pairs (e.g., {'job': 'web-server', 'level': 'error'})"
    )
    start: Optional[str] = Field(
        default=None,
        description="Start time for search range (ISO format, Unix timestamp, or relative time like '5m')"
    )
    end: Optional[str] = Field(
        default=None,
        description="End time for search range (ISO format, Unix timestamp, or relative time like '1h')"
    )
    limit: Optional[int] = Field(
        default=100,
        description="Maximum number of log entries to return",
        ge=1,
        le=5000
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether the search should be case sensitive"
    )
    operator: str = Field(
        default="AND",
        description="Logical operator for multiple keywords: 'AND' or 'OR'"
    )
    
    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v):
        if v not in ['AND', 'OR']:
            raise ValueError("Operator must be 'AND' or 'OR'")
        return v
    
    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, v):
        if not v:
            raise ValueError("At least one keyword must be provided")
        # Filter out empty keywords
        filtered = [k.strip() for k in v if k and k.strip()]
        if not filtered:
            raise ValueError("At least one non-empty keyword must be provided")
        return filtered


class SearchLogsResult(BaseModel):
    """Result from search_logs tool."""
    
    status: str
    entries: List[Dict[str, Any]]
    total_entries: int
    search_terms: List[str]
    labels_filter: Optional[Dict[str, str]]
    time_range: Dict[str, Optional[str]]
    query_used: str
    error: Optional[str] = None


async def search_logs_tool(
    params: SearchLogsParams,
    config: LokiConfig
) -> SearchLogsResult:
    """
    Search logs using keywords and return formatted results.
    
    Args:
        params: Search parameters
        config: Loki configuration
        
    Returns:
        Formatted search results
    """
    logger.info("Searching logs", keywords=params.keywords, labels=params.labels)
    
    try:
        # Build the search query
        query_builder = LogQLQueryBuilder()
        
        if params.operator == "OR":
            # For OR operator, create separate queries and combine results
            queries = []
            for keyword in params.keywords:
                query = query_builder.build_search_query(
                    keywords=[keyword],
                    labels=params.labels,
                    case_sensitive=params.case_sensitive
                )
                queries.append(query)
            
            # Combine with OR logic - we'll execute each query separately
            # and merge results (this is a limitation of LogQL)
            all_entries = []
            
            async with EnhancedLokiClient(config) as client:
                for query in queries:
                    try:
                        if params.start or params.end:
                            start_time = params.start or "1h"
                            end_time = params.end or "now"
                            
                            response = await client.query_range(
                                query=query,
                                start=start_time,
                                end=end_time,
                                limit=params.limit,
                                direction="backward"
                            )
                        else:
                            response = await client.query_instant(
                                query=query,
                                limit=params.limit,
                                direction="backward"
                            )
                        
                        entries = _format_search_results(response, params.keywords)
                        all_entries.extend(entries)
                        
                    except LokiClientError as e:
                        logger.warning("Query failed", query=query, error=str(e))
                        continue
            
            # Remove duplicates and sort by timestamp
            unique_entries = _deduplicate_entries(all_entries)
            final_query = f"OR combination of: {' | '.join(queries)}"
            
        else:
            # AND operator - build single query with all keywords
            search_query = query_builder.build_search_query(
                keywords=params.keywords,
                labels=params.labels,
                case_sensitive=params.case_sensitive
            )
            
            async with EnhancedLokiClient(config) as client:
                if params.start or params.end:
                    start_time = params.start or "1h"
                    end_time = params.end or "now"
                    
                    response = await client.query_range(
                        query=search_query,
                        start=start_time,
                        end=end_time,
                        limit=params.limit,
                        direction="backward"
                    )
                else:
                    response = await client.query_instant(
                        query=search_query,
                        limit=params.limit,
                        direction="backward"
                    )
                
                unique_entries = _format_search_results(response, params.keywords)
                final_query = search_query
        
        # Limit results if we have too many (can happen with OR queries)
        if len(unique_entries) > params.limit:
            unique_entries = unique_entries[:params.limit]
        
        return SearchLogsResult(
            status="success",
            entries=unique_entries,
            total_entries=len(unique_entries),
            search_terms=params.keywords,
            labels_filter=params.labels,
            time_range={
                "start": params.start,
                "end": params.end
            },
            query_used=final_query
        )
        
    except LokiClientError as e:
        logger.error("Loki client error", error=str(e), keywords=params.keywords)
        return SearchLogsResult(
            status="error",
            entries=[],
            total_entries=0,
            search_terms=params.keywords,
            labels_filter=params.labels,
            time_range={
                "start": params.start,
                "end": params.end
            },
            query_used="",
            error=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in search_logs", error=str(e), keywords=params.keywords)
        return SearchLogsResult(
            status="error",
            entries=[],
            total_entries=0,
            search_terms=params.keywords,
            labels_filter=params.labels,
            time_range={
                "start": params.start,
                "end": params.end
            },
            query_used="",
            error=f"Unexpected error: {str(e)}"
        )


def _format_search_results(response: Dict[str, Any], keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Format Loki API response for search results with keyword highlighting.
    
    Args:
        response: Raw response from Loki API
        keywords: Keywords that were searched for
        
    Returns:
        List of formatted log entries with search context
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
                
                # Find which keywords matched (for context)
                matched_keywords = []
                for keyword in keywords:
                    if keyword.lower() in log_line.lower():
                        matched_keywords.append(keyword)
                
                formatted_entry = {
                    "timestamp": readable_time,
                    "timestamp_ns": timestamp_ns,
                    "line": log_line,
                    "labels": stream_labels,
                    "matched_keywords": matched_keywords,
                    "context": _extract_context(log_line, keywords)
                }
                
                formatted_entries.append(formatted_entry)
    
    # Sort by timestamp (newest first)
    formatted_entries.sort(
        key=lambda x: int(x["timestamp_ns"]), 
        reverse=True
    )
    
    return formatted_entries


def _extract_context(log_line: str, keywords: List[str], context_chars: int = 100) -> List[Dict[str, str]]:
    """
    Extract context around matched keywords in the log line.
    
    Args:
        log_line: The log line text
        keywords: Keywords to find context for
        context_chars: Number of characters to include around each match
        
    Returns:
        List of context snippets with keyword positions
    """
    contexts = []
    log_lower = log_line.lower()
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        start = 0
        
        while True:
            pos = log_lower.find(keyword_lower, start)
            if pos == -1:
                break
            
            # Calculate context boundaries
            context_start = max(0, pos - context_chars // 2)
            context_end = min(len(log_line), pos + len(keyword) + context_chars // 2)
            
            # Extract context
            context_text = log_line[context_start:context_end]
            
            # Add ellipsis if we're not at the beginning/end
            if context_start > 0:
                context_text = "..." + context_text
            if context_end < len(log_line):
                context_text = context_text + "..."
            
            contexts.append({
                "keyword": keyword,
                "context": context_text,
                "position": pos
            })
            
            start = pos + len(keyword)
    
    return contexts


def _deduplicate_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate entries based on timestamp and log line.
    
    Args:
        entries: List of log entries
        
    Returns:
        Deduplicated list of entries
    """
    seen = set()
    unique_entries = []
    
    for entry in entries:
        # Create a unique key based on timestamp and log line
        key = (entry["timestamp_ns"], entry["line"])
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)
    
    # Sort by timestamp (newest first)
    unique_entries.sort(
        key=lambda x: int(x["timestamp_ns"]), 
        reverse=True
    )
    
    return unique_entries


def create_search_logs_tool() -> Tool:
    """Create the MCP tool definition for search_logs."""
    return Tool(
        name="search_logs",
        description="Search logs using keywords with support for multiple search terms and logical operators",
        inputSchema={
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of keywords to search for in log messages",
                    "minItems": 1
                },
                "labels": {
                    "type": "object",
                    "description": "Optional label filters as key-value pairs",
                    "additionalProperties": {"type": "string"}
                },
                "start": {
                    "type": "string",
                    "description": "Start time for search range (ISO format, Unix timestamp, or relative time like '5m')"
                },
                "end": {
                    "type": "string",
                    "description": "End time for search range (ISO format, Unix timestamp, or relative time like '1h')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log entries to return",
                    "minimum": 1,
                    "maximum": 5000,
                    "default": 100
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether the search should be case sensitive",
                    "default": False
                },
                "operator": {
                    "type": "string",
                    "description": "Logical operator for multiple keywords",
                    "enum": ["AND", "OR"],
                    "default": "AND"
                }
            },
            "required": ["keywords"]
        }
    )