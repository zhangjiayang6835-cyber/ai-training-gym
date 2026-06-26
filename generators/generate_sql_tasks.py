"""
generate_sql_tasks.py — SQL 注入训练样本生成器

生成包含 SQL 注入漏洞的 Python 代码片段及其修复版本。
用于训练模型识别和修复 SQL 注入漏洞。

用法: python generators/generate_sql_tasks.py
"""

import json
import random
import os
from typing import Dict, List, Tuple


# ============================================================================
# 场景模板
# ============================================================================

TEMPLATES = [
    # 模板格式: (场景名, 函数名, 参数列表, SQL语句模式, 漏洞位置描述)
    {
        "name": "get_user_by_id",
        "params": ["user_id"],
        "sql_pattern": "SELECT * FROM users WHERE id = {param}",
        "table": "users",
        "returns": "用户信息",
        "description": "根据用户 ID 查询用户信息"
    },
    {
        "name": "get_user_by_username",
        "params": ["username"],
        "sql_pattern": "SELECT * FROM users WHERE username = '{param}'",
        "table": "users",
        "returns": "用户信息",
        "description": "根据用户名查询用户信息"
    },
    {
        "name": "get_product",
        "params": ["product_id"],
        "sql_pattern": "SELECT name, price FROM products WHERE id = {param}",
        "table": "products",
        "returns": "商品名称和价格",
        "description": "根据商品 ID 查询商品信息"
    },
    {
        "name": "get_order",
        "params": ["order_id"],
        "sql_pattern": "SELECT * FROM orders WHERE order_id = '{param}'",
        "table": "orders",
        "returns": "订单信息",
        "description": "根据订单号查询订单信息"
    },
    {
        "name": "get_student",
        "params": ["student_id"],
        "sql_pattern": "SELECT name, grade FROM students WHERE id = {param}",
        "table": "students",
        "returns": "学生姓名和成绩",
        "description": "根据学生 ID 查询学生信息"
    },
    {
        "name": "get_employee",
        "params": ["email"],
        "sql_pattern": "SELECT * FROM employees WHERE email = '{param}'",
        "table": "employees",
        "returns": "员工信息",
        "description": "根据邮箱查询员工信息"
    },
    {
        "name": "search_articles",
        "params": ["keyword"],
        "sql_pattern": "SELECT title, content FROM articles WHERE title LIKE '%{param}%'",
        "table": "articles",
        "returns": "文章标题和内容",
        "description": "根据关键字搜索文章"
    },
]


# ============================================================================
# 漏洞代码生成器
# ============================================================================

VULN_STYLES = ["fstring", "format", "percent", "concat"]


def generate_vulnerable_code(template: Dict, style: str) -> str:
    """
    生成包含 SQL 注入漏洞的代码。

    参数:
        template: 场景模板
        style: 漏洞风格 (fstring/format/percent/concat)

    返回:
        str: 包含漏洞的 Python 代码
    """
    func_name = template["name"]
    params = template["params"]
    param = params[0]
    sql_pattern = template["sql_pattern"]
    table = template["table"]
    returns = template["returns"]

    if style == "fstring":
        sql = sql_pattern.replace("{param}", f"{{{param}}}")
        query_line = f'    cursor.execute(f"{sql}")'
    elif style == "format":
        placeholder = sql_pattern.replace("{param}", "{}")
        query_line = f'    cursor.execute("{placeholder}".format({param}))'
    elif style == "percent":
        if "'{param}'" in sql_pattern or '"{param}"' in sql_pattern:
            placeholder = sql_pattern.replace("'{param}'", "'%s'").replace('"{param}"', '"%s"')
        else:
            placeholder = sql_pattern.replace("{param}", "%s")
        query_line = f'    cursor.execute("{placeholder}" % {param})'
    elif style == "concat":
        # 字符串拼接
        parts = sql_pattern.split("{param}")
        if len(parts) == 2:
            query_line = f'    cursor.execute("{parts[0]}" + {param} + "{parts[1]}")'
        else:
            query_line = f'    cursor.execute("{parts[0]}" + {param})'
    else:
        raise ValueError(f"Unknown style: {style}")

    code = f'''import sqlite3


def {func_name}({param}):
    """
    根据{returns}（⚠️ 包含 SQL 注入漏洞）
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
{query_line}
    result = cursor.fetchall()
    conn.close()
    return result
'''
    return code


