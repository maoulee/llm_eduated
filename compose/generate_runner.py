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
