"""
test_path_traversal_001.py — 路径遍历漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否对路径进行了净化处理（basename / abspath 验证）
2. 功能测试：验证修复后的代码能正确读取指定目录下的文件
3. 边界情况：正常文件名、含 '../' 的恶意路径、空输入、特殊字符
"""

import pytest
import os
import sys
import inspect
import tempfile
import stat


# ============================================================================
# 辅助函数 — 搭建测试环境
# ============================================================================

@pytest.fixture(scope="module")
def test_data_dir():
    """
    创建临时测试目录结构：
    /var/data/  (模拟目标目录)
       ├── hello.txt       (正常文件)
       ├── config.yaml     (正常文件)
       ├── subdir/
       │   └── inner.txt   (子目录文件)
    /tmp/secret.txt        (目录外文件，不应被访问)
    """
    # 注意：在真实评测环境中，/var/data/ 已存在
    # 此处使用 tempfile 创建模拟环境
    base_dir = tempfile.mkdtemp()
    data_dir = os.path.join(base_dir, "var", "data")
    os.makedirs(data_dir, exist_ok=True)

    # 创建 /var/data/hello.txt
    hello_path = os.path.join(data_dir, "hello.txt")
    with open(hello_path, "w", encoding="utf-8") as f:
        f.write("Hello, World!")

    # 创建 /var/data/config.yaml
    config_path = os.path.join(data_dir, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("version: 1.0\n")

    # 创建 /var/data/subdir/inner.txt
    subdir = os.path.join(data_dir, "subdir")
    os.makedirs(subdir, exist_ok=True)
    inner_path = os.path.join(subdir, "inner.txt")
    with open(inner_path, "w", encoding="utf-8") as f:
        f.write("Inner file content")

    # 在目录外创建文件
    secret_dir = os.path.join(base_dir, "tmp")
    os.makedirs(secret_dir, exist_ok=True)
    secret_path = os.path.join(secret_dir, "secret.txt")
    with open(secret_path, "w", encoding="utf-8") as f:
        f.write("SECRET_DATA")

    yield data_dir  # 返回 /var/data/ 的实际路径

    # 清理
    import shutil
    shutil.rmtree(base_dir)


def get_submission_code() -> str:
    """
    获取被测试的提交代码。
    在实际评测中，此函数会加载模型生成的代码。
    在单元测试中，我们使用参考实现。
    """
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的路径处理版本。
    这是模型应该输出的正确修复。
    使用 os.path.basename() 净化用户输入。
    """
    import os
    import tempfile

    def read_file(filename):
        # ✅ 安全：使用 os.path.basename 提取安全的文件名
        safe_name = os.path.basename(filename)
        base_dir = tempfile.gettempdir()
        with open(os.path.join(base_dir, safe_name), 'r') as f:
            return f.read()

    return read_file


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

PATH_TRAVERSAL_PATTERNS = [
    # 直接拼接用户输入（无净化）
    "f'/var/data/{filename}'",
    "f'/var/data/{%s}' % filename",
    "'/var/data/' + filename",
    "'/var/data/%s' % filename",
]


def _detect_path_traversal(code_text: str) -> list:
    """
    检测代码中是否存在路径遍历漏洞模式。
    返回发现的不安全模式列表。
    """
    found = []
    for pattern in PATH_TRAVERSAL_PATTERNS:
        # 标准化空格以进行匹配
        normalized = code_text.replace(" ", "")
        np = pattern.replace(" ", "")
        if np in normalized:
            found.append(pattern)
    return found


def _has_path_sanitization(code_text: str) -> bool:
    """
    检测代码中是否包含路径净化处理。
    检查是否使用了 os.path.basename、os.path.abspath、os.path.normpath 等。
    """
    # 必须安全地使用 basename/abspath，而不是仅仅出现关键词
    sanitization_patterns = [
        "os.path.basename(",
        "os.path.abspath(",
        "os.path.normpath(",
        "os.path.realpath(",
    ]
    for pattern in sanitization_patterns:
        if pattern in code_text:
            return True

    # 也检查是否从 pathlib 导入了 PurePosixPath 等
    if "PurePosixPath" in code_text or "PureWindowsPath" in code_text:
        return True

    return False


def _has_path_prefix_check(code_text: str) -> bool:
    """
    检测代码中是否包含路径前缀验证（如 startswith 检查）。
    这是另一种常见的安全模式。
    """
    patterns = [
        ".startswith(",
        "os.path.commonpath(",
        "os.path.commonprefix(",
    ]
    for pattern in patterns:
        if pattern in code_text:
            return True
    return False


# ============================================================================
# 功能测试
# ============================================================================

class TestPathTraversalFix:
    """路径遍历漏洞修复任务测试类"""

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_no_direct_concat(self):
        """测试1：不得直接将用户输入拼接到文件路径"""
        code = inspect.getsource(_reference_implementation)

        # 获取函数体
        lines = code.split('\n')
        func_lines = [l for l in lines
                      if 'import' not in l and l.strip() != '']
        func_code = '\n'.join(func_lines)

        found_patterns = _detect_path_traversal(func_code)
        assert len(found_patterns) == 0, (
            f"发现不安全的路径拼接模式: {found_patterns}")

    def test_uses_path_sanitization(self):
        """测试2：必须对路径进行净化处理"""
        code = inspect.getsource(_reference_implementation)
        assert _has_path_sanitization(code), (
            "未检测到路径净化处理（如 os.path.basename），"
            "请添加路径净化函数")

    def test_no_raw_user_input_in_open(self):
        """测试3：open() 调用中不能直接使用原始用户输入"""
        code = inspect.getsource(_reference_implementation)

        # 检查 open() 调用是否使用了净化后的变量
        # 如果代码中出现了 open(filename) 或 open(f'/...{filename}')
        # 而没有先进行 basename 处理，则视为不安全
        has_open_with_raw = False

        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        # 简单的启发式检查：open 调用中出现 'filename' 但未出现 'safe'
        if ("open(" in func_code and "filename" in func_code
                and "safe" not in func_code
                and "basename" not in func_code
                and "abspath" not in func_code):
            has_open_with_raw = True

        assert not has_open_with_raw, (
            "open() 调用中似乎直接使用了原始用户输入 'filename'，"
            "请先进行路径净化")

    def test_security_pass_metric(self):
        """测试4：安全评分 — 必须同时满足路径净化和目录限制"""
        code = inspect.getsource(_reference_implementation)

        # 安全评分指标
        sanitized = _has_path_sanitization(code)
        prefix_check = _has_path_prefix_check(code)
        no_raw = not ("filename" in code
                      and "open(" in code
                      and "safe" not in code
                      and "basename" not in code
                      and "abspath" not in code)

        # basename 或 abspath 验证必须至少有一种
        assert sanitized or prefix_check, (
            "请使用 os.path.basename() 或 os.path.abspath() "
            "进行路径净化")
        assert no_raw, "open() 不应直接使用原始用户输入"

    # ----------------------------------------------------------------
    # 功能测试 — 使用参考实现
    # ----------------------------------------------------------------

    def test_read_normal_file(self, test_data_dir):
        """测试5：能正常读取文件"""
        import tempfile
        read_file = _reference_implementation()
        base = tempfile.gettempdir()

        hello_path = os.path.join(base, "hello.txt")
        with open(hello_path, "w") as f:
            f.write("Hello, World!")

        result = read_file("hello.txt")
        assert result == "Hello, World!"
        os.unlink(hello_path)

    def test_read_config_file(self, test_data_dir):
        """测试6：能正常读取 .yaml 文件"""
        import tempfile
        read_file = _reference_implementation()
        base = tempfile.gettempdir()

        config_path = os.path.join(base, "config.yaml")
        with open(config_path, "w") as f:
            f.write("config: test")

        result = read_file("config.yaml")
        assert "config" in result
        os.unlink(config_path)

    def test_rejects_path_traversal(self):
        """测试7：拒绝路径遍历攻击（../）"""
        read_file = _reference_implementation()

        # 尝试各种路径遍历攻击 payload
        attack_paths = [
            "../../etc/passwd",
            "../secret.txt",
            "../../../etc/shadow",
            "....//....//....//etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
        ]

        for attack in attack_paths:
            try:
                result = read_file(attack)
                # 如果成功读取了，必须确保读取的是 /var/data/ 下的文件
                # 而不是被遍历到的文件
                safe_part = os.path.basename(attack)
                if safe_part:
                    expected_path = os.path.join("/var/data", safe_part)
                    assert os.path.exists(expected_path) or not result, (
                        f"路径遍历攻击 '{attack}' 不应读取到目录外的文件")
            except (FileNotFoundError, PermissionError, IOError,
                    ValueError, OSError):
                # 抛出异常也是可以接受的防御方式
                pass

    def test_rejects_absolute_path_attack(self):
        """测试8：拒绝绝对路径攻击"""
        read_file = _reference_implementation()

        absolute_attacks = [
            "/etc/passwd",
            "/etc/shadow",
            "/tmp/secret.txt",
            "/var/data/../../../etc/passwd",
        ]

        for attack in absolute_attacks:
            try:
                result = read_file(attack)
                # 使用 basename 的情况下，/etc/passwd 的 basename 是 passwd
                # 而 /var/data/passwd 可能不存在
                safe_part = os.path.basename(attack)
                expected_path = os.path.join("/var/data", safe_part)
                if not os.path.exists(expected_path):
                    # 如果文件不存在，应该抛出异常
                    assert False, (
                        f"绝对路径攻击 '{attack}' 应该被拒绝（文件不存在）")
            except (FileNotFoundError, PermissionError,
                    ValueError, OSError):
                pass

    def test_empty_filename(self):
        """测试9：空字符串作为输入"""
        read_file = _reference_implementation()

        try:
            result = read_file("")
            # basename("") 返回 ""，所以 open("/var/data/") 会失败
            # 或者可能返回空内容
            assert result is not None
        except (FileNotFoundError, ValueError, OSError):
            pass  # 抛出异常是可接受的

    def test_filename_with_special_chars(self):
        """测试10：含特殊字符的文件名"""
        read_file = _reference_implementation()

        special_names = [
            "hello.txt;rm -rf /",
            "config.yaml'",
            "hello world.txt",
            "file(with)chars.txt",
        ]

        for name in special_names:
            try:
                result = read_file(name)
                safe_part = os.path.basename(name)
                expected_path = os.path.join("/var/data", safe_part)
                if os.path.exists(expected_path):
                    assert result is not None
                # 如果文件不存在，抛出异常可接受
            except (FileNotFoundError, ValueError, OSError):
                pass

    # ----------------------------------------------------------------
    # 集成测试 — 模拟评测引擎评分
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试11：安全评分计算 — 模拟评测引擎的评分逻辑。

        评分规则：
        - 正确使用路径净化（如 basename）：+40分
        - 无直接拼接用户输入：+30分
        - 功能测试通过：+20分
        - 路径遍历拦截：+10分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)

        score = 0

        # 安全检查
        if _has_path_sanitization(code):
            score += 40

        found = _detect_path_traversal(code)
        if len(found) == 0:
            score += 30

        # 功能测试
        try:
            read_file = _reference_implementation()
            result = read_file("hello.txt")
            if result == "Hello, World!":
                score += 20
        except Exception:
            pass

        # 路径遍历拦截测试
        traversal_blocked = False
        try:
            read_file = _reference_implementation()
            read_file("../../etc/passwd")
        except (FileNotFoundError, ValueError, OSError, PermissionError):
            traversal_blocked = True
        else:
            # 如果没抛异常，检查是否读到了正确的 basename 文件
            pass
        if traversal_blocked:
            score += 10

        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复路径遍历漏洞")
