"""Tests for rate limiting middleware."""

import pytest
from unittest.mock import Mock, patch

from middleware.rate_limiter import RateLimiter


def test_should_extract_ip_from_request():
    """Should correctly extract IP address from request."""
    # Mock request with client IP
    mock_request = Mock()
    mock_request.client.host = "192.168.1.100"

    limiter = RateLimiter()
    ip = limiter.extract_ip(mock_request)

    assert ip == "192.168.1.100"


def test_should_allow_request_when_under_limit():
    """Should allow request when it's under the rate limit."""
    mock_request = Mock()
    mock_request.client.host = "192.168.1.100"

    with patch('middleware.rate_limiter.SlidingWindow') as mock_window_class:
        mock_window = Mock()
        mock_window.is_request_allowed.return_value = True
        mock_window.add_request.return_value = 5
        mock_window_class.return_value = mock_window

        limiter = RateLimiter(max_requests=100, window_size=60)
        result = limiter.is_request_allowed(mock_request)

        assert result['allowed'] is True
        assert result['current_count'] == 5


def test_should_reject_request_when_over_limit():
    """Should reject request when it exceeds the rate limit."""
    mock_request = Mock()
    mock_request.client.host = "192.168.1.100"

    with patch('middleware.rate_limiter.SlidingWindow') as mock_window_class:
        mock_window = Mock()
        mock_window.is_request_allowed.return_value = False
        mock_window.get_current_count.return_value = 100  # At limit
        mock_window_class.return_value = mock_window

        limiter = RateLimiter(max_requests=100, window_size=60)
        result = limiter.is_request_allowed(mock_request)

        assert result['allowed'] is False


def test_should_include_rate_limit_headers_in_response():
    """Should include appropriate rate limit headers."""
    mock_request = Mock()
    mock_request.client.host = "192.168.1.100"

    with patch('middleware.rate_limiter.SlidingWindow') as mock_window_class:
        mock_window = Mock()
        mock_window.is_request_allowed.return_value = True
        mock_window.add_request.return_value = 25
        mock_window_class.return_value = mock_window

        limiter = RateLimiter(max_requests=100, window_size=60)
        result = limiter.is_request_allowed(mock_request)

        assert result['headers']['X-RateLimit-Limit'] == '100'
        assert result['headers']['X-RateLimit-Remaining'] == '75'
        assert result['headers']['X-RateLimit-Window'] == '60'