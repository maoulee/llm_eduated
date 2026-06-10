from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routes import interact_v2
from api.schemas_interact_v2 import AnnotationSubmission, SlotAnnotation
from api.services.draft_parser import parse_draft_md
from api.services.interact_v2_service import InteractV2Service


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


class FakeScheduler:
    def __init__(self, workspace):
        self.workspace = workspace
        self._interact_sessions = {}

    async def run_conversation_turn(self, session_id, teacher_message, role="interact"):
        ws = self.workspace / session_id
        draft_path = ws / "compose" / "interact_draft.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(
            "# 草案\n\n## Q1（选择题·2分）\n[ ] Cache映射（需多步推演）\n",
            encoding="utf-8",
        )
        self._interact_sessions[session_id] = SimpleNamespace(
            status="collecting",
            scenario="B_knowledge_point",
            turn_count=1,
        )
        return {
            "response_text": "草案已写入，请查看。",
            "files_written": ["compose/interact_draft.md"],
        }


def test_api_app_imports_with_legacy_and_v2_schemas():
    import api.app  # noqa: F401
    from api.schemas import SendMessageRequest
    from api.schemas_interact_v2 import DraftData

    assert SendMessageRequest.model_fields["message"]
    assert DraftData.model_fields["sections"]


def test_send_turn_parses_draft_from_written_file(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()

    result = run_async(service.send_turn(session.session_id, "出一道Cache题"))

    assert result.has_draft is True
    assert result.session_state == "reviewing"
    draft = service.get_draft(session.session_id)
    assert draft is not None
    assert draft.sections[0].slot_id == "Q1"
    assert draft.sections[0].options[0].text == "Cache映射"


def test_get_result_finds_yaml_under_compose_dir(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    result_path = tmp_path / session.session_id / "compose" / "paper_request.yaml"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text("schema_version: paper_request_v1\n", encoding="utf-8")

    result = service.get_result(session.session_id)

    assert result == {"schema_version": "paper_request_v1"}


def test_submit_annotation_rejects_stale_draft_id(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._drafts[session.session_id] = parse_draft_md(
        "# 草案\n\n## Q1\n[ ] A选项\n",
        draft_id="current",
    )

    stale = AnnotationSubmission(
        draft_id="stale",
        slots=[
            SlotAnnotation(
                slot_id="Q1",
                kept_options=["opt_1_1"],
                removed_options=[],
            )
        ],
    )

    with pytest.raises(ValueError, match="Draft ID mismatch"):
        service.submit_annotation(session.session_id, stale)


def test_draft_parser_preserves_internal_parentheses_and_hides_k_terms():
    draft = parse_draft_md(
        "# 草案\n\n"
        "## Q1\n"
        "[ ] Kahn算法（队列实现）— 入度删除（K3）\n"
        "> 教师批注: 不要显示K2\n",
        draft_id="d1",
    )

    option = draft.sections[0].options[0]
    assert option.text == "Kahn算法（队列实现）— 入度删除"
    assert option.cognitive_desc == "多步推演"
    assert "K2" not in draft.sections[0].annotation
    assert "单步代入" in draft.sections[0].annotation


def test_draft_parser_sanitizes_compact_k_labels_without_duplication():
    draft = parse_draft_md(
        "# 草案\n\n## Q1\n[ ] 地址字段划分（K3多步推演）\n",
        draft_id="d1",
    )

    option = draft.sections[0].options[0]
    assert option.text == "地址字段划分"
    assert option.cognitive_desc == "多步推演"


def test_v2_routes_return_400_for_invalid_session_id():
    with pytest.raises(HTTPException) as exc_info:
        run_async(interact_v2.get_draft("../bad"))

    assert exc_info.value.status_code == 400


def test_v2_routes_return_404_for_missing_session():
    with pytest.raises(HTTPException) as exc_info:
        run_async(interact_v2.get_session("abcdef123456"))

    assert exc_info.value.status_code == 404
