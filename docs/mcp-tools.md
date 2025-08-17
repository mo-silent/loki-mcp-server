# MCP Tool Schemas and Parameters

This document provides comprehensive documentation for all MCP tools available in the Loki MCP Server, including detailed parameter specifications, response schemas, and usage examples.

## Overview

The Loki MCP Server provides three main tools for log analysis:

1. **query_logs** - Execute LogQL queries directly
2. **search_logs** - Search logs using keywords with advanced filtering
3. **get_labels** - Discover available labels and their values

Each tool follows the MCP (Model Context Protocol) specification and returns structured data that can be processed by AI assistants.

## Time Format Support

All tools support flexible time formats for start/end parameters. See [Time Formats Documentation](time-formats.md) for complete details on supported formats including relative time (`5m`, `1h`), absolute time (ISO 8601, Unix timestamps), and special keywords (`now`).

## Tool: query_logs

Execute LogQL queries against Grafana Loki with support for both range and instant queries.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "LogQL query string to execute against Loki",
      "minLength": 1
    },
    "start": {
      "type": "string",
      "description": "Start time for query range (ISO format, Unix timestamp, or relative time like '5m')"
    },
    "end": {
      "type": "string", 
      "description": "End time for query range (ISO format, Unix timestamp, or relative time like '1h')"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of log entries to return",
      "minimum": 1,
      "maximum": 5000,
      "default": 100
    },
    "direction": {
      "type": "string",
      "description": "Query direction: 'forward' or 'backward'",
      "enum": ["forward", "backward"],
      "default": "backward"
    }
  },
  "required": ["query"]
}
```

### Parameters

#### query (required)
- **Type**: String
- **Description**: LogQL query string to execute against Loki
- **Constraints**: Minimum length of 1 character
- **Examples**:
  - `{job="web-server"}` - Basic label selector
  - `{job="api"} |= "error"` - Label selector with line filter
  - `count_over_time({job="api"}[5m])` - Aggregation query
  - `{job="nginx"} | json | status >= 400` - Structured log parsing

#### start (optional)
- **Type**: String
- **Description**: Start time for query range
- **Default**: None (instant query if neither start nor end specified)
- **Formats**:
  - **Relative**: `5m`, `1h`, `2d`, `1w`
  - **ISO 8601**: `2023-12-01T10:00:00Z`
  - **Unix timestamp**: `1701428400`
  - **RFC 3339**: `2023-12-01T10:00:00-05:00`
- **Examples**:
  - `"5m"` - 5 minutes ago
  - `"1h"` - 1 hour ago
  - `"2023-12-01T10:00:00Z"` - Specific timestamp

#### end (optional)
- **Type**: String
- **Description**: End time for query range
- **Default**: `"now"` when start is specified
- **Formats**: Same as start parameter
- **Examples**:
  - `"now"` - Current time
  - `"1h"` - 1 hour ago
  - `"2023-12-01T11:00:00Z"` - Specific timestamp

#### limit (optional)
- **Type**: Integer
- **Description**: Maximum number of log entries to return
- **Default**: 100
- **Range**: 1 to 5000
- **Note**: Larger limits may impact performance

#### direction (optional)
- **Type**: String
- **Description**: Query direction for log ordering
- **Default**: `"backward"`
- **Values**:
  - `"backward"` - Newest logs first (default)
  - `"forward"` - Oldest logs first
- **Use Cases**:
  - `"backward"` - Recent issues, monitoring
  - `"forward"` - Historical analysis, chronological order

### Response Schema

```json
{
  "status": "success|error",
  "result_type": "streams|matrix|vector|scalar",
  "entries": [
    {
      "timestamp": "2023-12-01T10:30:00.123Z",
      "timestamp_ns": "1701428400123456789",
      "line": "ERROR: Database connection failed",
      "labels": {
        "job": "api",
        "level": "error",
        "instance": "api-server-1"
      }
    }
  ],
  "total_entries": 42,
  "query": "{job=\"api\"} |= \"error\"",
  "time_range": {
    "start": "1h",
    "end": "now"
  },
  "error": null
}
```

### Response Fields

#### status
- **Type**: String
- **Values**: `"success"` or `"error"`
- **Description**: Indicates if the query executed successfully

#### result_type
- **Type**: String
- **Values**: `"streams"`, `"matrix"`, `"vector"`, `"scalar"`
- **Description**: Type of result returned by Loki API

#### entries
- **Type**: Array of objects
- **Description**: Log entries matching the query
- **Entry Structure**:
  - `timestamp`: Human-readable timestamp (ISO 8601)
  - `timestamp_ns`: Nanosecond precision timestamp
  - `line`: The log message content
  - `labels`: Key-value pairs of log labels

#### total_entries
- **Type**: Integer
- **Description**: Number of entries returned

#### query
- **Type**: String
- **Description**: The original query that was executed

#### time_range
- **Type**: Object
- **Description**: Time range used for the query
- **Fields**: `start`, `end`

#### error
- **Type**: String or null
- **Description**: Error message if status is "error"

### Usage Examples

#### Basic Log Query
```python
{
  "query": "{job=\"web-server\"} |= \"error\"",
  "start": "1h",
  "limit": 50
}
```

#### Structured Log Analysis
```python
{
  "query": "{job=\"api\"} | json | level=\"error\" | status >= 500",
  "start": "30m",
  "direction": "backward"
}
```

#### Aggregation Query
```python
{
  "query": "count_over_time({job=\"api\"}[5m])",
  "start": "2h",
  "end": "now"
}
```

## Tool: search_logs

Search logs using keywords with support for advanced filtering, logical operators, and pattern matching.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "keywords": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of keywords to search for in log messages",
      "minItems": 1
    },
    "labels": {
      "type": "object",
      "description": "Optional label filters as key-value pairs",
      "additionalProperties": {"type": "string"}
    },
    "start": {
      "type": "string",
      "description": "Start time for search range (ISO format, Unix timestamp, or relative time like '5m')"
    },
    "end": {
      "type": "string",
      "description": "End time for search range (ISO format, Unix timestamp, or relative time like '1h')"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of log entries to return",
      "minimum": 1,
      "maximum": 5000,
      "default": 100
    },
    "case_sensitive": {
      "type": "boolean",
      "description": "Whether the search should be case sensitive",
      "default": false
    },
    "operator": {
      "type": "string",
      "description": "Logical operator for multiple keywords",
      "enum": ["AND", "OR"],
      "default": "AND"
    }
  },
  "required": ["keywords"]
}
```

