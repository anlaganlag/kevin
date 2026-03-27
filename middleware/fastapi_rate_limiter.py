"""FastAPI rate limiting middleware."""

from typing import Callable, Dict, List, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from .rate_limiter import RateLimiter
from utils.ip_whitelist import IPWhitelist


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 100,
        window_size: int = 60,
        whitelist_ips: Optional[List[str]] = None,
        endpoint_limits: Optional[Dict[str, int]] = None
    ):
        """Initialize rate limiting middleware.

        Args:
            app: FastAPI application
            max_requests: Default maximum requests per window
            window_size: Window size in seconds
            whitelist_ips: List of whitelisted IP addresses/CIDR ranges
            endpoint_limits: Endpoint-specific rate limits
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(max_requests, window_size)
        self.whitelist = IPWhitelist(whitelist_ips or [])
        self.endpoint_limits = endpoint_limits or {}
        self.max_requests = max_requests
        self.window_size = window_size

        # Create endpoint-specific rate limiters
        self.endpoint_limiters = {}
        for endpoint, limit in self.endpoint_limits.items():
            self.endpoint_limiters[endpoint] = RateLimiter(limit, window_size)

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through rate limiting middleware."""
        # Extract IP address
        ip = self._extract_ip(request)

        # Check if IP is whitelisted
        if self.whitelist.is_whitelisted(ip):
            # Bypass rate limiting for whitelisted IPs
            response = await call_next(request)
            return self._add_headers(response, 0, self.max_requests, self.window_size)

        # Get endpoint-specific limit if configured
        endpoint = f"{request.method} {request.url.path}"

        if endpoint in self.endpoint_limiters:
            # Use endpoint-specific rate limiter
            result = self.endpoint_limiters[endpoint].is_request_allowed(request)
        else:
            # Use default rate limiter
            result = self.rate_limiter.is_request_allowed(request)

        if not result['allowed']:
            # Return 429 Too Many Requests
            retry_after = self.window_size  # Simplified: return window size
            headers = result['headers']
            headers['Retry-After'] = str(retry_after)

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=headers
            )

        # Process request normally
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in result['headers'].items():
            response.headers[key] = value

        return response

    def _extract_ip(self, request: Request) -> str:
        """Extract IP address from request, considering proxy headers."""
        # Check for forwarded IP headers first
        forwarded_ips = request.headers.get('X-Forwarded-For')
        if forwarded_ips:
            # Take the first IP (client IP)
            return forwarded_ips.split(',')[0].strip()

        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        return request.client.host

    def _add_headers(self, response, current_count: int, limit: int, window: int):
        """Add rate limit headers to response."""
        remaining = max(0, limit - current_count)
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        response.headers['X-RateLimit-Window'] = str(window)
        return response