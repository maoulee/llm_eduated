"""Prompts for PaperFormatterAgent — content polishing and layout quality."""

POLISH_EXPLANATION_PROMPT = """你是一位408考研试卷排版编辑。以下是某道题的解析原文，可能存在以下问题需要修正：

{issues}

请严格按照以下规则重写：

**格式规则：**
1. 每个选项分析必须独立成段，用 `- X选项：正确/错误。理由...` 格式
2. 计算过程每步单独一行，用编号标记
3. 难度评级必须填写（1-5）
4. 考点必须填写
5. 不要使用 &emsp;，用2个空格缩进

**内容规则：**
6. 去除所有自我讨论（如"等等"、"不对"、"重新审视"、"让我们"、"如果"、"修正"等内心独白）
7. 去除所有括号内的自我批注（如"（注：...但...）"）
8. 不要改变任何计算结果、答案或选项
9. 只做编辑润色，不做内容创造

原文：
{raw_text}

请输出修正后的markdown（只输出解析部分，不要输出题干）："""

SELF_DISCUSSION_PATTERNS = [
    "等等，",
    "不对",
    "重新审视",
    "让我们",
    "如果我们将",
    "修正最终",
    "我们严格指认",
    "但为了满足",
    "若按题干",
    "鉴于本题",
    "但等一下",
    "这可能产生干扰",
    "恰好匹配选项",
    "完美符合",
]

ISSUE_DETECT_RULES = {
    "has_self_discussion": "解析中包含自我讨论或内心独白",
    "missing_difficulty": "缺少难度评级",
    "missing_topic": "缺少考点描述",
    "missing_option_analysis": "缺少逐选项分析",
    "inline_calculation": "计算过程没有分行显示",
}
