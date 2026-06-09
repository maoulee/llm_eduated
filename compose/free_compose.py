"""Route 3: Free composition — GLM drafts knowledge assignments, teacher refines.

For subjects without experience cards, this module:
1. GLM generates initial slot→knowledge point assignments based on KG
2. Python auto-completes each knowledge point from KG
3. Teacher reviews/annotates (pause point)
4. For retained points, runs Route 2's grep + classify flow
5. Teacher selects modes (pause point)
6. Python generates outline_draft.md
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .topic_search import (
    TopicModeCard,
    _slugify,
    classify_by_modes,
    generate_grep_keywords,
    grep_question_bank,
)


async def generate_knowledge_draft(
    kg_context: str,
    slot_templates: dict[str, dict],
    user_requirements: str,
    gateway,
    model_routing: dict[str, str] | None = None,
) -> list[dict]:
    """GLM generates initial knowledge point assignments for all slots.

    Uses config:free_compose model (default glm5.1) — the only step that
    may need deep reasoning.

    Args:
        kg_context: Knowledge graph text for target subjects (~5K chars)
        slot_templates: Dict of slot_id -> {type, score, ...}
        user_requirements: Teacher requirements text
        gateway: LLMGateway for free_compose model
        model_routing: Optional model routing config

    Returns:
        List of dicts: [{slot_id, question_type, knowledge, direction, difficulty}]
    """
    # Build slot info table
    slot_rows = []
    for sid, tpl in sorted(slot_templates.items()):
        q_type = tpl.get("question_type", tpl.get("type", "single_choice"))
        score = tpl.get("score", 2)
        slot_rows.append(f"| {sid} | {q_type} | {score}分 |")
    slot_table = "| 题号 | 题型 | 分值 |\n|------|------|------|\n" + "\n".join(slot_rows)

    prompt = f"""基于以下知识点图谱，为一套考试规划每个题位的考点。
只输出知识点和考察方向，不需要详细内容。

教师要求: {user_requirements}

知识点图谱:
{kg_context[:6000]}

题位表:
{slot_table}

输出格式（markdown表格）:
| 题号 | 题型 | 知识点 | 考察方向 | 难度(1-5) |

要求:
- 知识点必须来自上面的知识点图谱
- 确保知识点覆盖主要知识域，避免连续多题考同一知识点
- 难度1-5，整体偏中等"""

    messages = [{"role": "user", "content": prompt}]

    # Use stream_chat for GLM (may think deeply)
    try:
        result = await gateway.stream_chat(messages, max_tokens=4000)
        raw = result.get("content", "")
        if not raw:
            raw = result.get("reasoning_content", "")
    except Exception as e:
        print(f"  [Route 3] GLM 初稿生成失败: {e}")
        return []

    if not raw:
        return []

    # Parse markdown table
    assignments = _parse_knowledge_table(raw, slot_templates)
    print(f"  [Route 3] GLM 初稿: {len(assignments)}/{len(slot_templates)} 个题位")
    return assignments


def _parse_knowledge_table(raw: str, slot_templates: dict) -> list[dict]:
    """Parse GLM's markdown table output into structured assignments."""
    assignments = []
    seen_slots = set()

    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|--") or line.startswith("| 题号"):
            continue

        cells = [c.strip() for c in line.split("|")]
        # Filter empty cells from leading/trailing |
        cells = [c for c in cells if c]

        if len(cells) < 4:
            continue

        slot_id = cells[0].strip()
        # Clean slot_id: extract Q\d+ or TOPIC_\d+
        sid_match = re.match(r"(Q\d+|TOPIC_\d+)", slot_id)
        if not sid_match:
            continue
        slot_id = sid_match.group(1)

        if slot_id in seen_slots or slot_id not in slot_templates:
            continue
        seen_slots.add(slot_id)

        q_type = cells[1].strip() if len(cells) > 1 else ""
        knowledge = cells[2].strip() if len(cells) > 2 else ""
        direction = cells[3].strip() if len(cells) > 3 else ""
        difficulty_str = cells[4].strip() if len(cells) > 4 else "3"

        try:
            difficulty = int(re.search(r"\d", difficulty_str).group())
        except (AttributeError, ValueError):
            difficulty = 3

        assignments.append({
            "slot_id": slot_id,
            "question_type": q_type,
            "knowledge": knowledge,
            "direction": direction,
            "difficulty": min(max(difficulty, 1), 5),
        })

    return assignments


