"""GLM5.1 comprehensive question speed test.

Tests Q41 (数据结构综合题) and Q45 (操作系统综合题) with GLM5.1 model.
Records generation time and output quality.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_glm_comprehensive.md"

TEST_SLOTS = {
    "Q41": {"subject": "数据结构", "section": "综合应用题", "topic": "算法设计"},
    "Q45": {"subject": "操作系统", "section": "综合应用题", "topic": "文件/进程管理"},
}


def _read_file(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    if len(content) > 8000:
        content = content[:8000] + "\n\n... (截断)"
    return f"\n### {title}\n\n```\n{content}\n```\n"


async def test_glm_comprehensive():
    from compose.compose_runner import run_compose
    from compose.generate_runner import load_compose_artifacts, _generate_doc
    from core_new.provider_router import get_routed_gateway
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    report = [
        "# GLM5.1 综合题速度测试报告\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **模型**: GLM5.1 (本地)",
        f"- **测试题位**: {', '.join(TEST_SLOTS.keys())}",
        f"- **科目**: {', '.join(v['subject'] for v in TEST_SLOTS.values())}",
    ]

    # ── Load data ──
    tpl_path = "data/slot_templates_all.json"
    with open(tpl_path, encoding="utf-8") as f:
        all_templates = json.load(f).get("templates", {})

    slot_ids = list(TEST_SLOTS.keys())
    templates = {k: v for k, v in all_templates.items() if k in slot_ids}
    report.append(f"- **加载 slot 模板**: {list(templates.keys())}")

    exp_cards = {}
    exp_dir = "data/slot_experiences_all"
    for sid in slot_ids:
        path = os.path.join(exp_dir, f"{sid}_experience.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                exp_cards[sid] = f.read()
    report.append(f"- **加载经验卡**: {list(exp_cards.keys())}\n")

    user_req = "出一套408模拟卷（综合应用题部分），包含数据结构和操作系统"
    report.append(_section("输入: user_requirements", user_req))

    # ── Phase A: Compose ──
    report.append("\n## Phase A: 组卷大纲\n")
    gateway = get_routed_gateway("paper_composer")

    compose_start = time.monotonic()
    compose_result = await run_compose(
        gateway, templates, exp_cards, user_req,
        slot_ids=slot_ids,
        output_dir="docs",
        model_routing={"_default": "local"},
        exp_dir="data/slot_experiences_all",
    )
    compose_elapsed = time.monotonic() - compose_start

    if compose_result.get("status") != "ok":
        report.append(f"**组卷失败**: {compose_result}\n")
        _write(report)
        return

    report.append(f"- **组卷耗时**: {compose_elapsed:.1f}s")

    outline_md = _read_file(compose_result["outline_path"])
    report.append(_section("outline.md", outline_md[:4000]))

    # ── Phase B: Generate each comprehensive question ──
    compose_dir = compose_result["compose_dir"]
    run_id = compose_result.get("run_id", timestamp)
    artifacts = load_compose_artifacts(compose_dir)

    total_gen_time = 0

    for sid in slot_ids:
        info = TEST_SLOTS[sid]
        report.append(f"\n---\n\n## Phase B: {sid} ({info['subject']}综合题 — {info['topic']})\n")

        if sid not in artifacts:
            report.append(f"**错误**: {sid} assembled doc 未找到\n")
            continue

        assembled_md = artifacts[sid].assembled_md
        report.append(_section(f"{sid}_assembled.md (头部)", assembled_md[:2000]))

        slot_data = {"slot_id": sid}
        gen_start = time.monotonic()

        gen_result = await _generate_doc(
            gateway, slot_data, sid, "",
            output_dir="docs",
            model_routing={"_default": "glm5.1"},
            assembled_experience_doc=assembled_md,
            resume_from=1,
            run_id=run_id,
        )

        gen_elapsed = time.monotonic() - gen_start
        total_gen_time += gen_elapsed
        ws_path = Path("docs/workspace") / run_id / sid

        report.append(_section("question.md", _read_file(ws_path / "question.md")))
        report.append(_section("review.md", _read_file(ws_path / "review.md")))
        report.append(_section("solution.md", _read_file(ws_path / "solution.md")))

        solve_py = _read_file(ws_path / "solve.py")
        if solve_py != "(文件不存在)":
            report.append(_section("solve.py ✅", solve_py))
            report.append(_section("solve_output.txt", _read_file(ws_path / "solve_output.txt")))

        report.append(_section("final_review.md", _read_file(ws_path / "final_review.md")))
        report.append(_section("final.md", _read_file(ws_path / "final.md")))

        report.append(f"\n**{sid} 生成耗时**: {gen_elapsed:.1f}s | ok={gen_result.get('ok')} | review={gen_result.get('review_status', '?')}")

    # ── Summary ──
    report.append("\n---\n\n## 速度对比\n")
    report.append(f"- **Compose 耗时**: {compose_elapsed:.1f}s")
    report.append(f"- **总生成耗时**: {total_gen_time:.1f}s")
    report.append(f"- **总耗时**: {compose_elapsed + total_gen_time:.1f}s")
    report.append(f"- **模型**: GLM5.1")
    report.append(f"- **题型**: 综合应用题 (数据结构 + 操作系统)")

    _write(report)
    print(f"\n报告已写入: {OUTPUT_REPORT}")


def _write(parts: list[str]):
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(test_glm_comprehensive())
