"""
benchmark.py — 模型基准评测脚本

对训练好的模型在所有任务上运行评测，输出得分表。

用法:
    python scripts/benchmark.py
    python scripts/benchmark.py --model_path ./outputs/lora_adapter
    python scripts/benchmark.py --model_path ./outputs/lora_adapter --tasks math
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


# ============================================================================
# 日志
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# 评测任务注册
# ============================================================================

TASKS = {
    "math-word-problems-001": {
        "path": "tasks/math-word-problems-001",
        "type": "generation",
        "test_dir": "tests",
        "data_file": "data/val.jsonl",
        "weight": 1.0,
    },
    "sql-injection-fix-001": {
        "path": "tasks/sql-injection-fix-001",
        "type": "code_fix",
        "test_dir": "tests",
        "data_file": None,
        "weight": 1.0,
    },
}


# ============================================================================
# 评测函数
# ============================================================================

def run_pytest(task_path: str, test_dir: str) -> Tuple[bool, str, Dict]:
    """
    在指定任务的测试目录下运行 pytest。

    返回:
        (passed, output, stats)
    """
    test_path = os.path.join(task_path, test_dir)
    if not os.path.exists(test_path):
        return False, f"测试目录不存在: {test_path}", {}

    logger.info(f"🔍 运行 pytest: {test_path}")

    result = subprocess.run(
        ["python", "-m", "pytest", test_path, "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # 解析输出
    passed = result.returncode == 0
    output = result.stdout + result.stderr

    # 尝试解析统计信息
    stats = _parse_pytest_output(output)

    return passed, output, stats


def _parse_pytest_output(output: str) -> Dict:
    """解析 pytest 输出，提取测试统计"""
    stats = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "total": 0,
    }

    import re

    # 匹配 "X passed, Y failed" 模式
    patterns = [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+skipped", "skipped"),
        (r"(\d+)\s+error", "errors"),
    ]

    for pattern, key in patterns:
        match = re.search(pattern, output)
        if match:
            stats[key] = int(match.group(1))

    stats["total"] = sum(stats.values())
    return stats


def run_exact_match_evaluation(
    data_path: str,
    model_path: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    运行精确匹配评测（适用于 generation 类型任务）。

    如果提供了 model_path，使用模型进行推理。
    否则，使用简单的规则引擎（用于测试框架本身）。
    """
    import re

    if not os.path.exists(data_path):
        return 0.0, {"error": f"数据文件不存在: {data_path}"}

    correct = 0
    total = 0
    details = []

    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line.strip())
            expected = item["answer"]

            if model_path:
                # TODO: 使用模型进行推理
                predicted = None
            else:
                # 简单规则引擎（仅用于测试）
                predicted = _rule_based_solve(item["question"])

            is_correct = (str(predicted) == str(expected))
            if is_correct:
                correct += 1
            total += 1

            details.append({
                "question": item["question"][:30] + "...",
                "expected": expected,
                "predicted": predicted,
                "correct": is_correct,
            })

    accuracy = correct / total if total > 0 else 0
    return accuracy, {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "details": details,
    }


def _rule_based_solve(question: str) -> Optional[int]:
    """规则引擎数学求解（中英文兼容，仅用于测试基准测试框架）"""
    import re
    nums = [int(n) for n in re.findall(r'\d+', question)]
    if len(nums) < 2:
        return None

    q = question.lower()
    # 除法：平均分 / share / divide equally
    if "平均分" in q or "share" in q or "divided" in q or "equally" in q:
        return nums[0] // nums[1] if nums[1] else None
    # 乘法：倍 / times as many / times
    if "倍" in q or "times as many" in q or "times" in q:
        return nums[0] * nums[1]
    # 减法：还剩 / fewer / left / less
    if "还剩" in q or "fewer" in q or " left" in q or "less" in q:
        return nums[0] - nums[1]
    # 加法：一共 / more / gets / buys
    if "一共" in q or "more" in q or "gets" in q or "buys" in q:
        return nums[0] + nums[1]
    return None


# ============================================================================
# 评分报告
# ============================================================================

