# Time Formats and Conversion

The Loki MCP Server supports various time formats for query parameters. This document describes the supported formats and how they are processed internally.

## Supported Time Formats

### Relative Time
Relative time expressions specify time relative to "now":

| Format | Description | Example |
|--------|-------------|---------|
| `5s` | 5 seconds ago | `"5s"` |
| `30m` | 30 minutes ago | `"30m"` |
| `2h` | 2 hours ago | `"2h"` |
| `7d` | 7 days ago | `"7d"` |
| `1w` | 1 week ago | `"1w"` |

### Absolute Time
Absolute time expressions specify exact timestamps:

| Format | Description | Example |
|--------|-------------|---------|
| ISO 8601 | Standard ISO format | `"2024-08-17T13:00:00Z"` |
| RFC 3339 | RFC 3339 format | `"2024-08-17T13:00:00-05:00"` |
| Unix Timestamp | Seconds since epoch | `"1642694400"` |

### Special Keywords
Special time keywords for convenience:

| Keyword | Description |
|---------|-------------|
| `"now"` | Current time |

### Complex Relative Time
The server also supports more complex relative time expressions:

| Format | Description | Example |
|--------|-------------|---------|
| `now-5m` | 5 minutes before now | `"now-5m"` |
| `now-1h` | 1 hour before now | `"now-1h"` |

## Time Conversion Process

The Loki MCP Server uses the `TimeConverter` class to convert all time formats to RFC 3339 format, which is required by the Loki API.

### Conversion Examples

```python
# Input -> Output (RFC 3339)
"5m"     -> "2024-08-17T12:55:00Z"     # 5 minutes ago
"1h"     -> "2024-08-17T12:00:00Z"     # 1 hour ago
"now"    -> "2024-08-17T13:00:00Z"     # Current time
"now-30m" -> "2024-08-17T12:30:00Z"    # 30 minutes ago

# ISO/RFC formats are validated and normalized
"2024-08-17T13:00:00+00:00" -> "2024-08-17T13:00:00Z"

# Unix timestamps are converted
"1692273600" -> "2023-08-17T12:00:00Z"
```

## Usage in Tools

### query_logs Tool
```python
{
    "query": "{job=\"api\"}",
    "start": "1h",        # 1 hour ago
    "end": "now"          # Current time
}
```

### search_logs Tool
```python
{
    "keywords": ["error"],
    "start": "2024-08-17T10:00:00Z",  # Absolute time
    "end": "30m"                       # 30 minutes ago
}
```

### get_labels Tool
```python
{
    "label_name": "job",
    "start": "1692273600",  # Unix timestamp
    "end": "now-5m"         # 5 minutes ago
}
```

## Time Range Behavior

### Default Behavior
- If neither `start` nor `end` is specified, the query uses a default time range
- If only `start` is specified, `end` defaults to `"now"`
- If only `end` is specified, `start` defaults to 1 hour before `end`

### Time Range Validation
The server validates that:
- Start time is before end time
- Time formats are valid
- Unix timestamps are reasonable (not negative, not too far in the future)

## Error Handling

### Invalid Time Formats
If an invalid time format is provided, the server returns a clear error message:

```json
{
    "status": "error",
    "error": "Invalid time format: '5x'. Supported formats: relative (5m, 1h), ISO 8601, Unix timestamp, or 'now'"
}
```

### Common Time Format Errors

| Input | Error | Correct Format |
|-------|-------|----------------|
| `"5x"` | Invalid unit | `"5m"` or `"5h"` |
| `"1.5h"` | No decimal support | `"90m"` |
| `"yesterday"` | Not supported | `"24h"` or `"1d"` |
| `"2024-13-01"` | Invalid month | `"2024-12-01T00:00:00Z"` |

## Performance Considerations

### Time Range Size
Larger time ranges may impact query performance:

- **Recommended**: Use specific time ranges (1h, 30m)
- **Avoid**: Very large ranges (30d, 1y) without good reason
- **Performance**: Smaller ranges = faster queries

### Caching
The `get_labels` tool caches results based on time ranges:
- Cache duration: 5 minutes
- Cache key includes start and end times
- Use `use_cache: true` for better performance

## Timezone Handling

### UTC Default
All times are converted to UTC for consistency:
- Relative times are calculated from current UTC time
- Absolute times are converted to UTC if they include timezone info
- Times without timezone are assumed to be UTC

### Examples
```python
# Input with timezone -> UTC conversion
"2024-08-17T13:00:00-05:00" -> "2024-08-17T18:00:00Z"

# Input without timezone -> assumed UTC
"2024-08-17T13:00:00" -> "2024-08-17T13:00:00Z"
```

## Best Practices

### Choosing Time Formats
1. **Use relative time for recent data**: `"5m"`, `"1h"`, `"1d"`
2. **Use absolute time for specific periods**: `"2024-08-17T10:00:00Z"`
3. **Use "now" for current time**: Especially useful as end time

### Query Optimization
1. **Start with smaller time ranges**: Begin with `"1h"` and expand if needed
2. **Use specific times for debugging**: Absolute timestamps for reproducible queries
3. **Consider time zones**: Always specify timezone for absolute times in production

### Error Prevention
1. **Validate time inputs**: Check format before making queries
2. **Handle edge cases**: Consider daylight saving time changes
3. **Use consistent formats**: Stick to one format style within an application

This time format documentation ensures users understand how to properly specify time ranges for all Loki MCP Server tools.