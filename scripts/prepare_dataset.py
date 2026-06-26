"""
prepare_dataset.py — 数据转换脚本

将 honeycode-honeypot 格式的原始提交数据转换为 HuggingFace Dataset 格式。
支持自定义映射规则。

用法:
    python scripts/prepare_dataset.py --input data/raw_submissions.jsonl --output datasets/my_dataset
    python scripts/prepare_dataset.py --input data/raw_submissions.jsonl --output datasets/my_dataset --mapping configs/mapping.yaml
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Any

import yaml
import pandas as pd
from datasets import Dataset, DatasetDict, Features, Value, Sequence


# ============================================================================
# 日志
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# HoneyCode 格式定义
# ============================================================================

# HoneyCode honeypot 原始数据格式示例:
#
# {
#   "submission_id": "sub_001",
#   "task_id": "sql-injection-fix-001",
#   "user_id": "user_42",
#   "timestamp": "2025-01-15T10:30:00Z",
#   "code": "def get_user(username):\n    ...",
#   "expected_code": "def get_user(username):\n    ...",
#   "passed": true,
#   "score": 85.0,
#   "evaluation": {
#     "functional": 1.0,
#     "security": 0.8,
#     "code_quality": 0.75
#   },
#   "metadata": {
#     "language": "python",
#     "difficulty": "medium",
#     "tags": ["sql", "security"]
#   }
# }


# ============================================================================
# 默认映射配置
# ============================================================================

DEFAULT_MAPPING = {
    # HoneyCode 字段 → 训练数据字段
    "fields": {
        "task_id": "task_id",
        "code": "input_text",
        "expected_code": "output_text",
        "score": "reward",
        "metadata.language": "language",
        "metadata.difficulty": "difficulty",
        "metadata.tags": "tags",
    },
    # 数据集特征定义
    "features": {
        "task_id": "string",
        "input_text": "string",
        "output_text": "string",
        "reward": "float32",
        "language": "string",
        "difficulty": "string",
        "tags": "sequence_string",
    },
    # 过滤条件（仅包含符合条件的样本）
    "filter": {
        "passed": True,  # 只包含通过的提交
    },
    # 训练/验证集分割
    "split": {
        "train_ratio": 0.8,
        "seed": 42,
    },
}


# ============================================================================
# 数据转换
# ============================================================================

def _nested_get(obj: Dict, path: str, default: Any = None) -> Any:
    """通过点分隔路径获取嵌套字典的值"""
    keys = path.split(".")
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def convert_submissions(
    submissions: List[Dict],
    mapping: Dict,
) -> pd.DataFrame:
    """
    将 honeycode 提交数据转换为训练数据格式。

    参数:
        submissions: honeycode-honeypot 格式的提交列表
        mapping: 字段映射配置

    返回:
        pd.DataFrame: 转换后的数据
    """
    records = []

    # 过滤条件
    filter_config = mapping.get("filter", {})

    for sub in submissions:
        # 应用过滤
        skip = False
        for key, expected_value in filter_config.items():
            actual = _nested_get(sub, key)
            if actual != expected_value:
                skip = True
                break

        if skip:
            continue

        # 字段映射
        record = {}
        for honey_field, train_field in mapping.get("fields", {}).items():
            value = _nested_get(sub, honey_field)
            record[train_field] = value

        records.append(record)

    logger.info(f"转换了 {len(records)} 条记录（过滤前 {len(submissions)} 条）")
    return pd.DataFrame(records)


def save_as_hf_dataset(
    df: pd.DataFrame,
    output_path: str,
    features: Dict,
    split_config: Dict,
):
    """
    将 DataFrame 保存为 HuggingFace Dataset 格式。

    参数:
        df: 转换后的 DataFrame
        output_path: 输出目录
        features: 数据集特征定义
        split_config: 分割配置
    """
    os.makedirs(output_path, exist_ok=True)

    # 构建特征定义
    hf_features = {}
    for field, field_type in features.items():
        if field not in df.columns:
            continue
        if field_type == "string":
            hf_features[field] = Value("string")
        elif field_type == "float32":
            hf_features[field] = Value("float32")
        elif field_type == "int32":
            hf_features[field] = Value("int32")
        elif field_type == "sequence_string":
            hf_features[field] = Sequence(Value("string"))
        else:
            hf_features[field] = Value("string")

    # 转换为 HF Dataset
    dataset = Dataset.from_pandas(df, features=Features(hf_features))

    # 分割训练/验证集
    train_ratio = split_config.get("train_ratio", 0.8)
    seed = split_config.get("seed", 42)

    split = dataset.train_test_split(
        train_ratio=train_ratio,
        seed=seed,
    )

    dataset_dict = DatasetDict({
        "train": split["train"],
        "validation": split["test"],
    })

    # 保存
    dataset_dict.save_to_disk(output_path)
    logger.info(f"💾 数据集已保存到: {output_path}")
    logger.info(f"  训练集: {len(dataset_dict['train'])} 条")
    logger.info(f"  验证集: {len(dataset_dict['validation'])} 条")

    # 同时保存为 JSONL（方便查看）
    for split_name in ["train", "validation"]:
        jsonl_path = os.path.join(output_path, f"{split_name}.jsonl")
        dataset_dict[split_name].to_json(jsonl_path)
        logger.info(f"  JSONL: {jsonl_path}")

    return dataset_dict


# ============================================================================
# 从 YAML 加载映射
# ============================================================================

def load_mapping(mapping_path: Optional[str]) -> Dict:
    """
    加载映射配置文件。

    参数:
        mapping_path: YAML 文件路径，如果为 None 则使用默认映射

    返回:
        Dict: 映射配置
    """
    if mapping_path and os.path.exists(mapping_path):
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping = yaml.safe_load(f)
        logger.info(f"📋 加载映射配置: {mapping_path}")
        return mapping

    logger.info("📋 使用默认映射配置")
    return DEFAULT_MAPPING.copy()


# ============================================================================
# 示例映射配置文件
# ============================================================================

MAPPING_EXAMPLE = """# honeycode-honeypot → HuggingFace Dataset 映射配置
# 定义字段映射、特征类型、过滤条件和数据集分割

