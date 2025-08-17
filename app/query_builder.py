"""LogQL query construction utilities."""

import re
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone


class LogQLQueryBuilder:
    """Builder class for constructing LogQL queries from user inputs."""
    
    def __init__(self):
        """Initialize the query builder."""
        pass
    
    def build_search_query(
        self, 
        keywords: List[str], 
        labels: Optional[Dict[str, str]] = None,
        case_sensitive: bool = False
    ) -> str:
        """
        Build a LogQL query for keyword search.
        
        Args:
            keywords: List of keywords to search for
            labels: Optional label filters as key-value pairs
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            LogQL query string
        """
        if not keywords:
            raise ValueError("At least one keyword must be provided")
        
        # Start with label selector
        label_selector = self._build_label_selector(labels or {})
        
        # Build keyword filters
        keyword_filters = []
        for keyword in keywords:
            if not keyword.strip():
                continue
            
            # Escape special regex characters in keywords
            escaped_keyword = re.escape(keyword.strip())
            
            if case_sensitive:
                keyword_filters.append(f'|~ "{escaped_keyword}"')
            else:
                keyword_filters.append(f'|~ "(?i){escaped_keyword}"')
        
        if not keyword_filters:
            raise ValueError("No valid keywords provided")
        
        # Combine label selector with keyword filters
        query = label_selector + "".join(keyword_filters)
        
        return query
    
    def build_pattern_query(
        self, 
        pattern: str, 
        labels: Optional[Dict[str, str]] = None,
        use_regex: bool = True
    ) -> str:
        """
        Build a LogQL query for pattern matching.
        
        Args:
            pattern: Pattern to search for (regex or literal)
            labels: Optional label filters as key-value pairs
            use_regex: Whether to treat pattern as regex (True) or literal (False)
            
        Returns:
            LogQL query string
        """
        if not pattern or not pattern.strip():
            raise ValueError("Pattern cannot be empty")
        
        # Start with label selector
        label_selector = self._build_label_selector(labels or {})
        
        # Build pattern filter
        if use_regex:
            # Validate regex pattern
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
            
            pattern_filter = f'|~ "{pattern}"'
        else:
            # Escape special regex characters for literal matching
            escaped_pattern = re.escape(pattern.strip())
            pattern_filter = f'|~ "{escaped_pattern}"'
        
        query = label_selector + pattern_filter
        
        return query
    
    def build_time_range_query(
        self, 
        base_query: str, 
        start: Optional[str] = None, 
        end: Optional[str] = None
    ) -> str:
        """
        Build a LogQL query with time range formatting.
        
        Args:
            base_query: Base LogQL query to add time range to
            start: Start time (ISO format, relative time, or timestamp)
            end: End time (ISO format, relative time, or timestamp)
            
        Returns:
            LogQL query string with time range context
            
        Note:
            Time range filtering is typically handled by the Loki API parameters,
            but this method validates and formats time strings for consistency.
        """
        if not base_query or not base_query.strip():
            raise ValueError("Base query cannot be empty")
        
        # Validate time formats if provided
        if start:
            self._validate_time_format(start)
        if end:
            self._validate_time_format(end)
        
        # For LogQL, time ranges are typically handled by API parameters
        # but we can add time-based filters to the query if needed
        query = base_query.strip()
        
        return query
    
    def build_label_query(self, labels: Dict[str, str]) -> str:
        """
        Build a LogQL query that only filters by labels.
        
        Args:
            labels: Label filters as key-value pairs
            
        Returns:
            LogQL query string
        """
        if not labels:
            raise ValueError("At least one label must be provided")
        
        return self._build_label_selector(labels)
    
    def _build_label_selector(self, labels: Dict[str, str]) -> str:
        """
        Build the label selector part of a LogQL query.
        
        Args:
            labels: Label filters as key-value pairs
            
        Returns:
            Label selector string
        """
        if not labels:
            # Return a selector that matches any stream with at least one label
            # This avoids the "empty-compatible value" error
            return '{__name__=~".+"}'
        
        label_parts = []
        for key, value in labels.items():
            if not key or not isinstance(key, str):
                raise ValueError(f"Invalid label key: {key}")
            if not isinstance(value, str):
                raise ValueError(f"Invalid label value for key '{key}': {value}")
            
            # Escape quotes in values
            escaped_value = value.replace('"', '\\"')
            
            # Use regex matching to avoid empty-compatible values
            if value == ".*" or value == "":
                # For wildcard or empty values, use a non-empty regex
                label_parts.append(f'{key}=~".+"')
            else:
                # For specific values, use exact match
                label_parts.append(f'{key}="{escaped_value}"')
        
        return "{" + ", ".join(label_parts) + "}"
    
    def _validate_time_format(self, time_str: str) -> None:
        """
        Validate time format for LogQL queries.
        
        Args:
            time_str: Time string to validate
            
        Raises:
            ValueError: If time format is invalid
        """
        if not time_str or not time_str.strip():
            raise ValueError("Time string cannot be empty")
        
        time_str = time_str.strip()
        
        # Check for relative time formats (e.g., "5m", "1h", "2d")
        relative_pattern = r'^\d+[smhdw]$'
        if re.match(relative_pattern, time_str):
            return
        
        # Check for Unix timestamp (seconds or milliseconds)
        if time_str.isdigit():
            timestamp = int(time_str)
            # Reasonable timestamp range check (year 2000 to 2100)
            if 946684800 <= timestamp <= 4102444800 or 946684800000 <= timestamp <= 4102444800000:
                return
        
        # Check for ISO format patterns
        iso_patterns = [
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$',
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$',
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
        ]
        
        # Check if it matches ISO pattern and try to parse basic date components
        for pattern in iso_patterns:
            if re.match(pattern, time_str):
                # Basic validation of date components for ISO format
                try:
                    # Extract date part for basic validation
                    date_part = time_str.split('T')[0] if 'T' in time_str else time_str.split(' ')[0]
                    year, month, day = map(int, date_part.split('-'))
                    
                    # Basic range checks
                    if not (1 <= month <= 12):
                        raise ValueError(f"Invalid month: {month}")
                    if not (1 <= day <= 31):
                        raise ValueError(f"Invalid day: {day}")
                    if not (1900 <= year <= 2200):
                        raise ValueError(f"Invalid year: {year}")
                    
                    return
                except (ValueError, IndexError):
                    # If parsing fails, continue to the error case
                    pass
        
        raise ValueError(f"Invalid time format: {time_str}. Expected ISO format, Unix timestamp, or relative time (e.g., '5m', '1h')")


# Convenience functions for common use cases
def search_logs(keywords: List[str], labels: Optional[Dict[str, str]] = None) -> str:
    """
    Convenience function to build a keyword search query.
    
    Args:
        keywords: List of keywords to search for
        labels: Optional label filters
        
    Returns:
        LogQL query string
    """
    builder = LogQLQueryBuilder()
    return builder.build_search_query(keywords, labels)


def search_pattern(pattern: str, labels: Optional[Dict[str, str]] = None) -> str:
    """
    Convenience function to build a pattern search query.
    
    Args:
        pattern: Regex pattern to search for
        labels: Optional label filters
        
    Returns:
        LogQL query string
    """
    builder = LogQLQueryBuilder()
    return builder.build_pattern_query(pattern, labels)