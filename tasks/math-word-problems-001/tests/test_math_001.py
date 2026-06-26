"""
test_math_001.py — 数学应用题求解任务测试套件

测试内容：
1. 模型输出的 JSON 格式验证
2. 答案精确匹配
3. 解题步骤合理性
4. 边界情况测试
"""

import pytest
import json
import re


# ============================================================================
# 测试数据
# ============================================================================

# 参考测试用例
TEST_CASES = [
    {
        "question": "小明有 15 个苹果，小红有 23 个苹果，他们一共有多少个苹果？",
        "expected_answer": 38
    },
    {
        "question": "商店有 45 个西瓜，卖出 27 个，还剩多少个？",
        "expected_answer": 18
    },
    {
        "question": "每排有 8 个座位，共有 6 排，一共有多少个座位？",
        "expected_answer": 48
    },
    {
        "question": "把 36 个糖果平均分给 4 个小朋友，每人分到几个？",
        "expected_answer": 9
    },
    {
        "question": "小明有 12 本书，小红的书是小明的 3 倍，小红有多少本书？",
        "expected_answer": 36
    }
]


# ============================================================================
# 模拟模型输出（用于测试测试框架本身）
# ============================================================================

def dummy_model_solve(question: str) -> dict:
    """
    模拟模型输出。
    在实际评测中，此函数会被替换为模型的输出。
    """
    # 简单解析模式
    nums = [int(n) for n in re.findall(r'\d+', question)]

    if "一共" in question and "苹果" in question and len(nums) >= 2:
        answer = nums[0] + nums[1]
        steps = [
            f"{nums[0]} + {nums[1]} = {answer}",
            f"总共 {answer} 个苹果"
        ]
    elif "还剩" in question and len(nums) >= 2:
        answer = nums[0] - nums[1]
        steps = [
            f"{nums[0]} - {nums[1]} = {answer}",
            f"还剩 {answer} 个"
        ]
    elif "每排" in question or "每行" in question:
        answer = nums[0] * nums[1]
        steps = [
            f"{nums[0]} × {nums[1]} = {answer}",
            f"共 {answer} 个座位"
        ]
    elif "平均分" in question:
        answer = nums[0] // nums[1]
        steps = [
            f"{nums[0]} ÷ {nums[1]} = {answer}",
            f"每人 {answer} 个"
        ]
    elif "倍" in question:
        answer = nums[0] * nums[1]
        steps = [
            f"{nums[0]} × {nums[1]} = {answer}",
            f"共 {answer} 本"
        ]
    else:
        answer = 0
        steps = ["无法解析题目"]

    return {"answer": answer, "steps": steps}


# ============================================================================
# 测试类
# ============================================================================

class TestMathWordProblems:
    """数学应用题求解测试类"""

    # ----------------------------------------------------------------
    # 格式验证
    # ----------------------------------------------------------------

    def test_output_is_valid_json(self):
        """测试1：模型输出应为有效的 JSON 对象"""
        result = dummy_model_solve(TEST_CASES[0]["question"])
        # 验证是字典
        assert isinstance(result, dict), "输出应为 dict 类型"
        # 验证包含必要字段
        assert "answer" in result, "输出应包含 'answer' 字段"
        assert "steps" in result, "输出应包含 'steps' 字段"

    def test_answer_is_number(self):
        """测试2：answer 字段应为数值类型"""
        for case in TEST_CASES:
            result = dummy_model_solve(case["question"])
            answer = result.get("answer")
            assert isinstance(answer, (int, float)), (
                f"答案应为数值类型，实际 {type(answer)}: {answer}")

    def test_steps_is_list(self):
        """测试3：steps 字段应为列表"""
        for case in TEST_CASES:
            result = dummy_model_solve(case["question"])
            steps = result.get("steps", [])
            assert isinstance(steps, list), "steps 应为列表类型"
            assert len(steps) > 0, "steps 不应为空列表"
            for step in steps:
                assert isinstance(step, str), (
                    f"steps 中的每一步应为字符串: {step}")

    # ----------------------------------------------------------------
    # 答案精确匹配
    # ----------------------------------------------------------------

    def test_addition_problem(self):
        """测试4：加法问题求解"""
        case = TEST_CASES[0]
        result = dummy_model_solve(case["question"])
        assert result["answer"] == case["expected_answer"], (
            f"加法问题: 期望 {case['expected_answer']}, 实际 {result['answer']}")

    def test_subtraction_problem(self):
        """测试5：减法问题求解"""
        case = TEST_CASES[1]
        result = dummy_model_solve(case["question"])
        assert result["answer"] == case["expected_answer"], (
            f"减法问题: 期望 {case['expected_answer']}, 实际 {result['answer']}")

    def test_multiplication_problem(self):
        """测试6：乘法问题求解"""
        case = TEST_CASES[2]
        result = dummy_model_solve(case["question"])
        assert result["answer"] == case["expected_answer"], (
            f"乘法问题: 期望 {case['expected_answer']}, 实际 {result['answer']}")

    def test_division_problem(self):
        """测试7：除法问题求解"""
        case = TEST_CASES[3]
        result = dummy_model_solve(case["question"])
        assert result["answer"] == case["expected_answer"], (
            f"除法问题: 期望 {case['expected_answer']}, 实际 {result['answer']}")

    def test_multiplication_problem_2(self):
        """测试8：倍数问题求解"""
        case = TEST_CASES[4]
        result = dummy_model_solve(case["question"])
        assert result["answer"] == case["expected_answer"], (
            f"倍数问题: 期望 {case['expected_answer']}, 实际 {result['answer']}")

    # ----------------------------------------------------------------
    # 批量测试
    # ----------------------------------------------------------------

    def test_all_cases(self):
        """测试9：批量验证所有测试用例"""
        for i, case in enumerate(TEST_CASES):
            result = dummy_model_solve(case["question"])
            assert result["answer"] == case["expected_answer"], (
                f"用例 {i}: {case['question'][:20]}... "
                f"期望 {case['expected_answer']}, 实际 {result['answer']}")

    # ----------------------------------------------------------------
    # 边界测试
    # ----------------------------------------------------------------

    def test_empty_question(self):
        """测试10：空题目应妥善处理"""
        result = dummy_model_solve("")
        assert "answer" in result, "空题目也应返回 answer 字段"

    def test_question_without_numbers(self):
        """测试11：不包含数字的题目"""
        result = dummy_model_solve("今天天气真好")
        assert "answer" in result, "不包含数字的题目也应返回 answer 字段"

    # ----------------------------------------------------------------
    # 评测引擎兼容性测试
    # ----------------------------------------------------------------

    def test_exact_match_scoring(self):
        """
        测试12：模拟评测引擎的 exact_match 评分逻辑。

        将所有测试用例的结果与预期答案比对，
        计算精确匹配得分。
        """
        correct = 0
        total = len(TEST_CASES)

        for case in TEST_CASES:
            result = dummy_model_solve(case["question"])
            if result["answer"] == case["expected_answer"]:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.8, (
            f"精确匹配率 {accuracy:.0%} < 80% "
            f"({correct}/{total} 正确)")
