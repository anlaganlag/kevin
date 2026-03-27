"""Rate limiting middleware implementation."""

from typing import Dict, Any
import time

from utils.sliding_window import SlidingWindow


class RateLimiter:
    """Rate limiting middleware for API requests."""

    def __init__(self, max_requests: int = 100, window_size: int = 60):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_size: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_size = window_size
        self.window = SlidingWindow(window_size, max_requests)

    def extract_ip(self, request) -> str:
        """Extract IP address from request."""
        return request.client.host

    def is_request_allowed(self, request) -> Dict[str, Any]:
        """Check if request is allowed and return status with headers."""
        ip = self.extract_ip(request)

        allowed = self.window.is_request_allowed(ip)

        if allowed:
            current_count = self.window.add_request(ip)
        else:
            # Get current count without adding request
            current_count = self.window.get_current_count(ip)

        remaining = max(0, self.max_requests - current_count)

        headers = {
            'X-RateLimit-Limit': str(self.max_requests),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Window': str(self.window_size)
        }

        return {
            'allowed': allowed,
            'current_count': current_count,
            'headers': headers
        }