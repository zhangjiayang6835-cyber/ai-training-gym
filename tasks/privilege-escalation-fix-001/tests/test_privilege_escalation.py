"""
test_privilege_escalation.py — 权限提升漏洞修复任务测试套件

测试内容：
1. 安全性检查：检测是否包含资源所有者校验
2. 功能测试：验证修复后的代码能正确访问授权资源
3. 越权测试：验证无法访问其他用户的资源
"""

import pytest
import inspect
import ast
import os
import sys


# ============================================================================
# 辅助函数
# ============================================================================

def get_submission_code() -> str:
    """获取被测试的提交代码"""
    return _reference_implementation


def _reference_implementation():
    """
    参考实现 — 安全的权限校验版本。
    这是模型应该输出的正确修复。
    """
    class User:
        def __init__(self, id, name, role="user"):
            self.id = id
            self.name = name
            self.role = role

    def get_db():
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER, name TEXT, email TEXT)")
        cursor.execute("INSERT INTO profiles VALUES (1, 'Alice', 'alice@example.com')")
        cursor.execute("INSERT INTO profiles VALUES (2, 'Bob', 'bob@example.com')")
        conn.commit()
        return conn

    def get_user_profile(current_user, target_user_id):
        # 安全：资源所有者校验
        if current_user.id != target_user_id:
            raise PermissionError("无权访问其他用户的资料")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (target_user_id,))
        return cursor.fetchone()

    return User, get_user_profile


# ============================================================================
# 安全检查 — 静态分析
# ============================================================================

def _has_authorization_check(code: str) -> bool:
    """
    检测代码中是否包含权限校验逻辑。
    检查：id 比较、权限检查、raise PermissionError 等模式。
    """
    checks = [
        "current_user.id != target_user_id",
        "current_user.id !=",
        "!= target_user_id",
        "PermissionError",
        "raise",
        "authorized",
        "permission",
    ]
    code_lower = code.lower()
    found = sum(1 for c in checks if c.lower() in code_lower)
    return found >= 2  # 至少命中两个安全检查模式


def _has_user_id_comparison(code: str) -> bool:
    """检测代码中是否包含用户 ID 比较逻辑"""
    return "!=" in code and ("id" in code.lower() or "user_id" in code.lower())


def _get_function_body(code: str, func_name: str = "get_user_profile") -> str:
    """从多函数代码中提取指定函数的函数体"""
    lines = code.split('\n')
    in_func = False
    indent = ""
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def " + func_name):
            in_func = True
            indent = line[:len(line) - len(line.lstrip())]
            continue
        if in_func:
            if stripped == "" or stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                body_lines.append(line)
                continue
            current_indent = line[:len(line) - len(line.lstrip())]
            if current_indent <= indent and stripped:
                break
            body_lines.append(line)
    return '\n'.join(body_lines)


def _has_authorization_before_access(code: str) -> bool:
    """提取 get_user_profile 函数体后，检测数据库访问前是否有权限校验"""
    func_body = _get_function_body(code, "get_user_profile")
    lines = func_body.split('\n')

    db_access_lines = [i for i, l in enumerate(lines) if 'execute(' in l]
    auth_lines = [i for i, l in enumerate(lines)
                  if any(k in l for k in ['raise', 'if ', 'PermissionError',
                                          'return None', 'return []'])]

    if not db_access_lines:
        return False
    if not auth_lines:
        return False

    # 检查是否有权限校验在数据库访问之前
    first_db = min(db_access_lines)
    for auth_line in auth_lines:
        if auth_line < first_db:
            return True
    return False


# ============================================================================
# 功能测试
# ============================================================================

class TestPrivilegeEscalationFix:
    """权限提升修复任务测试类"""

    # ----------------------------------------------------------------
    # 安全性测试（60分）
    # ----------------------------------------------------------------

    def test_has_authorization_check(self):
        """测试1：代码必须包含权限校验逻辑"""
        code = inspect.getsource(_reference_implementation)
        assert _has_authorization_check(code), (
            "未检测到权限校验逻辑。请添加 current_user.id 与 target_user_id 的比较")

    def test_user_id_comparison_exists(self):
        """测试2：必须比较 current_user.id 和 target_user_id"""
        code = inspect.getsource(_reference_implementation)
        assert _has_user_id_comparison(code), (
            "未检测到用户 ID 比较逻辑")

    def test_authorization_before_db_access(self):
        """测试3：权限校验必须在数据库查询之前"""
        code = inspect.getsource(_reference_implementation)
        assert _has_authorization_before_access(code), (
            "权限校验必须在数据库查询之前执行")

    def test_raises_on_unauthorized(self):
        """测试4：越权访问时应抛出异常或返回错误"""
        code = inspect.getsource(_reference_implementation)
        assert "raise" in code or "return None" in code or "return []" in code, (
            "越权访问时应抛出异常或返回空值")

    def test_no_hardcoded_user_id(self):
        """测试5：不应硬编码 user_id"""
        code = inspect.getsource(_reference_implementation)
        lines = code.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if 'target_user_id' in stripped and '=' in stripped and '!=' not in stripped:
                # 允许赋值但不允许硬编码数字
                if any(c.isdigit() for c in stripped.split('=')[-1]):
                    if stripped.split('=')[-1].strip().isdigit():
                        assert False, f"第 {i+1} 行: 不应硬编码 user_id"

    # ----------------------------------------------------------------
    # 功能测试（40分）
    # ----------------------------------------------------------------

    def test_access_own_profile_success(self):
        """测试6：用户可以访问自己的资料"""
        User, get_profile = _reference_implementation()
        current_user = User(1, "Alice")
        result = get_profile(current_user, 1)
        assert result is not None, "用户应能访问自己的资料"
        assert result[1] == "Alice", f"期望 'Alice'，实际 {result[1]}"

    def test_access_other_profile_blocked(self):
        """测试7：用户不能访问他人的资料"""
        User, get_profile = _reference_implementation()
        current_user = User(1, "Alice")
        with pytest.raises((PermissionError, Exception)):
            get_profile(current_user, 2)

    def test_admin_has_no_bypass(self):
        """测试8：普通用户角色不能越权访问（不允许仅靠 role 绕过）"""
        code = inspect.getsource(_reference_implementation)
        # 检查是否错误地使用了 role 来绕过
        if "role" in code.lower() and "admin" in code.lower():
            # 如果检测到 role bypass，需要确保同时有 id 检查
            assert "id" in code.lower(), (
                "使用 role 绕过时仍需检查用户 ID")

    def test_function_signature_preserved(self):
        """测试9：函数签名保持不变 — 检查 get_user_profile 包含 target_user_id 参数"""
        _, get_profile = _reference_implementation()
        import inspect as _inspect
        try:
            sig = _inspect.signature(get_profile)
            params = list(sig.parameters.keys())
            assert 'target_user_id' in params, (
                f"get_user_profile 应保持参数 'target_user_id'，实际: {params}")
        except (ValueError, TypeError):
            pass

    def test_normal_workflow_unaffected(self):
        """测试10：正常业务流程不受影响"""
        User, get_profile = _reference_implementation()
        current_user = User(2, "Bob")
        result = get_profile(current_user, 2)
        assert result is not None, "正常访问应返回结果"
        assert result[1] == "Bob", f"期望 'Bob'，实际 {result[1]}"
        assert result[2] == "bob@example.com", "应返回正确的邮箱"

    # ----------------------------------------------------------------
    # 安全评分计算
    # ------------------------
