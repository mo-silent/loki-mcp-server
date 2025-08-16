# LogQL Query Examples and Best Practices

This directory contains comprehensive examples of LogQL queries for use with the Loki MCP Server, organized by use case and complexity.

## Directory Structure

- `basic-queries.md` - Simple LogQL queries for getting started
- `advanced-queries.md` - Complex queries for deep analysis
- `performance-tips.md` - Optimization techniques and best practices
- `common-patterns.md` - Frequently used query patterns
- `troubleshooting-queries.md` - Queries for debugging and troubleshooting
- `metric-queries.md` - Log-based metrics and aggregations

## Quick Reference

### Basic Query Structure
```logql
{label="value"} |= "search_term" | filter | aggregation
```

### Common Labels
- `job` - Application or service name
- `level` - Log level (error, warn, info, debug)
- `instance` - Server or container instance
- `namespace` - Kubernetes namespace
- `pod` - Kubernetes pod name

### Useful Operators
- `|=` - Line contains string
- `!~` - Line doesn't match regex
- `| json` - Parse JSON logs
- `| logfmt` - Parse logfmt logs
- `| regexp` - Extract fields with regex

### Time Ranges
- `5m` - Last 5 minutes
- `1h` - Last 1 hour
- `1d` - Last 1 day
- `2023-01-01T00:00:00Z` - Specific timestamp

## Getting Started

1. Start with basic label filtering: `{job="your-app"}`
2. Add line filtering: `{job="your-app"} |= "error"`
3. Parse structured logs: `{job="your-app"} | json`
4. Extract metrics: `count_over_time({job="your-app"}[5m])`

## MCP Server Usage

With the Loki MCP Server, you can use these queries in several ways:

### Direct LogQL Queries
```python
# Via query_logs tool
params = {
    "query": '{job="web-server"} |= "error"',
    "start": "1h",
    "limit": 50
}
```

### Keyword Search
```python
# Via search_logs tool
params = {
    "keywords": ["error", "exception"],
    "labels": {"job": "web-server"},
    "start": "1h"
}
```

### Label Discovery
```python
# Via get_labels tool
params = {
    "label_name": "job"  # Get all job values
}
```

## Best Practices Summary

1. **Start Narrow**: Begin with specific labels
2. **Limit Time Range**: Use appropriate time windows
3. **Parse Early**: Parse logs before filtering
4. **Use Indexes**: Leverage indexed labels
5. **Optimize Performance**: Follow the performance tips
6. **Test Incrementally**: Build complex queries step by step

See individual files for detailed examples and explanations.