"""Unit tests for the interaction layer — session FSM, approval, compose, disambiguation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from interact.session_manager import (
    SessionManager,
    SessionState,
    SessionData,
    _APPROVAL_PATTERNS,
)
from interact.intent_router import IntentResult
from interact.blueprint_synthesizer import SynthesisResult


# ── Fakes ──────────────────────────────────────────────────────


class FakeIntentRouter:
    def __init__(self):
        self._next_result: IntentResult | None = None

    def set_result(self, result: IntentResult):
        self._next_result = result

    async def route(self, message: str, context=None) -> IntentResult:
        if self._next_result:
            return self._next_result
        return IntentResult(intent="clarify", response="请再描述")


class FakeKnowledgeRetriever:
    def __init__(self):
        self._resolved_tag: str | None = None
        self._search_results: list[str] = []

    def set_resolved_tag(self, tag):
        self._resolved_tag = tag

    def set_search_results(self, results):
        self._search_results = results

    def resolve_knowledge_tag(self, query):
        return self._resolved_tag

    def search(self, query):
        return self._search_results

    def retrieve_knowledge_subtree(self, tag):
        return f"[KG subtree for {tag}]"

    def retrieve_question_experiences(self, tag, max_count=15):
        return []

    def retrieve_knowledge_profile(self, tag):
        return ""

    def compute_statistics(self, tag):
        return MagicMock(
            question_count=0,
            k_distributions={},
            mode_frequencies={},
            slot_distribution={},
        )


class FakeBlueprintSynthesizer:
    def __init__(self):
        self.call_count = 0
        self.last_request = None

    async def synthesize(self, request):
        self.call_count += 1
        self.last_request = request
        return SynthesisResult(
            assembled_md="# test blueprint\n## 本次出题要求\n- **考点**: 测试",
            blueprint_id="bp-test-1234",
            sections_injected=[],
            sections_generated=[],
        )


def _make_manager():
    router = FakeIntentRouter()
    retriever = FakeKnowledgeRetriever()
    synthesizer = FakeBlueprintSynthesizer()
    sm = SessionManager(router, retriever, synthesizer)
    return sm, router, retriever, synthesizer


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Approval regex ──────────────────────────────────────────────


class TestApprovalRegex:
    """Verify approval patterns accept/reject correctly."""

    @pytest.mark.parametrize("text", [
        "确认", "没问题", "好的", "ok", "OK",
        "批准", "通过", "approve", "就这样", "同意",
        "可以", "行",
    ])
    def test_positive(self, text):
        assert _APPROVAL_PATTERNS.search(text), f"Should match: {text!r}"

    @pytest.mark.parametrize("text", [
        "不可以", "不行", "这样可以吗", "行的吗",
        "可以吗", "可以的吗",
    ])
    def test_negative(self, text):
        assert not _APPROVAL_PATTERNS.search(text), f"Should NOT match: {text!r}"


# ── State machine transitions ──────────────────────────────────


class TestFSMTransitions:
    """Test session state transitions end-to-end."""

    def test_idle_to_collecting_on_missing_params(self):
        sm, router, _, _ = _make_manager()
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={"knowledge_topic": "TCP拥塞控制"},
            missing_params=["question_count", "difficulty"],
        ))
        resp = run(sm.handle_message("s1", "出几道TCP的题"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.COLLECTING
        assert session.mode == "knowledge_point"

    def test_idle_to_blueprint_ready_on_complete_knowledge_point(self):
        sm, router, retriever, _ = _make_manager()
        retriever.set_resolved_tag("CN-5 > TCP协议 > TCP拥塞控制")
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={
                "knowledge_topic": "TCP拥塞控制",
                "subject": "计算机网络",
                "question_count": 3,
                "question_type": "选择题",
                "difficulty": "medium",
            },
        ))
        resp = run(sm.handle_message("s1", "出3道TCP选择题"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.BLUEPRINT_READY
        assert session.mode == "knowledge_point"

    def test_blueprint_ready_to_approved_on_confirm(self):
        sm, router, retriever, _ = _make_manager()
        retriever.set_resolved_tag("DS-3 > 二叉树")
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={"knowledge_topic": "二叉树", "question_count": 1},
        ))
        run(sm.handle_message("s1", "出1道二叉树题"))
        assert sm.get_or_create("s1").state == SessionState.BLUEPRINT_READY

        resp = run(sm.handle_message("s1", "确认"))
        assert sm.get_or_create("s1").state == SessionState.APPROVED

    def test_blueprint_ready_to_annotating_on_feedback(self):
        sm, router, retriever, synth = _make_manager()
        retriever.set_resolved_tag("DS-3 > 二叉树")
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={"knowledge_topic": "二叉树", "question_count": 1},
        ))
        run(sm.handle_message("s1", "出1道二叉树题"))

        resp = run(sm.handle_message("s1", "难度应该更高一些"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.BLUEPRINT_READY
        assert session.annotation_round == 1

    def test_annotating_max_rounds_auto_approves(self):
        sm, router, retriever, synth = _make_manager()
        retriever.set_resolved_tag("DS-3 > 二叉树")
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={"knowledge_topic": "二叉树", "question_count": 1},
        ))
        run(sm.handle_message("s1", "出1道二叉树题"))

        for i in range(3):
            resp = run(sm.handle_message("s1", f"修改意见{i+1}"))

        session = sm.get_or_create("s1")
        assert session.state == SessionState.APPROVED

    def test_error_state_allows_restart(self):
        sm, router, _, _ = _make_manager()
        session = sm.get_or_create("s1")
        session.state = SessionState.ERROR
        session.error_message = "test error"

        router.set_result(IntentResult(
            intent="knowledge_point",
            params={"knowledge_topic": "测试", "question_count": 1},
            missing_params=["difficulty"],
        ))
        resp = run(sm.handle_message("s1", "再来一次"))
        # Should have created new session (or reset) and entered collecting
        new_session = sm.get_or_create("s1")
        assert new_session.state == SessionState.COLLECTING


# ── Compose mode ────────────────────────────────────────────────


class TestComposeMode:
    """Verify compose mode doesn't enter blueprint synthesis."""

    def test_compose_complete_sets_blueprint_ready(self):
        sm, router, _, synth = _make_manager()
        router.set_result(IntentResult(
            intent="compose",
            params={
                "subject": "数据结构",
                "difficulty": "medium",
                "question_count": 7,
                "question_types": ["选择题", "综合应用题"],
            },
        ))
        resp = run(sm.handle_message("s1", "出一张数据结构试卷"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.BLUEPRINT_READY
        assert session.mode == "compose"
        assert synth.call_count == 0  # synthesizer NOT called for compose

    def test_compose_collecting_then_complete_no_synthesis(self):
        sm, router, _, synth = _make_manager()
        # First turn: partial compose
        router.set_result(IntentResult(
            intent="compose",
            params={"subject": "CO"},
            missing_params=["difficulty", "question_count"],
        ))
        run(sm.handle_message("s1", "出一张CO试卷"))
        assert sm.get_or_create("s1").state == SessionState.COLLECTING

        # Second turn: complete
        router.set_result(IntentResult(
            intent="compose",
            params={
                "subject": "CO",
                "difficulty": "hard",
                "question_count": 5,
                "question_types": ["选择题"],
            },
        ))
        resp = run(sm.handle_message("s1", "5道选择题，困难难度"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.BLUEPRINT_READY
        assert synth.call_count == 0


# ── Knowledge tag disambiguation ────────────────────────────────


class TestDisambiguation:
    """Verify ambiguous knowledge tags trigger clarification."""

    def test_ambiguous_tag_returns_candidates(self):
        sm, router, retriever, synth = _make_manager()
        retriever.set_resolved_tag(None)  # resolve returns None (ambiguous)
        retriever.set_search_results([
            "CO-4 > Cache > 映射方式",
            "CO-4 > Cache > 替换算法",
            "CO-4 > Cache > 写策略",
        ])
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={
                "knowledge_topic": "Cache",
                "subject": "CO",
                "question_count": 2,
                "difficulty": "medium",
            },
        ))
        resp = run(sm.handle_message("s1", "出2道Cache题"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.COLLECTING
        assert "多个知识点" in resp
        assert synth.call_count == 0

    def test_single_search_result_used_directly(self):
        sm, router, retriever, synth = _make_manager()
        retriever.set_resolved_tag(None)
        retriever.set_search_results(["CO-4 > Cache > 映射方式"])
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={
                "knowledge_topic": "Cache映射",
                "question_count": 1,
                "difficulty": "easy",
            },
        ))
        resp = run(sm.handle_message("s1", "出1道Cache映射题"))
        session = sm.get_or_create("s1")
        assert session.state == SessionState.BLUEPRINT_READY
        assert synth.call_count == 1


# ── Difficulty passthrough ──────────────────────────────────────


class TestDifficultyPassthrough:
    """Verify difficulty reaches SynthesisRequest."""

    def test_difficulty_passed_to_synthesizer(self):
        sm, router, retriever, synth = _make_manager()
        retriever.set_resolved_tag("DS-3 > 二叉树 > 遍历")
        router.set_result(IntentResult(
            intent="knowledge_point",
            params={
                "knowledge_topic": "二叉树遍历",
                "question_count": 2,
                "difficulty": "hard",
                "question_type": "选择题",
            },
        ))
        run(sm.handle_message("s1", "出2道二叉树遍历选择题，困难"))
        assert synth.last_request is not None
        assert synth.last_request.difficulty == "hard"
