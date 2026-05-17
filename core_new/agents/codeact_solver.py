"""CodeActSolverAgent — solves questions via a Python execution loop.

Instead of long text reasoning, this agent:
1. Reads the question
2. Writes Python code to compute the answer
3. Executes the code via tool_executor
4. Observes the result
5. Repeats or outputs final_answer

Max 5 action rounds per question.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.blackboard import Blackboard
from core_new.llm_gateway import LLMGateway, LLMResult
from core_new.tool_executor import execute_python

logger = logging.getLogger(__name__)

MAX_STEPS = 5


@dataclass
class SolverResult:
    """Structured output from CodeActSolver."""
    answer: str
    confidence: str
    evidence: str
    method: str  # "python" or "reasoning"
    sub_answers: Optional[Dict[str, str]] = None
    tool_steps: int = 0
    python_exec_count: int = 0
    raw_trace: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "answer": self.answer,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "method": self.method,
            "tool_steps": self.tool_steps,
            "python_exec_count": self.python_exec_count,
        }
        if self.sub_answers:
            d["sub_answers"] = self.sub_answers
        return d


def _extract_python_code(text: str) -> Optional[str]:
    """Extract Python code block from model output."""
    # Case-insensitive match for ```python, ```Python, etc.
    m = re.search(r"```[Pp]ython\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: generic code block with Python keywords
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if any(kw in content for kw in ["print(", "import ", "def ", "=", "for ", "if "]):
            return content
    return None


def _is_final_answer(text: str) -> bool:
    """Check if the model output contains a final_answer section."""
    return bool(re.search(r"#\s*final_answer", text, re.IGNORECASE)) or \
           bool(re.search(r"FINAL_ANSWER:", text, re.IGNORECASE))


def _parse_final_answer(text: str, question_type: str = "single_choice") -> SolverResult:
    """Parse final_answer section from model output."""
    answer = ""
    confidence = "medium"
    evidence = ""
    sub_answers = None

    # Try FINAL_ANSWER: X format first (common when model is forced to answer)
    m = re.search(r"FINAL_ANSWER:\s*([A-D])", text, re.IGNORECASE)
    if m:
        answer = m.group(1).upper()
    else:
        # Extract answer field from markdown
        m = re.search(r"\*\*answer\*\*:\s*(.+)", text)
        if m:
            answer = m.group(1).strip()
            for prefix in ["FINAL_ANSWER:", "final_answer:", "Answer:", "answer:"]:
                if answer.upper().startswith(prefix.upper()):
                    answer = answer[len(prefix):].strip()
    m = re.search(r"\*\*answers\*\*:\s*(.+)", text)
    if m:
        try:
            sub_answers = json.loads(m.group(1).strip())
            answer = json.dumps(sub_answers, ensure_ascii=False)
        except json.JSONDecodeError:
            answer = m.group(1).strip()

    m = re.search(r"\*\*confidence\*\*:\s*(\w+)", text)
    if m:
        confidence = m.group(1).strip().lower()

    m = re.search(r"\*\*evidence\*\*:\s*(.+?)(?:\n#|\n##|\Z)", text, re.DOTALL)
    if m:
        evidence = m.group(1).strip()

    return SolverResult(
        answer=answer,
        confidence=confidence,
        evidence=evidence,
        method="python",
        sub_answers=sub_answers,
    )


def _extract_text_answer(text: str, question_type: str) -> SolverResult:
    """Fallback: extract answer from text that lacks # final_answer marker.

    Tries to find structured answer patterns in the text.
    """
    sub_answers = {}

    # Try to find sub-question answers like "第1问 ... 答案: X" or "sub_q1: X"
    patterns = [
        (r"第[1]问.*?(?:答案|结果|为)\s*[:：]?\s*(.+?)(?:\n|$)", "sub_q1"),
        (r"第[2]问.*?(?:答案|结果|为)\s*[:：]?\s*(.+?)(?:\n|$)", "sub_q2"),
        (r"第[3]问.*?(?:答案|结果|为)\s*[:：]?\s*(.+?)(?:\n|$)", "sub_q3"),
        (r"第[4]问.*?(?:答案|结果|为)\s*[:：]?\s*(.+?)(?:\n|$)", "sub_q4"),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            sub_answers[key] = m.group(1).strip()[:200]

    # Also try JSON-like answer patterns
    m = re.search(r"(?:答案|answers?)[：:]\s*(\{[^}]+\})", text)
    if m:
        try:
            sub_answers.update(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    answer = ""
    if sub_answers:
        answer = json.dumps(sub_answers, ensure_ascii=False)

    # Single answer for choice questions
    if not answer:
        m = re.search(r"(?:选|答案|answer)[：:]\s*([A-D])", text, re.IGNORECASE)
        if m:
            answer = m.group(1).upper()

    return SolverResult(
        answer=answer,
        confidence="low",
        evidence="Extracted from text without final_answer marker",
        method="python",
        sub_answers=sub_answers if sub_answers else None,
    )


# ── Prompt templates for different states ──

_PROMPT_FORCE_FINAL = """请根据代码执行结果，严格按以下格式输出最终答案：

# final_answer

- **answers**: 各子问答案，JSON格式如 {{"sub_q1": "答案1", "sub_q2": "答案2"}}
- **confidence**: high/medium/low
- **evidence**: 各子问计算依据概要

直接输出，不要再写代码。"""

_PROMPT_NO_CODE_YET = """你必须用Python代码求解。请直接写代码，不要只做文字推理。

示例格式：
```python
from tools_408 import ieee754_single_hex, simulate_cache, simulate_page_replacement
# 根据题目参数计算
result = ...
print(f"答案: {result}")
```

