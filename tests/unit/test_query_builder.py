"""Unit tests for LogQL query builder."""

import pytest
import re
from app.query_builder import LogQLQueryBuilder, search_logs, search_pattern


class TestLogQLQueryBuilder:
    """Test cases for LogQLQueryBuilder class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = LogQLQueryBuilder()
    
    def test_build_search_query_single_keyword(self):
        """Test building search query with single keyword."""
        query = self.builder.build_search_query(["error"])
        expected = '{__name__=~".+"}|~ "(?i)error"'
        assert query == expected
    
    def test_build_search_query_multiple_keywords(self):
        """Test building search query with multiple keywords."""
        query = self.builder.build_search_query(["error", "timeout"])
        expected = '{__name__=~".+"}|~ "(?i)error"|~ "(?i)timeout"'
        assert query == expected
    
    def test_build_search_query_with_labels(self):
        """Test building search query with label filters."""
        labels = {"service": "api", "level": "error"}
        query = self.builder.build_search_query(["timeout"], labels)
        expected = '{service="api", level="error"}|~ "(?i)timeout"'
        assert query == expected
    
    def test_build_search_query_case_sensitive(self):
        """Test building case-sensitive search query."""
        query = self.builder.build_search_query(["Error"], case_sensitive=True)
        expected = '{__name__=~".+"}|~ "Error"'
        assert query == expected
    
    def test_build_search_query_escapes_special_chars(self):
        """Test that special regex characters are escaped in keywords."""
        query = self.builder.build_search_query(["error[123]"])
        expected = '{__name__=~".+"}|~ "(?i)error\\[123\\]"'
        assert query == expected
    
    def test_build_search_query_empty_keywords(self):
        """Test that empty keywords list raises ValueError."""
        with pytest.raises(ValueError, match="At least one keyword must be provided"):
            self.builder.build_search_query([])
    
    def test_build_search_query_whitespace_keywords(self):
        """Test that whitespace-only keywords are filtered out."""
        with pytest.raises(ValueError, match="No valid keywords provided"):
            self.builder.build_search_query(["", "  ", "\t"])
    
    def test_build_pattern_query_regex(self):
        """Test building pattern query with regex."""
        query = self.builder.build_pattern_query(r"error\d+", use_regex=True)
        expected = '{__name__=~".+"}|~ "error\\d+"'
        assert query == expected
    
    def test_build_pattern_query_literal(self):
        """Test building pattern query with literal matching."""
        query = self.builder.build_pattern_query("error[123]", use_regex=False)
        expected = '{__name__=~".+"}|~ "error\\[123\\]"'
        assert query == expected
    
    def test_build_pattern_query_with_labels(self):
        """Test building pattern query with label filters."""
        labels = {"app": "web"}
        query = self.builder.build_pattern_query("timeout", labels, use_regex=False)
        expected = '{app="web"}|~ "timeout"'
        assert query == expected
    
    def test_build_pattern_query_invalid_regex(self):
        """Test that invalid regex patterns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            self.builder.build_pattern_query("[invalid", use_regex=True)
    
    def test_build_pattern_query_empty_pattern(self):
        """Test that empty pattern raises ValueError."""
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            self.builder.build_pattern_query("")
    
    def test_build_time_range_query_basic(self):
        """Test building time range query with basic query."""
        base_query = '{service="api"}|~ "error"'
        query = self.builder.build_time_range_query(base_query)
        assert query == base_query
    
    def test_build_time_range_query_with_times(self):
        """Test building time range query with start and end times."""
        base_query = '{service="api"}|~ "error"'
        query = self.builder.build_time_range_query(
            base_query, 
            start="2023-01-01T00:00:00Z", 
            end="2023-01-01T23:59:59Z"
        )
        assert query == base_query
    
    def test_build_time_range_query_empty_base(self):
        """Test that empty base query raises ValueError."""
        with pytest.raises(ValueError, match="Base query cannot be empty"):
            self.builder.build_time_range_query("")
    
    def test_build_label_query(self):
        """Test building query with only label filters."""
        labels = {"service": "api", "env": "prod"}
        query = self.builder.build_label_query(labels)
        expected = '{service="api", env="prod"}'
        assert query == expected
    
    def test_build_label_query_empty_labels(self):
        """Test that empty labels dict raises ValueError."""
        with pytest.raises(ValueError, match="At least one label must be provided"):
            self.builder.build_label_query({})
    
    def test_build_label_selector_empty(self):
        """Test building empty label selector."""
        selector = self.builder._build_label_selector({})
        assert selector == '{__name__=~".+"}'
    
    def test_build_label_selector_single_label(self):
        """Test building label selector with single label."""
        selector = self.builder._build_label_selector({"service": "api"})
        assert selector == '{service="api"}'
    
    def test_build_label_selector_multiple_labels(self):
        """Test building label selector with multiple labels."""
        labels = {"service": "api", "level": "error", "env": "prod"}
        selector = self.builder._build_label_selector(labels)
        # Order might vary, so check all parts are present
        assert selector.startswith("{") and selector.endswith("}")
        assert 'service="api"' in selector
        assert 'level="error"' in selector
        assert 'env="prod"' in selector
    
    def test_build_label_selector_escapes_quotes(self):
        """Test that quotes in label values are escaped."""
        selector = self.builder._build_label_selector({"message": 'error "timeout"'})
        expected = '{message="error \\"timeout\\""}'
        assert selector == expected
    
    def test_build_label_selector_invalid_key(self):
        """Test that invalid label keys raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label key"):
            self.builder._build_label_selector({"": "value"})
        
        with pytest.raises(ValueError, match="Invalid label key"):
            self.builder._build_label_selector({123: "value"})
    
    def test_build_label_selector_invalid_value(self):
        """Test that invalid label values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid label value"):
            self.builder._build_label_selector({"key": 123})


