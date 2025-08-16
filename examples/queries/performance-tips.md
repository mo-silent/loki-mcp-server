# LogQL Performance Tips and Optimization

This guide provides comprehensive performance optimization techniques for LogQL queries used with the Loki MCP Server.

## Query Performance Fundamentals

### Understanding Query Execution

LogQL queries are executed in this order:
1. **Label Selection**: Filter streams using indexed labels
2. **Line Filtering**: Scan log lines for text patterns
3. **Log Parsing**: Extract structured data from lines
4. **Label Filtering**: Filter based on extracted labels
5. **Aggregation**: Perform mathematical operations

Optimize each stage for maximum performance.

## Label Selection Optimization

### Use Indexed Labels First
```logql
# Good - starts with most selective indexed labels
{job="api", environment="prod", region="us-east-1"} |= "error"

# Poor - starts with broad selection
{level="error"} | job="api" | environment="prod"
```

### Cardinality Considerations
```logql
# High cardinality labels (avoid in initial selection)
{request_id="abc123"}  # Each request has unique ID

# Low cardinality labels (good for initial selection)  
{job="api", environment="prod"}  # Few unique values
```

### Label Selector Strategies
```logql
# Most selective first
{service="user-auth", datacenter="dc1", level="error"}

# Use regex judiciously
{job=~"api-.*"}  # OK for small set of matches
{job=~".*"}      # Avoid - matches everything
```

### Optimal Label Combinations
```python
# MCP Server: Start with discovery
get_labels_params = {}  # Get all label names
get_labels_params = {"label_name": "job"}  # Get job values

# Then optimize your query
query_params = {
    "query": "{job=\"high-volume-service\", environment=\"prod\"} |= \"error\"",
    "start": "1h"
}
```

## Line Filtering Performance

### String Operations Efficiency
```logql
# Fast - simple string contains
{job="api"} |= "error"

# Slower - complex regex
{job="api"} |~ "error|exception|fail.*critical"

# Fastest for multiple terms
{job="api"} |= "error" or |= "exception" or |= "critical"
```

### Regex Optimization
```logql
# Inefficient regex
{job="api"} |~ ".*error.*"

# Better - use contains
{job="api"} |= "error"

# Efficient regex when needed
{job="api"} |~ "^ERROR|^FATAL"  # Anchored patterns are faster
```

### Case Sensitivity
```logql
# Faster - case sensitive (default)
{job="api"} |= "ERROR"

# Slower - case insensitive
{job="api"} |~ "(?i)error"
```

### Multiple Filters
```logql
# Chain filters from most to least selective
{job="api"} |= "database" |= "timeout" != "retry"

# Combine related filters
{job="api"} |~ "database.*timeout|timeout.*database"
```

## Log Parsing Performance

### Parse Only What You Need
```logql
# Inefficient - parses entire JSON
{job="api"} | json | status >= 400

# Efficient - parse specific fields
{job="api"} | json status="", response_time="" | status >= 400
```

### Conditional Parsing
```logql
# Parse only error logs
{job="api"} |= "error" | json | severity="high"

# More efficient than parsing everything
{job="api"} | json | level="error" | severity="high"
```

### Parser Selection
```logql
# Use appropriate parser
{job="api"} | json          # For JSON logs
{job="web"} | logfmt        # For logfmt logs  
{job="nginx"} | regexp      # For custom formats

# Avoid wrong parser (causes __error__)
{job="plaintext"} | json    # Will fail to parse
```

### Error Handling
```logql
# Include error handling
{job="api"} | json | __error__ = ""

# Or filter out parse errors
{job="api"} | json | __error__ != ""
```

## Time Range Optimization

### Appropriate Time Windows
```logql
# For real-time monitoring
{job="api"} |= "error" [5m]

# For historical analysis
{job="api"} |= "error" [24h]

# Avoid unnecessarily large ranges
{job="api"} |= "error" [30d]  # Usually too large
```

### Time Range Strategies
```python
# MCP Server: Use appropriate time ranges
query_params = {
    "query": "{job=\"api\"} |= \"error\"",
    "start": "15m",  # Recent issues
    "limit": 100
}

# For trends
query_params = {
    "query": "rate({job=\"api\"} |= \"error\" [5m])",
    "start": "4h",   # Longer range for trends
    "end": "now"
}
```

