"""Tests for core_new.agents.unified_pipeline — _is_single_choice routing logic."""

import pytest

from core_new.agents.unified_pipeline import UnifiedQuestionPipeline


class TestIsSingleChoice:
    """Tests for UnifiedQuestionPipeline._is_single_choice().

    After the executor's fix (Task #1), the method requires an explicit
    question_type and raises ValueError if it's missing or unknown.
    """

    def test_explicit_single_choice(self):
        bp = {"question_type": "single_choice"}
        assert UnifiedQuestionPipeline._is_single_choice(bp) is True

    def test_explicit_comprehensive(self):
        bp = {"question_type": "comprehensive"}
        assert UnifiedQuestionPipeline._is_single_choice(bp) is False

    def test_question_type_takes_priority_over_slot(self):
        bp = {"question_type": "single_choice", "slot_id": "Q43"}
        assert UnifiedQuestionPipeline._is_single_choice(bp) is True

    def test_question_type_comprehensive_with_low_slot(self):
        bp = {"question_type": "comprehensive", "slot_id": "Q01"}
        assert UnifiedQuestionPipeline._is_single_choice(bp) is False

    # -- Missing/invalid question_type raises ValueError --

    def test_no_type_raises_value_error(self):
        bp = {}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_empty_question_type_raises_value_error(self):
        bp = {"question_type": "", "slot_id": "Q43"}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_unknown_question_type_raises_value_error(self):
        bp = {"question_type": "unknown_type", "slot_id": "Q01"}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_no_type_with_slot_raises_value_error(self):
        bp = {"slot_id": "Q50"}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_no_type_non_numeric_slot_raises_value_error(self):
        bp = {"slot_id": "QXX"}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_no_type_slot_without_q_prefix_raises_value_error(self):
        bp = {"slot_id": "01"}
        with pytest.raises(ValueError, match="question_type"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_error_message_includes_slot_id(self):
        bp = {"slot_id": "Q99"}
        with pytest.raises(ValueError, match="Q99"):
            UnifiedQuestionPipeline._is_single_choice(bp)

    def test_error_message_includes_got_type(self):
        bp = {"question_type": "essay"}
        with pytest.raises(ValueError, match="'essay'"):
            UnifiedQuestionPipeline._is_single_choice(bp)
