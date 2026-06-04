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
                step_name="design_sc",
                output_format="markdown",
                output_key="sc_draft_result",
                max_tokens=16384,
                enable_thinking=False,
                max_retries=2,
                required_fields=["stem"],
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                tools=[],  # Designer is pure NL — no tools
                max_tool_rounds=0,
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

        question_design = blackboard.get("design", {})
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

        # Legacy: also check blackboard for fix_instruction
        fix_instruction = blackboard.get("fix_instruction", "")
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
                    build_408_tools(),
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
                        skill_names=["solve-408"],
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
                step_name="options",
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

        draft_result = blackboard.get("design", {})
        question_design = blackboard.get("design", {})
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


# ── SCSolutionFormatterAgent ───────────────────────────────────


class SCSolutionFormatterAgent(BaseAgent):
    """Format clean solution from solver result — no re-solving."""

    def __init__(self, llm_backend):
        super().__init__(
            AgentConfig(
                name="sc_solution_formatter",
                phase="sc_solution_format",
                step_name="format_sc",
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

        draft_result = blackboard.get("design", {})
        options_result = blackboard.get("options", {})
        solver_result = blackboard.get("solver_result", {})

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
                step_name="review",
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

        draft_result = blackboard.get("design", {})
        options_result = blackboard.get("options", {})
        solution_result = blackboard.get("solution", {})
        blueprint = blackboard.get("blueprint", {})

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

        draft_result = blackboard.get("design", {})
        options_result = blackboard.get("options", {})
        solution_result = blackboard.get("solution", {})
        review_result = blackboard.get("review", {})
        question_design = blackboard.get("design", {})
        solver_result = blackboard.get("solver_result", {})
        slot_blueprint = blackboard.get("blueprint", {})
        experience_card = blackboard.get("experience", {})
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

        draft_result = blackboard.get("design", {})
        options_result = blackboard.get("options", {})
        solution_result = blackboard.get("solution", {})
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
        blueprint = blackboard.get("blueprint", {})
        draft_result = blackboard.get("design", {})
        options_result = blackboard.get("options", {})
        solution_result = blackboard.get("solution", {})

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


# ═══════════════════════════════════════════════════════════════
# Merged SC Design Agent (replaces Draft + Options + Gate)
# ═══════════════════════════════════════════════════════════════


def _dump_sc_blueprint_md(blueprint: dict) -> str:
    """Convert SC blueprint to readable Markdown (3 core fields only)."""
    if not blueprint:
        return "（无特殊蓝图要求）"

    lines = []
    lines.append(f"- **核心考点**: {blueprint.get('primary_target_name', '未指定')}")
    lines.append(f"- **知识域**: {blueprint.get('target_family', '未指定')}")
    lines.append(f"- **目标难度**: {blueprint.get('difficulty_level', blueprint.get('target_difficulty', '未指定'))}")
    lines.append(f"- **K值目标**: {blueprint.get('k_target', '未指定')}")
    lines.append(f"- **难度说明**: {blueprint.get('difficulty_rationale', '无')}")
    lines.append(f"- **考察模式**: {blueprint.get('examination_mode', '未指定')}")

    return "\n".join(lines)


def _extract_sc_philosophy(slot_id: str) -> str:
    """Extract slot philosophy for SC merged design prompt."""
    import os as _os
    path = _os.path.join("data", "slots", f"{slot_id}_slot.md")
    if not _os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract key sections
    targets = ["认知雷达锚点", "考察理念", "设计理念", "出题指导"]
    lines = content.split("\n")
    parts = []

    for target in targets:
        capturing = False
        match_level = 0
        result = []
        for line in lines:
            hl = 0
            if line.startswith("# "):
                hl = 1
            elif line.startswith("## "):
                hl = 2
            elif line.startswith("### "):
                hl = 3

            if not capturing and hl >= 2 and target in line:
                capturing = True
                match_level = hl
                result.append(line)
                continue
            if capturing:
                if hl > 0 and hl <= match_level:
                    break
                result.append(line)

        text = "\n".join(result).strip()
        if text and len(text) > 20:
            parts.append(text)

    return "\n\n---\n\n".join(parts) if parts else ""


class MergedSCDesignAgent(BaseAgent):
    """Merged SC design: stem + 4 options + answer + self-check in one LLM call.

    Replaces SingleChoiceDraftAgent + OptionAndDistractorAgent + StemBlueprintGate.
    Pure NL — no tools. Parameter verification delegated to solver downstream.
    """

    def __init__(self, llm_backend, *, max_tokens: int = 16384):
        super().__init__(
            AgentConfig(
                name="merged_sc_design",
                phase="design",
                step_name="merged_sc_design",
                output_format="markdown",
                output_key="sc_merged_design",
                max_tokens=max_tokens,
                enable_thinking=False,
                max_retries=2,
                required_fields=["stem", "option_A", "option_B", "option_C", "option_D", "correct_answer"],
                repair_on_parse_failure=True,
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                tools=[],
                max_tool_rounds=0,
                expected_output_format=(
                    "## 题目\n"
                    "- **stem**: ...\n"
                    "- **given_conditions**: [...]\n\n"
                    "## 选项\n"
                    "- **option_A**: ...\n"
                    "- **option_B**: ...\n"
                    "- **option_C**: ...\n"
                    "- **option_D**: ...\n"
                    "- **correct_answer**: A/B/C/D\n\n"
                    "## 干扰策略\n"
                    "- **distractor_intent_A**: ...\n\n"
                    "## 自检清单\n"
                    "- **blueprint_compliance**: PASS/FAIL"
                ),
                system_prompt=(
                    "你是一位408考研出题专家。你一次完成选择题的题干、选项和干扰策略设计。"
                    "严格按markdown格式输出，自检清单全部PASS后再输出。"
                ),
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SC_MERGED_DESIGN_PROMPT, K_RADAR_DEFINITIONS

        blueprint = blackboard.get("current_blueprint", {})
        slot_id = blueprint.get("slot_id", "unknown")
        blueprint_md = _dump_sc_blueprint_md(blueprint)
        slot_philosophy = _extract_sc_philosophy(slot_id)

        prompt = SC_MERGED_DESIGN_PROMPT.format(
            slot_id=slot_id,
            blueprint_md=blueprint_md,
            k_definitions=K_RADAR_DEFINITIONS,
            slot_philosophy=slot_philosophy or "（未找到题位设计哲学）",
        )

        fix_instruction = blackboard.get("stem_fix_instruction", "")
        has_fix = bool(self._memory and any(
            m.get("role") == "review" for m in self._memory
        ))
        if fix_instruction:
            has_fix = True

        if has_fix:
            prompt += (
                "\n\n## 重要提示\n"
                "你正在**修改**前一轮生成的题目，不是重新出一道不同的题。\n"
                "请查看下方历史记录中的审查反馈，针对审核指出的具体问题进行精确修改。\n"
                "保持题目整体结构和考察方向不变，仅修正被指出的问题。\n"
            )
            if fix_instruction:
                prompt += f"\n补充修复指令：{fix_instruction}\n"

        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        # Strip code fences
        stripped = re.sub(r"^```(?:\w+)?\s*\n?", "", text)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        if len(stripped.strip()) > 50:
            text = stripped

        result = parse_structured_output(text, md_sections=("题目", "选项", "干扰策略", "自检清单"))
        if not result:
            all_sections = parse_md_sections(text)
            for _name, sec in all_sections.items():
                if isinstance(sec, dict) and sec.get("stem"):
                    result.update(sec)
                    break
        if not result:
            data = try_parse_json_object(text)
            if data and isinstance(data, dict):
                result = data

        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        stem = str(parsed.get("stem", ""))
        if "```" in stem or re.search(r"\b(int\s+main|#include|def\s+\w+\(|print\s*\()", stem):
            return False, "stem contains code instead of a question"
        if len(stem.strip()) < 8:
            return False, "stem is too short"
        answer = str(parsed.get("correct_answer", "")).strip().upper()
        if answer not in ("A", "B", "C", "D"):
            return False, f"correct_answer must be A/B/C/D, got '{answer}'"
        return True, ""


# ═══════════════════════════════════════════════════════════════
# Merged Review + Fix Agent (replaces verify + format + final_review + final_fixer)
# ═══════════════════════════════════════════════════════════════


class MergedReviewFixAgent(BaseAgent):
    """Merged SC review + fix + format: one agent call with python_exec tool.

    Reviews the question, verifies answer with code, fixes issues, writes explanation.
    Replaces _run_solver_verify + _format_sc + _run_final_review + _run_final_fixer.
    """

    def __init__(self, llm_backend, *, max_tokens: int = 12288):
        from core_new.agent_tools import PYTHON_EXEC_TOOL
        super().__init__(
            AgentConfig(
                name="merged_review_fix",
                phase="review_fix",
                step_name="merged_review_fix",
                output_format="markdown",
                output_key="sc_review_fix_result",
                max_tokens=max_tokens,
                enable_thinking=False,
                max_retries=1,
                required_fields=["status", "verified_answer", "correct_answer", "explanation"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                tools=[PYTHON_EXEC_TOOL],
                max_tool_calls=3,
                max_tool_rounds=3,
                expected_output_format=(
                    "## 审查结果\n"
                    "- **status**: pass|needs_fix\n"
                    "- **verified_answer**: A/B/C/D\n\n"
                    "## 修复内容\n"
                    "- **fix_target**: none|stem|options|answer\n\n"
                    "## 解析\n"
                    "- **correct_answer**: A/B/C/D\n"
                    "- **explanation**: ...\n"
                    "- **key_steps**: ..."
                ),
                system_prompt=(
                    "你是一位408考研审核与修复专家。你用python_exec验证答案，审查题目质量，"
                    "直接修复问题并编写解析。严格按markdown格式输出。"
                ),
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_MERGED_REVIEW_FIX_PROMPT

        design = blackboard.get("design", {})
        options = blackboard.get("options", {})
        solver_dict = blackboard.get("solver_dict", {})

        prompt = SC_MERGED_REVIEW_FIX_PROMPT.format(
            stem=design.get("stem", ""),
            option_A=options.get("option_A", ""),
            option_B=options.get("option_B", ""),
            option_C=options.get("option_C", ""),
            option_D=options.get("option_D", ""),
            solver_result_json=json.dumps(solver_dict, ensure_ascii=False, indent=2) if solver_dict else "{}",
        )

        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        sections = parse_md_sections(text)

        result: Dict[str, Any] = {}
        for section_name, section_data in sections.items():
            if isinstance(section_data, dict):
                result.update(section_data)

        # Normalize status
        status = result.get("status", "pass")
        if isinstance(status, str):
            status = status.strip().lower()
        result["status"] = status

        # Parse fixed_options if string
        fixed_opts = result.get("fixed_options", "{}")
        if isinstance(fixed_opts, str):
            try:
                result["fixed_options"] = json.loads(fixed_opts)
            except json.JSONDecodeError:
                result["fixed_options"] = {}

        # Parse key_steps from semicolon-separated string
        key_steps = result.get("key_steps", "")
        if isinstance(key_steps, str) and key_steps:
            result["key_steps_list"] = [s.strip() for s in key_steps.split(";") if s.strip()]

        # Fallback regex for critical fields
        if "status" not in result or not result["status"]:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if m:
                result["status"] = m.group(1).strip().lower()

        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        status = str(parsed.get("status", "")).strip().lower()
        if status not in ("pass", "needs_fix"):
            return False, "status must be pass or needs_fix"
        return True, ""


# ═══════════════════════════════════════════════════════════════
# V2: Outline-driven 3-stage pipeline agents
# ═══════════════════════════════════════════════════════════════


def _extract_available_patterns(experience_card_md: str) -> str:
    """Extract pattern names and frequency from experience card."""
    if not experience_card_md:
        return "（无经验卡）"
    patterns = []
    for line in experience_card_md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## 模式") or stripped.startswith("## 考察模式分布"):
            patterns.append(stripped.lstrip("# ").strip())
        elif "出现频率" in stripped and "**" in stripped:
            patterns.append(f"  {stripped}")
    return "\n".join(patterns) if patterns else "（未找到考察模式）"


def _read_experience_pattern(experience_card_md: str, pattern_name: str) -> str:
    """Extract a specific pattern's details from experience card."""
    if not experience_card_md:
        return "（无经验卡数据）"
    lines = experience_card_md.split("\n")
    capturing = False
    result = []
    for line in lines:
        stripped = line.strip()
        # Check if this is the start of the target pattern
        if stripped.startswith("## 模式") and pattern_name.lower() in stripped.lower():
            capturing = True
            result.append(stripped)
            continue
        # Check if this is a year-based lookup
        if pattern_name.isdigit() and stripped.startswith("### " + pattern_name):
            capturing = True
            result.append(stripped)
            continue
        # Stop at next ## section
        if capturing and stripped.startswith("## ") and not stripped.startswith("## 模式"):
            break
        if capturing:
            result.append(line)
    return "\n".join(result) if result else f"（未找到模式: {pattern_name}）"


class SCQuestionAgent(BaseAgent):
    """Stage 1: Analyze experience + Design + Generate question (uses read_workspace_file for experience)."""

    ALLOWED_TOOLS = ["python_exec"]

    def __init__(self, llm_backend, *, experience_card_path: str = "", max_tokens: int = 16384):
        self._experience_card_path = experience_card_path
        super().__init__(
            AgentConfig(
                name="sc_question",
                phase="question",
                output_format="markdown",
                output_key="sc_question",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["stem", "option_A", "option_B", "option_C", "option_D", "correct_answer"],
                role_type=RoleType.GENERATOR,
                system_prompt=(
                    "你是一位408考研出题专家。按三步流程出题：1.选知识点 2.设计题目 3.代码验证并调整。"
                    "使用python_exec工具验证数值计算，代码结果优先。严格按markdown格式输出最终题目。"
                ),
            ),
            llm_backend,
        )

    async def execute(self, blackboard: Blackboard):
        start = time.monotonic()

        for attempt in range(self.config.max_retries + 1):
            try:
                prompt = self.build_input(blackboard)
                loop = Edu408AgentLoop(
                    self.llm,
                    build_408_tools(),
                    workspace=DEFAULT_WORKSPACE,
                    max_iterations=8,
                    max_tokens=self.config.max_tokens,
                    enable_thinking=self.config.enable_thinking,
                    execution_policy=self.execution_policy,
                )
                result = await asyncio.wait_for(
                    loop.run(
                        self._runtime_task(prompt),
                        allowed_tools=self.ALLOWED_TOOLS,
                        skill_names=["solve-408"],
                        extra_system=self._runtime_system(),
                    ),
                    timeout=self.config.timeout_s,
                )

                if result.final.lower().startswith("error:"):
                    raise RuntimeError(result.final)

                parsed = self.parse_output(result.final)

                ok, detail = self.validate_parsed(parsed)
                if not ok:
                    logger.warning("SCQuestion validation failed (attempt %d): %s", attempt + 1, detail)
                    last_error = detail
                    continue

                elapsed = time.monotonic() - start
                parsed["_elapsed_s"] = round(elapsed, 1)
                parsed["_attempts"] = attempt + 1
                blackboard.set(self.config.output_key, parsed)
                return parsed

            except Exception as exc:
                last_error = str(exc)
                logger.warning("SCQuestion error (attempt %d): %s", attempt + 1, exc)

        blackboard.set(self.config.output_key, {"error": last_error})
        return {"error": last_error}

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SC_QUESTION_PROMPT

        outline_entry = blackboard.get("outline_entry", {})
        slot_id = outline_entry.get("slot_id", "unknown")

        # Single merged document: outline requirements + mode details + experience
        reference_doc = blackboard.get("assembled_experience_doc", "")
        if not reference_doc:
            reference_doc = "（无参考文档）"

        prompt = SC_QUESTION_PROMPT.format(
            slot_id=slot_id,
            reference_doc=reference_doc,
        )

        return prompt

    def _runtime_task(self, prompt: str) -> str:
        return (
            f"{prompt}\n\n"
            "Runtime requirements:\n"
            "1. You may use python_exec to verify calculations.\n"
            "2. The final answer must be markdown, not a tool call.\n"
            "3. Follow the three-step workflow: select knowledge → design question → code verify.\n"
        )

    @staticmethod
    def _runtime_system() -> str:
        return (
            "You are running as a question generation agent inside the Edu408 runtime. "
            "Use python_exec for any calculation verification. "
            "Output final markdown when done."
        )

    def _summarize_contract(self, contract: dict) -> str:
        """Create a compact summary of slot contract for the prompt."""
        if not contract:
            return "（无题位约束）"
        lines = []
        for key in ("preferred_subject", "preferred_target_families", "preferred_paper_roles",
                     "should_be", "should_not_be", "slot_guidance"):
            val = contract.get(key)
            if val and val != "无":
                lines.append(f"- **{key}**: {val}")
        # K-value anchors
        for k in ("K1", "K2", "K3", "K4", "K5"):
            mode = contract.get(f"{k}_mode")
            rng = contract.get(f"{k}_range")
            if mode:
                lines.append(f"- **{k}**: mode={mode}, range={rng or '?'}")
        return "\n".join(lines) if lines else "（无特殊约束）"

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)

        # Strategy 1: parse structured markdown sections
        parsed = parse_structured_output(
            text,
            md_sections=("题目", "选项", "干扰策略", "验证结果"),
        )

        # Flatten section dicts
        result: Dict[str, Any] = {}
        for section_name, section_data in parsed.items():
            if isinstance(section_data, dict):
                result.update(section_data)
            else:
                result[section_name] = section_data

        # If structured parse got nothing, try all ## sections
        if not result:
            all_sections = parse_md_sections(text)
            for _name, sec in all_sections.items():
                if isinstance(sec, dict):
                    result.update(sec)

        # Fallback regex for critical fields
        for field in ("stem", "option_A", "option_B", "option_C", "option_D",
                       "correct_answer", "code_verified", "verified_answer",
                       "adjustment_summary", "difficulty_self_assessment",
                       "knowledge_points", "selected_knowledge_rationale",
                       "option_style_used"):
            if field not in result or not result[field]:
                m = re.search(rf"\*\*{field}\*\*[:：]\s*(.+?)(?=\n-\s+\*\*|\n##|\Z)", text, re.DOTALL)
                if m:
                    result[field] = m.group(1).strip()

        # Fallback regex for distractor intents
        for letter in "ABCD":
            key = f"distractor_intent_{letter}"
            if key not in result or not result[key]:
                m = re.search(rf"\*\*{key}\*\*[:：]\s*(.+?)(?=\n-\s+\*\*|\n##|\Z)", text, re.DOTALL)
                if m:
                    result[key] = m.group(1).strip()

        return result


class SCCodeVerifyAgent(BaseAgent):
    """Stage 2: Code verification — python_exec to verify answer, code takes precedence."""

    ALLOWED_TOOLS = ["python_exec"]

    def __init__(self, llm_backend, *, max_tokens: int = 4096):
        super().__init__(
            AgentConfig(
                name="sc_code_verify",
                phase="code_verify",
                output_format="markdown",
                output_key="sc_code_verify",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["status", "verified_answer"],
                role_type=RoleType.VERIFIER,
                system_prompt="你是一位408考研题目校验专家。用代码独立验证答案，代码结果优先。",
            ),
            llm_backend,
        )

    async def execute(self, blackboard: Blackboard):
        start = time.monotonic()
        prompt = self.build_input(blackboard)

        loop = Edu408AgentLoop(
            self.llm,
            build_408_tools(),
            workspace=DEFAULT_WORKSPACE,
            max_iterations=3,
            max_tokens=self.config.max_tokens,
            enable_thinking=self.config.enable_thinking,
            execution_policy=self.execution_policy,
        )
        result = await asyncio.wait_for(
            loop.run(
                self._runtime_task(prompt),
                allowed_tools=self.ALLOWED_TOOLS,
                extra_system=self._runtime_system(),
            ),
            timeout=self.config.timeout_s,
        )

        parsed = self.parse_output(result.final)
        parsed["_elapsed_s"] = round(time.monotonic() - start, 1)
        blackboard.set(self.config.output_key, parsed)
        return parsed

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SC_CODE_VERIFY_PROMPT

        question = blackboard.get("sc_question", {})
        return SC_CODE_VERIFY_PROMPT.format(
            stem=question.get("stem", ""),
            option_A=question.get("option_A", ""),
            option_B=question.get("option_B", ""),
            option_C=question.get("option_C", ""),
            option_D=question.get("option_D", ""),
            claimed_answer=question.get("correct_answer", "?"),
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        parsed = parse_structured_output(text)
        result: Dict[str, Any] = {}
        for section_name, section_data in parsed.items():
            if isinstance(section_data, dict):
                result.update(section_data)
        # Fallback
        if "status" not in result:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if m:
                result["status"] = m.group(1).strip().lower()
        if "verified_answer" not in result:
            m = re.search(r"\*\*verified_answer\*\*[:：]\s*([A-D])", text)
            if m:
                result["verified_answer"] = m.group(1)
        return result


class SCReviewAgent(BaseAgent):
    """Stage 3: Adversarial review — pass/needs_fix with final explanation."""

    ALLOWED_TOOLS = ["python_exec"]

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="sc_review",
                phase="review",
                output_format="markdown",
                output_key="sc_review",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["status", "verified_answer"],
                role_type=RoleType.REVIEWER,
                system_prompt="你是一位408考研出题对抗审核员。主动寻找题目缺陷，无法攻破时才判pass。",
            ),
            llm_backend,
        )

    async def execute(self, blackboard: Blackboard):
        start = time.monotonic()
        prompt = self.build_input(blackboard)

        loop = Edu408AgentLoop(
            self.llm,
            build_408_tools(),
            workspace=DEFAULT_WORKSPACE,
            max_iterations=3,
            max_tokens=self.config.max_tokens,
            enable_thinking=self.config.enable_thinking,
            execution_policy=self.execution_policy,
        )
        result = await asyncio.wait_for(
            loop.run(
                self._runtime_task(prompt),
                allowed_tools=self.ALLOWED_TOOLS,
                extra_system=self._runtime_system(),
            ),
            timeout=self.config.timeout_s,
        )

        parsed = self.parse_output(result.final)
        parsed["_elapsed_s"] = round(time.monotonic() - start, 1)
        blackboard.set(self.config.output_key, parsed)
        return parsed

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SC_REVIEW_PROMPT

        question = blackboard.get("sc_question", {})
        verify_result = blackboard.get("sc_code_verify", {})
        outline_md = blackboard.get("outline_entry_md", "")

        return SC_REVIEW_PROMPT.format(
            outline_entry_md=outline_md,
            stem=question.get("stem", ""),
            option_A=question.get("option_A", ""),
            option_B=question.get("option_B", ""),
            option_C=question.get("option_C", ""),
            option_D=question.get("option_D", ""),
            code_verify_result=(
                f"status={verify_result.get('status', '?')}, "
                f"verified_answer={verify_result.get('verified_answer', '?')}, "
                f"code_summary={verify_result.get('code_summary', '?')}"
            ),
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        parsed = parse_structured_output(text)
        result: Dict[str, Any] = {}
        for section_name, section_data in parsed.items():
            if isinstance(section_data, dict):
                result.update(section_data)
        # Normalize status
        status = result.get("status", "pass")
        if isinstance(status, str):
            status = status.strip().lower()
        result["status"] = status
        # Parse key_steps
        key_steps = result.get("key_steps", "")
        if isinstance(key_steps, str) and key_steps:
            result["key_steps_list"] = [s.strip() for s in key_steps.split(";") if s.strip()]
        # Fallback
        if "status" not in result:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if m:
                result["status"] = m.group(1).strip().lower()
        return result
