"""
inference.py — LoRA 模型推理脚本

加载训练好的 LoRA adapter 并对测试提示运行推理。

用法:
    python training/inference.py --adapter_path ./outputs/lora_adapter
    python training/inference.py --adapter_path ./outputs/lora_adapter --prompt "题目: 小明有 15 个苹果"
    python training/inference.py --adapter_path ./outputs/lora_adapter --interactive
"""

import argparse
import json
import logging
import sys
from typing import Optional

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


# ============================================================================
# 日志
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# 推理
# ============================================================================

def load_model(
    base_model_name: str,
    adapter_path: str,
    use_cpu: bool = False,
):
    """
    加载基础模型和 LoRA adapter。

    参数:
        base_model_name: 基础模型名称（必须与训练时一致）
        adapter_path: LoRA adapter 路径
        use_cpu: 强制使用 CPU

    返回:
        (model, tokenizer)
    """
    logger.info(f"📦 加载基础模型: {base_model_name}")

    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    tokenizer.pad_token = tokenizer.eos_token

    # 加载基础模型
    device = "cpu" if use_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"💻 设备: {device}")

    if device == "cuda":
        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float32,
        )

    # 加载 LoRA adapter
    logger.info(f"🔧 加载 LoRA adapter: {adapter_path}")
    model = PeftModel.from_pretrained(model, adapter_path)

    model.eval()
    return model, tokenizer, device


def generate_response(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 64,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50,
    do_sample: bool = True,
    device: str = "cpu",
) -> str:
    """
    生成模型回复。

    参数:
        model: 模型
        tokenizer: Tokenizer
        prompt: 输入提示
        max_new_tokens: 最大生成长度
        temperature: 采样温度
        top_p: 核采样参数
        top_k: Top-K 采样参数
        do_sample: 是否采样（False = 贪婪解码）
        device: 设备

    返回:
        str: 生成文本
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            do_sample=do_sample,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # 仅返回新生成的部分
    if generated.startswith(prompt):
        generated = generated[len(prompt):]

    return generated.strip()


def run_interactive(model, tokenizer, device: str):
    """交互式推理模式"""
    print("\n" + "=" * 50)
    print("🤖 AI Training Gym — 交互式推理")
    print("=" * 50)
    print("输入 'quit' 或 'exit' 退出\n")

    while True:
        try:
            prompt = input("📝 请输入题目: ")
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if prompt.lower() in ("quit", "exit", "q"):
            break

        if not prompt.strip():
            continue

        # 确保格式正确
        if not prompt.startswith("题目:"):
            formatted_prompt = f"题目: {prompt}\n答案:"
        else:
            formatted_prompt = prompt + "\n答案:"

        print("🤔 思考中...")
        result = generate_response(model, tokenizer, formatted_prompt, device=device)
        print(f"✅ 答案: {result}\n")


# ============================================================================
# 评估函数
# ============================================================================

def evaluate_on_dataset(
    model,
    tokenizer,
    data_path: str,
    device: str = "cpu",
    max_samples: Optional[int] = None,
) -> dict:
    """
    在数据集上评估模型。

    返回:
        dict: 评估结果（正确率、详细结果等）
    """
    import json
    import re

    correct = 0
    total = 0
    results = []

    with open(data_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break

            item = json.loads(line.strip())
            question = item["question"]
            expected = item["answer"]

            prompt = f"题目: {question}\n答案:"
            generated = generate_response(
                model, tokenizer, prompt,
                max_new_tokens=32,
                temperature=0.3,  # 低温度提高确定性
                do_sample=False,  # 贪婪解码
                device=device,
            )

            # 尝试从生成中提取数字
            numbers = re.findall(r'-?\d+', generated)
            predicted = int(numbers[0]) if numbers else None

            is_correct = (predicted == expected)
            if is_correct:
                correct += 1
            total += 1

            results.append({
                "question": question,
                "expected": expected,
                "predicted": predicted,
                "generated": generated,
                "correct": is_correct,
            })

    accuracy = correct / total if total > 0 else 0
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "results": results,
    }


# ============================================================================
# 入口
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="LoRA 模型推理脚本 — AI Training Gym",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--adapter_path", type=str,
                        default="./outputs/lora_adapter",
                        help="LoRA adapter 路径")
    parser.add_argument("--base_model", type=str, default="distilgpt2",
                        help="基础模型名称")
    parser.add_argument("--prompt", type=str, default=None,
                        help="单次推理提示")
    parser.add_argument("--interactive", action="store_true",
                        help="交互式模式")
    parser.add_argument("--eval_data", type=str, default=None,
                        help="评估数据集路径（JSONL）")
    parser.add_argument("--max_tokens", type=int, default=64,
                        help="最大生成 token 数")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="采样温度")
    parser.add_argument("--use_cpu", action="store_true",
                        help="强制使用 CPU")
    parser.add_argument("--max_samples", type=int, default=None,
                        help="评估时最大样本数")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 加载模型
    model, tokenizer, device = load_model(
        base_model_name=args.base_model,
        adapter_path=args.adapter_path,
        use_cpu=args.use_cpu,
    )

    # 交互式模式
    if args.interactive:
        run_interactive(model, tokenizer, device)
        sys.exit(0)

    # 单次推理
    if args.prompt:
        formatted_prompt = args.prompt
        if not formatted_prompt.startswith("题目:"):
            formatted_prompt = f"题目: {formatted_prompt}\n答案:"
        result = generate_response(
            model, tokenizer, formatted_prompt,
            max_new_tokens=args.max_tokens,
            temperature=args.temperature,
            device=device,
        )
        print(f"📝 输入: {args.prompt}")
        print(f"✅ 输出: {result}")
        sys.exit(0)

    # 数据集评估
    if args.eval_data:
        logger.info(f"📊 评估数据集: {args.eval_data}")
        eval_result = evaluate_on_dataset(
            model, tokenizer, args.eval_data,
            device=device, max_samples=args.max_samples,
        )
        print(f"\n{'='*40}")
        print(f"📊 评估结果")
        print(f"{'='*40}")
        print(f"  正确: {eval_result['correct']}/{eval_result['total']}")
        print(f"  准确率: {eval_result['accuracy']:.2%}")
        print(f"{'='*40}")

        # 打印错误案例
        errors = [r for r in eval_result["results"] if not r["correct"]]
        if errors:
            print(f"\n⚠️  错误案例 ({len(errors)}):")
            for e in errors[:5]:
                print(f"  题目: {e['question']}")
                print(f"  期望: {e['expected']}, 预测: {e['predicted']}")
                print()
        sys.exit(0)

    # 没有指定任何模式，打印帮助
    print("请指定运行模式:")
    print("  --interactive    交互式模式")
    print("  --prompt TEXT    单次推理")
    print("  --eval_data PATH 数据集评估")
    print("  -h               查看完整帮助")
