"""Gate agents for the multi-gate review system.

Gate 1: KnowledgeSlotGateAgent — reviews knowledge points before stem generation
Gate 2: Three stem lenses + StemGateCoordinator
  - StemSemanticFrameReviewer
  - StemConditionParticipationReviewer
  - StemTerminologyPrecisionReviewer
Gate 3: Uses existing reviewers with GATE3_RESTRICTION_INSTRUCTION (handled in unified_pipeline.py)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from core_new.agent_base import BaseAgent, AgentConfig
from core_new.agent_roles import AuditMode, RoleType
from core_new.blackboard import Blackboard
from core_new.gate_protocol import GateDecision, GateResult, StemContract
from core_new.prompts.gate_prompts import (
    KNOWLEDGE_SLOT_GATE_PROMPT,
    STEM_SEMANTIC_FRAME_PROMPT,
    STEM_CONDITION_PARTICIPATION_PROMPT,
    STEM_TERMINOLOGY_PRECISION_PROMPT,
    STEM_CONTRACT_GENERATION_PROMPT,
)

logger = logging.getLogger(__name__)

# ── Parsing helpers ──────────────────────────────────────────────


def _parse_md_sections(text: str) -> dict[str, Any]:
    """Split markdown by ## headers, parse each section."""
    sections: dict[str, Any] = {}
    current_name = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_name:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name:
        sections[current_name] = "\n".join(current_lines).strip()

    return sections


def _extract_decision(text: str) -> str:
    """Extract pass/warning/blocked from text."""
    t = text.lower().strip()
    if t in ("pass", "通过"):
        return "pass"
    if t in ("warning", "警告"):
        return "warning"
    if t in ("blocked", "blocking", "阻塞"):
        return "blocked"
    # Fallback: check if text contains keywords
    if "blocked" in t or "阻塞" in t:
        return "blocked"
    if "warning" in t or "警告" in t:
        return "warning"
    return "pass"


def _extract_bool(text: str) -> bool:
    t = text.lower().strip()
    return t in ("true", "是", "yes")


