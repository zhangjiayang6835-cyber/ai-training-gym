"""
generate_security_tasks.py — Security Task Data Generator (Expanded)

Generates training data for 8 vulnerability types in JSONL format.
Output: 500+ samples per type (4000+ total).

Usage:
    python generators/generate_security_tasks.py
    python generators/generate_security_tasks.py --output-dir ./datasets
    python generators/generate_security_tasks.py --samples 1000 --types sql-injection,xss
"""

import argparse
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# Helper: generate variations
# ============================================================================

DB_NAMES = ["db", "app_db", "data", "store", "main", "production", "test_db"]
TABLE_NAMES = ["users", "orders", "products", "items", "accounts", "profiles"]
COLUMN_NAMES = ["username", "email", "id", "name", "price", "category", "status"]
SCENARIOS = ["Web API", "CLI tool", "library function", "Django app", "Flask app", "FastAPI endpoint"]
VULN_FORMATS = ["f-string", ".format()", "string concat (+)", "% formatting"]

def rand_db() -> str: return random.choice(DB_NAMES)
def rand_table() -> str: return random.choice(TABLE_NAMES)
def rand_col() -> str: return random.choice(COLUMN_NAMES)
def rand_scenario() -> str: return random.choice(SCENARIOS)

# ============================================================================
# SQL Injection Generator (500 samples)
# ============================================================================

def gen_sql_injection(i: int) -> Optional[Dict[str, Any]]:
    db = rand_db()
    table = rand_table()
    col = rand_col()
    scenario = rand_scenario()
    fmt = random.choice(VULN_FORMATS)
    param = random.choice(["username", "user_input", "search_term", "password", "email"])

    if fmt == "f-string":
        vuln = f'conn = sqlite3.connect("{db}.sqlite")\nquery = f"SELECT * FROM {table} WHERE {col} = \'{ {{ {param} }} }\'"\nreturn conn.execute(query).fetchall()'
        fix = f'conn = sqlite3.connect("{db}.sqlite")\nquery = "SELECT * FROM {table} WHERE {col} = ?"\nreturn conn.execute(query, ({param},)).fetchall()'
    elif fmt == "string concat (+)":
        vuln = f'conn = sqlite3.connect("{db}.sqlite")\nquery = "SELECT * FROM {table} WHERE {col} = \'" + {param} + "\'"\nreturn conn.execute(query).fetchall()'
        fix = f'conn = sqlite3.connect("{db}.sqlite")\nquery = "SELECT * FROM {table} WHERE {col} = ?"\nreturn conn.execute(query, ({param},)).fetchall()'
    else:
        vuln = f'conn = sqlite3.connect("{db}.sqlite")\nquery = "SELECT * FROM {table} WHERE {col} = \'%s\'" % {param}\nreturn conn.execute(query).fetchall()'
        fix = f'conn = sqlite3.connect("{db}.sqlite")\nquery = "SELECT * FROM {table} WHERE {col} = ?"\nreturn conn.execute(query, ({param},)).fetchall()'

    return {
        "id": f"sql-train-{i:04d}",
        "question": f"修复以下代码中的SQL注入漏洞（{scenario}）：\n```python\n{vuln}\n```",
        "answer": f"```python\n{fix}\n```",
        "source": "training-gym",
        "tags": ["sql-injection", "security", fmt],
        "scenario": scenario,
        "vulnerability_type": fmt,
    }


# ============================================================================
# XSS Generator (500 samples)
# ============================================================================

