"""Test the collaboration flow (WebGPT/GPT backend) for Q12.

Runs the generate phase using hybrid routing (local outline + remote GPT for
question/solve/review) and captures all inputs/outputs.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_REPORT = Path(__file__).resolve().parent.parent / "docs" / "test_report_collab.md"


def _read_file(path: str | Path) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else "(文件不存在)"


def _section(title: str, content: str) -> str:
    if len(content) > 8000:
        content = content[:8000] + "\n\n... (截断，全文见工作区文件)"
    return f"\n### {title}\n\n```\n{content}\n```\n"


async def test_collab():
    """Test collaboration flow with WebGPT for Q12."""
    from compose.generate_runner import load_compose_artifacts, _generate_doc
    from core_new.provider_router import get_routed_gateway
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"collab-{timestamp}"
    output_dir = "docs"
    workspace = os.path.join(output_dir, "workspace", run_id)

    report_parts = [
        f"# 协作流程测试报告 (WebGPT)\n",
        f"- **时间**: {datetime.now().isoformat()}",
        f"- **模式**: hybrid (本地Qwen + 远程GPT)",
        f"- **测试题位**: Q12",
        f"- **工作区**: {workspace}\n",
    ]

    # Load assembled doc
    compose_dir = "docs/compose"
    artifacts = load_compose_artifacts(compose_dir, slot_filter=["Q12"])

    if "Q12" not in artifacts:
        report_parts.append("**错误**: Q12 assembled doc 未找到\n")
        OUTPUT_REPORT.write_text("\n".join(report_parts), encoding="utf-8")
        return

    assembled_md = artifacts["Q12"].assembled_md
    report_parts.append("## Layer 0: 输入数据\n")
    report_parts.append(_section("输入: assembled.md (出题契约)", assembled_md[:3000] + "\n...(截断)"))

    # Run with hybrid model routing
    slot_data = {"slot_id": "Q12"}
    model_routing = {
        "_default": "local",
        "question": "webgpt",
        "review": "webgpt",
        "solve": "webgpt",
        "final_review": "webgpt",
    }

    report_parts.append("\n## 执行流水线\n")
    report_parts.append(f"Layer 1 跳过（使用 assembled doc）\n")
    report_parts.append(f"模型路由: question→webgpt, review→webgpt, solve→webgpt, final_review→webgpt\n")

    gateway = get_routed_gateway("generate")
    result = await _generate_doc(
        gateway, slot_data, "Q12", "",
        output_dir=output_dir,
        model_routing=model_routing,
        assembled_experience_doc=assembled_md,
        resume_from=1,
        run_id=run_id,
    )

    ws_path = Path(workspace) / "Q12"

    # Document each layer
    report_parts.append("## Layer 2: Question Agent (出题)\n")
    report_parts.append(_section("输出: question.md", _read_file(ws_path / "question.md")))

    report_parts.append("## Layer 3: Review Agent (题目审核)\n")
    report_parts.append(_section("输出: review.md", _read_file(ws_path / "review.md")))

    report_parts.append("## Layer 4: Solve Agent (独立求解)\n")
    report_parts.append(_section("输出: solution.md", _read_file(ws_path / "solution.md")))
    solve_py = _read_file(ws_path / "solve.py")
    if solve_py != "(文件不存在)":
        report_parts.append(_section("输出: solve.py", solve_py))
        report_parts.append(_section("输出: solve_output.txt", _read_file(ws_path / "solve_output.txt")))

    report_parts.append("## Layer 5: Final Review Agent (终审)\n")
    report_parts.append(_section("输出: final_review.md", _read_file(ws_path / "final_review.md")))

    report_parts.append("## Final: 最终输出\n")
    report_parts.append(_section("输出: final.md", _read_file(ws_path / "final.md")))

    # Result summary
    report_parts.append("## 结果摘要\n")
    for k, v in result.items():
        if k.startswith("_"):
            continue
        if k == "final_md" and v:
            report_parts.append(f"- **{k}**: (见上方 final.md)")
        else:
            report_parts.append(f"- **{k}**: {v}")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(report_parts), encoding="utf-8")
    print(f"\n报告已写入: {OUTPUT_REPORT}")


if __name__ == "__main__":
    asyncio.run(test_collab())
