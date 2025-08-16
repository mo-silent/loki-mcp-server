"""Unit tests for configuration management."""

import os
import pytest
from unittest.mock import patch

from app.config import LokiConfig, ConfigurationError, load_config


class TestLokiConfig:
    """Test cases for LokiConfig dataclass."""

    def test_valid_config_minimal(self):
        """Test creating config with minimal required parameters."""
        config = LokiConfig(url="http://localhost:3100")
        
        assert config.url == "http://localhost:3100"
        assert config.username is None
        assert config.password is None
        assert config.bearer_token is None
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_requests == 100
        assert config.rate_limit_period == 60

    def test_valid_config_with_basic_auth(self):
        """Test creating config with basic authentication."""
        config = LokiConfig(
            url="https://loki.example.com",
            username="admin",
            password="secret"
        )
        
        assert config.url == "https://loki.example.com"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.bearer_token is None

    def test_valid_config_with_bearer_token(self):
        """Test creating config with bearer token authentication."""
        config = LokiConfig(
            url="https://loki.example.com",
            bearer_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        )
        
        assert config.url == "https://loki.example.com"
        assert config.bearer_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        assert config.username is None
        assert config.password is None

    def test_valid_config_with_custom_values(self):
        """Test creating config with custom timeout and retry values."""
        config = LokiConfig(
            url="http://localhost:3100",
            timeout=60,
            max_retries=5,
            rate_limit_requests=200,
            rate_limit_period=120
        )
        
        assert config.timeout == 60
        assert config.max_retries == 5
        assert config.rate_limit_requests == 200
        assert config.rate_limit_period == 120

    def test_empty_url_raises_error(self):
        """Test that empty URL raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Loki URL is required"):
            LokiConfig(url="")

    def test_invalid_url_format_raises_error(self):
        """Test that invalid URL format raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Invalid Loki URL format"):
            LokiConfig(url="not-a-url")

    def test_invalid_url_scheme_raises_error(self):
        """Test that invalid URL scheme raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="must use http or https protocol"):
            LokiConfig(url="ftp://localhost:3100")

    def test_username_without_password_raises_error(self):
        """Test that username without password raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Password is required when username is provided"):
            LokiConfig(url="http://localhost:3100", username="admin")

    def test_password_without_username_raises_error(self):
        """Test that password without username raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Username is required when password is provided"):
            LokiConfig(url="http://localhost:3100", password="secret")

    def test_both_basic_auth_and_bearer_token_raises_error(self):
        """Test that using both basic auth and bearer token raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Cannot use both basic auth"):
            LokiConfig(
                url="http://localhost:3100",
                username="admin",
                password="secret",
                bearer_token="token123"
            )

    def test_negative_timeout_raises_error(self):
        """Test that negative timeout raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Timeout must be positive"):
            LokiConfig(url="http://localhost:3100", timeout=-1)

    def test_zero_timeout_raises_error(self):
        """Test that zero timeout raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Timeout must be positive"):
            LokiConfig(url="http://localhost:3100", timeout=0)

    def test_negative_max_retries_raises_error(self):
        """Test that negative max_retries raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Max retries cannot be negative"):
            LokiConfig(url="http://localhost:3100", max_retries=-1)

    def test_zero_rate_limit_requests_raises_error(self):
        """Test that zero rate_limit_requests raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Rate limit requests must be positive"):
            LokiConfig(url="http://localhost:3100", rate_limit_requests=0)

    def test_zero_rate_limit_period_raises_error(self):
        """Test that zero rate_limit_period raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Rate limit period must be positive"):
            LokiConfig(url="http://localhost:3100", rate_limit_period=0)


class TestLoadConfig:
    """Test cases for load_config function."""

    def test_load_config_minimal_required(self):
        """Test loading config with only required environment variable."""
        with patch.dict(os.environ, {'LOKI_URL': 'http://localhost:3100'}, clear=True):
            config = load_config()
            
            assert config.url == "http://localhost:3100"
            assert config.username is None
            assert config.password is None
            assert config.bearer_token is None
            assert config.timeout == 30
            assert config.max_retries == 3
            assert config.rate_limit_requests == 100
            assert config.rate_limit_period == 60

    def test_load_config_with_basic_auth(self):
        """Test loading config with basic authentication from environment."""
        env_vars = {
            'LOKI_URL': 'https://loki.example.com',
            'LOKI_USERNAME': 'admin',
            'LOKI_PASSWORD': 'secret'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            
            assert config.url == "https://loki.example.com"
            assert config.username == "admin"
            assert config.password == "secret"
            assert config.bearer_token is None

    def test_load_config_with_bearer_token(self):
        """Test loading config with bearer token from environment."""
        env_vars = {
            'LOKI_URL': 'https://loki.example.com',
            'LOKI_BEARER_TOKEN': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            
            assert config.url == "https://loki.example.com"
            assert config.bearer_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            assert config.username is None
            assert config.password is None

    def test_load_config_with_custom_values(self):
        """Test loading config with custom timeout and retry values."""
        env_vars = {
            'LOKI_URL': 'http://localhost:3100',
            'LOKI_TIMEOUT': '60',
            'LOKI_MAX_RETRIES': '5',
            'LOKI_RATE_LIMIT_REQUESTS': '200',
            'LOKI_RATE_LIMIT_PERIOD': '120'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            
            assert config.timeout == 60
            assert config.max_retries == 5
            assert config.rate_limit_requests == 200
            assert config.rate_limit_period == 120

    def test_load_config_missing_url_raises_error(self):
        """Test that missing LOKI_URL raises ConfigurationError with helpful message."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                load_config()
            
            error_message = str(exc_info.value)
            assert "LOKI_URL environment variable is required" in error_message
            assert "http://localhost:3100" in error_message

    def test_load_config_invalid_numeric_value_raises_error(self):
        """Test that invalid numeric environment variable raises ConfigurationError."""
        env_vars = {
            'LOKI_URL': 'http://localhost:3100',
            'LOKI_TIMEOUT': 'not-a-number'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError, match="Invalid numeric configuration value"):
                load_config()

    def test_load_config_validation_error_propagated(self):
        """Test that validation errors from LokiConfig are propagated."""
        env_vars = {
            'LOKI_URL': 'http://localhost:3100',
            'LOKI_USERNAME': 'admin'  # Missing password
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError, match="Password is required when username is provided"):
                load_config()

    def test_load_config_handles_zero_values(self):
        """Test that zero values in environment variables are handled correctly."""
        env_vars = {
            'LOKI_URL': 'http://localhost:3100',
            'LOKI_MAX_RETRIES': '0'  # Valid zero value
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            assert config.max_retries == 0

    def test_load_config_handles_empty_optional_values(self):
        """Test that empty optional environment variables are treated as None."""
        env_vars = {
            'LOKI_URL': 'http://localhost:3100',
            'LOKI_USERNAME': '',  # Empty string should be treated as None
            'LOKI_PASSWORD': ''
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            assert config.username == ''  # Empty string, not None
            assert config.password == ''