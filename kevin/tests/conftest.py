"""Shared pytest configuration."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: tests that require Claude CLI and/or network access"
    )
