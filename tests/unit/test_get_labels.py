"""Unit tests for get_labels tool."""

import pytest
import time
from unittest.mock import AsyncMock, patch

from app.tools.get_labels import (
    GetLabelsParams,
    GetLabelsResult,
    get_labels_tool,
    clear_label_cache,
    get_cache_stats,
    _get_cache_key,
    _is_cache_valid,
    _cache_labels,
    _get_cached_labels,
    create_get_labels_tool
)
from app.config import LokiConfig
from app.loki_client import LokiClientError


@pytest.fixture
def mock_config():
    """Create a mock Loki configuration."""
    return LokiConfig(
        url="http://localhost:3100",
        timeout=30,
        max_retries=3
    )


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    clear_label_cache()
    yield
    clear_label_cache()


class TestGetLabelsParams:
    """Test GetLabelsParams validation."""
    
    def test_valid_params(self):
        """Test valid parameter creation."""
        params = GetLabelsParams(
            label_name="job",
            start="1h",
            end="now",
            use_cache=False
        )
        
        assert params.label_name == "job"
        assert params.start == "1h"
        assert params.end == "now"
        assert params.use_cache is False
    
    def test_default_values(self):
        """Test default parameter values."""
        params = GetLabelsParams()
        
        assert params.label_name is None
        assert params.start is None
        assert params.end is None
        assert params.use_cache is True
    
    def test_label_names_query(self):
        """Test parameters for getting all label names."""
        params = GetLabelsParams()
        assert params.label_name is None  # Should get all label names
    
    def test_label_values_query(self):
        """Test parameters for getting specific label values."""
        params = GetLabelsParams(label_name="job")
        assert params.label_name == "job"  # Should get values for 'job' label


class TestCacheUtilities:
    """Test cache utility functions."""
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        key1 = _get_cache_key(None, None, None)
        key2 = _get_cache_key("job", "1h", "now")
        key3 = _get_cache_key("level", None, "now")
        
        assert key1 == "all:none:none"
        assert key2 == "job:1h:now"
        assert key3 == "level:none:now"
        
        # Same parameters should generate same key
        assert _get_cache_key("job", "1h", "now") == key2
    
    def test_cache_storage_and_retrieval(self):
        """Test caching and retrieving labels."""
        cache_key = "test:key"
        labels = ["job", "level", "instance"]
        
        # Cache labels
        _cache_labels(cache_key, labels, None)
        
        # Retrieve from cache
        cached = _get_cached_labels(cache_key)
        
        assert cached is not None
        assert cached["labels"] == labels
        assert cached["label_name"] is None
        assert "timestamp" in cached
    
    def test_cache_expiration(self):
        """Test cache expiration logic."""
        # Create a cache entry with old timestamp
        old_entry = {
            "labels": ["job"],
            "label_name": None,
            "timestamp": time.time() - 400  # 400 seconds ago (> 300 TTL)
        }
        
        # Test expiration check
        assert not _is_cache_valid(old_entry)
        
        # Create a fresh entry
        fresh_entry = {
            "labels": ["job"],
            "label_name": None,
            "timestamp": time.time()
        }
        
        assert _is_cache_valid(fresh_entry)
    
    def test_cache_miss_on_expired_entry(self):
        """Test that expired entries are removed and return None."""
        cache_key = "expired:key"
        
        # Manually add expired entry
        from app.tools.get_labels import _label_cache
        _label_cache[cache_key] = {
            "labels": ["job"],
            "label_name": None,
            "timestamp": time.time() - 400  # Expired
        }
        
        # Should return None and remove expired entry
        result = _get_cached_labels(cache_key)
        assert result is None
        assert cache_key not in _label_cache


class TestCacheManagement:
    """Test cache management functions."""
    
    def test_clear_cache(self):
        """Test cache clearing."""
        # Add some entries
        _cache_labels("key1", ["job"], None)
        _cache_labels("key2", ["level"], "level")
        
        # Verify entries exist
        assert _get_cached_labels("key1") is not None
        assert _get_cached_labels("key2") is not None
        
        # Clear cache
        clear_label_cache()
        
        # Verify entries are gone
        assert _get_cached_labels("key1") is None
        assert _get_cached_labels("key2") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        # Start with empty cache
        stats = get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0
        assert stats["expired_entries"] == 0
        
        # Add valid entry
        _cache_labels("valid", ["job"], None)
        
        # Add expired entry manually
        from app.tools.get_labels import _label_cache
        _label_cache["expired"] = {
            "labels": ["level"],
            "label_name": None,
            "timestamp": time.time() - 400  # Expired
        }
        
        stats = get_cache_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 1
        assert stats["expired_entries"] == 1


