"""Test hybrid composition: use GPT to generate paper outline via WebGPT.

Usage:
    export WEBGPT_API_KEY="your-key"
    python test_hybrid_outline.py [--routing hybrid]
"""
import asyncio
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.webgpt_client import get_webgpt_client
from core_new.slot_prompts import PAPER_OUTLINE_PROMPT


def load_slot_contracts():
    """Load slot contracts from slot_templates.json + experience cards."""
    import json
    from core_new.slot_contract import build_slot_contract
    from pathlib import Path

    with open("data/slot_templates.json", encoding="utf-8") as f:
        data = json.load(f)
    templates = data.get("templates", {})

    # Load experience cards
    exp_dir = Path("data/slot_experiences")
    experience_cards = {}
    for path in sorted(exp_dir.glob("*_experience.md")):
        sid = path.stem.replace("_experience", "")
        experience_cards[sid] = path.read_text(encoding="utf-8")

    contracts = {}
    for sid, tpl in templates.items():
        try:
            exp_card = experience_cards.get(sid, "")
            contract = build_slot_contract(sid, tpl, exp_card)
            if contract:
                contracts[sid] = contract
        except Exception as e:
            print(f"  Warning: failed to load {sid}: {e}")
    return contracts


def build_slot_contracts_md(contracts: dict) -> str:
    """Slot contracts are already markdown strings — just concatenate."""
    parts = []
    for slot_id in sorted(contracts.keys()):
        parts.append(contracts[slot_id])
    return "\n\n---\n\n".join(parts)


GPT_OUTLINE_SYSTEM = (
    "# 408考研组卷专家\n\n"
    "你是一位408考研组卷专家，以教师的视角规划试卷大纲。大纲是给下游出题智能体的'命题指令'。\n\n"
    "## 输出格式\n"
    "Markdown格式，包含：\n"
    "- `# 试卷大纲` 标题\n"
    "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
    "- 每个题位一个 `## Qxx` 段落，包含：target_subject, target_family, primary_target_name, "
    "difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
    "## 核心约束\n"
    "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
    "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
    "- 不要输出选项风格、干扰策略等设计级决策\n"
    "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
    "直接输出 Markdown 内容，不要用代码块包裹。"
)


async def test_hybrid_outline():
    client = get_webgpt_client()
    if not client:
        print("ERROR: WebGPT not configured. Set WEBGPT_API_KEY.")
        return

    # Health check
    print("Checking WebGPT connection...")
    ok = await client.health_check()
    if not ok:
        print("ERROR: WebGPT not reachable at", client.base_url)
        return
    print("WebGPT connected.\n")

    # Load slot contracts
    print("Loading slot contracts...")
    contracts = load_slot_contracts()
    print(f"  Loaded {len(contracts)} slots: {', '.join(sorted(contracts.keys())[:5])}...")

    # Build prompt
    slot_md = build_slot_contracts_md(contracts)
    user_req = "408考研模拟试卷，难度中等偏上（3-4），覆盖计算机组成原理、数据结构、操作系统、计算机网络四科。"
    prompt = PAPER_OUTLINE_PROMPT.format(
        user_requirements=user_req,
        slot_contracts_md=slot_md,
    )

    print(f"\nSending to GPT (prompt: {len(prompt)} chars)...")
    t0 = time.monotonic()

    try:
        raw = await client.delegate(
            agent_name="hybrid_outline",
            slot_id="test_outline",
            system_prompt=GPT_OUTLINE_SYSTEM,
            content=prompt,
        )
    except Exception as e:
        print(f"ERROR: GPT call failed: {e}")
        return

    elapsed = time.monotonic() - t0
    print(f"\nGPT responded in {elapsed:.1f}s ({len(raw)} chars)\n")

    # Print result
    print("=" * 60)
    print("GPT Outline Output:")
    print("=" * 60)
    print(raw[:3000])
    if len(raw) > 3000:
        print(f"\n... (truncated, total {len(raw)} chars)")

    # Validate structure
    print("\n" + "=" * 60)
    print("Validation:")
    print("=" * 60)
    slots_found = []
    for line in raw.split("\n"):
        if line.startswith("## Q"):
            slot_id = line.split()[1].strip("（").strip("）")
            slots_found.append(slot_id)
    print(f"  Slots found: {len(slots_found)} → {slots_found}")
    print(f"  Has 整体规划: {'整体规划' in raw}")
    print(f"  Has examination_mode: {'examination_mode' in raw}")
    print(f"  Has difficulty_level: {'difficulty_level' in raw}")

    # Cleanup
    await client.cleanup(slot_id="test_outline")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test_hybrid_outline())