def auto_complete_from_kg(knowledge_points: list[dict], kg_text: str) -> list[dict]:
    """Auto-complete knowledge points from KG data.

    For each knowledge point, finds:
    - Parent chapter path
    - Sibling knowledge points
    - Sub-topics

    Args:
        knowledge_points: List of assignment dicts from generate_knowledge_draft
        kg_text: Raw KG text

    Returns:
        Enriched assignment dicts with kg_path, siblings, subtopics
    """
    if not kg_text:
        return knowledge_points

    kg_lines = kg_text.split("\n")
    heading_map = {}  # heading text -> parent heading
    heading_stack = []  # (level, text)

    for line in kg_lines:
        heading_match = re.match(r"^(#{1,4})\s+(.+)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            # Pop stack to find parent
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent = heading_stack[-1][1] if heading_stack else ""
            heading_map[text] = parent
            heading_stack.append((level, text))

    for kp in knowledge_points:
        name = kp.get("knowledge", "")
        if not name:
            kp["kg_path"] = ""
            kp["siblings"] = []
            kp["subtopics"] = []
            continue

        # Find path to root
        path_parts = []
        current = name
        visited = set()
        while current and current not in visited:
            visited.add(current)
            path_parts.append(current)
            current = heading_map.get(current, "")
        path_parts.reverse()
        kp["kg_path"] = " > ".join(path_parts)

        # Find siblings (same parent)
        parent = heading_map.get(name, "")
        siblings = []
        for h, p in heading_map.items():
            if p == parent and h != name:
                siblings.append(h)
        kp["siblings"] = siblings[:5]

        # Find subtopics (headings whose parent is this name)
        subtopics = [h for h, p in heading_map.items() if p == name]
        kp["subtopics"] = subtopics[:5]

    return knowledge_points


def format_draft_for_teacher(
    assignments: list[dict],
    difficulty_target: int = 3,
    composition_rationale: str = "基于知识点图谱自动规划",
) -> str:
    """Format knowledge draft as markdown for teacher review.

    This is the proposal document — no CONTRACT markers.

    Args:
        assignments: Enriched knowledge point assignments
        difficulty_target: Overall difficulty target
        composition_rationale: Composition rationale text

    Returns:
        Markdown string for teacher review (proposal stage)
    """
    lines = ["# 试卷大纲（草案）\n"]
    lines.append("## 整体规划\n")
    lines.append(f"- **difficulty_target**: {difficulty_target}\n")
    lines.append(f"- **composition_rationale**: {composition_rationale}\n")
    lines.append("\n")
    lines.append("## 题位总览\n")
    lines.append("| 题号 | 题型 | 知识点 | 考察方向 | 难度 | KG路径 |\n")
    lines.append("|------|------|--------|---------|------|--------|\n")

    for a in assignments:
        kg_path = a.get("kg_path", a.get("knowledge", ""))
        lines.append(
            f"| {a['slot_id']} | {a.get('question_type', '')} "
            f"| {a['knowledge']} | {a.get('direction', '')} "
            f"| {a['difficulty']} | {kg_path[:30]} |\n"
        )

    lines.append("\n---\n\n")
    lines.append("## 各题位详情\n\n")

    for a in assignments:
        lines.append(f"### {a['slot_id']}（{a.get('question_type', '选择题')}）\n")
        lines.append(f"- **知识点**: {a['knowledge']}\n")
        lines.append(f"- **考察方向**: {a.get('direction', '')}\n")
        lines.append(f"- **难度**: {a['difficulty']}/5\n")
        if a.get("kg_path"):
            lines.append(f"- **KG路径**: {a['kg_path']}\n")
        if a.get("siblings"):
            lines.append(f"- **兄弟知识点**: {', '.join(a['siblings'])}\n")
        if a.get("subtopics"):
            lines.append(f"- **子主题**: {', '.join(a['subtopics'])}\n")
        lines.append("\n")

    lines.append("## 教师操作\n")
    lines.append("请批注或移除不想考的知识点。系统将根据保留的知识点生成正式大纲。\n")

    return "".join(lines)


async def run_free_compose(
    subjects: list[str],
    slot_templates: dict[str, dict],
    user_requirements: str,
    free_gateway,
    interaction_gateway=None,
    model_routing: dict[str, str] | None = None,
    data_dir: str = "data/question_experiences",
) -> dict:
    """Run full Route 3 pipeline.

    Steps:
    1. GLM generates knowledge draft (uses free_gateway)
    2. Python auto-completes from KG
    3. (Pause: teacher reviews draft — returns draft for review)
    4. For retained points, runs Route 2 grep + classify (uses interaction_gateway)
    5. (Pause: teacher selects modes — returns topic cards for selection)
    6. Python generates outline_draft.md

    Args:
        subjects: Target subjects (e.g. ["计算机组成原理"])
        slot_templates: Dict of slot_id -> template
        user_requirements: Teacher requirements
        free_gateway: Gateway for free_compose model (glm5.1)
        interaction_gateway: Gateway for interaction model (api_vllm), defaults to free_gateway
        model_routing: Optional model routing config
        data_dir: Question experience directory

    Returns:
        Dict with draft, assignments, and topic_cards
    """
    from compose.compose_runner import load_kg_for_subjects

    if interaction_gateway is None:
        interaction_gateway = free_gateway

    # Step 1: Load KG for target subjects
    print(f"  [Route 3] 加载 KG: {subjects}")
    kg_text = load_kg_for_subjects(subjects)

    # Step 2: GLM generates knowledge draft
    print(f"  [Route 3] GLM 生成知识点初稿 ({len(slot_templates)} 题位)...")
    assignments = await generate_knowledge_draft(
        kg_text, slot_templates, user_requirements, free_gateway, model_routing
    )

    if not assignments:
        print("  [Route 3] GLM 未生成有效分配")
        return {"status": "error", "error": "empty draft", "assignments": []}

    # Step 3: Auto-complete from KG
    print(f"  [Route 3] KG 自动补全...")
    assignments = auto_complete_from_kg(assignments, kg_text)

    # Step 4: Format draft for teacher review (proposal — no CONTRACT)
    draft_md = format_draft_for_teacher(assignments)

    # Step 5: For each knowledge point, run Route 2 grep + classify
    print(f"  [Route 3] 对 {len(assignments)} 个知识点执行 grep + 分类...")
    topic_cards = {}
    for a in assignments:
        kp = a["knowledge"]
        sid = a["slot_id"]
        if not kp:
            continue

        # Generate keywords and grep
        keywords = await generate_grep_keywords(kp, kp, interaction_gateway, model_routing)
        hits = grep_question_bank(keywords, data_dir, max_results=20)

        # Classify
        if hits:
            topic_card = await classify_by_modes(hits, kp, interaction_gateway, model_routing)
            topic_cards[sid] = topic_card.to_dict()
            modes_str = ", ".join(f"{m.name}({m.count})" for m in topic_card.modes)
            print(f"    [{sid}] {kp}: {len(hits)}题 → {modes_str}")
        else:
            # No grep hits — create a minimal card
            topic_cards[sid] = {
                "id": _slugify(kp),
                "title": kp,
                "knowledge": kp,
                "modes": [{"name": f"{kp}综合型", "count": 0, "description": "未检索到相关题目", "suitable_types": ["single_choice"], "difficulty": "medium"}],
            }
            print(f"    [{sid}] {kp}: 无grep命中")

    # Step 6: Generate outline_draft.md with CONTRACT markers
    outline_md = _build_outline_from_assignments(assignments, topic_cards, slot_templates)

    return {
        "status": "ok",
        "draft_md": draft_md,
        "outline_md": outline_md,
        "assignments": assignments,
        "topic_cards": topic_cards,
    }


def _build_outline_from_assignments(
    assignments: list[dict],
    topic_cards: dict[str, dict],
    slot_templates: dict[str, dict],
) -> str:
    """Build full outline_draft.md from assignments + topic cards."""
    from compose.outline_yaml_generator import generate_from_topic_mode

    lines = ["# 试卷大纲\n"]
    lines.append("## 整体规划\n")
    lines.append("- **difficulty_target**: 3\n")
    lines.append("- **composition_rationale**: 基于知识点图谱自动规划，经教师确认\n")
    lines.append("\n")

    for a in assignments:
        sid = a["slot_id"]
        template = slot_templates.get(sid, {})
        card = topic_cards.get(sid)

        if card:
            section = generate_from_topic_mode(card, sid, template)
            lines.append(section)
        else:
            # Fallback: minimal section
            q_type = template.get("question_type", template.get("type", "single_choice"))
            score = template.get("score", 2)
            knowledge = a.get("knowledge", "")
            direction = a.get("direction", "")

            lines.append(f"## {sid}（{q_type}）\n")
            lines.append("### 当前推荐\n")
            lines.append(f"- **知识点**: {knowledge}\n")
            lines.append(f"- **考察方向**: {direction}\n")
            lines.append(f"- **难度**: {a.get('difficulty', 3)}/5\n")
            lines.append("\n")
            lines.append("### 候选替换池\n")
            lines.append("- (暂无候选模式)\n")
            lines.append("\n")
            lines.append("### 教师可编辑说明\n")
            lines.append("（教师可直接修改的命题说明区）\n")
            lines.append("\n")

            # CONTRACT marker
            lines.append(f"<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot={sid} -->\n")
            lines.append("```yaml\n")
            lines.append(f"slot_id: {sid}\n")
            lines.append(f"question_type: {q_type}\n")
            lines.append(f"score: {score}\n")
            lines.append(f"primary_target_name: {knowledge}\n")
            lines.append(f"target_difficulty: {a.get('difficulty', 3)}\n")
            if direction:
                lines.append(f"examination_mode: {direction}\n")
            lines.append("active_selection:\n")
            lines.append(f"  mode_id: auto\n")
            lines.append(f"  mode_name: {direction}\n")
            if knowledge:
                lines.append("  selected_knowledge:\n")
                lines.append(f"    - {knowledge}\n")
            lines.append("candidate_pool_visible: []\n")
            lines.append("excluded:\n")
            lines.append("  modes: []\n")
            lines.append("  knowledge: []\n")
            lines.append("```\n")
            lines.append(f"<!-- CONTRACT:END slot={sid} -->\n")
            lines.append("\n")

    return "".join(lines)
