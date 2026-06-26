"""
train_lora.py — LoRA 微调训练脚本

使用 HuggingFace Transformers + PEFT 对小型语言模型进行 LoRA 微调。
默认使用 GPT-2 模型和内置的数学应用题数据集。

用法:
    python training/train_lora.py
    python training/train_lora.py --model_name distilgpt2 --output_dir ./outputs
    python training/train_lora.py --epochs 5 --lr 3e-4
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    set_seed,
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    PeftModel,
    prepare_model_for_kbit_training,
)

# ============================================================================
# 日志配置
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ============================================================================
# 数据集
# ============================================================================

class MathProblemDataset(Dataset):
    """
    数学应用题数据集 — 将 JSONL 转换为模型输入格式。

    每个样本格式化为:
    "题目: {question}\n答案: {answer}\n"
    """

    def __init__(self, data_path: str, tokenizer, max_length: int = 128):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.samples = []

        logger.info(f"📂 加载数据集: {data_path}")
        with open(data_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                # 格式化为输入-输出对
                text = f"题目: {item['question']}\n答案: {item['answer']}\n"
                self.samples.append(text)

        logger.info(f"✅ 加载了 {len(self.samples)} 个样本")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        text = self.samples[idx]
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": encoding["input_ids"].squeeze(),
        }


# ============================================================================
# 训练函数
# ============================================================================

def train_lora(
    model_name: str = "distilgpt2",
    train_path: str = "tasks/math-word-problems-001/data/train.jsonl",
    val_path: Optional[str] = "tasks/math-word-problems-001/data/val.jsonl",
    output_dir: str = "./outputs",
    num_epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 5e-4,
    max_length: int = 128,
    lora_r: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    seed: int = 42,
    use_cpu: bool = False,
):
    """
    执行 LoRA 微调。

    参数:
        model_name: HuggingFace 模型名称或路径
        train_path: 训练数据 JSONL 路径
        val_path: 验证数据 JSONL 路径（可选）
        output_dir: 输出目录
        num_epochs: 训练轮数
        batch_size: 批次大小
        learning_rate: 学习率
        max_length: 最大序列长度
        lora_r: LoRA 秩
        lora_alpha: LoRA alpha 参数
        lora_dropout: LoRA dropout 率
        seed: 随机种子
        use_cpu: 强制使用 CPU
    """
    # 设置随机种子
    set_seed(seed)

    # 设备检测
    if use_cpu:
        device = "cpu"
        logger.info("💻 使用 CPU")
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if torch.cuda.is_available():
            logger.info(f"🚀 使用 GPU: {torch.cuda.get_device_name(0)}")
        else:
            logger.info("💻 使用 CPU（建议安装 CUDA 加速）")

    # ------------------------------------------------------------------
    # 1. 加载 Tokenizer 和模型
    # ------------------------------------------------------------------
    logger.info(f"📦 加载模型: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float32 if device == "cpu" else torch.float16,
        device_map="auto" if device == "cuda" else None,
    )

    # ------------------------------------------------------------------
    # 2. 配置 LoRA
    # ------------------------------------------------------------------
    logger.info("🔧 配置 LoRA...")

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=["q_proj", "v_proj"],  # GPT-2 注意力层
        bias="none",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ------------------------------------------------------------------
    # 3. 加载数据
    # ------------------------------------------------------------------
    logger.info("📚 加载训练数据...")
    train_dataset = MathProblemDataset(train_path, tokenizer, max_length)

    val_dataset = None
    if val_path and os.path.exists(val_path):
        logger.info("📚 加载验证数据...")
        val_dataset = MathProblemDataset(val_path, tokenizer, max_length)

    # 数据整理器（自动创建 labels = input_ids）
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # 因果语言模型，非掩码语言模型
    )

    # ------------------------------------------------------------------
    # 4. 设置训练参数
    # ------------------------------------------------------------------
    logger.info("⚙️ 配置训练参数...")

    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=1,
        warmup_steps=100,
        learning_rate=learning_rate,
        weight_decay=0.01,
        logging_dir=os.path.join(output_dir, "logs"),
        logging_steps=10,
        evaluation_strategy="steps" if val_dataset else "no",
        eval_steps=50 if val_dataset else None,
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=val_dataset is not None,
        metric_for_best_model="eval_loss" if val_dataset else None,
        fp16=device == "cuda",
        dataloader_num_workers=2,
        report_to="none",  # 不向外部平台报告
        seed=seed,
    )

    # ------------------------------------------------------------------
    # 5. 创建 Trainer 并训练
    # ------------------------------------------------------------------
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    logger.info("🏋️ 开始训练...")
    trainer.train()

    # ------------------------------------------------------------------
    # 6. 保存模型
    # ------------------------------------------------------------------
    final_output = os.path.join(output_dir, "lora_adapter")
    logger.info(f"💾 保存 LoRA adapter 到: {final_output}")
    trainer.model.save_pretrained(final_output)
    tokenizer.save_pretrained(final_output)

    # 同时保存完整模型（可选）
    full_output = os.path.join(output_dir, "full_model")
    logger.info(f"💾 保存完整模型到: {full_output}")
    trainer.model.save_pretrained(full_output)

    logger.info("✅ 训练完成！")

    # 打印训练损失
    if trainer.state.log_history:
        final_loss = None
        for entry in reversed(trainer.state.log_history):
            if "loss" in entry:
                final_loss = entry["loss"]
                break
        if final_loss:
            logger.info(f"📉 最终训练损失: {final_loss:.4f}")

    return final_output


# ============================================================================
# 命令行入口
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="LoRA 微调训练脚本 — AI Training Gym",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--model_name", type=str, default="distilgpt2",
                        help="HuggingFace 模型名称")
    parser.add_argument("--train_path", type=str,
                        default="tasks/math-word-problems-001/data/train.jsonl",
                        help="训练数据路径")
    parser.add_argument("--val_path", type=str,
                        default="tasks/math-word-problems-001/data/val.jsonl",
                        help="验证数据路径")
    parser.add_argument("--output_dir", type=str, default="./outputs",
                        help="输出目录")
    parser.add_argument("--epochs", type=int, default=3,
                        help="训练轮数")
    parser.add_argument("--batch_size", type=int, default=8,
                        help="批次大小")
    parser.add_argument("--lr", type=float, default=5e-4,
                        help="学习率")
    parser.add_argument("--max_length", type=int, default=128,
                        help="最大序列长度")
    parser.add_argument("--lora_r", type=int, default=8,
                        help="LoRA 秩")
    parser.add_argument("--lora_alpha", type=int, default=16,
                        help="LoRA alpha")
    parser.add_argument("--lora_dropout", type=float, default=0.05,
                        help="LoRA dropout")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")
    parser.add_argument("--use_cpu", action="store_true",
                        help="强制使用 CPU")
    parser.add_argument("--eval_only", action="store_true",
                        help="仅评估已有模型（需用 --model_path 指定）")
    parser.add_argument("--model_path", type=str, default=None,
                        help="已有模型路径（用于 eval_only）")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.eval_only:
        # 仅评估模式（暂未实现完整评估逻辑）
        logger.info("评估模式尚未实现完整功能，请使用 scripts/benchmark.py")
        sys.exit(0)

    train_lora(
        model_name=args.model_name,
        train_path=args.train_path,
        val_path=args.val_path,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_length=args.max_length,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        seed=args.seed,
        use_cpu=args.use_cpu,
    )
