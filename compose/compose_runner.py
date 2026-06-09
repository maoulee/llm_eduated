"""Compose runner — outline generation and slot assembly.

Handles paper composition (hybrid GPT or local Qwen), outline parsing,
skeleton checking, experience doc assembly, and manifest writing.
"""

import hashlib
import os
import re
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from core_new.doc_pipeline.contracts import SlotBlueprint

from . import artifact_store

_OUTLINE_SYSTEM_PROMPT = (
    "# 408考研组卷专家\n\n"
    "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲同时面向教师阅读和下游出题智能体。\n\n"
    "## 输入结构\n"
    "你将收到：\n"
    "1. 共享参考信息：K1-K5认知雷达评分标准 + 计算机组成原理知识点图谱\n"
    "2. 各题位信息：考点定位 + 可选考察模式（含适用知识点和频率）+ 出题指导\n\n"
    "## 输出格式（Outline v2）\n"
    "Markdown格式，包含以下部分：\n\n"
    "### 全局部分\n"
    "- `# 试卷大纲` 标题\n"
    "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
    "- `## 1. 教师阅读版总览` — 自然语言描述整卷定位、知识点覆盖策略；附题位总览表格\n\n"
    "### 每个题位（`## Qxx（题型）`）包含四个子节：\n"
    "1. `### 当前推荐` — 当前选定的考察模式、核心知识点、推荐理由\n"
    "2. `### 候选替换池` — 该题位所有可选模式列表（模式A/B/C/D），教师可删除不想考的模式\n"
    "3. `### 教师可编辑说明` — 自然语言描述：考查什么知识点、定位什么难度、"
    "对学生的能力要求、可能的风险点。面向教师阅读，可自由编辑。\n"
    "4. `### 机器选择契约` — 用 ```yaml 代码块包裹以下字段：\n"
    "   slot_id, question_type, score, target_subject, target_family, primary_target_name, "
    "target_difficulty, k_target, examination_mode, active_selection (mode_id, mode_name, selected_knowledge), "
    "candidate_pool_visible, excluded (modes, knowledge)\n\n"
    "## 核心约束\n"
    "- examination_mode 必须精确复制自题位的'可选考察模式'标题（从 ### 后复制完整名称，不含频率）\n"
    "- target_family 使用知识点图谱中的层级路径（如 CO-1 > 计算机系统概述）\n"
    "- 知识点选择应参考模式中的'适用知识点'字段，确保选的知识点适合该考察模式\n"
    "- 综合应用题（Q43-Q45）的 examination_mode 写模式标题（如'存储层次地址翻译与映射模拟'）\n"
    "- 不要输出选项风格、干扰策略等设计级决策\n"
    "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n"
    "- 系统只解析机器选择契约，不从教师自然语言描述猜测结论\n\n"
    "直接输出 Markdown 内容，不要用代码块包裹。"
)


def get_model_for_task(task: str, model_routing: dict | None = None) -> str:
    """从配置读取模型，不硬编码。

    Args:
        task: 任务类型（如 'interaction', 'free_compose', 'paper_composer'）
        model_routing: 可选的模型路由字典（CLI 覆盖）

    Returns:
        模型名称（如 'api_vllm', 'glm5.1'）
    """
    # 如果 task 存在于 model_routing 中，直接返回
    if model_routing and task in model_routing:
        return model_routing[task]

    # 从 pipeline.yaml 读取默认配置
    import yaml
    from pathlib import Path
    # compose_runner.py 在 compose/ 目录下，需要向上两级到达项目根目录
    config_path = Path(__file__).resolve().parent.parent / "config" / "pipeline.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        routing = raw.get("model_routing", {})
        if task in routing:
            return routing[task]
        # task 不在 model_routing 中，使用 interaction 作为默认
        return routing.get("interaction", "api_vllm")

    # 最终 fallback
    return "api_vllm"


def load_kg_for_subjects(subjects: list[str]) -> str:
    """Load knowledge graphs for specified subjects only.

    Args:
        subjects: List of subject names (e.g., ["计算机组成原理", "数据结构"])

    Returns:
        Markdown string with K-radar definitions + requested subject KGs.
    """
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    parts: list[str] = []

    # 1. K-radar definitions (always included, small and常驻)
    parts.append("# 共享参考信息（所有题位公用）")
    parts.append("")
    parts.append(K_RADAR_DEFINITIONS.strip())
    parts.append("")

    # 2. Knowledge point graphs for specified subjects only
    subject_files = {
        "计算机组成原理": "computer_organization.md",
        "数据结构": "data_structure.md",
        "操作系统": "operating_system_knowledge.md",
        "计算机网络": "computer_network.md",
    }

    for subject_name in subjects:
        filename = subject_files.get(subject_name)
        if filename:
            kg = _extract_knowledge_graph(filename)
            if kg:
                kg = _translate_kg(kg)
                parts.append(f"## {subject_name}知识点图谱")
                parts.append("")
                parts.append(f"> 以下是{subject_name}的完整知识点层级结构，供规划知识点覆盖时参考。")
                parts.append("")
                parts.append(kg)

    return "\n".join(parts)


def load_experience_for_slots(slot_ids: list[str], exp_dir: str = "data/slot_experiences") -> dict[str, str]:
    """Load experience cards for specified slot IDs only.

    Args:
        slot_ids: List of slot IDs to load (e.g., ["Q41", "Q42"])
        exp_dir: Directory containing experience markdown files

    Returns:
        Dict mapping slot_id -> experience content. Missing slots return empty string.
    """
    _exp_dir = Path(exp_dir)
    experience_cards: dict[str, str] = {}

    for sid in slot_ids:
        exp_path = _exp_dir / f"{sid}_experience.md"
        if exp_path.exists():
            experience_cards[sid] = exp_path.read_text(encoding="utf-8")
        else:
            experience_cards[sid] = ""

    return experience_cards


def _build_shared_header() -> str:
    """Build shared header: K-radar definitions + knowledge point graphs for all subjects.

    Compatibility wrapper for load_kg_for_subjects. Loads all subjects for backward compatibility.
    """
    all_subjects = ["计算机组成原理", "数据结构", "操作系统", "计算机网络"]
    return load_kg_for_subjects(all_subjects)