### Parameters

#### keywords (required)
- **Type**: Array of strings
- **Description**: Keywords to search for in log messages
- **Constraints**: Minimum 1 item, no empty keywords
- **Examples**:
  - `["error"]` - Single keyword
  - `["error", "database"]` - Multiple keywords
  - `["timeout", "connection", "failed"]` - Complex search

#### labels (optional)
- **Type**: Object (key-value pairs)
- **Description**: Filter logs by specific label values
- **Format**: `{"label_name": "label_value"}`
- **Examples**:
  - `{"job": "api"}` - Filter by job
  - `{"job": "api", "level": "error"}` - Multiple label filters
  - `{"environment": "production", "region": "us-east-1"}` - Environment-specific

#### start (optional)
- **Type**: String
- **Description**: Start time for search range
- **Default**: None (searches recent logs)
- **Formats**: Same as query_logs tool

#### end (optional)
- **Type**: String
- **Description**: End time for search range
- **Default**: `"now"` when start is specified
- **Formats**: Same as query_logs tool

#### limit (optional)
- **Type**: Integer
- **Description**: Maximum number of log entries to return
- **Default**: 100
- **Range**: 1 to 5000

#### case_sensitive (optional)
- **Type**: Boolean
- **Description**: Whether search should be case sensitive
- **Default**: false
- **Examples**:
  - `false` - "ERROR" matches "error"
  - `true` - "ERROR" does not match "error"

#### operator (optional)
- **Type**: String
- **Description**: Logical operator for multiple keywords
- **Default**: `"AND"`
- **Values**:
  - `"AND"` - All keywords must be present
  - `"OR"` - Any keyword can be present
