"""Test the FULL compose→generate pipeline.

Phase A: Compose — Generate paper outline → parse blueprints → assemble per-slot docs
Phase B: Generate — For Q12, run 5-layer pipeline using assembled doc

Documents all inputs/outputs at every stage.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_compose_full.md"
COMPOSE_DIR = Path(__file__).resolve().parent.parent / "docs" / "compose_test"


def _read_file(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    if len(content) > 6000:
        content = content[:6000] + "\n\n... (截断)"
    return f"\n### {title}\n\n```\n{content}\n```\n"


async def test_full_compose():
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    report = [
        "# 完整 Compose→Generate 流水线测试报告\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **模型**: Qwen3.6-27B-FP8 (本地vLLM)",
        f"- **测试范围**: 组卷大纲生成 → per-slot assembly → Q12 出题",
        f"- **工作区**: docs/compose_test/\n",
    ]

    # ── Phase 0: Load inputs ──────────────────────────────────
    report.append("## Phase 0: 输入数据\n")

    tpl_path = "data/config/slot_templates.json"
    if not os.path.exists(tpl_path):
        report.append(f"**错误**: {tpl_path} 不存在\n")
        _write(report)
        return

    with open(tpl_path, encoding="utf-8") as f:
        tpl_data = json.load(f)
    templates = tpl_data.get("templates", {})

    # Filter to 4 slots for faster testing
    test_slots = ["Q12", "Q14", "Q22", "Q44"]
    templates = {k: v for k, v in templates.items() if k in test_slots}

    report.append(_section("输入: slot_templates.json (filtered)", json.dumps(templates, ensure_ascii=False, indent=2)[:3000]))

    exp_cards = {}
    exp_dir = "data/slot_experiences"
    if os.path.isdir(exp_dir):
        for fname in os.listdir(exp_dir):
            if fname.endswith("_experience.md"):
                slot_id = fname.replace("_experience.md", "")
                if slot_id in templates:
                    with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                        exp_cards[slot_id] = f.read()

    report.append(f"- 加载 {len(templates)} 个 slot 模板")
    report.append(f"- 加载 {len(exp_cards)} 个经验卡\n")

    user_requirements = "出一套标准难度的408模拟卷（选择题部分），难度分布均匀，覆盖主要知识点"
    report.append(_section("输入: user_requirements", user_requirements))

    # ── Phase A: Compose ───────────────────────────────────────
    report.append("\n## Phase A: 组卷大纲生成\n")

    from core_new.provider_router import get_routed_gateway
    from compose.compose_runner import run_compose

    gateway = get_routed_gateway("paper_composer")
    compose_start = time.monotonic()

    result = await run_compose(
        gateway, templates, exp_cards, user_requirements,
        slot_ids=test_slots,
        output_dir="docs",
        model_routing={"_default": "local"},
    )

    compose_elapsed = time.monotonic() - compose_start

    if result.get("status") != "ok":
        report.append(f"**组卷失败**: {result}\n")
        _write(report)
        return

    report.append(f"- **组卷耗时**: {compose_elapsed:.1f}s")
    report.append(f"- **生成题位数**: {result['slot_count']}")
    report.append(f"- **骨架违规**: {result.get('skeleton_violations', [])}\n")

    # Read and document the outline
    outline_md = _read_file(result["outline_path"])
    report.append(_section("输出: outline.md (组卷大纲)", outline_md))

    # Read and document each assembled doc (short summary)
    report.append("\n### 各题位 assembled.md 摘要\n")
    for sid, path in result["assembled_paths"].items():
        content = _read_file(path)
        # Extract just the header section
        lines = content.split("\n")
        header_lines = []
        for line in lines:
            if line.startswith("## 往年真题经验") or line.startswith("---"):
                break
            header_lines.append(line)
        header = "\n".join(header_lines[:30])
        report.append(_section(f"{sid}_assembled.md (头部)", header))

    # Read manifest
    manifest_path = os.path.join(result["compose_dir"], "manifest.md")
    report.append(_section("输出: manifest.md", _read_file(manifest_path)))

    # ── Phase B: Generate Q12 ──────────────────────────────────
    report.append("\n## Phase B: 出题 (Q12)\n")

    from compose.generate_runner import load_compose_artifacts, _generate_doc
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    compose_dir = result["compose_dir"]
    run_id = result.get("run_id", timestamp)
    artifacts = load_compose_artifacts(compose_dir, slot_filter=["Q12"])

    if "Q12" not in artifacts:
        report.append("**错误**: Q12 assembled doc 未在 compose 产物中找到\n")
        _write(report)
        return

    assembled_md = artifacts["Q12"].assembled_md

    slot_data = {"slot_id": "Q12"}
    gen_start = time.monotonic()

    gen_result = await _generate_doc(
        gateway, slot_data, "Q12", "",
        output_dir="docs",
        model_routing={"_default": "local"},
        assembled_experience_doc=assembled_md,
        resume_from=1,
        run_id=run_id,
    )

    gen_elapsed = time.monotonic() - gen_start

    ws_path = Path("docs/workspace") / run_id / "Q12"

    report.append(_section("Layer 2: question.md", _read_file(ws_path / "question.md")))
    report.append(_section("Layer 3: review.md", _read_file(ws_path / "review.md")))
    report.append(_section("Layer 4: solution.md", _read_file(ws_path / "solution.md")))
    report.append(_section("Layer 5: final_review.md", _read_file(ws_path / "final_review.md")))
    report.append(_section("Final: final.md", _read_file(ws_path / "final.md")))

    report.append("\n## 总结果\n")
    report.append(f"- **Compose 耗时**: {compose_elapsed:.1f}s")
    report.append(f"- **Generate 耗时**: {gen_elapsed:.1f}s")
    report.append(f"- **总耗时**: {compose_elapsed + gen_elapsed:.1f}s")
    report.append(f"- **pipeline_type**: {gen_result.get('pipeline_type')}")
    report.append(f"- **ok**: {gen_result.get('ok')}")
    report.append(f"- **review_status**: {gen_result.get('review_status', '?')}")

    _write(report)
    print(f"\n报告已写入: {OUTPUT_REPORT}")


def _write(parts: list[str]):
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(test_full_compose())
