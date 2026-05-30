"""Single-choice question pipeline: draft -> options -> solve -> format -> review.

Agents:
  SingleChoiceDraftAgent      — generates question stem only
  OptionAndDistractorAgent    — generates 4 options with distractor intent
  SCSolutionFormatterAgent    — formats solution from solver result
  SingleChoiceReviewerAgent   — reviews complete question
  SingleChoiceAssemblerAgent  — merges all pieces into final output dict

Pipeline:
  SingleChoicePipeline.run()  — orchestrates agents in sequence with revision loop
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_runtime import Edu408AgentLoop
from core_new.agent_roles import AuditMode, RoleType
from core_new.blackboard import Blackboard
from core_new.edu408_runtime.tools import DEFAULT_WORKSPACE, build_408_tools
from core_new.experience_view import build_design_experience_view
from core_new.llm_gateway import LLMGateway, LLMResult
from core_new.markdown_parser import try_parse_json_object, parse_md_kv, parse_md_sections, parse_structured_output

logger = logging.getLogger(__name__)


# ── SingleChoiceDraftAgent ─────────────────────────────────────


class SingleChoiceDraftAgent(BaseAgent):
    """Generate question stem from slot blueprint + experience card."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="sc_draft",
                phase="sc_draft",
                output_format="markdown",
                output_key="sc_draft_result",
                max_tokens=16384,
                enable_thinking=False,
                max_retries=2,
                required_fields=["stem"],
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                expected_output_format=(
                    "## stem\n"
                    "- **stem**: question stem only, no options, no answer, no code block\n"
                    "- **reasoning_hint**: one sentence"
                ),
                system_prompt="你是一位408考研出题专家，擅长根据蓝图精确生成题干。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_DRAFT_PROMPT

        question_design = blackboard.get("question_design", {})
        design_md = question_design.get("raw_design_md", "")
        if not design_md:
            design_md = json.dumps(question_design, ensure_ascii=False, indent=2)

        prompt = SC_DRAFT_PROMPT.format(
            question_design_md=design_md,
        )

        # Check if this is a fix round (memory has review messages)
        has_fix = bool(self._memory and any(
            m.get("role") == "review" for m in self._memory
        ))

        # Legacy: also check blackboard for stem_fix_instruction
        fix_instruction = blackboard.get("stem_fix_instruction", "")
        if fix_instruction:
            has_fix = True

        if has_fix:
            prompt += (
                "\n\n## 重要提示\n"
                "你正在**修改**前一轮生成的题干，不是重新出一道不同的题。\n"
                "请查看下方历史记录中的审查反馈，针对审核指出的具体问题进行精确修改。\n"
                "保持题干整体结构、考察方向和知识点不变，仅修正被指出的问题。\n"
            )
            if fix_instruction:
                prompt += f"\n补充修复指令：{fix_instruction}\n"

        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("stem",), json_nested_key="stem")
        if result:
            return result
        # Fallback: extract **stem** anywhere
        m = re.search(r"\*\*stem\*\*\s*[:：]\s*(.+?)(?=\*\*|\n##|\Z)", text, re.DOTALL)
        if m:
            return {"stem": m.group(1).strip(), "reasoning_hint": ""}
        if len(text.strip()) > 20 and not text.strip().startswith("##"):
            return {"stem": text.strip(), "reasoning_hint": ""}
        return {}

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        stem = str(parsed.get("stem", ""))
        if "```" in stem or re.search(r"\b(int\s+main|#include|def\s+\w+\(|print\s*\()", stem):
            return False, "stem appears to contain copied code instead of a question stem"
        if len(stem.strip()) < 8:
            return False, "stem is too short"
        return True, ""


