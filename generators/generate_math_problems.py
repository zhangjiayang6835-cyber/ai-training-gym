"""
generate_math_problems.py — 数学应用题数据生成器

生成中文小学数学应用题（加减乘除），输出 JSONL 格式文件。
每行包含: id, question, answer, steps

用法: python generators/generate_math_problems.py
"""

import json
import random
import os
from typing import Dict, List, Tuple


# ============================================================================
# 模板定义
# ============================================================================

# 人物/角色池
CHARACTERS = ["小明", "小红", "小华", "小刚", "小丽", "小芳", "小军", "小梅"]

# 物品池
OBJECTS = ["苹果", "香蕉", "橘子", "糖果", "铅笔", "书", "橡皮", "笔记本",
            "气球", "玩具车", "积木", "彩笔", "尺子", "书包", "水杯"]

# 地点/场景
SCENARIOS = ["商店", "学校", "果园", "农场", "超市", "图书馆", "食堂"]

# 单位
UNITS = ["个", "本", "支", "块", "盒", "箱", "袋", "只", "朵", "张"]


# ============================================================================
# 题目生成器
# ============================================================================

def generate_addition() -> Tuple[str, int, List[str]]:
    """生成加法应用题"""
    char1 = random.choice(CHARACTERS)
    char2 = random.choice([c for c in CHARACTERS if c != char1])
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    count1 = random.randint(3, 50)
    count2 = random.randint(3, 50)
    answer = count1 + count2

    question = f"{char1}有 {count1} {unit}{obj}，{char2}有 {count2} {unit}{obj}，他们一共有多少个{obj}？"
    steps = [
        f"{char1}有 {count1} {unit}{obj}",
        f"{char2}有 {count2} {unit}{obj}",
        f"{count1} + {count2} = {answer}"
    ]
    return question, answer, steps


def generate_multi_add() -> Tuple[str, int, List[str]]:
    """生成三项加法应用题"""
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    count1 = random.randint(5, 40)
    count2 = random.randint(5, 40)
    count3 = random.randint(5, 40)
    answer = count1 + count2 + count3

    question = (f"商店有{obj} {count1} {unit}，又运来{count2} {unit}，"
                f"再运来{count3} {unit}，现在一共有多少个{obj}？")
    steps = [
        f"原有 {count1} {unit}",
        f"第一次运来 {count2} {unit}",
        f"第二次运来 {count3} {unit}",
        f"{count1} + {count2} + {count3} = {answer}"
    ]
    return question, answer, steps


def generate_subtraction() -> Tuple[str, int, List[str]]:
    """生成减法应用题"""
    char = random.choice(CHARACTERS)
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    total = random.randint(20, 100)
    sold = random.randint(5, total - 1)
    answer = total - sold

    question = f"{char}有 {total} {unit}{obj}，用去了 {sold} {unit}，还剩多少个{obj}？"
    steps = [
        f"原有 {total} {unit}{obj}",
        f"用去了 {sold} {unit}",
        f"{total} - {sold} = {answer}"
    ]
    return question, answer, steps


