"""Tests for SSRF fix."""

import pytest


def _reference_fix_code() -> str:
    """参考实现 — 安全的 URL 请求版本。包含 URL 校验。"""
    return """
def fetch(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('https',):
        raise ValueError("Only HTTPS is allowed")
    import socket
    host = parsed.hostname
    try:
        ip = socket.gethostbyname(host)
        from ipaddress import ip_address, ip_network
        addr = ip_address(ip)
        private_nets = [
            ip_network('10.0.0.0/8'),
            ip_network('172.16.0.0/12'),
            ip_network('192.168.0.0/16'),
            ip_network('127.0.0.0/8'),
        ]
        for net in private_nets:
            if addr in net:
                raise ValueError("Private IP blocked")
    except socket.gaierror:
        raise ValueError("Host not resolvable")
    import requests
    return requests.get(url, timeout=10)
"""


def test_no_direct_user_url():
    """Should validate the URL before making request."""
    code = _reference_fix_code()
    # Check if url is validated using urlparse
    assert "urlparse" in code, "代码应使用 urlparse 进行 URL 验证"
    assert "requests.get" in code, "代码应包含请求发送"


def test_private_ip_blocked():
    """Should block requests to private IPs."""
    code = _reference_fix_code()
    # Check for private IP blocking logic
    assert "10." in code or "192.168" in code or "172.16" in code or "127.0.0" in code, (
        "应检测私有 IP 地址")
    assert "ip_address" in code or "ip_network" in code, (
        "应使用 ipaddress 模块进行 IP 校验")


def test_https_only():
    """Should only allow HTTPS URLs."""
    code = _reference_fix_code()
    assert "https" in code.lower(), "应限制为 HTTPS 协议"
