"""
DualPathSolver: Parallel reasoning + code solving for question answering.

This module implements a dual-path approach to solving questions:
- Path A: Natural reasoning with thinking
- Path B: Code generation with safe execution

Both paths run in parallel for efficiency.
"""

import asyncio
import re
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_REASONING = """请解答以下题目，给出你的推理过程和最终答案。

题目：
{question_text}

{experience_text}

{options_text}

请按以下XML格式输出：
<answer>你的最终答案（选项字母或计算结果）</answer>
<reasoning>你的详细推理过程</reasoning>
<confidence>0.0到1.0之间的置信度分数</confidence>
"""

PROMPT_CODE = """请为以下题目编写Python代码来独立计算并验证答案。

题目：
{question_text}

{experience_text}

{options_text}

要求：
1. 代码必须独立计算，不要依赖外部答案
2. 逐步计算并打印中间结果
3. 最后打印最终答案
4. 如果题目不适合用代码解答（如纯概念题），请设置code_applicable为false

请按以下格式输出：
```python
# 完整的Python代码
```

并在代码后按XML格式输出：
<computed_answer>代码运行后得到的答案</computed_answer>
<explanation>对代码逻辑的简要说明</explanation>
<code_applicable>true或false，表示本题是否适合用代码解答</code_applicable>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_xml_tag(text: str, tag: str) -> str:
    """Extract content from <tag>...</tag>, returns empty string if not found."""
    pattern = rf'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_code_block(text: str) -> str:
    """Extract Python code from ```python ... ``` blocks, falling back to XML <code> tags."""
    m = re.search(r'```(?:python)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return _extract_xml_tag(text, "code")


def _format_options(options: Dict[str, str]) -> str:
    """Format options dict as text."""
    if not options:
        return ""
    lines = []
    for key in sorted(options.keys()):
        lines.append(f"{key}. {options[key]}")
    return "\n".join(lines)


def _execute_code_safely(code: str, timeout: int = 10) -> Dict[str, Any]:
    """Execute Python code safely and capture print output."""
    stdout_buf = StringIO()
    stderr_buf = StringIO()

    # Restricted globals for safer execution
    restricted_globals = {
        "__builtins__": __builtins__,
        "math": __import__("math"),
    }

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, restricted_globals)
        output = stdout_buf.getvalue().strip()
        return {
            "success": True,
            "output": output,
            "stderr": stderr_buf.getvalue().strip()
        }
    except Exception:
        return {
            "success": False,
            "output": stdout_buf.getvalue().strip(),
            "error": traceback.format_exc()
        }


# ---------------------------------------------------------------------------
# DualPathSolver
# ---------------------------------------------------------------------------

class DualPathSolver:
    """Solver that runs reasoning and code paths in parallel."""

    def __init__(self, llm_provider, max_tokens: int = 4096):
        """
        Initialize the dual path solver.

        Args:
            llm_provider: LLM provider instance with generate_json_batch method
            max_tokens: Maximum tokens for generation
        """
        self.llm_provider = llm_provider
        self.max_tokens = max_tokens

    async def solve(self, question: Dict, experience_text: str) -> Dict:
        """
        Run both paths in parallel and return both results.

        Args:
            question: Question dict with keys:
                     - prompt: question text
                     - options: dict of option letters to text
                     - (optional) answer: ground truth answer
            experience_text: Natural language experience cards text

        Returns:
            Dict with keys:
            - reasoning_result: result from natural reasoning path
            - code_result: result from code generation path
        """
        reasoning_task = self._solve_reasoning(question, experience_text)
        code_task = self._solve_code(question, experience_text)
        reasoning_result, code_result = await asyncio.gather(
            reasoning_task, code_task
        )
        return {
            "reasoning_result": reasoning_result,
            "code_result": code_result,
        }

    async def _solve_reasoning(self, question: Dict, experience_text: str) -> Dict:
        """
        Path A: Natural reasoning with thinking.

        Returns:
            Dict with keys:
            - answer: extracted answer
            - reasoning: reasoning text
            - confidence: confidence score
            - raw: raw model output
        """
        question_text = question.get("prompt", "")
        options = question.get("options", {})
        options_text = _format_options(options)

        prompt = PROMPT_REASONING.format(
            question_text=question_text,
            experience_text=experience_text,
            options_text=options_text
        )

        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm_provider.generate_with_think_and_parse_batch(
            messages_batch=messages,
            max_token=self.max_tokens,
            enable_thinking=True,
        )

        if not results:
            return {
                "answer": "",
                "reasoning": "",
                "confidence": "0.0",
                "thinking": "",
            }

        result = results[0]
        content = result.get("answer", "")
        thinking = result.get("think", "")

        # Parse XML tags from content
        answer = _extract_xml_tag(content, "answer")
        reasoning = _extract_xml_tag(content, "reasoning")
        confidence = _extract_xml_tag(content, "confidence")

        # Fallback to thinking if reasoning tag is empty
        if not reasoning and thinking:
            reasoning = thinking

        # If answer not found in XML, try to extract from content
        if not answer:
            # Look for last line or explicit answer pattern
            lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
            if lines:
                answer = lines[-1][:100]

        return {
            "answer": answer,
            "reasoning": reasoning,
            "confidence": confidence,
            "thinking": thinking,
        }

    async def _solve_code(self, question: Dict, experience_text: str) -> Dict:
        """
        Path B: Code generation with execution.

        Returns:
            Dict with keys:
            - code: generated Python code
            - computed_answer: answer from code execution
            - explanation: code explanation
            - code_applicable: whether code path is applicable
            - exec_success: whether code executed successfully
            - exec_output: stdout from code execution
            - exec_error: error message if execution failed
            - raw: raw model output
        """
        question_text = question.get("prompt", "")
        options = question.get("options", {})
        options_text = _format_options(options)

        prompt = PROMPT_CODE.format(
            question_text=question_text,
            experience_text=experience_text,
            options_text=options_text
        )

        messages = [[{"role": "user", "content": prompt}]]

        results = await self.llm_provider.generate_with_think_and_parse_batch(
            messages_batch=messages,
            max_token=self.max_tokens,
            enable_thinking=True,
        )

        if not results:
            return {
                "code": "",
                "computed_answer": "",
                "explanation": "",
                "code_applicable": False,
                "exec_success": False,
                "exec_output": "",
                "exec_error": "No output from LLM",
            }

        result = results[0]
        content = result.get("answer", "")

        # Extract code (```python blocks first, then XML fallback)
        code = _extract_code_block(content)
        computed_answer = _extract_xml_tag(content, "computed_answer")
        explanation = _extract_xml_tag(content, "explanation")
        code_applicable_str = _extract_xml_tag(content, "code_applicable").lower()

        # Parse code_applicable boolean
        code_applicable = code_applicable_str in ("true", "yes", "1", "t")

        # Execute code if applicable and code was generated
        exec_success = False
        exec_output = ""
        exec_error = None

        if code_applicable and code:
            exec_result = _execute_code_safely(code)
            exec_success = exec_result["success"]
            exec_output = exec_result["output"]
            exec_error = exec_result.get("error")

            # If execution succeeded but no computed_answer in XML, extract from output
            if exec_success and not computed_answer:
                computed_answer = exec_output[:200]

        return {
            "code": code,
            "computed_answer": computed_answer,
            "explanation": explanation,
            "code_applicable": code_applicable,
            "exec_success": exec_success,
            "exec_output": exec_output,
            "exec_error": exec_error,
        }
