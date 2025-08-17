"""Time utilities for Loki queries."""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union


class TimeConverter:
    """Utility class for converting various time formats to Loki-compatible formats."""
    
    @staticmethod
    def to_loki_time(time_str: Optional[str]) -> Optional[str]:
        """
        Convert various time formats to Loki-compatible RFC3339 format.
        
        Args:
            time_str: Time string in various formats:
                - Relative time: "5m", "1h", "2d", "1w"
                - Unix timestamp: "1642694400"
                - ISO format: "2024-08-17T13:00:00Z"
                - "now" keyword
                
        Returns:
            RFC3339 formatted time string or None if input is None
            
        Raises:
            ValueError: If time format is invalid
        """
        if time_str is None:
            return None
            
        time_str = time_str.strip()
        
        if not time_str:
            return None
            
        # Handle "now" keyword
        if time_str.lower() == "now":
            return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Handle relative time formats (e.g., "5m", "1h", "2d", "now-1h")
        relative_match = re.match(r'^(\d+)([smhdw])$', time_str)
        now_relative_match = re.match(r'^now-(\d+)([smhdw])$', time_str)
        
        if relative_match or now_relative_match:
            if relative_match:
                amount = int(relative_match.group(1))
                unit = relative_match.group(2)
            else:  # now_relative_match
                amount = int(now_relative_match.group(1))
                unit = now_relative_match.group(2)
            
            # Calculate the datetime
            now = datetime.now(timezone.utc)
            
            if unit == 's':
                target_time = now - timedelta(seconds=amount)
            elif unit == 'm':
                target_time = now - timedelta(minutes=amount)
            elif unit == 'h':
                target_time = now - timedelta(hours=amount)
            elif unit == 'd':
                target_time = now - timedelta(days=amount)
            elif unit == 'w':
                target_time = now - timedelta(weeks=amount)
            else:
                raise ValueError(f"Unsupported time unit: {unit}")
            
            return target_time.isoformat().replace('+00:00', 'Z')
        
        # Handle Unix timestamp (seconds or milliseconds)
        if time_str.isdigit():
            timestamp = int(time_str)
            
            # Detect if it's milliseconds (rough heuristic: > year 2020 in seconds)
            if timestamp > 1577836800000:  # 2020-01-01 in milliseconds
                timestamp = timestamp / 1000
            
            # Validate timestamp range (year 2000 to 2100)
            if not (946684800 <= timestamp <= 4102444800):
                raise ValueError(f"Timestamp out of reasonable range: {timestamp}")
            
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.isoformat().replace('+00:00', 'Z')
        
        # Handle ISO format patterns
        iso_patterns = [
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$',
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$',
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
        ]
        
        for pattern in iso_patterns:
            if re.match(pattern, time_str):
                try:
                    # Try to parse the datetime to validate it
                    if 'T' in time_str:
                        if time_str.endswith('Z'):
                            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        elif '+' in time_str or time_str.count('-') > 2:
                            dt = datetime.fromisoformat(time_str)
                        else:
                            # Assume UTC if no timezone info
                            dt = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
                    else:
                        # Space-separated format, assume UTC
                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    
                    # Convert to UTC and return in RFC3339 format
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    
                    return dt.isoformat().replace('+00:00', 'Z')
                    
                except ValueError as e:
                    raise ValueError(f"Invalid datetime format: {time_str} - {e}")
        
        raise ValueError(f"Unsupported time format: {time_str}. Expected ISO format, Unix timestamp, relative time (e.g., '5m', '1h'), or 'now'")    
    
    @staticmethod
    def get_default_time_range() -> tuple[str, str]:
        """
        Get default time range for queries (last hour).
        
        Returns:
            Tuple of (start_time, end_time) in RFC3339 format
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        
        return (
            one_hour_ago.isoformat().replace('+00:00', 'Z'),
            now.isoformat().replace('+00:00', 'Z')
        )
    
    @staticmethod
    def validate_time_range(start: Optional[str], end: Optional[str]) -> tuple[str, str]:
        """
        Validate and convert time range, providing defaults if needed.
        
        Args:
            start: Start time string
            end: End time string
            
        Returns:
            Tuple of validated (start_time, end_time) in RFC3339 format
            
        Raises:
            ValueError: If time range is invalid
        """
        # Convert times
        start_converted = TimeConverter.to_loki_time(start) if start else None
        end_converted = TimeConverter.to_loki_time(end) if end else None
        
        # Provide defaults if needed
        if start_converted is None and end_converted is None:
            return TimeConverter.get_default_time_range()
        elif start_converted is None:
            # Default to 1 hour before end time
            end_dt = datetime.fromisoformat(end_converted.replace('Z', '+00:00'))
            start_dt = end_dt - timedelta(hours=1)
            start_converted = start_dt.isoformat().replace('+00:00', 'Z')
        elif end_converted is None:
            # Default to now
            end_converted = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Validate that start is before end
        start_dt = datetime.fromisoformat(start_converted.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_converted.replace('Z', '+00:00'))
        
        if start_dt > end_dt:
            raise ValueError(f"Start time ({start_converted}) must be before or equal to end time ({end_converted})")
        
        return start_converted, end_converted


# Convenience functions
def convert_time(time_str: Optional[str]) -> Optional[str]:
    """Convert time string to Loki-compatible format."""
    return TimeConverter.to_loki_time(time_str)


def get_time_range(start: Optional[str] = None, end: Optional[str] = None) -> tuple[str, str]:
    """Get validated time range with proper defaults."""
    return TimeConverter.validate_time_range(start, end)