def _build_slot_contracts_md(templates: dict, exp_dir: str = "data/slot_experiences") -> str:
    """Build shared header + concatenated slot contracts for compose prompts.

    Compatibility wrapper that uses the new on-demand loading functions internally.
    """
    from core_new.slot_contract import build_slot_contract

    # Load only required experience cards
    slot_ids = list(templates.keys())
    experience_cards = load_experience_for_slots(slot_ids, exp_dir)

    # Build per-slot contracts
    contracts = {}
    for sid, tpl in templates.items():
        try:
            contract = build_slot_contract(
                sid, tpl,
                experience_cards.get(sid, ""),
                slot_md_content=None,
            )
            if contract:
                contracts[sid] = contract
        except Exception:
            pass

    # Shared header + per-slot contracts
    header = _build_shared_header()
    slot_sections = "\n\n---\n\n".join(
        contracts[sid] for sid in sorted(contracts.keys())
    )
    # Translate all abbreviated codes in the combined output
    combined = header + "\n\n---\n\n" + slot_sections
    return _translate_kg(combined)


def _extract_knowledge_graph(filename: str = "computer_organization.md") -> str:
    """Extract title hierarchy tree from a knowledge graph file.

    Keeps only heading lines (##/###/####) and leaf node names (- item),
    removes '属性:' descriptions and '来源页' info.
    """
    import re as _re

    kg_path = Path("data/kg") / filename
    if not kg_path.exists():
        return ""

    text = kg_path.read_text(encoding="utf-8")
    lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.rstrip()
        # Keep headings
        if _re.match(r"^#{1,4}\s", stripped):
            lines.append(stripped)
        # Keep leaf node names (top-level bullets), skip sub-bullets with 属性/来源
        elif stripped.startswith("- ") and not stripped.startswith("  "):
            # Skip "来源页" and "属性:" lines
            name = stripped[2:].strip()
            if name and "来源页" not in stripped and "属性:" not in stripped:
                lines.append(stripped)
        # Skip everything else (sub-bullets with 属性, blank lines, etc.)

    # Collapse consecutive blank lines
    result: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return "\n".join(result)


def _translate_kg(text: str) -> str:
    """Translate abbreviated codes (DS-1, CO-1 etc.) to full chapter names."""
    from core_new.subject_map import translate_code
    return translate_code(text)


def extract_slot_recommendation(experience_card: str) -> dict:
    """Extract recommendation data from experience card.

    Args:
        experience_card: Raw markdown content of experience card

    Returns:
        Dict with:
        - recommended_mode: str (mode with highest frequency)
        - recommended_frequency: str (e.g., "53.8%")
        - alternatives: list[dict] with {mode, frequency}
        - applicable_knowledge: list[str] (knowledge points from recommended mode)
    """
    import re

    result = {
        "recommended_mode": "",
        "recommended_frequency": "",
        "alternatives": [],
        "applicable_knowledge": [],
    }

    if not experience_card:
        return result

    # Find考察模式分布 section
    dist_section_match = re.search(r'## 考察模式分布\s*(.*?)---', experience_card, re.DOTALL)
    if not dist_section_match:
        return result

    dist_section = dist_section_match.group(1)
    lines = [line.strip() for line in dist_section.split("\n") if line.strip()]

    # Parse mode distribution lines: "- **模式名**：X/Y (Z%)"
    modes_with_freq = []
    for line in lines:
        # Match pattern: - **mode**: X/Y (Z%)
        # The mode name can contain Chinese characters, letters, dashes, etc.
        mode_match = re.match(r'-\s*\*{2}([^*]+?)\*{2}：\s*(\d+)/(\d+)\s*\(([\d.]+)%\)', line)
        if mode_match:
            mode_name = mode_match.group(1).strip()
            freq_percent = mode_match.group(4) + "%"
            modes_with_freq.append((mode_name, freq_percent))

    # Sort by frequency (extract number) and pick highest
    if modes_with_freq:
        modes_with_freq.sort(key=lambda x: float(x[1].rstrip('%')), reverse=True)
        result["recommended_mode"] = modes_with_freq[0][0]
        result["recommended_frequency"] = modes_with_freq[0][1]
        result["alternatives"] = [{"mode": m, "frequency": f} for m, f in modes_with_freq[1:]]

    # Find applicable knowledge from the first mode (recommended mode)
    # Look for "适用知识点范围" in the experience card
    knowledge_match = re.search(r'适用知识点范围[^：:]*[：:]\s*(.+?)(?=\n-|$)', experience_card, re.DOTALL)
    if knowledge_match:
        knowledge_text = knowledge_match.group(1).strip()
        # Split by common delimiters
        points = re.split(r'[、,，]', knowledge_text)
        result["applicable_knowledge"] = [p.strip() for p in points if p.strip()]

    return result


def render_slot_card(slot_id: str, template: dict, experience_card: str, gateway=None) -> dict:
    """Render a slot card with recommendation data.

    Args:
        slot_id: Slot identifier (e.g., "Q12")
        template: Slot template dict with type, score, etc.
        experience_card: Raw markdown content of experience card
        gateway: Optional gateway for LLM-based recommendation reasoning

    Returns:
        Dict with slot_card data including recommended_mode, frequency, alternatives, etc.
    """
    # Extract data from experience card
    extracted = extract_slot_recommendation(experience_card)

    # Build base card
    card = {
        "slot_card": {
            "slot_id": slot_id,
            "type": template.get("question_type", "unknown"),
            "score": template.get("score", 0),
            "recommended_mode": extracted["recommended_mode"],
            "recommended_frequency": extracted["recommended_frequency"],
            "recommended_reason": "",
            "alternatives": extracted["alternatives"],
            "applicable_knowledge": extracted["applicable_knowledge"],
            "teacher_actions": ["confirm", "change_mode", "exclude_knowledge", "remove"],
        }
    }

    # If gateway provided, use LLM for recommendation reasoning
    if gateway and extracted["recommended_mode"]:
        card["slot_card"]["recommended_reason"] = _generate_recommendation_reason(
            slot_id, extracted["recommended_mode"], extracted["recommended_frequency"], gateway
        )
    else:
        card["slot_card"]["recommended_reason"] = f"该模式在{slot_id}题位出现频率最高({extracted['recommended_frequency']})"

    return card


def _generate_recommendation_reason(slot_id: str, mode: str, frequency: str, gateway) -> str:
    """Generate recommendation reasoning using LLM (lightweight call)."""
    prompt = f"""你是组卷专家。请简短解释为什么推荐以下模式：

题位：{slot_id}
推荐模式：{mode}
频率：{frequency}

请用一句话给出推荐理由，不超过50字。只输出理由，不要其他内容。"""

    try:
        messages = [{"role": "user", "content": prompt}]
        result = gateway.generate_text(messages, max_tokens=200)
        return result.content.strip() if result.content else f"该模式在{slot_id}题位出现频率最高({frequency})"
    except Exception:
        return f"该模式在{slot_id}题位出现频率最高({frequency})"


