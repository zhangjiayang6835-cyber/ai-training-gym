# 数据集格式文档 — AI Training Gym

本文档说明 AI Training Gym 中使用的数据集格式规范。

---

## 📂 目录结构

```
datasets/
├── README.md              # 本文件
├── <dataset_name>/        # HuggingFace Dataset 格式（由 prepare_dataset.py 生成）
│   ├── dataset_dict.json
│   ├── train/
│   │   ├── data-00000-of-00001.arrow
│   │   └── state.json
│   └── validation/
│       ├── data-00000-of-00001.arrow
│       └── state.json
├── <dataset_name>.jsonl   # JSONL 格式（适用于 generators 直接输出）
└── <dataset_name>/
    ├── train.jsonl
    └── val.jsonl
```

---

## 📄 支持的格式

### 1. JSONL 格式（推荐用于任务数据）

每行一个独立的 JSON 对象，使用 `\n` 分隔。

**数学应用题示例:**
```jsonl
{"id": "math-train-001", "question": "小明有 15 个苹果，小红有 23 个苹果，他们一共有多少个苹果？", "answer": 38, "steps": ["小明有 15 个苹果", "小红有 23 个苹果", "15 + 23 = 38"]}
{"id": "math-train-002", "question": "商店有 45 个西瓜，卖出 27 个，还剩多少个？", "answer": 18, "steps": ["商店有 45 个西瓜", "卖出 27 个", "45 - 27 = 18"]}
```

**SQL 注入训练样本示例:**
```jsonl
{"id": "sql-get_user_by_id-fstring", "task_id": "sql-injection-fix-001", "vulnerable_code": "import sqlite3\n\ndef get_user_by_id(user_id):\n    ...", "secure_code": "import sqlite3\n\ndef get_user_by_id(user_id):\n    ...", "vulnerability": "sql_injection", "language": "python"}
```

### 2. HuggingFace Dataset 格式（推荐用于训练）

由 `scripts/prepare_dataset.py` 从 honeycode-honeypot 原始数据生成。
使用 Apache Arrow 列式存储，支持高效随机访问和缓存。

```python
from datasets import load_from_disk

dataset = load_from_disk("datasets/my_dataset")
print(dataset["train"][0])
# {
#     "task_id": "sql-injection-fix-001",
#     "input_text": "def get_user(username):\n    ...",
#     "output_text": "def get_user(username):\n    ...",
#     "reward": 85.0,
#     "language": "python",
#     "difficulty": "medium",
#     "tags": ["sql", "security"]
# }
```

---

## 📋 字段规范

### 任务数据字段（JSONL）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 样本唯一标识 |
| `question` | string | ✅ | 输入问题（generation 任务） |
| `answer` | number/string | ✅ | 标准答案 |
| `steps` | string[] | ❌ | 解题步骤 |
| `vulnerable_code` | string | ❌ | 漏洞代码（code_fix 任务） |
| `secure_code` | string | ❌ | 安全代码（code_fix 任务） |
| `task_id` | string | ❌ | 关联的任务 ID |
| `metadata` | object | ❌ | 元数据 |

### 训练数据字段（HF Dataset）

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `input_text` | string | 模型输入文本 |
| `output_text` | string | 期望输出文本 |
| `reward` | float32 | 奖励分值 |
| `language` | string | 编程语言 |
| `difficulty` | string | 难度 |
| `tags` | sequence[string] | 标签列表 |

---

## 🔄 数据流水线

```
honeycode-honeypot (原始提交)
        │
        ▼
scripts/prepare_dataset.py  ← mapping.yaml (字段映射)
        │
        ▼
HuggingFace Dataset (Arrow 格式)
        │
        ├── train/  →  training/train_lora.py
        └── validation/  →  scripts/benchmark.py


generators/generate_*.py (合成数据)
        │
        ▼
tasks/<task-id>/data/*.jsonl  →  training/train_lora.py
```

---

## ⚡ 使用建议

1. **小数据集**（< 10,000 条）：使用 JSONL 格式，简单直接
2. **大数据集**（≥ 10,000 条）：使用 HuggingFace Dataset 格式，支持内存映射和快速加载
3. **从 honeycode-honeypot 导入**：使用 `prepare_dataset.py` 配合自定义映射配置
4. **合成数据**：使用 `generators/` 下的生成器脚本
