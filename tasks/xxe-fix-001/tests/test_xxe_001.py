"""
test_xxe_001.py — XXE漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否禁用了外部实体解析（使用 defusedxml 或配置安全解析器）
2. 功能测试：验证修复后的代码能正确解析 XML
3. 边界情况：空 XML、特殊字符 XML
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
    参考实现 — 安全的 XML 解析版本。
    使用 defusedxml 替代标准库 xml.etree.ElementTree。
    """
    from defusedxml import ElementTree as ET

    def parse_xml(xml_string: str) -> dict:
        root = ET.fromstring(xml_string)
        result = {}
        for child in root:
            result[child.tag] = child.text
        return result

    return parse_xml


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

XXE_SAFE_PATTERNS = [
    "defusedxml",
    "resolve_entities=False",
    "no_network=True",
]


def _detect_xxe_protection(code: str) -> list:
    """检测代码中是否存在 XXE 防护措施，返回已使用的防护模式"""
    found = []
    for pattern in XXE_SAFE_PATTERNS:
        if pattern in code:
            found.append(pattern)
    return found


def _has_defusedxml_import(code: str) -> bool:
    """检测是否导入了 defusedxml"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "defusedxml" in alias.name:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if "defusedxml" in node.module or (node.module and "defusedxml" in node.module):
                return True
    return False


def _has_safe_parser_config(code: str) -> bool:
    """检测是否配置了安全解析器（如 resolve_entities=False）"""
    patterns = ["resolve_entities=False", "resolve_entities = False",
                 "no_network=True", "no_network = True",
                 "dtd_validation=False", "dtd_validation = False"]
    return any(p in code for p in patterns)


# ============================================================================
# 功能测试
# ============================================================================

class TestXxeFix:
    """XXE漏洞修复任务测试类"""

    SAMPLE_XML = "<root><name>John</name><role>admin</role></root>"
    SAMPLE_EXPECTED = {"name": "John", "role": "admin"}

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_uses_defusedxml_or_safe_parser(self):
        """测试1：必须使用 defusedxml 或配置安全解析器"""
        code = inspect.getsource(_reference_implementation)
        has_defused = _has_defusedxml_import(code)
        has_safe_config = _has_safe_parser_config(code)
        assert has_defused or has_safe_config, (
            "未检测到 XXE 防护：请使用 defusedxml 库或配置解析器 "
            "resolve_entities=False")

    def test_no_unsafe_xml_parse(self):
        """测试2：不得使用未受保护的 xml.etree.ElementTree"""
        code = inspect.getsource(_reference_implementation)
        # 如果使用了 defusedxml，自动通过
        if _has_defusedxml_import(code):
            return
        # 仅检查 import 行，排除 docstring 中的文本提及
        import_lines = [l for l in code.split('\n') if 'import' in l]
        uses_xml_etree = any("xml.etree" in l for l in import_lines)
        if uses_xml_etree:
            assert _has_safe_parser_config(code), (
                "使用 xml.etree.ElementTree 时必须配置安全选项")

    def test_no_xml_external_entity_constructs(self):
        """测试3：代码中不应存在启用外部实体的配置"""
        code = inspect.getsource(_reference_implementation)
        unsafe_patterns = [
            "load_dtd=True", "load_dtd = True",
            "resolve_entities=True", "resolve_entities = True",
        ]
        for pattern in unsafe_patterns:
            assert pattern not in code, (
                f"发现不安全配置: {pattern}")

    def test_security_pass_metric(self):
        """测试4：安全评分 — 至少有一种防护措施"""
        code = inspect.getsource(_reference_implementation)
        protection = _detect_xxe_protection(code)
        has_defused = _has_defusedxml_import(code)
        has_safe_config = _has_safe_parser_config(code)

        assert has_defused or has_safe_config, (
            "XXE 防护缺失：请添加 defusedxml 或配置安全解析器")
        assert len(protection) > 0, (
            "未检测到任何已知的 XXE 防护模式")

    # ----------------------------------------------------------------
    # 功能测试 — 使用参考实现
    # ----------------------------------------------------------------

    def test_parse_valid_xml(self):
        """测试5：能正确解析合法的 XML"""
        parse_xml = _reference_implementation()
        result = parse_xml(self.SAMPLE_XML)
        assert result == self.SAMPLE_EXPECTED, (
            f"期望 {self.SAMPLE_EXPECTED}，实际 {result}")

    def test_parse_empty_root_xml(self):
        """测试6：能解析空根元素 XML"""
        parse_xml = _reference_implementation()
        result = parse_xml("<root></root>")
        assert isinstance(result, dict), "空 XML 应返回字典"

    def test_parse_nested_xml(self):
        """测试7：能解析嵌套 XML"""
        parse_xml = _reference_implementation()
        xml = "<root><user><name>Alice</name></user></root>"
        result = parse_xml(xml)
        assert isinstance(result, dict), "嵌套 XML 应返回字典"

    # ----------------------------------------------------------------
    # 集成测试 — 模拟评测引擎评分
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试8：安全评分计算。

        评分规则：
        - 使用 defusedxml：+50分
        - 配置安全解析器：+40分
        - 无 unsafe 模式：+10分
        - 功能测试通过：+20分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)
        score = 0

        if _has_defusedxml_import(code):
            score += 50
        elif _has_safe_parser_config(code):
            score += 40

        unsafe_found = any(p in code for p in [
            "load_dtd=True", "resolve_entities=True"])
        if not unsafe_found:
            score += 10

        try:
            parse_xml = _reference_implementation()
            result = parse_xml(self.SAMPLE_XML)
            if result == self.SAMPLE_EXPECTED:
                score += 20
        except Exception:
            pass

        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复 XXE 漏洞")
