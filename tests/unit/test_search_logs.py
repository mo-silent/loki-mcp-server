"""Unit tests for search_logs tool."""

import pytest
from unittest.mock import AsyncMock, patch

from app.tools.search_logs import (
    SearchLogsParams,
    SearchLogsResult,
    search_logs_tool,
    _format_search_results,
    _extract_context,
    _deduplicate_entries,
    create_search_logs_tool
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


@pytest.fixture
def sample_loki_response():
    """Sample Loki API response with search results."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "job": "web-server",
                        "level": "error"
                    },
                    "values": [
                        ["1640995200000000000", "ERROR: Database connection failed"],
                        ["1640995100000000000", "ERROR: Authentication error occurred"]
                    ]
                },
                {
                    "stream": {
                        "job": "web-server",
                        "level": "info"
                    },
                    "values": [
                        ["1640995150000000000", "INFO: User login successful"]
                    ]
                }
            ]
        }
    }


class TestSearchLogsParams:
    """Test SearchLogsParams validation."""
    
    def test_valid_params(self):
        """Test valid parameter creation."""
        params = SearchLogsParams(
            keywords=["error", "failed"],
            labels={"job": "web-server"},
            start="1h",
            end="now",
            limit=50,
            case_sensitive=True,
            operator="OR"
        )
        
        assert params.keywords == ["error", "failed"]
        assert params.labels == {"job": "web-server"}
        assert params.start == "1h"
        assert params.end == "now"
        assert params.limit == 50
        assert params.case_sensitive is True
        assert params.operator == "OR"
    
    def test_default_values(self):
        """Test default parameter values."""
        params = SearchLogsParams(keywords=["error"])
        
        assert params.keywords == ["error"]
        assert params.labels is None
        assert params.start is None
        assert params.end is None
        assert params.limit == 100
        assert params.case_sensitive is False
        assert params.operator == "AND"
    
    def test_invalid_operator(self):
        """Test invalid operator validation."""
        with pytest.raises(ValueError, match="Operator must be"):
            SearchLogsParams(keywords=["error"], operator="INVALID")
    
    def test_empty_keywords(self):
        """Test empty keywords validation."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchLogsParams(keywords=[])
    
    def test_whitespace_keywords_filtered(self):
        """Test that whitespace-only keywords are filtered out."""
        params = SearchLogsParams(keywords=["error", "  ", "", "failed", "\t"])
        assert params.keywords == ["error", "failed"]
    
    def test_all_empty_keywords(self):
        """Test validation when all keywords are empty."""
        with pytest.raises(ValueError, match="At least one non-empty keyword"):
            SearchLogsParams(keywords=["", "  ", "\t"])
    
    def test_limit_bounds(self):
        """Test limit boundary validation."""
        # Valid limits
        SearchLogsParams(keywords=["error"], limit=1)
        SearchLogsParams(keywords=["error"], limit=5000)
        
        # Invalid limits
        with pytest.raises(ValueError):
            SearchLogsParams(keywords=["error"], limit=0)
        
        with pytest.raises(ValueError):
            SearchLogsParams(keywords=["error"], limit=5001)


class TestFormatSearchResults:
    """Test search result formatting."""
    
    def test_format_with_keywords(self, sample_loki_response):
        """Test formatting with keyword matching."""
        keywords = ["error", "failed"]
        formatted = _format_search_results(sample_loki_response, keywords)
        
        assert len(formatted) == 3
        
        # Check that entries have search-specific fields
        for entry in formatted:
            assert "matched_keywords" in entry
            assert "context" in entry
            assert "timestamp" in entry
            assert "line" in entry
            assert "labels" in entry
        
        # Check keyword matching
        error_entries = [e for e in formatted if "error" in e["line"].lower()]
        assert len(error_entries) == 2
        
        for entry in error_entries:
            assert "error" in entry["matched_keywords"]
    
    def test_format_empty_response(self):
        """Test formatting of empty response."""
        empty_response = {
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": []
            }
        }
        
        formatted = _format_search_results(empty_response, ["error"])
        assert formatted == []
    
    def test_timestamp_sorting(self):
        """Test that entries are sorted by timestamp (newest first)."""
        response = {
            "data": {
                "result": [
                    {
                        "stream": {"job": "test"},
                        "values": [
                            ["1640995100000000000", "Older error message"],
                            ["1640995200000000000", "Newer error message"],
                            ["1640995150000000000", "Middle error message"]
                        ]
                    }
                ]
            }
        }
        
        formatted = _format_search_results(response, ["error"])
        
        assert len(formatted) == 3
        assert "Newer" in formatted[0]["line"]
        assert "Middle" in formatted[1]["line"]
        assert "Older" in formatted[2]["line"]


