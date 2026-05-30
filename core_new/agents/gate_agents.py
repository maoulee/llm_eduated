"""Gate agents for the 2-gate review system.

Gate 1: KnowledgeGateAgent — reviews knowledge points before stem generation
Gate 2: EnvironmentClosureGateAgent — reviews stem environment closure before solving

Both agents output Markdown sections format:
  ## verdict
  - **field**: value
  ...
  ## 审核分析
  (free-form analysis)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from core_new.agent_base import BaseAgent, AgentConfig
from core_new.agent_roles import AuditMode, RoleType
from core_new.blackboard import Blackboard
from core_new.gate_protocol import GateDecision, GateResult
from core_new.prompts.gate_prompts import (
    KNOWLEDGE_GATE_PROMPT,
    ENVIRONMENT_CLOSURE_GATE_PROMPT,
)

logger = logging.getLogger(__name__)

# ── Markdown Section Parser ────────────────────────────────────


def _parse_verdict_section(text: str) -> tuple[dict[str, str], str]:
    """Parse `## verdict` section into key-value dict + remaining body.

    Expected format:
        ## verdict
        - **key**: value
        ...
        ## 审核分析
        ...
    """
    fields: dict[str, str] = {}

    # Extract the ## verdict section content
    verdict_match = re.search(
        r"^##\s*verdict\s*\n(.*?)(?=^##\s|\Z)",
        text.strip(),
        re.DOTALL | re.MULTILINE,
    )
    if not verdict_match:
        return fields, text

    section_body = verdict_match.group(1)

    # Parse `- **key**: value` lines
    for line in section_body.splitlines():
        m = re.match(r"-\s*\*\*(.+?)\*\*\s*:\s*(.+)", line.strip())
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()

    # Extract everything after ## 审核分析 as the report
    report_match = re.search(
        r"^##\s*审核分析\s*\n(.*)",
        text.strip(),
        re.DOTALL | re.MULTILINE,
    )
    report_md = report_match.group(1).strip() if report_match else ""

    return fields, report_md


def _extract_verdict(fields: dict, key: str = "verdict") -> GateDecision:
    raw = str(fields.get(key, "pass")).lower().strip()
    if raw in ("blocked", "blocking", "阻塞"):
        return GateDecision.BLOCKED
    if raw in ("warning", "警告"):
        return GateDecision.WARNING
    return GateDecision.PASS


def _extract_bool(fields: dict, key: str, default: bool = True) -> bool:
    raw = fields.get(key, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).lower().strip() in ("true", "yes", "是")


def _extract_list(fields: dict, key: str) -> list[str]:
    raw = fields.get(key, "")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        raw = raw.strip()
        if raw in ("无", "", "none"):
            return []
        return [s.strip() for s in re.split(r"[,，、\s]+", raw) if s.strip()]
    return []


def _build_gate_result(
    gate_name: str,
    fields: dict[str, str],
    report_md: str,
    raw_response: str,
) -> GateResult:
    """Build GateResult from parsed Markdown fields + report section."""
    verdict = _extract_verdict(fields)

    return GateResult(
        gate_name=gate_name,
        verdict=verdict,
        severity=str(fields.get("severity", "pass")).lower().strip(),
        issue_types=_extract_list(fields, "issue_types"),
        can_continue=_extract_bool(fields, "can_continue", default=True),
        can_send_to_solver=_extract_bool(fields, "can_send_to_solver", default=verdict != GateDecision.BLOCKED),
        fix_instruction=str(fields.get("fix_instruction", "")),
        fix_target=str(fields.get("fix_target", "none")).lower().strip(),
        confidence=str(fields.get("confidence", "medium")).lower().strip(),
        summary=str(fields.get("summary", "")),
        report_md=report_md,
        raw_response=raw_response,
    )


# ── Gate 1: Knowledge Gate ──────────────────────────────────────


class KnowledgeGateAgent(BaseAgent):
    """Gate 1: Review knowledge points match slot intent and won't mislead."""

    def __init__(self, llm_backend, *, max_tokens: int = 3000):
        super().__init__(
            AgentConfig(
                name="knowledge_gate",
                phase="gate_knowledge",
                output_format="markdown",
                output_key="knowledge_gate_result",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.KNOWLEDGE_GATE,
                system_prompt="你是一位严格的408考试命题审核员，只审核知识点是否命中且不误导。严格按 Markdown 格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        slot_intent = blackboard.get("slot_intent", "")
        outline_scope = blackboard.get("outline_scope", "")
        knowledge_terms = blackboard.get("knowledge_terms_or_stem", "")

        templates = blackboard.get("slot_templates", {})
        if templates and not outline_scope:
            parts = []
            for sid, tmpl in templates.items():
                guidance = tmpl.get("slot_guidance", "")
                if guidance:
                    parts.append(f"**{sid}**: {guidance}")
            outline_scope = "\n".join(parts) if parts else "（暂无大纲范围数据）"

        return KNOWLEDGE_GATE_PROMPT.format(
            slot_intent=slot_intent,
            outline_scope=outline_scope,
            knowledge_terms_or_stem=knowledge_terms,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        fields, report_md = _parse_verdict_section(text)
        result = _build_gate_result("knowledge", fields, report_md, text)

        output = result.to_dict()
        output["decision"] = result.verdict.value
        output["can_continue"] = result.can_continue
        return output


# ── Gate 2: Environment Closure Gate ────────────────────────────


class EnvironmentClosureGateAgent(BaseAgent):
    """Gate 2: Review stem environment closure before solving."""

    def __init__(self, llm_backend, *, max_tokens: int = 4000):
        super().__init__(
            AgentConfig(
                name="environment_closure_gate",
                phase="gate_environment_closure",
                output_format="markdown",
                output_key="environment_closure_gate_result",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.ENVIRONMENT_CLOSURE_GATE,
                system_prompt="你是一位严格的408考试命题审核员，只审核题目环境是否闭环可解。严格按 Markdown 格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        approved_terms = blackboard.get("approved_knowledge_terms", "")
        stem = blackboard.get("stem", "")
        question_prompt = blackboard.get("question_prompt", "")

        return ENVIRONMENT_CLOSURE_GATE_PROMPT.format(
            approved_knowledge_terms=approved_terms,
            stem=stem,
            question_prompt=question_prompt,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        fields, report_md = _parse_verdict_section(text)
        result = _build_gate_result("environment_closure", fields, report_md, text)

        output = result.to_dict()
        output["decision"] = result.verdict.value
        output["can_continue"] = result.can_continue
        output["can_send_to_solver"] = result.can_send_to_solver
        return output


# ── Convenience: run both gates sequentially ─────────────────────


async def run_gates(
    gateway,
    *,
    slot_intent: str,
    outline_scope: str,
    knowledge_terms_or_stem: str,
    stem: str,
    question_prompt: str = "",
    slot_id: str = "",
    enable_knowledge_gate: bool = True,
    enable_environment_gate: bool = True,
) -> tuple[Optional[GateResult], Optional[GateResult]]:
    """Run Knowledge Gate then Environment Closure Gate sequentially.

    Returns (knowledge_gate_result, environment_gate_result).
    Environment gate is skipped if knowledge gate blocks.
    """
    knowledge_result = None
    environment_result = None

    # Gate 1: Knowledge Gate
    if enable_knowledge_gate:
        kg_agent = KnowledgeGateAgent(gateway)
        bb = Blackboard(
            task_id=f"knowledge_gate_{slot_id}",
            task_type="gate",
            initial_state={
                "slot_intent": slot_intent,
                "outline_scope": outline_scope,
                "knowledge_terms_or_stem": knowledge_terms_or_stem,
            },
        )
        record = await kg_agent.execute(bb)

        if record.error:
            logger.warning("[%s] Knowledge gate execution failed: %s", slot_id, record.error)
            knowledge_result = GateResult(
                gate_name="knowledge",
                verdict=GateDecision.WARNING,
                summary=f"Gate execution failed: {record.error}",
                raw_response=str(record.output),
            )
        else:
            parsed = bb.get("knowledge_gate_result", {})
            if isinstance(parsed, dict):
                knowledge_result = GateResult.from_dict(parsed)

        if knowledge_result and knowledge_result.blocked:
            logger.info("[%s] Knowledge gate BLOCKED: %s", slot_id, knowledge_result.summary)
            return knowledge_result, None

    # Gate 2: Environment Closure Gate
    if enable_environment_gate:
        approved = ""
        if knowledge_result and knowledge_result.passed:
            approved = knowledge_result.summary

        ec_agent = EnvironmentClosureGateAgent(gateway)
        bb = Blackboard(
            task_id=f"env_closure_gate_{slot_id}",
            task_type="gate",
            initial_state={
                "approved_knowledge_terms": approved,
                "stem": stem,
                "question_prompt": question_prompt,
            },
        )
        record = await ec_agent.execute(bb)

        if record.error:
            logger.warning("[%s] Environment gate execution failed: %s", slot_id, record.error)
            environment_result = GateResult(
                gate_name="environment_closure",
                verdict=GateDecision.WARNING,
                summary=f"Gate execution failed: {record.error}",
                raw_response=str(record.output),
            )
        else:
            parsed = bb.get("environment_closure_gate_result", {})
            if isinstance(parsed, dict):
                environment_result = GateResult.from_dict(parsed)

        if environment_result:
            if environment_result.blocked:
                logger.info("[%s] Environment gate BLOCKED: %s", slot_id, environment_result.summary)
            else:
                logger.info("[%s] Environment gate PASSED: %s", slot_id, environment_result.summary)

    return knowledge_result, environment_result
