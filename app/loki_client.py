"""HTTP client for Loki API communication."""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
import structlog

from .config import LokiConfig

logger = structlog.get_logger(__name__)


class LokiClientError(Exception):
    """Base exception for Loki client errors."""
    pass


class LokiConnectionError(LokiClientError):
    """Raised when connection to Loki fails."""
    pass


class LokiAuthenticationError(LokiClientError):
    """Raised when authentication fails."""
    pass


class LokiQueryError(LokiClientError):
    """Raised when query execution fails."""
    pass


class LokiRateLimitError(LokiClientError):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """Rate limiter for controlling request frequency."""
    
    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []
    
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        
        This method will block if the rate limit would be exceeded.
        """
        now = time.time()
        
        # Clean up old requests outside the time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        # If we're at the limit, wait until we can make another request
        if len(self.requests) >= self.max_requests:
            # Calculate how long to wait
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                # Update now after sleeping
                now = time.time()
                # Clean up again after waiting
                self.requests = [req_time for req_time in self.requests 
                               if now - req_time < self.time_window]
        
        # Record this request
        self.requests.append(now)


class LokiQueryError(LokiClientError):
    """Raised when query execution fails."""
    pass


class LokiRateLimitError(LokiClientError):
    """Raised when rate limit is exceeded."""
    pass


class LokiClient:
    """HTTP client for Grafana Loki API."""

    def __init__(self, config: LokiConfig):
        """Initialize Loki client with configuration.
        
        Args:
            config: Loki configuration object
        """
        self.config = config
        self._session: Optional[requests.Session] = None
        self._rate_limiter = RateLimiter(
            max_requests=config.rate_limit_requests,
            time_window=config.rate_limit_period
        )
        # Statistics tracking
        self._total_operations = 0
        self._total_errors = 0
        self._error_counts_by_category = {}

        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is initialized."""
        if self._session is None:
            self._session = requests.Session()
            
            # Set headers
            self._session.headers.update({
                "User-Agent": "loki-mcp-server/0.1.0",
                "Accept": "application/json",
                "Content-Type": "application/json"
            })
            
            # Set authentication
            if self.config.username and self.config.password:
                self._session.auth = (self.config.username, self.config.password)
            elif self.config.bearer_token:
                self._session.headers["Authorization"] = f"Bearer {self.config.bearer_token}"

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None

    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request to Loki API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            **kwargs: Additional arguments for requests
            
        Returns:
            Response data as dictionary
            
        Raises:
            LokiConnectionError: When connection fails
            LokiAuthenticationError: When authentication fails
            LokiQueryError: When query fails
            LokiRateLimitError: When rate limited
        """
        await self._ensure_session()
        await self._rate_limiter.acquire()
        
        url = urljoin(self.config.url.rstrip('/') + '/', endpoint.lstrip('/'))
        
        logger.debug(
            "Making request to Loki",
            method=method,
            url=url
        )
        
        # Track operation
        self._total_operations += 1
        
        # Use asyncio.to_thread to run the synchronous requests call in a thread
        def make_sync_request():
            return self._session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.config.timeout,
                **kwargs
            )
        
        try:
            response = await asyncio.to_thread(make_sync_request)
        except requests.exceptions.ConnectionError as e:
            self._total_errors += 1
            self._error_counts_by_category["connection"] = self._error_counts_by_category.get("connection", 0) + 1
            raise LokiConnectionError(f"Failed to connect to Loki: {e}")
        except requests.exceptions.Timeout as e:
            self._total_errors += 1
            self._error_counts_by_category["timeout"] = self._error_counts_by_category.get("timeout", 0) + 1
            raise LokiConnectionError(f"Request to Loki timed out: {e}")
        except requests.exceptions.RequestException as e:
            self._total_errors += 1
            self._error_counts_by_category["request"] = self._error_counts_by_category.get("request", 0) + 1
            raise LokiConnectionError(f"Request to Loki failed: {e}")
        
        # Handle different HTTP status codes
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            self._total_errors += 1
            self._error_counts_by_category["authentication"] = self._error_counts_by_category.get("authentication", 0) + 1
            raise LokiAuthenticationError(
                "Authentication failed. Check your credentials."
            )
        elif response.status_code == 429:
            self._total_errors += 1
            self._error_counts_by_category["rate_limit"] = self._error_counts_by_category.get("rate_limit", 0) + 1
            raise LokiRateLimitError(
                "Rate limit exceeded. Please reduce request frequency."
            )
        elif response.status_code >= 400:
            self._total_errors += 1
            self._error_counts_by_category["query"] = self._error_counts_by_category.get("query", 0) + 1
            error_msg = f"Loki API error: {response.status_code}"
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_msg += f" - {error_data['error']}"
            except Exception:
                error_msg += f" - {response.text}"
            
            raise LokiQueryError(error_msg)



    async def query_range(
        self,
        query: str,
        start: str,
        end: str,
        limit: Optional[int] = None,
        direction: str = "backward",
        step: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a range query against Loki.
        
        Args:
            query: LogQL query string
            start: Start time (RFC3339 or Unix timestamp)
            end: End time (RFC3339 or Unix timestamp)
            limit: Maximum number of entries to return
            direction: Query direction ("forward" or "backward")
            step: Query resolution step for metric queries
            
        Returns:
            Query results from Loki
            
        Raises:
            LokiQueryError: When query fails
        """
        params = {
            "query": query,
            "start": start,
            "end": end,
            "direction": direction
        }
        
        if limit is not None:
            params["limit"] = limit
        if step is not None:
            params["step"] = step
            
        logger.info("Executing range query", query=query, start=start, end=end)
        return await self._make_request("GET", "/loki/api/v1/query_range", params=params)

    async def query_instant(
        self,
        query: str,
        time: Optional[str] = None,
        limit: Optional[int] = None,
        direction: str = "backward"
    ) -> Dict[str, Any]:
        """Execute an instant query against Loki.
        
        Args:
            query: LogQL query string
            time: Query time (RFC3339 or Unix timestamp), defaults to now
            limit: Maximum number of entries to return
            direction: Query direction ("forward" or "backward")
            
        Returns:
            Query results from Loki
            
        Raises:
            LokiQueryError: When query fails
        """
        params = {
            "query": query,
            "direction": direction
        }
        
        if time is not None:
            params["time"] = time
        if limit is not None:
            params["limit"] = limit
            
        logger.info("Executing instant query", query=query, time=time)
        return await self._make_request("GET", "/loki/api/v1/query", params=params)

    async def label_names(self, start: Optional[str] = None, end: Optional[str] = None) -> List[str]:
        """Get list of label names.
        
        Args:
            start: Start time for label query
            end: End time for label query
            
        Returns:
            List of label names
            
        Raises:
            LokiQueryError: When query fails
        """
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
            
        logger.info("Fetching label names")
        response = await self._make_request("GET", "/loki/api/v1/labels", params=params)
        return response.get("data", [])

    async def label_values(
        self, 
        label: str, 
        start: Optional[str] = None, 
        end: Optional[str] = None
    ) -> List[str]:
        """Get list of label values for a specific label.
        
        Args:
            label: Label name
            start: Start time for label query
            end: End time for label query
            
        Returns:
            List of label values
            
        Raises:
            LokiQueryError: When query fails
        """
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
            
        logger.info("Fetching label values", label=label)
        response = await self._make_request(
            "GET", 
            f"/loki/api/v1/label/{label}/values", 
            params=params
        )
        return response.get("data", [])

    async def series(
        self,
        match: Union[str, List[str]],
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Get list of time series that match label selectors.
        
        Args:
            match: Label selector(s) to match series
            start: Start time for series query
            end: End time for series query
            
        Returns:
            List of series with their labels
            
        Raises:
            LokiQueryError: When query fails
        """
        params = {}
        
        if isinstance(match, str):
            params["match[]"] = match
        else:
            params["match[]"] = match
            
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
            
        logger.info("Fetching series", match=match)
        response = await self._make_request("GET", "/loki/api/v1/series", params=params)
        return response.get("data", [])

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for this client.
        
        Returns:
            Dictionary containing error statistics
        """
        return {
            "total_operations": self._total_operations,
            "total_errors": self._total_errors,
            "error_counts_by_category": self._error_counts_by_category.copy(),
            "operation_stats": {
                "success_rate": (self._total_operations - self._total_errors) / max(self._total_operations, 1),
                "error_rate": self._total_errors / max(self._total_operations, 1)
            }
        }


class RateLimiter:
    """Simple rate limiter for HTTP requests."""
    
    def __init__(self, max_requests: int, time_window: int):
        """Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire permission to make a request, waiting if necessary."""
        async with self._lock:
            now = time.time()
            
            # Remove old requests outside the time window
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # If we're at the limit, wait until we can make another request
            if len(self.requests) >= self.max_requests:
                oldest_request = min(self.requests)
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    logger.debug("Rate limit reached, waiting", wait_time=wait_time)
                    await asyncio.sleep(wait_time)
            
            # Record this request
            self.requests.append(now)