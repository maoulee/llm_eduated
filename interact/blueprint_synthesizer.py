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

BLUEPRINT_REVISION_SYSTEM_PROMPT = """\
你是一位408考研教学设计师（instructional designer）。教师对当前的出题蓝图提出了修改意见，你需要根据反馈修订教学决策。

## 你的任务

根据教师的批注反馈，修订当前的出题决策。保留教师认可的部分，只修改被指出的问题。

## 输出要求

输出修订后的完整决策（格式与原始蓝图一致），不要只输出差异。严格按以下Markdown格式：

## 本次出题要求
- **考点**: ...
- **知识域**: ...
- **难度**: ...
- **K目标**: ...
- **难度说明**: ...
- **考察模式**: ...
- **出题数量**: ...
- **题型**: ...

## 出题策略
- **examination_angles**: ...
- **difficulty_gradient**: ...
- **should_be**: ...
- **should_not_be**: ...
- **question_type_recommendation**: ...

## 模式概览
- **recommended_mode**: ...
- **mode_rationale**: ...
- **alternative_modes**: ...

## 约束
- 只修改与反馈相关的部分，其他保持不变
- 修订后的决策仍需基于统计数据
- 不要凭空想象新的考察角度
"""

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
- **考察模式**: （必须从输入中"可选考察模式"列表选择一个，直接使用原名称）
- **出题数量**: （推荐出几道题）
- **题型**: （推荐的题型：single_choice 或 comprehensive）

## 出题策略
- **examination_angles**: （建议的考察角度，2-3个，逗号分隔）
- **difficulty_gradient**: （难度梯度描述，如"从概念辨析到公式应用"）
- **should_be**: （这道题应该具备什么特征）
- **should_not_be**: （这道题不应该出现什么问题）
- **question_type_recommendation**: （推荐的题型和数量，如"2道选择题，1道综合题"）

## 模式概览
- **recommended_mode**: （必须与考察模式字段完全一致）
- **mode_rationale**: （为什么推荐这个模式，一句话）
- **alternative_modes**: （备选模式，从可选列表中选择，逗号分隔）

