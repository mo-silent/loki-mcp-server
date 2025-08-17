# Bearer Token Authentication

This guide covers setting up the Loki MCP Server with bearer token authentication, which is the recommended approach for production deployments.

## Overview

Bearer token authentication uses an API token to authenticate with Loki. This method is more secure than basic authentication and is the standard for modern API authentication.

## Configuration

### Environment Variables

Set the bearer token:

```bash
export LOKI_URL="https://loki.example.com"
export LOKI_BEARER_TOKEN="your-api-token-here"
```

### Configuration File (.env)

Create a `.env` file:

```env
LOKI_URL=https://loki.example.com
LOKI_BEARER_TOKEN=your-api-token-here
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "loki": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki.example.com",
        "LOKI_BEARER_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

## Token Generation

### Grafana Cloud

If using Grafana Cloud Loki:

1. Go to your Grafana Cloud stack
2. Navigate to "Access Policies" 
3. Create a new access policy with Loki permissions
4. Generate a token for the policy
5. Use this token as your bearer token

### Self-Hosted with Grafana

For self-hosted Grafana with Loki:

1. Go to Grafana UI → Configuration → API Keys
2. Create a new API key with appropriate permissions
3. Use this key as your bearer token

### Custom Token Generation

For custom implementations, ensure tokens:
- Are cryptographically secure (minimum 32 characters)
- Have appropriate scopes/permissions
- Include expiration dates
- Are properly validated by your auth service

## Loki Server Configuration

### Enable Bearer Token Auth

Configure Loki to accept bearer tokens in `loki.yaml`:

```yaml
auth_enabled: true

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

auth:
  type: enterprise # or your auth provider
  
# For Grafana Enterprise Logs
enterprise:
  auth:
    enabled: true
    type: default
```

### Reverse Proxy Configuration

#### Nginx with Bearer Token Validation

```nginx
server {
    listen 443 ssl;
    server_name loki.example.com;
    
    # Validate bearer token
    location / {
        # Extract and validate token
        if ($http_authorization !~* "^Bearer (.+)$") {
            return 401 "Missing or invalid authorization header";
        }
        
        # Forward to token validation service
        auth_request /auth;
        
        proxy_pass http://localhost:3100;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
    }
    
    # Internal auth endpoint
    location = /auth {
        internal;
        proxy_pass http://auth-service/validate;
        proxy_set_header Authorization $http_authorization;
    }
}
```

#### Apache with Bearer Token

```apache
<VirtualHost *:443>
    ServerName loki.example.com
    
    # Enable mod_auth_bearer (custom module)
    LoadModule auth_bearer_module modules/mod_auth_bearer.so
    
    <Location />
        AuthType Bearer
        AuthBearerProvider file
        AuthBearerTokenFile /etc/apache2/tokens
        Require valid-token
        
        ProxyPass http://localhost:3100/
        ProxyPassReverse http://localhost:3100/
    </Location>
</VirtualHost>
```

## Advanced Token Management

### Token Rotation

Implement automatic token rotation:

```python
import os
import time
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self):
        self.token = None
        self.expires_at = None
    
    def get_token(self):
        if self.token is None or self.is_expired():
            self.refresh_token()
        return self.token
    
    def is_expired(self):
        if self.expires_at is None:
            return True
        return datetime.now() >= self.expires_at
    
    def refresh_token(self):
        # Implement your token refresh logic
        self.token = self._fetch_new_token()
        self.expires_at = datetime.now() + timedelta(hours=1)
    
    def _fetch_new_token(self):
        # Call your auth service to get a new token
        pass
```

### Multiple Environments

Different tokens for different environments:

```bash
# Development
export LOKI_BEARER_TOKEN="dev-token-12345"

# Staging  
export LOKI_BEARER_TOKEN="staging-token-67890"

# Production
export LOKI_BEARER_TOKEN="prod-token-abcdef"
```

### Service Account Tokens

For automated systems, use service account tokens:

```json
{
  "mcpServers": {
    "loki-monitoring": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki.company.com",
        "LOKI_BEARER_TOKEN": "${SERVICE_ACCOUNT_TOKEN}"
      }
    }
  }
}
```

## Testing Bearer Token Auth

### Test with curl

```bash
# Test without token (should fail)
curl https://loki.example.com/ready

# Test with bearer token
curl -H "Authorization: Bearer your-token-here" \
     https://loki.example.com/ready

# Test label endpoint
curl -H "Authorization: Bearer your-token-here" \
     https://loki.example.com/loki/api/v1/label
```

### Test with MCP Server

```bash
export LOKI_URL="https://loki.example.com"
export LOKI_BEARER_TOKEN="your-token-here"
loki-mcp-server
```

### Automated Testing

```python
import pytest
import os
import asyncio
from app.config import LokiConfig
from app.enhanced_client import EnhancedLokiClient
from app.loki_client import LokiClientError

