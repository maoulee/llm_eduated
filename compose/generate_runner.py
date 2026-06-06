"""Generate runner — load compose artifacts and generate questions.

Handles loading assembled docs from disk, running DocPipeline per slot,
and formatting/exporting results.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

from core_new.doc_pipeline.contracts import ComposeArtifact


_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_OPTION_RE = re.compile(r"^\s*(?:[-*]\s*)?([A-D])\s*[.、:：)]\s*(.+?)\s*$")
_SUBQ_RE = re.compile(r"^\s*(?:[-*]\s*)?(\(?\d+\)|\d+[.、])\s*(.+?)\s*$")


def load_compose_artifacts(compose_dir: str, slot_filter: list[str] | None = None) -> dict[str, ComposeArtifact]:
    """Load compose artifacts from disk.

    Returns {slot_id: ComposeArtifact}.

    If manifest.md exists, uses slot IDs from the manifest table (backward compatible).
    Otherwise falls back to glob for *_assembled.md files.
    """
    import glob as glob_mod
    manifest_path = Path(compose_dir) / "manifest.md"

    # Try to read slot IDs from manifest
    manifest_slot_ids = None
    if manifest_path.exists():
        manifest_text = manifest_path.read_text(encoding="utf-8")
        slot_id_pattern = r"^\| (\w+) \|"
        manifest_slot_ids = []
        for line in manifest_text.split("\n"):
            m = re.match(slot_id_pattern, line.strip())
            if m:
                slot_id = m.group(1)
                if slot_id != "Slot":
                    manifest_slot_ids.append(slot_id)
        if manifest_slot_ids:
            print(f"  Using manifest.md with {len(manifest_slot_ids)} slots")

    # Determine which slots to load
    if manifest_slot_ids:
        target_slots = manifest_slot_ids if not slot_filter else [s for s in manifest_slot_ids if s in slot_filter]
    else:
        pattern = os.path.join(compose_dir, "*_assembled.md")
        files = sorted(glob_mod.glob(pattern))
        target_slots = []
        for fpath in files:
            fname = os.path.basename(fpath)
            slot_id = fname.replace("_assembled.md", "")
            if not slot_filter or slot_id in slot_filter:
                target_slots.append(slot_id)
        if not files:
            print(f"ERROR: No assembled docs found in {compose_dir}")
            return {}

    # Load the assembled docs for target slots
    slots: dict[str, ComposeArtifact] = {}
    for slot_id in target_slots:
        assembled_path = os.path.join(compose_dir, f"{slot_id}_assembled.md")
        if not os.path.exists(assembled_path):
            print(f"  WARNING: {assembled_path} not found (skipping)")
            continue

        with open(assembled_path, encoding="utf-8") as f:
            assembled_md = f.read()

        slots[slot_id] = ComposeArtifact(
            slot_id=slot_id,
            assembled_md=assembled_md,
            assembled_path=assembled_path,
        )

    return slots


async def run_generate(
    gateway,
    compose_dir: str,
    output_dir: str = "docs",
    model_routing: dict[str, str] | None = None,
    slot_filter: list[str] | None = None,
    resume_from: int = 1,
    run_id: str | None = None,
) -> dict:
    """Phase B: Load compose artifacts → generate questions → format.

    Args:
        run_id: Run identifier for workspace isolation. If not provided,
                reads from {compose_dir}/manifest.md.
    """
    total_start = time.monotonic()

    # Resolve run_id from manifest if not provided
    if not run_id:
        run_id = _read_run_id_from_manifest(compose_dir)

    artifacts = load_compose_artifacts(compose_dir, slot_filter)
    if not artifacts:
        return {"status": "error", "error": "no artifacts loaded"}

    # Load experience cards for style reference
    exp_cards = {}
    exp_dir = "data/slot_experiences"
    if os.path.isdir(exp_dir):
        for fname in os.listdir(exp_dir):
            if fname.endswith("_experience.md"):
                sid = fname.replace("_experience.md", "")
                if sid in artifacts:
                    with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                        exp_cards[sid] = f.read()

    # Build minimal slot_blueprints and assembled_docs for generate_questions
    slot_blueprints = []
    assembled_docs = {}
    for sid, art in artifacts.items():
        slot_blueprints.append({"slot_id": sid})
        assembled_docs[sid] = art.assembled_md

    # Generate questions
    final_questions = await _generate_slots(
        gateway, slot_blueprints, exp_cards, assembled_docs,
        output_dir=output_dir, model_routing=model_routing,
        resume_from=resume_from, run_id=run_id,
    )

    total_time = time.monotonic() - total_start

    # Save results
    output = {
        "final_questions": final_questions,
        "total_time_s": round(total_time, 1),
        "compose_dir": compose_dir,
        "slots_generated": list(artifacts.keys()),
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "slot_composition_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存到: {output_path}")

    # Format & Export
    await _format_and_export(gateway, final_questions, output_dir)

    return output


async def _generate_slots(
    gateway, slot_blueprints, experience_cards, assembled_docs, *,
    output_dir="docs", model_routing=None, resume_from=1, run_id=None,
) -> list:
    """Generate questions for multiple slots (with concurrency control)."""
    print("\n" + "=" * 60)
    print(f"出题 ({len(slot_blueprints)}题，并行，doc pipeline)")
    if resume_from > 1:
        print(f"  从 Layer {resume_from} 继续")
    if run_id:
        print(f"  run_id: {run_id}")
    print("=" * 60)

    slot_concurrency = int(os.getenv("PIPELINE_SLOT_CONCURRENCY", "2"))
    slot_semaphore = asyncio.Semaphore(max(1, slot_concurrency))
    print(f"  题位并发上限: {max(1, slot_concurrency)}")

    async def _generate_one(sb):
        async with slot_semaphore:
            slot_id = sb.get("slot_id", "Q12")
            exp_card = experience_cards.get(slot_id, "")
            assembled_doc = assembled_docs.get(slot_id, "")
            return await _generate_doc(
                gateway, sb, slot_id, exp_card,
                output_dir=output_dir, model_routing=model_routing,
                assembled_experience_doc=assembled_doc,
                resume_from=resume_from, run_id=run_id,
            )

    tasks = [_generate_one(sb) for sb in slot_blueprints]
    questions = await asyncio.gather(*tasks)
    return list(questions)


async def _generate_doc(gateway, sb, slot_id, exp_card, *, output_dir="docs",
                        model_routing=None, assembled_experience_doc=None, resume_from=1,
                        run_id=None):
    """Generate a question using the document-based pipeline."""
    from core_new.doc_pipeline import DocPipeline

    try:
        from core_new.slot_prompts import K_RADAR_DEFINITIONS
    except ImportError:
        K_RADAR_DEFINITIONS = ""

    if resume_from > 1:
        print(f"  [{slot_id}] DocPipeline (resume from layer {resume_from})...")
    elif assembled_experience_doc:
        print(f"  [{slot_id}] DocPipeline (3-layer, assembled doc)...")
    else:
        print(f"  [{slot_id}] DocPipeline (5-layer)...")
    t0 = time.monotonic()

    try:
        workspace_parts = [output_dir, "workspace"]
        if run_id:
            workspace_parts.append(run_id)
        doc_workspace = os.path.join(*workspace_parts)
        dp = DocPipeline(workspace=doc_workspace, model_routing=model_routing)
        result = await dp.run(
            slot_id=slot_id,
            slot_data=sb,
            experience_card=exp_card,
            k_definitions=K_RADAR_DEFINITIONS if "K_RADAR_DEFINITIONS" in dir() else "",
            assembled_experience_doc=assembled_experience_doc or "",
            start_layer=resume_from,
        )
        elapsed = time.monotonic() - t0

        q_data = {
            "slot_id": slot_id,
            "pipeline_type": result.pipeline_type,
            "generation_time_s": result.total_time_s,
            "ok": result.ok,
            "_blueprint": sb,
            "_experience_card": exp_card,
        }

        if result.final_content:
            q_data["final_md"] = result.final_content
            q_data.update(_extract_structured_fields_from_final_md(result.final_content, slot_id))

        print(f"  [{slot_id}] DocPipeline done ({elapsed:.1f}s): "
              f"review={result.review_status} iters={result.analysis_iterations} ok={result.ok}")

        return q_data

    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"  [{slot_id}] DocPipeline failed ({elapsed:.1f}s): {e}")
        return {"slot_id": slot_id, "status": "error", "error": str(e), "pipeline_type": "doc_5layer"}


async def _format_and_export(gateway, final_questions, output_dir, blueprint=None):
    """Format questions into exam paper markdown."""
    try:
        from core_new.agents.paper_formatter import PaperFormatterAgent
        formatter = PaperFormatterAgent(gateway=gateway)
        md = await formatter.format(final_questions, blueprint or {}, {})
        md_path = Path(output_dir) / "exam_paper_clean.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md, encoding="utf-8")
        print(f"排版完成: {md_path}")
    except Exception as exc:
        print(f"排版步骤跳过: {exc}")


def _read_run_id_from_manifest(compose_dir: str) -> str | None:
    """Read run_id from compose manifest.md."""
    manifest_path = Path(compose_dir) / "manifest.md"
    if not manifest_path.exists():
        return None
    text = manifest_path.read_text(encoding="utf-8")
    m = re.search(r"^- run_id:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _extract_structured_fields_from_final_md(final_md: str, slot_id: str) -> dict:
    """Parse DocPipeline final.md into the legacy structured dict used by formatter."""
    if not final_md:
        return {}

    stem = _extract_h2_section(final_md, "题目")
    options_text = _extract_h2_section(final_md, "选项")
    subq_text = _extract_h2_section(final_md, "子问题")
    process_text = _extract_h2_section(final_md, "求解过程")
    code_output = _extract_h2_section(final_md, "代码验证输出")
    answer_text = _extract_h2_section(final_md, "答案")
    design_notes = _extract_h2_section(final_md, "设计说明")

    slot_num = int(re.sub(r"[^\d]", "", slot_id) or "99")
    is_comp = slot_num >= 43 or (subq_text and not options_text)
    data: dict[str, object] = {
        "stem": stem.strip(),
        "question_type": "comprehensive" if is_comp else "single_choice",
    }

    options = _parse_option_fields(options_text)
    if options:
        data.update(options)

    if is_comp:
        data["sub_questions"] = _parse_sub_questions(subq_text)
        if answer_text:
            data["answer"] = answer_text.strip()
    else:
        correct_answer = _parse_correct_answer(answer_text)
        if correct_answer:
            data["correct_answer"] = correct_answer

    explanation_parts = [part.strip() for part in (process_text, code_output) if part and part.strip()]
    if explanation_parts:
        data["explanation"] = "\n\n".join(explanation_parts)
    elif answer_text:
        data["explanation"] = answer_text.strip()

    if design_notes:
        data["parameter_notes"] = design_notes.strip()

    return data


def _extract_h2_section(text: str, heading: str) -> str:
    """Extract content under a ## heading, preserving ### subsections."""
    matches = list(_H2_RE.finditer(text or ""))
    for i, match in enumerate(matches):
        if match.group(1).strip() == heading:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[start:end].strip()
    return ""


