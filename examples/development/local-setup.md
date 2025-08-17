# Local Development Setup

This guide helps you set up a local development environment for the Loki MCP Server.

## Prerequisites

- Python 3.8 or higher
- Git
- A Loki instance (local or remote)

## Step-by-Step Setup

### 1. Install Loki Locally (Optional)

If you don't have a Loki instance, you can run one locally:

#### Using Docker
```bash
docker run -d \
  --name loki \
  -p 3100:3100 \
  grafana/loki:latest \
  -config.file=/etc/loki/local-config.yaml
```

#### Using Docker Compose
```bash
# Use the provided docker-compose setup
cd examples/docker
docker-compose up -d loki
```

#### Using Binary
```bash
# Download Loki binary
curl -LO https://github.com/grafana/loki/releases/download/v2.9.0/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
chmod +x loki-linux-amd64

# Run with default config
./loki-linux-amd64 -config.file=loki-local-config.yaml
```

### 2. Clone and Install the MCP Server

```bash
# Clone the repository
git clone <repository-url>
cd loki-mcp-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
LOKI_URL=http://localhost:3100
# LOKI_USERNAME=admin
# LOKI_PASSWORD=password
# LOKI_BEARER_TOKEN=your-token
```

### 4. Generate Sample Logs (Optional)

To have some data to work with:

#### Using Promtail
```bash
# Install Promtail
curl -LO https://github.com/grafana/loki/releases/download/v2.9.0/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip
chmod +x promtail-linux-amd64

# Create a simple config
cat > promtail-local.yaml << EOF
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*.log
EOF

# Run Promtail
./promtail-linux-amd64 -config.file=promtail-local.yaml
```

#### Using Log Generator
```bash
# Install flog (fake log generator)
go install github.com/mingrammer/flog@latest

# Generate JSON logs
flog -f json -o /tmp/app.log -t log &

# Configure Promtail to read these logs
```

### 5. Test the Setup

```bash
# Test Loki is accessible
curl http://localhost:3100/ready

# Test label endpoint
curl http://localhost:3100/loki/api/v1/label

# Run the MCP server
loki-mcp-server
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/performance/    # Performance tests

# Run with coverage
pytest --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
black .
isort .

# Type checking
mypy app/

# Linting
ruff check .

# Fix linting issues
ruff check . --fix
```

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

3. **Run tests**:
   ```bash
   pytest
   ```

4. **Format and lint**:
   ```bash
   black .
   ruff check . --fix
   ```

5. **Commit and push**:
   ```bash
   git add .
   git commit -m "Add your feature"
   git push origin feature/your-feature-name
   ```

### Debugging

#### Enable Debug Logging
```bash
export PYTHONPATH=.
export DEBUG=true
export LOG_LEVEL=DEBUG
loki-mcp-server

# Alternative: set environment variables inline
DEBUG=true LOG_LEVEL=DEBUG loki-mcp-server
```

#### VS Code Configuration
Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug MCP Server",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/app/main.py",
      "env": {
        "LOKI_URL": "http://localhost:3100",
        "PYTHONPATH": "${workspaceFolder}",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG"
      },
      "console": "integratedTerminal"
    }
  ]
}
```

#### Testing with MCP Inspector

Install and use the MCP Inspector for interactive testing:

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run with your server
mcp-inspector loki-mcp-server
```

## Common Development Tasks

### Adding a New Tool

1. Create the tool file in `app/tools/`
2. Define the parameter and result models
3. Implement the tool function
4. Create the MCP tool definition
5. Register in `server.py`
6. Add tests

### Modifying the Client

1. Update `loki_client.py` or `enhanced_client.py`
2. Add corresponding tests in `tests/unit/`
3. Update integration tests if needed

### Adding Configuration Options

1. Update `config.py` with new settings
2. Add environment variable handling
3. Update documentation
4. Add tests for the new configuration

## Environment Variables

Common environment variables for development:

```bash
# Core settings
export LOKI_URL="http://localhost:3100"
export LOKI_USERNAME="admin"
export LOKI_PASSWORD="password"

# Development settings
export PYTHONPATH="."
export DEBUG="true"
export LOG_LEVEL="DEBUG"

# Testing settings
export PYTEST_CURRENT_TEST="true"
export TEST_LOKI_URL="http://localhost:3100"
```

## IDE Setup

### VS Code Extensions
Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort
- Ruff

### PyCharm Setup
1. Open the project
2. Configure the Python interpreter to use your venv
3. Enable pytest as the test runner
4. Configure code formatting to use Black

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=.

# Reinstall in development mode
pip install -e .
```

#### Loki Connection Issues
```bash
# Check if Loki is running
curl http://localhost:3100/ready

# Check firewall/network
telnet localhost 3100

# Verify environment variables
echo $LOKI_URL
```

#### Test Failures
```bash
# Run tests with verbose output
pytest -v

# Run specific failing test
pytest tests/unit/test_specific.py::test_function -v

# Check test dependencies
pip list | grep pytest
```

### Getting Help

1. Check the main README troubleshooting section
2. Review the test outputs for clues
3. Enable debug logging
4. Check Loki server logs
5. Verify your environment configuration