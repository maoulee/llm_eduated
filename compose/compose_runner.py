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

from core_new.doc_pipeline.contracts import SlotBlueprint

from . import artifact_store

_OUTLINE_SYSTEM_PROMPT = (
    "# 408考研组卷专家\n\n"
    "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲是给下游出题智能体的'命题指令'。\n\n"
    "## 输出格式\n"
    "Markdown格式，包含：\n"
    "- `# 试卷大纲` 标题\n"
    "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
    "- 每个题位一个 `## Qxx` 段落，包含：target_subject, target_family, primary_target_name, "
    "difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
    "## 核心约束\n"
    "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
    "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
    "- 不要输出选项风格、干扰策略等设计级决策\n"
    "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
    "直接输出 Markdown 内容，不要用代码块包裹。"
)


def _build_slot_contracts_md(templates: dict) -> str:
    """Build concatenated slot contracts markdown for compose prompts."""
    from core_new.slot_contract import build_slot_contract

    exp_dir = Path("data/slot_experiences")
    experience_cards = {}
    for path in sorted(exp_dir.glob("*_experience.md")):
        sid = path.stem.replace("_experience", "")
        experience_cards[sid] = path.read_text(encoding="utf-8")

    slot_dir = Path("data/slots")
    slot_contents = {}
    for path in sorted(slot_dir.glob("*_slot.md")):
        sid = path.stem.replace("_slot", "")
        slot_contents[sid] = path.read_text(encoding="utf-8")

    contracts = {}
    for sid, tpl in templates.items():
        try:
            contract = build_slot_contract(
                sid, tpl,
                experience_cards.get(sid, ""),
                slot_contents.get(sid, ""),
            )
            if contract:
                contracts[sid] = contract
        except Exception:
            pass

    return "\n\n---\n\n".join(contracts[sid] for sid in sorted(contracts.keys()))


async def _compose_hybrid(templates, user_requirements) -> tuple[str, dict]:
    """Hybrid composition: GPT generates outline via WebGPT.

    Returns (outline_md, blueprint_dict).
    """
    from core_new.webgpt_client import get_webgpt_client
    from core_new.slot_prompts import PAPER_OUTLINE_PROMPT

    client = get_webgpt_client()
    if not client:
        print("  ERROR: WebGPT not configured for hybrid composition")
        return "", {}

    slot_md = _build_slot_contracts_md(templates)
    prompt = PAPER_OUTLINE_PROMPT.format(
        user_requirements=user_requirements,
        slot_contracts_md=slot_md,
        total_slots=len(templates),
    )

    t0 = time.monotonic()
    try:
        raw = await client.delegate(
            agent_name="hybrid_paper_composer",
            slot_id="compose",
            system_prompt=_OUTLINE_SYSTEM_PROMPT,
            content=prompt,
        )
    except Exception as e:
        print(f"  ERROR: GPT call failed: {e}")
        return "", {}

    elapsed = time.monotonic() - t0
    print(f"  GPT responded in {elapsed:.1f}s ({len(raw)} chars)")

    blueprint = _parse_outline_to_blueprint(raw, templates)
    _print_blueprint_summary(blueprint)
    return raw, blueprint


async def _compose_local(gateway, templates, user_requirements) -> tuple[str, dict]:
    """Local composition: Qwen generates outline via gateway.

    Returns (outline_md, blueprint_dict).
    """
    from core_new.slot_prompts import PAPER_OUTLINE_PROMPT

    slot_md = _build_slot_contracts_md(templates)
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
        result = await gateway.generate_text(messages, max_tokens=8192)
        raw = result.content or ""
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


def _parse_outline_to_blueprint(outline_md: str, templates: dict) -> dict:
    """Parse GPT/Qwen outline MD into blueprint dict format."""
    slots = []
    pattern = r"## (Q\d+)"
    parts = re.split(pattern, outline_md)

    overall_difficulty = 3
    composition_rationale = ""

    header = parts[0] if parts else ""
    dm = re.search(r"difficulty_target[*:\s]*(\d)", header)
    if dm:
        overall_difficulty = int(dm.group(1))
    cm = re.search(r"composition_rationale[*:\s]*(.+?)(?:\n|$)", header)
    if cm:
        composition_rationale = cm.group(1).strip()

    for i in range(1, len(parts), 2):
        slot_id = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""

        def _extract(field: str, default: str = "") -> str:
            m = re.search(rf"\* *{field}[*:\s]*(.+?)(?:\n|$)", content)
            return m.group(1).strip() if m else default

        difficulty = _extract("difficulty_level", "3")
        try:
            difficulty = int(difficulty)
        except ValueError:
            difficulty = 3

        tpl = templates.get(slot_id, {})
        target_subject = _extract("target_subject") or tpl.get("subject", "")
        question_type = tpl.get("question_type", "single_choice")

        slot_blueprint = SlotBlueprint(
            slot_id=slot_id,
            target_subject=target_subject,
            target_family=_extract("target_family"),
            primary_target_name=_extract("primary_target_name"),
            target_difficulty=difficulty,
            examination_mode=_extract("examination_mode"),
            k_target=_extract("k_target"),
            difficulty_rationale=_extract("difficulty_rationale"),
            question_type=question_type,
        )

        slots.append(slot_blueprint)

    return {
        "paper_type": "408模拟卷",
        "total_questions": len(slots),
        "difficulty_target": overall_difficulty,
        "composition_rationale": composition_rationale,
        "slots": slots,
    }


async def compose_paper(gateway, templates, user_requirements, model_routing=None) -> tuple[str, dict]:
    """Step 1: Generate paper outline/blueprint.

    Routes to hybrid (GPT via WebGPT) or local (Qwen via gateway).
    Returns (outline_md, blueprint_dict).
    """
    print("=" * 60)
    is_hybrid = model_routing and str(model_routing.get("paper_composer", "")).lower() == "hybrid"

    if is_hybrid:
        print("Step 1: Compose — 规划试卷蓝图 (hybrid: GPT→Qwen)")
        print("=" * 60)
        return await _compose_hybrid(templates, user_requirements)
    else:
        print("Step 1: Compose — 规划试卷蓝图 (local: Qwen)")
        print("=" * 60)
        return await _compose_local(gateway, templates, user_requirements)


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


async def run_compose(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list | None = None,
    output_dir: str = "docs",
    model_routing: dict[str, str] | None = None,
) -> dict:
    """Phase A: Compose outline + assemble experience docs → save to compose/.

    Returns dict with compose metadata (outline path, assembled paths, slot_count).
    """
    compose_start = time.monotonic()

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

    # Step 1: Compose
    outline_md, blueprint = await compose_paper(gateway, templates, user_requirements, model_routing=model_routing)
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
        exp_path = os.path.join("data", "slot_experiences", f"{sid}_experience.md")
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
