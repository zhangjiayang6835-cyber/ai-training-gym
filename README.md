# 🏋️ AI训练场 (AI Training Gym)

<p align="center">
  <img src="https://img.shields.io/badge/status-active--development-blueviolet?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/framework-HuggingFace%20%7C%20PEFT-yellow?style=flat-square" alt="Framework">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome">
</p>

<p align="center">
  <b>中文</b> | <a href="#english">English</a>
</p>

---

## 📋 项目简介

**AI训练场（AI Training Gym）** 是一个面向大语言模型（LLM）的**结构化训练与评测平台**。它提供标准化的任务格式、自动化的测试框架、以及 LoRA 微调流水线，帮助开发者快速构建、训练和评估 AI 模型的代码修复、数学推理、安全修复等能力。

### 🎯 核心特性

- ✅ **标准化任务格式** — 基于 YAML 的任务定义 + JSONL 数据集，易于扩展
- ✅ **自动化评测** — 每种任务类型配备专用测试脚本，支持功能测试、安全测试、精确匹配等多种指标
- ✅ **LoRA 微调流水线** — 基于 HuggingFace Transformers + PEFT 的完整训练脚本
- ✅ **数据生成器** — 内置数学问题、SQL 注入场景等数据生成工具
- ✅ **CI 集成** — GitHub Actions 自动运行测试和格式校验
- ✅ **与 HoneyCode 生态集成** — 支持从 honeycode-honeypot 格式转换数据集

---

## 🏗️ 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    AI Training Gym                    │
├──────────────┬──────────────┬───────────────────────┤
│  任务定义层    │  训练引擎层    │   评测引擎层           │
│  task.yaml   │  train_lora  │   pytest + 指标计算    │
│  JSONL 数据   │  inference   │   benchmark.py        │
├──────────────┴──────────────┴───────────────────────┤
│  数据生成器                                          │
│  generators/generate_*.py                           │
├──────────────────────────────────────────────────────┤
│  数据转换层                                          │
│  scripts/prepare_dataset.py (honeycode → HF Dataset) │
└──────────────────────────────────────────────────────┘
```

### 🔗 相关项目

| 项目 | 说明 |
|------|------|
| [honeycode-honeypot](https://github.com/your-org/honeycode-honeypot) | 数据采集与标注平台，capture 原始提交数据 |
| [eval-engine](https://github.com/your-org/eval-engine) | 独立评测引擎，支持多维度指标计算与报告生成 |

`AI Training Gym` 位于两者之间：**从 honeycode-honeypot 获取原始数据 → 转换为标准训练格式 → 训练模型 → 提交到 eval-engine 进行深度评测**。

---

## 🚀 快速开始

### 环境准备

```bash
# 克隆仓库
git clone https://github.com/your-org/ai-training-gym.git
cd ai-training-gym

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 生成数据

```bash
# 生成数学问题数据
python generators/generate_math_problems.py

# 生成 SQL 注入训练样本
python generators/generate_sql_tasks.py
```

### 运行测试

```bash
# 运行所有任务测试
pytest tasks/ -v

# 运行特定任务测试
pytest tasks/sql-injection-fix-001/tests/ -v
```

### 训练模型

```bash
# LoRA 微调（默认使用 GPT-2）
python training/train_lora.py

# 使用指定模型
python training/train_lora.py --model_name distilgpt2 --output_dir ./outputs
```

### 运行推理

```bash
python training/inference.py --adapter_path ./outputs/lora_adapter --prompt "修复此代码："
```

### 基准评测

```bash
python scripts/benchmark.py --model_path ./outputs/lora_adapter
```

---

## 📝 任务格式文档

每个任务包含以下结构：

```
tasks/<task-id>/
├── task.yaml            # 任务定义文件
├── tests/               # 测试脚本目录
│   └── test_*.py        # pytest 测试
└── data/                # 数据集目录（可选）
    ├── train.jsonl      # 训练集
    └── val.jsonl        # 验证集
```

### task.yaml 规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 任务唯一标识 |
| `title` | string | ✅ | 任务标题 |
| `type` | enum | ✅ | 任务类型：`code_fix` / `generation` / `classification` / `qa` |
| `difficulty` | enum | ✅ | 难度：`easy` / `medium` / `hard` |
| `source` | string | ✅ | 数据来源 |
| `languages` | string[] | ✅ | 编程语言列表 |
| `test_cases_path` | string | ❌ | 测试用例路径 |
| `evaluation` | object | ✅ | 评测配置 |
| `tags` | string[] | ❌ | 标签 |
| `reward_virtual` | integer | ❌ | 虚拟奖励分值 |
| `description` | string | ✅ | 任务描述（中文） |

完整模板见 [tasks/task-spec.yaml](tasks/task-spec.yaml)。

---

## 🤝 如何贡献

我们欢迎任何形式的贡献！请遵循以下步骤：

1. **Fork** 本仓库
2. **创建特性分支**：`git checkout -b feat/your-feature`
3. **添加任务**：按照 `task-spec.yaml` 模板在 `tasks/` 下创建新任务
4. **编写测试**：每个任务必须有对应的 pytest 测试
5. **提交 PR**：确保 CI 通过

### 贡献任务清单

- [ ] 创建 `tasks/<task-id>/` 目录
- [ ] 编写 `task.yaml`（参考模板）
- [ ] 编写 `tests/test_<task-id>.py`
- [ ] 如果需要，添加 `data/train.jsonl` 和 `data/val.jsonl`
- [ ] 本地运行 `pytest tasks/<task-id>/tests/ -v` 通过

---

## 📄 许可

本项目基于 [MIT License](LICENSE) 开源。

```
MIT License

Copyright (c) 2025 AI Training Gym

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

---

## 🌟 致谢

- [HuggingFace Transformers](https://github.com/huggingface/transformers)
- [PEFT](https://github.com/huggingface/peft)
- [HoneyCode Honeypot](https://github.com/your-org/honeycode-honeypot)
- 所有贡献者 ❤️

---

<a name="english"></a>
## English Summary

**AI Training Gym** is a structured training & evaluation platform for LLMs. It standardizes task definitions, automates testing, and provides LoRA fine-tuning pipelines. Built to work with honeycode-honeypot (data collection) and eval-engine (deep evaluation).

