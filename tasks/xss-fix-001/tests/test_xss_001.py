"""
test_xss_001.py — XSS跨站脚本漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否使用 HTML 转义（非直接插入用户输入）
2. 功能性测试：验证修复后的代码能正确处理正常请求
3. 边界情况：空输入、特殊字符、脚本注入载荷
"""

import pytest
import html
import inspect
import ast
import sys


# ============================================================================
# 辅助函数
# ============================================================================

def get_submission_code() -> str:
    """
    获取被测试的提交代码。
    在实际评测中，此函数会加载模型生成的代码。
    在单元测试中，我们使用一个参考实现。
    """
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的 HTML 转义版本。
    这是模型应该输出的正确修复。
    """
    import html as _html

    def hello(name: str = "world") -> str:
        """安全的 hello 函数 — 用户输入经过 HTML 转义。"""
        safe_name = _html.escape(name)
        return f"<h1>Hello {safe_name}</h1>"

    return hello


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

XSS_SNIPPETS = [
    "<script>",
    "alert(",
    "onerror=",
    "onload=",
    "javascript:",
]

# 检测直接用户输入插入 HTML 的模式
UNSAFE_PATTERNS_IN_HTML_CONTEXT = [
    # f-string 直接插入变量到 HTML 标签内
    ("{name}", "直接插入变量 name 到 HTML"),
    ("{name}", "直接插入变量 name 到 HTML"),
    ("{user_input}", "直接插入变量 user_input 到 HTML"),
    ("{username}", "直接插入变量 username 到 HTML"),
    ("{msg}", "直接插入变量 msg 到 HTML"),
    ("{message}", "直接插入变量 message 到 HTML"),
    ("{data}", "直接插入变量 data 到 HTML"),
    ("{text}", "直接插入变量 text 到 HTML"),
    ("{content}", "直接插入变量 content 到 HTML"),
]


def _has_direct_user_interpolation(code: str) -> bool:
    """
    使用 AST 静态分析检测代码中是否将用户输入直接插入 HTML。
    返回 True 如果发现任何不安全模式。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True  # 无法解析，保守认为不安全

    class XssVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found_unsafe = False

        def _is_html_context(self, text: str) -> bool:
            """判断字符串是否包含 HTML 标签上下文"""
            lowered = text.lower()
            return any(tag in lowered for tag in ["<h1", "<div", "<p>", "<span",
                                                    "<html", "<body", "<title",
                                                    "<a ", "<img ", "<input",
                                                    "<script", "<style"])

        def visit_JoinedStr(self, node):
            """检测 f-string (JoinedStr) 中是否将变量直接插在 HTML 上下文中"""
            # 检查整个 f-string 是否包含 HTML 标签
            full_text = ""
            has_interpolation = False
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    full_text += value.value
                elif isinstance(value, (ast.Name, ast.Attribute, ast.Call)):
                    has_interpolation = True

            if has_interpolation and self._is_html_context(full_text):
                # 进一步检查：在插值周围是否有转义操作
                # 检查 f-string 的变量部分
                for value in node.values:
                    if isinstance(value, ast.Call):
                        # 如果有函数调用，检查是否是 escape
                        if isinstance(value.func, ast.Attribute):
                            if value.func.attr == "escape":
                                # 有 escape() 调用，安全
                                continue
                    elif isinstance(value, (ast.Name, ast.Attribute)):
                        # 裸变量插入 HTML 上下文 => 不安全
                        # 但跳过那些明显已转义的变量（如 safe_name）
                        var_name = None
                        if isinstance(value, ast.Name):
                            var_name = value.id
                        elif isinstance(value, ast.Attribute):
                            var_name = value.attr

                        if var_name and ("safe" in var_name.lower()
                                         or "escaped" in var_name.lower()
                                         or "sanitized" in var_name.lower()):
                            continue

                        self.found_unsafe = True
                        return

            self.generic_visit(node)

        def visit_Call(self, node):
            """检测 .format() 调用是否将用户输入插入 HTML"""
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'format'):
                # 检查调用者是否包含 HTML 上下文
                if (isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)):
                    if self._is_html_context(node.func.value.value):
                        # 检查 format 参数是否经过转义
                        for arg in node.args:
                            if isinstance(arg, ast.Call):
                                if (isinstance(arg.func, ast.Attribute)
                                        and arg.func.attr == "escape"):
                                    continue
                            elif isinstance(arg, (ast.Name, ast.Constant)):
                                continue
                            self.found_unsafe = True
                            return
            self.generic_visit(node)

        def visit_BinOp(self, node):
            """检测字符串拼接 (+) 将用户输入加入 HTML"""
            if isinstance(node.op, ast.Add):
                # 检查左右操作数是否包含 HTML
                texts = []
                has_user_var = False
                for child in [node.left, node.right]:
                    if isinstance(child, ast.Constant) and isinstance(child.value, str):
                        texts.append(child.value)
                    elif isinstance(child, (ast.Name, ast.Attribute, ast.Call)):
                        has_user_var = True

                combined = " ".join(texts)
                if has_user_var and self._is_html_context(combined):
                    self.found_unsafe = True
                    return
            self.generic_visit(node)

    visitor = XssVisitor()
    visitor.visit(tree)
    return visitor.found_unsafe


