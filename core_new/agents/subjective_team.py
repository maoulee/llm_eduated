"""Subjective (comprehensive) question pipeline agents and orchestrator.

Pipeline:
  ProblemSketcher → Parameterizer → SubjectiveDraftAssembler
  → CodeActSolver → SolutionFormatter → RubricWriter → SubjectiveReviewer
  → SubjectiveAssemblerAgent (merge into final output)

Each agent does ONE narrow task. Reviewer can route back to a specific agent
for one revision round.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent, NoLLMAgent
from core_new.blackboard import Blackboard

logger = logging.getLogger(__name__)


# ── Markdown parsing helpers (local copy from slot_agents.py) ──


def _parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    """Parse '- **key**: value' lines into a dict."""
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None

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
    current_name: Optional[str] = None
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


# ── 1. ProblemSketcherAgent ───────────────────────────────────


class ProblemSketcherAgent(BaseAgent):
    """Produce a structural sketch of the question (no params, no answer)."""

    def __init__(self, llm_backend, *, max_tokens: int = 800):
        super().__init__(
            AgentConfig(
                name="problem_sketcher",
                phase="subjective_sketch",
                output_format="markdown",
                output_key="problem_sketch",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研出题专家，擅长构思综合应用题的骨架结构。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import PROBLEM_SKETCHER_PROMPT

        slot_instruction = blackboard.read("slot_instruction", "请出一道综合应用题")
        return PROBLEM_SKETCHER_PROMPT.format(slot_instruction=slot_instruction)

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("题目骨架", {})


# ── 2. ParameterizerAgent ─────────────────────────────────────


class ParameterizerAgent(BaseAgent):
    """Fill concrete parameters into the sketch, verify solvability."""

    def __init__(self, llm_backend, *, max_tokens: int = 800):
        super().__init__(
            AgentConfig(
                name="parameterizer",
                phase="subjective_param",
                output_format="markdown",
                output_key="problem_parameters",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研出题专家，擅长为题目骨架填入自洽的具体参数。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import PARAMETERIZER_PROMPT

        sketch = blackboard.read("problem_sketch", "无骨架")
        return PARAMETERIZER_PROMPT.format(problem_sketch=sketch)

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("参数设定", {})


# ── 3. SubjectiveDraftAssembler ────────────────────────────────


class SubjectiveDraftAssembler(BaseAgent):
    """Merge sketch + params into a final question draft."""

    def __init__(self, llm_backend, *, max_tokens: int = 800):
        super().__init__(
            AgentConfig(
                name="subjective_draft_assembler",
                phase="subjective_draft",
                output_format="markdown",
                output_key="question_draft",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研出题专家，擅长将骨架和参数合并为完整的综合应用题。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import SUBJECTIVE_DRAFT_PROMPT

        sketch = blackboard.read("problem_sketch", "无骨架")
        params = blackboard.read("problem_parameters", "无参数")
        return SUBJECTIVE_DRAFT_PROMPT.format(
            problem_sketch=sketch,
            problem_parameters=params,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("题目草稿", {})


# ── 4. SolutionFormatterAgent ──────────────────────────────────


class SolutionFormatterAgent(BaseAgent):
    """Format the solver's raw output into clean solution text."""

    def __init__(self, llm_backend, *, max_tokens: int = 1200):
        super().__init__(
            AgentConfig(
                name="solution_formatter",
                phase="subjective_format_solution",
                output_format="markdown",
                output_key="formatted_solution",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研解题专家，擅长将原始求解结果整理为规范的解答文本。严格按markdown格式输出。不要重新求解。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import SOLUTION_FORMATTER_PROMPT

        solver_result = blackboard.read("solver_result", "无求解结果")
        return SOLUTION_FORMATTER_PROMPT.format(solver_result=solver_result)

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("规范解答", {})


# ── 5. RubricWriterAgent ──────────────────────────────────────


class RubricWriterAgent(BaseAgent):
    """Write grading rubric (scoring points) from question + solution."""

    def __init__(self, llm_backend, *, max_tokens: int = 800):
        super().__init__(
            AgentConfig(
                name="rubric_writer",
                phase="subjective_rubric",
                output_format="markdown",
                output_key="rubric",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研阅卷专家，擅长编写采分点评分标准。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import RUBRIC_WRITER_PROMPT

        question_draft = blackboard.read("question_draft", "无题目草稿")
        solution = blackboard.read("formatted_solution", "无标准答案")
        return RUBRIC_WRITER_PROMPT.format(
            question_draft=question_draft,
            solution=solution,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("评分标准", {})


# ── 6. SubjectiveReviewerAgent ────────────────────────────────


class SubjectiveReviewerAgent(BaseAgent):
    """Review the full output and decide pass or route to a specific agent."""

    def __init__(self, llm_backend, *, max_tokens: int = 1200):
        super().__init__(
            AgentConfig(
                name="subjective_reviewer",
                phase="subjective_review",
                output_format="markdown",
                output_key="subjective_review",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研出题质量审核专家，负责审核综合应用题的完整产出。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.subjective_prompts import SUBJECTIVE_REVIEWER_PROMPT

        slot_instruction = blackboard.read("slot_instruction", "")
        question_draft = blackboard.read("question_draft", "")
        solution = blackboard.read("formatted_solution", "")
        rubric = blackboard.read("rubric", "")
        return SUBJECTIVE_REVIEWER_PROMPT.format(
            slot_instruction=slot_instruction,
            question_draft=question_draft,
            solution=solution,
            rubric=rubric,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)
        return sections.get("审核结论", {})


# ── 7. SubjectiveAssemblerAgent (no LLM) ──────────────────────


class SubjectiveAssemblerAgent(NoLLMAgent):
    """Merge all outputs into the final assembled question (no LLM call)."""

    def __init__(self, llm_backend=None):
        # Pass a dummy config; we override execute so _call_llm is never used.
        super().__init__(
            AgentConfig(
                name="subjective_assembler",
                phase="subjective_assemble",
                output_format="markdown",
                output_key="final_question",
                max_tokens=0,
                enable_thinking=True,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        return ""

    def parse_output(self, raw: Any) -> Any:
        return raw

    async def execute(self, blackboard: Blackboard):
        """Assemble final output from all pipeline stages."""
        sketch = blackboard.get("problem_sketch", {})
        params = blackboard.get("problem_parameters", {})
        draft = blackboard.get("question_draft", {})
        solution = blackboard.get("formatted_solution", {})
        rubric = blackboard.get("rubric", {})
        review = blackboard.get("subjective_review", {})

        assembled = {
            "question": draft,
            "solution": solution,
            "rubric": rubric,
            "review": review,
            "sketch": sketch,
            "parameters": params,
        }

        md_lines = [
            "# final_question",
            "",
            "## 题目",
        ]
        for k, v in (draft if isinstance(draft, dict) else {}).items():
            md_lines.append(f"- **{k}**: {v}")
        md_lines.append("")
        md_lines.append("## 标准答案")
        for k, v in (solution if isinstance(solution, dict) else {}).items():
            md_lines.append(f"- **{k}**: {v}")
        md_lines.append("")
        md_lines.append("## 评分标准")
        for k, v in (rubric if isinstance(rubric, dict) else {}).items():
            md_lines.append(f"- **{k}**: {v}")
        md_lines.append("")

        md_text = "\n".join(md_lines)
        return await blackboard.write(
            self.config.name,
            md_text,
            self.config.phase,
            output_key=self.config.output_key,
            parsed=assembled,
            input_snapshot={},
        )


# ── Pipeline orchestrator ──────────────────────────────────────

# Maps reviewer target_agent values to pipeline phase names
_REVISION_ROUTE = {
    "sketcher": "subjective_sketch",
    "parameterizer": "subjective_param",
    "draft": "subjective_draft",
    "formatter": "subjective_format_solution",
    "rubric": "subjective_rubric",
}

_MAX_REVISION_ROUNDS = 1


@dataclass
class SubjectivePipelineResult:
    """Result of the full subjective pipeline run."""
    final_question: Dict[str, Any]
    review: Dict[str, Any]
    revised: bool


class SubjectivePipeline:
    """Orchestrate the subjective question pipeline.

    Usage::

        pipeline = SubjectivePipeline()
        result = await pipeline.run(slot_blueprint, experience_card, gateway)
    """

    def __init__(self, *, max_revision_rounds: int = _MAX_REVISION_ROUNDS):
        self.max_revision_rounds = max_revision_rounds

    async def run(
        self,
        slot_blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> SubjectivePipelineResult:
        """Run the full subjective pipeline.

        Args:
            slot_blueprint: The SlotBlueprint for this slot.
            experience_card: Experience card markdown text.
            gateway: LLMGateway instance.

        Returns:
            SubjectivePipelineResult with the assembled question and metadata.
        """
        from core_new.agents.codeact_solver import CodeActSolverAgent

        # Build slot instruction from blueprint
        slot_instruction = self._build_slot_instruction(slot_blueprint, experience_card)

        # Create blackboard for this pipeline run
        bb = Blackboard(
            task_id=f"subjective_{slot_blueprint.get('slot_id', 'unknown')}",
            task_type="subjective_pipeline",
        )
        await bb.set_input("slot_instruction", slot_instruction)

        # Instantiate agents
        sketcher = ProblemSketcherAgent(gateway)
        parameterizer = ParameterizerAgent(gateway)
        draft_assembler = SubjectiveDraftAssembler(gateway)
        solver = CodeActSolverAgent(gateway)
        formatter = SolutionFormatterAgent(gateway)
        rubric_writer = RubricWriterAgent(gateway)
        reviewer = SubjectiveReviewerAgent(gateway)
        assembler = SubjectiveAssemblerAgent(gateway)

        # --- Forward pass ---
        await sketcher.execute(bb)
        await parameterizer.execute(bb)
        await draft_assembler.execute(bb)

        # CodeActSolver: extract question text and sub-questions
        draft_data = bb.get("question_draft", {})
        question_text = draft_data.get("stem", "") if isinstance(draft_data, dict) else ""
        sub_qs_raw = draft_data.get("sub_questions", "") if isinstance(draft_data, dict) else ""
        sub_questions = self._parse_sub_questions(sub_qs_raw)

        solver_result = await solver.solve(
            question_draft=question_text,
            sub_questions=sub_questions if sub_questions else None,
            question_type="comprehensive",
        )

        # Store solver result on blackboard
        solver_result_text = (
            f"answer: {solver_result.answer}\n"
            f"confidence: {solver_result.confidence}\n"
            f"evidence: {solver_result.evidence}\n"
            f"sub_answers: {json.dumps(solver_result.sub_answers or {}, ensure_ascii=False)}"
        )
        await bb.set_input("solver_result", solver_result_text)

        # Continue forward pass
        await formatter.execute(bb)
        await rubric_writer.execute(bb)
        await reviewer.execute(bb)

        # --- Revision loop ---
        revised = False
        for _ in range(self.max_revision_rounds):
            review = bb.get("subjective_review", {})
            if not isinstance(review, dict):
                break
            if review.get("status") != "needs_fix":
                break

            target = review.get("target_agent", "")
            phase = _REVISION_ROUTE.get(target)
            if not phase:
                logger.warning("Reviewer requested fix for unknown target '%s', skipping", target)
                break

            revised = True
            logger.info("Revision round: re-running %s (target=%s)", phase, target)

            # Re-run the target agent and all downstream agents
            if phase == "subjective_sketch":
                await sketcher.execute(bb)
                await parameterizer.execute(bb)
                await draft_assembler.execute(bb)
            elif phase == "subjective_param":
                await parameterizer.execute(bb)
                await draft_assembler.execute(bb)
            elif phase == "subjective_draft":
                await draft_assembler.execute(bb)
            elif phase == "subjective_format_solution":
                await formatter.execute(bb)
                await rubric_writer.execute(bb)
            elif phase == "subjective_rubric":
                await rubric_writer.execute(bb)

            # Re-run reviewer after revision
            await reviewer.execute(bb)

        # --- Final assembly ---
        await assembler.execute(bb)

        final_question = bb.get("final_question", {})
        review = bb.get("subjective_review", {})

        return SubjectivePipelineResult(
            final_question=final_question,
            review=review if isinstance(review, dict) else {},
            revised=revised,
        )

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _build_slot_instruction(blueprint: Dict[str, Any], experience_card: str) -> str:
        """Build the slot instruction text from blueprint + experience card."""
        parts = [
            f"题位: {blueprint.get('slot_id', 'unknown')}",
            f"科目: {blueprint.get('target_subject', '')}",
            f"知识领域: {blueprint.get('target_family', '')}",
            f"主考点: {blueprint.get('primary_target_name', '')}",
            f"考点深度: {blueprint.get('target_depth', '')}",
            f"目标难度: {blueprint.get('target_difficulty', '')}",
            f"功能角色: {blueprint.get('primary_paper_role', '')}",
            f"子问题数: {blueprint.get('sub_questions', 2)}",
        ]
        if blueprint.get("must_include"):
            parts.append(f"必须包含: {blueprint['must_include']}")
        if blueprint.get("must_avoid"):
            parts.append(f"必须避免: {blueprint['must_avoid']}")
        if experience_card:
            parts.append(f"\n经验卡:\n{experience_card}")
        return "\n".join(parts)

    @staticmethod
    def _parse_sub_questions(raw: Any) -> List[str]:
        """Parse sub_questions field into a list of strings."""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            # Split by newlines or numbered patterns like (1), (2), 1., 2.
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            if len(lines) > 1:
                return lines
            # Try splitting by common delimiters
            parts = re.split(r"(?:\(?\d+[\.\)]\s*)", raw)
            return [p.strip() for p in parts if p.strip()]
        return []
