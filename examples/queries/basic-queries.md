# Basic LogQL Queries

This guide covers fundamental LogQL queries to get you started with log analysis using the Loki MCP Server.

## Query Structure

LogQL queries follow this basic structure:
```logql
{label_selector} |= "line_filter" | log_pipeline | aggregation
```

## Label Selectors

### Single Label
```logql
{job="web-server"}
```
*Returns all logs from the "web-server" job*

### Multiple Labels (AND)
```logql
{job="web-server", level="error"}
```
*Returns error logs from the web-server*

### Label Matching
```logql
{job=~"web-.*"}
```
*Returns logs from jobs starting with "web-"*

### Label Exclusion
```logql
{job!="debug-service"}
```
*Returns logs from all jobs except "debug-service"*

## Line Filters

### Contains String
```logql
{job="web-server"} |= "error"
```
*Lines containing "error"*

### Does Not Contain
```logql
{job="web-server"} != "debug"
```
*Lines not containing "debug"*

### Regular Expression Match
```logql
{job="web-server"} |~ "error|exception|fail"
```
*Lines matching the regex pattern*

### Regular Expression Exclude
```logql
{job="web-server"} !~ "INFO|DEBUG"
```
*Lines not matching the regex pattern*

### Case Insensitive
```logql
{job="web-server"} |~ "(?i)error"
```
*Case insensitive match for "error"*

## Time Ranges

### Relative Time
```logql
{job="web-server"} |= "error" [5m]
```
*Last 5 minutes*

```logql
{job="web-server"} |= "error" [1h]
```
*Last 1 hour*

```logql
{job="web-server"} |= "error" [1d]
```
*Last 1 day*

### Absolute Time
```logql
{job="web-server"} |= "error" [2023-12-01T10:00:00Z:2023-12-01T11:00:00Z]
```
*Specific time range*

## Basic Aggregations

### Count Lines
```logql
count_over_time({job="web-server"}[5m])
```
*Count log lines in 5-minute windows*

### Rate of Logs
```logql
rate({job="web-server"}[5m])
```
*Rate of log entries per second*

### Count by Label
```logql
count by (level) (count_over_time({job="web-server"}[5m]))
```
*Count logs grouped by level*

## MCP Server Examples

### Using query_logs Tool

#### Basic Error Search
```python
{
  "query": "{job=\"web-server\"} |= \"error\"",
  "start": "1h",
  "limit": 100
}
```

#### Application Logs
```python
{
  "query": "{namespace=\"production\", app=\"api\"} |= \"request\"",
  "start": "30m",
  "direction": "backward"
}
```

#### Recent Critical Issues
```python
{
  "query": "{level=\"critical\"} or {level=\"fatal\"}",
  "start": "15m",
  "limit": 50
}
```

### Using search_logs Tool

#### Simple Keyword Search
```python
{
  "keywords": ["error", "exception"],
  "labels": {"job": "web-server"},
  "start": "1h",
  "operator": "OR"
}
```

#### Specific Service Issues
```python
{
  "keywords": ["timeout", "connection refused"],
  "labels": {"service": "database", "environment": "prod"},
  "start": "30m",
  "case_sensitive": false
}
```

#### Performance Issues
```python
{
  "keywords": ["slow", "latency", "performance"],
  "labels": {"component": "api"},
  "start": "2h",
  "operator": "OR"
}
```

## Common Patterns

### Application Startup Logs
```logql
{job="my-app"} |= "started" or "listening" or "ready"
```

### HTTP Errors
```logql
{job="nginx"} |~ "HTTP/1.[01]\" [45][0-9][0-9]"
```

### Database Queries
```logql
{job="api"} |= "SELECT" or "INSERT" or "UPDATE" or "DELETE"
```

### Security Events
```logql
{job="auth-service"} |= "failed login" or "unauthorized" or "forbidden"
```

### Performance Metrics
```logql
{job="api"} |~ "response_time|duration|latency"
```

## Structured Log Parsing

### JSON Logs
```logql
{job="app"} | json | level="error"
```
*Parse JSON and filter by level field*

### Logfmt Logs
```logql
{job="app"} | logfmt | level="error"
```
*Parse logfmt and filter by level field*

### Extract Fields
```logql
{job="nginx"} | regexp "(?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+)" | ip="192.168.1.1"
```
*Extract IP addresses and filter*

## Best Practices for Basic Queries

### 1. Start with Labels
Always start with label selectors to narrow down the search space:
```logql
# Good
{job="web-server", environment="prod"} |= "error"

# Less efficient  
{} |= "error" | job="web-server"
```

### 2. Use Appropriate Time Ranges
Don't query more data than necessary:
```logql
# For recent issues
{job="api"} |= "error" [15m]

# For trend analysis
{job="api"} |= "error" [1d]
```

### 3. Limit Results
Use appropriate limits to avoid overwhelming output:
```python
{
  "query": "{job=\"web-server\"} |= \"error\"",
  "limit": 100  # Reasonable limit
}
```

### 4. Use Specific Search Terms
Be specific in your search terms:
```logql
# Specific
{job="api"} |= "connection timeout"

# Too broad
{job="api"} |= "error"
```

### 5. Combine Multiple Conditions
Use multiple filters for precise results:
```logql
{job="api", level="error"} |~ "database|db" != "debug"
```

## Common Mistakes to Avoid

### 1. No Label Selector
```logql
# Bad - scans all logs
|= "error"

# Good - uses label index
{job="api"} |= "error"
```

### 2. Too Broad Time Range
```logql
# Bad - queries entire history
{job="api"} |= "error"

# Good - reasonable time window
{job="api"} |= "error" [1h]
```

### 3. Complex Regex Without Optimization
```logql
# Bad - expensive regex
{job="api"} |~ ".*error.*|.*exception.*|.*fail.*"

# Better - simple contains
{job="api"} |= "error" or "exception" or "fail"
```

### 4. Not Using Log Parsing
```logql
# Bad - string matching on structured logs
{job="api"} |= "\"level\":\"error\""

# Good - parse then filter
{job="api"} | json | level="error"
```

## Testing Your Queries

### Start Simple
```logql
# Step 1: Basic label selector
{job="web-server"}

# Step 2: Add line filter
{job="web-server"} |= "error"

# Step 3: Add time range
{job="web-server"} |= "error" [1h]

# Step 4: Add parsing if needed
{job="web-server"} |= "error" | json | severity="high"
```

### Verify Results
Always check your query results make sense:
- Are you getting the expected number of results?
- Do the timestamps look correct?
- Are the log messages what you expected?

### Use MCP Tools Effectively
```python
# First, discover available labels
get_labels_params = {}

# Then, explore specific label values
get_labels_params = {"label_name": "job"}

# Finally, query with discovered labels
query_params = {
    "query": "{job=\"discovered-service\"} |= \"error\"",
    "start": "1h"
}
```