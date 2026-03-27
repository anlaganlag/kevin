"""Sliding window rate limiting algorithm implementation."""

from typing import Dict, List, Optional
import time


class SlidingWindow:
    """Sliding window rate limiter implementation."""

    def __init__(self, window_size: int, max_requests: int):
        """Initialize sliding window.

        Args:
            window_size: Window size in seconds
            max_requests: Maximum requests allowed in window
        """
        self.window_size = window_size
        self.max_requests = max_requests
        # Store list of timestamps for each IP
        self.requests: Dict[str, List[float]] = {}

    def _get_current_time(self, timestamp: Optional[float] = None) -> float:
        """Get current time or use provided timestamp."""
        return timestamp if timestamp is not None else time.time()

    def _clean_expired_requests(self, ip: str, current_time: float) -> None:
        """Remove requests outside the current time window."""
        if ip in self.requests:
            cutoff_time = current_time - self.window_size
            self.requests[ip] = [
                req_time for req_time in self.requests[ip]
                if req_time >= cutoff_time
            ]

    def add_request(self, ip: str, timestamp: Optional[float] = None) -> int:
        """Add a request for the given IP and return current count."""
        current_time = self._get_current_time(timestamp)

        if ip not in self.requests:
            self.requests[ip] = []

        # Clean expired requests first
        self._clean_expired_requests(ip, current_time)

        # Add new request
        self.requests[ip].append(current_time)

        return len(self.requests[ip])

    def is_request_allowed(self, ip: str, timestamp: Optional[float] = None) -> bool:
        """Check if a request from the IP is allowed."""
        current_time = self._get_current_time(timestamp)

        # Clean expired requests first
        self._clean_expired_requests(ip, current_time)

        current_count = len(self.requests.get(ip, []))
        return current_count < self.max_requests

    def get_current_count(self, ip: str, timestamp: Optional[float] = None) -> int:
        """Get current request count for IP."""
        current_time = self._get_current_time(timestamp)

        # Clean expired requests first
        self._clean_expired_requests(ip, current_time)

        return len(self.requests.get(ip, []))