class RuntimeSingleChoiceDraftAgent(SingleChoiceDraftAgent):
    """Generate an SC stem through the DeepTutor-style runtime loop."""

    ALLOWED_TOOLS = ["search_knowledge_408", "read_workspace_file", "check_question_408"]

    def __init__(self, llm_backend):
        super().__init__(llm_backend)
        self.config.name = "runtime_sc_draft"

    async def execute(self, blackboard: Blackboard):
        input_snapshot = blackboard.get_relevant_state(self.config.name)
        start = time.monotonic()
        last_error = ""

        for attempt in range(self.config.max_retries + 1):
            try:
                prompt = self.build_input(blackboard)
                loop = Edu408AgentLoop(
                    self.llm,
                    build_408_tools(self.llm, include_llm_tools=False),
                    workspace=DEFAULT_WORKSPACE,
                    max_iterations=5,
                    max_tokens=self.config.max_tokens,
                    enable_thinking=self.config.enable_thinking,
                    execution_policy=self.execution_policy,
                )
                result = await asyncio.wait_for(
                    loop.run(
                        self._runtime_task(prompt),
                        allowed_tools=self.ALLOWED_TOOLS,
                        skill_names=["generate-question-408"],
                        extra_system=self._runtime_system(),
                    ),
                    timeout=self.config.timeout_s,
                )

                if result.final.lower().startswith("error:"):
                    raise RuntimeError(result.final)

                raw_text, parsed, _repair_attempts = await self._parse_validate_repair(
                    prompt=prompt,
                    result=LLMResult.success(
                        content=result.final,
                        provider=self.llm.provider_name,
                        model=self.llm.model_name,
                        latency_ms=0,
                    ),
                )
                if not raw_text and parsed is not None:
                    raw_text = json.dumps(parsed, ensure_ascii=False, indent=2, default=str)

                latency_s = time.monotonic() - start
                logger.info("[Runtime SC draft] tools_used=%s", result.tools_used)
                return await blackboard.write(
                    self.config.name,
                    raw_text,
                    self.config.phase,
                    output_key=self.config.output_key,
                    parsed=parsed,
                    input_snapshot=input_snapshot,
                    latency_s=latency_s,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt >= self.config.max_retries:
                    latency_s = time.monotonic() - start
                    return await blackboard.mark_failed(
                        self.config.name,
                        last_error,
                        phase=self.config.phase,
                        input_snapshot=input_snapshot,
                        latency_s=latency_s,
                    )
                await asyncio.sleep(min(2 ** attempt, 5))

    def _runtime_task(self, prompt: str) -> str:
        return (
            f"{prompt}\n\n"
            "Runtime requirements:\n"
            "1. You may use search_knowledge_408 or read_workspace_file if the slot needs grounding.\n"
            "2. Before the final answer, use check_question_408 if you have enough structured draft data.\n"
            "3. The final answer must be markdown, not a tool call, and must match:\n"
            f"{self.config.expected_output_format}\n"
            "4. Do not include answer options, final answer, code blocks, or copied reference code."
        )

    @staticmethod
    def _runtime_system() -> str:
        return (
            "You are running as a single-choice question designer inside the Edu408 runtime. "
            "The deterministic pipeline owns final slot acceptance, so keep the final output "
            "strictly parseable and limited to the stem design fields."
        )


# ── OptionAndDistractorAgent ───────────────────────────────────


class OptionAndDistractorAgent(BaseAgent):
    """Generate 4 options (A/B/C/D) with distractor intent for each wrong option."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="sc_options",
                phase="sc_options",
                output_format="markdown",
                output_key="sc_options_result",
                max_tokens=16384,
                enable_thinking=False,
                max_retries=2,
                required_fields=["option_A", "option_B", "option_C", "option_D", "correct_answer"],
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                expected_output_format=(
                    "## options\n"
                    "- **option_A**: ...\n"
                    "- **option_B**: ...\n"
                    "- **option_C**: ...\n"
                    "- **option_D**: ...\n\n"
                    "## distractors\n"
                    "- **distractor_intent_A**: ...\n"
                    "- **distractor_intent_B**: ...\n"
                    "- **distractor_intent_C**: ...\n"
                    "- **distractor_intent_D**: ...\n\n"
                    "## answer\n"
                    "- **correct_answer**: A|B|C|D\n"
                    "- **option_style_used**: ..."
                ),
                system_prompt="你是一位408考研出题专家，擅长设计选项和干扰项。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_OPTIONS_PROMPT

        draft_result = blackboard.get("sc_draft_result", {})
        question_design = blackboard.get("question_design", {})
        design_md = question_design.get("raw_design_md", "")
        if not design_md:
            design_md = json.dumps(question_design, ensure_ascii=False, indent=2)
        stem = draft_result.get("stem", "")

        return SC_OPTIONS_PROMPT.format(
            stem=stem,
            question_design_md=design_md,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        # Try JSON first for nested key extraction
        data = try_parse_json_object(text)
        if data:
            result = {}
            for key in ("options", "distractors", "answer"):
                if isinstance(data.get(key), dict):
                    result.update(data[key])
            if any(f"option_{letter}" in data for letter in "ABCD"):
                result.update(data)
            if result:
                return result
        # Shared markdown parser
        result = parse_structured_output(text, md_sections=("options", "distractors", "answer"))
        if result:
            return result
        # Last resort: regex
        result = {}
        for letter in "ABCD":
            m = re.search(rf"\*\*option_{letter}\*\*\s*[:：]\s*(.+?)(?=\*\*|\n##|\Z)", text, re.DOTALL)
            if m:
                result[f"option_{letter}"] = m.group(1).strip()
        m = re.search(r"\*\*correct_answer\*\*\s*[:：]\s*([A-D])", text)
        if m:
            result["correct_answer"] = m.group(1)
        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        answer = str(parsed.get("correct_answer", "")).strip().upper()
        if answer not in {"A", "B", "C", "D"}:
            return False, "correct_answer must be one of A/B/C/D"
        options = [str(parsed.get(f"option_{letter}", "")).strip() for letter in "ABCD"]
        if len(set(options)) < 4:
            return False, "options must be distinct"
        return True, ""


# ── StemVerifierAgent ─────────────────────────────────────────


class StemVerifierAgent(BaseAgent):
    """Pre-solve stem verification: coding agent that verifies parameters, severity-graded.

    Works like the solver — a coding agent with full Python execution environment.
    The model analyzes the stem, writes verification code, runs it, and judges based
    on actual computation results.
    """

    def __init__(self, llm_backend):
        from core_new.agent_tools import ToolDef
        from core_new.tool_executor import execute_python

        def _python_exec_handler(code: str, **kwargs) -> str:
            import json
            result = execute_python(code, timeout=kwargs.get("timeout", 10.0))
            return json.dumps({
                "ok": result.ok,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }, ensure_ascii=False)

        python_exec_tool = ToolDef(
            name="python_exec",
            description=(
                "Execute Python code in a sandbox environment. "
                "Available: math, struct, itertools, collections, functools, and standard library. "
                "Write any code you need for verification."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute for verification",
                    },
                },
                "required": ["code"],
            },
            handler=_python_exec_handler,
        )

        super().__init__(
            AgentConfig(
                name="stem_verifier",
                phase="stem_verification",
                output_format="markdown",
                output_key="stem_verification_result",
                max_tokens=8192,
                enable_thinking=True,
                max_retries=1,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.STEM_VERIFICATION,
                tools=[python_exec_tool],
                max_tool_rounds=5,
                expected_output_format=(
                    "## verification\n"
                    "- **status**: pass|needs_fix|pass_with_notes\n"
                    "- **severity**: none|critical|minor\n"
                    "- **code_verification_results**: ...\n"
                    "- **critical_issues**: ...\n"
                    "- **minor_issues**: ...\n"
                    "- **overall_comment**: ...\n\n"
                    "## fix_instruction\n"
                    "- **fix_target**: stem|none\n"
                    "- **fix_detail**: ..."
                ),
                system_prompt=(
                    "你是一位408考研题干参数审核专家。你的任务是验证题干中的数值参数是否自洽。"
                    "你有 code_exec_408 工具可以执行 Python 代码验证数值。"
                    "只阻断 critical 问题，minor 问题记录但不阻断。严格按markdown格式输出。"
                ),
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import STEM_VERIFICATION_PROMPT

        draft_result = blackboard.get("sc_draft_result", blackboard.get("sc_design", {}))
        question_design = blackboard.get("question_design", {})
        design_md = question_design.get("raw_design_md", "")
        if not design_md:
            design_md = json.dumps(question_design, ensure_ascii=False, indent=2)

        stem = draft_result.get("stem", "")

        # Build options section if available
        options_result = blackboard.get("sc_options_result", blackboard.get("sc_options", {}))
        if options_result:
            options_md = (
                f"- A: {options_result.get('option_A', '')}\n"
                f"- B: {options_result.get('option_B', '')}\n"
                f"- C: {options_result.get('option_C', '')}\n"
                f"- D: {options_result.get('option_D', '')}"
            )
        else:
            options_md = "（非选择题，无选项）"

        return STEM_VERIFICATION_PROMPT.format(
            stem=stem,
            options_md=options_md,
            question_design_md=design_md,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("verification", "fix_instruction"))
        if result:
            # Handle fix_instruction as dict
            data = try_parse_json_object(text)
            if data and isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            return result
        return {}

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        status = str(parsed.get("status", "")).strip().lower()
        if status not in {"pass", "needs_fix", "pass_with_notes"}:
            return False, "status must be pass, needs_fix, or pass_with_notes"
        return True, ""


# ── SCSolutionFormatterAgent ───────────────────────────────────


class SCSolutionFormatterAgent(BaseAgent):
    """Format clean solution from solver result — no re-solving."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="sc_solution_formatter",
                phase="sc_solution_format",
                output_format="markdown",
                output_key="sc_solution_result",
                max_tokens=8192,
                enable_thinking=False,
                required_fields=["correct_answer", "explanation"],
                repair_max_retries=1,
                role_type=RoleType.SUMMARIZER,
                system_prompt="你是一位408考研解析编写专家，擅长整理和格式化解析。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_SOLUTION_FORMATTER_PROMPT

        draft_result = blackboard.get("sc_draft_result", {})
        options_result = blackboard.get("sc_options_result", {})
        solver_result = blackboard.get("sc_solver_result", {})

        stem = draft_result.get("stem", "")
        options_md = (
            f"- A: {options_result.get('option_A', '')}\n"
            f"- B: {options_result.get('option_B', '')}\n"
            f"- C: {options_result.get('option_C', '')}\n"
            f"- D: {options_result.get('option_D', '')}"
        )

        return SC_SOLUTION_FORMATTER_PROMPT.format(
            stem=stem,
            options_md=options_md,
            solver_result_json=json.dumps(solver_result, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("solution",), json_nested_key="solution")
        if result:
            return result
        # Fallback: check for top-level keys in JSON
        data = try_parse_json_object(text)
        if data and ("correct_answer" in data or "explanation" in data):
            return data
        return {}


# ── SingleChoiceReviewerAgent ──────────────────────────────────


class SingleChoiceReviewerAgent(BaseAgent):
    """Review complete question against blueprint for quality."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="sc_reviewer",
                phase="sc_review",
                output_format="markdown",
                output_key="sc_review_result",
                max_tokens=8192,
                enable_thinking=False,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.QUESTION_REVIEW,
                system_prompt="你是一位408考研出题审核专家，严格审核题目质量。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_REVIEWER_PROMPT

        draft_result = blackboard.get("sc_draft_result", {})
        options_result = blackboard.get("sc_options_result", {})
        solution_result = blackboard.get("sc_solution_result", {})
        blueprint = blackboard.get("current_blueprint", {})

        stem = draft_result.get("stem", "")
        option_A = options_result.get("option_A", "")
        option_B = options_result.get("option_B", "")
        option_C = options_result.get("option_C", "")
        option_D = options_result.get("option_D", "")

        solution_parts = []
        for key in ("correct_answer", "explanation", "solution_steps"):
            val = solution_result.get(key, "")
            if val:
                solution_parts.append(f"- **{key}**: {val}")
        solution_md = "\n".join(solution_parts) if solution_parts else "（无解析）"

        prompt = SC_REVIEWER_PROMPT.format(
            stem=stem,
            option_A=option_A,
            option_B=option_B,
            option_C=option_C,
            option_D=option_D,
            solution_md=solution_md,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("review", "fix_instruction"))
        if result:
            # Handle fix_instruction as dict from JSON
            data = try_parse_json_object(text)
            if data and isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            return result
        return {}


# ── SingleChoiceAssemblerAgent ─────────────────────────────────


# ── PostReviewAgent ──────────────────────────────────────────


class PostReviewAgent(BaseAgent):
    """Blueprint-driven post-review: checks solution correctness + blueprint compliance."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="post_reviewer",
                phase="post_review",
                output_format="markdown",
                output_key="post_review_result",
                max_tokens=8192,
                enable_thinking=False,
                max_retries=1,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.QUESTION_REVIEW,
                expected_output_format=(
                    "## post_review\n"
                    "- **status**: pass|needs_fix\n"
                    "- **solution_correctness**: pass|fail\n"
                    "- **blueprint_compliance**: pass|fail\n"
                    "- **difficulty_match**: pass|fail\n"
                    "- **overall_quality**: 1-10\n\n"
                    "## fix_instruction\n"
                    "- **fix_target**: ...\n"
                    "- **fix_detail**: ..."
                ),
                system_prompt="你是一位408考研出题对抗终审专家。你拿着出题蓝图，对照生成的题目，判定是否符合蓝图要求。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import POST_REVIEW_PROMPT

        draft_result = blackboard.get("sc_draft_result", blackboard.get("sc_design", {}))
        options_result = blackboard.get("sc_options_result", blackboard.get("sc_options", {}))
        solution_result = blackboard.get("sc_solution_result", {})
        review_result = blackboard.get("review", {})
        question_design = blackboard.get("question_design", {})
        solver_result = blackboard.get("solver_result", {})
        slot_blueprint = blackboard.get("slot_blueprint", {})
        experience_card = blackboard.get("experience_card", "")
        is_sc = blackboard.get("is_sc", True)

        stem = draft_result.get("stem", "")
        solution_md = solution_result.get("explanation", "")
        if solution_result.get("solution_steps"):
            solution_md += "\n步骤: " + solution_result["solution_steps"]

        design_md = question_design.get("raw_design_md", "")
        if not design_md:
            design_md = json.dumps(question_design, ensure_ascii=False, indent=2)

        solver_output = "（无求解输出）"
        outputs = solver_result.get("outputs", [])
        if outputs:
            solver_output = outputs[-1][:3000] if isinstance(outputs[-1], str) else str(outputs[-1])[:3000]

        review_summary = json.dumps({
            "status": review_result.get("status", "unknown"),
            "comment": review_result.get("comment", ""),
        }, ensure_ascii=False, indent=2)

        # Blueprint formatting
        slot_blueprint_md = json.dumps(slot_blueprint, ensure_ascii=False, indent=2) if slot_blueprint else "（无蓝图）"

        # Extract K1-K5 radar section from experience card
        experience_card_radar = "（无经验卡）"
        if experience_card:
            lines = experience_card.split("\n")
            radar_lines = []
            in_radar = False
            for line in lines:
                if "认知雷达" in line:
                    in_radar = True
                if in_radar:
                    radar_lines.append(line)
                    if line.strip().startswith("典型形状") or line.strip().startswith("雷达形状"):
                        in_radar = False
            if radar_lines:
                experience_card_radar = "\n".join(radar_lines)
            else:
                experience_card_radar = experience_card[:800]

        # Conditional: question body + type-specific checks + fix_target options
        if is_sc:
            question_body = (
                f"- **题干**: {stem}\n"
                f"- **选项A**: {options_result.get('option_A', '')}\n"
                f"- **选项B**: {options_result.get('option_B', '')}\n"
                f"- **选项C**: {options_result.get('option_C', '')}\n"
                f"- **选项D**: {options_result.get('option_D', '')}"
            )
            type_specific_checks = (
                "11. **排除法攻击**: 用排除法重新检查每个选项，看是否能得到相同结论。是否有不止一个选项\"无法排除\"？\n"
                "12. **干扰项质量攻击**: 错误选项是否\"一秒排除\"？正确选项是否\"太明显\"？每个干扰项是否真的有迷惑性？\n"
                "13. **选项格式**: 选项格式是否符合蓝图 option_style 要求（数字结果/概念判断/代码分析）？"
            )
            fix_target_options = "solution 或 stem 或 options 或 none"
        else:
            sub_qs = draft_result.get("sub_questions", [])
            sub_q_lines = ""
            if sub_qs:
                for i, sq in enumerate(sub_qs, 1):
                    sub_q_lines += f"- **子问{i}**: {sq}\n"
            else:
                sub_q_lines = "- （无子问题列表）\n"
            question_body = (
                f"- **题干**: {stem}\n"
                f"{sub_q_lines}"
                f"- **注意**: 本题为综合应用题，无ABCD选项"
            )
            type_specific_checks = (
                "11. **子问题完整性**: 子问题数量是否与蓝图 sub_questions 要求一致？\n"
                "12. **答案格式**: 答案格式是否符合蓝图 answer_format 要求？\n"
                "13. **求解条件充分性**: 每个子问题是否都有充分的条件可以独立求解？"
            )
            fix_target_options = "solution 或 stem 或 none"

        return POST_REVIEW_PROMPT.format(
            slot_blueprint_md=slot_blueprint_md,
            experience_card_radar=experience_card_radar,
            question_design_md=design_md or "（无设计方案）",
            question_body=question_body,
            solution_md=solution_md or "（无解析）",
            solver_output=solver_output,
            review_summary=review_summary,
            type_specific_checks=type_specific_checks,
            fix_target_options=fix_target_options,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("post_review", "fix_instruction"))
        if result:
            # Handle fix_instruction as dict from JSON
            data = try_parse_json_object(text)
            if data and isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            return result
        return {}

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        status = str(parsed.get("status", "")).strip().lower()
        if status not in {"pass", "needs_fix"}:
            return False, "status must be pass or needs_fix"
        return True, ""


# ── QuestionSummaryAgent ─────────────────────────────────────


class QuestionSummaryAgent(BaseAgent):
    """Consolidate all pipeline outputs into a clean, structured final summary."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="question_summary",
                phase="summary",
                output_format="markdown",
                output_key="question_summary",
                max_tokens=8192,
                enable_thinking=False,
                max_retries=1,
                required_fields=["final_stem", "correct_answer"],
                repair_max_retries=1,
                role_type=RoleType.SUMMARIZER,
                expected_output_format=(
                    "## summary\n"
                    "- **final_stem**: ...\n"
                    "- **final_explanation**: ...\n"
                    "- **correct_answer**: ...\n"
                    "- **knowledge_tags**: ...\n"
                    "- **difficulty_summary**: ...\n"
                    "- **quality_notes**: ..."
                ),
                system_prompt="你是一位408考研题目整理专家，负责将题目各部分汇总为规范的最终输出。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import QUESTION_SUMMARY_PROMPT

        draft_result = blackboard.get("sc_draft_result", blackboard.get("sc_design", {}))
        options_result = blackboard.get("sc_options_result", blackboard.get("sc_options", {}))
        solution_result = blackboard.get("sc_solution_result", {})
        solver_result = blackboard.get("solver_result", {})
        review_result = blackboard.get("review", {})
        is_sc = blackboard.get("is_sc", True)

        stem = draft_result.get("stem", "")
        solution_md = solution_result.get("explanation", "")
        if solution_result.get("solution_steps"):
            solution_md += "\n步骤: " + solution_result["solution_steps"]

        solver_process = "（无求解过程）"
        if solver_result:
            outputs = solver_result.get("outputs", [])
            if outputs:
                solver_process = outputs[-1][:2000] if isinstance(outputs[-1], str) else str(outputs[-1])[:2000]

        review_summary = f"技术审核: {review_result.get('status', 'unknown')}"
        post_review = blackboard.get("post_review_result", {})
        if post_review:
            review_summary += f" | 终审: {post_review.get('status', 'unknown')} | 质量: {post_review.get('overall_quality', '?')}/10"

        if is_sc:
            options_md = "\n".join(
                f"- {opt}: {options_result.get(f'option_{opt}', '')}"
                for opt in ("A", "B", "C", "D")
            )
        else:
            sub_qs = draft_result.get("sub_questions", [])
            if sub_qs:
                options_md = "综合应用题（无ABCD选项）\n子问题：\n" + "\n".join(
                    f"- ({i}) {sq}" for i, sq in enumerate(sub_qs, 1)
                )
            else:
                options_md = "综合应用题（无ABCD选项）"

        return QUESTION_SUMMARY_PROMPT.format(
            stem=stem,
            options_md=options_md,
            solution_md=solution_md or "（无解析）",
            solver_process=solver_process,
            review_summary=review_summary,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        result = parse_structured_output(text, md_sections=("summary",))
        if result:
            return result
        return {}


class SingleChoiceAssemblerAgent(BaseAgent):
    """Merge all pieces into final output dict (no LLM call)."""

    def __init__(self):
        # Pass a dummy config — we override execute so no LLM is called
        super().__init__(
            AgentConfig(
                name="sc_assembler",
                phase="sc_assemble",
                output_format="text",
                output_key="sc_final_question",
                max_tokens=0,
                enable_thinking=False,
                max_retries=0,
                role_type=RoleType.SUMMARIZER,
            ),
            _DummyGateway(),
        )

    def build_input(self, blackboard: Blackboard) -> str:
        return ""

    def parse_output(self, raw: Any) -> Any:
        return raw

    async def execute(self, blackboard: Blackboard) -> Any:
        blueprint = blackboard.get("current_blueprint", {})
        draft_result = blackboard.get("sc_draft_result", {})
        options_result = blackboard.get("sc_options_result", {})
        solution_result = blackboard.get("sc_solution_result", {})

        assembled = {
            "slot_id": blueprint.get("slot_id", ""),
            "stem": draft_result.get("stem", ""),
            "option_A": options_result.get("option_A", ""),
            "option_B": options_result.get("option_B", ""),
            "option_C": options_result.get("option_C", ""),
            "option_D": options_result.get("option_D", ""),
            "correct_answer": solution_result.get("correct_answer", options_result.get("correct_answer", "")),
            "explanation": solution_result.get("explanation", ""),
            "solution_steps": solution_result.get("solution_steps", ""),
            "difficulty_self_assessment": solution_result.get("difficulty_self_assessment", ""),
            "trap_description": solution_result.get("trap_description", ""),
            "knowledge_points": solution_result.get("knowledge_points", ""),
            "generation_time_s": blackboard.get("sc_generation_time_s", 0.0),
            "pipeline_type": "single_choice_v2",
        }

        await blackboard.update(
            agent_name="sc_assembler",
            output=assembled,
            phase="sc_assemble",
            output_key="sc_final_question",
        )
        return assembled


