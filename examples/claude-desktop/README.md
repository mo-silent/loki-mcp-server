# Claude Desktop Configuration

This folder contains example configurations for integrating the Loki MCP Server with Claude Desktop.

## Basic Configuration

Add the following to your Claude Desktop configuration file:

**Location**: 
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

## Configuration with Authentication

### Basic Authentication
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

### Bearer Token Authentication
```json
{
  "mcpServers": {
    "loki": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki.example.com",
        "LOKI_BEARER_TOKEN": "your-api-token"
      }
    }
  }
}
```

## Multiple Loki Instances

You can configure multiple Loki instances:

```json
{
  "mcpServers": {
    "loki-prod": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki-prod.example.com",
        "LOKI_BEARER_TOKEN": "prod-token"
      }
    },
    "loki-staging": {
      "command": "loki-mcp-server",
      "env": {
        "LOKI_URL": "https://loki-staging.example.com",
        "LOKI_BEARER_TOKEN": "staging-token"
      }
    }
  }
}
```

## Setup Steps

1. **Install the Loki MCP Server**:
   ```bash
   pip install -e /path/to/loki-mcp-server
   ```

2. **Locate your Claude Desktop config file** (create if it doesn't exist)

3. **Add the Loki MCP server configuration**

4. **Restart Claude Desktop**

5. **Verify the connection** by asking Claude to query your logs

## Example Conversations

Once configured, you can interact with your Loki logs through Claude:

**"Show me error logs from the last hour"**
- Claude will use the search_logs tool to find error entries

**"Query all logs from the web-server job"**
- Claude will use query_logs with a LogQL query like `{job="web-server"}`

**"What labels are available in my logs?"**
- Claude will use get_labels to show available log labels

## Troubleshooting

### Server Not Found
- Ensure `loki-mcp-server` is in your PATH
- Try using the full path to the executable

### Connection Issues
- Verify your `LOKI_URL` is correct and accessible
- Check firewall settings
- Ensure Loki is running

### Authentication Problems
- Verify credentials are correct
- Check if your Loki instance requires authentication
- Ensure tokens haven't expired

### Permission Issues
- Make sure the MCP server has network access
- Check if Loki has any IP restrictions

## Advanced Configuration

### Custom Installation Path
If you installed the server in a custom location:

```json
{
  "mcpServers": {
    "loki": {
      "command": "/path/to/your/venv/bin/loki-mcp-server",
      "env": {
        "LOKI_URL": "http://localhost:3100"
      }
    }
  }
}
```

### Environment File
You can use an environment file instead of inline env vars:

```json
{
  "mcpServers": {
    "loki": {
      "command": "loki-mcp-server",
      "env": {
        "ENV_FILE": "/path/to/your/.env"
      }
    }
  }
}
```

Where `.env` contains:
```env
LOKI_URL=http://localhost:3100
LOKI_USERNAME=admin
LOKI_PASSWORD=password
```