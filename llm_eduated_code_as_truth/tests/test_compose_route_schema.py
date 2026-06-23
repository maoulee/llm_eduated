from __future__ import annotations

import asyncio

from compose.compose_runner import compose_route_2


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_compose_route_2_accepts_current_slot_blueprint_schema(monkeypatch):
    async def fake_run_topic_search(**_kwargs):
        return {
            "outline_section": "## TOPIC_001\n- mode: 旋转判断\n",
            "topic_card": {
                "modes": [
                    {"name": "旋转判断"},
                    {"name": "平衡因子计算"},
                ]
            },
        }

    monkeypatch.setattr("compose.topic_search.run_topic_search", fake_run_topic_search)

    slot_blueprint = {
        "slot_id": "TOPIC_001",
        "question_type": "single_choice",
        "score": 2,
        "target_subject": "数据结构",
        "target_family": "数据结构 > 树与二叉树 > 平衡二叉树",
        "primary_target_name": "AVL树旋转",
        "target_difficulty": 4,
        "active_selection": {"selected_knowledge": ["AVL树旋转"]},
        "excluded_modes": ["构造证明"],
        "excluded_knowledge": ["红黑树"],
    }
    templates = {"TOPIC_001": {"question_type": "single_choice", "score": 2}}

    _outline, blueprint = run_async(
        compose_route_2(None, slot_blueprint, templates)
    )

    slot = blueprint["slots"][0]
    assert slot.target_difficulty == 4
    assert slot.excluded_modes == ["构造证明"]
    assert slot.excluded_knowledge == ["红黑树"]
    assert slot.candidate_pool_visible == ["旋转判断", "平衡因子计算"]
