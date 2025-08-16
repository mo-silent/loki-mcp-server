# Basic Authentication Configuration

This guide covers setting up the Loki MCP Server with basic authentication.

## Overview

Basic authentication uses a username and password to authenticate with Loki. This is the simplest form of authentication and is suitable for development and internal deployments.

## Configuration

### Environment Variables

Set the following environment variables:

```bash
export LOKI_URL="https://loki.example.com"
export LOKI_USERNAME="your-username"
export LOKI_PASSWORD="your-password"
```

### Configuration File (.env)

Create a `.env` file in your project directory:

```env
LOKI_URL=https://loki.example.com
LOKI_USERNAME=your-username
LOKI_PASSWORD=your-password
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "loki": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki.example.com",
        "LOKI_USERNAME": "your-username",
        "LOKI_PASSWORD": "your-password"
      }
    }
  }
}
```

## Loki Server Configuration

### Enable Basic Auth in Loki

Add to your `loki.yaml` configuration:

```yaml
auth_enabled: true

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  
# Add basic auth middleware
auth:
  type: basic
  basic_auth_users:
    your-username: $2a$10$your-hashed-password
```

### Using htpasswd for Password Hashing

Generate hashed passwords using `htpasswd`:

```bash
# Install apache2-utils (Ubuntu/Debian) or httpd-tools (CentOS/RHEL)
sudo apt-get install apache2-utils

# Generate password hash
htpasswd -nBC 10 your-username
```

Add the output to your Loki configuration.

### Nginx Reverse Proxy with Basic Auth

If running Loki behind Nginx:

```nginx
server {
    listen 80;
    server_name loki.example.com;
    
    auth_basic "Loki Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    location / {
        proxy_pass http://localhost:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Create the password file:
```bash
htpasswd -c /etc/nginx/.htpasswd your-username
```

## Testing Basic Auth

### Test with curl

```bash
# Test without auth (should fail)
curl http://loki.example.com/ready

# Test with basic auth
curl -u your-username:your-password http://loki.example.com/ready

# Test with MCP server
LOKI_URL=http://loki.example.com \
LOKI_USERNAME=your-username \
LOKI_PASSWORD=your-password \
loki-mcp-server
```

### Test with Python

```python
import os
from app.config import load_config
from app.enhanced_client import EnhancedLokiClient

# Set environment variables
os.environ['LOKI_URL'] = 'http://loki.example.com'
os.environ['LOKI_USERNAME'] = 'your-username'
os.environ['LOKI_PASSWORD'] = 'your-password'

# Test connection
config = load_config()
async with EnhancedLokiClient(config) as client:
    labels = await client.label_names()
    print(f"Available labels: {labels}")
```

## Security Considerations

### Password Security
- Use strong, unique passwords
- Rotate passwords regularly
- Don't store passwords in version control
- Use environment variables or secure secret management

### Network Security
- Always use HTTPS in production
- Consider VPN or network isolation
- Implement rate limiting
- Monitor authentication attempts

### Best Practices

1. **Use Environment Variables**: Never hardcode credentials
2. **Principle of Least Privilege**: Give minimal necessary permissions
3. **Regular Rotation**: Change passwords periodically
4. **Audit Logs**: Monitor authentication attempts
5. **Secure Storage**: Use secret management systems

## Example Configurations

### Development Environment

```bash
# .env file for development
LOKI_URL=http://localhost:3100
LOKI_USERNAME=dev-user
LOKI_PASSWORD=dev-password-123
```

### Production Environment

```bash
# Use a secret management system
LOKI_URL=https://loki-prod.company.com
LOKI_USERNAME=$(vault kv get -field=username secret/loki/prod)
LOKI_PASSWORD=$(vault kv get -field=password secret/loki/prod)
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
env:
  LOKI_URL: ${{ secrets.LOKI_URL }}
  LOKI_USERNAME: ${{ secrets.LOKI_USERNAME }}
  LOKI_PASSWORD: ${{ secrets.LOKI_PASSWORD }}
```

## Troubleshooting

### Common Issues

#### 401 Unauthorized
- Verify username and password are correct
- Check if Loki has basic auth enabled
- Ensure credentials are properly encoded

#### Connection Refused
- Verify Loki URL is correct
- Check if Loki is running
- Verify network connectivity

#### Authentication Loops
- Check if reverse proxy auth conflicts with Loki auth
- Verify auth configuration consistency

### Debug Commands

```bash
# Test Loki endpoint directly
curl -v -u username:password http://loki.example.com/ready

# Check environment variables
env | grep LOKI

# Test with debug logging
DEBUG=true loki-mcp-server
```

### Logs to Check

- Loki server logs for authentication errors
- Nginx/reverse proxy logs
- MCP server logs with debug enabled
- Network connectivity logs

## Migration from No Auth

### Steps to Enable Basic Auth

1. **Configure Loki** with basic auth
2. **Create user credentials**
3. **Update MCP server configuration**
4. **Test the connection**
5. **Update all client configurations**

### Backward Compatibility

To support both auth and no-auth during migration:

```python
# Conditional authentication in config
if os.getenv('LOKI_USERNAME'):
    # Use basic auth
    auth = (username, password)
else:
    # No authentication
    auth = None
```

## Related Documentation

- [Bearer Token Authentication](bearer-token.md)
- [OAuth2 Authentication](oauth2.md)
- [TLS Configuration](../production/tls.md)
- [Security Best Practices](../production/security.md)