def _has_html_escaping(code: str) -> bool:
    """
    检测代码中是否使用了 HTML 转义。
    检查 html.escape, markupsafe.escape, escape, Markup, render_template 等。
    """
    has_import = False
    has_escape_call = False

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        # 检查 import html 或 from html import escape
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("html", "markupsafe"):
                    has_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("html", "markupsafe", "flask", "jinja2"):
                for alias in node.names:
                    if alias.name in ("escape", "Markup", "render_template",
                                       "render_template_string"):
                        has_import = True

        # 检查 escape() 调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "escape":
                has_escape_call = True
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "escape":
                    has_escape_call = True
                elif node.func.attr == "render_template_string":
                    has_escape_call = True

    return has_import or has_escape_call


def _has_flask_template_autoescape(code: str) -> bool:
    """
    检测是否使用了 Flask/Jinja2 自动转义模板。
    """
    patterns = [
        "render_template_string",
        "render_template(",
        "Markup",
        "autoescape",
    ]
    return any(p in code for p in patterns)


# ============================================================================
# 功能测试
# ============================================================================

class TestXssFix:
    """XSS跨站脚本漏洞修复任务测试类"""

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_no_direct_interpolation_in_html(self):
        """测试1：用户输入不得直接插入 HTML（无转义）"""
        code = inspect.getsource(_reference_implementation)
        # 过滤 import 行
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        has_unsafe = _has_direct_user_interpolation(func_code)
        assert not has_unsafe, (
            "检测到用户输入被直接插入 HTML 上下文（无转义），"
            "请使用 html.escape() 进行转义")

    def test_uses_html_escaping(self):
        """测试2：代码必须使用 HTML 转义（html.escape 或类似）"""
        code = inspect.getsource(_reference_implementation)
        assert _has_html_escaping(code), (
            "未检测到 HTML 转义代码。请确保：\n"
            "1. import html 或 from html import escape\n"
            "2. 在插入用户输入前调用 html.escape()")

    def test_no_script_tag_in_output(self):
        """测试3：输出中不应包含未转义的 <script> 标签"""
        hello_func = _reference_implementation()
        payload = "<script>alert('XSS')</script>"
        result = hello_func(payload)
        assert "&lt;script&gt;" in result, (
            f"输出中的 <script> 应被转义为 &lt;script&gt;\n"
            f"实际输出: {result}")

    def test_no_event_handler_in_output(self):
        """测试4：输出中不应包含未转义的 HTML 事件处理器"""
        hello_func = _reference_implementation()
        payload = '<img src=x onerror="alert(1)">'
        result = hello_func(payload)
        assert "onerror" not in result or "&lt;" in result, (
            f"事件处理器属性应被转义\n实际输出: {result}")

    # ----------------------------------------------------------------
    # 功能性测试
    # ----------------------------------------------------------------

    def test_normal_name(self):
        """测试5：正常用户名能正确显示"""
        hello_func = _reference_implementation()
        result = hello_func("Alice")
        assert "Alice" in result, (
            f"正常用户名 'Alice' 应出现在输出中\n实际输出: {result}")
        assert result.startswith("<h1>"), (
            f"输出应以 <h1> 开头\n实际输出: {result}")
        assert result.endswith("</h1>"), (
            f"输出应以 </h1> 结尾\n实际输出: {result}")

    def test_default_name(self):
        """测试6：默认参数 'world' 能正确显示"""
        hello_func = _reference_implementation()
        result = hello_func()
        assert "world" in result, (
            f"默认值 'world' 应出现在输出中\n实际输出: {result}")

    def test_chinese_name(self):
        """测试7：中文名字能正确处理"""
        hello_func = _reference_implementation()
        result = hello_func("张三")
        assert "张三" in result, (
            f"中文名 '张三' 应出现在输出中\n实际输出: {result}")

    def test_empty_name(self):
        """测试8：空字符串作为输入"""
        hello_func = _reference_implementation()
        result = hello_func("")
        assert "<h1>Hello </h1>" in result, (
            f"空字符串输入应生成 '<h1>Hello </h1>'\n实际输出: {result}")

    def test_special_characters(self):
        """测试9：特殊字符应被转义"""
        hello_func = _reference_implementation()
        payloads = [
            ('<b>bold</b>', '&lt;b&gt;'),
            ('"quote"', '&quot;'),
            ("'single'", '&#x27;'),
            ('&', '&amp;'),
        ]
        for payload, expected_encoded in payloads:
            result = hello_func(payload)
            assert expected_encoded in result, (
                f"特殊字符 '{payload}' 应被转义为 '{expected_encoded}'\n"
                f"实际输出: {result}")

    # ----------------------------------------------------------------
    # 安全边界测试（脚本注入载荷）
    # ----------------------------------------------------------------

    def test_script_injection_payload(self):
        """测试10：script 注入载荷应被安全转义"""
        hello_func = _reference_implementation()
        payloads = [
            "<script>alert('XSS')</script>",
            "<script>alert(\"XSS\")</script>",
            "<SCRIPT>alert('XSS')</SCRIPT>",
            "<script>document.cookie</script>",
        ]
        for payload in payloads:
            result = hello_func(payload)
            # 验证 < 和 > 被转义
            assert "&lt;" in result, (
                f"载荷 '{payload[:30]}...' 中的 < 应被转义为 &lt;\n"
                f"实际输出: {result}")
            # 验证没有裸 script 标签
            assert "<script>" not in result.lower(), (
                f"载荷 '{payload[:30]}...' 不应包含裸 <script> 标签\n"
                f"实际输出: {result}")

    def test_html_attribute_injection_payload(self):
        """测试11：HTML 属性注入载荷应被安全转义"""
        hello_func = _reference_implementation()
        payloads = [
            ('"><script>alert(1)</script>', '&gt;'),
            ('" onfocus="alert(1)', '&quot;'),
            ("'-alert(1)-'", '&#x27;'),
        ]
        for payload, expected_encoded in payloads:
            result = hello_func(payload)
            assert expected_encoded in result, (
                f"载荷 '{payload}' 中的特殊字符应被转义为 '{expected_encoded}'\n"
                f"实际输出: {result}")

    # ----------------------------------------------------------------
    # 集成测试 — 模拟模型输出评测
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试12：安全评分计算 — 模拟评测引擎的评分逻辑。

        评分规则：
        - 没有直接插入用户输入到 HTML：+30分
        - 使用 HTML 转义（html.escape 等）：+30分
        - 功能测试通过（正常用户名）：+20分
        - 脚本注入载荷被转义：+20分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        score = 0

        # 安全检查
        if not _has_direct_user_interpolation(func_code):
            score += 30
            print(f"  [PASS] 无直接插入用户输入: +30")

        if _has_html_escaping(code):
            score += 30
            print(f"  [PASS] 使用了 HTML 转义: +30")

        # 功能测试
        try:
            hello_func = _reference_implementation()
            result = hello_func("Alice")
            if "Alice" in result and "<h1>" in result:
                score += 20
                print(f"  [PASS] 功能测试通过: +20")
        except Exception:
            pass

        # 脚本注入测试
        try:
            hello_func = _reference_implementation()
            result = hello_func("<script>alert('XSS')</script>")
            if "&lt;" in result and "<script>" not in result.lower():
                score += 20
                print(f"  [PASS] 脚本注入被转义: +20")
        except Exception:
            pass

        print(f"\n  总分: {score}/100")
        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复 XSS 漏洞")
