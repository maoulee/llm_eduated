"""FileCodeSolverAgent — writes Python scripts to disk, runs them, returns code + output.

Unlike the inline CodeActSolver, this agent:
1. Writes complete, self-contained Python scripts to tmp/solutions/{slot_id}/
2. Runs them via subprocess
3. Code is persisted for independent verification
4. Does NOT format answers — just produces code + raw output
5. No dependency on pre-built tools_408.py — writes everything from scratch
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core_new.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

SOLUTIONS_DIR = os.path.join("tmp", "solutions")
MAX_STEPS = 5
RUN_TIMEOUT = 10  # seconds per script execution


@dataclass
class CodeSolution:
    """Result from FileCodeSolverAgent — code files + outputs, no formatted answer."""
    slot_id: str
    code_files: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    computed_results: Dict[str, Any] = field(default_factory=dict)
    python_exec_count: int = 0
    total_time_s: float = 0.0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "code_files": self.code_files,
            "outputs": [o[:2000] for o in self.outputs],
            "computed_results": self.computed_results,
            "python_exec_count": self.python_exec_count,
            "total_time_s": round(self.total_time_s, 1),
            "error": self.error,
        }

    def get_last_output(self) -> str:
        if self.outputs:
            return self.outputs[-1]
        return ""


def _extract_python_code(text: str) -> Optional[str]:
    """Extract Python code block from model output."""
    m = re.search(r"```[Pp]ython\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if any(kw in content for kw in ["print(", "import ", "def ", "=", "for ", "if "]):
            return content
    return None


def _extract_results_from_output(output: str) -> Dict[str, Any]:
    """Try to extract structured results from script output."""
    results: Dict[str, Any] = {}

    # Try JSON output
    try:
        # Look for JSON in output
        m = re.search(r"\{[^{}]+\}", output, re.DOTALL)
        if m:
            results = json.loads(m.group())
    except json.JSONDecodeError:
        pass

    # Try key=value patterns
    for m in re.finditer(r"(?:结果|result|answer|答案)[：:]\s*(.+)", output, re.IGNORECASE):
        key = f"result_{len(results)}"
        results[key] = m.group(1).strip()

    return results


def _is_final_answer(text: str) -> bool:
    return bool(re.search(r"#\s*final_answer", text, re.IGNORECASE)) or \
           bool(re.search(r"FINAL_ANSWER:", text, re.IGNORECASE))


def _save_script(slot_id: str, step: int, code: str) -> str:
    """Save a Python script to disk and return the file path."""
    dir_path = os.path.join(SOLUTIONS_DIR, slot_id)
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, f"step{step}.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code)

    return file_path


def _run_script(file_path: str, timeout: int = RUN_TIMEOUT) -> tuple:
    """Run a Python script and return (exit_code, stdout, stderr)."""
    abs_path = os.path.abspath(file_path)
    work_dir = os.path.dirname(abs_path)
    try:
        proc = subprocess.run(
            ["python", abs_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        return proc.returncode, proc.stdout[:5000], proc.stderr[:1000]
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


# ── Prompt templates ──

FILE_SOLVER_SYSTEM = """你是一个Python编程解题智能体。你的任务是为408考研题目编写Python求解脚本。

核心规则：
1. 写出**完整的、可直接运行的**Python脚本
2. 脚本必须是**自包含的** — 不依赖任何外部工具库（除标准库外）
3. 用 print() 输出所有计算结果
4. 不要输出最终答案格式（# final_answer），只输出计算过程和结果
5. 每个脚本解决一个明确的计算目标

你可以自由使用Python标准库：math, struct, itertools, collections, functools等。
根据题目需要自己编写计算函数，不要假设有预建的工具函数。"""

FILE_SOLVER_USER = """请为以下题目编写Python求解脚本：

{question_draft}

{sub_questions_section}

要求：
- 写出完整的Python脚本
- 用 print() 输出每个子问的计算过程和结果
- 脚本必须可以直接运行（python step1.py）"""

FILE_SOLVER_OBSERVATION = """# observation
脚本 {file_path} 执行结果：
- exit_code: {exit_code}
- stdout:
{stdout}
- stderr:
{stderr}

请分析执行结果。如果需要进一步计算，请写新的脚本。如果已经得到所有结果，请输出 # final_answer 和 JSON 格式的计算结果。"""

FILE_SOLVER_FORCE_FINAL = """请根据所有代码执行结果，输出最终计算结果。

格式：
# final_answer
```json
{{
  "sub_q1": "计算结果1",
  "sub_q2": "计算结果2",
  "sub_q3": "计算结果3"
}}
```

直接输出，不要再写代码。"""