### Sliding Windows
```logql
# Efficient sliding window
rate({job="api"}[5m])

# Less efficient large window
rate({job="api"}[1h])  # If you only need 5-minute resolution
```

## Aggregation Performance

### Pre-filtering Before Aggregation
```logql
# Efficient - filter then aggregate
sum by (service) (
  rate({environment="prod"} | json | status >= 500 [5m])
)

# Less efficient - aggregate then filter
sum by (service) (
  rate({environment="prod"} | json [5m])
) and status >= 500
```

### Grouping Optimization
```logql
# Limit grouping dimensions
sum by (service) (rate({job=~".*"}[5m]))

# Avoid high-cardinality grouping
sum by (request_id) (rate({job=~".*"}[5m]))  # Too many groups
```

### Aggregation Function Selection
```logql
# Use appropriate aggregation
count_over_time({job="api"}[5m])  # Count log lines
rate({job="api"}[5m])             # Rate per second
increase({job="api"}[1h])         # Total increase
```

## Memory and Resource Management

### Query Result Limits
```python
# MCP Server: Use reasonable limits
query_params = {
    "query": "{job=\"high-volume\"} |= \"error\"",
    "limit": 1000,  # Reasonable limit
    "start": "1h"
}

# Avoid unlimited queries
query_params = {
    "query": "{job=\"high-volume\"} |= \"error\"",
    # No limit - could return millions of lines
    "start": "1d"
}
```

### Streaming vs Batch Queries
```python
# For large datasets, use smaller time windows
for hour in range(24):
    query_params = {
        "query": "{job=\"api\"} |= \"error\"",
        "start": f"{hour}h",
        "end": f"{hour-1}h",
        "limit": 1000
    }
```

### Memory-Efficient Patterns
```logql
# Memory efficient - counts only
count_over_time({job="api"}[1h])

# Memory intensive - returns all lines
{job="api"}[1h]
```

## Caching Strategies

### Label Caching
```python
# MCP Server: Use caching for label queries
get_labels_params = {
    "use_cache": True,  # Enable caching
    "label_name": "job"
}
```

### Query Result Caching
```python
# Cache frequently used queries
common_queries = {
    "error_rate": "rate({job=\"api\"} |= \"error\" [5m])",
    "request_count": "rate({job=\"api\"} [5m])",
    "slow_queries": "{job=\"api\"} | json | response_time > 1000"
}
```

### Time-based Cache Invalidation
```python
import time
from datetime import datetime, timedelta

class QueryCache:
    def __init__(self, ttl_minutes=5):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, query, time_range):
        key = f"{query}:{time_range}"
        if key in self.cache:
            result, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return result
        return None
    
    def set(self, query, time_range, result):
        key = f"{query}:{time_range}"
        self.cache[key] = (result, datetime.now())
```

## Query Planning and Testing

### Progressive Query Building
```logql
# Step 1: Start with labels
{job="api", environment="prod"}

# Step 2: Add line filters
{job="api", environment="prod"} |= "error"

# Step 3: Add parsing
{job="api", environment="prod"} |= "error" | json

# Step 4: Add field filters
{job="api", environment="prod"} |= "error" | json | status >= 500

# Step 5: Add aggregation
count_over_time({job="api", environment="prod"} |= "error" | json | status >= 500 [5m])
```

### Query Performance Testing
```python
import time

def benchmark_query(query_params):
    start_time = time.time()
    
    # Execute query via MCP Server
    result = execute_query(query_params)
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    print(f"Query: {query_params['query']}")
    print(f"Execution time: {execution_time:.2f}s")
    print(f"Result count: {len(result.get('entries', []))}")
    
    return execution_time

# Test different query variations
queries = [
    "{job=\"api\"} |= \"error\"",
    "{job=\"api\", level=\"error\"}",
    "{job=\"api\"} | json | level=\"error\""
]

for query in queries:
    benchmark_query({"query": query, "start": "1h", "limit": 100})
```

