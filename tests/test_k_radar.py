"""Tests for K-radar 5D cognitive dimension system.

Validates:
  - k_radar_reader data extraction (slot experience cards, question aggregation, heuristic fallback)
  - resolve_k_radar priority chain
  - compute_k_dominant
  - single_question_adapter backward compat (k_target → k_dominant)
  - outline_yaml_generator k_radar output
  - artifact_store k_radar rendering
"""

from __future__ import annotations

import textwrap

import pytest

from compose.k_radar_reader import (
    aggregate_question_k_radar,
    compute_k_dominant,
    estimate_k_radar_heuristic,
    read_question_k_radar,
    read_slot_k_radar,
    resolve_k_radar,
)


# ── 1. Slot experience card reader ──────────────────────────────


class TestReadSlotKRadar:
    """Test reading K-radar from slot experience card K值锚点."""

    def test_q14_experience_card(self):
        """Q14 has real experience card with known K values."""
        k_radar = read_slot_k_radar("Q14")
        assert k_radar == {"K1": 3, "K2": 3, "K3": 2, "K4": 4, "K5": 1}

    def test_q17_experience_card(self):
        """Q17 has real experience card — should be K1 dominant."""
        k_radar = read_slot_k_radar("Q17")
        assert k_radar  # non-empty
        assert "K1" in k_radar
        assert compute_k_dominant(k_radar) == "K1"

    def test_nonexistent_slot(self):
        """Missing slot returns empty dict."""
        k_radar = read_slot_k_radar("NONEXISTENT_999")
        assert k_radar == {}


# ── 2. Question experience aggregation ──────────────────────────


class TestAggregateQuestionKRadar:
    """Test aggregating K values across multiple question experience files."""

    def test_project_relative_path_independent_of_cwd(self, monkeypatch, tmp_path):
        """Agent-provided data/... paths should work outside the repo cwd."""
        monkeypatch.chdir(tmp_path)

        k_radar = read_question_k_radar("data/question_experiences/2009_Q5.md")

        assert k_radar == {"K1": 3, "K2": 3, "K3": 3, "K4": 4, "K5": 1}

    def test_empty_list(self):
        """Empty file list returns empty dict."""
        assert aggregate_question_k_radar([]) == {}

    def test_nonexistent_file(self):
        """Non-existent file returns empty dict."""
        assert aggregate_question_k_radar(["nonexistent_file_999.md"]) == {}


# ── 3. Heuristic fallback ──────────────────────────────────────


class TestEstimateKRadarHeuristic:
    """Test keyword-based heuristic K-radar estimation."""

    def test_conceptual_keywords(self):
        """Conceptual keywords → K1 should be high."""
        k = estimate_k_radar_heuristic("概念辨析", "")
        assert k["K1"] >= 3

    def test_formula_keywords(self):
        """Formula keywords → K2 should be high."""
        k = estimate_k_radar_heuristic("公式代入", "")
        assert k["K2"] >= 3

    def test_multi_step_keywords(self):
        """Multi-step keywords → K3 should be high."""
        k = estimate_k_radar_heuristic("多步推演", "")
        assert k["K3"] >= 3

    def test_trap_keywords(self):
        """Trap/combination keywords → K4 should be high."""
        k = estimate_k_radar_heuristic("陷阱", "")
        assert k["K4"] >= 3

    def test_design_keywords(self):
        """Design/open-ended keywords → K5 should be high."""
        k = estimate_k_radar_heuristic("综合运用", "")
        assert k["K5"] >= 3

    def test_unknown_returns_default(self):
        """Unknown mode returns default radar (all dimensions present)."""
        k = estimate_k_radar_heuristic("未知模式", "")
        assert set(k.keys()) == {"K1", "K2", "K3", "K4", "K5"}

    def test_all_dimensions_present(self):
        """Every heuristic result has K1-K5."""
        k = estimate_k_radar_heuristic("测试", "")
        for dim in ("K1", "K2", "K3", "K4", "K5"):
            assert dim in k


# ── 4. resolve_k_radar priority ─────────────────────────────────


