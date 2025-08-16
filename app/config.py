"""Configuration management for the Loki MCP server."""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


@dataclass
class LokiConfig:
    """Configuration for Loki MCP server."""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    bearer_token: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """Validate configuration values."""
        # Validate URL
        if not self.url:
            raise ConfigurationError("Loki URL is required")
        
        parsed_url = urlparse(self.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ConfigurationError(f"Invalid Loki URL format: {self.url}")
        
        if parsed_url.scheme not in ['http', 'https']:
            raise ConfigurationError(f"Loki URL must use http or https protocol: {self.url}")

        # Validate authentication
        if self.username and not self.password:
            raise ConfigurationError("Password is required when username is provided")
        
        if self.password and not self.username:
            raise ConfigurationError("Username is required when password is provided")

        if self.username and self.bearer_token:
            raise ConfigurationError("Cannot use both basic auth (username/password) and bearer token")

        # Validate numeric values
        if self.timeout <= 0:
            raise ConfigurationError(f"Timeout must be positive: {self.timeout}")
        
        if self.max_retries < 0:
            raise ConfigurationError(f"Max retries cannot be negative: {self.max_retries}")
        
        if self.rate_limit_requests <= 0:
            raise ConfigurationError(f"Rate limit requests must be positive: {self.rate_limit_requests}")
        
        if self.rate_limit_period <= 0:
            raise ConfigurationError(f"Rate limit period must be positive: {self.rate_limit_period}")


def load_config() -> LokiConfig:
    """Load configuration from environment variables with defaults."""
    try:
        # Required configuration
        url = os.getenv('LOKI_URL')
        if not url:
            raise ConfigurationError(
                "LOKI_URL environment variable is required. "
                "Please set it to your Loki server URL (e.g., http://localhost:3100)"
            )

        # Optional authentication
        username = os.getenv('LOKI_USERNAME')
        password = os.getenv('LOKI_PASSWORD')
        bearer_token = os.getenv('LOKI_BEARER_TOKEN')

        # Optional configuration with defaults
        timeout = int(os.getenv('LOKI_TIMEOUT', '30'))
        max_retries = int(os.getenv('LOKI_MAX_RETRIES', '3'))
        rate_limit_requests = int(os.getenv('LOKI_RATE_LIMIT_REQUESTS', '100'))
        rate_limit_period = int(os.getenv('LOKI_RATE_LIMIT_PERIOD', '60'))

        return LokiConfig(
            url=url,
            username=username,
            password=password,
            bearer_token=bearer_token,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit_requests=rate_limit_requests,
            rate_limit_period=rate_limit_period
        )
    
    except ValueError as e:
        raise ConfigurationError(f"Invalid numeric configuration value: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")