class TestTimeValidation:
    """Test cases for time format validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = LogQLQueryBuilder()
    
    def test_validate_relative_time_formats(self):
        """Test validation of relative time formats."""
        valid_times = ["5m", "1h", "2d", "30s", "1w", "10m", "24h"]
        for time_str in valid_times:
            # Should not raise exception
            self.builder._validate_time_format(time_str)
    
    def test_validate_unix_timestamps(self):
        """Test validation of Unix timestamps."""
        valid_timestamps = [
            "1640995200",      # 2022-01-01 00:00:00 UTC (seconds)
            "1640995200000",   # 2022-01-01 00:00:00 UTC (milliseconds)
            "1577836800",      # 2020-01-01 00:00:00 UTC
        ]
        for timestamp in valid_timestamps:
            # Should not raise exception
            self.builder._validate_time_format(timestamp)
    
    def test_validate_iso_formats(self):
        """Test validation of ISO time formats."""
        valid_iso_times = [
            "2023-01-01T00:00:00Z",
            "2023-01-01T00:00:00.123Z",
            "2023-01-01T00:00:00+00:00",
            "2023-01-01T00:00:00.123+05:30",
            "2023-01-01T00:00:00-08:00",
            "2023-01-01 00:00:00",
        ]
        for time_str in valid_iso_times:
            # Should not raise exception
            self.builder._validate_time_format(time_str)
    
    def test_validate_invalid_time_formats(self):
        """Test that invalid time formats raise ValueError."""
        # Empty strings have a specific error message
        empty_times = ["", "   "]
        for time_str in empty_times:
            with pytest.raises(ValueError, match="Time string cannot be empty"):
                self.builder._validate_time_format(time_str)
        
        # Other invalid formats have the general error message
        invalid_times = [
            "invalid",
            "5x",  # Invalid unit
            "abc123",
            "2023-13-01T00:00:00Z",  # Invalid month
            "not-a-time",
            "123abc",
        ]
        for time_str in invalid_times:
            with pytest.raises(ValueError, match="Invalid time format"):
                self.builder._validate_time_format(time_str)
    
    def test_validate_empty_time(self):
        """Test that empty time string raises ValueError."""
        with pytest.raises(ValueError, match="Time string cannot be empty"):
            self.builder._validate_time_format("")


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_search_logs_function(self):
        """Test search_logs convenience function."""
        query = search_logs(["error", "timeout"])
        expected = '{__name__=~".+"}|~ "(?i)error"|~ "(?i)timeout"'
        assert query == expected
    
    def test_search_logs_with_labels(self):
        """Test search_logs with label filters."""
        labels = {"service": "api"}
        query = search_logs(["error"], labels)
        expected = '{service="api"}|~ "(?i)error"'
        assert query == expected
    
    def test_search_pattern_function(self):
        """Test search_pattern convenience function."""
        query = search_pattern(r"error\d+")
        expected = '{__name__=~".+"}|~ "error\\d+"'
        assert query == expected
    
    def test_search_pattern_with_labels(self):
        """Test search_pattern with label filters."""
        labels = {"app": "web"}
        query = search_pattern("timeout", labels)
        expected = '{app="web"}|~ "timeout"'
        assert query == expected


class TestIntegrationScenarios:
    """Test cases for realistic integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.builder = LogQLQueryBuilder()
    
    def test_error_log_search(self):
        """Test building query for error log search."""
        labels = {"service": "user-api", "level": "error"}
        query = self.builder.build_search_query(["timeout", "connection"], labels)
        expected = '{service="user-api", level="error"}|~ "(?i)timeout"|~ "(?i)connection"'
        assert query == expected
    
    def test_application_log_pattern(self):
        """Test building query for application log pattern matching."""
        labels = {"app": "web-server"}
        pattern = r"HTTP \d{3} .+"
        query = self.builder.build_pattern_query(pattern, labels)
        expected = '{app="web-server"}|~ "HTTP \\d{3} .+"'
        assert query == expected
    
    def test_service_specific_search(self):
        """Test building query for service-specific log search."""
        labels = {"service": "payment-service", "env": "production"}
        query = self.builder.build_search_query(["failed", "retry"], labels)
        expected = '{service="payment-service", env="production"}|~ "(?i)failed"|~ "(?i)retry"'
        assert query == expected
    
    def test_complex_label_filtering(self):
        """Test building query with complex label filtering."""
        labels = {
            "service": "api-gateway",
            "version": "v1.2.3",
            "datacenter": "us-west-2",
            "level": "warn"
        }
        query = self.builder.build_label_query(labels)
        # Check that all labels are present
        assert query.startswith("{") and query.endswith("}")
        for key, value in labels.items():
            assert f'{key}="{value}"' in query