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

from core_new.agent_roles import RoleType
from core_new.agent_runtime import ToolRegistry
from core_new.edu408_runtime import build_408_tools
from core_new.edu408_runtime.tools import DEFAULT_WORKSPACE
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
3. **必须打印完整的求解过程** — 每一步中间计算都要用 print() 输出，不能只输出最终结果
4. 不要输出最终答案格式（# final_answer），只输出计算过程和结果
5. 每个脚本解决一个明确的计算目标

**求解过程打印要求**：
- 每一步计算都要 print，格式如：print(f"Step 1: 从地址 0x{addr:08X} 提取页号 = {page_num}")
- 关键中间变量必须打印：print(f"块大小 = {block_size}B, 组数 = {num_sets}, tag位数 = {tag_bits}")
- 公式推导要打印：print(f"E = 阶码 - 偏移量 = {exponent_raw} - {bias} = {E}")
- 最终结论要打印：print(f"=> 选项{letter} {'正确' if correct else '错误'}: {reason}")

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
- **必须打印完整的求解过程**：每一步中间计算都要 print，包括公式推导、中间变量值、单位换算等
- 不能只打印最终结果，要让审核者能追踪完整的推理链
- 脚本必须可以直接运行（python step1.py）

打印格式示例：
```python
print(f"Step 1: 从题目条件得: 虚拟地址位数={{va_bits}}, 页面大小={{page_size}}")
print(f"Step 2: 页内偏移 = log2({{page_size}}) = {{offset_bits}}位")
print(f"Step 3: VPN位数 = {{va_bits}} - {{offset_bits}} = {{vpn_bits}}位")
```"""

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
- **每个选项验证时，必须打印完整的推理过程**：
  - 从题目条件中提取了什么数据
  - 应用了什么公式或规则
  - 中间计算步骤
  - 最终结论
- 最后输出一个JSON格式的验证结果

**打印过程示例**：
```python
print("=== 验证选项A ===")
print(f"Step 1: 提取题目条件: 页面大小={page_size}B, 虚拟地址位数={va_bits}")
print(f"Step 2: 计算页内偏移位数 = log2({page_size}) = {offset_bits}")
print(f"Step 3: 计算虚拟页号位数 = {va_bits} - {offset_bits} = {vpn_bits}")
print(f"=> 选项A描述: '...', 计算结果: {computed}, 结论: {'正确' if match else '错误'}")
```

最后用print输出JSON结果：
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

请分析执行结果并采取行动：
- **如果 exit_code != 0（执行出错）**：仔细阅读 stderr 错误信息，修复代码中的 bug（语法错误、逻辑错误、变量名错误等），输出修复后的完整脚本
- **如果输出缺少求解过程**：只输出了最终结果而没有中间步骤的 print，需要添加 print(f"Step N: ...") 语句来展示完整推理链
- **如果结果已经完整**（有过程、有结论）：输出 # final_answer 和 JSON 格式的计算结果"""

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

FILE_SOLVER_PROCESS_MISSING = """代码执行成功了，但输出缺少**求解过程**。你的目标不仅是得到正确结果，还要让审核者能追踪完整的推理链。

请在代码中添加 print() 语句，输出每一步的计算过程：
- 从题目条件中提取了什么数据
- 应用了什么公式
- 中间变量值是什么
- 每步推理的结论

然后重新输出修复后的完整脚本。"""