async def render_all_slot_cards(slot_ids: list[str], templates: dict, exp_dir: str = "data/slot_experiences", gateway=None) -> list[dict]:
    """Render slot cards for multiple slots.

    Args:
        slot_ids: List of slot IDs to render
        templates: Dict of slot_id -> template data
        exp_dir: Directory containing experience cards
        gateway: Optional gateway for LLM-based reasoning

    Returns:
        List of slot card dicts
    """
    # Load experience cards on-demand
    experience_cards = load_experience_for_slots(slot_ids, exp_dir)

    cards = []
    for slot_id in slot_ids:
        template = templates.get(slot_id, {})
        exp_card = experience_cards.get(slot_id, "")

        card = render_slot_card(slot_id, template, exp_card, gateway)
        cards.append(card)

    return cards


async def _compose_hybrid(templates, user_requirements, exp_dir="data/slot_experiences") -> tuple[str, dict]:
    """Hybrid composition: GPT generates outline via WebGPT.

    Returns (outline_md, blueprint_dict).
    """
    from core_new.webgpt_client import get_webgpt_client
    from core_new.slot_prompts import PAPER_OUTLINE_PROMPT

    client = get_webgpt_client()
    if not client:
        print("  ERROR: WebGPT not configured for hybrid composition")
        return "", {}

    # Run-scoped session key prevents cross-run context leakage
    compose_session = f"compose-{time.monotonic_ns()}"

    slot_md = _build_slot_contracts_md(templates, exp_dir)
    prompt = PAPER_OUTLINE_PROMPT.format(
        user_requirements=user_requirements,
        slot_contracts_md=slot_md,
        total_slots=len(templates),
    )

    t0 = time.monotonic()
    try:
        raw = await client.delegate(
            agent_name="hybrid_paper_composer",
            slot_id=compose_session,
            system_prompt=_OUTLINE_SYSTEM_PROMPT,
            content=prompt,
        )
    except Exception as e:
        print(f"  ERROR: GPT call failed: {e}")
        return "", {}
    finally:
        try:
            await client.cleanup(slot_id=compose_session)
        except Exception:
            pass

    elapsed = time.monotonic() - t0
    print(f"  GPT responded in {elapsed:.1f}s ({len(raw)} chars)")

    blueprint = _parse_outline_to_blueprint(raw, templates)
    _print_blueprint_summary(blueprint)
    return raw, blueprint