fields:
  # honeycode 原始字段    训练数据字段
  task_id:                "task_id"
  code:                   "input_text"
  expected_code:          "output_text"
  score:                  "reward"
  metadata.language:      "language"
  metadata.difficulty:    "difficulty"
  metadata.tags:          "tags"

features:
  task_id:        "string"
  input_text:     "string"
  output_text:    "string"
  reward:         "float32"
  language:       "string"
  difficulty:     "string"
  tags:           "sequence_string"

filter:
  passed: true          # 只包含通过的提交

split:
  train_ratio: 0.8      # 训练集比例
  seed: 42              # 随机种子
"""


# ============================================================================
# 入口
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="数据转换脚本 — honeycode → HuggingFace Dataset",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--input", "-i", type=str, required=True,
                        help="输入文件路径（honeycode JSONL 格式）")
    parser.add_argument("--output", "-o", type=str, required=True,
                        help="输出目录")
    parser.add_argument("--mapping", "-m", type=str, default=None,
                        help="映射配置 YAML 文件路径")
    parser.add_argument("--generate-mapping", action="store_true",
                        help="生成示例映射配置文件")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 生成示例映射配置
    if args.generate_mapping:
        example_path = "configs/mapping.yaml"
        os.makedirs("configs", exist_ok=True)
        with open(example_path, 'w', encoding='utf-8') as f:
            f.write(MAPPING_EXAMPLE)
        logger.info(f"📝 示例映射配置已生成: {example_path}")
        logger.info("请编辑后使用: python prepare_dataset.py --input ... --mapping configs/mapping.yaml")
        sys.exit(0)

    # 检查输入文件
    if not os.path.exists(args.input):
        logger.error(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)

    # 加载映射
    mapping = load_mapping(args.mapping)

    # 读取输入数据
    logger.info(f"📂 读取输入: {args.input}")
    submissions = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                submissions.append(json.loads(line))

    logger.info(f"读取了 {len(submissions)} 条提交记录")

    # 转换为 DataFrame
    df = convert_submissions(submissions, mapping)

    if len(df) == 0:
        logger.warning("⚠️  没有符合条件的记录")
        sys.exit(1)

    # 保存为 HuggingFace Dataset
    dataset = save_as_hf_dataset(
        df,
        args.output,
        mapping.get("features", DEFAULT_MAPPING["features"]),
        mapping.get("split", DEFAULT_MAPPING["split"]),
    )

    # 打印样例
    logger.info("\n📝 数据样例:")
    for split_name in ["train", "validation"]:
        if split_name in dataset:
            sample = dataset[split_name][0]
            logger.info(f"  [{split_name}] {dict(sample)}")