def _has_process_output(stdout: str) -> bool:
    """Check if stdout contains step-by-step solving process."""
    if not stdout or len(stdout.strip()) < 20:
        return False
    # Heuristic: process output should have multiple lines with meaningful content
    lines = [l.strip() for l in stdout.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return False
    # Check for process indicators: Step, =>, =, 计算得, 验证, etc.
    process_signals = 0
    for line in lines:
        if any(sig in line for sig in ("Step", "step", "=>", "==>", "验证", "计算", "得")):
            process_signals += 1
        elif "=" in line and not line.startswith("{") and not line.startswith("["):
            process_signals += 1
    # At least 2 lines look like process output
    return process_signals >= 2


class FileCodeSolverAgent:
    """Solves questions by writing Python scripts to disk and running them."""

    role_type = RoleType.REASONER

    def __init__(
        self,
        gateway: LLMGateway,
        *,
        max_tokens: int = 16384,
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
        slot_id: str = "unknown",
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

                if exit_code != 0:
                    logger.warning("[%s] Script %s failed: exit=%d stderr=%s",
                                   slot_id, file_path, exit_code, stderr[:200])
                    messages.append({"role": "user", "content": obs})
                elif not _has_process_output(stdout):
                    logger.info("[%s] Output lacks process, requesting step-by-step prints", slot_id)
                    messages.append({"role": "user", "content": obs + "\n\n" + FILE_SOLVER_PROCESS_MISSING})
                else:
                    messages.append({"role": "user", "content": obs})
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


# ── Runtime solver: tool-calling loop ─────────────────────────


RUNTIME_SOLVER_SYSTEM = """你是一个Python编程解题智能体。你的任务是为408考研题目编写Python求解脚本，并通过工具执行验证。

## 你的工作方式
1. 分析题目，规划求解步骤
2. 使用 code_exec_408 工具执行Python代码
3. 观察执行结果，如果出错则修复代码重新执行
4. 确保输出包含**完整的求解过程**（每一步中间计算都要 print）
5. 得到最终结果后，直接用文字输出最终答案

## 核心规则
- 每步中间计算都必须 print，包括：公式推导、中间变量值、单位换算
- 严禁硬编码中间值，必须用代码从原始数据计算
- 如果代码执行出错（exit_code != 0），分析错误原因并修复后重新执行
- 如果输出缺少求解过程（只有最终结果），添加 print 语句后重新执行
- 代码必须是自包含的，只依赖Python标准库

## 完成标志
当你已经得到所有子问/选项的计算结果并确认正确时，直接输出最终答案文本，不再调用工具。"""


RUNTIME_SOLVER_SC_TASK = """请逐个验证以下单选题的每个选项。

## 题目
{stem}

## 选项
A: {option_A}
B: {option_B}
C: {option_C}
D: {option_D}

## 要求
- 使用 code_exec_408 工具编写并执行Python代码
- 对每个选项独立计算验证
- **打印完整推理过程**：提取了什么数据、用了什么公式、中间步骤、最终结论
- 如果代码出错，分析错误并修复后重新执行
- 全部验证完毕后，输出最终结论"""


RUNTIME_SOLVER_COMP_TASK = """请为以下综合题编写Python求解脚本。

## 题目
{question_draft}

{sub_questions_section}

## 要求
- 使用 code_exec_408 工具编写并执行Python代码
- **打印完整求解过程**：每步推导、中间变量、公式应用
- 如果代码出错，分析错误并修复后重新执行
- 全部子问求解完毕后，输出最终答案"""


class RuntimeFileCodeSolver:
    """Tool-calling solver: model decides when to write code, fix errors, and stop.

    Unlike FileCodeSolverAgent (text-parsing loop), this uses Edu408AgentLoop
    so the model is in control of the observe-think-act cycle:
    - Model outputs tool calls → code_exec_408 runs → model sees result
    - Model decides: fix error? add prints? output final answer?
    """

    role_type = RoleType.REASONER

    def __init__(
        self,
        gateway: LLMGateway,
        *,
        max_tokens: int = 16384,
        max_iterations: int = 8,
    ):
        self.gateway = gateway
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.tools = build_408_tools(gateway=None, include_llm_tools=False)

    async def solve(
        self,
        question_draft: str,
        options: Optional[Dict[str, str]] = None,
        sub_questions: Optional[List[str]] = None,
        question_type: str = "comprehensive",
        slot_id: str = "unknown",
    ) -> CodeSolution:
        """Run the tool-calling solver loop."""
        start_time = time.monotonic()
        solution = CodeSolution(slot_id=slot_id)

        # Build task description
        if question_type == "single_choice" and options:
            task = RUNTIME_SOLVER_SC_TASK.format(
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
            task = RUNTIME_SOLVER_COMP_TASK.format(
                question_draft=question_draft,
                sub_questions_section=sub_questions_section,
            )

        # Run the agent loop
        from core_new.agent_runtime import Edu408AgentLoop

        loop = Edu408AgentLoop(
            self.gateway,
            self.tools,
            workspace=DEFAULT_WORKSPACE,
            max_iterations=self.max_iterations,
            max_tokens=self.max_tokens,
            enable_thinking=False,
        )

        result = await loop.run(
            task,
            allowed_tools=["code_exec_408"],
            extra_system=RUNTIME_SOLVER_SYSTEM,
        )

        # Extract solution from the loop result
        final_text = result.final

        # Parse computed results from final output
        if is_final_answer(final_text):
            parsed = parse_final_json(final_text)
            solution.computed_results.update(parsed)
        else:
            # Try to extract JSON from the final text
            parsed = parse_final_json(final_text)
            if parsed:
                solution.computed_results.update(parsed)
            else:
                solution.computed_results["raw_text"] = final_text.strip()[:3000]

        # Collect code files and outputs from tool traces
        for trace_entry in (result.trace.tool_traces if result.trace else []):
            tool_name = trace_entry.tool_name
            if tool_name == "code_exec_408":
                solution.python_exec_count += 1
                obs = str(trace_entry.observation)
                # Extract file paths and outputs from observations
                file_match = re.search(r"file_path[\":\s]+(tmp/solutions/[^\s\"']+)", obs)
                if file_match:
                    solution.code_files.append(file_match.group(1))
                # Extract stdout from observation
                stdout_match = re.search(r"stdout[\":\s]+(.*?)(?:stderr|$)", obs, re.DOTALL)
                if stdout_match:
                    stdout_text = stdout_match.group(1).strip()[:5000]
                    if stdout_text:
                        solution.outputs.append(stdout_text)
                        extracted = extract_results_from_output(stdout_text)
                        solution.computed_results.update(extracted)

        solution.total_time_s = time.monotonic() - start_time
        logger.info("[%s] Runtime solver done: %d tool calls, %.1fs, tools=%s",
                     slot_id, len(result.tools_used), solution.total_time_s,
                     result.tools_used)
        return solution
