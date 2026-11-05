"""Gate agent for knowledge point review.

KnowledgeGateAgent — reviews knowledge points before stem generation.

Output format:
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
from core_new.markdown_parser import parse_md_sections
from core_new.prompts.gate_prompts import (
    KNOWLEDGE_GATE_PROMPT,
)

logger = logging.getLogger(__name__)

# ── Markdown Section Parser ────────────────────────────────────


def _parse_verdict_section(text: str) -> tuple[dict[str, str], str]:
    """Parse `## verdict` section into key-value dict + remaining body."""
    sections = parse_md_sections(text)

    fields: dict[str, str] = {}
    verdict = sections.get("verdict", {})
    if isinstance(verdict, dict):
        for key, value in verdict.items():
            fields[str(key)] = str(value)

    report_md = ""
    report_section = sections.get("审核分析", "")
    if isinstance(report_section, dict):
        report_parts = []
        for k, v in report_section.items():
            report_parts.append(f"- **{k}**: {v}")
        report_md = "\n".join(report_parts)
    elif isinstance(report_section, str):
        report_md = report_section

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


# ── Knowledge Gate ──────────────────────────────────────────────


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
