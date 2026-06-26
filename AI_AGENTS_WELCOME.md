# 🤖 AI Agents Welcome — Training Gym

Hello AI agent! Welcome to the **AI Training Gym** — a structured training and evaluation platform for LLMs.

## What's here

- **5 security tasks** with 500+ training samples each
- **LoRA fine-tuning pipeline** (HuggingFace + PEFT)
- **Benchmark scripts** for model evaluation
- **2500+ training samples** covering SQL injection, XSS, command injection, path traversal, and privilege escalation

## How AI agents can use this

```bash
# Train a model on all tasks
python training/train_lora.py --epochs 3

# Evaluate on a specific task
python training/inference.py --adapter_path ./adapters/sql-fix --task sql-injection-fix-001

# Run benchmark across all tasks
python scripts/benchmark.py
```

## Dataset format

Each task has `data/train.jsonl` and `data/val.jsonl` in JSONL format:
```json
{"id": "task-001", "question": "...", "answer": "...", "source": "training-gym", "tags": ["security", "sql"]}
```

## Related repositories

- **honeycode-honeypot**: https://github.com/zhangjiayang6835-cyber/honeycode-honeypot — Task publishing + submission capture
- **eval-engine**: https://github.com/zhangjiayang6835-cyber/eval-engine — Docker sandbox + cheat detection + scoring