@pytest.mark.asyncio
class TestGetLabelsTool:
    """Test get_labels_tool function."""
    
    async def test_get_label_names_success(self, mock_config):
        """Test successful retrieval of label names."""
        params = GetLabelsParams(use_cache=False)  # Disable cache for test
        
        mock_labels = ["job", "level", "instance", "service"]
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_names.return_value = mock_labels
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.label_type == "names"
            assert result.label_name is None
            assert result.labels == sorted(mock_labels)
            assert result.total_count == 4
            assert result.cached is False
            assert result.error is None
            
            # Verify client was called correctly
            mock_client.label_names.assert_called_once_with(
                start=None,
                end=None
            )
    
    async def test_get_label_values_success(self, mock_config):
        """Test successful retrieval of label values."""
        params = GetLabelsParams(
            label_name="job",
            start="1h",
            end="now",
            use_cache=False
        )
        
        mock_values = ["web-server", "api-server", "worker"]
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_values.return_value = mock_values
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.label_type == "values"
            assert result.label_name == "job"
            assert result.labels == sorted(mock_values)
            assert result.total_count == 3
            assert result.cached is False
            
            # Verify client was called correctly
            mock_client.label_values.assert_called_once_with(
                label="job",
                start="1h",
                end="now"
            )
    
    async def test_cache_hit(self, mock_config):
        """Test cache hit scenario."""
        params = GetLabelsParams(label_name="job", use_cache=True)
        
        # Pre-populate cache
        cache_key = _get_cache_key("job", None, None)
        cached_labels = ["web-server", "api-server"]
        _cache_labels(cache_key, cached_labels, "job")
        
        # Should not call Loki client
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.labels == cached_labels
            assert result.cached is True
            
            # Client should not be called
            mock_client_class.assert_not_called()
    
    async def test_cache_miss_then_cache(self, mock_config):
        """Test cache miss followed by caching."""
        params = GetLabelsParams(label_name="level", use_cache=True)
        
        mock_values = ["error", "warn", "info", "debug"]
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_values.return_value = mock_values
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.cached is False
            
            # Verify data was cached
            cache_key = _get_cache_key("level", None, None)
            cached = _get_cached_labels(cache_key)
            assert cached is not None
            assert cached["labels"] == sorted(mock_values)
    
    async def test_empty_labels_response(self, mock_config):
        """Test handling of empty labels response."""
        params = GetLabelsParams(use_cache=False)
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_names.return_value = []
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.labels == []
            assert result.total_count == 0
    
    async def test_loki_client_error(self, mock_config):
        """Test handling of Loki client errors."""
        params = GetLabelsParams(use_cache=False)
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_names.side_effect = LokiClientError("Connection failed")
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.labels == []
            assert result.total_count == 0
            assert result.error == "Connection failed"
            assert result.cached is False
    
    async def test_unexpected_error(self, mock_config):
        """Test handling of unexpected errors."""
        params = GetLabelsParams(use_cache=False)
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.labels == []
            assert result.total_count == 0
            assert "Unexpected error" in result.error
    
    async def test_cache_disabled(self, mock_config):
        """Test behavior when cache is disabled."""
        params = GetLabelsParams(use_cache=False)
        
        # Pre-populate cache (should be ignored)
        cache_key = _get_cache_key(None, None, None)
        _cache_labels(cache_key, ["cached"], None)
        
        mock_labels = ["fresh", "data"]
        
        with patch('app.tools.get_labels.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.label_names.return_value = mock_labels
            
            result = await get_labels_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.labels == sorted(mock_labels)
            assert result.cached is False
            
            # Should have called client despite cache
            mock_client.label_names.assert_called_once()


class TestCreateGetLabelsTool:
    """Test MCP tool creation."""
    
    def test_tool_creation(self):
        """Test that tool is created with correct schema."""
        tool = create_get_labels_tool()
        
        assert tool.name == "get_labels"
        assert "label" in tool.description.lower()
        
        # Check schema structure
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "label_name" in schema["properties"]
        assert "start" in schema["properties"]
        assert "end" in schema["properties"]
        assert "use_cache" in schema["properties"]
        
        # Check that no fields are required
        assert schema["required"] == []
        
        # Check use_cache field
        cache_field = schema["properties"]["use_cache"]
        assert cache_field["type"] == "boolean"
        assert cache_field["default"] is True
        
        # Check label_name field
        label_name_field = schema["properties"]["label_name"]
        assert label_name_field["type"] == "string"