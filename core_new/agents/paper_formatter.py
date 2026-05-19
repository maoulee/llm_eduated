"""PaperFormatterAgent — post-process pipeline output into clean, print-ready markdown.

Two-layer approach:
  1. Rule-based structural formatting (fast, deterministic)
  2. LLM content polishing (handles self-discussion, empty fields, etc.)

Usage:
  agent = PaperFormatterAgent(gateway)
  md = await agent.format(questions, blueprint, review)
  paths = agent.export(Path("docs/exam_paper_clean.md"))
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from core_new.llm_gateway import LLMGateway
from core_new.prompts.formatter_prompts import (
    POLISH_EXPLANATION_PROMPT,
    SELF_DISCUSSION_PATTERNS,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


class PaperFormatterAgent:
    """Post-process pipeline output into clean, print-ready exam paper."""

    def __init__(self, gateway: LLMGateway | None = None):
        self.gateway = gateway

    async def format(
        self,
        questions: list[dict],
        blueprint: dict | None = None,
        review: dict | None = None,
    ) -> str:
        """Format all questions into clean markdown."""
        blueprint = blueprint or {}
        review = review or {}

        md = self._format_structured(questions, blueprint, review)

        if self.gateway:
            md = await self._polish_content(md, questions)

        return md

    # ── Step 1: Rule-based structural formatting ────────────────

    def _format_structured(
        self,
        questions: list[dict],
        blueprint: dict,
        review: dict,
    ) -> str:
        sc_qs, comp_qs = self._split_questions(questions)
        lines: list[str] = []

        # Title
        lines.append("# 408计算机组成原理 模拟试卷")
        lines.append("")
        lines.append(
            "> 本试卷涵盖计算机组成原理选择题（第1-11题）和综合应用题"
            "（第43-45题），难度对标全国统考408真题。"
        )
        lines.append("")

        # Part 1: Multiple choice questions
        lines.append("---")
        lines.append("")
        lines.append("## 第一部分 选择题（每题2分，共22分）")
        lines.append("")
        lines.append("下列每题给出的四个选项中，只有一个选项最符合题目要求。")
        lines.append("")

        for idx, q in enumerate(sc_qs, 1):
            lines.extend(self._format_sc_question(idx, q))

        # Part 2: Comprehensive questions
        lines.append("---")
        lines.append("")
        lines.append("## 第二部分 综合应用题")
        lines.append("")

        for q in comp_qs:
            lines.extend(self._format_comp_question(q))

        # Part 3: Answer key
        lines.append("---")
        lines.append("")
        lines.append("# 参考答案与解析")
        lines.append("")
        lines.extend(self._format_answer_table(sc_qs))
        lines.append("## 选择题解析")
        lines.append("")

        for idx, q in enumerate(sc_qs, 1):
            lines.extend(self._format_sc_explanation(idx, q))

        lines.append("## 综合应用题解析")
        lines.append("")

        for q in comp_qs:
            lines.extend(self._format_comp_explanation(q, review))

        # Part 4: Design analysis
        lines.append("---")
        lines.append("")
        lines.append("# 命题设计分析")
        lines.append("")

        lines.extend(self._format_design_analysis(sc_qs, comp_qs, blueprint))

        return "\n".join(lines)

    # ── SC question formatting ──────────────────────────────────

    def _format_sc_question(self, idx: int, q: dict) -> list[str]:
        sid = q.get("slot_id", "?")
        stem = q.get("stem", "").strip()
        lines = [f"**{idx}.** {stem}", ""]

        for opt in "ABCD":
            val = q.get(f"option_{opt}", "").strip()
            lines.append(f"  {opt}. {val}")
        lines.append("")
        return lines

    def _format_comp_question(self, q: dict) -> list[str]:
        sid = q.get("slot_id", "?")
        stem = q.get("stem", "").strip()
        sub_qs = q.get("sub_questions", [])
        lines = [f"**{sid}.** {stem}", ""]

        if sub_qs:
            for si, sq in enumerate(sub_qs, 1):
                text = sq if isinstance(sq, str) else str(sq)
                lines.append(f"({si}) {text}")
                lines.append("")

        lines.append("---")
        lines.append("")
        return lines

    # ── Answer table ────────────────────────────────────────────

    def _format_answer_table(self, sc_qs: list[dict]) -> list[str]:
        if not sc_qs:
            return []

        lines = ["## 选择题答案", ""]
        nums = " | ".join(str(i) for i in range(1, len(sc_qs) + 1))
        seps = "|".join("---" for _ in sc_qs)
        answers = " | ".join(q.get("correct_answer", "?") for q in sc_qs)

        lines.append(f"| 题号 | {nums} |")
        lines.append(f"|------|{seps}|")
        lines.append(f"| 答案 | {answers} |")
        lines.append("")
        return lines

    # ── SC explanation formatting ───────────────────────────────

    def _format_sc_explanation(self, idx: int, q: dict) -> list[str]:
        sid = q.get("slot_id", "?")
        answer = q.get("correct_answer", "?")
        explanation = q.get("explanation", "").strip()
        lines = [f"**{idx}. 答案：{answer}**", ""]

        if explanation:
            lines.append(explanation)
        else:
            lines.append("（解析待补充）")

        lines.append("")
        lines.append("---")
        lines.append("")
        return lines

    # ── Comprehensive explanation formatting ────────────────────

    def _format_comp_explanation(self, q: dict, review: dict) -> list[str]:
        sid = q.get("slot_id", "?")
        explanation = q.get("explanation", "").strip()
        answer = q.get("correct_answer", q.get("answer", {}))
        rubric = q.get("rubric", {})
        solver = q.get("solver_result", {})

        score = self._get_review_score(sid, review)
        lines = [f"### {sid} (审核评分：{score}/10)", ""]

        if explanation:
            lines.append(explanation)
        elif isinstance(answer, dict) and answer:
            lines.append("**参考答案：**")
            lines.append("")
            for k, v in sorted(answer.items()):
                lines.append(f"- {k}: {v}")
            lines.append("")

            if solver and isinstance(solver, dict):
                evidence = solver.get("evidence", "")
                if evidence:
                    lines.append("**计算验证：**")
                    lines.append("")
                    lines.append(evidence)

        lines.append("")
        lines.append("---")
        lines.append("")
        return lines

    # ── Design analysis formatting ──────────────────────────────

    def _format_design_analysis(
        self,
        sc_qs: list[dict],
        comp_qs: list[dict],
        blueprint: dict,
    ) -> list[str]:
        lines = ["## 选择题", ""]

        for idx, q in enumerate(sc_qs, 1):
            difficulty = self._infer_difficulty(q, blueprint)
            topic = self._infer_topic(q, blueprint)
            trap = q.get("trap_description", "").strip()

            lines.append(f"**{idx}.** 难度：{difficulty}/5")
            lines.append(f"- 考察目标：{topic}")
            if trap:
                lines.append(f"- 陷阱说明：{self._truncate(trap, 200)}")
            lines.append("")

        lines.append("## 综合应用题")
        lines.append("")

        for q in comp_qs:
            sid = q.get("slot_id", "?")
            difficulty = self._infer_difficulty(q, blueprint)
            topic = self._infer_topic(q, blueprint)
            param_notes = q.get("parameter_notes", "").strip()

            lines.append(f"**{sid}** 难度：{difficulty}/5")
            lines.append(f"- 考察目标：{topic}")
            if param_notes:
                lines.append(f"- 参数设计说明：{self._truncate(param_notes, 500)}")

            sub_qs = q.get("sub_questions", [])
            if sub_qs:
                lines.append("- **子问逻辑：**", )
                for si, sq in enumerate(sub_qs, 1):
                    text = sq if isinstance(sq, str) else str(sq)
                    intent_key = f"sub_q{si}_intent"
                    design = q.get("design_intent", {})
                    intent = design.get(intent_key, "") if isinstance(design, dict) else ""
                    line = f"  - 子问{si}：{self._truncate(text, 60)}"
                    if intent:
                        line += f" → {self._truncate(intent, 80)}"
                    lines.append(line)

            lines.append("")

        return lines

    # ── Step 2: LLM content polishing ───────────────────────────

    async def _polish_content(self, md: str, questions: list[dict]) -> str:
        """Use LLM to clean up problematic explanation sections."""
        if not self.gateway:
            return md

        sections = md.split("---")
        polished = []

        for section in sections:
            needs_polish, issues = self._detect_issues(section)

            if needs_polish and issues:
                try:
                    polished_section = await self._llm_polish(section, issues)
                    polished.append(polished_section)
                    logger.info("Polished section with issues: %s", issues)
                except Exception as exc:
                    logger.warning("Polish failed, keeping original: %s", exc)
                    polished.append(section)
            else:
                polished.append(section)

        return "---".join(polished)

    def _detect_issues(self, section: str) -> tuple[bool, str]:
        issues = []

        for pattern in SELF_DISCUSSION_PATTERNS:
            if pattern in section:
                issues.append(f"包含自我讨论：'{pattern}'")

        if re.search(r"难度：\?/5|难度：/5", section):
            issues.append("缺少难度评级")

        if re.search(r"考察目标：\s*$|考点：\s*$", section, re.MULTILINE):
            issues.append("缺少考点描述")

        return bool(issues), "; ".join(issues)

    async def _llm_polish(self, section: str, issues: str) -> str:
        prompt = POLISH_EXPLANATION_PROMPT.format(
            issues=issues,
            raw_text=section.strip(),
        )

        result = await self.gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            enable_thinking=False,
        )

        content = result.content.strip() if result.content else section

        if not content or len(content) < 50:
            return section

        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        return content

    # ── Step 3: Export ──────────────────────────────────────────

    def export(self, md_path: Path) -> dict[str, Path]:
        """Export markdown to HTML and PDF."""
        paths: dict[str, Path] = {"md": md_path}

        try:
            html_path = self._export_html(md_path)
            paths["html"] = html_path

            pdf_path = self._export_pdf(html_path)
            if pdf_path:
                paths["pdf"] = pdf_path
        except Exception as exc:
            logger.warning("Export failed: %s", exc)

        return paths

    def _export_html(self, md_path: Path) -> Path:
        from core_new.export.md_to_html import convert

        html_path = md_path.with_suffix(".html")
        convert(str(md_path), str(html_path))
        return html_path

    def _export_pdf(self, html_path: Path) -> Path | None:
        html_path = html_path.resolve()
        pdf_path = html_path.with_suffix(".pdf")

        edge_candidates = [
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]

        edge = next((p for p in edge_candidates if p.exists()), None)
        if not edge:
            logger.warning("Edge not found, skipping PDF export")
            return None

        try:
            subprocess.run(
                [
                    str(edge),
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--print-to-pdf={pdf_path}",
                    "--print-to-pdf-no-header",
                    html_path.as_uri(),
                ],
                timeout=30,
                capture_output=True,
            )
            if pdf_path.exists():
                return pdf_path
        except Exception as exc:
            logger.warning("PDF export failed: %s", exc)

        return None

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _split_questions(
        questions: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        sc, comp = [], []
        for q in questions:
            if not q.get("stem"):
                continue
            sid = q.get("slot_id", "Q99")
            num = int(re.sub(r"[^\d]", "", sid) or "99")
            (sc if num < 43 else comp).append(q)
        sc.sort(key=lambda x: x.get("slot_id", ""))
        comp.sort(key=lambda x: x.get("slot_id", ""))
        return sc, comp

    @staticmethod
    def _get_review_score(sid: str, review: dict) -> str:
        for sr in review.get("slot_reviews", []):
            if sr.get("slot_id") == sid:
                return str(sr.get("quality_score", "?"))
        return "?"

    @staticmethod
    def _infer_difficulty(q: dict, blueprint: dict) -> str:
        d = q.get("difficulty_self_assessment", "")
        if d and str(d).strip() and str(d) != "None":
            return str(d)
        slots = blueprint.get("slots", [])
        sid = q.get("slot_id", "")
        for s in slots:
            if s.get("slot_id") == sid:
                return str(s.get("target_difficulty", "3"))
        return "3"

    @staticmethod
    def _infer_topic(q: dict, blueprint: dict) -> str:
        kp = q.get("knowledge_points", "").strip()
        if kp and kp != "None":
            return kp
        slots = blueprint.get("slots", [])
        sid = q.get("slot_id", "")
        for s in slots:
            if s.get("slot_id") == sid:
                return s.get("primary_target_name", s.get("must_include", ""))
        return ""

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
