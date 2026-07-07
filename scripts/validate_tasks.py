#!/usr/bin/env python3
"""
validate_tasks.py — 验证任务格式有效性

检查 tasks/ 下所有子任务的 task.yaml 文件：
- 文件是否存在
- YAML 是否可解析
- 必填字段是否齐全
- 类型和难度是否在允许范围内
- 是否至少定义了一个评测指标

退出码：
  0 — 全部通过
  1 — 有错误
"""

import os
import sys
import yaml


TASKS_DIR = "tasks"

REQUIRED_FIELDS = ["id", "title", "type", "difficulty", "source", "evaluation", "description"]
VALID_TYPES = ["code_fix", "generation", "classification", "qa"]
VALID_DIFFICULTIES = ["easy", "medium", "hard"]


def validate_all() -> list[str]:
    errors: list[str] = []

    if not os.path.isdir(TASKS_DIR):
        errors.append(f"任务目录不存在: {TASKS_DIR}")
        return errors

    for task_id in sorted(os.listdir(TASKS_DIR)):
        task_path = os.path.join(TASKS_DIR, task_id)
        yaml_path = os.path.join(task_path, "task.yaml")

        if not os.path.isdir(task_path):
            continue
        if not os.path.exists(yaml_path):
            errors.append(f"{task_id}: 缺少 task.yaml")
            continue

        with open(yaml_path, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"{task_id}: YAML 解析错误 - {e}")
                continue

        if not isinstance(config, dict):
            errors.append(f"{task_id}: task.yaml 内容不是有效的映射")
            continue

        # 验证必填字段
        for field in REQUIRED_FIELDS:
            if field not in config:
                errors.append(f'{task_id}: 缺少必填字段 "{field}"')

        # 验证类型
        if config.get("type") not in VALID_TYPES:
            errors.append(f'{task_id}: 无效的任务类型 "{config.get("type")}"')

        # 验证难度
        if config.get("difficulty") not in VALID_DIFFICULTIES:
            errors.append(f'{task_id}: 无效的难度 "{config.get("difficulty")}"')

        # 验证评测指标
        metrics = config.get("evaluation", {}).get("metrics", [])
        if not metrics:
            errors.append(f"{task_id}: 必须至少定义一个评测指标")

    return errors


def main():
    errors = validate_all()

    if errors:
        print("[FAIL] 格式验证失败:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("[PASS] 所有任务格式验证通过")


if __name__ == "__main__":
    main()
