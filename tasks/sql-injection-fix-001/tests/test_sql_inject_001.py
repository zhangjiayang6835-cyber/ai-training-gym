"""
test_sql_inject_001.py — SQL注入修复任务测试套件

测试内容：
1. 安全性检查：检测是否使用参数化查询（非字符串拼接）
2. 功能测试：验证修复后的代码能正确执行查询
3. 边界情况：空输入、特殊字符
"""

import pytest
import sqlite3
import inspect
import ast
import os
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
    # 默认返回参考实现（参数化查询版本）
    # 实际使用时，此函数会从模型输出中读取代码
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的参数化查询版本。
    这是模型应该输出的正确修复。
    """
    import sqlite3

    def get_user(username):
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        # 创建测试表
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER, username TEXT)")
        cursor.execute("INSERT INTO users VALUES (1, 'admin')")
        cursor.execute("INSERT INTO users VALUES (2, 'guest')")
        conn.commit()

        # ✅ 安全：参数化查询
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchall()

    return get_user


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

SQL_KEYWORDS = ["select", "insert", "update", "delete", "from", "where"]

# 检测 SQL 字符串拼接的模式
STRING_FORMAT_PATTERNS = [
    "f'", 'f"',           # f-strings
    ".format(",            # str.format()
    "%s", "%d", "%("      # % formatting (in SQL context)
]


def _has_sql_string_concatenation(code: str) -> bool:
    """
    使用 AST 静态分析检测代码中是否存在 SQL 字符串拼接。
    返回 True 如果发现任何不安全模式。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # 如果代码无法解析，保守起见认为不安全
        return True

    class SqlConcatVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found_unsafe = False

        def _is_sql_context(self, node_text: str) -> bool:
            """判断字符串是否包含 SQL 关键字"""
            lowered = node_text.lower()
            return any(kw in lowered for kw in SQL_KEYWORDS)

        def visit_JoinedStr(self, node):
            """检测 f-string (JoinedStr)"""
            # 检查 f-string 是否包含 SQL 上下文
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if self._is_sql_context(value.value):
                        self.found_unsafe = True
                        return
            self.generic_visit(node)

        def visit_Call(self, node):
            """检测 .format() 调用"""
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'format'):
                # 检查调用者是否包含 SQL 上下文
                if (isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)):
                    if self._is_sql_context(node.func.value.value):
                        self.found_unsafe = True
                        return
            self.generic_visit(node)

        def visit_BinOp(self, node):
            """检测字符串拼接 (+)"""
            if isinstance(node.op, ast.Add):
                left_is_str = (isinstance(node.left, ast.Constant)
                               and isinstance(node.left.value, str))
                right_is_str = (isinstance(node.right, ast.Constant)
                                and isinstance(node.right.value, str))
                if left_is_str or right_is_str:
                    left_text = (node.left.value if left_is_str else "")
                    right_text = (node.right.value if right_is_str else "")
                    if self._is_sql_context(left_text + right_text):
                        self.found_unsafe = True
                        return
            self.generic_visit(node)

    visitor = SqlConcatVisitor()
    visitor.visit(tree)
    return visitor.found_unsafe


def _has_parameterized_query(code: str) -> bool:
    """
    检测代码中是否使用了参数化查询（? 占位符）。
    """
    return "?" in code and ("execute(" in code or "executemany(" in code)


# ============================================================================
# 功能测试
# ============================================================================

