"""IP whitelist management."""

import ipaddress
from typing import List, Union


class IPWhitelist:
    """Manages IP whitelist with support for single IPs and CIDR ranges."""

    def __init__(self, whitelist_entries: List[str]):
        """Initialize IP whitelist.

        Args:
            whitelist_entries: List of IP addresses or CIDR ranges
        """
        self.whitelist_entries = whitelist_entries
        self._networks = []
        self._ips = []

        # Parse and categorize entries
        for entry in whitelist_entries:
            try:
                # Try to parse as network (CIDR)
                if '/' in entry:
                    self._networks.append(ipaddress.ip_network(entry))
                else:
                    # Parse as single IP
                    self._ips.append(ipaddress.ip_address(entry))
            except ValueError:
                # Skip invalid entries
                pass

    def is_whitelisted(self, ip_str: str) -> bool:
        """Check if IP address is whitelisted.

        Args:
            ip_str: IP address to check

        Returns:
            True if IP is whitelisted, False otherwise
        """
        if not self.whitelist_entries:
            return False

        try:
            ip = ipaddress.ip_address(ip_str)

            # Check against single IPs
            if ip in self._ips:
                return True

            # Check against networks (CIDR ranges)
            for network in self._networks:
                if ip in network:
                    return True

            return False

        except ValueError:
            # Invalid IP format
            return False