"""Knowledge-point blueprint synthesizer — combines Python data injection with LLM teaching decisions.

Python does data搬运 (knowledge subtree, question experiences, K-value statistics).
LLM does 教学决策 (examination angles, difficulty targets, mode selection).
The assembled output matches the format produced by artifact_store.assemble_slot_experience_doc().
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core_new.slot_prompts import K_RADAR_DEFINITIONS

if TYPE_CHECKING:
    from core_new.llm_gateway import LLMGateway
    from interact.knowledge_retriever import KnowledgeRetriever


# ── System prompt for the LLM teaching designer ───────────────

BLUEPRINT_DESIGNER_SYSTEM_PROMPT = """\
你是一位408考研教学设计师（instructional designer）。你的任务是基于历史统计数据，为特定知识点做出出题策略决策。

## 你的角色

你不是在出题，而是在做出题之前的**教学决策**：
- 这个知识点应该从什么角度考察
- 难度梯度如何设计
- 应该出什么类型的题
- 考察模式选择

## 输入格式

你将收到一段统计摘要，包含：
- K值历史分布（K1-K5各维度的常见值）
- 考察模式频率（各模式出现的次数）
- 题位分布（该知识点在哪些题位出现）
- 历史题目数量
- 用户出题意图

## 输出要求

请严格按以下Markdown格式输出（不要用代码块包裹）：

## 本次出题要求
- **考点**: （基于知识点标签确定的具体考点名称）
- **知识域**: （知识点所属的学科章节域）
- **难度**: （推荐难度等级1-5，附简要理由）
- **K目标**: （推荐的K值组合，如K2-K3平衡型）
- **难度说明**: （为什么推荐这个难度，一句话）
- **考察模式**: （推荐的考察模式名称）
- **出题数量**: （推荐出几道题）
- **题型**: （推荐的题型：single_choice 或 comprehensive）

## 出题策略
- **examination_angles**: （建议的考察角度，2-3个，逗号分隔）
- **difficulty_gradient**: （难度梯度描述，如"从概念辨析到公式应用"）
- **should_be**: （这道题应该具备什么特征）
- **should_not_be**: （这道题不应该出现什么问题）
- **question_type_recommendation**: （推荐的题型和数量，如"2道选择题，1道综合题"）

## 模式概览
- **recommended_mode**: （推荐的考察模式，需与考察模式字段一致）
- **mode_rationale**: （为什么推荐这个模式，一句话）
- **alternative_modes**: （备选模式，逗号分隔）

