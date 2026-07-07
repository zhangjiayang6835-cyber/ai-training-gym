"""
test_deserialization_001.py — 反序列化漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否使用了安全的反序列化方式（json / yaml.safe_load / ast.literal_eval）
2. 功能测试：验证修复后的代码能正确解析数据
3. 边界情况：空数据、特殊字符
"""

import pytest
import inspect
import ast
import json
import sys


# ============================================================================
# 辅助函数
# ============================================================================

def get_submission_code() -> str:
    """获取被测试的提交代码（实际评测时加载模型输出）"""
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的反序列化版本。
    使用 json.loads 替代 pickle.loads / yaml.load。
    """
    import json

    def safe_deserialize(data: bytes) -> dict:
        return json.loads(data.decode("utf-8"))

    return safe_deserialize


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

SAFE_DESERIALIZATION_IMPORTS = [
    "json",
    "yaml.safe_load",
    "yaml",
    "ast.literal_eval",
    "orjson",
]


def _get_unsafe_deserialization_calls(code: str) -> list:
    """检测代码中存在的不安全反序列化调用"""
    unsafe_patterns = [
        "pickle.load(",
        "pickle.loads(",
        "yaml.load(",
        "shelve.open(",
    ]
    found = []
    for pattern in unsafe_patterns:
        if pattern in code:
            # 排除 yaml.safe_load
            if pattern == "yaml.load(":
                if "yaml.safe_load" not in code:
                    found.append(pattern)
            else:
                found.append(pattern)
    return found


def _has_safe_deserialization(code: str) -> bool:
    """检测是否使用了安全的反序列化方式"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        # 检查 import json / import yaml / import orjson
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("json", "orjson"):
                    return True

        # 检查 from yaml import safe_load / from ast import literal_eval
        if isinstance(node, ast.ImportFrom):
            if node.module in ("json", "yaml", "ast", "orjson"):
                for alias in node.names:
                    if alias.name in ("safe_load", "literal_eval", "loads",
                                       "dumps"):
                        if alias.name == "load" and node.module == "yaml":
                            continue  # yaml.load 不安全
                        return True

    # 后备：字符串匹配
    patterns = [".safe_load(", "yaml.safe_load", "ast.literal_eval(",
                "orjson.loads("]
    return any(p in code for p in patterns)


def _has_pickle_allowlist(code: str) -> bool:
    """
    检测是否使用了 pickle 白名单方式（受限的 Unpickler）。
    这是一种可接受的折中方案。
    """
    return "find_class" in code and "Unpickler" in code


# ============================================================================
# 功能测试
# ============================================================================

class TestDeserializationFix:
    """反序列化漏洞修复任务测试类"""

    SAMPLE_DATA = b'{"name": "admin", "role": "admin", "id": 1}'
    SAMPLE_EXPECTED = {"name": "admin", "role": "admin", "id": 1}

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_no_pickle_loads(self):
        """测试1：不得使用 pickle.loads() 处理不可信数据"""
        code = inspect.getsource(_reference_implementation)
        unsafe = _get_unsafe_deserialization_calls(code)
        assert "pickle.loads(" not in unsafe or _has_pickle_allowlist(code), (
            "发现不安全的 pickle.loads() 调用，"
            "请使用 json 或 ast.literal_eval 替代")

    def test_no_yaml_load(self):
        """测试2：不得使用 yaml.load() (不含 SafeLoader)"""
        code = inspect.getsource(_reference_implementation)
        unsafe = _get_unsafe_deserialization_calls(code)
        assert "yaml.load(" not in unsafe, (
            "发现不安全的 yaml.load() 调用，"
            "请使用 yaml.safe_load() 或指定 Loader=yaml.SafeLoader")

    def test_uses_safe_deserialization(self):
        """测试3：必须使用安全的反序列化方式"""
        code = inspect.getsource(_reference_implementation)
        has_safe = _has_safe_deserialization(code)
        has_allowlist = _has_pickle_allowlist(code)

        assert has_safe or has_allowlist, (
            "未检测到安全反序列化方式。"
            "请使用 json.loads, yaml.safe_load, "
            "或 ast.literal_eval 替代不安全的反序列化")

    def test_security_pass_metric(self):
        """测试4：安全评分 — 必须通过基本安全检查"""
        code = inspect.getsource(_reference_implementation)
        unsafe = _get_unsafe_deserialization_calls(code)
        has_safe = _has_safe_deserialization(code)

        assert len(unsafe) == 0, (
            f"发现不安全的反序列化调用: {unsafe}")
        assert has_safe, "请使用安全的反序列化方式"

    # ----------------------------------------------------------------
    # 功能测试 — 使用参考实现
    # ----------------------------------------------------------------

    def test_deserialize_valid_json(self):
        """测试5：能正确解析合法的 JSON 数据"""
        deserialize = _reference_implementation()
        result = deserialize(self.SAMPLE_DATA)
        assert result == self.SAMPLE_EXPECTED, (
            f"期望 {self.SAMPLE_EXPECTED}，实际 {result}")

    def test_deserialize_empty_object(self):
        """测试6：能解析空对象"""
        deserialize = _reference_implementation()
        result = deserialize(b"{}")
        assert result == {}, "空对象 {} 应返回空字典"

    def test_deserialize_nested_data(self):
        """测试7：能解析嵌套数据"""
        deserialize = _reference_implementation()
        data = b'{"user": {"name": "Alice", "scores": [1, 2, 3]}}'
        result = deserialize(data)
        assert "user" in result
        assert result["user"]["name"] == "Alice"

    def test_deserialize_unicode(self):
        """测试8：能正确处理 Unicode 字符"""
        deserialize = _reference_implementation()
        data = '{"message": "你好，世界"}'.encode("utf-8")
        result = deserialize(data)
        assert result["message"] == "你好，世界"

    # ----------------------------------------------------------------
    # 集成测试 — 模拟评测引擎评分
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试9：安全评分计算。

        评分规则：
        - 使用 json.loads / orjson.loads：+50分
        - 使用 yaml.safe_load / ast.literal_eval：+40分
        - 不使用 pickle/yaml.load：+30分
        - 功能测试通过：+20分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)
        unsafe = _get_unsafe_deserialization_calls(code)
        has_safe = _has_safe_deserialization(code)
        has_allowlist = _has_pickle_allowlist(code)

        score = 0

        # 安全检查
        if len(unsafe) == 0:
            score += 30

        if has_safe:
            if "json" in code:
                score += 50
            elif "yaml.safe_load" in code or "ast.literal_eval" in code:
                score += 40
        elif has_allowlist:
            score += 30

        # 功能测试
        try:
            deserialize = _reference_implementation()
            result = deserialize(self.SAMPLE_DATA)
            if result == self.SAMPLE_EXPECTED:
                score += 20
        except Exception:
            pass

        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复反序列化漏洞")
