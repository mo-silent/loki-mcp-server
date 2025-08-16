# Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues with the Loki MCP Server.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Connection Issues](#connection-issues)
3. [Authentication Problems](#authentication-problems)
4. [Query Errors](#query-errors)
5. [Performance Issues](#performance-issues)
6. [Configuration Problems](#configuration-problems)
7. [MCP Protocol Issues](#mcp-protocol-issues)
8. [Loki Server Issues](#loki-server-issues)
9. [Network and Firewall Issues](#network-and-firewall-issues)
10. [Debug Mode and Logging](#debug-mode-and-logging)

## Quick Diagnostics

Start with these basic checks before diving into specific issues.

### Health Check Commands

```bash
# Check if Loki is accessible
curl -f http://localhost:3100/ready

# Check environment variables
env | grep LOKI

# Test MCP server startup
loki-mcp-server --help

# Verify Python installation
python -c "import app; print('OK')"
```

### Basic Connectivity Test

```python
# Test script: test_connection.py
import os
import asyncio
from app.config import load_config
from app.enhanced_client import EnhancedLokiClient

async def test_connection():
    try:
        config = load_config()
        print(f"Testing connection to: {config.url}")
        
        async with EnhancedLokiClient(config) as client:
            labels = await client.label_names()
            print(f"✅ Connection successful! Found {len(labels)} labels.")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())
```

## Connection Issues

### Problem: "Connection refused" or "Connection timeout"

#### Symptoms
- Error messages about connection being refused
- Timeouts when trying to reach Loki
- Network-related error messages

#### Diagnosis Steps

1. **Verify Loki URL**:
   ```bash
   echo $LOKI_URL
   # Should output something like: http://localhost:3100
   ```

2. **Test direct connectivity**:
   ```bash
   curl -v http://localhost:3100/ready
   # Should return: ready
   ```

3. **Check if Loki is running**:
   ```bash
   # For Docker
   docker ps | grep loki
   
   # For systemd
   systemctl status loki
   
   # Check process
   ps aux | grep loki
   ```

4. **Verify port availability**:
   ```bash
   netstat -tuln | grep 3100
   # Should show Loki listening on port 3100
   ```

#### Solutions

**Loki Not Running**:
```bash
# Start Loki with Docker
docker run -d --name loki -p 3100:3100 grafana/loki:latest

# Or with Docker Compose
cd examples/docker
docker-compose up -d loki
```

**Wrong URL Configuration**:
```bash
# Correct the URL
export LOKI_URL="http://localhost:3100"

# For remote Loki
export LOKI_URL="https://loki.yourdomain.com"
```

**Firewall Issues**:
```bash
# Check if port is blocked
telnet localhost 3100

# For remote hosts
telnet your-loki-host 3100
```

### Problem: "SSL/TLS errors"

#### Symptoms
- SSL certificate verification failures
- TLS handshake errors
- Certificate validation errors

#### Solutions

**Self-signed certificates**:
```bash
# Temporarily skip SSL verification (not recommended for production)
export LOKI_SKIP_TLS_VERIFY="true"
```

**Certificate issues**:
```bash
# Update CA certificates
sudo apt-get update && sudo apt-get install ca-certificates

# Or use specific certificate
export LOKI_CA_CERT_PATH="/path/to/ca-cert.pem"
```

## Authentication Problems

### Problem: "401 Unauthorized" or "403 Forbidden"

#### Symptoms
- Authentication failures
- Access denied messages
- Token validation errors

#### Diagnosis Steps

1. **Check credentials**:
   ```bash
   echo $LOKI_USERNAME
   echo $LOKI_PASSWORD | head -c 5  # Only show first 5 chars
   echo $LOKI_BEARER_TOKEN | head -c 10  # Only show first 10 chars
   ```

2. **Test authentication manually**:
   ```bash
   # Basic auth
   curl -u "$LOKI_USERNAME:$LOKI_PASSWORD" http://localhost:3100/ready
   
   # Bearer token
   curl -H "Authorization: Bearer $LOKI_BEARER_TOKEN" http://localhost:3100/ready
   ```

3. **Verify Loki auth configuration**:
   ```bash
   # Check if Loki requires auth
   curl http://localhost:3100/ready
   # If this works but MCP server doesn't, check auth config
   ```

#### Solutions

**Invalid Credentials**:
```bash
# Reset credentials
export LOKI_USERNAME="correct-username"
export LOKI_PASSWORD="correct-password"

# Or use token
unset LOKI_USERNAME LOKI_PASSWORD
export LOKI_BEARER_TOKEN="valid-token"
```

**Expired Token**:
```bash
# Get new token from your auth provider
export LOKI_BEARER_TOKEN="new-valid-token"
```

**Mixed Auth Methods**:
```bash
# Use only one method
unset LOKI_BEARER_TOKEN  # If using basic auth
# OR
unset LOKI_USERNAME LOKI_PASSWORD  # If using token
```

### Problem: "Token validation failed"

#### Symptoms
- Bearer token rejection
- Token format errors
- Authorization header issues

#### Solutions

**Check token format**:
```bash
# Token should not include "Bearer " prefix
export LOKI_BEARER_TOKEN="abc123xyz789"  # ✅ Correct
export LOKI_BEARER_TOKEN="Bearer abc123xyz789"  # ❌ Wrong
```

**Verify token scope**:
```bash
# Ensure token has necessary permissions
# Check with your auth provider or Grafana admin
```

## Query Errors

### Problem: "Invalid LogQL query" or syntax errors

#### Symptoms
- LogQL parsing errors
- Syntax error messages
- Query execution failures

#### Common Query Issues

**Unbalanced braces**:
```logql
# ❌ Wrong
{job="api" |= "error"

# ✅ Correct  
{job="api"} |= "error"
```

**Invalid label names**:
```logql
# ❌ Wrong - label doesn't exist
{nonexistent_label="value"}

# ✅ Correct - use get_labels to discover
{job="api"}
```

**Regex syntax errors**:
```logql
# ❌ Wrong - invalid regex
{job=~"[api"}

# ✅ Correct
{job=~"api.*"}
```

#### Diagnosis Steps

1. **Test query in Grafana**:
   - Copy query to Grafana Explore
   - Check for syntax highlighting errors

2. **Simplify query progressively**:
   ```logql
   # Start simple
   {job="api"}
   
   # Add filters one by one
   {job="api"} |= "error"
   {job="api"} |= "error" | json
   {job="api"} |= "error" | json | level="error"
   ```

3. **Validate with MCP tools**:
   ```python
   # Use get_labels to verify label names
   get_labels_result = {"use_cache": True}
   
   # Use search_logs for complex filters
   search_result = {
       "keywords": ["error"],
       "labels": {"job": "api"}
   }
   ```

### Problem: "No data found" or empty results

#### Symptoms
- Queries return no results
- Empty response arrays
- Zero total counts

#### Diagnosis Steps

1. **Check time range**:
   ```python
   # Too narrow time range
   {"query": "{job=\"api\"}", "start": "1m"}  # May be too short
   
   # Broader time range  
   {"query": "{job=\"api\"}", "start": "1h"}  # Better
   ```

2. **Verify label values**:
   ```python
   # Check available jobs
   {"label_name": "job"}
   
   # Use discovered values
   {"query": "{job=\"discovered-job-name\"}"}
   ```

3. **Test without filters**:
   ```logql
   # Start broad
   {job="api"}
   
   # Add filters gradually
   {job="api"} |= "error"
   ```

## Performance Issues

### Problem: Slow query execution

#### Symptoms
- Long response times
- Timeouts
- High CPU/memory usage

#### Diagnosis

1. **Profile query performance**:
   ```python
   import time
   
   start_time = time.time()
   result = query_logs({"query": "your-query", "start": "1h"})
   execution_time = time.time() - start_time
   
   print(f"Query took {execution_time:.2f} seconds")
   print(f"Returned {result['total_entries']} entries")
   ```

2. **Check query complexity**:
   ```logql
   # Slow - no label selectors
   |= "error"
   
   # Fast - good label selector
   {job="api"} |= "error"
   ```

#### Solutions

**Optimize label selectors**:
```logql
# ❌ Slow - broad selection
{level="error"}

# ✅ Fast - specific selection
{job="api", environment="prod"} |= "error"
```

**Reduce time range**:
```python
# ❌ Slow - large time range
{"query": "{job=\"api\"}", "start": "7d"}

# ✅ Fast - reasonable time range
{"query": "{job=\"api\"}", "start": "1h"}
```

**Use appropriate limits**:
```python
# ❌ Slow - no limit
{"query": "{job=\"high-volume\"} |= \"error\""}

# ✅ Fast - reasonable limit
{"query": "{job=\"high-volume\"} |= \"error\"", "limit": 100}
```

**Enable caching**:
```python
# Use caching for label queries
{"label_name": "job", "use_cache": True}
```

### Problem: Memory issues or out-of-memory errors

#### Solutions

**Reduce result size**:
```python
# Use smaller limits
{"query": "{job=\"api\"}", "limit": 100}

# Use shorter time ranges
{"query": "{job=\"api\"}", "start": "15m"}
```

**Stream large datasets**:
```python
# Process in chunks
time_ranges = ["1h", "2h", "3h", "4h"]
for time_range in time_ranges:
    result = query_logs({
        "query": "{job=\"api\"}",
        "start": time_range,
        "end": f"{int(time_range[0])-1}h",
        "limit": 500
    })
    # Process chunk
```

## Configuration Problems

### Problem: Environment variables not loaded

#### Symptoms
- Default values being used
- "Configuration not found" errors
- Settings not taking effect

#### Solutions

**Check environment variables**:
```bash
# List all Loki-related env vars
env | grep LOKI

# Set explicitly
export LOKI_URL="http://localhost:3100"
export LOKI_USERNAME="admin"
export LOKI_PASSWORD="password"
```

**Use .env file**:
```bash
# Create .env file
cat > .env << EOF
LOKI_URL=http://localhost:3100
LOKI_USERNAME=admin
LOKI_PASSWORD=password
EOF

# Load .env file
source .env
```

**Verify configuration loading**:
```python
# Test script
from app.config import load_config

config = load_config()
print(f"URL: {config.url}")
print(f"Username: {config.username}")
print(f"Has password: {bool(config.password)}")
print(f"Has token: {bool(config.bearer_token)}")
```

### Problem: Claude Desktop integration issues

#### Symptoms
- MCP server not appearing in Claude
- Tool discovery failures
- Communication errors

#### Solutions

**Check Claude config location**:
```bash
# macOS
ls -la ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
dir %APPDATA%\Claude\claude_desktop_config.json
```

**Validate config syntax**:
```bash
# Check JSON syntax
python -m json.tool ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Correct config format**:
```json
{
  "mcpServers": {
    "loki": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "http://localhost:3100"
      }
    }
  }
}
```

**Use full path if needed**:
```json
{
  "mcpServers": {
    "loki": {
      "command": "/full/path/to/loki-mcp-server",
      "env": {
        "LOKI_URL": "http://localhost:3100"
      }
    }
  }
}
```

## MCP Protocol Issues

### Problem: Tool discovery failures

#### Symptoms
- Tools not available in Claude
- "No tools found" messages
- MCP handshake failures

#### Solutions

**Test MCP server directly**:
```bash
# Run server and test manually
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | loki-mcp-server
```

**Check server startup**:
```bash
# Enable debug logging
DEBUG=true loki-mcp-server
```

**Verify installation**:
```bash
# Check if installed correctly
pip show loki-mcp-server

# Reinstall if needed
pip install -e .
```

## Loki Server Issues

### Problem: Loki server errors or instability

#### Symptoms
- Loki returning 500 errors
- Inconsistent responses
- Server timeouts

#### Diagnosis

**Check Loki logs**:
```bash
# Docker
docker logs loki-container-name

# Systemd
journalctl -u loki -f

# Local instance
tail -f /var/log/loki/loki.log
```

**Check Loki health**:
```bash
curl http://localhost:3100/ready
curl http://localhost:3100/metrics
```

#### Solutions

**Restart Loki**:
```bash
# Docker
docker restart loki-container

# Systemd
sudo systemctl restart loki
```

**Check Loki configuration**:
```yaml
# Ensure proper config in loki.yaml
server:
  http_listen_port: 3100
  grpc_listen_port: 9096

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
```

## Network and Firewall Issues

### Problem: Network connectivity problems

#### Diagnosis

**Test network path**:
```bash
# Test connectivity
ping loki-host

# Test port
telnet loki-host 3100

# Trace route
traceroute loki-host
```

**Check firewall rules**:
```bash
# Linux iptables
sudo iptables -L | grep 3100

# UFW
sudo ufw status | grep 3100

# Check if port is open
nmap -p 3100 loki-host
```

#### Solutions

**Open firewall ports**:
```bash
# UFW
sudo ufw allow 3100

# iptables
sudo iptables -A INPUT -p tcp --dport 3100 -j ACCEPT
```

**Configure proxy if needed**:
```bash
export HTTP_PROXY="http://proxy:8080"
export HTTPS_PROXY="http://proxy:8080"
export NO_PROXY="localhost,127.0.0.1"
```

## Debug Mode and Logging

### Enable Debug Logging

**Environment variable**:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
loki-mcp-server
```

**Python logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or in code
import structlog
logger = structlog.get_logger(__name__)
logger.setLevel(logging.DEBUG)
```

### Debugging Workflow

1. **Enable debug mode**:
   ```bash
   DEBUG=true LOG_LEVEL=DEBUG loki-mcp-server
   ```

2. **Test basic connectivity**:
   ```bash
   curl -v http://localhost:3100/ready
   ```

3. **Test with simple query**:
   ```python
   {"query": "{}", "limit": 1}
   ```

4. **Gradually increase complexity**:
   ```python
   {"query": "{job=\"api\"}", "limit": 10}
   {"query": "{job=\"api\"} |= \"error\"", "limit": 10}
   ```

### Log Analysis

**Look for these patterns**:
- Connection errors: `Connection refused`, `Timeout`
- Auth errors: `401`, `403`, `Authentication failed`
- Query errors: `Invalid query`, `Parse error`
- Performance issues: `Slow query`, `High memory usage`

## Getting Help

If you can't resolve the issue:

1. **Check the GitHub issues**: Look for similar problems
2. **Create a minimal reproduction case**
3. **Gather debug information**:
   - Environment variables (sanitized)
   - Error messages
   - Query that's failing
   - Loki version and configuration
   - MCP server version

4. **Include debug output**:
   ```bash
   DEBUG=true loki-mcp-server 2>&1 | head -50
   ```

5. **Test with example configuration**:
   - Use the Docker Compose example
   - Try with a fresh Loki instance
   - Verify with known-good queries

## Common Error Messages Reference

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `Connection refused` | Loki not running | Start Loki service |
| `401 Unauthorized` | Wrong credentials | Check auth settings |
| `404 Not Found` | Wrong URL/endpoint | Verify LOKI_URL |
| `Invalid query` | LogQL syntax error | Check query syntax |
| `No data found` | Wrong time range | Expand time range |
| `Rate limit exceeded` | Too many requests | Reduce query frequency |
| `Timeout` | Network/performance | Check network, optimize query |
| `Parse error` | Malformed log format | Check log parsing |

This troubleshooting guide should help you diagnose and resolve most issues with the Loki MCP Server. For complex problems, don't hesitate to seek help from the community or maintainers.