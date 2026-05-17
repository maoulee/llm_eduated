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
from core_new.agents.codeact_solver import CodeActSolverAgent, SolverResult
from core_new.blackboard import Blackboard
from core_new.edu408_runtime.tools import DEFAULT_WORKSPACE, build_408_tools
from core_new.experience_view import build_design_experience_view
from core_new.llm_gateway import LLMGateway, LLMResult
from core_new.markdown_parser import try_parse_json_object

logger = logging.getLogger(__name__)


# ── Markdown parsing helpers (local copy) ──────────────────────


def _parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    """Parse '- **key**: value' lines into a dict."""
    result: Dict[str, Any] = {}
    current_key = None

    for line in lines:
        m = re.match(r"^- \*\*(.+?)\*\*:\s*(.*)", line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            if value and (value.startswith("{") or value.startswith("[")):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            result[key] = value
            current_key = key
        elif line.startswith("  ") and current_key and current_key in result:
            existing = result[current_key]
            if isinstance(existing, str):
                result[current_key] = existing + "\n" + line.strip()
        elif current_key and current_key in result and isinstance(result[current_key], str):
            result[current_key] = result[current_key] + "\n" + line

    return result


def _parse_md_sections(text: str) -> Dict[str, Any]:
    """Split markdown by ## headers, parse each section's key-value pairs."""
    sections: Dict[str, Any] = {}
    current_name = None
    current_lines: List[str] = []

    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_name:
                sections[current_name] = _parse_md_kv(current_lines)
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name:
        sections[current_name] = _parse_md_kv(current_lines)

    return sections


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
                max_tokens=800,
                enable_thinking=True,
                max_retries=2,
                required_fields=["stem"],
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                expected_output_format=(
                    "## stem\n"
                    "- **stem**: question stem only, no options, no answer, no code block\n"
                    "- **stem_length**: short|medium|long\n"
                    "- **condition_count**: integer\n"
                    "- **reasoning_hint**: one sentence"
                ),
                system_prompt="你是一位408考研出题专家，擅长根据蓝图精确生成题干。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.single_choice_prompts import SC_DRAFT_PROMPT

        blueprint = blackboard.get("current_blueprint", {})
        slot_id = blueprint.get("slot_id", "Q1")
        experience_card = build_design_experience_view(blackboard.read("experience_card", ""))

        return SC_DRAFT_PROMPT.format(
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            experience_card_md=experience_card,
        )

    def parse_output(self, raw: Any) -> Any:
        data = try_parse_json_object(str(raw))
        if data:
            nested = data.get("stem")
            if isinstance(nested, dict):
                return nested
            if "stem" in data:
                return data
        sections = _parse_md_sections(str(raw))
        result = sections.get("stem", {})
        return result

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

                raw_text, parsed = await self._parse_validate_repair(
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
                max_tokens=800,
                enable_thinking=True,
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
        blueprint = blackboard.get("current_blueprint", {})
        stem = draft_result.get("stem", "")

        return SC_OPTIONS_PROMPT.format(
            stem=stem,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        data = try_parse_json_object(str(raw))
        if data:
            result = {}
            for key in ("options", "distractors", "answer"):
                if isinstance(data.get(key), dict):
                    result.update(data[key])
            if any(f"option_{letter}" in data for letter in "ABCD"):
                result.update(data)
            if result:
                return result
        sections = _parse_md_sections(str(raw))
        result = {}
        if "options" in sections:
            result.update(sections["options"])
        if "distractors" in sections:
            result.update(sections["distractors"])
        if "answer" in sections:
            result.update(sections["answer"])
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
                output_format="markdown",
                output_key="sc_solution_result",
                max_tokens=1200,
                enable_thinking=True,
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
        data = try_parse_json_object(str(raw))
        if data:
            nested = data.get("solution")
            if isinstance(nested, dict):
                return nested
            if "correct_answer" in data or "explanation" in data:
                return data
        sections = _parse_md_sections(str(raw))
        result = sections.get("solution", {})
        return result


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
                max_tokens=1200,
                enable_thinking=True,
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

        return SC_REVIEWER_PROMPT.format(
            stem=stem,
            option_A=option_A,
            option_B=option_B,
            option_C=option_C,
            option_D=option_D,
            solution_md=solution_md,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        data = try_parse_json_object(str(raw))
        if data:
            result = {}
            nested_review = data.get("review")
            if isinstance(nested_review, dict):
                result.update(nested_review)
            else:
                result.update(data)
            if isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            return result
        sections = _parse_md_sections(str(raw))
        result = sections.get("review", {})
        fix = sections.get("fix_instruction", {})
        result["fix_instruction"] = fix
        return result


# ── SingleChoiceAssemblerAgent ─────────────────────────────────


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
                enable_thinking=True,
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


class _DummyGateway:
    """Placeholder gateway for AssemblerAgent (never called)."""

    async def generate_text(self, *args, **kwargs):
        return None


# ── SingleChoicePipeline ───────────────────────────────────────


class SingleChoicePipeline:
    """Orchestrates the single-choice question generation pipeline.

    Sequence: Draft -> Options -> CodeActSolver -> Formatter -> Reviewer -> Assembler
    If reviewer says needs_fix, routes fix to specific agent (max 1 revision round).
    """

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway
        self.draft_agent = SingleChoiceDraftAgent(gateway)
        self.options_agent = OptionAndDistractorAgent(gateway)
        self.solver = CodeActSolverAgent(gateway)
        self.formatter_agent = SCSolutionFormatterAgent(gateway)
        self.reviewer_agent = SingleChoiceReviewerAgent(gateway)
        self.assembler_agent = SingleChoiceAssemblerAgent()

    async def run(
        self,
        slot_blueprint: Dict[str, Any],
        experience_card: str,
        gateway: LLMGateway | None = None,
    ) -> Dict[str, Any]:
        """Run the full pipeline and return the assembled question dict."""
        gw = gateway or self.gateway
        bb = Blackboard(
            task_id=f"sc_{slot_blueprint.get('slot_id', 'unknown')}_{int(time.time())}",
            task_type="single_choice",
        )

        # Seed blackboard
        await bb.set_input("current_blueprint", slot_blueprint)
        await bb.set_input("experience_card", experience_card)

        start_time = time.monotonic()

        # Step 1: Draft stem
        await self.draft_agent.execute(bb)
        draft_result = bb.get("sc_draft_result", {})
        if not draft_result.get("stem"):
            logger.error("Draft agent produced no stem")
            return self._empty_result(slot_blueprint)

        # Step 2: Generate options
        await self.options_agent.execute(bb)
        options_result = bb.get("sc_options_result", {})
        if not all(options_result.get(f"option_{c}") for c in "ABCD"):
            logger.error("Options agent produced incomplete options")
            return self._empty_result(slot_blueprint)

        # Step 3: Solve via CodeActSolver
        stem = draft_result.get("stem", "")
        options_dict = {
            "A": options_result.get("option_A", ""),
            "B": options_result.get("option_B", ""),
            "C": options_result.get("option_C", ""),
            "D": options_result.get("option_D", ""),
        }
        solver_result: SolverResult = await self.solver.solve(
            question_draft=stem,
            options=options_dict,
            question_type="single_choice",
        )
        await bb.update(
            agent_name="sc_solver",
            output=solver_result.to_dict(),
            phase="sc_solve",
            output_key="sc_solver_result",
        )

        # Step 4: Format solution
        await self.formatter_agent.execute(bb)

        # Step 5: Review
        await self.reviewer_agent.execute(bb)
        review_result = bb.get("sc_review_result", {})

        # Step 6: Handle revision (max 1 round)
        if review_result.get("status") == "needs_fix":
            fix_target = review_result.get("fix_instruction", {}).get("fix_target", "none")
            await self._apply_fix(bb, fix_target, review_result)

        # Record total generation time
        total_time = time.monotonic() - start_time
        await bb.update(
            agent_name="sc_timer",
            output=total_time,
            phase="sc_timer",
            output_key="sc_generation_time_s",
        )

        # Step 7: Assemble
        assembled = await self.assembler_agent.execute(bb)
        return assembled

    async def _apply_fix(
        self,
        bb: Blackboard,
        fix_target: str,
        review_result: Dict[str, Any],
    ) -> None:
        """Route fix to the specific agent based on review feedback. Max 1 round."""
        fix_detail = review_result.get("fix_instruction", {}).get("fix_detail", "")
        if not fix_detail:
            return

        if fix_target == "draft":
            logger.info("Revision: re-running draft agent")
            await self.draft_agent.execute(bb)
            await self.options_agent.execute(bb)
            # Re-solve with new stem + options
            draft_result = bb.get("sc_draft_result", {})
            options_result = bb.get("sc_options_result", {})
            options_dict = {
                "A": options_result.get("option_A", ""),
                "B": options_result.get("option_B", ""),
                "C": options_result.get("option_C", ""),
                "D": options_result.get("option_D", ""),
            }
            solver_result = await self.solver.solve(
                question_draft=draft_result.get("stem", ""),
                options=options_dict,
                question_type="single_choice",
            )
            await bb.update(
                agent_name="sc_solver",
                output=solver_result.to_dict(),
                phase="sc_solve",
                output_key="sc_solver_result",
            )
            await self.formatter_agent.execute(bb)

        elif fix_target == "options":
            logger.info("Revision: re-running options agent")
            await self.options_agent.execute(bb)
            options_result = bb.get("sc_options_result", {})
            draft_result = bb.get("sc_draft_result", {})
            options_dict = {
                "A": options_result.get("option_A", ""),
                "B": options_result.get("option_B", ""),
                "C": options_result.get("option_C", ""),
                "D": options_result.get("option_D", ""),
            }
            solver_result = await self.solver.solve(
                question_draft=draft_result.get("stem", ""),
                options=options_dict,
                question_type="single_choice",
            )
            await bb.update(
                agent_name="sc_solver",
                output=solver_result.to_dict(),
                phase="sc_solve",
                output_key="sc_solver_result",
            )
            await self.formatter_agent.execute(bb)

        elif fix_target == "solution":
            logger.info("Revision: re-running solution formatter")
            await self.formatter_agent.execute(bb)

        # else: fix_target == "none" or unrecognized, skip revision

    @staticmethod
    def _empty_result(slot_blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Return an empty result dict for early-exit cases."""
        return {
            "slot_id": slot_blueprint.get("slot_id", ""),
            "stem": "",
            "option_A": "",
            "option_B": "",
            "option_C": "",
            "option_D": "",
            "correct_answer": "",
            "explanation": "",
            "solution_steps": "",
            "difficulty_self_assessment": "",
            "trap_description": "",
            "knowledge_points": "",
            "generation_time_s": 0.0,
            "pipeline_type": "single_choice_v2",
        }
