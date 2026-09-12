"""
Security, SSRF validation, and URL normalization.
"""

import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Tuple, Optional, Set

TRACKING_PARAM_PREFIXES = ("utm_", "mc_")
TRACKING_PARAM_EXACT = {
    "fbclid",
    "gclid",
    "msclkid",
    "dclid",
    "wbraid",
    "gbraid",
    "_ga",
    "_gl",
    "ref",
    "ref_src",
    "source",
    "ncid",
    "sr_share",
}

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "instance-data",
}


class SSRFSecurityError(Exception):
    """Raised when an acquisition target violates SSRF policy."""
    pass


def normalize_url(raw_url: str) -> str:
    """
    Normalizes a URL by lowercasing scheme/host, removing default ports,
    stripping fragments, filtering tracking query parameters, and sorting query keys.
    """
    raw_url = raw_url.strip()
    if not raw_url:
        return ""

    raw_lower = raw_url.lower()
    if raw_lower.startswith("//"):
        raw_url = "https:" + raw_url
    elif not (raw_lower.startswith("http://") or raw_lower.startswith("https://")):
        # Prepend https if scheme is missing
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove standard ports
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Normalize path
    path = parsed.path
    if not path:
        path = "/"
    else:
        # Collapse multiple slashes
        path = re.sub(r"/+", "/", path)

    # Filter query parameters
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_params = []
    for k, v in query_params:
        k_lower = k.lower()
        if any(k_lower.startswith(prefix) for prefix in TRACKING_PARAM_PREFIXES):
            continue
        if k_lower in TRACKING_PARAM_EXACT:
            continue
        filtered_params.append((k, v))

    filtered_params.sort(key=lambda x: x[0])
    clean_query = urlencode(filtered_params, doseq=True)

    # Drop fragment entirely
    return urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))


def is_ip_restricted(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks if an IP address belongs to private, loopback, link-local, or reserved ranges."""
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_url_security(url: str, allowed_schemes: Optional[Set[str]] = None) -> Tuple[bool, str]:
    """
    Validates that a URL is safe to fetch and does not attempt SSRF against
    internal infrastructure or cloud metadata services.
    Returns (is_safe, error_message).
    """
    if allowed_schemes is None:
        allowed_schemes = {"http", "https"}

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL structure: {str(e)}"

    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        return False, f"Scheme '{scheme}' is forbidden. Only {allowed_schemes} allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL."

    hostname_clean = hostname.strip().lower()

    if hostname_clean in BLOCKED_HOSTNAMES:
        return False, f"Host '{hostname}' is explicitly blocked (internal/loopback)."

    # Cloud metadata check
    if hostname_clean in ("169.254.169.254", "metadata.google.internal", "fd00:ec2::254"):
        return False, f"Access to cloud metadata endpoint '{hostname}' is blocked."

    # Check integer, hex, or octal IPv4 notations
    if hostname_clean.isdigit():
        try:
            val = int(hostname_clean)
            if 0 <= val <= 0xFFFFFFFF:
                ip = ipaddress.IPv4Address(val)
                if is_ip_restricted(ip):
                    return False, f"Integer IP '{hostname}' ({ip}) resolves to restricted address."
        except Exception:
            pass
    elif hostname_clean.startswith("0x") or hostname_clean.startswith("0X"):
        try:
            val = int(hostname_clean, 16)
            if 0 <= val <= 0xFFFFFFFF:
                ip = ipaddress.IPv4Address(val)
                if is_ip_restricted(ip):
                    return False, f"Hex IP '{hostname}' ({ip}) resolves to restricted address."
        except Exception:
            pass

    # Check if host is direct IP literal
    try:
        ip = ipaddress.ip_address(hostname_clean)
        if is_ip_restricted(ip):
            return False, f"Direct IP '{hostname}' resolves to restricted/private address."
    except ValueError:
        # Not a direct IP literal; resolve via DNS
        try:
            # Resolve all addresses (both IPv4 and IPv6)
            addr_info = socket.getaddrinfo(hostname_clean, None)
            if not addr_info:
                return False, f"DNS resolution failed: Could not resolve host '{hostname}'."

            for entry in addr_info:
                sockaddr = entry[4]
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_restricted(ip_obj):
                    return False, f"Host '{hostname}' resolves to restricted IP {ip_str}."
        except socket.gaierror as e:
            return False, f"DNS resolution failed for host '{hostname}': {str(e)}"
        except Exception as e:
            return False, f"Security check failed for host '{hostname}': {str(e)}"

    return True, ""