def _parse_option_fields(options_text: str) -> dict[str, str]:
    options: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key:
            options[f"option_{current_key}"] = " ".join(line.strip() for line in current_lines if line.strip()).strip()
        current_key = ""
        current_lines = []

    for line in (options_text or "").splitlines():
        match = _OPTION_RE.match(line)
        if match:
            flush()
            current_key = match.group(1).upper()
            current_lines = [match.group(2).strip()]
        elif current_key and line.strip():
            current_lines.append(line.strip())
    flush()
    return options


def _parse_sub_questions(subq_text: str) -> list[str]:
    text = (subq_text or "").strip()
    if not text:
        return []

    heading_matches = list(re.finditer(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE))
    if heading_matches:
        items: list[str] = []
        for i, match in enumerate(heading_matches):
            start = match.end()
            end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(text)
            body = text[start:end].strip()
            heading = match.group(1).strip()
            items.append((heading + ("\n" + body if body else "")).strip())
        return items

    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _SUBQ_RE.match(stripped)
        if match:
            items.append(f"{match.group(1)} {match.group(2).strip()}")
        elif items:
            items[-1] += " " + stripped
        else:
            items.append(stripped)
    return items


def _parse_correct_answer(answer_text: str) -> str:
    text = (answer_text or "").strip()
    if not text:
        return ""
    match = re.search(r"(?:正确答案|答案)\s*[：:]\s*([A-D])\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r"\b([A-D])\b", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""
