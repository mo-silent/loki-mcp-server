# Contributing to Loki MCP Server

Thank you for your interest in contributing to the Loki MCP Server! This document provides guidelines and information for contributors.

## Project Overview

The Loki MCP Server is a Model Context Protocol (MCP) server that provides AI assistants with the ability to query and analyze logs from Grafana Loki. The project is built using Python and implements the MCP specification to expose Loki's capabilities through standardized tools.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Access to a Grafana Loki instance (for testing)

### Setting Up the Development Environment

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd loki-mcp-server
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up environment variables:**
   ```bash
   export LOKI_URL="http://localhost:3100"
   # Add other environment variables as needed
   ```

### Project Structure

```
loki-mcp-server/
├── app/                    # Main application package
│   ├── __init__.py
│   ├── main.py            # CLI entry point
│   ├── server.py          # MCP server implementation
│   ├── config.py          # Configuration management
│   ├── loki_client.py     # Basic Loki client
│   ├── enhanced_client.py # Enhanced client with features
│   ├── query_builder.py   # LogQL query building
│   ├── error_handler.py   # Error classification and handling
│   ├── logging_config.py  # Logging setup
│   ├── time_utils.py      # Time conversion utilities
│   └── tools/             # MCP tools
│       ├── __init__.py
│       ├── query_logs.py  # LogQL query tool
│       ├── search_logs.py # Keyword search tool
│       └── get_labels.py  # Label discovery tool
├── tests/                 # Comprehensive test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── performance/      # Performance tests
│   ├── fixtures/         # Test fixtures and sample data
│   └── utils/            # Test utilities
├── docs/                 # Documentation
├── examples/             # Configuration examples
├── scripts/              # Utility scripts
└── pyproject.toml        # Project configuration
```

## Development Workflow

### Code Style and Quality

This project follows strict code quality standards:

#### Formatting
```bash
# Format code with Black
black .

# Sort imports with isort
isort .
```

#### Type Checking
```bash
# Run type checking with mypy
mypy app/
```

#### Linting
```bash
# Check code quality with ruff
ruff check .
```

#### Running All Quality Checks
```bash
# Use the test runner script to run all checks
python scripts/run_tests.py --quality-only
```

### Testing

#### Test Categories

- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test MCP protocol and Loki integration
- **Performance Tests** (`tests/performance/`): Benchmark query performance and resource usage

#### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/performance/   # Performance tests only

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Use the comprehensive test runner
python scripts/run_tests.py --test-type all --coverage
```

#### Writing Tests

- Follow the existing test structure and naming conventions
- Use the fixtures in `tests/fixtures/sample_logs.py` for consistent test data
- Mock external dependencies appropriately
- Include both positive and negative test cases
- Add performance tests for new features that may impact performance

### Making Changes

#### Before You Start

1. Check existing issues and pull requests to avoid duplication
2. For significant changes, consider opening an issue first to discuss the approach
3. Ensure you have the latest changes from the main branch

#### Development Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Follow the existing code patterns and architecture
   - Add appropriate tests for new functionality
   - Update documentation if needed
   - Ensure all quality checks pass

3. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```
   
   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for test-related changes
   - `refactor:` for code refactoring
   - `perf:` for performance improvements

4. **Run the complete test suite:**
   ```bash
   python scripts/run_tests.py --test-type all --coverage
   ```

5. **Push your branch and create a pull request**

## Contributing Guidelines

### Code Contributions

#### New Features
- Ensure the feature aligns with the project's goals and MCP specifications
- Add comprehensive tests covering the feature
- Update relevant documentation
- Consider backward compatibility

#### Bug Fixes
- Include a test case that reproduces the bug
- Ensure the fix doesn't break existing functionality
- Add regression tests where appropriate

#### Performance Improvements
- Include benchmarks demonstrating the improvement
- Ensure changes don't negatively impact other functionality
- Add performance tests to prevent regressions

### Documentation

- Keep documentation up-to-date with code changes
- Use clear, concise language
- Include examples where helpful
- Follow the existing documentation structure

### Security

- Never commit secrets, passwords, or API keys
- Follow secure coding practices
- Report security vulnerabilities privately
- Use environment variables for sensitive configuration

## Architecture Guidelines

### Design Principles

The project follows these architectural principles from the design specifications:

1. **Layered Architecture**: Clear separation between MCP protocol, business logic, Loki integration, and configuration layers
2. **Error Handling**: Comprehensive error classification and user-friendly error messages
3. **Performance**: Efficient query handling with caching and rate limiting
4. **Testability**: Modular design that supports comprehensive testing

### Key Components

- **MCP Server Core** (`server.py`): Main server implementation using the MCP library
- **Loki Clients** (`loki_client.py`, `enhanced_client.py`): HTTP clients for Loki API communication
- **Query Builder** (`query_builder.py`): LogQL query construction utilities
- **Tools** (`tools/`): Individual MCP tools for specific operations
- **Error Handler** (`error_handler.py`): Centralized error handling and classification

### Adding New Tools

When adding new MCP tools:

1. Create a new file in the `tools/` directory
2. Follow the existing tool patterns and interfaces
3. Register the tool in `server.py`
4. Add comprehensive tests in `tests/unit/`
5. Update documentation

## Getting Help

- Check the [troubleshooting guide](docs/troubleshooting.md)
- Review existing issues and discussions
- Look at the [examples](examples/) for configuration guidance
- Run the test suite to verify your setup

## Review Process

All contributions go through a review process:

1. **Automated Checks**: All tests and quality checks must pass
2. **Code Review**: Maintainers will review the code for quality, architecture, and alignment with project goals
3. **Testing**: Changes are tested in various environments
4. **Documentation Review**: Ensure documentation is complete and accurate

## Release Process

The project follows semantic versioning (SemVer):

- **Major versions** (1.0.0): Breaking changes
- **Minor versions** (0.1.0): New features, backward compatible
- **Patch versions** (0.0.1): Bug fixes, backward compatible

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:

1. Check this guide and the project documentation
2. Search existing issues
3. Open a new issue with the "question" label

Thank you for contributing to the Loki MCP Server!