### A/B Testing Query Performance
```python
def compare_queries(query_a, query_b, iterations=3):
    times_a = []
    times_b = []
    
    for i in range(iterations):
        time_a = benchmark_query({"query": query_a, "start": "1h"})
        time_b = benchmark_query({"query": query_b, "start": "1h"})
        
        times_a.append(time_a)
        times_b.append(time_b)
    
    avg_a = sum(times_a) / len(times_a)
    avg_b = sum(times_b) / len(times_b)
    
    print(f"Query A average: {avg_a:.2f}s")
    print(f"Query B average: {avg_b:.2f}s")
    print(f"Performance improvement: {((avg_a - avg_b) / avg_a * 100):.1f}%")
```

## Monitoring Query Performance

### Performance Metrics to Track
```python
query_metrics = {
    "execution_time": 0.0,
    "bytes_processed": 0,
    "lines_examined": 0,
    "lines_returned": 0,
    "cache_hit_rate": 0.0,
    "query_complexity": "simple|medium|complex"
}
```

### Slow Query Detection
```python
def log_slow_query(query, execution_time, threshold=5.0):
    if execution_time > threshold:
        print(f"SLOW QUERY DETECTED:")
        print(f"Query: {query}")
        print(f"Time: {execution_time:.2f}s")
        print(f"Threshold: {threshold}s")
        
        # Suggest optimizations
        suggest_optimizations(query)

def suggest_optimizations(query):
    suggestions = []
    
    if not query.startswith('{'):
        suggestions.append("Add label selectors at the beginning")
    
    if '.*' in query:
        suggestions.append("Avoid .* regex patterns")
    
    if '| json' in query and not ('|=' in query or '!=' in query):
        suggestions.append("Add line filters before JSON parsing")
    
    for suggestion in suggestions:
        print(f"💡 {suggestion}")
```

## Performance Anti-patterns

### Avoid These Patterns

#### 1. No Label Selection
```logql
# Bad - scans all logs
|= "error"

# Good - uses label index
{job="api"} |= "error"
```

#### 2. Broad Regex
```logql
# Bad - expensive regex
{job="api"} |~ ".*error.*"

# Good - simple contains
{job="api"} |= "error"
```

#### 3. Parse Before Filter
```logql
# Bad - parses all lines
{job="api"} | json | level="error"

# Good - filters then parses
{job="api"} |= "error" | json | level="error"
```

#### 4. High Cardinality Grouping
```logql
# Bad - too many groups
sum by (request_id) (rate({job="api"}[5m]))

# Good - reasonable grouping
sum by (service, region) (rate({job="api"}[5m]))
```

#### 5. Unlimited Results
```python
# Bad - no limit
query_params = {
    "query": "{job=\"high-volume\"} |= \"error\"",
    "start": "24h"
}

# Good - reasonable limit
query_params = {
    "query": "{job=\"high-volume\"} |= \"error\"",
    "start": "24h",
    "limit": 1000
}
```

## Performance Best Practices Summary

1. **Start Narrow**: Begin with selective label filters
2. **Filter Early**: Use line filters before parsing
3. **Parse Selectively**: Only parse fields you need
4. **Limit Results**: Use appropriate limits and time ranges
5. **Use Caching**: Cache label information and frequent queries
6. **Monitor Performance**: Track query execution times
7. **Test Incrementally**: Build and test queries progressively
8. **Choose Appropriate Tools**: Use the right MCP tool for your use case

## Tool-Specific Performance Tips

### query_logs Tool
```python
# Optimize for LogQL queries
{
    "query": "{job=\"api\", environment=\"prod\"} |= \"error\" | json | status >= 500",
    "start": "1h",          # Reasonable time range
    "limit": 500,           # Reasonable limit
    "direction": "backward" # Most recent first
}
```

### search_logs Tool
```python
# Optimize for keyword searches
{
    "keywords": ["timeout", "connection"],  # Specific terms
    "labels": {"service": "database"},      # Narrow scope
    "start": "30m",                        # Short time range
    "operator": "AND",                     # More selective than OR
    "case_sensitive": False                # Only if needed
}
```

### get_labels Tool
```python
# Use caching for label queries
{
    "label_name": "job",    # Specific label
    "use_cache": True,      # Enable caching
    "start": "1h"          # Reasonable time window
}
```

Following these performance guidelines will ensure your LogQL queries run efficiently and provide fast results through the Loki MCP Server.