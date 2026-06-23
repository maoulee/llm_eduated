#!/usr/bin/env python3
"""单题出题测试：构造一个 slot 直接跑 DocPipeline，看路由 + 耗时。

不走 compose 全链，直接喂 slot_data 给 DocPipeline.run()。
用于快速验证：概念题/标准题路由、单题真实耗时、超时保护。

用法：
  # 标准题（full pipeline: design→solve→review→final）
  python scripts/test_single_slot.py --complexity standard

  # 概念题（轻量路径：concept_creator→review，跳过 solve/final）
  python scripts/test_single_slot.py --complexity conceptual

  # 自定义知识点/形式
  python scripts/test_single_slot.py --topic "单链表判断是否有环" --form "题干给单链表场景，要求用C描述算法思想并编写代码"
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")


# 预设 slot 模板（可被 --topic/--form 覆盖）
SLOT_TEMPLATES = {
    "standard": {
        "slot_id": "TEST_STD",
        "question_type": "comprehensive",
        "score": 13,
        "primary_target_name": "单链表判断是否有环",
        "target_family": "DS-2 > 线性表 > 单链表",
        "target_difficulty": 4,
        "examination_mode": "算法设计与分析",
        "expected_form": "题干给单链表场景，要求用 C 或 C++ 语言：①定义链表结点数据类型 ②描述算法基本设计思想 ③编写算法",
        "complexity": "standard",
        "k_radar": {"K1": 2, "K2": 2, "K3": 4, "K4": 3, "K5": 2},
        "k_dominant": "K3",
        "difficulty_rationale": "需设计算法+分析时空复杂度",
    },
    "conceptual": {
        "slot_id": "TEST_CONCEPT",
        "question_type": "single_choice",
        "score": 5,
        "primary_target_name": "SRAM 与 DRAM 的区别",
        "target_family": "CO-4 > 存储系统",
        "target_difficulty": 2,
        "examination_mode": "概念辨析",
        "expected_form": "",  # 概念题留空
        "complexity": "conceptual",
        "k_radar": {"K1": 3, "K2": 1, "K3": 1, "K4": 2, "K5": 1},
        "k_dominant": "K1",
        "difficulty_rationale": "纯概念记忆与辨析",
    },
}


def _build_assembled_doc(slot_data: dict) -> str:
    """构造预制 assembled doc，跳过 outline 生成（Layer 1）。

    两条 complexity 路径都用预制 doc，纯粹测 concept_creator vs
    design+solve 的路由差异和耗时，不卡在 outline。
    """
    sid = slot_data["slot_id"]
    qt = slot_data["question_type"]
    mode = slot_data["examination_mode"]
    topic = slot_data["primary_target_name"]
    diff = slot_data["target_difficulty"]
    return f"""## final_machine_contract

```yaml
slot_id: {sid}
question_type: {qt}
score: {slot_data.get("score", 5)}
examination_mode: {mode}
```

---

# {sid} 出题参考文档（考察模式：{mode}）

## 本次出题要求（来自组卷大纲）
- **考点**: {topic}
- **知识域**: {slot_data.get("target_family", "通用")}
- **难度**: {diff}
- **难度说明**: {slot_data.get("difficulty_rationale", "")}
- **考察模式**: {mode}
"""


async def run_single_slot(complexity: str, topic: str | None, form: str | None,
                          output_dir: str, timeout: int):
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway

    gateway = get_gateway("api_vllm")
    slot_data = dict(SLOT_TEMPLATES[complexity])
    if topic:
        slot_data["primary_target_name"] = topic
    if form is not None:
        slot_data["expected_form"] = form

    slot_id = slot_data["slot_id"]
    print("=" * 60)
    print(f"单题测试: {slot_id}")
    print(f"  complexity: {complexity}")
    print(f"  知识点: {slot_data['primary_target_name']}")
    print(f"  expected_form: {slot_data['expected_form'][:60] or '(空-概念题)'}")
    print(f"  timeout: {timeout}s")
    print("=" * 60)

    dp = DocPipeline(workspace=output_dir, model_routing={"_default": "api_vllm"})
    # 预制 assembled doc：跳过 Layer 1 (outline 生成)，直接进 blueprint→出题。
    # 两条路径都不卡 outline，纯粹对比 concept_creator vs design+solve。
    assembled = _build_assembled_doc(slot_data)
    t0 = time.monotonic()

    try:
        result = await asyncio.wait_for(
            dp.run(
                slot_id=slot_id,
                slot_data=slot_data,
                experience_card="",
                k_definitions="",
                assembled_experience_doc=assembled,
            ),
            timeout=timeout,
        )
        elapsed = time.monotonic() - t0
        print(f"\n{'=' * 60}")
        print(f"完成 ({elapsed:.1f}s)")
        print(f"  ok: {result.ok}")
        print(f"  pipeline_type: {result.pipeline_type}")
        print(f"  review: {result.review_status}")
        print(f"  total_time_s: {result.total_time_s}")
        if result.final_content:
            print(f"  final.md 长度: {len(result.final_content)} chars")
        print(f"{'=' * 60}")
        return result

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        print(f"\n⏱ TIMEOUT after {elapsed:.0f}s (limit {timeout}s)")
        return None
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"\n❌ FAILED ({elapsed:.1f}s): {type(e).__name__}: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="单题出题测试（直接 DocPipeline）")
    parser.add_argument("--complexity", choices=["standard", "conceptual"],
                        default="standard", help="题目类型（决定路由路径）")
    parser.add_argument("--topic", help="覆盖知识点")
    parser.add_argument("--form", help="覆盖 expected_form（传空串=概念题留空）")
    parser.add_argument("--output-dir", default="docs/test_output/single_slot",
                        help="工作目录")
    parser.add_argument("--timeout", type=int,
                        default=int(os.getenv("SLOT_TIMEOUT_SECONDS", "900")),
                        help="单题超时（秒），默认 900 (15min)")
    args = parser.parse_args()

    asyncio.run(run_single_slot(
        args.complexity, args.topic, args.form, args.output_dir, args.timeout,
    ))


if __name__ == "__main__":
    main()
