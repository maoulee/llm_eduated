"""FileCodeSolverAgent — writes Python scripts to disk, runs them, returns code + output.

Unlike the inline CodeActSolver, this agent:
1. Writes complete, self-contained Python scripts to tmp/solutions/{slot_id}/
2. Runs them via code_exec_408 in ToolRegistry
3. Code is persisted for independent verification
4. Does NOT format answers — just produces code + raw output
5. No dependency on pre-built tools_408.py — writes everything from scratch
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core_new.agent_runtime import ToolRegistry
from core_new.edu408_runtime import build_408_tools
from core_new.llm_gateway import LLMGateway
from core_new.agents.solver_utils import (
    extract_python_code, is_final_answer, parse_exec_result,
    extract_results_from_output, parse_final_json,
)

logger = logging.getLogger(__name__)

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


# ── Prompt templates ──

FILE_SOLVER_SYSTEM = """你是一个Python编程解题智能体。你的任务是为408考研题目编写Python求解脚本。

核心规则：
1. 写出**完整的、可直接运行的**Python脚本
2. 脚本必须是**自包含的** — 不依赖任何外部工具库（除标准库外）
3. 用 print() 输出所有计算结果
4. 不要输出最终答案格式（# final_answer），只输出计算过程和结果
5. 每个脚本解决一个明确的计算目标

**严禁硬编码中间值**：
- 必须用代码从题目给定的原始数据（如十六进制机器数）中解析出字段，而非凭记忆硬编码解析结果
- IEEE 754浮点数：必须用 struct.unpack('<I', bytes.fromhex(...)) 解析二进制，再手动提取符号位/阶码/尾数字段
- Cache地址计算：必须用代码计算 block_addr = addr // block_size, set_index = block_num % num_sets
- 任何从题目条件推导的中间值都必须通过代码计算，不得手动推算后硬编码

你可以自由使用Python标准库：math, struct, itertools, collections, functools等。
根据题目需要自己编写计算函数，不要假设有预建的工具函数。"""

FILE_SOLVER_USER = """请为以下题目编写Python求解脚本：

{question_draft}

{sub_questions_section}

要求：
- 写出完整的Python脚本
- 用 print() 输出每个子问的计算过程和结果
- 脚本必须可以直接运行（python step1.py）"""

FILE_SOLVER_SC_VERIFY = """请为以下单选题编写Python脚本，**逐个验证每个选项**的正确性。

## 题目
{stem}

## 选项
A: {option_A}
B: {option_B}
C: {option_C}
D: {option_D}

## 要求
- 编写Python代码，对每个选项进行独立计算验证
- 必须从题目原始数据（如十六进制数、地址值等）用代码解析，严禁硬编码中间值
- IEEE 754浮点数必须用struct模块解析，Cache地址必须用代码计算
- 对每个选项，计算其对应的结果，判断选项描述是否正确
- 最后输出一个JSON格式的验证结果

输出格式示例：
```json
{{
  "option_A": {{"computed": "计算得到的值", "is_correct": false, "reason": "为什么不对"}},
  "option_B": {{"computed": "计算得到的值", "is_correct": true, "reason": "为什么正确"}},
  "option_C": {{"computed": "计算得到的值", "is_correct": false, "reason": "为什么不对"}},
  "option_D": {{"computed": "计算得到的值", "is_correct": false, "reason": "为什么不对"}},
  "computed_correct": "B"
}}
```"""

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

    def __init__(
        self,
        gateway: LLMGateway,
        *,
        max_tokens: int = 4096,
        max_steps: int = MAX_STEPS,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.gateway = gateway
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.tools = tool_registry or build_408_tools(gateway=None, include_llm_tools=False)

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

        # Choose prompt based on question type
        if question_type == "single_choice" and options:
            user_msg = FILE_SOLVER_SC_VERIFY.format(
                stem=question_draft,
                option_A=options.get("A", ""),
                option_B=options.get("B", ""),
                option_C=options.get("C", ""),
                option_D=options.get("D", ""),
            )
        else:
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
                enable_thinking=True,
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
            if is_final_answer(response_text):
                parsed = parse_final_json(response_text)
                solution.computed_results.update(parsed)
                logger.info("[%s] Final answer at step %d: %s", slot_id, step + 1,
                            json.dumps(parsed, ensure_ascii=False)[:200])
                break

            # Extract Python code
            code = extract_python_code(response_text)
            if code:
                exec_raw = await self.tools.execute("code_exec_408", {
                    "code": code,
                    "slot_id": slot_id,
                    "step": step + 1,
                    "timeout": RUN_TIMEOUT,
                    "max_stdout": 5000,
                    "execution_mode": "subprocess",
                    "persist": True,
                })
                exec_result = parse_exec_result(exec_raw)
                file_path = exec_result.get("file_path", "")
                exit_code = int(exec_result.get("exit_code", -1))
                stdout = str(exec_result.get("stdout", ""))[:5000]
                stderr = str(exec_result.get("stderr", ""))[:1000]

                if file_path:
                    solution.code_files.append(file_path)
                logger.info("[%s] Saved step %d: %s (%d chars)", slot_id, step + 1, file_path, len(code))

                solution.python_exec_count += 1

                if stdout:
                    solution.outputs.append(stdout)
                    extracted = extract_results_from_output(stdout)
                    solution.computed_results.update(extracted)
                if not exec_result.get("ok") and not solution.error:
                    solution.error = stderr or str(exec_result.get("error", "execution failed"))

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
                messages, max_tokens=self.max_tokens, enable_thinking=True,
            )
            if result.ok and result.content:
                if is_final_answer(result.content):
                    parsed = parse_final_json(result.content)
                    solution.computed_results.update(parsed)
                else:
                    solution.computed_results["raw_text"] = result.content.strip()[:500]

        solution.total_time_s = time.monotonic() - start_time
        logger.info("[%s] FileCodeSolver done: %d files, %d execs, %.1fs",
                     slot_id, len(solution.code_files), solution.python_exec_count,
                     solution.total_time_s)
        return solution

    async def re_run(self, file_path: str) -> Dict[str, Any]:
        """Re-run a previously saved script (for verification)."""
        raw = await self.tools.execute("code_exec_408", {
            "file_path": file_path,
            "timeout": RUN_TIMEOUT,
            "max_stdout": 5000,
            "execution_mode": "subprocess",
        })
        return parse_exec_result(raw)
