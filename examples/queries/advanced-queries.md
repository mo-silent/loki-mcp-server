# Advanced LogQL Queries

This guide covers complex LogQL queries for sophisticated log analysis and monitoring use cases.

## Advanced Log Parsing

### Complex JSON Parsing
```logql
{job="api"} 
| json 
| request_id != "" 
| response_time_ms > 1000
| line_format "{{.timestamp}} [{{.level}}] Request {{.request_id}} took {{.response_time_ms}}ms"
```
*Parse JSON logs, filter slow requests, and reformat output*

### Multi-level JSON Parsing
```logql
{job="microservice"} 
| json 
| json request="request" 
| json response="response"
| request_method="POST" 
| response_status >= 400
```
*Parse nested JSON structures*

### Conditional Parsing
```logql
{job="mixed-logs"} 
| json message="" 
| __error__ = "" 
| level="error"
or
{job="mixed-logs"} 
| logfmt 
| __error__ = "" 
| level="error"
```
*Handle logs with mixed formats*

### Complex Field Extraction
```logql
{job="nginx"} 
| regexp `(?P<ip>\d+\.\d+\.\d+\.\d+).*?"(?P<method>\w+) (?P<path>[^"]*)".*?(?P<status>\d{3}) (?P<size>\d+) (?P<duration>[\d.]+)`
| status >= 400
| duration > 1.0
```
*Extract multiple fields from complex log formats*

## Advanced Filtering and Transformations

### Complex Boolean Logic
```logql
{job="api"} 
| json 
| (level="error" and component="database") 
  or (level="warn" and response_time > 5000)
  or (status >= 500)
```
*Complex conditional filtering*

### Pattern-based Line Filtering
```logql
{job="security"} 
|~ `(?i)(failed.*login|unauthorized.*access|suspicious.*activity|brute.*force)`
| json timestamp="", user="", ip="", action=""
| ip !~ "192\.168\..*|10\..*|172\.(1[6-9]|2[0-9]|3[01])\..*"
```
*Security event detection with private IP exclusion*

### Data Transformation
```logql
{job="ecommerce"} 
| json 
| order_value != "" 
| label_format order_category="{{if gt .order_value 1000}}premium{{else if gt .order_value 100}}standard{{else}}basic{{end}}"
| unwrap order_value 
| sum by (order_category)
```
*Categorize and aggregate order values*

### Rate Limiting Analysis
```logql
{job="api-gateway"} 
| json 
| status="429" 
| label_format client_tier="{{if .rate_limit_tier}}{{.rate_limit_tier}}{{else}}unknown{{end}}"
| count by (client_tier, client_id) 
> 10
```
*Identify clients hitting rate limits frequently*

## Advanced Aggregations and Metrics

### Percentile Calculations
```logql
quantile_over_time(0.95, 
  {job="api"} 
  | json 
  | unwrap response_time_ms [5m]
) by (endpoint)
```
*95th percentile response times by endpoint*

### Multi-dimensional Aggregations
```logql
sum by (service, region, environment) (
  rate({job=~".*", environment=~"prod|staging"} 
  | json 
  | level="error" [5m])
) > 0.1
```
*Error rates across multiple dimensions*

### Histogram Analysis
```logql
histogram_quantile(0.99,
  sum by (le) (
    rate({job="api"} 
    | json 
    | unwrap duration_bucket [5m])
  )
)
```
*99th percentile from histogram buckets*

### Complex Rate Calculations
```logql
(
  sum(rate({job="payment-service"} | json | status="success" [5m])) /
  sum(rate({job="payment-service"} | json [5m]))
) * 100
```
*Payment success rate percentage*

### Anomaly Detection
```logql
(
  rate({job="api"} | json | level="error" [5m])
  /
  rate({job="api"} | json [5m])
) > bool 0.05
```
*Alert when error rate exceeds 5%*

## Time Series Analysis

### Moving Averages
```logql
avg_over_time(
  rate({job="metrics"} 
  | json 
  | unwrap cpu_usage [1m])[10m:1m]
)
```
*10-minute moving average of CPU usage*

### Trend Analysis
```logql
increase(
  sum(count_over_time({job="orders"} 
  | json 
  | status="completed" [1h]))
)[24h:1h]
```
*24-hour trend of completed orders*

### Delta Calculations
```logql
delta(
  max_over_time({job="database"} 
  | json 
  | unwrap connection_count [5m])
)[1h:5m]
```
*Connection count changes over time*

### Seasonal Pattern Detection
```logql
(
  rate({job="web"} [1h]) -
  rate({job="web"} offset 24h [1h])
) / rate({job="web"} offset 24h [1h]) * 100
```
*Day-over-day percentage change in request rate*

## Advanced Use Cases

### Distributed Tracing Correlation
```logql
{job=~"service-.*"} 
| json 
| trace_id="abc123" 
| sort by (timestamp) asc
| line_format "{{.timestamp}} [{{.service}}] {{.span_name}}: {{.message}}"
```
*Follow a distributed trace across services*

### Error Pattern Analysis
```logql
{job="api"} 
| json 
| level="error" 
| regexp `(?P<error_type>.*Exception|.*Error)` 
| count by (error_type) 
| sort desc
```
*Categorize and count different error types*

### Performance Regression Detection
```logql
(
  quantile(0.95, 
    {job="api"} | json | unwrap response_time [1h]
  ) 
  -
  quantile(0.95, 
    {job="api"} | json | unwrap response_time offset 24h [1h]
  )
) > 100
```
*Detect response time regressions > 100ms*

### User Journey Analysis
```logql
{job="web"} 
| json 
| user_id!="" 
| user_id="user123"
| sort by (timestamp) asc
| line_format "{{.timestamp}}: {{.action}} on {{.page}}"
```
*Track specific user's journey through application*

### Resource Usage Correlation
```logql
{job="kubernetes"} 
| json 
| pod_name!="" 
| regexp `(?P<resource_type>cpu|memory|disk)` 
| unwrap usage_percent 
| avg by (pod_name, resource_type) 
| > 80
```
*Find pods with high resource usage*

### Business Intelligence Queries
```logql
sum by (product_category) (
  {job="ecommerce"} 
  | json 
  | event="purchase" 
  | unwrap order_value 
) > 10000
```
*Revenue by product category (over $10k)*

### Security Threat Detection
```logql
{job="security"} 
| json 
| ip!="" 
| ip !~ "192\.168\..*" 
| (
    action =~ "(?i)login.*fail" 
    or action =~ "(?i)brute.*force"
    or action =~ "(?i)suspicious"
  )
| count by (ip) > 5
```
*Detect potential security threats from external IPs*

### SLA Monitoring
```logql
1 - (
  sum(rate({job="api"} | json | status >= 500 [5m])) /
  sum(rate({job="api"} | json [5m]))
) * 100 > 99.9
```
*Check if availability SLA (99.9%) is being met*

## MCP Server Advanced Usage

### Complex Query Tool Usage
```python
{
  "query": """
    sum by (service, error_type) (
      rate({environment="production"} 
      | json 
      | level="error" 
      | regexp `(?P<error_type>.*Exception)` [5m])
    ) > 0.01
  """,
  "start": "2h",
  "end": "now",
  "limit": 1000
}
```

### Multi-stage Analysis
```python
# Stage 1: Find problematic services
stage1_query = """
sum by (service) (
  rate({environment="prod"} | json | level="error" [15m])
) > 0.1
"""

# Stage 2: Deep dive into specific service
stage2_query = """
{environment="prod", service="problematic-service"} 
| json 
| level="error" 
| line_format "{{.timestamp}} [{{.component}}]: {{.message}}"
"""
```

### Conditional Search Patterns
```python
{
  "keywords": ["OutOfMemoryError", "GC overhead", "heap space"],
  "labels": {"environment": "production"},
  "operator": "OR",
  "start": "4h",
  "case_sensitive": True
}
```

## Performance Optimization

### Efficient Label Selection
```logql
# Efficient - uses indexed labels first
{job="api", environment="prod", region="us-east-1"} 
| json 
| level="error"

# Less efficient - broad initial selection
{level="error"} 
| job="api" 
| environment="prod"
```

### Smart Time Windowing
```logql
# For high-frequency data, use smaller windows
rate({job="high-volume-service"}[30s]) by (endpoint)

# For trend analysis, use larger windows
increase({job="daily-reports"}[24h:1h])
```

### Optimized Parsing
```logql
# Parse only what you need
{job="api"} 
| json status="", response_time=""
| status >= 400

# Avoid parsing everything
{job="api"} 
| json 
| status >= 400
```

### Efficient Aggregations
```logql
# Pre-filter before aggregating
sum by (service) (
  rate({job=~"service-.*"} | json | status >= 500 [5m])
)

# More efficient than post-filtering
sum by (service) (
  rate({job=~"service-.*"} | json [5m])
) and status >= 500
```

## Best Practices for Advanced Queries

1. **Use Label Indexes**: Start with the most selective labels
2. **Parse Strategically**: Only parse fields you actually use
3. **Optimize Time Ranges**: Use appropriate windows for your use case
4. **Test Incrementally**: Build complex queries step by step
5. **Monitor Performance**: Watch query execution times
6. **Cache Results**: Use caching for repeated complex queries
7. **Document Queries**: Comment complex queries for maintenance

## Common Advanced Patterns

### Error Correlation
```logql
{job="api"} 
| json 
| trace_id!="" 
| level="error" 
| trace_id="{{.trace_id}}"
```

### Capacity Planning
```logql
predict_linear(
  rate({job="api"}[1h])[7d:1h], 
  86400 * 30
)
```

### A/B Testing Analysis
```logql
sum by (experiment_variant) (
  rate({job="web"} 
  | json 
  | event="conversion" [1h])
) / 
sum by (experiment_variant) (
  rate({job="web"} 
  | json 
  | event="view" [1h])
) * 100
```

These advanced patterns enable sophisticated log analysis for complex operational and business intelligence use cases.