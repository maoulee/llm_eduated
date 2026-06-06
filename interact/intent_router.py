"""Lightweight LLM intent classifier for teacher exam-question requests."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

INTENT_ROUTER_SYSTEM_PROMPT = """\
你是一个意图分类助手。用户是教师，正在请求生成考试题目。

请根据用户输入判断意图类型，并提取参数。输出严格 JSON 格式。

## 意图类型

### 1. compose — 组卷请求
教师希望按科目、难度等条件组一套完整试卷。

必填参数：
- subject: 科目（如 "数据结构"、"操作系统"、"计算机组成原理"、"计算机网络"）
- difficulty: 难度（easy / medium / hard）
- question_count: 题目数量（整数）
- question_types: 题型列表，如 ["选择题", "综合应用题"]

### 2. knowledge_point — 知识点出题请求
教师希望针对某个具体知识点出题。

必填参数：
- knowledge_topic: 知识点名称（如 "二叉树遍历"、"页面置换算法"）
- subject: 所属科目
- question_count: 题目数量（整数）
- question_type: 题型（"选择题" 或 "综合应用题"）
- difficulty: 难度（easy / medium / hard）

### 3. clarify — 需要澄清
用户输入不够明确，无法判断意图或缺少关键参数。

字段：
- missing_params: 缺少的参数名列表
- clarification_question: 向用户提出的追问

## 输出格式

严格输出以下 JSON（不要用 markdown 代码块包裹）：

对于 compose 意图：
{"intent": "compose", "params": {"subject": "...", "difficulty": "...", "question_count": N, "question_types": [...]}, "missing_params": [], "response": ""}

对于 knowledge_point 意图：
{"intent": "knowledge_point", "params": {"knowledge_topic": "...", "subject": "...", "question_count": N, "question_type": "...", "difficulty": "..."}, "missing_params": [], "response": ""}

对于 clarify 意图：
{"intent": "clarify", "params": {}, "missing_params": ["..."], "response": "..."}

## 示例

用户: "帮我出一套数据结构的中等难度试卷，5道选择题2道综合题"
输出: {"intent": "compose", "params": {"subject": "数据结构", "difficulty": "medium", "question_count": 7, "question_types": ["选择题", "综合应用题"]}, "missing_params": [], "response": ""}

用户: "出3道关于二叉树遍历的选择题，简单难度"
输出: {"intent": "knowledge_point", "params": {"knowledge_topic": "二叉树遍历", "subject": "数据结构", "question_count": 3, "question_type": "选择题", "difficulty": "easy"}, "missing_params": [], "response": ""}

用户: "帮我出几道题"
输出: {"intent": "clarify", "params": {}, "missing_params": ["subject", "difficulty", "question_count", "question_types"], "response": "请问您需要哪个科目的题目？需要什么难度和题型？"}

用户: "操作系统页面置换相关内容"
输出: {"intent": "knowledge_point", "params": {"knowledge_topic": "页面置换算法", "subject": "操作系统", "question_count": 1, "question_type": "选择题", "difficulty": "medium"}, "missing_params": [], "response": ""}
"""


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try stripping markdown code fences
    if "```json" in text:
        match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Try stripping generic code fences
    if "```" in text:
        match = re.search(r"```\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Last resort: find first { ... } pair
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


@dataclass
class IntentResult:
    intent: str  # "compose" | "knowledge_point" | "clarify"
    params: dict = field(default_factory=dict)
    missing_params: list[str] = field(default_factory=list)
    response: str = ""  # clarification question to ask user


class IntentRouter:
    """Classify teacher intent and extract parameters via a single LLM call."""

    def __init__(self, gateway) -> None:
        """gateway is an LLMGateway instance."""
        self.gateway = gateway

    async def route(self, user_message: str, context: dict | None = None) -> IntentResult:
        """Classify user intent and extract parameters.

        Single LLM call with structured JSON output.
        """
        messages = [
            {"role": "system", "content": INTENT_ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Low temperature for classification; low token budget for short JSON
        result = await self.gateway.generate_json(
            messages,
            max_tokens=512,
            enable_thinking=False,
        )

        if not result.ok or result.parsed_json is None:
            logger.warning(
                "Intent router LLM call failed: %s (content=%s)",
                result.error_message,
                (result.content or "")[:200],
            )
            return IntentResult(
                intent="clarify",
                response="请再详细描述一下您的需求",
            )

        data = result.parsed_json

        # Fallback: if parsed_json is None but content exists, try manual extraction
        if data is None and result.content:
            data = _extract_json(result.content)

        if data is None:
            return IntentResult(
                intent="clarify",
                response="请再详细描述一下您的需求",
            )

        intent = data.get("intent", "clarify")
        if intent not in ("compose", "knowledge_point", "clarify"):
            intent = "clarify"

        return IntentResult(
            intent=intent,
            params=data.get("params", {}),
            missing_params=data.get("missing_params", []),
            response=data.get("response", ""),
        )