def _extract_list(text: str) -> list[str]:
    """Extract bullet-point list items from text."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^[-*]\s+(.+)", line)
        if m:
            items.append(m.group(1).strip())
        elif line and not line.startswith("#"):
            items.append(line)
    return items


def _parse_stem_contract_json(text: str) -> dict:
    """Extract JSON from markdown code fence."""
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: try parsing entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ── Gate 1: Knowledge/Slot Gate ──────────────────────────────────


class KnowledgeSlotGateAgent(BaseAgent):
    """Gate 1: Review knowledge points and slot fit before stem generation."""

    def __init__(self, llm_backend, *, max_tokens: int = 4096):
        super().__init__(
            AgentConfig(
                name="knowledge_slot_gate",
                phase="gate_knowledge_slot",
                output_format="markdown",
                output_key="knowledge_gate_result",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.KNOWLEDGE_SLOT_GATE,
                system_prompt="你是一位严格的408考试命题审核人，只审核知识点和slot适配性。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        blueprint = blackboard.get("paper_blueprint", {})
        templates = blackboard.get("slot_templates", {})
        user_requirements = blackboard.get("user_requirements", "")

        slots = blueprint.get("slots", [])
        outline_scope = user_requirements
        slot_experience = ""

        # Build slot-level outline scope from templates
        template_parts = []
        for sid, tmpl in templates.items():
            guidance = tmpl.get("slot_guidance", "")
            if guidance:
                template_parts.append(f"**{sid}**: {guidance}")
        if template_parts:
            outline_scope += "\n\n" + "\n".join(template_parts)

        prompt = KNOWLEDGE_SLOT_GATE_PROMPT.format(
            slot_blueprint=json.dumps(slots, ensure_ascii=False, indent=2),
            outline_scope=outline_scope,
            slot_experience=slot_experience or "（暂无历史题位经验数据）",
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(str(raw))
        decision_text = sections.get("overall_decision", "pass")
        severity_text = sections.get("severity", "pass")
        issue_types_text = sections.get("issue_types", "")
        evidence = sections.get("evidence", "")
        required_fix = sections.get("required_fix", "")
        approved = sections.get("approved_knowledge_terms", "")
        rejected = sections.get("rejected_or_risky_terms", "")

        return {
            "decision": _extract_decision(decision_text),
            "severity": _extract_decision(severity_text),
            "issue_types": _extract_list(issue_types_text),
            "evidence": evidence,
            "required_fix": required_fix,
            "approved_knowledge_terms": approved,
            "rejected_or_risky_terms": rejected,
        }


# ── Gate 2: Stem Gate Lenses ─────────────────────────────────────


class StemSemanticFrameReviewer(BaseAgent):
    """Gate 2a: Semantic Frame Review — checks stem self-consistency."""

    def __init__(self, llm_backend, *, max_tokens: int = 6000):
        super().__init__(
            AgentConfig(
                name="stem_semantic_frame_reviewer",
                phase="gate_stem_semantic_frame",
                output_format="markdown",
                output_key="stem_semantic_frame_result",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.STEM_SEMANTIC_FRAME,
                system_prompt="你是一位非常严格的408考试命题审稿人，专审题干语义框架稳定性。不要替题干圆场。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        stem = blackboard.get("stem", "")
        slot_blueprint = blackboard.get("slot_blueprint", {})
        prompt = STEM_SEMANTIC_FRAME_PROMPT.format(
            stem=stem,
            slot_blueprint=json.dumps(slot_blueprint, ensure_ascii=False, indent=2) if isinstance(slot_blueprint, dict) else str(slot_blueprint),
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(str(raw))
        stem_pass = _extract_bool(sections.get("stem_pass", "false"))
        severity = _extract_decision(sections.get("severity", "pass"))
        issue_types = _extract_list(sections.get("issue_types", ""))
        evidence = sections.get("evidence", "")
        minimal_fix = sections.get("minimal_fix", "")
        can_continue = _extract_bool(sections.get("can_continue_to_later_review", "true"))
        semantic_frame = sections.get("semantic_frame", "")
        global_settings = sections.get("global_settings", "")
        local_settings = sections.get("local_settings", "")
        ambiguous_terms = sections.get("ambiguous_scope_terms", "")

        return {
            "stem_pass": stem_pass,
            "severity": severity,
            "issue_types": issue_types,
            "evidence": evidence,
            "minimal_fix": minimal_fix,
            "can_continue": can_continue,
            "semantic_frame": semantic_frame,
            "global_settings": global_settings,
            "local_settings": local_settings,
            "ambiguous_scope_terms": ambiguous_terms,
        }


class StemConditionParticipationReviewer(BaseAgent):
    """Gate 2b: Condition Participation Review — checks if each condition actually participates."""

    def __init__(self, llm_backend, *, max_tokens: int = 6000):
        super().__init__(
            AgentConfig(
                name="stem_condition_participation_reviewer",
                phase="gate_stem_condition_participation",
                output_format="markdown",
                output_key="stem_condition_participation_result",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.STEM_CONDITION_PARTICIPATION,
                system_prompt="你是一位非常严格的408考试命题审稿人，专审题干中每个条件是否真正参与解题。不要只说条件本身正确。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        stem = blackboard.get("stem", "")
        return STEM_CONDITION_PARTICIPATION_PROMPT.format(stem=stem)

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(str(raw))
        stem_pass = _extract_bool(sections.get("stem_condition_pass", "false"))
        severity = _extract_decision(sections.get("severity", "pass"))
        condition_usage = sections.get("condition_usage", "")
        issue_types = _extract_list(sections.get("issue_types", ""))
        minimal_fix = sections.get("minimal_fix", "")
        can_continue = _extract_bool(sections.get("can_continue_to_later_review", "true"))

        return {
            "stem_pass": stem_pass,
            "severity": severity,
            "condition_usage": condition_usage,
            "issue_types": issue_types,
            "minimal_fix": minimal_fix,
            "can_continue": can_continue,
        }


class StemTerminologyPrecisionReviewer(BaseAgent):
    """Gate 2c: Terminology Precision Review — checks professional term accuracy."""

    def __init__(self, llm_backend, *, max_tokens: int = 4000):
        super().__init__(
            AgentConfig(
                name="stem_terminology_precision_reviewer",
                phase="gate_stem_terminology_precision",
                output_format="markdown",
                output_key="stem_terminology_precision_result",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.STEM_TERMINOLOGY_PRECISION,
                system_prompt="你是一位严格的408考试命题术语审稿人，专审专业术语的精确性和规范性。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        stem = blackboard.get("stem", "")
        return STEM_TERMINOLOGY_PRECISION_PROMPT.format(stem=stem)

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(str(raw))
        terminology_pass = _extract_bool(sections.get("terminology_pass", "false"))
        severity = _extract_decision(sections.get("severity", "pass"))
        issues = sections.get("issues", "")
        can_continue = _extract_bool(sections.get("can_continue_to_later_review", "true"))

        return {
            "terminology_pass": terminology_pass,
            "severity": severity,
            "issues": issues,
            "can_continue": can_continue,
        }


# ── Stem Gate Coordinator ────────────────────────────────────────


class StemGateCoordinator:
    """Runs all 3 stem lenses in parallel, aggregates results, produces StemContract on pass."""

    def __init__(self, gateway):
        self.semantic_reviewer = StemSemanticFrameReviewer(gateway)
        self.condition_reviewer = StemConditionParticipationReviewer(gateway)
        self.terminology_reviewer = StemTerminologyPrecisionReviewer(gateway)
        self.gateway = gateway

    async def review(
        self,
        stem: str,
        slot_blueprint: dict,
        slot_id: str,
    ) -> GateResult:
        """Run all 3 lenses in parallel, aggregate into GateResult."""
        # Build blackboards for each lens
        bb_semantic = Blackboard(
            task_id=f"stem_gate_semantic_{slot_id}",
            task_type="stem_gate",
            initial_state={
                "stem": stem,
                "slot_blueprint": slot_blueprint,
            },
        )
        bb_condition = Blackboard(
            task_id=f"stem_gate_condition_{slot_id}",
            task_type="stem_gate",
            initial_state={"stem": stem},
        )
        bb_terminology = Blackboard(
            task_id=f"stem_gate_terminology_{slot_id}",
            task_type="stem_gate",
            initial_state={"stem": stem},
        )

        # Run all 3 lenses in parallel
        records = await asyncio.gather(
            self.semantic_reviewer.execute(bb_semantic),
            self.condition_reviewer.execute(bb_condition),
            self.terminology_reviewer.execute(bb_terminology),
            return_exceptions=True,
        )

        # Parse results
        lens_names = ["semantic_frame", "condition_participation", "terminology_precision"]
        lens_bbs = [bb_semantic, bb_condition, bb_terminology]
        lens_output_keys = [
            "stem_semantic_frame_result",
            "stem_condition_participation_result",
            "stem_terminology_precision_result",
        ]
        lens_results: dict[str, dict] = {}
        all_error_types: list[str] = []
        worst_decision = GateDecision.PASS
        fix_instructions: list[str] = []
        evidence_parts: list[str] = []

        for name, record, bb, okey in zip(lens_names, records, lens_bbs, lens_output_keys):
            if isinstance(record, Exception):
                lens_results[name] = {"error": str(record)}
                worst_decision = GateDecision.WARNING  # degraded but not blocked
                evidence_parts.append(f"[{name}] 执行异常: {record}")
                continue

            # Parsed data is stored on the blackboard, not on the record
            parsed = bb.get(okey, {})
            if not isinstance(parsed, dict):
                parsed = {}
            lens_results[name] = parsed

            # Determine this lens's decision
            passed = parsed.get(
                "stem_pass",
                parsed.get(
                    "stem_condition_pass",
                    parsed.get("terminology_pass", False),
                ),
            )
            severity = parsed.get("severity", "pass")
            can_continue = parsed.get("can_continue", True)

            if not passed:
                if not can_continue or severity == "blocked":
                    worst_decision = GateDecision.BLOCKED
                elif worst_decision == GateDecision.PASS:
                    worst_decision = GateDecision.WARNING

            lens_issues = parsed.get("issue_types", [])
            all_error_types.extend(lens_issues)

            minimal_fix = parsed.get("minimal_fix", "")
            if minimal_fix:
                fix_instructions.append(f"[{name}] {minimal_fix}")

            ev = parsed.get("evidence", parsed.get("issues", ""))
            if ev:
                evidence_parts.append(f"[{name}] {ev[:500]}")

        # Build aggregated result
        gate_result = GateResult(
            gate_name="stem",
            decision=worst_decision,
            error_types=all_error_types,
            fix_instruction="\n".join(fix_instructions),
            fix_target="stem" if worst_decision == GateDecision.BLOCKED else "none",
            confidence="high" if worst_decision == GateDecision.BLOCKED else "medium",
            evidence="\n".join(evidence_parts),
            lens_results=lens_results,
        )

        # If passed (or warning), generate StemContract
        if gate_result.passed:
            stem_contract = await self._generate_stem_contract(
                stem, slot_id, lens_results,
            )
            gate_result.stem_contract = stem_contract

        return gate_result

    async def _generate_stem_contract(
        self,
        stem: str,
        slot_id: str,
        lens_results: dict[str, dict],
    ) -> StemContract:
        """Call LLM to synthesize a StemContract from the 3 lens results."""
        prompt = STEM_CONTRACT_GENERATION_PROMPT.format(
            stem=stem,
            semantic_frame_result=str(lens_results.get("semantic_frame", {})),
            condition_participation_result=str(lens_results.get("condition_participation", {})),
            terminology_precision_result=str(lens_results.get("terminology_precision", {})),
        )

        try:
            result = await self.gateway.generate_text(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            raw = result.content or ""

            contract_data = _parse_stem_contract_json(raw)

            return StemContract(
                slot_id=slot_id,
                stem_text=stem,
                canonical_interpretation=contract_data.get("canonical_interpretation", stem),
                participating_conditions=contract_data.get("participating_conditions", []),
                non_participating_conditions=contract_data.get("non_participating_conditions", []),
                defined_terms=contract_data.get("defined_terms", {}),
                semantic_frame=contract_data.get("semantic_frame", ""),
                constraint_summary=contract_data.get("constraint_summary", ""),
                caveats=[],
            )
        except Exception as exc:
            logger.warning("Stem contract generation failed: %s", exc)
            return StemContract(
                slot_id=slot_id,
                stem_text=stem,
                canonical_interpretation=stem,
            )
