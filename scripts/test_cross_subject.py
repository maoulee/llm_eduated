"""Cross-subject test: 数据结构 Q1, 计算机网络 Q33, 操作系统 Q23.

Tests the 5-layer pipeline with subjects OTHER than 计算机组成原理.
Uses locally extracted slot templates and experience cards.
Models: Qwen (local) for all layers.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_cross_subject.md"

# Slots to test — one from each non-CO subject
TEST_SLOTS = {
    "Q1": {"subject": "数据结构", "topic": "缓冲区/队列"},
    "Q33": {"subject": "计算机网络", "topic": "网络体系结构/协议"},
    "Q23": {"subject": "操作系统", "topic": "进程/文件管理"},
}


def _read_file(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    if len(content) > 6000:
        content = content[:6000] + "\n\n... (截断)"
    return f"\n### {title}\n\n```\n{content}\n```\n"


async def test_cross_subject():
    from compose.compose_runner import run_compose
    from compose.generate_runner import load_compose_artifacts, _generate_doc
    from core_new.provider_router import get_routed_gateway
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    report = [
        "# 跨科目出题测试报告\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **模型**: Qwen3.6-27B-FP8 (本地vLLM)",
        f"- **测试题位**: {', '.join(TEST_SLOTS.keys())}",
        f"- **科目**: {', '.join(v['subject'] for v in TEST_SLOTS.values())}",
    ]

    # ── Load data ──
    tpl_path = "data/slot_templates_all.json"
    with open(tpl_path, encoding="utf-8") as f:
        all_templates = json.load(f).get("templates", {})

    # Filter to test slots
    slot_ids = list(TEST_SLOTS.keys())
    templates = {k: v for k, v in all_templates.items() if k in slot_ids}
    report.append(f"- **加载 slot 模板**: {list(templates.keys())}")

    # Experience cards
    exp_cards = {}
    exp_dir = "data/slot_experiences_all"
    for sid in slot_ids:
        path = os.path.join(exp_dir, f"{sid}_experience.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                exp_cards[sid] = f.read()
    report.append(f"- **加载经验卡**: {list(exp_cards.keys())}\n")

    user_req = "出一套408模拟卷（选择题部分），覆盖数据结构、计算机网络、操作系统"
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
    report.append(f"- **骨架违规**: {compose_result.get('skeleton_violations', [])}")

    outline_md = _read_file(compose_result["outline_path"])
    report.append(_section("outline.md", outline_md[:4000]))

    # ── Phase B: Generate each slot ──
    compose_dir = compose_result["compose_dir"]
    run_id = compose_result.get("run_id", timestamp)
    artifacts = load_compose_artifacts(compose_dir)

    for sid in slot_ids:
        info = TEST_SLOTS[sid]
        report.append(f"\n---\n\n## Phase B: {sid} ({info['subject']} — {info['topic']})\n")

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
            model_routing={"_default": "local"},
            assembled_experience_doc=assembled_md,
            resume_from=1,
            run_id=run_id,
        )

        gen_elapsed = time.monotonic() - gen_start
        ws_path = Path("docs/workspace") / run_id / sid

        report.append(_section("question.md", _read_file(ws_path / "question.md")))
        report.append(_section("review.md", _read_file(ws_path / "review.md")))
        report.append(_section("solution.md", _read_file(ws_path / "solution.md")))

        # Check solve.py (key fix verification)
        solve_py = _read_file(ws_path / "solve.py")
        if solve_py != "(文件不存在)":
            report.append(_section("solve.py ✅", solve_py))
            report.append(_section("solve_output.txt", _read_file(ws_path / "solve_output.txt")))
        else:
            # Check if this is truly a concept question
            question_md = _read_file(ws_path / "question.md")
            has_numbers = any(c.isdigit() for c in question_md[:500])
            if has_numbers:
                report.append(f"\n**⚠️ solve.py 缺失！题目包含数值但未生成代码**\n")
            else:
                report.append(f"\nsolve.py 不存在（纯概念题，符合预期）\n")

        report.append(_section("final_review.md", _read_file(ws_path / "final_review.md")))
        report.append(_section("final.md", _read_file(ws_path / "final.md")))

        report.append(f"\n**{sid} 生成耗时**: {gen_elapsed:.1f}s | ok={gen_result.get('ok')} | review={gen_result.get('review_status', '?')}")

    # ── Summary ──
    report.append("\n---\n\n## 总结果\n")
    report.append(f"- **Compose 耗时**: {compose_elapsed:.1f}s")
    report.append(f"- **测试科目**: 数据结构(Q1), 计算机网络(Q33), 操作系统(Q23)")
    report.append(f"- **模型**: Qwen3.6-27B-FP8")

    _write(report)
    print(f"\n报告已写入: {OUTPUT_REPORT}")


def _write(parts: list[str]):
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(test_cross_subject())
