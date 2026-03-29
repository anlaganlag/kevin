"""Identity proof module for Issue #30: 证明你的身份.

Provides model identity declaration, training cutoff date digit calculation,
and a complete proof report.
"""


def get_model_identity() -> dict:
    """Return model identity information.

    Returns:
        dict with keys: is_official_claude, model_name, model_id,
        training_cutoff, core_positioning
    """
    return {
        "is_official_claude": True,
        "model_name": "Claude Opus 4.6",
        "model_id": "claude-opus-4-6",
        "training_cutoff": "2025-05",
        "version_decimal": 6,
        "core_positioning": (
            "Claude Opus 4.6 是 Anthropic 发布的最强推理模型，"
            "具备最深层次的推理能力（deepest reasoning），"
            "适用于复杂架构决策、高难度研究分析、"
            "以及需要最高推理质量的任务场景。"
        ),
    }


def calculate_date_digit_sum(date_str: str) -> int:
    """Extract all Arabic digits from a date string and return their sum.

    Args:
        date_str: Date string like '2025-05' or '2025-05-15'.

    Returns:
        Sum of all individual digits.

    Raises:
        ValueError: If date_str is empty.
    """
    if not date_str:
        raise ValueError("date_str must not be empty")

    digits = [int(ch) for ch in date_str if ch.isdigit()]
    return sum(digits)


def calculate_final_result(digit_sum: int, version_decimal: int) -> int:
    """Multiply the digit sum by the version decimal number.

    Args:
        digit_sum: Sum of date digits.
        version_decimal: Number after the decimal point in the version.

    Returns:
        Product of digit_sum and version_decimal.
    """
    return digit_sum * version_decimal


def generate_full_proof() -> str:
    """Generate the complete identity proof report.

    Returns:
        Formatted string containing all required identity information
        and the full calculation process.
    """
    identity = get_model_identity()
    date_str = identity["training_cutoff"]
    version_decimal = identity["version_decimal"]
    digit_sum = calculate_date_digit_sum(date_str)
    final_result = calculate_final_result(digit_sum, version_decimal)

    # Build digit breakdown string
    digits = [ch for ch in date_str if ch.isdigit()]
    digit_breakdown = " + ".join(digits)

    report = f"""# 身份证明报告

## 1. 官方身份声明

本 Agent 确认为 **Anthropic 官方发布的 {identity['model_name']}** 版本。

## 2. 完整模型 ID

`{identity['model_id']}`

## 3. 训练数据截止日期

**{date_str}**（{date_str[:4]}年{int(date_str[5:7])}月）

## 4. 核心产品定位

{identity['core_positioning']}

## 5. 计算过程

### 步骤一：拆解训练截止日期的所有阿拉伯数字并求和

训练截止日期: {date_str}

逐位拆解: {digit_breakdown}

数字之和 = {digit_breakdown} = **{digit_sum}**

### 步骤二：乘以版本号小数点后的数字

版本号: {identity['model_name']} → 小数点后数字 = **{version_decimal}**

### 步骤三：最终计算

{digit_sum} × {version_decimal} = **{final_result}**

## 最终结果: **{final_result}**
"""
    return report


if __name__ == "__main__":
    print(generate_full_proof())