def generate_multi_subtract() -> Tuple[str, int, List[str]]:
    """生成连续减法应用题"""
    char = random.choice(CHARACTERS)
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    total = random.randint(30, 100)
    give1 = random.randint(5, total // 3)
    give2 = random.randint(5, (total - give1) // 2)
    answer = total - give1 - give2

    question = (f"{char}有 {total} {unit}{obj}，给了朋友 {give1} {unit}，"
                f"又给了同学 {give2} {unit}，{char}还剩多少个{obj}？")
    steps = [
        f"原有 {total} {unit}{obj}",
        f"给出 {give1} {unit}",
        f"又给出 {give2} {unit}",
        f"{total} - {give1} - {give2} = {answer}"
    ]
    return question, answer, steps


def generate_multiplication() -> Tuple[str, int, List[str]]:
    """生成乘法应用题"""
    scenario = random.choice(SCENARIOS)
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    rows = random.randint(3, 12)
    per_row = random.randint(4, 15)
    answer = rows * per_row

    question = f"{scenario}有 {rows} 行{obj}，每行有 {per_row} {unit}，一共有多少个{obj}？"
    steps = [
        f"有 {rows} 行",
        f"每行 {per_row} {unit}",
        f"{rows} × {per_row} = {answer}"
    ]
    return question, answer, steps


def generate_division() -> Tuple[str, int, List[str]]:
    """生成除法应用题"""
    char = random.choice(CHARACTERS)
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    total = random.randint(20, 100)
    # 确保能整除
    factors = [n for n in range(2, 11) if total % n == 0]
    if not factors:
        total = 36  # fallback
        factors = [2, 3, 4, 6, 9]
    people = random.choice(factors)
    answer = total // people

    question = f"把 {total} {unit}{obj}平均分给 {people} 个小朋友，每人分到几个？"
    steps = [
        f"有 {total} {unit}{obj}",
        f"分给 {people} 个小朋友",
        f"{total} ÷ {people} = {answer}"
    ]
    return question, answer, steps


def generate_multiplication_scalar() -> Tuple[str, int, List[str]]:
    """生成倍数乘法应用题"""
    char1 = random.choice(CHARACTERS)
    char2 = random.choice([c for c in CHARACTERS if c != char1])
    obj = random.choice(OBJECTS)
    unit = random.choice(UNITS)

    base = random.randint(3, 20)
    times = random.choice([2, 3, 4, 5])
    answer = base * times

    question = (f"{char1}有 {base} {unit}{obj}，"
                f"{char2}的{obj}是{char1}的 {times} 倍，{char2}有多少个{obj}？")
    steps = [
        f"{char1}有 {base} {unit}{obj}",
        f"{char2}是{char1}的 {times} 倍",
        f"{base} × {times} = {answer}"
    ]
    return question, answer, steps


# ============================================================================
# 生成器主函数
# ============================================================================

GENERATORS = [
    ("addition", generate_addition, 0.20),
    ("multi_add", generate_multi_add, 0.10),
    ("subtraction", generate_subtraction, 0.20),
    ("multi_subtract", generate_multi_subtract, 0.10),
    ("multiplication", generate_multiplication, 0.15),
    ("division", generate_division, 0.15),
    ("multiplication_scalar", generate_multiplication_scalar, 0.10),
]


def generate_problems(n: int, seed: int = 42) -> List[Dict]:
    """
    生成 n 道数学应用题。

    参数:
        n: 生成题目数量
        seed: 随机种子

    返回:
        List[Dict]: 包含 id, question, answer, steps 的字典列表
    """
    random.seed(seed)

    problems = []
    # 按权重分配各类型数量
    names = [g[0] for g in GENERATORS]
    funcs = [g[1] for g in GENERATORS]
    weights = [g[2] for g in GENERATORS]

    # 确保每种类型至少有一个
    type_counts = {name: max(1, int(n * weight)) for name, weight in
                   zip(names, weights)}

    # 调整总数
    total_assigned = sum(type_counts.values())
    if total_assigned < n:
        # 把剩余的分配给第一个类型
        type_counts[names[0]] += n - total_assigned

    problem_id = 0
    for name, func in zip(names, funcs):
        for _ in range(type_counts[name]):
            question, answer, steps = func()
            problems.append({
                "id": f"math-{name}-{problem_id:04d}",
                "question": question,
                "answer": answer,
                "steps": steps
            })
            problem_id += 1
            if len(problems) >= n:
                break
        if len(problems) >= n:
            break

    return problems[:n]


def save_jsonl(problems: List[Dict], filepath: str):
    """保存为 JSONL 格式"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        for problem in problems:
            f.write(json.dumps(problem, ensure_ascii=False) + '\n')
    print(f"✅ 已生成 {len(problems)} 道题目 → {filepath}")


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    # 生成训练集 (100 题)
    train = generate_problems(100, seed=42)
    save_jsonl(train, "tasks/math-word-problems-001/data/train.jsonl")

    # 生成验证集 (20 题)
    val = generate_problems(20, seed=123)
    save_jsonl(val, "tasks/math-word-problems-001/data/val.jsonl")

    # 打印样例
    print("\n📝 样例:")
    sample = train[0]
    print(f"  题目: {sample['question']}")
    print(f"  答案: {sample['answer']}")
    print(f"  步骤: {sample['steps']}")
