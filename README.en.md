🌐 [English](README.en.md) | [中文](README.md)

# 🏋️ AI Training Gym — AI Security Training Dataset 2500+ Samples
### 5 OWASP Categories · LoRA Fine-Tuning · JSONL Format · Open-Source LLM Security Dataset

<p align="center">
  <img src="https://img.shields.io/badge/dataset-2500%2B%20samples-brightgreen?style=flat-square" alt="2500+ samples">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/framework-HuggingFace%20%7C%20PEFT-yellow?style=flat-square" alt="Framework">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome">
</p>

---

## 📋 Introduction

**AI Training Gym** is a **structured training and evaluation platform** for Large Language Models (LLMs). It provides standardized task formats, automated testing frameworks, and LoRA fine-tuning pipelines, enabling developers to quickly build, train, and evaluate AI models for code repair, mathematical reasoning, and security fixes.

### 🎯 Key Features

- ✅ **Standardized Task Format** — YAML-based task definitions + JSONL datasets, easy to extend
- ✅ **Automated Evaluation** — Dedicated test scripts per task type, supporting functional tests, security tests, and exact match metrics
- ✅ **LoRA Fine-Tuning Pipeline** — Complete training scripts based on HuggingFace Transformers + PEFT
- ✅ **Data Generators** — Built-in generators for math problems, SQL injection scenarios, and more
- ✅ **CI Integration** — GitHub Actions automatically runs tests and format validation
- ✅ **HoneyCode Ecosystem Integration** — Supports dataset conversion from honeycode-honeypot format

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                    AI Training Gym                    │
├──────────────┬──────────────┬───────────────────────┤
│  Task Layer  │  Train Layer │  Eval Layer            │
│  task.yaml   │  train_lora  │  pytest + Metrics      │
│  JSONL Data  │  inference   │  benchmark.py          │
├──────────────┴──────────────┴───────────────────────┤
│  Data Generators                                     │
│  generators/generate_*.py                           │
├──────────────────────────────────────────────────────┤
│  Data Conversion                                     │
│  scripts/prepare_dataset.py (honeycode → HF Dataset) │
└──────────────────────────────────────────────────────┘
```

### 🔗 Related Projects

| Project | Description |
|---------|-------------|
| [honeycode-honeypot](https://github.com/zhangjiayang6835-cyber/honeycode-honeypot) | Data collection and annotation platform |
| [eval-engine](https://github.com/zhangjiayang6835-cyber/eval-engine) | Independent evaluation engine for multi-dimensional metrics |

`AI Training Gym` sits between them: **raw data from honeycode-honeypot → convert to training format → train model → submit to eval-engine for deep evaluation**.

---

## 🚀 Quick Start

### Environment Setup

```bash
git clone https://github.com/zhangjiayang6835-cyber/ai-training-gym.git
cd ai-training-gym
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Generate Data

```bash
python generators/generate_math_problems.py
python generators/generate_sql_tasks.py
```

### Run Tests

```bash
pytest tasks/ -v
pytest tasks/sql-injection-fix-001/tests/ -v
```

### Train Model

```bash
python training/train_lora.py
python training/train_lora.py --model_name distilgpt2 --output_dir ./outputs
```

### Inference

```bash
python training/inference.py --adapter_path ./outputs/lora_adapter --prompt "修复此代码："
```

### Benchmark

```bash
python scripts/benchmark.py --model_path ./outputs/lora_adapter
```

---

## 📝 Task Format

Each task follows this structure:

```
tasks/<task-id>/
├── task.yaml            # Task definition
├── tests/               # Test scripts
│   └── test_*.py        # pytest tests
└── data/                # Dataset (optional)
    ├── train.jsonl      # Training set
    └── val.jsonl        # Validation set
```

### task.yaml Specification

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Unique task identifier |
| `title` | string | ✅ | Task title |
| `type` | enum | ✅ | `code_fix` / `generation` / `classification` / `qa` |
| `difficulty` | enum | ✅ | `easy` / `medium` / `hard` |
| `source` | string | ✅ | Data source |
| `languages` | string[] | ✅ | Programming languages |
| `test_cases_path` | string | ❌ | Test case path |
| `evaluation` | object | ✅ | Evaluation config |
| `tags` | string[] | ❌ | Tags |
| `reward_virtual` | integer | ❌ | Virtual reward |
| `description` | string | ✅ | Task description |

Full template at [tasks/task-spec.yaml](tasks/task-spec.yaml).

---

## 🤝 How to Contribute

1. **Fork** this repository
2. **Create a feature branch**: `git checkout -b feat/your-feature`
3. **Add a task**: Create a new task under `tasks/` following `task-spec.yaml`
4. **Write tests**: Each task must have pytest tests
5. **Submit a PR**: Ensure CI passes

### Contribution Checklist

- [ ] Create `tasks/<task-id>/` directory
- [ ] Write `task.yaml` (see template)
- [ ] Write `tests/test_<task-id>.py`
- [ ] Add `data/train.jsonl` and `data/val.jsonl` if needed
- [ ] Run `pytest tasks/<task-id>/tests/ -v` locally

---

## 📄 License

This project is open-sourced under the [MIT License](LICENSE).

---

## 🌟 Acknowledgements

- [HuggingFace Transformers](https://github.com/huggingface/transformers)
- [PEFT](https://github.com/huggingface/peft)
- [HoneyCode Honeypot](https://github.com/zhangjiayang6835-cyber/honeycode-honeypot)
- All contributors ❤️
