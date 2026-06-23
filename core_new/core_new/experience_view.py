"""Experience-card views for generation prompts."""

from __future__ import annotations

import re


_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

_ANSWER_TOKENS = (
    "answer",
    "solution",
    "verification",
    "verification_code",
    "verification_result",
    "\u7b54\u6848",
    "\u6b63\u786e\u7b54\u6848",
    "\u6807\u51c6\u7b54\u6848",
    "\u7b54\u6848\u5206\u6790",
    "\u89e3\u9898\u6b65\u9aa4",
    "\u89e3\u6790",
)

_KEEP_TOKENS = (
    "slot",
    "question_type",
    "target",
    "difficulty",
    "trap",
    "style",
    "reasoning_steps",
    "stem_length",
    "condition_count",
    "calculation_load",
    "trap_strength",
    "option_style",
    "reasoning_shape",
    "foundation_check",
    "trap_diagnosis",
    "calculation_stability",
    "\u9898\u4f4d",
    "\u9898\u578b",
    "\u79d1\u76ee",
    "\u8003\u70b9",
    "\u96be\u5ea6",
    "\u529f\u80fd\u89d2\u8272",
    "\u51fa\u9898\u6307\u5bfc",
    "\u5e94\u8be5",
    "\u4e0d\u5e94",
    "\u751f\u6210\u98ce\u683c",
    "\u9884\u671f\u5f62\u6001",
    "\u9002\u5408\u8003\u70b9",
    "\u5e72\u6270",
    "\u9677\u9631",
    "\u98ce\u683c",
)

_GUIDANCE_TOKENS = (
    "should",
    "avoid",
    "must",
    "knowledge",
    "mechanism",
    "pattern",
    "foundation_check",
    "trap_diagnosis",
    "calculation_stability",
    "\u5e94\u8be5",
    "\u4e0d\u5e94",
    "\u8003\u67e5",
    "\u8003\u70b9",
    "\u96be\u5ea6",
    "\u9677\u9631",
    "\u5e72\u6270",
    "\u98ce\u683c",
    "\u6761\u4ef6",
    "\u63a8\u7406",
    "\u8ba1\u7b97",
)


def build_design_experience_view(experience_card: str, *, max_chars: int = 5000) -> str:
    """Return a prompt-safe design view of an experience card.

    Design agents need slot style, difficulty anchors, target families, and trap
    summaries. They should not see full reference code, complete answers, or
    line-by-line solutions, because those strongly encourage copying.
    """
    if not experience_card:
        return ""

    scrubbed = _CODE_BLOCK_RE.sub("[code block removed for design view]", experience_card)
    kept: list[str] = [
        "# Design-safe experience view",
        "",
        "Full reference answers/code are intentionally filtered. Use this only for slot style, target family, difficulty, and trap patterns.",
        "",
    ]

    in_dropped_section = False
    for raw_line in scrubbed.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue

        if re.match(r"^#{1,4}\s+", stripped):
            in_dropped_section = _is_answer_or_solution_text(stripped)
            if in_dropped_section:
                continue
            kept.append(line)
            continue

        if in_dropped_section:
            continue

        if _is_answer_or_solution_text(stripped):
            continue

        if _looks_like_design_line(stripped):
            kept.append(line)

    result = "\n".join(kept).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rstrip() + "\n...[design view truncated]"
    return result


def _is_answer_or_solution_text(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in _ANSWER_TOKENS)


def _looks_like_design_line(line: str) -> bool:
    lowered = line.lower()
    if any(token in lowered for token in _KEEP_TOKENS):
        return True
    if len(line) <= 180 and any(token in lowered for token in _GUIDANCE_TOKENS):
        return True
    return False
