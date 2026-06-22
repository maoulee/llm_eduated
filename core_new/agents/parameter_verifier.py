"""ParameterVerifier — validate design draft parameters for consistency and unique solutions.

Runs AFTER the Designer step and BEFORE the Solver step.
Uses python_exec (max 2 calls) to numerically verify:
  - Parameter self-consistency (e.g., address bits fit capacity)
  - Unique solution existence
  - Physical feasibility of given values

Input: QuestionDesignDraft (incremental — no blueprint needed).
Output: ParameterValidationReport (status: pass/needs_fix, detail, verified_parameters).

On failure, returns feedback that triggers Designer re-generation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import RoleType
from core_new.agent_tools import PYTHON_EXEC_TOOL
from core_new.blackboard import Blackboard
from core_new.markdown_parser import parse_md_sections


PARAMETER_VERIFY_PROMPT = """你是一位408考研参数验证专家。你的任务是验证题目设计稿中的数值参数是否自洽且能产生唯一解。

## 题目设计稿
{design_draft_json}

## 验证任务

请逐一检查以下方面：

1. **参数自洽性**: 所有给定数值参数之间是否存在逻辑矛盾？
   - 地址计算：位数是否足够表示给定地址空间
   - Cache参数：容量、组数、行大小、Tag位数是否匹配
   - 存储器参数：容量、字长、编址单位是否一致
   - 时序参数：周期、频率、延迟是否物理合理

2. **条件充分性**: 给定条件是否足以推导出唯一解？
   - 是否缺少关键参数导致多解
   - 是否存在冗余但不矛盾的参数

3. **唯一解保证**: 题目是否有且仅有一个确定解？

## 工具使用

使用 `python_exec` 工具进行数值验证（最多2次调用）。验证步骤：
- 计算关键导出量（如地址位数、Tag位数、页号等）
- 检查参数约束是否满足
- 确认数值在合理范围内

## 输出格式

请严格按以下markdown格式输出：

## 验证结果
- **status**: pass 或 needs_fix
- **confidence**: high 或 medium 或 low
- **summary**: 一句话验证结论

## 参数检查
- **consistency**: pass 或 fail（参数是否自洽，附说明）
- **sufficiency**: pass 或 fail（条件是否充分，附说明）
- **unique_solution**: pass 或 fail（是否有唯一解，附说明）

## 已验证参数
（列出通过代码验证确认的参数值，JSON格式）
- **verified_parameters**: {{"param1": value1, "param2": value2}}

## 修复建议（status为pass时写"无"）
- **fix_detail**: 具体问题描述和修复建议
- **problematic_params**: 有问题的参数列表（无问题写"无"）
"""


class ParameterVerifierAgent(BaseAgent):
    """Verify design draft parameters using python_exec (max 2 calls)."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="parameter_verifier",
                phase="parameter_verify",
                output_format="markdown",
                output_key="parameter_validation",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                tools=[PYTHON_EXEC_TOOL],
                max_tool_calls=2,
                max_tool_rounds=3,
                system_prompt=(
                    "你是一位408考研参数验证专家。你用python_exec工具验证题目参数的自洽性和唯一解。"
                    "严格按markdown格式输出。"
                ),
                expected_output_format=(
                    "## 验证结果\n"
                    "- **status**: pass|needs_fix\n"
                    "- **confidence**: high|medium|low\n"
                    "- **summary**: ...\n\n"
                    "## 参数检查\n"
                    "- **consistency**: pass|fail\n"
                    "- **sufficiency**: pass|fail\n"
                    "- **unique_solution**: pass|fail\n\n"
                    "## 已验证参数\n"
                    "- **verified_parameters**: {...}\n\n"
                    "## 修复建议\n"
                    "- **fix_detail**: ...\n"
                    "- **problematic_params**: ..."
                ),
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        design = blackboard.get("design", {})
        if not design:
            design = blackboard.get("question_design", {})

        design_json = json.dumps(design, ensure_ascii=False, indent=2)

        return PARAMETER_VERIFY_PROMPT.format(
            design_draft_json=design_json,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)

        sections = parse_md_sections(text)

        # Collect results from all sections
        result: Dict[str, Any] = {}

        for section_name, section_data in sections.items():
            if isinstance(section_data, dict):
                result.update(section_data)

        # Normalize status
        status = result.get("status", "pass")
        if isinstance(status, str):
            status = status.strip().lower()
        result["status"] = status

        # Parse verified_parameters if it's a string
        vp = result.get("verified_parameters")
        if isinstance(vp, str):
            try:
                result["verified_parameters"] = json.loads(vp)
            except json.JSONDecodeError:
                result["verified_parameters"] = {}

        # Fallback: regex extraction for critical fields
        if "status" not in result or not result["status"]:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if m:
                result["status"] = m.group(1).strip().lower()

        if "summary" not in result or not result["summary"]:
            m = re.search(r"\*\*summary\*\*[:：]\s*(.+?)(?:\n|$)", text)
            if m:
                result["summary"] = m.group(1).strip()

        if "fix_detail" not in result or not result["fix_detail"]:
            m = re.search(r"\*\*fix_detail\*\*[:：]\s*(.+?)(?:\n|$)", text)
            if m:
                result["fix_detail"] = m.group(1).strip()

        # Build feedback for Designer on failure
        if result.get("status") == "needs_fix":
            result["feedback"] = (
                f"参数验证失败: {result.get('fix_detail', '参数自洽性问题')}\n"
                f"问题参数: {result.get('problematic_params', '未知')}"
            )

        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        status = str(parsed.get("status", "")).strip().lower()
        if status not in {"pass", "needs_fix"}:
            return False, "status must be pass or needs_fix"
        return True, ""
