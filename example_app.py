#!/usr/bin/env python3
"""Example FastAPI application with rate limiting middleware."""

from fastapi import FastAPI
import uvicorn

from middleware.fastapi_rate_limiter import RateLimitMiddleware
from config.rate_limit_config import RateLimitConfig

# Load configuration
config = RateLimitConfig()

# Create FastAPI app
app = FastAPI(title="Rate Limited API", version="1.0.0")

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    max_requests=config.default_rate_limit,
    window_size=config.default_window_size,
    whitelist_ips=config.whitelist_ips,
    endpoint_limits=config.endpoint_limits
)

# API endpoints
@app.get("/")
def read_root():
    """Root endpoint."""
    return {"message": "Welcome to the Rate Limited API"}

@app.get("/api/users")
def get_users():
    """Get users - uses default rate limit."""
    return {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}

@app.post("/api/auth/login")
def login():
    """Login endpoint - may have stricter rate limit."""
    return {"token": "fake_jwt_token", "expires_in": 3600}

@app.get("/api/data/export")
def export_data():
    """Export data - may have stricter rate limit."""
    return {"status": "export_started", "job_id": "12345"}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "rate_limit": "active"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)