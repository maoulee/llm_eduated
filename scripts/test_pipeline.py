"""Test the new 5-layer pipeline with full I/O documentation.

Runs Q12 through the pipeline using local Qwen model and captures
all inputs/outputs at each layer into a comprehensive report.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_5layer.md"


def _read_file(path: str | Path) -> str:
    """Read file content, return empty string if not found."""
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    """Format a markdown section."""
    if len(content) > 8000:
        content = content[:8000] + "\n\n... (截断，全文见工作区文件)"
    return f"\n### {title}\n\n```\n{content}\n```\n"


async def test_local_qwen():
    """Test with local Qwen model on Q12 slot."""
    from compose.generate_runner import load_compose_artifacts
    from core_new.doc_pipeline import DocPipeline
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"test-{timestamp}"
    output_dir = "docs"
    workspace = os.path.join(output_dir, "workspace", run_id)

    report_parts = [
        f"# 5层流水线测试报告\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **模型**: Qwen3.6-27B-FP8 (本地vLLM)",
        f"- **测试题位**: Q12",
        f"- **工作区**: {workspace}\n",
    ]

    # ── Step 0: Load input data ──────────────────────────────
    report_parts.append("## Layer 0: 输入数据\n")

    # Load assembled doc
    compose_dir = "docs/compose"
    artifacts = load_compose_artifacts(compose_dir, slot_filter=["Q12"])

    if "Q12" not in artifacts:
        report_parts.append("**错误**: Q12 assembled doc 未找到\n")
        _write_report(report_parts)
        return

    assembled_md = artifacts["Q12"].assembled_md
    report_parts.append(_section("输入: assembled.md (出题契约)", assembled_md))

    # Slot data
    slot_data = {"slot_id": "Q12"}
    report_parts.append(_section("输入: slot_data", json.dumps(slot_data, ensure_ascii=False, indent=2)))

    report_parts.append(_section("输入: K_RADAR_DEFINITIONS", K_RADAR_DEFINITIONS[:3000]))

    # ── Run pipeline with layer-by-layer capture ─────────────
    report_parts.append("\n## 执行流水线\n")
    report_parts.append("Layer 1 跳过（使用 assembled doc 作为蓝图替代）\n")

    # Create pipeline with local routing
    dp = DocPipeline(workspace=workspace, model_routing={"_default": "local"})
    result = await dp.run(
        slot_id="Q12",
        slot_data=slot_data,
        experience_card="",
        k_definitions=K_RADAR_DEFINITIONS,
        assembled_experience_doc=assembled_md,
        start_layer=1,
    )

    ws_path = Path(workspace) / "Q12"

    # ── Layer 2: Question ────────────────────────────────────
    report_parts.append("## Layer 2: Question Agent (出题)\n")
    report_parts.append(_section("输出: blueprint.md (规划文件)", _read_file(ws_path / "blueprint.md")))
    report_parts.append(_section("输出: question.md (题目)", _read_file(ws_path / "question.md")))

    # ── Layer 3: Review ──────────────────────────────────────
    report_parts.append("## Layer 3: Review Agent (题目审核)\n")
    report_parts.append(_section("输出: review.md (审核结果)", _read_file(ws_path / "review.md")))

    # ── Layer 4: Solve ───────────────────────────────────────
    report_parts.append("## Layer 4: Solve Agent (独立求解)\n")
    report_parts.append(_section("输出: solution.md (求解过程)", _read_file(ws_path / "solution.md")))
    solve_py = _read_file(ws_path / "solve.py")
    if solve_py != "(文件不存在)":
        report_parts.append(_section("输出: solve.py (求解代码)", solve_py))
        report_parts.append(_section("输出: solve_output.txt (代码执行结果)", _read_file(ws_path / "solve_output.txt")))
    else:
        report_parts.append("\nsolve.py 不存在（概念题，无需代码）\n")

    # ── Layer 5: Final Review ────────────────────────────────
    report_parts.append("## Layer 5: Final Review Agent (终审)\n")
    report_parts.append(_section("输出: final_review.md (终审结果)", _read_file(ws_path / "final_review.md")))

    # ── Final output ─────────────────────────────────────────
    report_parts.append("## Final: 最终输出\n")
    report_parts.append(_section("输出: final.md", _read_file(ws_path / "final.md")))

    # ── Pipeline result summary ──────────────────────────────
    report_parts.append("## 流水线结果摘要\n")
    report_parts.append(f"- **ok**: {result.ok}")
    report_parts.append(f"- **pipeline_type**: {result.pipeline_type}")
    report_parts.append(f"- **total_time_s**: {result.total_time_s}")
    report_parts.append(f"- **analysis_iterations**: {result.analysis_iterations}")
    report_parts.append(f"- **review_status**: {result.review_status}")
    report_parts.append(f"- **code_exec_ok**: {result.code_exec_ok}")
    report_parts.append(f"- **code_skipped**: {result.code_skipped}")
    report_parts.append(f"- **error**: {result.error or '(无)'}")
    report_parts.append(f"- **files**: ")
    for k, v in result.files.items():
        exists = "✓" if v and Path(v).exists() else "✗"
        report_parts.append(f"  - {k}: {exists} {v}")

    _write_report(report_parts)
    print(f"\n报告已写入: {OUTPUT_REPORT}")


def _write_report(parts: list[str]):
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(test_local_qwen())
