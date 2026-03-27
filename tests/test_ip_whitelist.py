"""Tests for IP whitelist functionality."""

import pytest

from utils.ip_whitelist import IPWhitelist


def test_should_allow_single_ip_in_whitelist():
    """Should return True for IP that is explicitly whitelisted."""
    whitelist = IPWhitelist(["192.168.1.100", "10.0.0.1"])

    assert whitelist.is_whitelisted("192.168.1.100") is True
    assert whitelist.is_whitelisted("10.0.0.1") is True


def test_should_deny_ip_not_in_whitelist():
    """Should return False for IP that is not whitelisted."""
    whitelist = IPWhitelist(["192.168.1.100"])

    assert whitelist.is_whitelisted("192.168.1.200") is False


def test_should_support_cidr_notation():
    """Should support CIDR notation for IP ranges."""
    whitelist = IPWhitelist(["192.168.1.0/24", "10.0.0.0/8"])

    # IPs in range should be allowed
    assert whitelist.is_whitelisted("192.168.1.50") is True
    assert whitelist.is_whitelisted("192.168.1.255") is True
    assert whitelist.is_whitelisted("10.5.10.20") is True

    # IPs outside range should be denied
    assert whitelist.is_whitelisted("192.168.2.50") is False
    assert whitelist.is_whitelisted("11.0.0.1") is False


def test_should_handle_localhost_variations():
    """Should recognize localhost variations."""
    whitelist = IPWhitelist(["127.0.0.1"])

    assert whitelist.is_whitelisted("127.0.0.1") is True


def test_should_handle_empty_whitelist():
    """Should deny all IPs when whitelist is empty."""
    whitelist = IPWhitelist([])

    assert whitelist.is_whitelisted("127.0.0.1") is False
    assert whitelist.is_whitelisted("192.168.1.1") is False


def test_should_handle_mixed_formats():
    """Should handle mix of single IPs and CIDR ranges."""
    whitelist = IPWhitelist([
        "127.0.0.1",
        "192.168.1.0/24",
        "10.0.0.100"
    ])

    # Specific IPs
    assert whitelist.is_whitelisted("127.0.0.1") is True
    assert whitelist.is_whitelisted("10.0.0.100") is True

    # CIDR range
    assert whitelist.is_whitelisted("192.168.1.50") is True

    # Not whitelisted
    assert whitelist.is_whitelisted("8.8.8.8") is False