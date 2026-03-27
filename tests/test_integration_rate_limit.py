"""Integration tests for rate limiting functionality."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from middleware.fastapi_rate_limiter import RateLimitMiddleware


@pytest.fixture
def app():
    """Create FastAPI app with rate limiting middleware."""
    app = FastAPI()

    # Add a simple test endpoint
    @app.get("/api/test")
    def test_endpoint():
        return {"message": "success"}

    @app.post("/api/auth/login")
    def login_endpoint():
        return {"token": "fake_token"}

    return app


def test_should_allow_requests_under_limit(app):
    """Should allow requests when under the rate limit."""
    app.add_middleware(RateLimitMiddleware, max_requests=5, window_size=60)
    client = TestClient(app)

    # Make multiple requests under the limit
    for i in range(3):
        response = client.get("/api/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0


def test_should_reject_requests_over_limit(app):
    """Should reject requests with 429 when over limit."""
    app.add_middleware(RateLimitMiddleware, max_requests=2, window_size=60)
    client = TestClient(app)

    # Make requests up to the limit
    for i in range(2):
        response = client.get("/api/test")
        assert response.status_code == 200

    # Next request should be rejected
    response = client.get("/api/test")
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.json()["detail"] == "Rate limit exceeded"


def test_should_include_correct_rate_limit_headers(app):
    """Should include correct rate limit headers in response."""
    app.add_middleware(RateLimitMiddleware, max_requests=10, window_size=60)
    client = TestClient(app)

    response = client.get("/api/test")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Window"] == "60"
    assert int(response.headers["X-RateLimit-Remaining"]) == 9  # After first request


@patch('middleware.fastapi_rate_limiter.IPWhitelist')
def test_should_bypass_rate_limit_for_whitelisted_ips(mock_whitelist_class, app):
    """Should bypass rate limiting for whitelisted IP addresses."""
    # Setup mock whitelist
    mock_whitelist = MagicMock()
    mock_whitelist.is_whitelisted.return_value = True
    mock_whitelist_class.return_value = mock_whitelist

    app.add_middleware(
        RateLimitMiddleware,
        max_requests=1,
        window_size=60,
        whitelist_ips=["127.0.0.1"]
    )
    client = TestClient(app)

    # Make multiple requests from whitelisted IP - all should succeed
    for i in range(5):
        response = client.get("/api/test")
        assert response.status_code == 200


def test_should_apply_endpoint_specific_limits(app):
    """Should apply different limits for different endpoints."""
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=10,
        window_size=60,
        endpoint_limits={"POST /api/auth/login": 2}
    )
    client = TestClient(app)

    # Login endpoint should have stricter limit
    response1 = client.post("/api/auth/login")
    response2 = client.post("/api/auth/login")
    assert response1.status_code == 200
    assert response2.status_code == 200

    # Third request should be rate limited
    response3 = client.post("/api/auth/login")
    assert response3.status_code == 429

    # But regular endpoint should still work
    response4 = client.get("/api/test")
    assert response4.status_code == 200