"""Tests for sliding window rate limiting algorithm."""

import pytest
import time
from datetime import datetime

from utils.sliding_window import SlidingWindow


def test_should_record_single_request():
    """Should record and count a single request correctly."""
    window = SlidingWindow(window_size=60, max_requests=100)

    count = window.add_request("192.168.1.1")

    assert count == 1


def test_should_count_multiple_requests_from_same_ip():
    """Should accumulate request count for same IP."""
    window = SlidingWindow(window_size=60, max_requests=100)

    window.add_request("192.168.1.1")
    window.add_request("192.168.1.1")
    count = window.add_request("192.168.1.1")

    assert count == 3


def test_should_allow_requests_within_limit():
    """Should return True when requests are within the limit."""
    window = SlidingWindow(window_size=60, max_requests=2)

    window.add_request("192.168.1.1")
    is_allowed = window.is_request_allowed("192.168.1.1")

    assert is_allowed is True


def test_should_reject_requests_exceeding_limit():
    """Should return False when requests exceed the limit."""
    window = SlidingWindow(window_size=60, max_requests=2)

    window.add_request("192.168.1.1")
    window.add_request("192.168.1.1")
    is_allowed = window.is_request_allowed("192.168.1.1")

    assert is_allowed is False


def test_should_expire_old_requests_outside_window():
    """Should not count requests that are outside the sliding window."""
    window = SlidingWindow(window_size=2, max_requests=2)

    # Add requests at current time
    window.add_request("192.168.1.1", timestamp=100)
    window.add_request("192.168.1.1", timestamp=101)

    # Check that limit is reached
    assert window.is_request_allowed("192.168.1.1", timestamp=102) is False

    # Move to a time where first request should be expired (outside 2-second window)
    assert window.is_request_allowed("192.168.1.1", timestamp=103) is True