@pytest.mark.asyncio
async def test_bearer_token_auth():
    config = LokiConfig(
        url="https://loki.example.com",
        bearer_token="test-token"
    )
    
    async with EnhancedLokiClient(config) as client:
        # This should succeed with valid token
        labels = await client.label_names()
        assert isinstance(labels, list)

@pytest.mark.asyncio 
async def test_invalid_token():
    config = LokiConfig(
        url="https://loki.example.com",
        bearer_token="invalid-token"
    )
    
    with pytest.raises(LokiClientError):
        async with EnhancedLokiClient(config) as client:
            await client.label_names()

# Manual test function
async def test_bearer_connection():
    """Test bearer token connection manually"""
    config = LokiConfig(
        url="https://loki.example.com",
        bearer_token="your-token-here"
    )
    
    try:
        async with EnhancedLokiClient(config) as client:
            labels = await client.label_names()
            print(f"✅ Authentication successful! Found {len(labels)} labels.")
            
            # Test query capability  
            response = await client.query_range(
                query="{}",
                start="1h", 
                end="now",
                limit=5
            )
            print(f"✅ Query successful!")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_bearer_connection())
```

## Security Best Practices

### Token Security

1. **Never log tokens**: Ensure tokens don't appear in logs
2. **Use secure storage**: Store tokens in secure vaults
3. **Implement rotation**: Regularly rotate tokens
4. **Scope appropriately**: Give minimal necessary permissions
5. **Monitor usage**: Track token usage patterns

### Implementation Guidelines

```python
# Good: Using environment variable
token = os.getenv('LOKI_BEARER_TOKEN')

# Good: Using secret management
import boto3
secretsmanager = boto3.client('secretsmanager')
response = secretsmanager.get_secret_value(SecretId='loki-token')
token = response['SecretString']

# Bad: Hardcoded in code
token = "abc123xyz789"  # Never do this!

# Bad: Storing in version control
token = config.get('hardcoded_token')
```

### Network Security

- Always use HTTPS
- Implement rate limiting
- Use network isolation
- Monitor for token abuse
- Implement token validation logging

## Production Deployment

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: loki-credentials
type: Opaque
data:
  bearer-token: <base64-encoded-token>
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: loki-mcp-server
spec:
  template:
    spec:
      containers:
      - name: mcp-server
        image: loki-mcp-server:latest
        env:
        - name: LOKI_BEARER_TOKEN
          valueFrom:
            secretKeyRef:
              name: loki-credentials
              key: bearer-token
```

### Docker Secrets

```bash
# Create secret
echo "your-token-here" | docker secret create loki_token -

# Use in service
docker service create \
  --secret source=loki_token,target=/run/secrets/loki_token \
  --env LOKI_BEARER_TOKEN_FILE=/run/secrets/loki_token \
  loki-mcp-server:latest
```

### HashiCorp Vault Integration

```python
import hvac

class VaultTokenProvider:
    def __init__(self, vault_url, vault_token):
        self.client = hvac.Client(url=vault_url, token=vault_token)
    
    def get_loki_token(self):
        response = self.client.secrets.kv.v2.read_secret_version(
            path='loki/prod'
        )
        return response['data']['data']['bearer_token']
```

## Troubleshooting

### Common Issues

#### 401 Unauthorized
- Verify token is correct and not expired
- Check token has proper permissions
- Ensure Authorization header format is correct

#### Token Not Found
- Check environment variable name spelling
- Verify token is set in the environment
- Ensure no extra whitespace in token

#### Permission Denied
- Verify token has required scopes
- Check Loki RBAC configuration
- Ensure token hasn't been revoked

### Debug Commands

```bash
# Check environment
echo $LOKI_BEARER_TOKEN | head -c 20  # Show first 20 chars only

# Test token with curl
curl -v -H "Authorization: Bearer $LOKI_BEARER_TOKEN" \
     https://loki.example.com/ready

# Enable debug logging
DEBUG=true LOKI_BEARER_TOKEN=$TOKEN loki-mcp-server
```

### Monitoring and Alerts

Set up monitoring for:
- Token expiration warnings
- Authentication failure rates
- Unusual token usage patterns
- Token refresh failures

## Migration Guide

### From Basic Auth to Bearer Tokens

1. Generate bearer tokens for all users
2. Update client configurations
3. Test new configuration
4. Disable basic auth
5. Monitor for issues

### Token Format Migration

If changing token formats:

```python
def migrate_token_format(old_token):
    """Convert old token format to new format"""
    if old_token.startswith('legacy_'):
        # Convert legacy token
        return f"new_{old_token[7:]}"
    return old_token
```

## Related Documentation

- [Basic Authentication](basic-auth.md)
- [Claude Desktop Configuration](../claude-desktop/README.md)
- [Docker Setup](../docker/README.md)
- [Development Setup](../development/local-setup.md)