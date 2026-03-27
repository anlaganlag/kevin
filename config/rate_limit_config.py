"""Rate limit configuration management."""

import os
import json
from typing import Dict, List, Optional


class RateLimitConfig:
    """Manages rate limiting configuration from environment variables."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Default rate limiting settings
        self.default_rate_limit = int(os.getenv('DEFAULT_RATE_LIMIT', '100'))
        self.default_window_size = int(os.getenv('DEFAULT_WINDOW_SIZE', '60'))

        # Redis configuration
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password = os.getenv('REDIS_PASSWORD')
        self.redis_db = int(os.getenv('REDIS_DB', '0'))

        # Parse endpoint-specific configuration
        self.endpoint_limits = self._parse_endpoint_config()

        # Parse IP whitelist
        self.whitelist_ips = self._parse_whitelist_ips()

        # Logging configuration
        self.log_level = os.getenv('RATE_LIMIT_LOG_LEVEL', 'INFO')

    def _parse_endpoint_config(self) -> Dict[str, int]:
        """Parse endpoint-specific rate limit configuration from JSON."""
        config_str = os.getenv('RATE_LIMIT_CONFIG', '{}')
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            # Return empty dict on invalid JSON
            return {}

    def _parse_whitelist_ips(self) -> List[str]:
        """Parse comma-separated whitelist IPs."""
        whitelist_str = os.getenv('WHITELIST_IPS', '')
        if not whitelist_str.strip():
            return []

        return [ip.strip() for ip in whitelist_str.split(',') if ip.strip()]

    def get_endpoint_limit(self, endpoint: str) -> int:
        """Get rate limit for specific endpoint.

        Args:
            endpoint: Endpoint string (e.g., "POST /api/auth/login")

        Returns:
            Rate limit for the endpoint, or default if not configured
        """
        return self.endpoint_limits.get(endpoint, self.default_rate_limit)