FILE_SOLVER_NO_CODE = """你必须编写Python脚本来求解。请直接写出完整的Python代码：

```python
# 完整的计算脚本
def solve():
    # 根据题目编写计算逻辑
    pass

solve()
```"""


class FileCodeSolverAgent:
    """Solves questions by writing Python scripts to disk and running them."""

    def __init__(self, gateway: LLMGateway, *, max_tokens: int = 4096, max_steps: int = MAX_STEPS):
        self.gateway = gateway
        self.max_tokens = max_tokens
        self.max_steps = max_steps

    async def solve(
        self,
        question_draft: str,
        options: Optional[Dict[str, str]] = None,
        sub_questions: Optional[List[str]] = None,
        question_type: str = "comprehensive",
        slot_id: str = "Q43",
    ) -> CodeSolution:
        """Run the file-based coding loop to solve a question."""
        start_time = time.monotonic()
        solution = CodeSolution(slot_id=slot_id)

        sub_questions_section = ""
        if sub_questions:
            lines = [f"- {sq}" for sq in sub_questions]
            sub_questions_section = "## 子问\n" + "\n".join(lines)

        user_msg = FILE_SOLVER_USER.format(
            question_draft=question_draft,
            sub_questions_section=sub_questions_section,
        )

        messages = [
            {"role": "system", "content": FILE_SOLVER_SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        for step in range(self.max_steps):
            result = await self.gateway.generate_text(
                messages,
                max_tokens=self.max_tokens,
                enable_thinking=False,
            )

            if not result.ok:
                logger.warning("[%s] LLM call failed at step %d: %s", slot_id, step + 1, result.error_message)
                continue

            response_text = result.content or ""

            if not response_text.strip():
                logger.warning("[%s] Empty response at step %d", slot_id, step + 1)
                messages.append({"role": "assistant", "content": "(empty)"})
                messages.append({"role": "user", "content": FILE_SOLVER_NO_CODE})
                continue

            # Check if model gives final answer
            if _is_final_answer(response_text):
                parsed = self._parse_final_results(response_text)
                solution.computed_results.update(parsed)
                logger.info("[%s] Final answer at step %d: %s", slot_id, step + 1,
                            json.dumps(parsed, ensure_ascii=False)[:200])
                break

            # Extract Python code
            code = _extract_python_code(response_text)
            if code:
                # Save to disk
                file_path = _save_script(slot_id, step + 1, code)
                solution.code_files.append(file_path)
                logger.info("[%s] Saved step %d: %s (%d chars)", slot_id, step + 1, file_path, len(code))

                # Run the script
                exit_code, stdout, stderr = _run_script(file_path)
                solution.python_exec_count += 1

                if stdout:
                    solution.outputs.append(stdout)
                    extracted = _extract_results_from_output(stdout)
                    solution.computed_results.update(extracted)

                obs = FILE_SOLVER_OBSERVATION.format(
                    file_path=file_path,
                    exit_code=exit_code,
                    stdout=stdout[:2000] if stdout else "(empty)",
                    stderr=stderr[:500] if stderr else "(empty)",
                )

                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "user", "content": obs})

                if exit_code != 0:
                    logger.warning("[%s] Script %s failed: exit=%d stderr=%s",
                                   slot_id, file_path, exit_code, stderr[:200])
                continue

            # No code found — prompt for code
            logger.info("[%s] No code at step %d, prompting", slot_id, step + 1)
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": FILE_SOLVER_NO_CODE})

        else:
            # Exhausted steps — force final output
            messages.append({"role": "user", "content": FILE_SOLVER_FORCE_FINAL})
            result = await self.gateway.generate_text(
                messages, max_tokens=self.max_tokens, enable_thinking=False,
            )
            if result.ok and result.content:
                if _is_final_answer(result.content):
                    parsed = self._parse_final_results(result.content)
                    solution.computed_results.update(parsed)
                else:
                    solution.computed_results["raw_text"] = result.content.strip()[:500]

        solution.total_time_s = time.monotonic() - start_time
        logger.info("[%s] FileCodeSolver done: %d files, %d execs, %.1fs",
                     slot_id, len(solution.code_files), solution.python_exec_count,
                     solution.total_time_s)
        return solution

    def _parse_final_results(self, text: str) -> Dict[str, Any]:
        """Parse final answer JSON from model output."""
        # Try JSON code block
        m = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try inline JSON
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        # Try key-value patterns
        results = {}
        for m in re.finditer(r"\*\*(sub_q\d+)\*\*:\s*(.+)", text):
            results[m.group(1)] = m.group(2).strip()

        return results

    async def re_run(self, file_path: str) -> Dict[str, Any]:
        """Re-run a previously saved script (for verification)."""
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        exit_code, stdout, stderr = _run_script(file_path)
        return {
            "file_path": file_path,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }
