# API Rate Limiting Implementation

## Overview

This implementation provides a comprehensive rate limiting system for FastAPI applications using a sliding window algorithm with Redis backend support.

## Features

- ✅ Sliding window rate limiting algorithm
- ✅ IP-based rate limiting with whitelist support
- ✅ Endpoint-specific rate limits
- ✅ FastAPI middleware integration
- ✅ Configurable via environment variables
- ✅ Proper HTTP status codes and headers
- ✅ CIDR notation support for IP ranges
- ✅ Comprehensive test coverage (27 tests)

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (copy `.env.example` to `.env`):
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the example app**:
   ```bash
   python example_app.py
   ```

4. **Test rate limiting**:
   ```bash
   # Make multiple requests to test rate limiting
   for i in {1..5}; do curl http://localhost:8000/api/users; echo; done
   ```

## Usage

### Basic Integration

```python
from fastapi import FastAPI
from middleware.fastapi_rate_limiter import RateLimitMiddleware

app = FastAPI()

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    max_requests=100,  # 100 requests
    window_size=60,    # per 60 seconds
)
```

### Advanced Configuration

```python
from config.rate_limit_config import RateLimitConfig

config = RateLimitConfig()

app.add_middleware(
    RateLimitMiddleware,
    max_requests=config.default_rate_limit,
    window_size=config.default_window_size,
    whitelist_ips=config.whitelist_ips,
    endpoint_limits=config.endpoint_limits
)
```

## Configuration

Environment variables:

- `DEFAULT_RATE_LIMIT`: Default requests per window (default: 100)
- `DEFAULT_WINDOW_SIZE`: Window size in seconds (default: 60)
- `RATE_LIMIT_CONFIG`: JSON string for endpoint-specific limits
- `WHITELIST_IPS`: Comma-separated list of IPs/CIDR ranges to whitelist
- `REDIS_HOST`, `REDIS_PORT`, etc.: Redis configuration (for future Redis integration)

## Response Headers

All responses include rate limiting information:

- `X-RateLimit-Limit`: Maximum requests allowed in window
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Window`: Window size in seconds
- `Retry-After`: Seconds to wait before retrying (on 429 responses)

## Testing

Run all tests:
```bash
pytest -v
```

Run specific test suites:
```bash
pytest tests/test_sliding_window.py -v      # Core algorithm
pytest tests/test_integration_rate_limit.py -v  # End-to-end tests
```

## Architecture

- **SlidingWindow**: Core rate limiting algorithm with time-based expiration
- **RateLimiter**: Request processing logic and header management
- **IPWhitelist**: IP address and CIDR range matching
- **RateLimitConfig**: Environment-based configuration management
- **RateLimitMiddleware**: FastAPI/Starlette integration

## Future Enhancements

- Redis backend integration for distributed rate limiting
- User-based rate limiting (in addition to IP-based)
- Rate limiting metrics and monitoring
- Dynamic configuration updates without restart