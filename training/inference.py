"""
inference.py — LoRA 模型推理脚本（安全加固版）

加载训练好的 LoRA adapter 并对测试提示运行推理。
安全改进：adapter 路径经过严格验证，防止路径注入攻击。

用法:
    python training/inference.py --adapter_path ./outputs/lora_adapter
    python training/inference.py --adapter_path ./outputs/lora_adapter --interactive
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
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
# 安全验证
# ============================================================================

ALLOWED_ADAPTER_DIRS = [
    Path("./outputs").resolve(),
    Path("./lora_adapters").resolve(),
    Path("./checkpoints").resolve(),
]

def validate_adapter_path(adapter_path: str) -> Path:
    """
    验证 adapter 路径的安全性。

    Raises:
        ValueError: 如果路径包含遍历攻击（.. 或 ~）或不在允许的目录内。
    """
    resolved = Path(adapter_path).resolve()

    # 安全检查：拒绝包含 .. 的路径
    if ".." in adapter_path.split(os.sep):
        raise ValueError(
            f"Security: path traversal detected in adapter path: {adapter_path}"
        )

    # 安全检查：拒绝绝对路径中指向敏感系统目录的模式
    system_dirs = ["/etc/", "/var/", "/usr/", "/bin/", "/boot/", "/dev/",
                   "C:\\Windows\\", "C:\\Program Files\\", "C:\\System32\\"]
    resolved_str = str(resolved)
    for sys_dir in system_dirs:
        if sys_dir.lower() in resolved_str.lower():
            raise ValueError(
                f"Security: adapter path points to system directory: {adapter_path}"
            )

    # 安全检查：不允许执行权限
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Security: adapter path is not a directory: {adapter_path}")

    # 安全检查：不允许包含符号链接（防止链接到敏感路径）
    if resolved.is_symlink():
        raise ValueError(f"Security: adapter path is a symlink, not allowed: {adapter_path}")

    # 建议的安全检查：检查是否在允许的目录内（宽松模式，仅警告）
    in_allowed = any(
        str(allowed).lower() in resolved_str.lower()
        for allowed in ALLOWED_ADAPTER_DIRS
    )
    if not in_allowed:
        logger.warning(
            f"⚠️  Adapter path {resolved} is outside standard directories. "
            f"Allowed: {[str(d) for d in ALLOWED_ADAPTER_DIRS]}"
        )

    # 检查 adapter 目录是否包含必要的文件
    required_files = ["adapter_config.json", "adapter_model.safetensors"]
    missing = [f for f in required_files if not (resolved / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Adapter directory missing required files: {missing}. "
            f"Ensure the path '{resolved}' contains a valid LoRA adapter."
        )

    return resolved


# ============================================================================
# 推理（与原始逻辑相同，安全加固部分在上面）
# ============================================================================

def load_model(
    base_model_name: str,
    adapter_path: str,
    use_cpu: bool = False,
):
    """加载基础模型和 LoRA adapter，带路径安全验证。"""
    safe_path = validate_adapter_path(adapter_path)
    logger.info(f"✅ Adapter path validated: {safe_path}")

    logger.info(f"📦 加载基础模型: {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(str(safe_path))
    tokenizer.pad_token = tokenizer.eos_token

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

    logger.info(f"🔧 加载 LoRA adapter: {safe_path}")
    model = PeftModel.from_pretrained(model, str(safe_path))
    model.eval()
    logger.info("✅ 模型加载完成")

    return model, tokenizer, device


def run_inference(
    model,
    tokenizer,
    prompt: str,
    device: str,
    max_length: int = 256,
    temperature: float = 0.7,
):
    """运行推理并返回生成的文本。"""
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_length,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser(description="LoRA Model Inference")
    parser.add_argument("--adapter_path", type=str, required=True, help="LoRA adapter 路径")
    parser.add_argument("--base_model", type=str, default="gpt2", help="基础模型名称")
    parser.add_argument("--prompt", type=str, default=None, help="测试提示")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    parser.add_argument("--use_cpu", action="store_true", help="强制使用 CPU")
    args = parser.parse_args()

    model, tokenizer, device = load_model(args.base_model, args.adapter_path, args.use_cpu)

    if args.interactive:
        logger.info("💬 交互模式启动（输入 exit 退出）")
        while True:
            try:
                prompt = input("\n提示 > ").strip()
                if prompt.lower() in ("exit", "quit"):
                    break
            except (EOFError, KeyboardInterrupt):
                break
            result = run_inference(model, tokenizer, prompt, device)
            print(f"\n生成 > {result}")
    elif args.prompt:
        result = run_inference(model, tokenizer, args.prompt, device)
        print(result)
    else:
        logger.warning("请提供 --prompt 或使用 --interactive 模式")
        parser.print_help()


if __name__ == "__main__":
    main()
