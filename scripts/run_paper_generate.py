#!/usr/bin/env python3
"""D 场景整卷出题：paper_request.yaml → generate（绕过 compose）。

compose 流程依赖经验卡 templates，D 场景（interact 自由生成 slot）无经验卡，
走不通。本脚本直接从 paper_request.yaml 构造 generate 需要的输入：
  - paper_selection.yaml（slot blueprint 元数据）
  - {slot_id}_assembled.md（每题出题参考文档，跳 outline）
然后调 run_generate 跑整卷出题。

用法：
  python scripts/run_paper_generate.py --paper-request <path> [--slots Q1 Q5]
  python scripts/run_paper_generate.py --paper-request <paper_request.yaml>
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")


def _build_assembled_md(slot: dict) -> str:
    """从 paper_request slot 构造 assembled doc（跳 outline，直进 blueprint）。"""
    sid = slot.get("slot_id", "Q?")
    qt = slot.get("question_type", "subjective")
    mode = slot.get("examination_mode", "")
    topic = slot.get("primary_target_name", "")
    diff = slot.get("target_difficulty", 3)
    family = slot.get("target_family", "")
    score = slot.get("score", 5)
    form = slot.get("expected_form", "")
    rationale = slot.get("difficulty_rationale", "")
    return f"""## final_machine_contract

```yaml
slot_id: {sid}
question_type: {qt}
score: {score}
examination_mode: {mode}
expected_form: "{form}"
complexity: {slot.get("complexity", "standard")}
```

---

# {sid} 出题参考文档（考察模式：{mode}）

## 本次出题要求（来自组卷大纲）
- **考点**: {topic}
- **知识域**: {family}
- **难度**: {diff}
- **难度说明**: {rationale}
- **考察模式**: {mode}
"""


def prepare_compose_dir(paper_request_path: str, compose_dir: str,
                        slot_filter: list[str] | None = None) -> list[str]:
    """从 paper_request.yaml 构造 generate 所需的 compose_dir 产物。

    写入：
      - {compose_dir}/{slot_id}_assembled.md（每题）
      - {compose_dir}/paper_selection.yaml（blueprint 元数据）
      - {compose_dir}/manifest.md（slot 列表）
    返回实际处理的 slot_id 列表。
    """
    import yaml

    with open(paper_request_path, encoding="utf-8") as f:
        req = yaml.safe_load(f)

    slots = req.get("slots", [])
    if slot_filter:
        slots = [s for s in slots if s.get("slot_id") in slot_filter]

    compose_path = Path(compose_dir)
    compose_path.mkdir(parents=True, exist_ok=True)

    # 写每 slot 的 assembled.md
    written_slots = []
    for slot in slots:
        sid = slot.get("slot_id", f"Q{len(written_slots)+1}")
        assembled = _build_assembled_md(slot)
        (compose_path / f"{sid}_assembled.md").write_text(assembled, encoding="utf-8")
        written_slots.append(sid)

    # 写 paper_selection.yaml（_load_blueprint_map 优先读这个）
    selection = {"slots": []}
    for slot in slots:
        sid = slot.get("slot_id")
        selection["slots"].append({
            "slot_id": sid,
            "question_type": slot.get("question_type", "subjective"),
            "score": slot.get("score", 5),
            "examination_mode": slot.get("examination_mode", ""),
            "complexity": slot.get("complexity", "standard"),
            "expected_form": slot.get("expected_form", ""),
            "primary_target_name": slot.get("primary_target_name", ""),
            "target_difficulty": slot.get("target_difficulty", 3),
            "teacher_annotation": slot.get("teacher_annotation", ""),
        })
    (compose_path / "paper_selection.yaml").write_text(
        yaml.dump(selection, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 写 manifest.md（load_compose_artifacts 读 slot 列表）
    manifest_lines = ["| Slot | Type |", "|------|------|"]
    for slot in slots:
        sid = slot.get("slot_id")
        manifest_lines.append(f"| {sid} | {slot.get('complexity', 'standard')} |")
    (compose_path / "manifest.md").write_text(
        "\n".join(manifest_lines), encoding="utf-8")

    return written_slots


async def run(paper_request_path: str, output_dir: str,
              slot_filter: list[str] | None, routing: str):
    from compose import generate_runner
    from core_new.llm_gateway import get_gateway

    compose_dir = os.path.join(output_dir, "compose")
    written = prepare_compose_dir(paper_request_path, compose_dir, slot_filter)

    print("=" * 60)
    print(f"D 场景整卷出题: {len(written)} slots")
    print(f"  slots: {written}")
    print(f"  compose_dir: {compose_dir}")
    print(f"  timeout: {os.getenv('SLOT_TIMEOUT_SECONDS', '900')}s/slot")
    print(f"  concurrency: {os.getenv('PIPELINE_SLOT_CONCURRENCY', '2')}")
    print("=" * 60)

    provider = routing if routing != "all_local" else "api_vllm"
    gateway = get_gateway(provider)
    model_routing = {"_default": provider}

    result = await generate_runner.run_generate(
        gateway,
        compose_dir=compose_dir,
        output_dir=output_dir,
        model_routing=model_routing,
        slot_filter=slot_filter,
    )
    print(f"\n结果: status={result.get('status')}")
    questions = result.get("questions", [])
    ok_count = sum(1 for q in questions if q.get("ok"))
    timeout_count = sum(1 for q in questions if q.get("status") == "timeout")
    print(f"  成功: {ok_count}/{len(questions)}, 超时: {timeout_count}")
    for q in questions:
        sid = q.get("slot_id", "?")
        status = "timeout" if q.get("status") == "timeout" else ("ok" if q.get("ok") else "fail")
        t = q.get("generation_time_s", 0)
        print(f"    {sid}: {status} ({t:.0f}s)")
    return result


def main():
    parser = argparse.ArgumentParser(description="D 场景整卷出题（paper_request → generate）")
    parser.add_argument("--paper-request", required=True, help="paper_request.yaml 路径")
    parser.add_argument("--output-dir", default="docs/test_output/paper_generate",
                        help="输出目录")
    parser.add_argument("--slots", nargs="+", help="只跑指定 slot（如 --slots Q1 Q5）")
    parser.add_argument("--routing", default="all_local", help="路由 profile")
    args = parser.parse_args()

    asyncio.run(run(args.paper_request, args.output_dir, args.slots, args.routing))


if __name__ == "__main__":
    main()