- **Examples**:
  - `"AND"` with `["database", "error"]` - Lines containing both terms
  - `"OR"` with `["error", "warning"]` - Lines containing either term

### Response Schema

```json
{
  "status": "success|error",
  "entries": [
    {
      "timestamp": "2023-12-01T10:30:00.123Z",
      "timestamp_ns": "1701428400123456789",
      "line": "Database connection error: timeout after 30s",
      "labels": {
        "job": "api",
        "level": "error"
      },
      "matched_keywords": ["database", "error"],
      "context": [
        {
          "keyword": "database",
          "context": "...Database connection error: timeout...",
          "position": 0
        },
        {
          "keyword": "error",
          "context": "...connection error: timeout after 30s...",
          "position": 19
        }
      ]
    }
  ],
  "total_entries": 15,
  "search_terms": ["database", "error"],
  "labels_filter": {"job": "api"},
  "time_range": {
    "start": "1h",
    "end": "now"
  },
  "query_used": "{job=\"api\"} |= \"database\" |= \"error\"",
  "error": null
}
```

### Response Fields

#### entries
Extended with search-specific fields:
- `matched_keywords`: Array of keywords that were found in this log entry
- `context`: Array of context objects, each containing:
  - `keyword`: The matched keyword
  - `context`: Text snippet showing the keyword in context (with ellipsis if truncated)
  - `position`: Character position of the keyword in the original log line

#### search_terms
- **Type**: Array of strings
- **Description**: Keywords that were searched for

#### labels_filter
- **Type**: Object
- **Description**: Label filters that were applied

#### query_used
- **Type**: String
- **Description**: The LogQL query generated from search parameters

### Usage Examples

#### Simple Keyword Search
```python
{
  "keywords": ["error", "exception"],
  "operator": "OR",
  "start": "1h"
}
```

#### Filtered Search
```python
{
  "keywords": ["timeout"],
  "labels": {"job": "database", "environment": "prod"},
  "start": "30m",
  "case_sensitive": true
}
```

#### Complex Search
```python
{
  "keywords": ["payment", "failed"],
  "labels": {"service": "billing"},
  "operator": "AND",
  "start": "2h",
  "limit": 200
}
```

## Tool: get_labels

