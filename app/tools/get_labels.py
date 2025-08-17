"""Tool for retrieving available log labels."""

from typing import Any, Dict, List, Optional
import time
from datetime import datetime, timezone

import structlog
from mcp import Tool
from pydantic import BaseModel, Field

from ..enhanced_client import EnhancedLokiClient
from ..loki_client import LokiClientError
from ..config import LokiConfig
from ..time_utils import convert_time

logger = structlog.get_logger(__name__)


class GetLabelsParams(BaseModel):
    """Parameters for the get_labels tool."""
    
    label_name: Optional[str] = Field(
        default=None,
        description="Specific label name to get values for. If not provided, returns all label names."
    )
    start: Optional[str] = Field(
        default=None,
        description="Start time for label query (ISO format, Unix timestamp, or relative time like '5m')"
    )
    end: Optional[str] = Field(
        default=None,
        description="End time for label query (ISO format, Unix timestamp, or relative time like '1h')"
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached label information to improve performance"
    )


class GetLabelsResult(BaseModel):
    """Result from get_labels tool."""
    
    status: str
    label_type: str  # "names" or "values"
    label_name: Optional[str]
    labels: List[str]
    total_count: int
    time_range: Dict[str, Optional[str]]
    cached: bool
    error: Optional[str] = None


# Simple in-memory cache for label information
_label_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 300  # 5 minutes


def _get_cache_key(label_name: Optional[str], start: Optional[str], end: Optional[str]) -> str:
    """Generate cache key for label query."""
    return f"{label_name or 'all'}:{start or 'none'}:{end or 'none'}"


def _is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid."""
    return time.time() - cache_entry["timestamp"] < _cache_ttl


def _cache_labels(cache_key: str, labels: List[str], label_name: Optional[str]) -> None:
    """Cache label information."""
    _label_cache[cache_key] = {
        "labels": labels,
        "label_name": label_name,
        "timestamp": time.time()
    }


def _get_cached_labels(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached label information if valid."""
    if cache_key in _label_cache:
        cache_entry = _label_cache[cache_key]
        if _is_cache_valid(cache_entry):
            return cache_entry
        else:
            # Remove expired cache entry
            del _label_cache[cache_key]
    return None


def clear_label_cache() -> None:
    """Clear the label cache. Useful for testing."""
    global _label_cache
    _label_cache.clear()


async def get_labels_tool(
    params: GetLabelsParams,
    config: LokiConfig
) -> GetLabelsResult:
    """
    Retrieve available log labels or label values from Loki.
    
    Args:
        params: Label query parameters
        config: Loki configuration
        
    Returns:
        Formatted label information
    """
    logger.info("Retrieving labels", label_name=params.label_name)
    
    # Check cache first if enabled
    cache_key = _get_cache_key(params.label_name, params.start, params.end)
    cached_result = None
    
    if params.use_cache:
        cached_result = _get_cached_labels(cache_key)
        if cached_result:
            logger.info("Using cached label data", cache_key=cache_key)
            return GetLabelsResult(
                status="success",
                label_type="values" if params.label_name else "names",
                label_name=params.label_name,
                labels=cached_result["labels"],
                total_count=len(cached_result["labels"]),
                time_range={
                    "start": params.start,
                    "end": params.end
                },
                cached=True
            )
    
    try:
        async with EnhancedLokiClient(config) as client:
            # Convert time parameters to proper format
            start_time = convert_time(params.start)
            end_time = convert_time(params.end)
            
            if params.label_name:
                # Get values for specific label
                labels = await client.label_values(
                    label=params.label_name,
                    start=start_time,
                    end=end_time
                )
                label_type = "values"
            else:
                # Get all label names
                labels = await client.label_names(
                    start=start_time,
                    end=end_time
                )
                label_type = "names"
            
            # Sort labels for consistent output
            sorted_labels = sorted(labels) if labels else []
            
            # Cache the result if caching is enabled
            if params.use_cache:
                _cache_labels(cache_key, sorted_labels, params.label_name)
            
            return GetLabelsResult(
                status="success",
                label_type=label_type,
                label_name=params.label_name,
                labels=sorted_labels,
                total_count=len(sorted_labels),
                time_range={
                    "start": params.start,
                    "end": params.end
                },
                cached=False
            )
            
    except LokiClientError as e:
        logger.error("Loki client error", error=str(e), label_name=params.label_name)
        return GetLabelsResult(
            status="error",
            label_type="values" if params.label_name else "names",
            label_name=params.label_name,
            labels=[],
            total_count=0,
            time_range={
                "start": params.start,
                "end": params.end
            },
            cached=False,
            error=str(e)
        )
    except Exception as e:
        logger.error("Unexpected error in get_labels", error=str(e), label_name=params.label_name)
        return GetLabelsResult(
            status="error",
            label_type="values" if params.label_name else "names",
            label_name=params.label_name,
            labels=[],
            total_count=0,
            time_range={
                "start": params.start,
                "end": params.end
            },
            cached=False,
            error=f"Unexpected error: {str(e)}"
        )


def clear_label_cache() -> None:
    """Clear the label cache. Useful for testing or manual cache invalidation."""
    global _label_cache
    _label_cache.clear()
    logger.info("Label cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    current_time = time.time()
    valid_entries = 0
    expired_entries = 0
    
    for cache_entry in _label_cache.values():
        if current_time - cache_entry["timestamp"] < _cache_ttl:
            valid_entries += 1
        else:
            expired_entries += 1
    
    return {
        "total_entries": len(_label_cache),
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "cache_ttl_seconds": _cache_ttl
    }


def create_get_labels_tool() -> Tool:
    """Create the MCP tool definition for get_labels."""
    return Tool(
        name="get_labels",
        description="Retrieve available log labels or values for a specific label from Loki",
        inputSchema={
            "type": "object",
            "properties": {
                "label_name": {
                    "type": "string",
                    "description": "Specific label name to get values for. If not provided, returns all label names."
                },
                "start": {
                    "type": "string",
                    "description": "Start time for label query (ISO format, Unix timestamp, or relative time like '5m')"
                },
                "end": {
                    "type": "string",
                    "description": "End time for label query (ISO format, Unix timestamp, or relative time like '1h')"
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use cached label information to improve performance",
                    "default": True
                }
            },
            "required": []
        }
    )