class TestResolveKRadar:
    """Test unified K-radar resolution with priority chain."""

    def test_experience_card_priority(self):
        """Q14 has experience card → source='experience_card'."""
        k_radar, source = resolve_k_radar(slot_id="Q14")
        assert source == "experience_card"
        assert k_radar["K4"] == 4  # Q14 is K4 dominant

    def test_heuristic_fallback(self):
        """No slot_id, no files → heuristic fallback."""
        k_radar, source = resolve_k_radar(examination_mode="概念辨析")
        assert source == "heuristic"
        assert k_radar["K1"] >= 3

    def test_question_aggregate_priority(self):
        """No slot_id, has files → question_aggregate if data exists."""
        k_radar, source = resolve_k_radar(question_files=["nonexistent_999.md"])
        # Files don't exist → falls through to heuristic
        assert source == "heuristic"


# ── 5. compute_k_dominant ──────────────────────────────────────


class TestComputeKDominant:
    """Test dominant K dimension extraction."""

    def test_clear_winner(self):
        assert compute_k_dominant({"K1": 1, "K2": 1, "K3": 1, "K4": 5, "K5": 1}) == "K4"

    def test_tie_returns_first(self):
        """Tie → returns first in K1-K5 order."""
        assert compute_k_dominant({"K1": 3, "K2": 3, "K3": 3, "K4": 3, "K5": 3}) == "K1"

    def test_empty_returns_default(self):
        assert compute_k_dominant({}) == "K3"

    def test_partial_radar(self):
        """Partial radar still works."""
        assert compute_k_dominant({"K2": 5}) == "K2"

    def test_tie_uses_k_dimension_order_not_dict_insertion(self):
        """Tie → returns K1 even when the input dict starts with K4."""
        assert compute_k_dominant({"K4": 3, "K2": 3, "K1": 3}) == "K1"


# ── 6. single_question_adapter backward compat ─────────────────


class TestSingleQuestionAdapterCompat:
    """Test that k_target is correctly aliased to k_dominant."""

    def test_k_target_to_k_dominant(self):
        from compose.single_question_adapter import normalize_slot_blueprint_data

        data = {"slot_id": "TEST", "k_target": "K3"}
        result = normalize_slot_blueprint_data(data)
        assert result.get("k_dominant") == "K3"
        assert "k_target" not in result

    def test_k_dominant_takes_priority(self):
        from compose.single_question_adapter import normalize_slot_blueprint_data

        data = {"slot_id": "TEST", "k_target": "K2", "k_dominant": "K4"}
        result = normalize_slot_blueprint_data(data)
        assert result.get("k_dominant") == "K4"
        assert "k_target" not in result

    def test_k_radar_passthrough(self):
        from compose.single_question_adapter import normalize_slot_blueprint_data

        radar = {"K1": 1, "K2": 2, "K3": 4, "K4": 2, "K5": 1}
        data = {"slot_id": "TEST", "k_radar": radar}
        result = normalize_slot_blueprint_data(data)
        assert result["k_radar"] == radar


# ── 7. outline_yaml_generator k_radar output ────────────────────


class TestOutlineYamlGenerator:
    """Test that outline_yaml_generator outputs k_radar YAML."""

    def test_k_radar_in_output(self):
        from compose.outline_yaml_generator import _build_yaml_lines

        slot_data = {
            "slot_id": "Q1",
            "target_subject": "计组",
            "target_family": "计组 > 存储系统",
            "primary_target_name": "Cache映射",
            "target_difficulty": 3,
            "k_radar": {"K1": 2, "K2": 4, "K3": 1, "K4": 3, "K5": 1},
            "k_dominant": "K2",
            "k_source": "experience_card",
        }
        lines = _build_yaml_lines(slot_data, {}, "Q1")
        output = "".join(lines)
        assert "k_radar:" in output
        assert "K2: 4" in output
        assert 'k_dominant: "K2"' in output
        assert 'k_source: "experience_card"' in output

    def test_k_radar_output_order_is_stable(self):
        """K-radar YAML always emits known dimensions in K1-K5 order."""
        from compose.outline_yaml_generator import _build_yaml_lines

        slot_data = {
            "slot_id": "Q1",
            "k_radar": {"K4": 4, "K2": 2, "K1": 1},
        }

        output = "".join(_build_yaml_lines(slot_data, {}, "Q1"))

        assert "k_radar:\n  K1: 1\n  K2: 2\n  K4: 4\n" in output

    def test_fallback_to_k_target(self):
        """Old data with only k_target should still produce k_dominant."""
        from compose.outline_yaml_generator import _build_yaml_lines

        slot_data = {
            "slot_id": "Q1",
            "k_target": "K3",
        }
        lines = _build_yaml_lines(slot_data, {}, "Q1")
        output = "".join(lines)
        assert 'k_dominant: "K3"' in output