def gen_xss(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    context = random.choice(["HTML", "JavaScript", "URL", "attribute"])
    dangerous = random.choice([
        f"return render_template_string(\"<div>{'{{ user_input }}'}</div>\", user_input=user_input)",
        f'return f"<h1>Welcome, {{user_input}}</h1>"',
        f"return Template(\"<p>{{{{ name }}}}</p>\").render(name=user_input)",
        f'return """<script>var name = "{{user_input}}";</script>"""',
        f'response.write("<span>" + user_input + "</span>")',
    ])
    safe = random.choice([
        "from markupsafe import escape\nreturn f\"<h1>Welcome, {escape(user_input)}</h1>\"",
        "import html\nreturn f\"<div>{html.escape(user_input)}</div>\"",
        "from flask import escape\nreturn render_template_string(\"<div>{{ user_input|e }}</div>\", user_input=user_input)",
        'return f"<span>{html.escape(user_input)}</span>"',
    ])

    return {
        "id": f"xss-train-{i:04d}",
        "question": f"修复以下代码中的XSS漏洞（{scenario}，{context}上下文）：\n```python\n{dangerous}\n```",
        "answer": f"```python\n{safe}\n```",
        "source": "training-gym",
        "tags": ["xss", "security", context],
        "scenario": scenario,
        "vulnerability_type": "reflected_xss",
    }


# ============================================================================
# Command Injection Generator (500 samples)
# ============================================================================

def gen_command_injection(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    cmd = random.choice(["ls", "cat", "ping", "grep", "find", "whois"])
    pattern = random.choice([
        f'subprocess.run(f"{cmd} {{user_input}}", shell=True)',
        f'os.system(f"{cmd} {{user_input}}")',
        f'subprocess.Popen(f"{cmd} {{user_input}}", shell=True)',
        f'commands.getoutput(f"{cmd} {{user_input}}")',
    ])
    fix = random.choice([
        f'subprocess.run(["{cmd}", user_input], shell=False)',
        f'subprocess.run(["{cmd}", shlex.quote(user_input)])',
        f'import shlex; subprocess.run(["{cmd}"] + shlex.split(user_input))',
    ])

    return {
        "id": f"cmd-train-{i:04d}",
        "question": f"修复以下代码中的命令注入漏洞（{scenario}）：\n```python\nimport subprocess\nimport os\n\ndef execute(user_input):\n    {pattern}\n```",
        "answer": f"```python\nimport subprocess\nimport shlex\n\ndef execute(user_input):\n    {fix}\n```",
        "source": "training-gym",
        "tags": ["command-injection", "security", cmd],
        "scenario": scenario,
        "vulnerability_type": "shell_injection",
    }


# ============================================================================
# SSRF Generator (500 samples)
# ============================================================================

def gen_ssrf(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    param = random.choice(["url", "target_url", "callback", "webhook"])

    vuln = f'def fetch_url({param}):\n    return requests.get({param})'
    fix = f'def fetch_url({param}):\n    from urllib.parse import urlparse\n    parsed = urlparse({param})\n    blocked = ["169.254.", "127.", "10.", "172.16.", "192.168.", "::1", "0.0.0.0"]\n    if any(parsed.hostname.startswith(p) for p in blocked):\n        raise ValueError("Private/internal URL blocked")\n    ALLOWED_SCHEMES = ["https"]\n    if parsed.scheme not in ALLOWED_SCHEMES:\n        raise ValueError(f"Scheme {{parsed.scheme}} not allowed")\n    return requests.get({param})'

    return {
        "id": f"ssrf-train-{i:04d}",
        "question": f"修复以下代码中的SSRF漏洞（{scenario}）：\n```python\nimport requests\n\ndef fetch_data({param}):\n    {vuln}\n```",
        "answer": f"```python\nimport requests\nfrom urllib.parse import urlparse\n\ndef fetch_data({param}):\n    {fix}\n```",
        "source": "training-gym",
        "tags": ["ssrf", "security", "server-side"],
        "scenario": scenario,
        "vulnerability_type": "ssrf",
    }


# ============================================================================
# IDOR Generator (500 samples)
# ============================================================================

def gen_idor(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    resource = random.choice(["order", "user", "invoice", "document", "profile"])

    vuln = f"""@app.route("/api/{resource}/<{resource}_id>")
def get_{resource}({resource}_id):
    return {resource}_db.query(id={resource}_id)"""

    fix = f"""@app.route("/api/{resource}/<{resource}_id>")
def get_{resource}({resource}_id):
    user_id = get_current_user_id()
    item = {resource}_db.query(id={resource}_id)
    if item.owner_id != user_id:
        abort(403, "Access denied")
    return item"""

    return {
        "id": f"idor-train-{i:04d}",
        "question": f"修复以下代码中的IDOR漏洞（{scenario}）：\n```python\nfrom flask import Flask, request, abort\n\napp = Flask(__name__)\n\n{vuln}\n```",
        "answer": f"```python\nfrom flask import Flask, request, abort\n\napp = Flask(__name__)\n\n{fix}\n```",
        "source": "training-gym",
        "tags": ["idor", "security", "access-control"],
        "scenario": scenario,
        "vulnerability_type": "missing_authorization",
    }


# ============================================================================
# XXE Generator (500 samples)
# ============================================================================

def gen_xxe(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    parser = random.choice(["xml.etree.ElementTree", "lxml", "minidom"])

    vuln = f'from {parser} import parse\n\ndef process_xml(xml_data):\n    tree = parse(xml_data)\n    return tree'
    fix = f'from {parser} import parse\n\ndef process_xml(xml_data):\n    parser_instance = parse\n    # Disable external entities\n    import defusedxml\n    from defusedxml import {parser.split(".")[-1]}\n    tree = {parser.split(".")[-1]}.fromstring(xml_data.read())\n    return tree'

    return {
        "id": f"xxe-train-{i:04d}",
        "question": f"修复以下代码中的XXE漏洞（{scenario}）：\n```python\nfrom {parser} import parse\n\ndef read_config(xml_path):\n    {vuln}\n```",
        "answer": f"```python\nfrom defusedxml import {parser.split('.')[-1]}\n\ndef read_config(xml_path):\n    {fix}\n```",
        "source": "training-gym",
        "tags": ["xxe", "security", "xml"],
        "scenario": scenario,
        "vulnerability_type": "external_entity",
    }


# ============================================================================
# Insecure Deserialization Generator (500 samples)
# ============================================================================

def gen_deserialization(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    method = random.choice(["pickle", "yaml", "marshal"])
    safe_method = {"pickle": "json", "yaml": "yaml.safe_load", "marshal": "json"}[method]

    vuln = {
        "pickle": f'data = pickle.loads(user_data)',
        "yaml": f'data = yaml.load(user_data)',
        "marshal": f'data = marshal.loads(user_data)',
    }[method]
    fix = {
        "pickle": f'data = json.loads(user_data)  # Replaced pickle with JSON',
        "yaml": f'data = yaml.safe_load(user_data)',
        "marshal": f'data = json.loads(user_data)  # Replaced marshal with JSON',
    }[method]

    return {
        "id": f"deserialize-train-{i:04d}",
        "question": f"修复以下代码中的反序列化漏洞（{scenario}，使用{method}）：\n```python\nimport {method}\n\ndef load_data(user_data):\n    {vuln}\n    return data\n```",
        "answer": f"```python\nimport json\n\ndef load_data(user_data):\n    {fix}\n    return data\n```",
        "source": "training-gym",
        "tags": ["deserialization", "security", method],
        "scenario": scenario,
        "vulnerability_type": "insecure_deserialization",
    }


# ============================================================================
# Path Traversal Generator (500 samples)
# ============================================================================

def gen_path_traversal(i: int) -> Optional[Dict[str, Any]]:
    scenario = rand_scenario()
    param = random.choice(["filename", "path", "page", "template"])

    vuln = f'def read_file({param}):\n    with open(f"/var/data/{{{param}}}", "r") as f:\n        return f.read()'

    fix = f'import os\n\ndef read_file({param}):\n    safe_dir = os.path.abspath("/var/data/")\n    requested = os.path.abspath(os.path.join(safe_dir, {param}))\n    if not requested.startswith(safe_dir):\n        raise ValueError("Path traversal detected")\n    with open(requested, "r") as f:\n        return f.read()'

    return {
        "id": f"path-train-{i:04d}",
        "question": f"修复以下代码中的路径遍历漏洞（{scenario}）：\n```python\n{vuln}\n```",
        "answer": f"```python\n{fix}\n```",
        "source": "training-gym",
        "tags": ["path-traversal", "security"],
        "scenario": scenario,
        "vulnerability_type": "path_traversal",
    }


# ============================================================================
# Main
# ============================================================================

GENERATORS: Dict[str, Callable] = {
    "sql-injection": gen_sql_injection,
    "xss": gen_xss,
    "command-injection": gen_command_injection,
    "ssrf": gen_ssrf,
    "idor": gen_idor,
    "xxe": gen_xxe,
    "deserialization": gen_deserialization,
    "path-traversal": gen_path_traversal,
}

TASK_TYPES = {
    "sql-injection": "Fix SQL Injection Vulnerability",
    "xss": "Fix Cross-Site Scripting (XSS) Vulnerability",
    "command-injection": "Fix Command Injection Vulnerability",
    "ssrf": "Fix Server-Side Request Forgery (SSRF) Vulnerability",
    "idor": "Fix Insecure Direct Object Reference (IDOR) Vulnerability",
    "xxe": "Fix XML External Entity (XXE) Injection Vulnerability",
    "deserialization": "Fix Insecure Deserialization Vulnerability",
    "path-traversal": "Fix Path Traversal Vulnerability",
}


def generate_dataset(
    vuln_type: str,
    count: int = 500,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generate a dataset for a specific vulnerability type."""
    random.seed(seed)
    generator = GENERATORS.get(vuln_type)
    if not generator:
        raise ValueError(f"Unknown vulnerability type: {vuln_type}. Available: {list(GENERATORS.keys())}")

    samples: List[Dict[str, Any]] = []
    for i in range(1, count + 1):
        sample = generator(i)
        if sample is not None:
            samples.append(sample)
    return samples


def main():
    parser = argparse.ArgumentParser(description="Security Task Data Generator")
    parser.add_argument("--output-dir", type=str, default="./datasets", help="Output directory")
    parser.add_argument("--samples", type=int, default=500, help="Samples per type")
    parser.add_argument(
        "--types", type=str,
        default=",".join(GENERATORS.keys()),
        help=f"Comma-separated types: {', '.join(GENERATORS.keys())}",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_types = [t.strip() for t in args.types.split(",")]

    total = 0
    for vuln_type in selected_types:
        logger.info(f"Generating {args.samples} {vuln_type} samples...")
        samples = generate_dataset(vuln_type, args.samples, args.seed)

        # Split 80/20 train/val
        split = int(len(samples) * 0.8)
        train, val = samples[:split], samples[split:]

        train_file = output_dir / f"{vuln_type}-train.jsonl"
        val_file = output_dir / f"{vuln_type}-val.jsonl"

        with open(train_file, "w", encoding="utf-8") as f:
            for s in train:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        with open(val_file, "w", encoding="utf-8") as f:
            for s in val:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        total += len(samples)
        logger.info(f"  → {train_file} ({len(train)} samples)")
        logger.info(f"  → {val_file} ({len(val)} samples)")

    logger.info(f"✅ Done! Generated {total} total samples across {len(selected_types)} types.")
    logger.info(f"   Output: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
