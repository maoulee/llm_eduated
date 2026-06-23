"""GLM5.1 generation + GPT final review test.

Tests the new SC/COMP split with:
- GLM5.1: question generation + solve
- GPT (WebGPT): final review

Usage:
    python scripts/test_glm_gpt_review.py                  # Test Q12 (SC) + Q43 (COMP)
    python scripts/test_glm_gpt_review.py --slots Q1 Q45   # Custom slots
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_glm_gpt_review.md"

# Default test slots: one SC, one COMP
DEFAULT_SLOTS = ["Q12", "Q43"]


def _read_file(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    if len(content) > 6000:
        content = content[:6000] + "\n\n... (截断)"
    return f"\n### {title}\n\n{content}\n"


async def run_test(slot_ids: list[str]):
    from core_new.doc_pipeline import DocPipeline

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"{timestamp}"

    report = [
        "# GLM5.1 出题 + GPT 终审 测试报告\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **出题/求解模型**: GLM5.1 (remote)",
        f"- **终审模型**: GPT (WebGPT)",
        f"- **路由**: glm_gpt_review",
        f"- **测试题位**: {', '.join(slot_ids)}",
        f"- **run_id**: {run_id}",
    ]

    # Routing: GLM5.1 for question + solve, GPT for final_review
    model_routing = {
        "_default": "glm5.1",  # GLM5.1 for all roles except final_review
        "final_review": "hybrid",  # GPT generates, Qwen relays
    }

    total_time = 0

    for sid in slot_ids:
        # Determine type
        is_comp = 41 <= int(sid[1:]) <= 47
        q_type = "综合应用题" if is_comp else "选择题"
        subject_map = {
            "DS": "数据结构", "CO": "计算机组成原理",
            "OS": "操作系统", "CN": "计算机网络",
        }
        # Simple subject inference
        q_num = int(sid[1:])
        if q_num <= 11 or q_num in (41, 42):
            subject = "数据结构"
        elif 12 <= q_num <= 22 or q_num in (43, 44):
            subject = "计算机组成原理"
        elif 23 <= q_num <= 32 or q_num in (45, 46, 47):
            subject = "操作系统"
        else:
            subject = "计算机网络"

        report.append(f"\n---\n\n## {sid} ({subject} {q_type})\n")

        # Load experience card
        exp_dir = Path("data/slot_experiences")
        exp_path = exp_dir / f"{sid}_experience.md"
        if exp_path.exists():
            experience_doc = exp_path.read_text(encoding="utf-8")
            report.append(f"- **经验卡**: {len(experience_doc)} chars")
        else:
            experience_doc = ""
            report.append(f"- **经验卡**: 未找到")

        # Run pipeline
        workspace = f"docs/workspace/{run_id}"
        dp = DocPipeline(workspace=workspace, model_routing=model_routing)

        slot_data = {
            "slot_id": sid,
            "subject": subject,
            "question_type": "comprehensive" if is_comp else "single_choice",
        }

        print(f"\n{'='*60}")
        print(f"  {sid} ({subject} {q_type}) — GLM5.1 出题 + GPT 终审")
        print(f"{'='*60}")

        t0 = time.monotonic()
        try:
            result = await dp.run(
                slot_id=sid,
                slot_data=slot_data,
                assembled_experience_doc=experience_doc,
                start_layer=2,  # Skip outline, use assembled doc
                question_type="comprehensive" if is_comp else "single_choice",
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            report.append(f"\n**Pipeline 异常** ({elapsed:.1f}s): `{e}`\n")
            print(f"  [{sid}] FAILED: {e}")
            continue

        elapsed = time.monotonic() - t0
        total_time += elapsed

        # Report results
        ws = Path(workspace) / sid
        report.append(f"- **耗时**: {elapsed:.1f}s")
        report.append(f"- **ok**: {result.ok}")
        report.append(f"- **review_status**: {result.review_status}")
        report.append(f"- **code_exec_ok**: {result.code_exec_ok}")

        # Agent outputs
        report.append(_section("question.md", _read_file(ws / "question.md")))
        report.append(_section("review.md", _read_file(ws / "review.md")))
        report.append(_section("solution.md", _read_file(ws / "solution.md")))

        solve_py = _read_file(ws / "solve.py")
        if solve_py != "(文件不存在)":
            report.append(_section("solve.py", solve_py))
            report.append(_section("solve_output.txt", _read_file(ws / "solve_output.txt")))

        report.append(_section("final_review.md (GPT)", _read_file(ws / "final_review.md")))
        report.append(_section("final.md", _read_file(ws / "final.md")))

        print(f"  [{sid}] Done: {elapsed:.1f}s, ok={result.ok}, review={result.review_status}")

    # Summary
    report.append(f"\n---\n\n## 汇总\n")
    report.append(f"- **总耗时**: {total_time:.1f}s")
    report.append(f"- **模型配置**: GLM5.1 (出题+求解) + GPT (终审)")
    report.append(f"- **run_id**: {run_id}")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"\n报告已写入: {OUTPUT_REPORT}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--slots", nargs="+", default=DEFAULT_SLOTS)
    args = parser.parse_args()
    asyncio.run(run_test(args.slots))


if __name__ == "__main__":
    main()
