"""
GLMArbiter: Resolves inconsistencies between reasoning and code paths using GLM5.1.

This module implements LLM-based arbitration for cases where reasoning and code
paths disagree, using GLM5.1's thinking capability to make informed judgments.
"""

import re
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_ARBITRATION = """下面是同一道题的两个解法结果不一致，请判断哪个更可信。

## 题目
{stem}

## 本地模型推理答案
答案：{reasoning_answer}
推理过程：{reasoning}

## 本地模型代码求解答案
答案：{computed_answer}
代码输出：{code_output}

## 相关经验
{experience_cards}

请判断哪个答案更可信，或给出新的最终答案。
请输出：
<final_answer>...</final_answer>
<trusted_source>reasoning|code|neither|mixed</trusted_source>
<reason>...</reason>
<should_update_experience>true|false</should_update_experience>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_xml_tag(text: str, tag: str) -> str:
    """Extract content from <tag>...</tag>, returns empty string if not found."""
    pattern = rf'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_bool(value: str) -> bool:
    """Parse string to boolean."""
    if not value:
        return False
    return value.lower() in ("true", "yes", "1", "t", "y")


# ---------------------------------------------------------------------------
# GLMArbiter
# ---------------------------------------------------------------------------

class GLMArbiter:
    """
    Arbitrates disagreements between reasoning and code paths using GLM5.1.

    This component should only be called when ConsistencyChecker indicates
    need_glm=True, i.e., when there's a genuine disagreement that requires
    LLM judgment to resolve.
    """

    def __init__(self, llm_provider, max_tokens: int = 4096):
        """
        Initialize the GLM arbiter.

        Args:
            llm_provider: LLM provider instance with _generate_raw_batch method
            max_tokens: Maximum tokens for generation
        """
        self.llm_provider = llm_provider
        self.max_tokens = max_tokens

    async def arbitrate(
        self,
        question: Dict,
        reasoning_result: Dict,
        code_result: Dict,
        consistency: Dict,
        experience_text: str = "",
    ) -> Dict:
        """
        Call GLM to resolve disagreement between reasoning and code paths.

        Args:
            question: Question dict with keys:
                     - prompt: question text
                     - options: dict of option letters to text
            reasoning_result: Result from reasoning path with keys:
                             - answer: str
                             - reasoning: str
            code_result: Result from code path with keys:
                        - computed_answer: str
                        - exec_output: str
                        - code_applicable: bool
                        - exec_success: bool
            consistency: Result from ConsistencyChecker with keys:
                        - reasoning_answer: str
                        - code_answer: str
            experience_text: Natural language experience cards text

        Returns:
            Dict with keys:
            - final_answer: str (the arbitrated final answer)
            - trusted_source: str ("reasoning" | "code" | "neither" | "mixed")
            - reason: str (explanation for the decision)
            - should_update_experience: bool (whether to update experience database)
            - raw: str (raw model output)
        """
        # Extract question info
        stem = question.get("prompt", "")

        # Extract reasoning path info
        reasoning_answer = reasoning_result.get("answer", "").strip()
        reasoning = reasoning_result.get("reasoning", "").strip()

        # Extract code path info
        computed_answer = code_result.get("computed_answer", "").strip()
        code_output = code_result.get("exec_output", "").strip()
        code_applicable = code_result.get("code_applicable", False)
        exec_success = code_result.get("exec_success", False)

        # Format code output for display
        if code_applicable and exec_success:
            code_display = code_output if code_output else computed_answer
        elif not code_applicable:
            code_display = f"(代码不适用于此题) {computed_answer}"
        else:
            code_display = f"(代码执行失败) {computed_answer}"

        # Build prompt
        prompt = PROMPT_ARBITRATION.format(
            stem=stem,
            reasoning_answer=reasoning_answer,
            reasoning=reasoning,
            computed_answer=computed_answer,
            code_output=code_display,
            experience_cards=experience_text or "暂无相关经验"
        )

        messages = [[{"role": "user", "content": prompt}]]

        # Call GLM with thinking enabled
        results = await self.llm_provider.generate_with_think_and_parse_batch(
            messages_batch=messages,
            max_token=self.max_tokens,
            enable_thinking=True,
        )

        if not results:
            return {
                "final_answer": "",
                "trusted_source": "neither",
                "reason": "Error: No output from LLM",
                "should_update_experience": False,
            }

        content = results[0].get("answer", "")

        # Parse XML tags
        final_answer = _extract_xml_tag(content, "final_answer")
        trusted_source = _extract_xml_tag(content, "trusted_source")
        reason = _extract_xml_tag(content, "reason")
        should_update_experience_str = _extract_xml_tag(content, "should_update_experience")

        # Validate trusted_source values
        valid_sources = {"reasoning", "code", "neither", "mixed"}
        if trusted_source not in valid_sources:
            trusted_source = "neither"

        # Parse boolean
        should_update_experience = _parse_bool(should_update_experience_str)

        # If final_answer not found, try to extract from content
        if not final_answer:
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            if lines:
                final_answer = lines[-1][:100]

        return {
            "final_answer": final_answer,
            "trusted_source": trusted_source,
            "reason": reason,
            "should_update_experience": should_update_experience,
        }
