from __future__ import annotations

import asyncio
import unittest.mock
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routes import interact_v2
from api.schemas_interact_v2 import (
    AnnotationSubmission,
    QuestionAnnotationRequest,
    SlotAnnotation,
)
from api.services.display_result_service import DisplayResultService
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


class HandoffOnlyScheduler(FakeScheduler):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.last_teacher_message = ""

    async def run_conversation_turn(self, session_id, teacher_message, role="interact"):
        self.last_teacher_message = teacher_message
        ws = self.workspace / session_id
        result_path = ws / "compose" / "paper_request.yaml"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text("schema_version: paper_request_v1\n", encoding="utf-8")
        self._interact_sessions[session_id] = SimpleNamespace(
            status="collecting",
            scenario="C_free_compose",
            turn_count=2,
        )
        return {
            "response_text": "交接文档已生成。",
            "files_written": ["compose/paper_request.yaml"],
        }


class RecordingDraftScheduler(FakeScheduler):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.call_count = 0
        self.last_teacher_message = ""

    async def run_conversation_turn(self, session_id, teacher_message, role="interact"):
        self.call_count += 1
        self.last_teacher_message = teacher_message
        ws = self.workspace / session_id
        draft_path = ws / "compose" / "interact_draft.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(
            "[SCENARIO: C]\n[ROUND: 1]\n[PHASE: knowledge]\n"
            "# 第一轮草案\n\n"
            "## Q1 考察范围\n"
            "[ ] 线性表\n"
            "[ ] 树和二叉树\n\n"
            "## Q1 题型\n"
            "[ ] 选择题\n"
            "[ ] 算法题\n",
            encoding="utf-8",
        )
        self._interact_sessions[session_id] = SimpleNamespace(
            status="collecting",
            scenario="C_free_compose",
            turn_count=1,
        )
        return {
            "response_text": "[SCENARIO: C] 第一轮草案已生成。",
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
    assert draft.sections[0].display_id == "1"
    assert draft.sections[0].options[0].text == "Cache映射"


def test_session_history_persists_turn_messages(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()

    run_async(service.send_turn(session.session_id, "出一道Cache题"))
    history = service.get_session_history(session.session_id)

    assert history["title"] == "出一道Cache题"
    assert history["messages"][0]["role"] == "teacher"
    assert history["messages"][0]["content"] == "出一道Cache题"
    assert history["messages"][1]["role"] == "agent"
    assert "草案已写入" in history["messages"][1]["content"]


def test_list_sessions_filters_by_user_id():
    service = InteractV2Service()

    alice = service.create_session(user_id="alice")
    bob = service.create_session(user_id="bob")

    alice_sessions = service.list_sessions(user_id="alice")
    bob_sessions = service.list_sessions(user_id="bob")

    assert [s.session_id for s in alice_sessions] == [alice.session_id]
    assert [s.session_id for s in bob_sessions] == [bob.session_id]
    assert service.get_session_info(alice.session_id).user_id == "alice"


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


def test_submit_annotation_accepts_selected_option_id_only(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._drafts[session.session_id] = parse_draft_md(
        "# 草案\n\n## Q1\n[ ] A选项\n[ ] B选项\n",
        draft_id="current",
    )

    annotation = AnnotationSubmission(
        draft_id="current",
        slots=[
            SlotAnnotation(
                slot_id="Q1",
                selected_option_id="opt_1_2",
            )
        ],
    )

    assert service.submit_annotation(session.session_id, annotation) is True
    written = (
        tmp_path
        / session.session_id
        / "compose"
        / "interact_draft.md"
    ).read_text(encoding="utf-8")
    assert "B选项" in written
    assert "A选项" not in written
    history = service.get_session_history(session.session_id)
    assert history["messages"][-1]["role"] == "teacher"
    assert "已提交草案选择" in history["messages"][-1]["content"]


def test_display_result_builds_teacher_view_from_draft_selection(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._drafts[session.session_id] = parse_draft_md(
        "# 草案\n\n## Q1（选择题·2分）\n[ ] A方向（概念辨析）\n[ ] B方向（多步推演）\n",
        draft_id="current",
    )
    service.submit_annotation(
        session.session_id,
        AnnotationSubmission(
            draft_id="current",
            slots=[SlotAnnotation(slot_id="Q1", selected_option_id="opt_1_2")],
        ),
    )

    result = DisplayResultService(service).get_display_result(session.session_id)

    assert result.status == "partial"
    assert result.questions[0].display_id == "1"
    assert result.questions[0].status == "generating"
    assert "B方向" in result.questions[0].stem
    assert "## 一、试题" in result.paper_markdown


def test_display_result_reads_generated_final_md(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._scheduler_cache["api_vllm_False"] = fake_scheduler
    qdir = tmp_path / session.session_id / "Q12"
    qdir.mkdir(parents=True)
    (qdir / "final.md").write_text(
        "## 题目\n题干文本\n\n"
        "## 选项\n- A: 选项A\n- B: 选项B\n\n"
        "## 求解过程\n解析文本\n\n"
        "## 答案\n**B**\n",
        encoding="utf-8",
    )

    result = DisplayResultService(service).get_display_result(session.session_id)

    assert result.status == "completed"
    assert result.questions[0].slot_id == "Q12"
    assert result.questions[0].options == ["选项A", "选项B"]
    assert result.questions[0].answer == "B"


def test_display_result_uses_handoff_title_for_internal_topic_slot(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._scheduler_cache["api_vllm_False"] = fake_scheduler
    handoff = tmp_path / session.session_id / "compose" / "slot_blueprint.yaml"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "schema_version: slot_blueprint_v1\n"
        "slot_id: TOPIC_001\n"
        "question_type: single_choice\n"
        "primary_target_name: 平衡二叉树AVL — 最小不平衡子树定位\n",
        encoding="utf-8",
    )
    qdir = tmp_path / session.session_id / "questions" / "TOPIC_001"
    qdir.mkdir(parents=True)
    (qdir / "error.md").write_text("mock failure", encoding="utf-8")

    result = DisplayResultService(service).get_display_result(session.session_id)

    assert len(result.questions) == 1
    assert result.questions[0].display_id == "1"
    assert result.questions[0].title == "选择题 — 平衡二叉树AVL — 最小不平衡子树定位"
    assert "TOPIC_001" not in result.paper_markdown


def test_display_result_collapses_nested_pipeline_work_artifacts(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._scheduler_cache["api_vllm_False"] = fake_scheduler
    handoff = tmp_path / session.session_id / "compose" / "slot_blueprint.yaml"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "schema_version: slot_blueprint_v1\n"
        "slot_id: TOPIC_001\n"
        "question_type: single_choice\n"
        "primary_target_name: AVL树插入模拟\n",
        encoding="utf-8",
    )
    public_dir = tmp_path / session.session_id / "questions" / "TOPIC_001"
    nested_dir = public_dir / "TOPIC_001"
    nested_dir.mkdir(parents=True)
    (public_dir / "error.md").write_text("outer failure", encoding="utf-8")
    (nested_dir / "question.md").write_text(
        "## 题目\n不应作为第二题展示\n",
        encoding="utf-8",
    )

    result = DisplayResultService(service).get_display_result(session.session_id)

    assert len(result.questions) == 1
    assert result.questions[0].stem == "outer failure"


def test_display_result_recomputes_status_after_pipeline_progress_merge(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._drafts[session.session_id] = parse_draft_md(
        "# 草案\n\n## Q1\n[ ] A方向\n",
        draft_id="current",
    )
    service.submit_annotation(
        session.session_id,
        AnnotationSubmission(
            draft_id="current",
            slots=[SlotAnnotation(slot_id="Q1", selected_option_id="opt_1_1")],
        ),
    )

    from api.services.pipeline_trigger import PipelineProgress, _jobs

    progress = PipelineProgress(session.session_id, 1)
    progress.slot_status["Q1"] = {
        "status": "completed",
        "stage": "已完成",
        "label": "第1题",
    }
    _jobs[session.session_id] = progress
    try:
        result = DisplayResultService(service).get_display_result(session.session_id)
    finally:
        _jobs.pop(session.session_id, None)

    assert result.status == "completed"
    assert result.questions[0].status == "completed"
    assert result.questions[0].progress_label == "已完成"


def test_display_result_reports_failed_when_pipeline_failed(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    service._drafts[session.session_id] = parse_draft_md(
        "# 草案\n\n## Q1\n[ ] A方向\n",
        draft_id="current",
    )
    service.submit_annotation(
        session.session_id,
        AnnotationSubmission(
            draft_id="current",
            slots=[SlotAnnotation(slot_id="Q1", selected_option_id="opt_1_1")],
        ),
    )

    from api.services.pipeline_trigger import PipelineProgress, _jobs

    progress = PipelineProgress(session.session_id, 1)
    progress.slot_status["Q1"] = {
        "status": "failed",
        "stage": "失败: mock",
        "label": "第1题",
    }
    _jobs[session.session_id] = progress
    try:
        result = DisplayResultService(service).get_display_result(session.session_id)
    finally:
        _jobs.pop(session.session_id, None)

    assert result.status == "failed"
    assert result.questions[0].status == "failed"
    assert "mock" in result.questions[0].progress_label


def test_display_result_saves_question_annotation(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    display = DisplayResultService(service)

    response = display.save_question_annotation(
        session.session_id,
        "Q1",
        QuestionAnnotationRequest(annotation="加大难度"),
    )

    assert response.ok is True
    assert response.status == "recorded"


def test_display_result_regeneration_annotation_is_record_only(tmp_path):
    service = InteractV2Service()
    fake_scheduler = FakeScheduler(tmp_path)
    service._get_scheduler = lambda provider, thinking: fake_scheduler
    session = service.create_session()
    display = DisplayResultService(service)

    response = display.save_question_annotation(
        session.session_id,
        "Q1",
        QuestionAnnotationRequest(annotation="本题加一个陷阱条件", action="regenerate_question"),
    )

    assert response.ok is True
    assert response.status == "recorded"
    assert "尚未接入" in response.message


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


def test_draft_parser_preserves_round_marker():
    draft = parse_draft_md(
        "[SCENARIO: C]\n[ROUND: 2]\n"
        "# 第二轮草案\n\n"
        "## Q1 考察模式\n"
        "[ ] 计算型 · CPU执行时间公式计算\n",
        draft_id="d1",
    )

    assert draft.scenario == "C"
    assert draft.current_round == 2
    assert draft.sections[0].display_id == "1"
    assert draft.sections[0].phase == "examination"


def test_draft_parser_infers_section_phase_markers():
    draft = parse_draft_md(
        "[SCENARIO: C]\n[ROUND: 1]\n[PHASE: knowledge]\n"
        "# 第一轮草案\n\n"
        "## Q1 知识点\n"
        "[ ] AVL旋转\n"
        "## Q1 题型\n"
        "[ ] 选择题\n",
        draft_id="d1",
    )

    assert draft.sections[0].phase == "knowledge"
    assert draft.sections[1].phase == "question_type"


def test_render_annotated_md_preserves_phase_header(tmp_path):
    from api.services.draft_parser import render_annotated_md

    draft = parse_draft_md(
        "[SCENARIO: C]\n[ROUND: 1]\n[PHASE: knowledge]\n"
        "# 第一轮草案\n\n"
        "## Q1 知识点\n"
        "[ ] AVL旋转\n",
        draft_id="d1",
    )
    rendered = render_annotated_md(
        draft,
        AnnotationSubmission(
            draft_id="d1",
            slots=[SlotAnnotation(slot_id="Q1", selected_option_id="opt_1_1")],
        ),
    )

    assert "[SCENARIO: C]" in rendered
    assert "[ROUND: 1]" in rendered
    assert "[PHASE: knowledge]" in rendered
    assert "AVL旋转" in rendered


def test_pipeline_trigger_records_setup_failure(tmp_path):
    from api.services.pipeline_trigger import _jobs, get_job, trigger_generation

    session_id = "setupfail001"
    _jobs.pop(session_id, None)
    handoff = tmp_path / "paper_request.yaml"
    handoff.write_text("slots: [", encoding="utf-8")

    with pytest.raises(Exception):
        run_async(trigger_generation(session_id, handoff, tmp_path))

    job = get_job(session_id)
    try:
        assert job is not None
        assert job.status == "failed"
        assert job.is_done is True
        assert job.error
        assert job.to_dict()["status"] == "failed"
    finally:
        _jobs.pop(session_id, None)


def test_v2_routes_return_400_for_invalid_session_id():
    with pytest.raises(HTTPException) as exc_info:
        run_async(interact_v2.get_draft("../bad"))

    assert exc_info.value.status_code == 400


def test_v2_routes_return_404_for_missing_session():
    with pytest.raises(HTTPException) as exc_info:
        run_async(interact_v2.get_session("abcdef123456"))

    assert exc_info.value.status_code == 404


def test_pipeline_progress_returns_404_for_missing_session():
    with pytest.raises(HTTPException) as exc_info:
        run_async(interact_v2.get_pipeline_progress("abcdef123456"))

    assert exc_info.value.status_code == 404


# ── 确认门 + 产物边界校验（行为归 LLM，边界归 service）──────────────


def _make_service_with_handoff(tmp_path, slots):
    """Build a service whose workspace already contains a paper_request.yaml.

    Uses a no-op scheduler (doesn't overwrite the pre-written YAML), so the
    confirm-gate logic sees exactly the slots we planted.
    """
    import yaml

    class _NoopScheduler(FakeScheduler):
        async def run_conversation_turn(self, session_id, teacher_message, role="interact"):
            self._interact_sessions[session_id] = SimpleNamespace(
                status="reviewing", scenario="unknown", turn_count=2,
            )
            return {"response_text": "ok", "files_written": []}

    service = InteractV2Service()
    service._get_scheduler = lambda provider, thinking: _NoopScheduler(tmp_path)
    session = service.create_session()
    compose_dir = tmp_path / session.session_id / "compose"
    compose_dir.mkdir(parents=True, exist_ok=True)
    (compose_dir / "paper_request.yaml").write_text(
        yaml.dump({"schema_version": "paper_request_v1", "slots": slots}),
        encoding="utf-8",
    )
    return service, session, compose_dir


_COMPLETE_SLOT = {
    "slot_id": "Q1", "question_type": "single_choice",
    "primary_target_name": "AVL旋转", "target_difficulty": 3,
    "examination_mode": "计算型",
}


def test_confirm_gate_quarantines_yaml_without_explicit_confirm(tmp_path):
    """handoff YAML present but intent=discuss → quarantined, not triggered."""
    service, session, compose_dir = _make_service_with_handoff(tmp_path, [_COMPLETE_SLOT])
    result = run_async(service.send_turn(session.session_id, "再讨论一下", intent="discuss"))
    assert result.has_result is False
    assert result.session_state != "confirmed"
    # YAML should have been quarantined (renamed .blocked.*)
    assert not (compose_dir / "paper_request.yaml").exists()
    assert list(compose_dir.glob("paper_request.yaml.blocked.*"))


def test_confirm_gate_triggers_on_explicit_confirm_with_complete_yaml(tmp_path):
    """intent=confirm_handoff + complete fields → pipeline triggered."""
    service, session, compose_dir = _make_service_with_handoff(tmp_path, [_COMPLETE_SLOT])
    with unittest.mock.patch.object(service, "_trigger_generation") as mock_trig:
        result = run_async(service.send_turn(session.session_id, "确认出题", intent="confirm_handoff"))
    assert result.session_state == "confirmed"
    assert mock_trig.called


def test_confirm_gate_rejects_incomplete_yaml(tmp_path):
    """intent=confirm_handoff but missing required fields → not triggered."""
    incomplete = [{"slot_id": "Q1"}]  # missing question_type/difficulty/etc.
    service, session, compose_dir = _make_service_with_handoff(tmp_path, incomplete)
    with unittest.mock.patch.object(service, "_trigger_generation") as mock_trig:
        result = run_async(service.send_turn(session.session_id, "确认出题", intent="confirm_handoff"))
    assert result.session_state == "reviewing"
    assert not mock_trig.called