async def _compose_local(gateway, templates, user_requirements, exp_dir="data/slot_experiences") -> tuple[str, dict]:
    """Local composition: Qwen generates outline via gateway.

    Returns (outline_md, blueprint_dict).
    """
    from core_new.slot_prompts import PAPER_OUTLINE_PROMPT

    slot_md = _build_slot_contracts_md(templates, exp_dir)
    prompt = PAPER_OUTLINE_PROMPT.format(
        user_requirements=user_requirements,
        slot_contracts_md=slot_md,
        total_slots=len(templates),
    )

    messages = [
        {"role": "system", "content": _OUTLINE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    t0 = time.monotonic()
    try:
        # Use stream_chat to avoid timeout on long compose responses (GLM thinking mode)
        stream_result = await gateway.stream_chat(messages, max_tokens=30000)
        raw = stream_result.get("content", "")
        if not raw:
            # Fallback: reasoning might contain the actual answer
            raw = stream_result.get("reasoning_content", "")
    except Exception as e:
        print(f"  ERROR: Local compose failed: {e}")
        return "", {}

    elapsed = time.monotonic() - t0
    print(f"  Local Qwen responded in {elapsed:.1f}s ({len(raw)} chars)")

    blueprint = _parse_outline_to_blueprint(raw, templates)
    _print_blueprint_summary(blueprint)
    return raw, blueprint


def _print_blueprint_summary(blueprint: dict) -> None:
    slots = blueprint.get("slots", [])
    print(f"  题位数: {len(slots)}")
    print(f"  组卷思路: {blueprint.get('composition_rationale', 'N/A')[:200]}")
    for sb in slots:
        slot_id = sb.slot_id if isinstance(sb, SlotBlueprint) else sb.get("slot_id")
        subject = sb.target_subject if isinstance(sb, SlotBlueprint) else sb.get("target_subject", "?")
        name = sb.primary_target_name if isinstance(sb, SlotBlueprint) else sb.get("primary_target_name", "?")
        diff = sb.target_difficulty if isinstance(sb, SlotBlueprint) else sb.get("target_difficulty", "?")
        print(
            f"    {slot_id}: {subject}/{name} "
            f"d={diff}"
        )


def _extract_yaml_contract(content: str) -> dict:
    """Extract YAML contract from content.

    Delegates to markdown_contract_parser. Falls back to direct heading+yaml
    regex for slot fragments without ## Qxx headings.
    """
    from compose.markdown_contract_parser import scan_contract_blocks, load_yaml_contract, _LEGACY_HEADING
    import yaml

    blocks = scan_contract_blocks(content)
    for block in blocks:
        loaded = load_yaml_contract(block)
        if loaded.data:
            return loaded.data

    # Fallback: direct regex for content fragments (no ## Qxx heading)
    m = _LEGACY_HEADING.search(content)
    if m:
        try:
            return yaml.safe_load(m.group(1)) or {}
        except Exception:
            return {}

    return {}


def _parse_outline_to_blueprint(outline_md: str, templates: dict) -> dict:
    """Parse outline MD into blueprint dict format.

    Delegates to markdown_contract_parser for unified parsing, then
    maps SlotContract → SlotBlueprint. Falls back to legacy **field**
    extraction for fields not in the YAML contract.
    """
    from compose.markdown_contract_parser import parse_outline_to_selection

    result = parse_outline_to_selection(outline_md)
    overall_difficulty = result.header.difficulty_target
    composition_rationale = result.header.composition_rationale

    slots: list[SlotBlueprint] = []
    parts = re.split(r"## ((?:Q\d+|TOPIC_\d+))", outline_md)

    for contract in result.slots:
        # Find content for this slot (legacy **field** fallback)
        content = ""
        for i in range(1, len(parts), 2):
            if parts[i] == contract.slot_id:
                content = parts[i + 1] if i + 1 < len(parts) else ""
                break

        tpl = templates.get(contract.slot_id, {})

        # Extract raw YAML data for blueprint-level fields not in SlotContract
        yaml_data = _extract_yaml_contract(content)

        def _extract(field: str, default: str = "") -> str:
            # YAML data takes priority, then legacy **field** format
            if yaml_data and field in yaml_data:
                return str(yaml_data[field])
            m = re.search(rf"\* *{field}[*:\s]*(.+?)(?:\n|$)", content)
            return m.group(1).strip() if m else default

        target_subject = _extract("target_subject") or tpl.get("subject", "")
        difficulty_str = _extract("difficulty_level") or _extract("target_difficulty", "3")
        try:
            difficulty = int(difficulty_str)
        except ValueError:
            difficulty = 3

        slots.append(SlotBlueprint(
            slot_id=contract.slot_id,
            target_subject=target_subject,
            target_family=_extract("target_family"),
            primary_target_name=_extract("primary_target_name"),
            target_difficulty=difficulty,
            examination_mode=contract.examination_mode,
            k_target=_extract("k_target"),
            difficulty_rationale=_extract("difficulty_rationale"),
            question_type=contract.question_type,
            score=contract.score,
            active_selection=contract.active_selection,
            candidate_pool_visible=contract.candidate_pool_visible,
            excluded_modes=contract.excluded_modes,
            excluded_knowledge=contract.excluded_knowledge,
            teacher_annotation=contract.teacher_annotation,
        ))

    return {
        "paper_type": "408模拟卷",
        "total_questions": len(slots),
        "difficulty_target": overall_difficulty,
        "composition_rationale": composition_rationale,
        "slots": slots,
    }


def determine_route(
    compose_dir: str,
    slot_templates: dict,
    exp_dir: str = "data/slot_experiences",
) -> tuple[int, str]:
    """Determine which compose route to use based on intake output.

    Args:
        compose_dir: Compose output directory (may contain intake files)
        slot_templates: Available slot templates
        exp_dir: Experience cards directory

    Returns:
        (route_number, reason_string)
        - route 1: paper_request + has experience cards
        - route 2: slot_blueprint (single knowledge point)
        - route 3: paper_request + no experience cards
    """
    compose_path = Path(compose_dir)

    # Check for slot_blueprint.yaml → Route 2
    blueprint_path = compose_path / "slot_blueprint.yaml"
    if blueprint_path.exists():
        return 2, "slot_blueprint detected — single knowledge point"

    # Check for paper_request.yaml → Route 1 or 3
    request_path = compose_path / "paper_request.yaml"
    if request_path.exists():
        try:
            with open(request_path, encoding="utf-8") as f:
                pr = yaml.safe_load(f)
        except Exception:
            pr = {}

        has_experience = False
        for sid in slot_templates:
            exp_path = Path(exp_dir) / f"{sid}_experience.md"
            if exp_path.exists():
                has_experience = True
                break

        if has_experience:
            return 1, "paper_request + experience cards available"
        else:
            return 3, "paper_request + no experience cards"

    # Default: check if experience cards exist for any slot
    for sid in slot_templates:
        if (Path(exp_dir) / f"{sid}_experience.md").exists():
            return 1, "experience cards available (default)"

    return 3, "no intake files, no experience cards — free compose"


async def compose_route_2(
    gateway,
    slot_blueprint: dict,
    slot_templates: dict,
    model_routing: dict[str, str] | None = None,
    data_dir: str = "data/question_experiences",
) -> tuple[str, dict]:
    """Route 2: Single knowledge point — grep + classify.

    Args:
        gateway: LLMGateway for interaction model
        slot_blueprint: Parsed slot_blueprint.yaml
        slot_templates: Available slot templates
        model_routing: Optional model routing config
        data_dir: Question experience directory

    Returns:
        (outline_md, blueprint_dict)
    """
    from compose.topic_search import run_topic_search

    topic_name = slot_blueprint.get("primary_target_name", "")
    slot_id = slot_blueprint.get("slot_id", "TOPIC_001")
    template = slot_templates.get(slot_id, {
        "question_type": slot_blueprint.get("question_type", "single_choice"),
        "score": slot_blueprint.get("score", 2),
    })

    print(f"  [Route 2] 知识点: {topic_name}, 题位: {slot_id}")

    result = await run_topic_search(
        topic_name=topic_name,
        slot_id=slot_id,
        template=template,
        gateway=gateway,
        model_routing=model_routing,
        data_dir=data_dir,
    )

    outline_md = result["outline_section"]
    topic_card = result["topic_card"]

    # Build blueprint dict for downstream compatibility
    modes = topic_card.get("modes", [])
    selected_mode = modes[0]["name"] if modes else ""
    difficulty = slot_blueprint.get("difficulty_level", 3)
    if isinstance(difficulty, str):
        try:
            difficulty = int(difficulty)
        except ValueError:
            difficulty = 3

    sb = SlotBlueprint(
        slot_id=slot_id,
        target_subject=slot_blueprint.get("target_subject", ""),
        target_family=slot_blueprint.get("target_family", ""),
        primary_target_name=topic_name,
        target_difficulty=difficulty,
        examination_mode=selected_mode,
        question_type=slot_blueprint.get("question_type", "single_choice"),
        score=slot_blueprint.get("score", 2),
        active_selection=slot_blueprint.get("active_selection", {}),
        candidate_pool_visible=[m["name"] for m in modes],
        excluded_modes=slot_blueprint.get("excluded", {}).get("modes", []),
        excluded_knowledge=slot_blueprint.get("excluded", {}).get("knowledge", []),
        teacher_annotation=slot_blueprint.get("teacher_annotation", ""),
    )

    # Wrap outline in full document
    full_outline = f"# 试卷大纲\n\n## 整体规划\n- **difficulty_target**: {difficulty}\n- **composition_rationale**: 单知识点组卷 — {topic_name}\n\n{outline_md}"

    blueprint = {
        "paper_type": "单知识点",
        "total_questions": 1,
        "difficulty_target": difficulty,
        "composition_rationale": f"单知识点组卷: {topic_name}",
        "slots": [sb],
    }

    return full_outline, blueprint


async def compose_route_3(
    gateway,
    slot_templates: dict,
    user_requirements: str,
    model_routing: dict[str, str] | None = None,
    data_dir: str = "data/question_experiences",
) -> tuple[str, dict]:
    """Route 3: Free composition — GLM draft + grep + classify.

    Args:
        gateway: LLMGateway (will be used for both free_compose and interaction)
        slot_templates: Available slot templates
        user_requirements: Teacher requirements text
        model_routing: Optional model routing config
        data_dir: Question experience directory

    Returns:
        (outline_md, blueprint_dict)
    """
    from compose.free_compose import run_free_compose

    # Determine subjects from requirements or default
    subjects = _infer_subjects(user_requirements)
    print(f"  [Route 3] 科目: {subjects}")

    result = await run_free_compose(
        subjects=subjects,
        slot_templates=slot_templates,
        user_requirements=user_requirements,
        free_gateway=gateway,
        interaction_gateway=gateway,
        model_routing=model_routing,
        data_dir=data_dir,
    )

    if result.get("status") != "ok":
        error = result.get("error", "unknown Route 3 failure")
        print(f"  [Route 3] 失败: {error}")
        return "", {"error": error}

    outline_md = result["outline_md"]
    assignments = result["assignments"]

    # Parse outline for blueprint
    blueprint = _parse_outline_to_blueprint(outline_md, slot_templates)

    return outline_md, blueprint


def _infer_subjects(requirements: str) -> list[str]:
    """Infer target subjects from requirements text."""
    subject_keywords = {
        "计算机组成原理": ["组成原理", "计算机组成", "CO", "硬件"],
        "数据结构": ["数据结构", "DS", "算法", "树", "图", "排序"],
        "操作系统": ["操作系统", "OS", "进程", "内存管理"],
        "计算机网络": ["计算机网络", "网络", "TCP", "IP", "CN"],
    }
    found = []
    for subject, keywords in subject_keywords.items():
        for kw in keywords:
            if kw in requirements:
                if subject not in found:
                    found.append(subject)
                break
    return found if found else ["计算机组成原理"]


async def compose_paper(gateway, templates, user_requirements, model_routing=None, exp_dir="data/slot_experiences") -> tuple[str, dict]:
    """Step 1: Generate paper outline/blueprint.

    Routes to hybrid (GPT via WebGPT) or local (Qwen via gateway).
    Returns (outline_md, blueprint_dict).
    """
    print("=" * 60)
    is_hybrid = model_routing and str(model_routing.get("paper_composer", "")).lower() == "hybrid"

    if is_hybrid:
        print("Step 1: Compose — 规划试卷蓝图 (hybrid: GPT→Qwen)")
        print("=" * 60)
        return await _compose_hybrid(templates, user_requirements, exp_dir)
    else:
        print("Step 1: Compose — 规划试卷蓝图 (local: Qwen)")
        print("=" * 60)
        return await _compose_local(gateway, templates, user_requirements, exp_dir)


def _write_manifest(compose_dir: str, run_id: str, routing_profile: str, slot_info: list, compose_time: float) -> None:
    """Write manifest.md to compose directory with run metadata and per-slot info."""
    manifest_path = Path(compose_dir) / "manifest.md"

    lines = [
        "# Compose Run Manifest",
        "",
        f"- run_id: {run_id}",
        f"- routing_profile: {routing_profile}",
        f"- total_slots: {len(slot_info)}",
        f"- compose_time_s: {round(compose_time, 2)}",
        "",
        "## Slots",
        "| Slot | Mode | Difficulty | Assembled Chars | Hash |",
        "|------|------|-----------|-----------------|------|",
    ]

    for slot in slot_info:
        slot_id = slot.get("slot_id", "?")
        mode = slot.get("mode", "?")
        difficulty = slot.get("difficulty", "?")
        content = slot.get("content", "")
        char_count = len(content)
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:8] if content else "N/A"
        lines.append(f"| {slot_id} | {mode} | {difficulty} | {char_count} | {content_hash} |")

    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  manifest.md written ({len(slot_info)} slots)")


def _filter_templates(slot_templates: dict, slot_ids: list | None) -> dict:
    """Filter templates by slot_ids."""
    if slot_ids:
        return {k: v for k, v in slot_templates.items() if k in slot_ids}
    return slot_templates


def _build_type_hint(templates: dict, slot_ids: list | None) -> str:
    """Build a type-hint string for the user requirements."""
    if not slot_ids:
        return ""
    slot_types = []
    for sid, tmpl in templates.items():
        q_type = tmpl.get("question_type", "")
        if q_type == "comprehensive" or (sid.startswith("Q") and sid[1:].isdigit() and int(sid[1:]) >= 43):
            slot_types.append(f"{sid}(综合应用题)")
        else:
            slot_types.append(f"{sid}(选择题)")
    return "。指定题位：" + "、".join(slot_types) + "。"


def _write_sidecar_artifacts(compose_dir: str, outline_md: str) -> None:
    """Parse outline and write paper_selection.yaml + parse_report.md."""
    from compose.markdown_contract_parser import parse_outline_to_selection
    from compose.outline_contract_parser import write_paper_selection

    result = parse_outline_to_selection(outline_md)

    selection_path = os.path.join(compose_dir, "paper_selection.yaml")
    write_paper_selection(result.slots, selection_path)

    report_path = os.path.join(compose_dir, "parse_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result.report)

    print(f"  paper_selection.yaml ({len(result.slots)} slots, status={result.validation.status})")
    if result.validation.errors:
        for e in result.validation.errors:
            print(f"    [error] {e.slot_id}: {e.message}")


async def run_compose(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list | None = None,
    output_dir: str = "docs",
    model_routing: dict[str, str] | None = None,
    exp_dir: str = "data/slot_experiences",
) -> dict:
    """Phase A: Compose outline + assemble experience docs → save to compose/.

    Returns dict with compose metadata (outline path, assembled paths, slot_count).
    """
    compose_start = time.monotonic()

    # Check for paper_request.yaml (intake layer output)
    compose_dir = os.path.join(output_dir, "compose")
    paper_request = load_paper_request(compose_dir)
    if paper_request:
        mapped = map_paper_request_to_params(paper_request)
        # Merge: paper_request enhances existing requirements, not just fallback
        mapped_req = mapped.get("user_requirements", "")
        if mapped_req:
            if user_requirements:
                user_requirements = f"{user_requirements}\n\n[intake 补充] {mapped_req}"
            else:
                user_requirements = mapped_req
        # Model routing: mapped is base, explicit CLI params take precedence
        if mapped.get("model_routing"):
            model_routing = {**mapped["model_routing"], **(model_routing or {})}
        print(f"  [intake] Merged paper_request params: {len(user_requirements)} chars requirements")

    templates = _filter_templates(slot_templates, slot_ids)
    if not templates:
        print("No templates to compose from!")
        return {"status": "error", "error": "no templates"}

    type_hint = _build_type_hint(templates, slot_ids)
    if type_hint:
        user_requirements += type_hint

    # Determine routing profile name
    routing_profile = "unknown"
    if model_routing:
        routing_profile = model_routing.get("paper_composer", "all_local")
    else:
        # 如果没有提供 model_routing，从 pipeline.yaml 读取默认配置
        model_routing = {
            "paper_composer": get_model_for_task("free_compose", model_routing=None),
            "interaction": get_model_for_task("interaction", model_routing=None),
        }
        routing_profile = model_routing.get("paper_composer", "all_local")
        print(f"  [config] Loaded model_routing from pipeline.yaml: {model_routing}")

    # Step 0: Determine route
    route, route_reason = determine_route(compose_dir, templates, exp_dir)
    print(f"  [route] Route {route}: {route_reason}")

    # Step 1: Compose — route to appropriate path
    if route == 2:
        # Route 2: slot_blueprint → single topic grep + classify
        blueprint_path = Path(compose_dir) / "slot_blueprint.yaml"
        if not blueprint_path.exists():
            return {"status": "error", "error": "Route 2 requires slot_blueprint.yaml"}
        with open(blueprint_path, encoding="utf-8") as f:
            slot_blueprint_data = yaml.safe_load(f) or {}
        if not slot_blueprint_data:
            return {"status": "error", "error": "slot_blueprint.yaml is empty or invalid"}
        outline_md, blueprint = await compose_route_2(
            gateway, slot_blueprint_data, templates, model_routing=model_routing,
        )
    elif route == 3:
        # Route 3: free composition — GLM draft + grep + classify
        outline_md, blueprint = await compose_route_3(
            gateway, templates, user_requirements, model_routing=model_routing,
        )
    else:
        # Route 1 (default): experience card rendering or legacy LLM compose
        outline_md, blueprint = await compose_paper(
            gateway, templates, user_requirements, model_routing=model_routing, exp_dir=exp_dir,
        )

    if not blueprint:
        return {"status": "error", "step": "compose"}

    # Step 1b: Skeleton check (needs dict representation for downstream)
    from core_new.skeleton_checker import check_blueprint_skeleton
    raw_slots = blueprint.get("slots", [])
    slots_as_dicts = [asdict(sb) if isinstance(sb, SlotBlueprint) else sb for sb in raw_slots]
    blueprint_for_check = {**blueprint, "slots": slots_as_dicts}
    skeleton_violations = check_blueprint_skeleton(blueprint_for_check)
    if skeleton_violations:
        print(f"  骨架检查: {len(skeleton_violations)} violations")
        for v in skeleton_violations:
            print(f"    [{v['slot_id']}] {v['rule']}: {v['detail']}")
    else:
        print("  骨架检查: pass")

    # Ensure all slots are SlotBlueprint instances
    slot_blueprints: list[SlotBlueprint] = []
    for sb in raw_slots:
        if isinstance(sb, SlotBlueprint):
            slot_blueprints.append(sb)
        else:
            slot_blueprints.append(SlotBlueprint(**{k: v for k, v in sb.items() if k in SlotBlueprint.__dataclass_fields__}))

    if not slot_blueprints:
        print("  ERROR: No slot blueprints generated")
        return {"status": "error", "step": "compose", "error": "empty slots"}

    # Inherit question_type from templates
    for sb in slot_blueprints:
        if not sb.question_type:
            tpl = templates.get(sb.slot_id, {})
            if tpl.get("question_type"):
                sb.question_type = tpl["question_type"]

    # Step 2: Assemble experience docs
    compose_dir = os.path.join(output_dir, "compose")
    os.makedirs(compose_dir, exist_ok=True)
    compose_path = Path(compose_dir)

    # Keep compose/ as a snapshot of the current compose run
    for stale_path in compose_path.glob("*_assembled.md"):
        stale_path.unlink()
    outline_stale = compose_path / "outline.md"
    if outline_stale.exists():
        outline_stale.unlink()

    assembled_paths = {}
    slot_info_for_manifest = []
    for sb in slot_blueprints:
        sid = sb.slot_id
        mode = sb.examination_mode
        difficulty = sb.target_difficulty
        slot_md_path = os.path.join("data", "slots", f"{sid}_slot.md")
        exp_path = os.path.join(exp_dir, f"{sid}_experience.md")
        sb_dict = asdict(sb)
        doc = artifact_store.assemble_slot_experience_doc(sid, mode, slot_md_path, exp_path, outline_entry=sb_dict)
        print(f"  [{sid}] 经验文档已组装: {mode} ({len(doc)} chars)")

        # Save assembled doc to disk
        assembled_path = os.path.join(compose_dir, f"{sid}_assembled.md")
        with open(assembled_path, "w", encoding="utf-8") as f:
            f.write(doc)
        assembled_paths[sid] = assembled_path

        # Collect slot info for manifest
        slot_info_for_manifest.append({
            "slot_id": sid,
            "mode": mode,
            "difficulty": difficulty,
            "content": doc,
        })

    # Save outline MD
    outline_path = os.path.join(compose_dir, "outline.md")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(outline_md)

    # Generate sidecar artifacts: paper_selection.yaml + parse_report.md
    _write_sidecar_artifacts(compose_dir, outline_md)

    # Generate run_id and write manifest
    compose_elapsed = time.monotonic() - compose_start
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
    _write_manifest(compose_dir, run_id, routing_profile, slot_info_for_manifest, compose_elapsed)

    print(f"\n组卷产物已保存到: {compose_dir}/")
    print(f"  outline.md ({len(outline_md)} chars)")
    for sid, p in assembled_paths.items():
        print(f"  {sid}_assembled.md")
    print(f"  manifest.md (run_id={run_id})")

    return {
        "status": "ok",
        "compose_dir": compose_dir,
        "outline_path": outline_path,
        "assembled_paths": assembled_paths,
        "slot_count": len(slot_blueprints),
        "skeleton_violations": skeleton_violations,
        "run_id": run_id,
    }


async def revise_outline(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    base_outline_path: str,
    annotated_outline_path: str | None = None,
    output_dir: str = "docs",
    model_routing: dict[str, str] | None = None,
    exp_dir: str = "data/slot_experiences",
) -> dict:
    """Revise outline based on teacher annotations and/or field changes.

    Dual-channel detection:
    1. Diff: YAML contract field changes between base and annotated
    2. Annotation: non-empty teacher annotations in annotated

    Pure YAML changes (no annotations) are applied deterministically.
    Annotation changes trigger LLM revision.

    Returns dict with revision metadata.
    """
    from core_new.slot_prompts import OUTLINE_REVISION_PROMPT
    from .outline_diff import (
        compute_outline_diff,
        compute_gitdiff,
        validate_changes,
        format_diff_summary,
    )

    revise_start = time.monotonic()
    print("=" * 60)
    print("Step: Revise — 修订大纲")
    print("=" * 60)

    # If no annotated path, use base (teacher edited in-place)
    if annotated_outline_path is None:
        annotated_outline_path = base_outline_path

    base_md = Path(base_outline_path).read_text(encoding="utf-8")
    annotated_md = Path(annotated_outline_path).read_text(encoding="utf-8")

    # Detect changes
    diff = compute_outline_diff(base_md, annotated_md)
    if not diff.has_any_changes:
        print("  未检测到变更，跳过修订")
        return {"status": "unchanged", "changed_slots": []}

    changed_ids = [sd.slot_id for sd in diff.changed_slots]
    print(f"  检测到变更题位: {', '.join(changed_ids)}")
    for sd in diff.changed_slots:
        if sd.field_changes:
            for fc in sd.field_changes:
                print(f"    [{sd.slot_id}] {fc.field}: {fc.old_value!r} → {fc.new_value!r}")
        if sd.annotation:
            print(f"    [{sd.slot_id}] 批注: {sd.annotation[:60]}...")

    # Validate changes
    warnings = validate_changes(diff.changed_slots, slot_templates)
    if warnings:
        print("  验证警告:")
        for w in warnings:
            print(f"    ⚠ {w}")

    # Decide revision path
    has_annotations = any(sd.annotation for sd in diff.changed_slots)
    slot_md = _build_slot_contracts_md(slot_templates, exp_dir)

    if has_annotations:
        # Need LLM to interpret annotations
        print("  路径: LLM 修订（含批注意见）")
        # Use git-style diff for better structure understanding
        gitdiff = compute_gitdiff(base_md, annotated_md)
        changes_summary = format_diff_summary(diff, warnings)
        # Combine gitdiff with summary for comprehensive context
        detected_changes_text = f"## Git-style Diff\n{gitdiff}\n\n## 结构化变更摘要\n{changes_summary}"
        prompt = OUTLINE_REVISION_PROMPT.format(
            original_outline=base_md,
            detected_changes=detected_changes_text,
            slot_contracts_md=slot_md,
        )

        is_hybrid = model_routing and str(model_routing.get("paper_composer", "")).lower() == "hybrid"
        if is_hybrid:
            revised_md = await _revise_hybrid(prompt)
        else:
            revised_md = await _revise_local(gateway, prompt)

        if not revised_md:
            print("  ERROR: LLM 修订失败")
            return {"status": "error", "step": "revise"}
    else:
        # Pure YAML changes — apply deterministically (just use annotated version)
        print("  路径: 确定性修订（纯字段变更）")
        revised_md = annotated_md

    # Parse revised outline
    blueprint = _parse_outline_to_blueprint(revised_md, slot_templates)
    if not blueprint.get("slots"):
        print("  ERROR: 修订后大纲解析失败")
        return {"status": "error", "step": "revise", "error": "parse failed"}

    # Skeleton check
    from core_new.skeleton_checker import check_blueprint_skeleton
    raw_slots = blueprint.get("slots", [])
    slots_as_dicts = [asdict(sb) if isinstance(sb, SlotBlueprint) else sb for sb in raw_slots]
    blueprint_for_check = {**blueprint, "slots": slots_as_dicts}
    skeleton_violations = check_blueprint_skeleton(blueprint_for_check)
    if skeleton_violations:
        print(f"  骨架检查: {len(skeleton_violations)} violations")
        for v in skeleton_violations:
            print(f"    [{v['slot_id']}] {v['rule']}: {v['detail']}")
    else:
        print("  骨架检查: pass")

    # Convert to SlotBlueprint instances
    slot_blueprints: list[SlotBlueprint] = []
    for sb in raw_slots:
        if isinstance(sb, SlotBlueprint):
            slot_blueprints.append(sb)
        else:
            slot_blueprints.append(SlotBlueprint(**{k: v for k, v in sb.items() if k in SlotBlueprint.__dataclass_fields__}))

    # Inherit question_type
    for sb in slot_blueprints:
        if not sb.question_type:
            tpl = slot_templates.get(sb.slot_id, {})
            if tpl.get("question_type"):
                sb.question_type = tpl["question_type"]

    # Re-assemble only affected slots
    compose_dir = os.path.join(output_dir, "compose")
    compose_path = Path(compose_dir)

    assembled_paths = {}
    for sb in slot_blueprints:
        if sb.slot_id not in changed_ids:
            continue
        sid = sb.slot_id
        mode = sb.examination_mode
        slot_md_path = os.path.join("data", "slots", f"{sid}_slot.md")
        exp_path = os.path.join(exp_dir, f"{sid}_experience.md")
        sb_dict = asdict(sb)
        doc = artifact_store.assemble_slot_experience_doc(sid, mode, slot_md_path, exp_path, outline_entry=sb_dict)
        print(f"  [{sid}] 重新组装: {mode} ({len(doc)} chars)")

        assembled_path = os.path.join(compose_dir, f"{sid}_assembled.md")
        with open(assembled_path, "w", encoding="utf-8") as f:
            f.write(doc)
        assembled_paths[sid] = assembled_path

    # Save revised outline
    outline_path = os.path.join(compose_dir, "outline.md")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(revised_md)

    # Regenerate sidecar artifacts after revision
    _write_sidecar_artifacts(compose_dir, revised_md)

    # Write revision report
    report_path = os.path.join(compose_dir, "revision_report.md")
    report = _build_revision_report(diff, warnings, has_annotations, time.monotonic() - revise_start)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  revision_report.md 已写入")

    print(f"\n大纲修订完成: {len(changed_ids)} 个题位已更新")
    return {
        "status": "ok",
        "compose_dir": compose_dir,
        "outline_path": outline_path,
        "assembled_paths": assembled_paths,
        "changed_slots": changed_ids,
        "skeleton_violations": skeleton_violations,
        "revision_report_path": report_path,
    }


async def _revise_hybrid(prompt: str) -> str:
    """Revise outline via hybrid (GPT) mode."""
    from core_new.webgpt_client import get_webgpt_client
    client = get_webgpt_client()
    if client is None:
        return ""
    revise_session = f"revise-{time.monotonic_ns()}"
    try:
        raw = await client.delegate(
            agent_name="hybrid_paper_reviser",
            slot_id=revise_session,
            system_prompt=_OUTLINE_SYSTEM_PROMPT,
            content=prompt,
        )
    except Exception as e:
        print(f"  ERROR: GPT revise failed: {e}")
        return ""
    finally:
        try:
            await client.cleanup(slot_id=revise_session)
        except Exception:
            pass
    print(f"  GPT 修订完成 ({len(raw)} chars)")
    return raw


async def _revise_local(gateway, prompt: str) -> str:
    """Revise outline via local Qwen."""
    messages = [
        {"role": "system", "content": _OUTLINE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    try:
        result = await gateway.generate_text(messages, max_tokens=8192)
        raw = result.content or ""
    except Exception as e:
        print(f"  ERROR: Local revise failed: {e}")
        return ""
    print(f"  Local Qwen 修订完成 ({len(raw)} chars)")
    return raw


def _build_revision_report(
    diff: "OutlineDiff",
    warnings: list[str],
    used_llm: bool,
    elapsed: float,
) -> str:
    """Build revision_report.md content."""
    lines = [
        "# 大纲修订报告",
        "",
        f"- 修订方式: {'LLM 修订' if used_llm else '确定性修订（纯字段变更）'}",
        f"- 修订题位数: {len(diff.changed_slots)}",
        f"- 未变题位: {len(diff.unchanged_slots)}",
        f"- 耗时: {elapsed:.1f}s",
        "",
        "## 已采纳变更",
        "",
    ]

    for sd in diff.changed_slots:
        lines.append(f"### {sd.slot_id}")
        if sd.field_changes:
            for fc in sd.field_changes:
                lines.append(f"- {fc.field}: {fc.old_value!r} → {fc.new_value!r}")
        if sd.annotation:
            lines.append(f"- 教师批注: {sd.annotation}")
        lines.append("")

    if warnings:
        lines.append("## 验证警告")
        lines.append("")
        for w in warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")

    lines.append("## 未采纳")
    lines.append("无。")
    lines.append("")

    return "\n".join(lines)


def load_paper_request(compose_dir: str) -> dict | None:
    """Load paper_request.yaml from compose directory if it exists.

    This is the intake layer output for paper (组卷) tasks.

    Args:
        compose_dir: Path to compose directory (e.g., "docs/compose")

    Returns:
        Parsed paper_request dict, or None if file doesn't exist (backward compat)
    """
    request_path = Path(compose_dir) / "paper_request.yaml"
    if not request_path.exists():
        return None

    try:
        with open(request_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        print(f"  [intake] Loaded paper_request.yaml (schema={data.get('schema_version', 'unknown')})")
        return data
    except Exception as e:
        print(f"  ERROR: Failed to load paper_request.yaml: {e}")
        return None


def map_paper_request_to_params(pr: dict) -> dict:
    """Map paper_request fields to run_compose() parameters.

    Args:
        pr: Parsed paper_request dict

    Returns:
        Dict with keys matching run_compose() parameter names:
        - user_requirements: Generated from knowledge_scope + difficulty
        - subject_files: Inferred from assessment.subjects
        - slot_templates_hints: Inferred from question_config.types
        - model_routing: Inferred from difficulty.target
    """
    # Build user_requirements from knowledge_scope and difficulty
    ks = pr.get("knowledge_scope", {})
    diff = pr.get("difficulty", {})
    pref = pr.get("teacher_preferences", {})

    req_parts = []

    # Subjects
    subjects = pr.get("assessment", {}).get("subjects", [])
    if subjects:
        req_parts.append(f"科目：{', '.join(subjects)}")

    # Knowledge scope
    if ks.get("primary_chapters"):
        req_parts.append(f"重点章节：{', '.join(ks['primary_chapters'])}")
    if ks.get("focus_points"):
        req_parts.append(f"重点关注：{', '.join(ks['focus_points'])}")
    if ks.get("excluded_points"):
        req_parts.append(f"排除考点：{', '.join(ks['excluded_points'])}")

    # Coverage strategy
    strategy = ks.get("coverage_strategy", "balanced")
    strategy_map = {
        "balanced": "均衡覆盖",
        "focus_heavy": "重点突出",
        "exam_weighted": "按考试权重",
    }
    req_parts.append(f"覆盖策略：{strategy_map.get(strategy, strategy)}")

    # Difficulty
    target = diff.get("target", "medium")
    target_map = {"easy": "容易", "medium": "中等", "hard": "较难"}
    req_parts.append(f"难度目标：{target_map.get(target, target)}")

    # Teacher preferences
    if pref.get("style_notes"):
        req_parts.append(f"教师备注：{pref['style_notes']}")

    # Require/avoid keywords
    if pref.get("require"):
        req_parts.append(f"必须包含：{', '.join(pref['require'])}")
    if pref.get("avoid"):
        req_parts.append(f"避免：{', '.join(pref['avoid'])}")

    user_requirements = "。".join(req_parts) + "。"

    # Infer subject files from assessment.subjects
    subject_to_file = {
        "计算机组成原理": "computer_organization.md",
        "数据结构": "data_structure.md",
        "操作系统": "operating_system_knowledge.md",
        "计算机网络": "computer_network.md",
    }
    subject_files = [subject_to_file.get(s, "") for s in subjects]
    subject_files = [f for f in subject_files if f]  # Filter empty

    # Infer slot templates hints from question_config
    qc = pr.get("question_config", {})
    slot_hints = []
    for qtype_spec in qc.get("types", []):
        qtype = qtype_spec.get("type")
        count_range = qtype_spec.get("count_range", [])
        slot_hints.append({
            "question_type": qtype,
            "count_range": count_range,
        })

    # Infer model routing from difficulty
    routing = {}
    if target == "hard":
        routing["paper_composer"] = "hybrid"

    return {
        "user_requirements": user_requirements,
        "subject_files": subject_files,
        "slot_templates_hints": slot_hints,
        "model_routing": routing,
    }