def print_score_table(results: Dict[str, Dict]):
    """打印格式化的得分表"""
    print("\n" + "=" * 72)
    print("📊 AI Training Gym — 基准评测报告")
    print("=" * 72)

    print(f"\n{'任务':<30} {'类型':<15} {'得分':<10} {'详情':<15}")
    print("-" * 72)

    total_score = 0.0
    total_weight = 0.0

    for task_id, result in sorted(results.items()):
        task_info = TASKS.get(task_id, {})
        task_type = task_info.get("type", "unknown")
        weight = task_info.get("weight", 1.0)

        passed = result.get("passed", False)
        stats = result.get("stats", {})
        accuracy = result.get("accuracy", 0.0)

        if task_type == "code_fix":
            score = 100.0 if passed else 0.0
            detail = f"✅ {stats.get('passed', 0)}/{stats.get('total', 0)} 通过" if passed else f"❌ {stats.get('failed', 0)} 失败"
        elif task_type == "generation":
            score = accuracy * 100
            detail = f"🎯 {result.get('correct', 0)}/{result.get('total', 0)} 正确"
        else:
            score = 0.0
            detail = "未知类型"

        weighted_score = score * weight
        total_score += weighted_score
        total_weight += weight

        task_label = f"{task_id[:28]}" if len(task_id) > 28 else task_id
        print(f"{task_label:<30} {task_type:<15} {score:<8.1f} {detail:<15}")

    print("-" * 72)

    # 加权总分
    if total_weight > 0:
        final_score = total_score / total_weight
    else:
        final_score = 0.0

    print(f"{'综合得分':<30} {'':<15} {final_score:<8.1f} / 100")
    print("=" * 72)

    return final_score


# ============================================================================
# 主函数
# ============================================================================

def run_benchmark(
    model_path: Optional[str] = None,
    task_filter: Optional[str] = None,
) -> float:
    """
    运行所有任务的基准评测。

    参数:
        model_path: 模型路径（可选，未提供时只运行任务测试）
        task_filter: 任务 ID 过滤（可选）

    返回:
        float: 综合得分
    """
    results = {}

    for task_id, task_info in TASKS.items():
        if task_filter and task_filter not in task_id:
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"📋 评测任务: {task_id}")
        logger.info(f"{'='*50}")

        task_path = task_info["path"]
        task_type = task_info["type"]

        result = {"task_id": task_id, "type": task_type}

        if task_type == "code_fix":
            # 运行 pytest 测试
            passed, output, stats = run_pytest(task_path, task_info["test_dir"])
            result["passed"] = passed
            result["output"] = output
            result["stats"] = stats

            if passed:
                logger.info(f"✅ {task_id}: 全部通过 ({stats.get('total', 0)} 个测试)")
            else:
                logger.warning(f"❌ {task_id}: 有 {stats.get('failed', 0)} 个测试失败")

        elif task_type == "generation":
            # 运行精确匹配评测
            data_path = os.path.join(task_path, task_info["data_file"])
            accuracy, eval_info = run_exact_match_evaluation(data_path, model_path)
            result["accuracy"] = accuracy
            result["correct"] = eval_info.get("correct", 0)
            result["total"] = eval_info.get("total", 0)
            result["eval_info"] = eval_info

            logger.info(f"🎯 {task_id}: 准确率 {accuracy:.2%} "
                        f"({eval_info.get('correct', 0)}/{eval_info.get('total', 0)})")

        results[task_id] = result

    # 打印得分表
    print_score_table(results)

    return results


# ============================================================================
# 入口
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="基准评测脚本 — AI Training Gym",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--model_path", type=str, default=None,
                        help="模型路径（可选）")
    parser.add_argument("--tasks", type=str, default=None,
                        help="任务过滤（例如: math, sql）")
    parser.add_argument("--output", type=str, default=None,
                        help="结果输出路径（JSON）")
    parser.add_argument("--ci", action="store_true",
                        help="CI 模式（简化输出）")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logger.info("🏋️ AI Training Gym — 基准评测")
    logger.info(f"模型路径: {args.model_path or '（未指定，仅运行任务测试）'}")

    results = run_benchmark(
        model_path=args.model_path,
        task_filter=args.tasks,
    )

    # 保存结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 结果已保存: {args.output}")

    # 计算退出码（CI 模式）
    if args.ci:
        all_passed = all(
            r.get("passed", False) or r.get("accuracy", 0) >= 0.5
            for r in results.values()
        )
        sys.exit(0 if all_passed else 1)
