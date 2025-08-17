"""Unit tests for time utilities."""

import pytest
from datetime import datetime, timezone, timedelta

from app.time_utils import TimeConverter, get_time_range, convert_time


class TestTimeConverter:
    """Test TimeConverter class."""
    
    def test_to_loki_time_none(self):
        """Test handling of None input."""
        result = TimeConverter.to_loki_time(None)
        assert result is None
    
    def test_to_loki_time_empty_string(self):
        """Test handling of empty string."""
        result = TimeConverter.to_loki_time("")
        assert result is None
        
        result = TimeConverter.to_loki_time("   ")
        assert result is None
    
    def test_to_loki_time_now(self):
        """Test 'now' keyword conversion."""
        result = TimeConverter.to_loki_time("now")
        assert result is not None
        assert result.endswith('Z')
        
        # Should be close to current time
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        diff = abs((now - parsed).total_seconds())
        assert diff < 2  # Within 2 seconds
    
    def test_to_loki_time_relative_seconds(self):
        """Test relative time in seconds."""
        result = TimeConverter.to_loki_time("30s")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(seconds=30)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2  # Within 2 seconds
    
    def test_to_loki_time_relative_minutes(self):
        """Test relative time in minutes."""
        result = TimeConverter.to_loki_time("15m")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(minutes=15)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2
    
    def test_to_loki_time_relative_hours(self):
        """Test relative time in hours."""
        result = TimeConverter.to_loki_time("2h")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(hours=2)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2
    
    def test_to_loki_time_relative_days(self):
        """Test relative time in days."""
        result = TimeConverter.to_loki_time("3d")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(days=3)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2
    
    def test_to_loki_time_relative_weeks(self):
        """Test relative time in weeks."""
        result = TimeConverter.to_loki_time("1w")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(weeks=1)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2
    
    def test_to_loki_time_now_relative(self):
        """Test now-relative time format."""
        result = TimeConverter.to_loki_time("now-1h")
        assert result is not None
        assert result.endswith('Z')
        
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        expected = datetime.now(timezone.utc) - timedelta(hours=1)
        diff = abs((expected - parsed).total_seconds())
        assert diff < 2
    
    def test_to_loki_time_unix_timestamp_seconds(self):
        """Test Unix timestamp in seconds."""
        timestamp = "1692277200"  # 2023-08-17 13:00:00 UTC
        result = TimeConverter.to_loki_time(timestamp)
        assert result == "2023-08-17T13:00:00Z"
    
    def test_to_loki_time_unix_timestamp_milliseconds(self):
        """Test Unix timestamp in milliseconds."""
        timestamp = "1692277200000"  # 2023-08-17 13:00:00 UTC
        result = TimeConverter.to_loki_time(timestamp)
        assert result == "2023-08-17T13:00:00Z"
    
    def test_to_loki_time_iso_format_z(self):
        """Test ISO format with Z suffix."""
        iso_time = "2024-08-17T13:00:00Z"
        result = TimeConverter.to_loki_time(iso_time)
        assert result == "2024-08-17T13:00:00Z"
    
    def test_to_loki_time_iso_format_timezone(self):
        """Test ISO format with timezone offset."""
        iso_time = "2024-08-17T13:00:00+02:00"
        result = TimeConverter.to_loki_time(iso_time)
        assert result == "2024-08-17T11:00:00Z"  # Converted to UTC
    
    def test_to_loki_time_iso_format_no_timezone(self):
        """Test ISO format without timezone (assumes UTC)."""
        iso_time = "2024-08-17T13:00:00"
        result = TimeConverter.to_loki_time(iso_time)
        assert result == "2024-08-17T13:00:00Z"
    
    def test_to_loki_time_space_separated(self):
        """Test space-separated datetime format."""
        datetime_str = "2024-08-17 13:00:00"
        result = TimeConverter.to_loki_time(datetime_str)
        assert result == "2024-08-17T13:00:00Z"
    
    def test_to_loki_time_invalid_relative_unit(self):
        """Test invalid relative time unit."""
        with pytest.raises(ValueError, match="Unsupported time format"):
            TimeConverter.to_loki_time("5x")
    
    def test_to_loki_time_invalid_timestamp(self):
        """Test invalid timestamp."""
        with pytest.raises(ValueError, match="Timestamp out of reasonable range"):
            TimeConverter.to_loki_time("123")  # Too small
    
    def test_to_loki_time_invalid_format(self):
        """Test invalid time format."""
        with pytest.raises(ValueError, match="Unsupported time format"):
            TimeConverter.to_loki_time("invalid-time")
    
    def test_to_loki_time_invalid_iso_date(self):
        """Test invalid ISO date components."""
        with pytest.raises(ValueError, match="Invalid datetime format"):
            TimeConverter.to_loki_time("2024-13-01T13:00:00Z")  # Invalid month
    
    def test_get_default_time_range(self):
        """Test default time range generation."""
        start, end = TimeConverter.get_default_time_range()
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        # Should be approximately 1 hour apart
        diff = (end_dt - start_dt).total_seconds()
        assert 3590 <= diff <= 3610  # Allow some variance
    
    def test_validate_time_range_both_provided(self):
        """Test time range validation with both times provided."""
        start, end = TimeConverter.validate_time_range("2h", "now")
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt
    
    def test_validate_time_range_start_only(self):
        """Test time range validation with only start time."""
        start, end = TimeConverter.validate_time_range("1h", None)
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt
    
    def test_validate_time_range_end_only(self):
        """Test time range validation with only end time."""
        start, end = TimeConverter.validate_time_range(None, "now")
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt
        
        # Should be approximately 1 hour apart
        diff = (end_dt - start_dt).total_seconds()
        assert 3590 <= diff <= 3610
    
    def test_validate_time_range_neither_provided(self):
        """Test time range validation with no times provided."""
        start, end = TimeConverter.validate_time_range(None, None)
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt
    
    def test_validate_time_range_invalid_order(self):
        """Test time range validation with invalid order."""
        with pytest.raises(ValueError, match="Start time .* must be before or equal to end time"):
            TimeConverter.validate_time_range("now", "1h")


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_convert_time(self):
        """Test convert_time convenience function."""
        result = convert_time("1h")
        assert result is not None
        assert result.endswith('Z')
        
        result = convert_time(None)
        assert result is None
    
    def test_get_time_range(self):
        """Test get_time_range convenience function."""
        start, end = get_time_range("1h", "now")
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt
    
    def test_get_time_range_defaults(self):
        """Test get_time_range with defaults."""
        start, end = get_time_range()
        
        assert start.endswith('Z')
        assert end.endswith('Z')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        assert start_dt < end_dt