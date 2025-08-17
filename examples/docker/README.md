# Docker Examples

This directory contains Docker and Docker Compose configurations for running Loki MCP Server with a complete Loki stack.

## Quick Start

1. **Start the complete stack**:
   ```bash
   cd examples/docker
   docker-compose up -d
   ```

2. **Check if Loki is running**:
   ```bash
   curl http://localhost:3100/ready
   ```

3. **Test the MCP server**:
   ```bash
   docker-compose exec loki-mcp-server loki-mcp-server
   ```

## What's Included

The Docker Compose setup includes:

- **Loki**: Log aggregation system
- **Promtail**: Log collector that sends logs to Loki  
- **Log Generator**: Creates sample logs for testing
- **Loki MCP Server**: The MCP server container

## Configuration Files

### docker-compose.yml
Main orchestration file that defines all services and their relationships.

### Dockerfile
Multi-stage build for the Loki MCP Server with:
- Python 3.11 slim base
- Security-focused (non-root user)
- Optimized for size

### loki-config.yaml
Loki configuration optimized for development:
- No authentication required
- Local filesystem storage
- Reasonable retention policies

### promtail-config.yaml
Promtail configuration that collects:
- System logs from `/var/log`
- Docker container logs
- Generated application logs

## Usage Examples

### Basic Query Testing
```bash
# Enter the MCP server container
docker-compose exec loki-mcp-server bash

# Set environment
export LOKI_URL=http://loki:3100

# Test direct connection
curl http://loki:3100/loki/api/v1/label

# Run MCP server
loki-mcp-server
```

### Integration with Claude Desktop

Update your Claude Desktop config to point to the containerized Loki:

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

## Production Considerations

This setup is for development/testing. For production:

1. **Security**: Enable authentication in Loki
2. **Storage**: Use persistent volumes or object storage
3. **Networking**: Use proper network isolation
4. **Monitoring**: Add health checks and monitoring
5. **Scaling**: Consider Loki in microservices mode

## Customization

### Different Log Sources

To add your own log sources, update `promtail-config.yaml`:

```yaml
scrape_configs:
  - job_name: my-app
    static_configs:
      - targets:
          - localhost
        labels:
          job: my-app
          __path__: /path/to/my/logs/*.log
```

### Custom Loki Config

Modify `loki-config.yaml` for your needs:
- Change retention periods
- Configure different storage backends
- Add authentication
- Tune performance settings

### Environment Variables

Create a `.env` file for custom settings (copy from `.env.example`):

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
nano .env
```

Example `.env` content:
```env
LOKI_URL=http://loki:3100
DEBUG=true
LOG_LEVEL=DEBUG
LOKI_PORT=3100
PROMTAIL_PORT=9080
```

The environment variables are automatically loaded by docker-compose.

## Troubleshooting

### Logs Not Appearing
```bash
# Check Promtail logs
docker-compose logs promtail

# Check if Promtail can reach Loki
docker-compose exec promtail curl http://loki:3100/ready

# Verify log file permissions
docker-compose exec promtail ls -la /var/log/
```

### MCP Server Connection Issues
```bash
# Check Loki health
curl http://localhost:3100/ready

# Test from MCP server container
docker-compose exec loki-mcp-server curl http://loki:3100/ready

# Check environment variables
docker-compose exec loki-mcp-server env | grep LOKI
```

### Performance Issues
```bash
# Check resource usage
docker stats

# Monitor Loki metrics
curl http://localhost:3100/metrics

# Check disk usage
docker system df
```

## Cleanup

Stop and remove everything:
```bash
docker-compose down -v
docker system prune -f
```

## Advanced Scenarios

### Multi-tenant Setup
See `examples/production/multi-tenant/` for multi-tenant configurations.

### Grafana Integration
Add Grafana to the stack:

```yaml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana-data:/var/lib/grafana
```

### TLS/SSL Setup
See `examples/production/tls/` for HTTPS configurations.