## 约束
- 不要重复或摘要原始数据——只做决策
- 不要输出知识点图谱或真题经验——这些由程序直接注入
- 决策必须基于统计数据，不要凭空想象
"""


# ── Data classes ──────────────────────────────────────────────

@dataclass
class SynthesisRequest:
    knowledge_tag: str = ""       # resolved tag from KnowledgeRetriever
    user_intent: str = ""         # free text, e.g. "出3道选择题，K2-K3难度"
    subject: str = ""             # optional subject hint
    question_count: int = 1       # number of questions to generate
    question_type: str = ""       # "single_choice" | "comprehensive" or empty for auto
    existing_blueprint: str = ""  # for revision: current blueprint text
    feedback: str = ""            # for revision: user annotation


@dataclass
class SynthesisResult:
    assembled_md: str               # the assembled markdown document
    blueprint_id: str               # unique ID for this blueprint
    sections_injected: list[str]    # which sections came from Python data
    sections_generated: list[str]   # which sections came from LLM


# ── Synthesizer ───────────────────────────────────────────────

class BlueprintSynthesizer:
    """Combine Python data injection with LLM teaching decisions to produce
    an assembled reference document for the downstream 5-layer pipeline.
    """

    def __init__(self, gateway: LLMGateway, retriever: KnowledgeRetriever):
        self._gateway = gateway
        self._retriever = retriever

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Main entry point. Assemble a blueprint document from data + LLM decisions."""
        tag = request.knowledge_tag

        # ── Step 1: Retrieve all data (pure Python) ──
        subtree = self._retriever.retrieve_knowledge_subtree(tag)
        experiences = self._retriever.retrieve_question_experiences(tag, max_count=15)
        stats = self._retriever.compute_statistics(tag)
        profile = self._retriever.retrieve_knowledge_profile(tag)

        # ── Step 2: Compute statistics summary for LLM context ──
        stats_summary = self._build_stats_summary(stats, request)

        # ── Step 3: LLM teaching decisions ──
        llm_result = await self._gateway.generate_text(
            messages=[
                {"role": "system", "content": BLUEPRINT_DESIGNER_SYSTEM_PROMPT},
                {"role": "user", "content": stats_summary},
            ],
            max_tokens=2048,
        )

        llm_decisions = ""
        if llm_result.ok and llm_result.content:
            llm_decisions = llm_result.content
        else:
            # Fallback: minimal decisions without LLM
            llm_decisions = self._fallback_decisions(request, stats)

        # Extract examination_mode from LLM decisions for the title
        examination_mode = self._extract_examination_mode(llm_decisions)
        slot_id = self._extract_slot_hint(tag, stats)

        # ── Step 4: Merge into assembled.md ──
        parts = self._assemble_sections(
            slot_id=slot_id,
            examination_mode=examination_mode,
            llm_decisions=llm_decisions,
            request=request,
            stats=stats,
            subtree=subtree,
            experiences=experiences,
        )

        assembled_md = "\n\n---\n\n".join(parts)

        # Translate abbreviated codes if subject_map available
        assembled_md = self._translate_codes(assembled_md)

        return SynthesisResult(
            assembled_md=assembled_md,
            blueprint_id=f"bp-{tag[:20].replace('>', '-').replace(' ', '')}-{uuid.uuid4().hex[:8]}",
            sections_injected=[
                "相关知识点细纲",
                "往年真题经验",
                "K值锚点",
                "K1-K5 认知雷达评分标准",
            ],
            sections_generated=[
                "本次出题要求",
                "基本信息",
                "模式概览",
            ],
        )

    # ── Internal helpers ────────────────────────────────────

    def _build_stats_summary(
        self,
        stats: KnowledgeStatistics,
        request: SynthesisRequest,
    ) -> str:
        """Build a concise statistical summary for the LLM. NOT the raw data."""
        lines = [
            f"## 知识点统计摘要",
            f"",
            f"- **知识点标签**: {request.knowledge_tag}",
            f"- **历史题目数量**: {stats.question_count}",
            f"- **用户意图**: {request.user_intent}",
        ]

        if request.subject:
            lines.append(f"- **科目提示**: {request.subject}")
        if request.question_count:
            lines.append(f"- **出题数量**: {request.question_count}")
        if request.question_type:
            lines.append(f"- **题型**: {request.question_type}")

        # K-value distributions
        if stats.k_distributions:
            lines.append("")
            lines.append("### K值历史分布")
            for k_key in ("K1", "K2", "K3", "K4", "K5"):
                values = stats.k_distributions.get(k_key, [])
                if values:
                    avg = sum(values) / len(values)
                    lines.append(
                        f"- **{k_key}**: 出现{len(values)}次, "
                        f"范围[{min(values)}-{max(values)}], "
                        f"均值{avg:.1f}"
                    )

        # Mode frequencies
        if stats.mode_frequencies:
            lines.append("")
            lines.append("### 考察模式频率")
            total_modes = sum(stats.mode_frequencies.values())
            for mode, count in sorted(
                stats.mode_frequencies.items(), key=lambda x: -x[1]
            ):
                pct = count / total_modes * 100 if total_modes else 0
                lines.append(f"- **{mode}**: {count}次 ({pct:.1f}%)")

        # Slot distribution
        if stats.slot_distribution:
            lines.append("")
            lines.append("### 题位分布")
            for slot, count in sorted(stats.slot_distribution.items()):
                lines.append(f"- **{slot}**: {count}次")

        return "\n".join(lines)

    def _fallback_decisions(
        self,
        request: SynthesisRequest,
        stats: KnowledgeStatistics,
    ) -> str:
        """Generate minimal decisions when LLM is unavailable."""
        # Pick the most frequent mode, or a default
        mode = "概念辨析型"
        if stats.mode_frequencies:
            mode = max(stats.mode_frequencies, key=stats.mode_frequencies.get)

        difficulty = 3
        if stats.k_distributions:
            all_k = []
            for vals in stats.k_distributions.values():
                all_k.extend(vals)
            if all_k:
                difficulty = round(sum(all_k) / len(all_k))

        return (
            f"## 本次出题要求\n"
            f"- **考点**: {request.knowledge_tag}\n"
            f"- **知识域**: {request.knowledge_tag.split('>')[0].strip()}\n"
            f"- **难度**: {difficulty}\n"
            f"- **K目标**: K{max(1, difficulty - 1)}-K{min(5, difficulty + 1)}\n"
            f"- **难度说明**: 基于历史平均难度\n"
            f"- **考察模式**: {mode}\n"
            f"- **出题数量**: {request.question_count}\n"
            f"- **题型**: {request.question_type or 'single_choice'}\n"
            f"\n"
            f"## 出题策略\n"
            f"- **examination_angles**: 基础概念, 机制理解\n"
            f"- **difficulty_gradient**: 从基础到中等\n"
            f"- **should_be**: 符合历史出题模式\n"
            f"- **should_not_be**: 超纲或过难\n"
            f"- **question_type_recommendation**: {request.question_count}道题\n"
            f"\n"
            f"## 模式概览\n"
            f"- **recommended_mode**: {mode}\n"
            f"- **mode_rationale**: 历史最高频模式\n"
            f"- **alternative_modes**: 无\n"
        )

    def _extract_examination_mode(self, llm_decisions: str) -> str:
        """Extract the examination_mode from LLM decisions text."""
        # Try to find the examination mode from 本次出题要求 section
        m = re.search(r"\*?\*?考察模式\*?\*?[:：]\s*(.+?)(?:\n|$)", llm_decisions)
        if m:
            return m.group(1).strip()
        # Fallback: try recommended_mode
        m = re.search(r"\*?\*?recommended_mode\*?\*?[:：]\s*(.+?)(?:\n|$)", llm_decisions)
        if m:
            return m.group(1).strip()
        return "综合考察"

    def _extract_slot_hint(self, tag: str, stats: KnowledgeStatistics) -> str:
        """Derive a slot_id hint from the knowledge tag or statistics."""
        if stats.slot_distribution:
            # Most frequent slot
            return max(stats.slot_distribution, key=stats.slot_distribution.get)
        # Derive from tag domain
        parts = [p.strip() for p in tag.split(">")]
        if parts:
            domain = parts[0].split("-")[0] if "-" in parts[0] else parts[0][:2]
            return f"{domain}_auto"
        return "auto"

    def _assemble_sections(
        self,
        *,
        slot_id: str,
        examination_mode: str,
        llm_decisions: str,
        request: SynthesisRequest,
        stats: KnowledgeStatistics,
        subtree: str,
        experiences: list,
    ) -> list[str]:
        """Assemble the 7-section document matching artifact_store format."""
        parts = []

        # ── Section 1: Title + requirements (from LLM + user intent) ──
        title = f"# {slot_id} 出题参考文档（考察模式：{examination_mode}）"

        # Extract the 本次出题要求 section from LLM decisions
        req_section = self._extract_section(llm_decisions, "本次出题要求")
        if req_section:
            # Override with user intent context
            req_lines = [title, "", "## 本次出题要求（来自组卷大纲）"]
            # Extract structured fields from LLM output
            for line in req_section.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- "):
                    req_lines.append(stripped)
            # Append user intent
            req_lines.append(f"- **用户意图**: {request.user_intent}")
            parts.append("\n".join(req_lines))
        else:
            parts.append(title)

        # ── Section 2: Basic info (from statistics) ──
        basic_lines = ["## 基本信息"]
        basic_lines.append(f"- **知识点**: {request.knowledge_tag}")
        basic_lines.append(f"- **历史题目数**: {stats.question_count}")
        if request.subject:
            basic_lines.append(f"- **科目**: {request.subject}")
        if stats.slot_distribution:
            slots_str = ", ".join(
                f"{s}({c})" for s, c in sorted(stats.slot_distribution.items())
            )
            basic_lines.append(f"- **题位分布**: {slots_str}")
        basic_text = "\n".join(basic_lines)
        if basic_text.strip() != "## 基本信息":
            parts.append(basic_text)

        # ── Section 3: Mode overview (from LLM) ──
        mode_section = self._extract_section(llm_decisions, "模式概览")
        if mode_section:
            parts.append(f"## 模式概览（来自教学设计师决策）\n\n{mode_section}")

        # ── Section 4: Knowledge subtree (VERBATIM from retriever) ──
        if subtree:
            parts.append(f"## 相关知识点细纲\n\n{subtree}")

        # ── Section 5: Question experiences (VERBATIM from retriever) ──
        if experiences:
            exp_entries = []
            for exp in experiences:
                # Use raw content directly — no LLM rewriting
                exp_entries.append(exp.content)
            if exp_entries:
                parts.append(
                    f"## 往年真题经验（共{len(exp_entries)}题）\n\n"
                    + "\n\n---\n\n".join(exp_entries)
                )

        # ── Section 6: K-value anchors (computed from statistics) ──
        k_anchors = self._build_k_anchors(stats)
        if k_anchors:
            parts.append(
                f"## K值锚点（{slot_id} 历史分布）\n\n{k_anchors}"
            )

        # ── Section 7: K-radar definitions (static template) ──
        radar_text = K_RADAR_DEFINITIONS.strip()
        # Strip the top-level heading line, matching artifact_store behavior
        radar_text = re.sub(r"^##\s+K1-K5.*?\n", "", radar_text)
        parts.append(f"## K1-K5 认知雷达评分标准\n\n{radar_text.strip()}")

        return parts

    def _build_k_anchors(self, stats: KnowledgeStatistics) -> str:
        """Build K-value anchor text from statistics."""
        if not stats.k_distributions:
            return ""

        lines = []
        for k_key in ("K1", "K2", "K3", "K4", "K5"):
            values = stats.k_distributions.get(k_key, [])
            if values:
                avg = sum(values) / len(values)
                lines.append(
                    f"- **{k_key}**: 范围[{min(values)}-{max(values)}], "
                    f"均值{avg:.1f}, 中位数{sorted(values)[len(values) // 2]}"
                )

        return "\n".join(lines)

    @staticmethod
    def _extract_section(text: str, heading: str) -> str:
        """Extract a markdown section by heading name."""
        pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _translate_codes(text: str) -> str:
        """Translate abbreviated codes (DS-1, CO-1 etc.) to full chapter names."""
        try:
            from core_new.subject_map import translate_code
            return translate_code(text)
        except ImportError:
            return text