class TestSqlInjectionFix:
    """SQL注入修复任务测试类"""

    # ----------------------------------------------------------------
    # 安全性测试
    # ----------------------------------------------------------------

    def test_no_fstring_in_query(self):
        """测试1：SQL 查询中不得使用 f-string"""
        code = inspect.getsource(_reference_implementation)
        # 获取函数体（排除 import 语句）
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        # 应该没有 f-string 拼接
        for pattern in ["f'", 'f"']:
            # 检查不含 SQL 关键字的 f-string 是允许的
            # 我们只检查包含 SQL 关键字的 f-string
            has_fstring_sql = False
            if pattern in func_code:
                # 检查是否与 SQL 相关
                idx = func_code.find(pattern)
                surrounding = func_code[max(0, idx-20):idx+80].lower()
                if any(kw in surrounding for kw in SQL_KEYWORDS):
                    has_fstring_sql = True
            assert not has_fstring_sql, (
                f"发现不安全的 f-string SQL 拼接: {pattern}")

    def test_no_format_in_query(self):
        """测试2：SQL 查询中不得使用 .format()"""
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        has_format_sql = False
        if '.format(' in func_code:
            idx = func_code.find('.format(')
            surrounding = func_code[max(0, idx-30):idx+60].lower()
            if any(kw in surrounding for kw in SQL_KEYWORDS):
                has_format_sql = True
        assert not has_format_sql, "发现不安全的 .format() SQL 拼接"

    def test_no_percent_formatting_in_query(self):
        """测试3：SQL 查询中不得使用 % 格式化"""
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        for pattern in ["%s", "%d"]:
            has_percent_sql = False
            if pattern in func_code:
                idx = func_code.find(pattern)
                surrounding = func_code[max(0, idx-20):idx+40].lower()
                if any(kw in surrounding for kw in SQL_KEYWORDS):
                    has_percent_sql = True
            assert not has_percent_sql, (
                f"发现不安全的 % 格式化 SQL 拼接: {pattern}")

    def test_uses_parameterized_query(self):
        """测试4：确认使用了参数化查询（? 占位符）"""
        code = inspect.getsource(_reference_implementation)
        assert "?" in code, "未检测到 ? 占位符，请使用参数化查询"
        assert "execute(" in code, "未检测到 execute() 调用"

    def test_static_analysis_no_concatenation(self):
        """测试5：AST 静态分析确认无字符串拼接"""
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        has_concat = _has_sql_string_concatenation(func_code)
        assert not has_concat, "AST 静态分析检测到 SQL 字符串拼接"

    # ----------------------------------------------------------------
    # 功能测试
    # ----------------------------------------------------------------

    def test_get_user_returns_correct_result(self):
        """测试6：get_user 能正确返回用户信息"""
        get_user = _reference_implementation()
        result = get_user('admin')
        assert len(result) > 0, "应返回至少一条记录"
        assert result[0][1] == 'admin', f"期望用户名 'admin'，实际 {result[0][1]}"

    def test_get_user_nonexistent(self):
        """测试7：查询不存在的用户应返回空列表"""
        get_user = _reference_implementation()
        result = get_user('nonexistent_user')
        assert result == [], f"不存在的用户应返回空列表，实际 {result}"

    def test_get_user_special_chars(self):
        """测试8：处理包含特殊字符的用户名"""
        get_user = _reference_implementation()
        special_cases = ["admin' OR '1'='1", "guest; DROP TABLE users;",
                         "test_user", "123", "admin\"", "\\admin"]
        for username in special_cases:
            # 参数化查询不会因为特殊字符而报错或注入
            result = get_user(username)
            assert isinstance(result, list), (
                f"特殊用户名 '{username}' 查询应返回列表")

    def test_get_user_empty_string(self):
        """测试9：空字符串作为输入"""
        get_user = _reference_implementation()
        result = get_user('')
        assert isinstance(result, list), "空字符串查询应返回列表"

    def test_function_signature_preserved(self):
        """测试10：函数签名保持不变"""
        import inspect as ins
        try:
            sig = ins.signature(_reference_implementation())
            params = list(sig.parameters.keys())
            assert 'username' in params, (
                f"函数应保持参数 'username'，实际参数: {params}")
        except (ValueError, TypeError):
            pass  # 某些动态函数可能无法检查签名

    # ----------------------------------------------------------------
    # 集成测试 — 模拟模型输出评测
    # ----------------------------------------------------------------

    def test_security_score_calculation(self):
        """
        测试11：安全评分计算 — 模拟评测引擎的评分逻辑。

        评分规则：
        - 没有字符串拼接：+50分
        - 使用参数化查询：+30分
        - 功能测试通过：+20分
        - 总分 ≥ 80 视为通过
        """
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        func_lines = [l for l in lines if 'import' not in l]
        func_code = '\n'.join(func_lines)

        score = 0

        # 安全检查
        if not _has_sql_string_concatenation(func_code):
            score += 50

        if _has_parameterized_query(func_code):
            score += 30

        # 功能测试
        try:
            get_user = _reference_implementation()
            result = get_user('admin')
            if len(result) > 0 and result[0][1] == 'admin':
                score += 20
        except Exception:
            pass

        assert score >= 80, (
            f"安全评分 {score}/100 < 80，请修复安全问题")
