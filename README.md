# Loki MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with the ability to query and analyze logs from Grafana Loki. This server enables seamless integration between AI assistants and Loki, allowing for intelligent log analysis, troubleshooting, and monitoring workflows.

## Architecture

```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐    HTTP/API    ┌─────────────────┐
│   AI Assistant │ ◄─────────────────► │ Loki MCP Server │ ◄─────────────►│  Grafana Loki   │
│   (Claude et al)│                    │                 │                │   Log System    │
└─────────────────┘                    └─────────────────┘                └─────────────────┘
```

## Features

- 🔍 **Query Logs**: Execute LogQL queries against Loki with support for range and instant queries
- 🔎 **Search Logs**: Keyword-based log searching with advanced filtering and pattern matching
- 🏷️ **Label Discovery**: Retrieve available log labels and label values for stream exploration
- 🤖 **MCP Protocol**: Fully compatible with Model Context Protocol for AI assistant integration
- ⚡ **Performance**: Built-in caching and optimized query execution
- 🛡️ **Security**: Support for multiple authentication methods (basic auth, bearer tokens)
- 📊 **Rich Results**: Structured output with timestamps, labels, and context information

## Installation

### From Source

1. Clone the repository:
```bash
git clone <repository-url>
cd loki-mcp-server
```

2. Install the package:
```bash
pip install -e .
```

### Development Installation

For development work, install with development dependencies:

```bash
pip install -e ".[dev]"
```

### Requirements

- Python 3.8 or higher
- Access to a Grafana Loki instance
- Network connectivity to your Loki server

## Configuration

### Environment Variables

Configure the server using these environment variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `LOKI_URL` | Yes | URL of your Loki instance | `http://localhost:3100` |
| `LOKI_USERNAME` | No | Username for basic authentication | `admin` |
| `LOKI_PASSWORD` | No | Password for basic authentication | `password123` |
| `LOKI_BEARER_TOKEN` | No | Bearer token for authentication | `your-token-here` |

### Configuration Examples

#### Local Development
```bash
export LOKI_URL="http://localhost:3100"
```

#### Production with Basic Auth
```bash
export LOKI_URL="https://loki.example.com"
export LOKI_USERNAME="service-account"
export LOKI_PASSWORD="secure-password"
```

#### Production with Bearer Token
```bash
export LOKI_URL="https://loki.example.com"
export LOKI_BEARER_TOKEN="your-api-token"
```

### Configuration File (Optional)

You can also use a `.env` file in your project directory:

```env
LOKI_URL=http://localhost:3100
LOKI_USERNAME=admin
LOKI_PASSWORD=password123
```

## Usage

### Starting the Server

Start the MCP server using the command line:

```bash
loki-mcp-server
```

The server will start and listen for MCP protocol messages via stdio.

### Integration with AI Assistants

Add the server to your AI assistant's MCP configuration. Example for Claude Desktop:

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

### Available Tools

The server provides three main tools for log analysis:

#### 1. query_logs
Execute LogQL queries directly against Loki.

**Parameters:**
- `query` (required): LogQL query string
- `start` (optional): Start time for range queries
- `end` (optional): End time for range queries  
- `limit` (optional): Maximum entries to return (default: 100)
- `direction` (optional): Query direction ('forward' or 'backward')

#### 2. search_logs
Search logs using keywords with advanced filtering.

**Parameters:**
- `keywords` (required): List of keywords to search for
- `labels` (optional): Label filters as key-value pairs
- `start` (optional): Start time for search range
- `end` (optional): End time for search range
- `limit` (optional): Maximum entries to return (default: 100)
- `case_sensitive` (optional): Case-sensitive search (default: false)
- `operator` (optional): Logical operator ('AND' or 'OR')

#### 3. get_labels
Discover available labels and their values.

**Parameters:**
- `label_name` (optional): Specific label to get values for
- `start` (optional): Start time for label query
- `end` (optional): End time for label query
- `use_cache` (optional): Use cached results (default: true)

## Development

### Setup Development Environment

1. Clone and install:
```bash
git clone <repository-url>
cd loki-mcp-server
pip install -e ".[dev]"
```

2. Run tests:
```bash
pytest
```

3. Run specific test suites:
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only  
pytest tests/integration/

# Performance tests
pytest tests/performance/
```

### Code Quality

Run linting and formatting:

```bash
# Format code
black .
isort .

# Type checking
mypy app/

# Linting
ruff check .
```

### Project Structure

```
loki-mcp-server/
├── app/          # Main package
│   ├── __init__.py
│   ├── main.py               # CLI entry point
│   ├── server.py             # MCP server implementation
│   ├── config.py             # Configuration management
│   ├── loki_client.py        # Basic Loki client
│   ├── enhanced_client.py    # Enhanced client with features
│   ├── query_builder.py      # LogQL query building
│   ├── error_handler.py      # Error classification and handling
│   ├── logging_config.py     # Logging setup
│   └── tools/                # MCP tools
│       ├── query_logs.py     # LogQL query tool
│       ├── search_logs.py    # Keyword search tool
│       └── get_labels.py     # Label discovery tool
├── tests/                    # Test suite
├── pyproject.toml           # Project configuration
└── README.md               # This file
```

### Testing

The project includes comprehensive tests:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test MCP protocol and Loki integration
- **Performance Tests**: Benchmark query performance
- **Mock Tests**: Test with simulated Loki responses

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

## Troubleshooting

### Common Issues

#### Connection Errors
- Verify `LOKI_URL` is correct and accessible
- Check firewall and network connectivity
- Ensure Loki is running and healthy

#### Authentication Errors
- Verify credentials are correct
- Check if Loki requires authentication
- Ensure bearer token is valid and not expired

#### Query Errors
- Validate LogQL syntax
- Check label names and values exist
- Verify time range is reasonable

### Debug Mode

Enable debug logging by setting:
```bash
export PYTHONPATH=.
python -m app.main --debug
```

### Getting Help

1. Check the troubleshooting guide in `docs/troubleshooting.md`
2. Review example configurations in `examples/`
3. Run the test suite to verify your setup
4. Check Loki server logs for additional context

## License

MIT License - see LICENSE file for details.