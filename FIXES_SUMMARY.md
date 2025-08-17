# Loki MCP Server - Fixes Summary

## Issues Fixed

The original Loki MCP server had several critical issues that prevented it from working correctly with Claude and other MCP clients. Here are the issues that have been resolved:

### 1. Time Parameter Parsing Issues

**Problem**: The server was passing relative time strings like "1h" and "now" directly to Loki, but Loki expects proper RFC3339 timestamps.

**Error Messages**:
- `strconv.ParseInt: parsing "now": invalid syntax`
- `could not parse 'end' parameter`

**Solution**: Created a comprehensive time conversion utility (`time_utils.py`) that:
- Converts relative times ("1h", "30m", "5d") to proper RFC3339 timestamps
- Handles "now" keyword by converting to current UTC time
- Supports Unix timestamps and ISO format dates
- Provides proper defaults when time parameters are missing

### 2. LogQL Query Validation Issues

**Problem**: Empty label selectors were generating queries that Loki rejected.

**Error Message**:
- `queries require at least one regexp or equality matcher that does not have an empty-compatible value. For instance, app=~".*" does not meet this requirement, but app=~".+" will`

**Solution**: Updated the query builder to:
- Use `{__name__=~".+"}` instead of `{}` for empty label selectors
- Avoid empty-compatible regex patterns
- Ensure all queries have at least one non-empty matcher

### 3. Query Type Issues

**Problem**: The server was mixing instant queries and range queries inappropriately.

**Solution**: 
- Standardized on range queries for all operations
- Always provide proper time ranges with RFC3339 timestamps
- Removed problematic instant query usage

## Files Modified

### New Files
- `app/time_utils.py` - Time conversion utilities

### Modified Files
- `app/query_builder.py` - Fixed empty label selector issue
- `app/tools/search_logs.py` - Added time conversion
- `app/tools/query_logs.py` - Added time conversion and standardized on range queries
- `app/tools/get_labels.py` - Added time conversion

## Testing

The fixes have been tested with:
- `test_fixes.py` - Basic functionality tests
- `test_core_fixes.py` - Comprehensive edge case testing

All tests pass and demonstrate that the problematic scenarios now work correctly.

## Usage Examples

### Working Queries

These queries will now work correctly:

```python
# Search for errors in the last hour
search_logs(
    keywords=["error"],
    start="1h",
    end="now",
    limit=100
)

# Query with LogQL
query_logs(
    query='{job=~".+"}|~ "(?i)error"',
    start="30m",
    end="now"
)

# Get labels for a time range
get_labels(
    start="1h",
    end="now"
)
```

### Time Format Support

The server now supports these time formats:
- Relative: `"5m"`, `"1h"`, `"2d"`, `"1w"`
- Keyword: `"now"`
- Unix timestamp: `"1692277200"`
- ISO format: `"2024-08-17T13:00:00Z"`

## Key Improvements

1. **Robust Time Handling**: All time parameters are properly converted to RFC3339 format
2. **Valid LogQL Queries**: All generated queries meet Loki's requirements
3. **Better Error Handling**: More descriptive error messages when issues occur
4. **Consistent API**: All tools use the same time conversion logic

## Before vs After

### Before (Broken)
```
Request: show me all logs from the last hour
Error: strconv.ParseInt: parsing "now": invalid syntax
```

### After (Working)
```
Request: show me all logs from the last hour
Success: Returns logs from 2025-08-16T17:46:40Z to 2025-08-16T18:46:40Z
Query: {__name__=~".+"}|~ "(?i)error"
```

The MCP server should now work correctly with Claude and other MCP clients for log searching and analysis tasks.