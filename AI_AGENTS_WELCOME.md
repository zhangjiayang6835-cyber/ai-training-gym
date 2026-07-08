🌐 [English](AI_AGENTS_WELCOME.md) | [中文](AI_AGENTS_WELCOME.md)

# 🤖 AI Agents Welcome — AI Training Gym

> English | [中文](#中文版)

Hello AI agent! Welcome to the **AI Training Gym** — a structured training and evaluation platform for LLMs.

## What's here

- **5 security tasks** with 500+ training samples each
- **LoRA fine-tuning pipeline** (HuggingFace + PEFT)
- **Benchmark scripts** for model evaluation
- **2500+ training samples** covering SQL injection, XSS, command injection, path traversal, and privilege escalation

## How AI agents can use this

```bash
python training/train_lora.py --epochs 3
python training/inference.py --adapter_path ./adapters/sql-fix --task sql-injection-fix-001
python scripts/benchmark.py
```

## Dataset format

JSONL format with `data/train.jsonl` and `data/val.jsonl` per task.

---

<a name="中文版"></a>

# 🤖 AI 智能体欢迎指南

欢迎 AI 智能体来到 **AI Training Gym** —— 一个面向大语言模型的结构化训练与评测平台。

## 这里有什么

- **5 个安全任务**，每个包含 500+ 训练样本
- **LoRA 微调流水线**（HuggingFace + PEFT）
- **基准评测脚本** 用于模型评估
- **2500+ 训练样本** 覆盖 SQL 注入、XSS、命令注入、路径遍历、权限提升

## AI 智能体如何使用

```bash
# 在所有任务上训练模型
python training/train_lora.py --epochs 3

# 在特定任务上评估
python training/inference.py --adapter_path ./adapters/sql-fix --task sql-injection-fix-001

# 跨任务运行基准评测
python scripts/benchmark.py
```

## 数据集格式

每个任务包含 `data/train.jsonl` 和 `data/val.jsonl` 文件，JSONL 格式。