请立即写出对应的Python代码。如果你已经有确定答案，请直接输出 `# final_answer`。"""


class CodeActSolverAgent:
    """Solves questions by writing and executing Python code."""

    def __init__(self, gateway: LLMGateway, *, max_tokens: int = 4096, max_steps: int = MAX_STEPS):
        self.gateway = gateway
        self.max_tokens = max_tokens
        self.max_steps = max_steps

    async def solve(
        self,
        question_draft: str,
        options: Optional[Dict[str, str]] = None,
        sub_questions: Optional[List[str]] = None,
        question_type: str = "single_choice",
    ) -> SolverResult:
        """Run the CodeAct loop to solve a question."""
        from core_new.prompts.codeact_prompts import (
            CODEACT_SYSTEM_PROMPT, CODEACT_USER_TEMPLATE, CODEACT_OBSERVATION_TEMPLATE,
        )

        options_section = ""
        if options:
            lines = [f"- {k}: {v}" for k, v in options.items()]
            options_section = "## 选项\n" + "\n".join(lines)

        sub_questions_section = ""
        if sub_questions:
            lines = [f"- {sq}" for sq in sub_questions]
            sub_questions_section = "## 子问\n" + "\n".join(lines)

        user_msg = CODEACT_USER_TEMPLATE.format(
            question_draft=question_draft,
            options_section=options_section,
            sub_questions_section=sub_questions_section,
        )

        messages = [
            {"role": "system", "content": CODEACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        tool_steps = 0
        python_exec_count = 0
        has_code_run = False
        full_trace_parts = [f"[User] {user_msg[:200]}..."]

        for step in range(self.max_steps):
            result = await self.gateway.generate_text(
                messages,
                max_tokens=self.max_tokens,
                enable_thinking=False,
            )

            if not result.ok:
                logger.warning("CodeAct LLM call failed: %s", result.error_message)
                return SolverResult(
                    answer="",
                    confidence="low",
                    evidence=f"LLM error: {result.error_message}",
                    method="python",
                    tool_steps=tool_steps,
                    python_exec_count=python_exec_count,
                    raw_trace="\n".join(full_trace_parts),
                )

            response_text = result.content or ""
            full_trace_parts.append(f"\n[Step {step + 1}] {response_text[:500]}")

            if not response_text.strip():
                logger.warning("CodeAct step %d: empty response, asking again", step + 1)
                messages.append({"role": "assistant", "content": "(empty)"})
                messages.append({"role": "user", "content": "请输出Python代码来验证计算。"})
                continue

            # Check if model gave a final answer
            if _is_final_answer(response_text):
                parsed = _parse_final_answer(response_text, question_type)
                parsed.tool_steps = tool_steps
                parsed.python_exec_count = python_exec_count
                parsed.raw_trace = "\n".join(full_trace_parts)
                logger.info("CodeAct final answer at step %d: %s", step + 1, parsed.answer)
                return parsed

            # If code already ran and model gives text without code/final_answer,
            # try to extract the answer from text
            if has_code_run and step >= 2:
                text_answer = _extract_text_answer(response_text, question_type)
                if text_answer.answer:
                    logger.info("CodeAct extracted text answer at step %d (no marker)", step + 1)
                    text_answer.tool_steps = tool_steps
                    text_answer.python_exec_count = python_exec_count
                    text_answer.raw_trace = "\n".join(full_trace_parts)
                    return text_answer

            # Try to extract and execute Python code
            code = _extract_python_code(response_text)
            if code:
                logger.info("CodeAct step %d: extracted %d chars of Python code",
                            step + 1, len(code))
                exec_result = execute_python(code, timeout=5.0)
                python_exec_count += 1
                tool_steps += 1
                has_code_run = True

                obs = CODEACT_OBSERVATION_TEMPLATE.format(
                    exit_code=exec_result.exit_code,
                    stdout=exec_result.stdout[:2000] if exec_result.stdout else "",
                    stderr=exec_result.stderr[:500] if exec_result.stderr else "",
                )

                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": obs})
                full_trace_parts.append(f"\n[Observation] exit={exec_result.exit_code} stdout={exec_result.stdout[:200]}")
                continue

            # No code found and no final answer
            logger.info("CodeAct step %d: no code block found, has_code_run=%s",
                        step + 1, has_code_run)
            messages.append({"role": "assistant", "content": response_text})

            # Choose prompt based on whether code has already executed
            if has_code_run:
                messages.append({"role": "user", "content": _PROMPT_FORCE_FINAL})
            else:
                messages.append({"role": "user", "content": _PROMPT_NO_CODE_YET})

        # Exhausted steps — force a final answer from last context
        messages.append({
            "role": "user",
            "content": _PROMPT_FORCE_FINAL,
        })
        result = await self.gateway.generate_text(
            messages, max_tokens=self.max_tokens, enable_thinking=False,
        )
        if result.ok and result.content:
            response_text = result.content
            if _is_final_answer(response_text):
                parsed = _parse_final_answer(response_text, question_type)
            else:
                # Last resort: try text extraction
                parsed = _extract_text_answer(response_text, question_type)
                if not parsed.answer:
                    parsed = SolverResult(
                        answer=response_text.strip()[:500],
                        confidence="low",
                        evidence="Max steps reached, forced answer",
                        method="python",
                    )
            parsed.tool_steps = tool_steps
            parsed.python_exec_count = python_exec_count
            parsed.raw_trace = "\n".join(full_trace_parts)
            return parsed

        return SolverResult(
            answer="",
            confidence="low",
            evidence="Max steps reached, no answer obtained",
            method="python",
            tool_steps=tool_steps,
            python_exec_count=python_exec_count,
            raw_trace="\n".join(full_trace_parts),
        )