## 约束
- 不要重复或摘要原始数据——只做决策
- 不要输出知识点图谱或真题经验——这些由程序直接注入
- 决策必须基于统计数据，不要凭空想象
- 考察模式必须从"可选考察模式"列表中选择，不要自创模式名称
"""


# ── Data classes ──────────────────────────────────────────────

@dataclass
class SynthesisRequest:
    knowledge_tag: str = ""       # resolved tag from KnowledgeRetriever
    user_intent: str = ""         # free text, e.g. "出3道选择题，K2-K3难度"
    subject: str = ""             # optional subject hint
    difficulty: str = ""          # easy / medium / hard
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

        # ── Step 1.5: Pre-load experience card to extract available modes ──
        slot_hint = self._extract_slot_hint(tag, stats)
        slot_exp_card = self._load_slot_experience_card(slot_hint)
        if not slot_exp_card:
            slot_exp_card = self._find_matching_experience_card(
                tag, request.question_type,
            )
        if slot_exp_card:
            m = re.match(r"# (Q\d+)", slot_exp_card)
            if m:
                slot_hint = m.group(1)

        available_modes = self._extract_available_modes(slot_exp_card)

        # ── Step 2: Compute statistics summary for LLM context ──
        stats_summary = self._build_stats_summary(stats, request, available_modes)

        # ── Step 3: LLM teaching decisions (fresh or revision) ──
        if request.existing_blueprint and request.feedback:
            llm_messages = [
                {"role": "system", "content": BLUEPRINT_REVISION_SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"## 当前蓝图（教师已批注）\n\n{request.existing_blueprint}\n\n"
                    f"## 统计数据\n\n{stats_summary}\n\n"
                    f"## 教师反馈\n\n{request.feedback}"
                )},
            ]
        else:
            llm_messages = [
                {"role": "system", "content": BLUEPRINT_DESIGNER_SYSTEM_PROMPT},
                {"role": "user", "content": stats_summary},
            ]

        llm_result = await self._gateway.generate_text(
            messages=llm_messages,
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

        # ── Step 4: Merge into assembled.md ──
        parts = self._assemble_sections(
            slot_id=slot_hint,
            examination_mode=examination_mode,
            llm_decisions=llm_decisions,
            request=request,
            stats=stats,
            subtree=subtree,
            experiences=experiences,
            slot_exp_card=slot_exp_card,
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
        available_modes: list[str] | None = None,
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
        if request.difficulty:
            lines.append(f"- **难度要求**: {request.difficulty}")
        if request.question_count:
            lines.append(f"- **出题数量**: {request.question_count}")
        if request.question_type:
            lines.append(f"- **题型**: {request.question_type}")

        # Available modes from experience card — LLM must choose from these
        if available_modes:
            lines.append(f"- **可选考察模式（必须从中选择）**: {', '.join(available_modes)}")

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

    @staticmethod
    def _extract_available_modes(exp_card: str) -> list[str]:
        """Extract mode names from experience card headings."""
        if not exp_card:
            return []
        mode_pattern = re.compile(r"^(?:##|###) (模式[A-Z][：:](.+?))(?:\n|$)", re.MULTILINE)
        return [m.group(2).strip() for m in mode_pattern.finditer(exp_card)]

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
        slot_exp_card: str = "",
    ) -> list[str]:
        """Assemble the 7-section document matching artifact_store format."""
        from compose.artifact_store import (
            _extract_matching_mode,
            _extract_mode_years,
            _extract_knowledge_graph_section,
        )

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

        # ── Section 2: Basic info (from slot experience card or statistics) ──
        if slot_exp_card:
            from compose.artifact_store import _extract_basic_info
            basic_info = _extract_basic_info(slot_exp_card)
            if basic_info:
                parts.append(f"## 基本信息\n\n{basic_info}")
        else:
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

        # ── Section 3: Mode overview (from slot experience card, NOT just LLM) ──
        mode_from_card = ""
        if slot_exp_card and examination_mode:
            mode_from_card = _extract_matching_mode(slot_exp_card, examination_mode)
        if mode_from_card:
            parts.append(f"## 模式概览（来自题位经验卡）\n\n{mode_from_card}")
        else:
            # Fallback: LLM-generated mode overview
            mode_section = self._extract_section(llm_decisions, "模式概览")
            if mode_section:
                parts.append(f"## 模式概览（来自教学设计师决策）\n\n{mode_section}")

        # ── Section 4: Knowledge subtree (from retriever or knowledge graph) ──
        if subtree:
            parts.append(f"## 相关知识点细纲\n\n{subtree}")
        else:
            target_family = ""
            req_section_text = self._extract_section(llm_decisions, "本次出题要求")
            if req_section_text:
                m = re.search(r"\*?\*?知识域\*?\*?[:：]\s*(.+?)(?:\n|$)", req_section_text)
                if m:
                    target_family = m.group(1).strip()
            syllabus = _extract_knowledge_graph_section(target_family)
            if syllabus:
                parts.append(f"## 相关知识点细纲\n\n{syllabus}")

        # ── Section 5: Past year questions (from slot experience card) ──
        past_questions_injected = False
        if slot_exp_card:
            mode_years = _extract_mode_years(mode_from_card) if mode_from_card else []
            if mode_years:
                from compose.artifact_store import _build_question_entries
                question_entries = _build_question_entries(slot_id, mode_years)
                if question_entries:
                    parts.append(
                        f"## 往年真题经验（{examination_mode}，共{len(question_entries)}题）\n\n"
                        + "\n\n---\n\n".join(question_entries)
                    )
                    past_questions_injected = True
        # Fallback: individual question experiences from retriever
        if not past_questions_injected and experiences:
            exp_entries = []
            for exp in experiences:
                exp_entries.append(exp.content)
            if exp_entries:
                parts.append(
                    f"## 往年真题经验（共{len(exp_entries)}题）\n\n"
                    + "\n\n---\n\n".join(exp_entries)
                )

        # ── Section 5.5: 出题指导 should_be/should_not_be (from slot experience card) ──
        if slot_exp_card:
            guidance = self._extract_teaching_guidance(slot_exp_card)
            if guidance:
                parts.append(f"## 出题指导\n\n{guidance}")

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

    @staticmethod
    def _load_slot_experience_card(slot_id: str) -> str:
        """Load the slot experience card from data/slot_experiences/."""
        import os
        # Strip any suffix after the base slot_id (e.g. "Q43-1" → "Q43")
        base_slot = slot_id.split("-")[0] if "-" in slot_id else slot_id
        for candidate in (slot_id, base_slot):
            path = os.path.join("data", "slot_experiences", f"{candidate}_experience.md")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read()
        return ""

    @staticmethod
    def _find_matching_experience_card(
        knowledge_tag: str,
        question_type: str = "",
    ) -> str:
        """Fuzzy-match an experience card when slot_id lookup fails.

        Strategy:
        1. Scan all cards in data/slot_experiences/
        2. Score each card by keyword overlap with knowledge_tag
        3. Prefer cards matching the question_type (comprehensive → Q41-47)
        4. Return the highest-scoring card, or empty string.
        """
        import os

        card_dir = os.path.join("data", "slot_experiences")
        if not os.path.isdir(card_dir):
            return ""

        # Extract meaningful keywords from the knowledge tag
        # "平衡二叉树AVL的插入旋转" → ["平衡二叉树avl", "插入旋转", "平衡二叉树avl的插入旋转"]
        # Also extract shorter CJK substrings: "平衡", "二叉树", "插入", "旋转"
        tag_lower = knowledge_tag.lower()
        keywords = []
        for chunk in re.split(r"[>的与、，,\s]+", tag_lower):
            chunk = chunk.strip()
            if len(chunk) >= 2:
                keywords.append(chunk)
        # Add the full tag for exact-substring matches
        if len(tag_lower) >= 4:
            keywords.append(tag_lower)
        # For CJK-heavy tags, add 2-4 char sliding windows as secondary keywords
        cjk_text = re.sub(r"[a-zA-Z0-9\s]", "", tag_lower)
        if len(cjk_text) >= 4:
            for size in (2, 3, 4):
                for i in range(len(cjk_text) - size + 1):
                    sub = cjk_text[i : i + size]
                    if sub not in keywords:
                        keywords.append(sub)

        if not keywords:
            return ""

        # Determine slot range from question_type
        # comprehensive → Q41-Q47, single_choice → Q1-Q40
        qt_lower = question_type.lower()
        prefer_comp = "comp" in qt_lower or "综合" in qt_lower or "应用题" in qt_lower

        best_score = 0
        best_card = ""

        for fname in os.listdir(card_dir):
            if not fname.endswith("_experience.md"):
                continue
            path = os.path.join(card_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue

            # Slot name filter: prefer matching question type
            # Comprehensive slots: Q41-Q47 (综合应用题), Choice slots: Q1-Q40 (选择题)
            slot_name = fname.replace("_experience.md", "")
            slot_num = int(slot_name[1:]) if slot_name[1:].isdigit() else 0
            is_comp = 41 <= slot_num <= 47
            if prefer_comp and not is_comp:
                continue  # skip choice slots when we need comprehensive
            if not prefer_comp and is_comp:
                continue  # skip comprehensive slots when we need choice

            # Score by keyword matches in content
            content_lower = content.lower()
            score = 0
            for kw in keywords:
                count = content_lower.count(kw)
                if count > 0:
                    score += min(count, 5)  # cap per-keyword contribution

            if score > best_score:
                best_score = score
                best_card = content

        # Fallback: no keyword match — return default comprehensive card only
        if best_score == 0 and prefer_comp:
            path = os.path.join(card_dir, "Q43_experience.md")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read()

        return best_card

    @staticmethod
    def _extract_teaching_guidance(exp_card: str) -> str:
        """Extract should_be/should_not_be from the slot experience card."""
        m = re.search(r"## 出题指导\n(.*?)(?=\n## |\Z)", exp_card, re.DOTALL)
        return m.group(1).strip() if m else ""

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