class TestExtractContext:
    """Test context extraction around keywords."""
    
    def test_extract_single_keyword(self):
        """Test context extraction for single keyword."""
        log_line = "This is a test error message with some context around it"
        keywords = ["error"]
        
        contexts = _extract_context(log_line, keywords, context_chars=20)
        
        assert len(contexts) == 1
        context = contexts[0]
        assert context["keyword"] == "error"
        assert "error" in context["context"]
        assert context["position"] == 15  # Position of "error" in the string
    
    def test_extract_multiple_keywords(self):
        """Test context extraction for multiple keywords."""
        log_line = "Database error occurred during user authentication process"
        keywords = ["error", "user"]
        
        contexts = _extract_context(log_line, keywords, context_chars=20)
        
        assert len(contexts) == 2
        
        # Check that both keywords are found
        found_keywords = [c["keyword"] for c in contexts]
        assert "error" in found_keywords
        assert "user" in found_keywords
    
    def test_extract_with_ellipsis(self):
        """Test context extraction with ellipsis for long lines."""
        log_line = "A" * 200 + "error" + "B" * 200
        keywords = ["error"]
        
        contexts = _extract_context(log_line, keywords, context_chars=20)
        
        assert len(contexts) == 1
        context = contexts[0]
        assert context["context"].startswith("...")
        assert context["context"].endswith("...")
        assert "error" in context["context"]
    
    def test_extract_no_matches(self):
        """Test context extraction when no keywords match."""
        log_line = "This is a normal log message"
        keywords = ["error", "failed"]
        
        contexts = _extract_context(log_line, keywords)
        assert contexts == []


class TestDeduplicateEntries:
    """Test entry deduplication."""
    
    def test_deduplicate_identical_entries(self):
        """Test deduplication of identical entries."""
        entries = [
            {
                "timestamp_ns": "1640995200000000000",
                "line": "Test message",
                "labels": {"job": "test"}
            },
            {
                "timestamp_ns": "1640995200000000000",
                "line": "Test message",
                "labels": {"job": "test"}
            },
            {
                "timestamp_ns": "1640995100000000000",
                "line": "Different message",
                "labels": {"job": "test"}
            }
        ]
        
        unique = _deduplicate_entries(entries)
        
        assert len(unique) == 2
        assert unique[0]["line"] == "Test message"
        assert unique[1]["line"] == "Different message"
    
    def test_deduplicate_preserves_order(self):
        """Test that deduplication preserves timestamp order."""
        entries = [
            {
                "timestamp_ns": "1640995100000000000",
                "line": "Older message",
                "labels": {}
            },
            {
                "timestamp_ns": "1640995200000000000",
                "line": "Newer message",
                "labels": {}
            }
        ]
        
        unique = _deduplicate_entries(entries)
        
        assert len(unique) == 2
        # Should be sorted newest first
        assert unique[0]["line"] == "Newer message"
        assert unique[1]["line"] == "Older message"


@pytest.mark.asyncio
class TestSearchLogsTool:
    """Test search_logs_tool function."""
    
    async def test_successful_and_search(self, mock_config, sample_loki_response):
        """Test successful AND search execution."""
        params = SearchLogsParams(
            keywords=["error"],
            labels={"job": "web-server"},
            start="1h",
            end="now"
        )
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_range.return_value = sample_loki_response
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.total_entries == 3
            assert result.search_terms == ["error"]
            assert result.labels_filter == {"job": "web-server"}
            assert result.error is None
            
            # Verify client was called correctly
            mock_client.query_range.assert_called_once()
    
    async def test_successful_or_search(self, mock_config, sample_loki_response):
        """Test successful OR search execution."""
        params = SearchLogsParams(
            keywords=["error", "info"],
            operator="OR"
        )
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_instant.return_value = sample_loki_response
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.search_terms == ["error", "info"]
            assert "OR combination" in result.query_used
            
            # Should be called twice for OR operation
            assert mock_client.query_instant.call_count == 2
    
    async def test_instant_query_without_time_range(self, mock_config, sample_loki_response):
        """Test instant query when no time range is specified."""
        params = SearchLogsParams(keywords=["error"])
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_instant.return_value = sample_loki_response
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "success"
            mock_client.query_instant.assert_called_once()
            mock_client.query_range.assert_not_called()
    
    async def test_loki_client_error(self, mock_config):
        """Test handling of Loki client errors."""
        params = SearchLogsParams(keywords=["error"])
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_instant.side_effect = LokiClientError("Connection failed")
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.total_entries == 0
            assert result.error == "Connection failed"
    
    async def test_unexpected_error(self, mock_config):
        """Test handling of unexpected errors."""
        params = SearchLogsParams(keywords=["error"])
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Unexpected error")
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "error"
            assert result.total_entries == 0
            assert "Unexpected error" in result.error
    
    async def test_limit_enforcement(self, mock_config):
        """Test that result limit is enforced."""
        # Create a response with many entries
        large_response = {
            "data": {
                "result": [
                    {
                        "stream": {"job": "test"},
                        "values": [[f"164099{i:04d}000000000", f"Message {i}"] for i in range(200)]
                    }
                ]
            }
        }
        
        params = SearchLogsParams(keywords=["Message"], limit=50)
        
        with patch('app.tools.search_logs.EnhancedLokiClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.query_instant.return_value = large_response
            
            result = await search_logs_tool(params, mock_config)
            
            assert result.status == "success"
            assert result.total_entries == 50  # Should be limited


class TestCreateSearchLogsTool:
    """Test MCP tool creation."""
    
    def test_tool_creation(self):
        """Test that tool is created with correct schema."""
        tool = create_search_logs_tool()
        
        assert tool.name == "search_logs"
        assert "keyword" in tool.description.lower()
        
        # Check schema structure
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "keywords" in schema["properties"]
        assert "labels" in schema["properties"]
        assert "operator" in schema["properties"]
        
        # Check required fields
        assert schema["required"] == ["keywords"]
        
        # Check keywords field
        keywords_field = schema["properties"]["keywords"]
        assert keywords_field["type"] == "array"
        assert keywords_field["minItems"] == 1
        
        # Check operator field
        operator_field = schema["properties"]["operator"]
        assert operator_field["enum"] == ["AND", "OR"]
        assert operator_field["default"] == "AND"