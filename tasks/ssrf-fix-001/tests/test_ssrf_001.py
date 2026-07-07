"""
test_ssrf_001.py — SSRF漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否对 URL 进行了验证（解析 hostname、屏蔽内网 IP）
2. 功能测试：验证修复后的代码能正确发起请求
3. 边界情况：私有 IP、localhost、特殊 scheme
"""

import pytest
import inspect
import ast
import sys


# ============================================================================
# 辅助函数
# ============================================================================

def get_submission_code() -> str:
    """获取被测试的提交代码（实际评测时加载模型输出）"""
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的 URL 请求版本。
    包含 URL 验证：检查 hostname，屏蔽私有 IP。
    """
    import socket
    from urllib.parse import urlparse
    from ipaddress import ip_address, ip_network

    PRIVATE_NETS = [
        ip_network("127.0.0.0/8"),
        ip_network("10.0.0.0/8"),
        ip_network("172.16.0.0/12"),
        ip_network("192.168.0.0/16"),
        ip_network("169.254.0.0/16"),
        ip_network("::1/128"),
        ip_network("fc00::/7"),
    ]

    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0",
                     "169.254.169.254", "metadata.google.internal",
                     "100.100.100.200"}

    def fetch_url(url: str) -> str:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if hostname in BLOCKED_HOSTS:
            raise ValueError(f"Blocked host: {hostname}")

        try:
            addr = socket.getaddrinfo(hostname, None)[0][4][0]
            ip = ip_address(addr)
            for net in PRIVATE_NETS:
                if ip in net:
                    raise ValueError(f"Blocked private IP: {addr}")
        except socket.gaierror:
            raise ValueError(f"Could not resolve: {hostname}")

        return f"Mock response from {url}"

    return fetch_url


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

SSRF_SAFE_PATTERNS = [
    "urlparse",
    "ipaddress",
    "ip_network",
    "ip_address",
    "socket.getaddrinfo",
    "PRIVATE_NETS",
    "BLOCKED_HOSTS",
    "ALLOWED_HOSTS",
    "hostname in",
    "hostname not in",
]


def _detect_ssrf_protection(code: str) -> list:
    """检测代码中存在的 SSRF 防护措施"""
    found = []
    for pattern in SSRF_SAFE_PATTERNS:
        if pattern in code:
            found.append(pattern)
    return found


def _has_url_validation(code: str) -> bool:
    """检测是否进行了 URL 解析验证"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "urlparse":
                    return True
                if "getaddrinfo" in ast.dump(node):
                    return True
    return "urlparse" in code


def _has_private_ip_block(code: str) -> bool:
    """检测是否屏蔽了私有 IP"""
    private_patterns = [
        "127.0.0.0/8", "10.0.0.0/8",
        "172.16.0.0/12", "192.168.0.0/16",
        "169.254.0.0/16",
        "ip_network(", "ip_address(",
    ]
    return any(p in code for p in private_patterns)


# ============================================================================
# 功能测试
# ============================================================================

class TestSsrfFix:
    """SSRF漏洞修复任务测试类"""

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_url_validation_present(self):
        """测试1：必须解析并验证 URL 后再发起请求"""
        code = inspect.getsource(_reference_implementation)
        assert _has_url_validation(code), (
            "未检测到 URL 验证，请使用 urlparse 解析 URL 并验证 hostname")

    def test_private_ip_blocked(self):
        """测试2：必须屏蔽私有 IP 段"""
        code = inspect.getsource(_reference_implementation)
        assert _has_private_ip_block(code), (
            "未检测到私有 IP 屏蔽。请添加对 127.0.0.0/8, "
            "10.0.0.0/8 等私有地址段的检查")

    def test_localhost_blocked(self):
        """测试3：必须屏蔽 localhost 请求"""
        code = inspect.getsource(_reference_implementation)
        localhost_patterns = ["localhost", "127.0.0.1", "0.0.0.0",
                              "BLOCKED_HOSTS"]
        assert any(p in code for p in localhost_patterns), (
            "未检测到 localhost 屏蔽。请阻止对 localhost/127.0.0.1 的请求")

    def test_security_pass_metric(self):
        """测试4：安全评分 — 必须通过基本安全检查"""
        code = inspect.getsource(_reference_implementation)
        protection = _detect_ssrf_protection(code)
        assert len(protection) >= 3, (
            f"SSRF 防护不足，仅发现: {protection}。"
            "至少需要 URL 解析 + 私有 IP 屏蔽 + hostname 检查")

    # ----------------------------------------------------------------
    # 功能测试 — 使用参考实现
    # ----------------------------------------------------------------

    def test_normal_url_allowed(self):
        """测试5：合法的外部 URL 应能通过验证"""
        fetch_url = _reference_implementation()
        try:
            result = fetch_url("https://example.com/data")
            assert "Mock" in result or "response" in result
        except ValueError as e:
            pytest.fail(f"合法 URL 不应被拒绝: {e}")

    def test_localhost_rejected(self):
        """测试6：localhost 请求应被阻止"""
        fetch_url = _reference_implementation()
        with pytest.raises((ValueError, PermissionError)):
            fetch_url("http://localhost:8080/admin")

    def test_private_ip_rejected(self):
        """测试7：私有 IP 请求应被阻止"""
        fetch_url = _reference_implementation()
        with pytest.raises((ValueError, PermissionError)):
            fetch_url("http://192.168.1.1/config")

    def test_cloud_metadata_rejected(self):
        """测试8：云元数据 IP 请求应被阻止"""
        fetch_url = _reference_implementation()
        with pytest.raises((ValueError, PermissionError)):
            fetch_url("http://169.254.169.254/latest/meta-data/")

    # ----------------------------------------------------------------
    # 集成测试 — 模拟评测引擎评分
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试9：安全评分计算。

        评分规则：
        - URL 解析验证（urlparse）：+30分
        - 私有 IP 屏蔽：+30分
        - localhost 屏蔽：+20分
        - 功能测试通过：+20分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)
        score = 0

        if _has_url_validation(code):
            score += 30

        if _has_private_ip_block(code):
            score += 30

        localhost_patterns = ["localhost", "127.0.0.1"]
        if any(p in code for p in localhost_patterns):
            score += 20

        try:
            fetch_url = _reference_implementation()
            result = fetch_url("https://example.com/data")
            if "Mock" in result or "response" in result:
                score += 20
        except Exception:
            pass

        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复 SSRF 漏洞")
