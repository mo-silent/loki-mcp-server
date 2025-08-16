"""Enhanced Loki client with comprehensive error handling."""

from typing import Any, Dict, List, Optional, Union

import structlog

from .config import LokiConfig
from .loki_client import LokiClient
from .error_handler import ErrorHandler, ErrorContext

logger = structlog.get_logger(__name__)


class EnhancedLokiClient:
    """Loki client with enhanced error handling and retry logic."""
    
    def __init__(self, config: LokiConfig):
        """
        Initialize enhanced Loki client.
        
        Args:
            config: Loki configuration
        """
        self.config = config
        self._client = LokiClient(config)
        self._error_handler = ErrorHandler(
            max_retries=config.max_retries,
            enable_circuit_breaker=True
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def query_range(
        self,
        query: str,
        start: str,
        end: str,
        limit: Optional[int] = None,
        direction: str = "backward",
        step: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a range query against Loki with error handling."""
        context = ErrorContext(
            operation="query_range",
            parameters={
                "query": query,
                "start": start,
                "end": end,
                "limit": limit,
                "direction": direction,
                "step": step
            },
            max_attempts=self.config.max_retries + 1,
            loki_url=self.config.url
        )
        
        return await self._error_handler.handle_with_retry(
            self._client.query_range,
            context,
            query,
            start,
            end,
            limit,
            direction,
            step
        )
    
    async def query_instant(
        self,
        query: str,
        time: Optional[str] = None,
        limit: Optional[int] = None,
        direction: str = "backward"
    ) -> Dict[str, Any]:
        """Execute an instant query against Loki with error handling."""
        context = ErrorContext(
            operation="query_instant",
            parameters={
                "query": query,
                "time": time,
                "limit": limit,
                "direction": direction
            },
            max_attempts=self.config.max_retries + 1,
            loki_url=self.config.url
        )
        
        return await self._error_handler.handle_with_retry(
            self._client.query_instant,
            context,
            query,
            time,
            limit,
            direction
        )
    
    async def label_names(
        self, 
        start: Optional[str] = None, 
        end: Optional[str] = None
    ) -> List[str]:
        """Get list of label names with error handling."""
        context = ErrorContext(
            operation="label_names",
            parameters={"start": start, "end": end},
            max_attempts=self.config.max_retries + 1,
            loki_url=self.config.url
        )
        
        return await self._error_handler.handle_with_retry(
            self._client.label_names,
            context,
            start,
            end
        )
    
    async def label_values(
        self, 
        label: str, 
        start: Optional[str] = None, 
        end: Optional[str] = None
    ) -> List[str]:
        """Get list of label values for a specific label with error handling."""
        context = ErrorContext(
            operation="label_values",
            parameters={"label": label, "start": start, "end": end},
            max_attempts=self.config.max_retries + 1,
            loki_url=self.config.url
        )
        
        return await self._error_handler.handle_with_retry(
            self._client.label_values,
            context,
            label,
            start,
            end
        )
    
    async def series(
        self,
        match: Union[str, List[str]],
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Get list of time series that match label selectors with error handling."""
        context = ErrorContext(
            operation="series",
            parameters={"match": match, "start": start, "end": end},
            max_attempts=self.config.max_retries + 1,
            loki_url=self.config.url
        )
        
        return await self._error_handler.handle_with_retry(
            self._client.series,
            context,
            match,
            start,
            end
        )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring and debugging."""
        return self._error_handler.get_error_statistics()