def generate_secure_code(template: Dict) -> str:
    """
    生成安全的参数化查询版本。

    参数:
        template: 场景模板

    返回:
        str: 安全的 Python 代码
    """
    func_name = template["name"]
    params = template["params"]
    param = params[0]
    sql_pattern = template["sql_pattern"]
    returns = template["returns"]

    # 转换为参数化查询
    # 将 {param} 和 '{param}' 都替换为 ?
    param_sql = sql_pattern.replace("'{param}'", "?").replace('"{param}"', "?").replace("{param}", "?")

    code = f'''import sqlite3


def {func_name}({param}):
    """
    根据{returns}（✅ 安全：参数化查询）
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("{param_sql}", ({param},))
    result = cursor.fetchall()
    conn.close()
    return result
'''
    return code


# ============================================================================
# 训练样本生成
# ============================================================================

def generate_sample(template: Dict, style: str) -> Dict:
    """
    生成一个训练样本。

    返回:
        Dict: 包含漏洞代码、修复代码、元数据的字典
    """
    func_name = template["name"]
    param = template["params"][0]

    vulnerable = generate_vulnerable_code(template, style)
    secure = generate_secure_code(template)

    return {
        "id": f"sql-{func_name}-{style}",
        "task_id": "sql-injection-fix-001",
        "vulnerable_code": vulnerable,
        "secure_code": secure,
        "function_name": func_name,
        "parameter": param,
        "vulnerability_type": style,
        "vulnerability": "sql_injection",
        "description": template["description"],
        "language": "python",
        "difficulty": "medium"
    }


def generate_all_samples() -> List[Dict]:
    """生成所有组合的训练样本"""
    samples = []
    for template in TEMPLATES:
        for style in VULN_STYLES:
            sample = generate_sample(template, style)
            samples.append(sample)
    return samples


# ============================================================================
# 保存
# ============================================================================

def save_jsonl(samples: List[Dict], filepath: str):
    """保存为 JSONL 格式"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"✅ 已生成 {len(samples)} 个训练样本 → {filepath}")


def save_sample_files(samples: List[Dict], output_dir: str):
    """将每个样本保存为单独的文件（便于查看）"""
    os.makedirs(output_dir, exist_ok=True)
    for sample in samples:
        sample_dir = os.path.join(output_dir, sample["id"])
        os.makedirs(sample_dir, exist_ok=True)

        # 保存漏洞代码
        with open(os.path.join(sample_dir, "vulnerable.py"), 'w') as f:
            f.write(sample["vulnerable_code"])

        # 保存修复代码
        with open(os.path.join(sample_dir, "secure.py"), 'w') as f:
            f.write(sample["secure_code"])

        # 保存元数据
        meta = {k: v for k, v in sample.items()
                if k not in ["vulnerable_code", "secure_code"]}
        with open(os.path.join(sample_dir, "meta.json"), 'w') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存 {len(samples)} 个样本到 {output_dir}/")


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    samples = generate_all_samples()

    # 保存为 JSONL 格式（用于训练）
    save_jsonl(samples, "tasks/sql-injection-fix-001/data/train.jsonl")

    # 也保存为单独文件（便于人工审查）
    save_sample_files(samples, "tasks/sql-injection-fix-001/samples")

    # 打印统计信息
    styles = [s["vulnerability_type"] for s in samples]
    print(f"\n📊 统计:")
    print(f"  总样本数: {len(samples)}")
    print(f"  场景数: {len(TEMPLATES)}")
    print(f"  漏洞风格: {set(styles)}")

    # 打印样例
    print(f"\n📝 样例 ({samples[0]['id']}):")
    print(samples[0]["vulnerable_code"])
