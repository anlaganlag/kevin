"""Tests for rate limit configuration management."""

import pytest
import os
from unittest.mock import patch

from config.rate_limit_config import RateLimitConfig


def test_should_load_default_configuration():
    """Should load default values when no env vars are set."""
    config = RateLimitConfig()

    assert config.default_rate_limit == 100
    assert config.default_window_size == 60
    assert config.redis_host == "localhost"
    assert config.redis_port == 6379


def test_should_load_config_from_environment():
    """Should load configuration from environment variables."""
    env_vars = {
        'DEFAULT_RATE_LIMIT': '50',
        'DEFAULT_WINDOW_SIZE': '120',
        'REDIS_HOST': 'redis.example.com',
        'REDIS_PORT': '6380',
        'REDIS_PASSWORD': 'secret123'
    }

    with patch.dict(os.environ, env_vars):
        config = RateLimitConfig()

        assert config.default_rate_limit == 50
        assert config.default_window_size == 120
        assert config.redis_host == "redis.example.com"
        assert config.redis_port == 6380
        assert config.redis_password == "secret123"


def test_should_parse_endpoint_specific_config():
    """Should parse endpoint-specific rate limit configuration."""
    endpoint_config = '{"POST /api/auth/login": 10, "GET /api/data/export": 5}'

    with patch.dict(os.environ, {'RATE_LIMIT_CONFIG': endpoint_config}):
        config = RateLimitConfig()

        assert config.get_endpoint_limit("POST /api/auth/login") == 10
        assert config.get_endpoint_limit("GET /api/data/export") == 5


def test_should_return_default_for_unconfigured_endpoint():
    """Should return default limit for endpoints not specifically configured."""
    config = RateLimitConfig()

    assert config.get_endpoint_limit("GET /api/users") == 100  # default


def test_should_parse_whitelist_ips():
    """Should parse comma-separated whitelist IPs."""
    whitelist_ips = "127.0.0.1,192.168.1.0/24,10.0.0.0/8"

    with patch.dict(os.environ, {'WHITELIST_IPS': whitelist_ips}):
        config = RateLimitConfig()

        expected = ["127.0.0.1", "192.168.1.0/24", "10.0.0.0/8"]
        assert config.whitelist_ips == expected


def test_should_handle_invalid_json_config():
    """Should handle invalid JSON in endpoint configuration gracefully."""
    invalid_config = '{"POST /api/auth/login": 10, "invalid": }'

    with patch.dict(os.environ, {'RATE_LIMIT_CONFIG': invalid_config}):
        config = RateLimitConfig()

        # Should fallback to empty config
        assert config.endpoint_limits == {}


def test_should_handle_empty_whitelist():
    """Should handle empty whitelist configuration."""
    config = RateLimitConfig()

    assert config.whitelist_ips == []