Discover available log labels and their values from Loki, with caching support for improved performance.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "label_name": {
      "type": "string",
      "description": "Specific label name to get values for. If not provided, returns all label names."
    },
    "start": {
      "type": "string",
      "description": "Start time for label query (ISO format, Unix timestamp, or relative time like '5m')"
    },
    "end": {
      "type": "string",
      "description": "End time for label query (ISO format, Unix timestamp, or relative time like '1h')"
    },
    "use_cache": {
      "type": "boolean",
      "description": "Whether to use cached label information to improve performance",
      "default": true
    }
  },
  "required": []
}
```

### Parameters

#### label_name (optional)
- **Type**: String
- **Description**: Specific label name to get values for
- **Default**: None (returns all label names)
- **Examples**:
  - `"job"` - Get all job values
  - `"level"` - Get all log levels
  - `"environment"` - Get all environments

#### start (optional)
- **Type**: String
- **Description**: Start time for label query
- **Default**: None (queries all available data)
- **Formats**: Same as other tools

#### end (optional)
- **Type**: String
- **Description**: End time for label query
- **Default**: `"now"` when start is specified
- **Formats**: Same as other tools

#### use_cache (optional)
- **Type**: Boolean
- **Description**: Whether to use cached label information
- **Default**: true
- **Benefits**: Improves performance for repeated queries
- **Cache Duration**: 5 minutes (300 seconds)
- **Cache Key**: Based on label_name, start, and end parameters
- **Cache Behavior**: 
  - Automatic expiration after TTL
  - Memory-based storage (not persistent)
  - Thread-safe for concurrent requests

### Response Schema

```json
{
  "status": "success|error",
  "label_type": "names|values",
  "label_name": "job",
  "labels": [
    "api",
    "web-server", 
    "database",
    "worker"
  ],
  "total_count": 4,
  "time_range": {
    "start": "1h",
    "end": "now"
  },
  "cached": false,
  "error": null
}
```

### Response Fields

#### label_type
- **Type**: String
- **Values**: `"names"` or `"values"`
- **Description**: 
  - `"names"` - When querying all label names
  - `"values"` - When querying values for specific label

#### label_name
- **Type**: String or null
- **Description**: The specific label name queried (null for label names query)

#### labels
- **Type**: Array of strings
- **Description**: List of label names or values, sorted alphabetically

#### total_count
- **Type**: Integer
- **Description**: Total number of labels returned

#### cached
- **Type**: Boolean
- **Description**: Whether the result came from cache

### Usage Examples

#### Get All Label Names
```python
{
  "use_cache": true
}
```

#### Get Values for Specific Label
```python
{
  "label_name": "job",
  "start": "24h",
  "use_cache": true
}
```

#### Get Recent Labels (No Cache)
```python
{
  "label_name": "environment",
  "start": "1h",
  "use_cache": false
}
```

## Error Handling

All tools follow consistent error handling patterns:

### Common Error Responses

```json
{
  "status": "error",
  "error": "Error message describing what went wrong",
  "entries": [],
  "total_entries": 0
}
```

### Error Types

#### Authentication Errors
- **Message**: "Authentication failed"
- **Cause**: Invalid credentials or expired tokens
- **Resolution**: Check LOKI_USERNAME/LOKI_PASSWORD or LOKI_BEARER_TOKEN

#### Connection Errors
- **Message**: "Connection failed"
- **Cause**: Network issues or Loki server unavailable
- **Resolution**: Verify LOKI_URL and network connectivity

#### Query Errors
- **Message**: "Invalid LogQL query"
- **Cause**: Malformed LogQL syntax
- **Resolution**: Check query syntax and label names

#### Rate Limit Errors
- **Message**: "Rate limit exceeded"
- **Cause**: Too many requests in short time
- **Resolution**: Reduce query frequency

#### Validation Errors
- **Message**: "Parameter validation failed"
- **Cause**: Invalid parameter values
- **Resolution**: Check parameter types and constraints

## Performance Considerations

### Query Optimization
- Use specific label selectors
- Limit time ranges appropriately
- Use reasonable result limits
- Enable caching for get_labels

### Memory Usage
- Large result sets use more memory
- Use pagination for large datasets
- Consider streaming for real-time queries

### Rate Limiting
- Respect Loki server rate limits
- Use caching to reduce API calls
- Batch related queries when possible

## Integration Examples

### AI Assistant Integration

```python
# Discovery workflow
labels_result = get_labels({})
print(f"Available labels: {labels_result['labels']}")

# Explore specific label
job_values = get_labels({"label_name": "job"})
print(f"Available jobs: {job_values['labels']}")

# Search for issues
error_search = search_logs({
    "keywords": ["error", "exception"],
    "labels": {"job": "api"},
    "start": "1h",
    "operator": "OR"
})

# Deep dive with LogQL
detailed_query = query_logs({
    "query": "{job=\"api\"} | json | level=\"error\" | status >= 500",
    "start": "1h",
    "limit": 100
})
```

### Monitoring Workflow

```python
# Check error rates
error_rate_query = query_logs({
    "query": "rate({job=\"api\"} |= \"error\" [5m])",
    "start": "1h"
})

# Find slow requests
slow_requests = search_logs({
    "keywords": ["slow", "timeout", "latency"],
    "labels": {"service": "api"},
    "start": "30m"
})

# Investigate specific issues
detailed_logs = query_logs({
    "query": "{job=\"api\"} | json | response_time > 1000",
    "start": "2h",
    "limit": 50
})
```

## Validation Rules

### Input Validation
- All string parameters are trimmed
- Empty keywords are filtered out
- Label values must be valid strings
- Time ranges are validated for format
- Limits are constrained to reasonable values

### Output Validation
- Timestamps are converted to ISO format
- Labels are sorted alphabetically
- Results are limited to specified constraints
- Error messages are user-friendly

This comprehensive documentation provides all the information needed to effectively use the Loki MCP Server tools for log analysis and monitoring tasks.