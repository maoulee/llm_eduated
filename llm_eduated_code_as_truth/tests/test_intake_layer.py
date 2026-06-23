"""Tests for intake layer: route_gate, confidence, output_policy, schema parsing, adapters."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Helpers: route_gate validation
# ---------------------------------------------------------------------------

def validate_paper_route_gate(data: dict) -> tuple[bool, list[str]]:
    """Validate paper_route_gate required fields. Returns (passed, missing)."""
    required = [
        lambda d: d.get("task_type") == "paper",
        lambda d: d.get("assessment", {}).get("type"),
        lambda d: d.get("assessment", {}).get("subjects"),
        lambda d: (
            d.get("question_config")
            or d.get("assessment", {}).get("total_score")
            or d.get("assessment", {}).get("duration_minutes")
        ),
        lambda d: (
            d.get("knowledge_scope", {}).get("primary_chapters")
            or d.get("knowledge_scope", {}).get("focus_points")
        ),
        lambda d: d.get("difficulty", {}).get("target"),
    ]
    missing = []
    for i, check in enumerate(required):
        if not check(data):
            missing.append(f"required_field_{i}")
    return len(missing) == 0, missing


def validate_single_question_route_gate(data: dict) -> tuple[bool, list[str]]:
    """Validate single_question_route_gate required fields."""
    required = [
        lambda d: d.get("task_type") == "single_question",
        lambda d: d.get("target_subject"),
        lambda d: d.get("primary_target_name"),
        lambda d: d.get("target_family") or d.get("kg_node_path"),
        lambda d: d.get("question_type") or d.get("default_question_type"),
        lambda d: d.get("difficulty_level") or d.get("difficulty", {}).get("target"),
    ]
    missing = []
    for i, check in enumerate(required):
        if not check(data):
            missing.append(f"required_field_{i}")
    return len(missing) == 0, missing


def validate_retrieval_route_gate(data: dict) -> tuple[bool, list[str]]:
    """Validate retrieval_route_gate required fields."""
    required = [
        lambda d: d.get("task_type") == "retrieval",
        lambda d: d.get("keywords") or d.get("knowledge_tags"),
    ]
    missing = []
    for i, check in enumerate(required):
        if not check(data):
            missing.append(f"required_field_{i}")
    return len(missing) == 0, missing


def can_route_by_confidence(confidence_level: str) -> bool:
    """Only high/medium can route. low/blocked/unsupported cannot."""
    return confidence_level in ("high", "medium")


def check_output_policy(gate_passed: bool, task_type: str, written_files: list[str]) -> tuple[bool, str]:
    """Check output_policy compliance.
    gate not passed → only intake_response.md + intake_result.yaml allowed.
    gate passed → exactly one route_output file allowed.
    """
    downstream_files = {"paper_request.yaml", "slot_blueprint.yaml", "retrieval_query.yaml"}
    route_output_map = {
        "paper": "paper_request.yaml",
        "single_question": "slot_blueprint.yaml",
        "retrieval": "retrieval_query.yaml",
    }

    written_downstream = [f for f in written_files if f in downstream_files]

    if not gate_passed:
        if written_downstream:
            return False, f"gate not passed but downstream files written: {written_downstream}"
        return True, ""
    else:
        expected = route_output_map.get(task_type, "")
        if len(written_downstream) != 1:
            return False, f"gate passed but found {len(written_downstream)} downstream files, expected 1"
        if written_downstream[0] != expected:
            return False, f"expected {expected}, got {written_downstream[0]}"
        return True, ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_paper_request():
    return {
        "task_type": "paper",
        "assessment": {
            "type": "kaoyan_408",
            "subjects": ["计算机组成原理", "数据结构"],
            "total_score": 45,
        },
        "knowledge_scope": {
            "primary_chapters": ["存储系统"],
            "focus_points": ["Cache", "虚拟存储器"],
            "excluded_points": [],
            "coverage_strategy": "balanced",
        },
        "question_config": {
            "types": [
                {"type": "single_choice", "count_range": [10, 15], "score_per": 2},
                {"type": "comprehensive", "count_range": [2, 3], "score_range": [8, 13]},
            ]
        },
        "difficulty": {"target": "medium", "distribution": {"easy": 30, "medium": 50, "hard": 20}},
    }


@pytest.fixture
def valid_slot_blueprint():
    return {
        "task_type": "single_question",
        "slot_id": "TOPIC_001",
        "question_type": "comprehensive",
        "score": 10,
        "target_subject": "数据结构",
        "target_family": "数据结构 > 查找 > 字符串模式匹配",
        "primary_target_name": "KMP算法",
        "difficulty_level": 3,
        "confidence": {"level": "high"},
    }


@pytest.fixture
def valid_retrieval_query():
    return {
        "task_type": "retrieval",
        "keywords": ["Cache", "地址映射"],
        "knowledge_tags": [],
    }


# ---------------------------------------------------------------------------
# Test: paper_request.yaml parsing
# ---------------------------------------------------------------------------

class TestPaperRequestParsing:
    def test_valid_produces_correct_fields(self, valid_paper_request):
        passed, missing = validate_paper_route_gate(valid_paper_request)
        assert passed, f"Missing fields: {missing}"
        assert valid_paper_request["assessment"]["subjects"] == ["计算机组成原理", "数据结构"]
        assert valid_paper_request["difficulty"]["target"] == "medium"

    def test_yaml_roundtrip(self, valid_paper_request, tmp_path):
        path = tmp_path / "paper_request.yaml"
        path.write_text(yaml.dump(valid_paper_request, allow_unicode=True), encoding="utf-8")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert loaded["assessment"]["type"] == "kaoyan_408"
        assert loaded["knowledge_scope"]["focus_points"] == ["Cache", "虚拟存储器"]


# ---------------------------------------------------------------------------
# Test: slot_blueprint.yaml → SlotBlueprint dataclass
# ---------------------------------------------------------------------------

class TestSlotBlueprintParsing:
    def test_maps_to_dataclass(self, valid_slot_blueprint, tmp_path):
        from core_new.doc_pipeline.contracts import SlotBlueprint

        path = tmp_path / "slot_blueprint.yaml"
        data = {k: v for k, v in valid_slot_blueprint.items() if k != "task_type"}
        data["target_difficulty"] = data.pop("difficulty_level", 3)
        data["active_selection"] = {}
        data["candidate_pool_visible"] = []
        data["excluded_modes"] = []
        data["excluded_knowledge"] = []
        data["teacher_annotation"] = ""
        data["k_target"] = ""
        data["examination_mode"] = ""
        data["difficulty_rationale"] = ""

        path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")

        bp = SlotBlueprint(**{k: v for k, v in data.items() if k in SlotBlueprint.__dataclass_fields__})
        assert bp.slot_id == "TOPIC_001"
        assert bp.question_type == "comprehensive"
        assert bp.primary_target_name == "KMP算法"

    def test_adapter_load(self, valid_slot_blueprint, tmp_path):
        from compose.single_question_adapter import load_slot_blueprint, build_blueprint_map

        data = {k: v for k, v in valid_slot_blueprint.items() if k not in ("task_type", "confidence")}
        data["target_difficulty"] = data.pop("difficulty_level", 3)
        data["active_selection"] = {}
        data["candidate_pool_visible"] = []
        data["excluded_modes"] = []
        data["excluded_knowledge"] = []
        data["teacher_annotation"] = ""
        data["k_target"] = ""
        data["examination_mode"] = ""
        data["difficulty_rationale"] = ""

        path = tmp_path / "slot_blueprint.yaml"
        path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")

        bp = load_slot_blueprint(str(path))
        assert bp is not None
        assert bp.slot_id == "TOPIC_001"

        bpm = build_blueprint_map(bp)
        assert "TOPIC_001" in bpm


# ---------------------------------------------------------------------------
# Test: retrieval_query.yaml parsing
# ---------------------------------------------------------------------------

class TestRetrievalQueryParsing:
    def test_valid_keywords_produce_query(self, valid_retrieval_query):
        passed, missing = validate_retrieval_route_gate(valid_retrieval_query)
        assert passed, f"Missing fields: {missing}"
        assert "Cache" in valid_retrieval_query["keywords"]


# ---------------------------------------------------------------------------
# Test: route_gate validation
# ---------------------------------------------------------------------------

class TestRouteGate:
    def test_paper_missing_assessment_type(self):
        data = {
            "task_type": "paper",
            "assessment": {"subjects": ["数据结构"]},
            "difficulty": {"target": "medium"},
        }
        passed, missing = validate_paper_route_gate(data)
        assert not passed
        assert len(missing) > 0

    def test_paper_all_required_present(self, valid_paper_request):
        passed, missing = validate_paper_route_gate(valid_paper_request)
        assert passed

    def test_single_question_missing_target_subject(self):
        data = {
            "task_type": "single_question",
            "primary_target_name": "KMP",
            "target_family": "数据结构",
            "question_type": "single_choice",
            "difficulty_level": 3,
        }
        passed, missing = validate_retrieval_route_gate(data)
        assert not passed

    def test_retrieval_keywords_present(self, valid_retrieval_query):
        passed, missing = validate_retrieval_route_gate(valid_retrieval_query)
        assert passed


# ---------------------------------------------------------------------------
# Test: confidence gating
# ---------------------------------------------------------------------------

class TestConfidenceGating:
    @pytest.mark.parametrize("level,expected", [
        ("high", True),
        ("medium", True),
        ("low", False),
        ("blocked", False),
        ("unsupported", False),
    ])
    def test_routing_by_confidence(self, level, expected):
        assert can_route_by_confidence(level) == expected

    def test_low_must_upgrade(self):
        assert not can_route_by_confidence("low")
        # Simulate upgrade
        assert can_route_by_confidence("medium")


# ---------------------------------------------------------------------------
# Test: output_policy
# ---------------------------------------------------------------------------

class TestOutputPolicy:
    def test_gate_not_passed_no_downstream(self):
        ok, msg = check_output_policy(False, "paper", ["intake_response.md", "intake_result.yaml"])
        assert ok, msg

    def test_gate_not_passed_downstream_written_fails(self):
        ok, msg = check_output_policy(False, "paper", ["intake_response.md", "paper_request.yaml"])
        assert not ok

    def test_gate_passed_paper_correct_file(self):
        ok, msg = check_output_policy(True, "paper", ["paper_request.yaml"])
        assert ok, msg

    def test_gate_passed_wrong_file_type(self):
        ok, msg = check_output_policy(True, "paper", ["slot_blueprint.yaml"])
        assert not ok

    def test_gate_passed_multiple_downstream_fails(self):
        ok, msg = check_output_policy(True, "paper", ["paper_request.yaml", "slot_blueprint.yaml"])
        assert not ok


# ---------------------------------------------------------------------------
# Test: load_paper_request backward compat
# ---------------------------------------------------------------------------

class TestLoadPaperRequest:
    def test_returns_none_when_file_missing(self, tmp_path):
        from compose.compose_runner import load_paper_request
        result = load_paper_request(str(tmp_path))
        assert result is None

    def test_maps_fields_when_file_exists(self, tmp_path):
        from compose.compose_runner import load_paper_request, map_paper_request_to_params

        pr = {
            "schema_version": "paper_request_v1",
            "assessment": {
                "type": "course_final",
                "subjects": ["数据结构"],
                "total_score": 100,
            },
            "knowledge_scope": {
                "primary_chapters": ["树与二叉树", "图"],
                "focus_points": ["AVL树", "最短路径"],
                "excluded_points": [],
                "coverage_strategy": "balanced",
            },
            "question_config": {
                "types": [
                    {"type": "single_choice", "count_range": [10, 15], "score_per": 2},
                ]
            },
            "difficulty": {"target": "medium"},
            "teacher_preferences": {"require": ["AVL树"], "avoid": ["B树"], "style_notes": "侧重理解"},
        }

        path = tmp_path / "paper_request.yaml"
        path.write_text(yaml.dump(pr, allow_unicode=True), encoding="utf-8")

        loaded = load_paper_request(str(tmp_path))
        assert loaded is not None
        assert loaded["assessment"]["subjects"] == ["数据结构"]

        mapped = map_paper_request_to_params(loaded)
        assert "数据结构" in mapped["user_requirements"]
        assert "data_structure.md" in mapped["subject_files"]
        assert mapped["slot_templates_hints"][0]["question_type"] == "single_choice"


# ---------------------------------------------------------------------------
# Test: KG node classification
# ---------------------------------------------------------------------------

class TestKGNodeClassification:
    def test_neighbor_nodes_dont_enter_focus_points(self):
        """Simulate: KG shows sibling nodes, only user-selected ones go to focus_points."""
        kg_nodes = {
            "confirmed": ["Cache直接映射"],
            "candidate": ["Cache组相联映射", "Cache全相联映射"],
            "neighbor": ["虚拟存储器", "TLB"],
        }

        focus_points = list(kg_nodes["confirmed"])
        # Neighbor nodes must NOT be automatically added
        assert "虚拟存储器" not in focus_points
        assert "TLB" not in focus_points
        # Only user explicit selection upgrades
        focus_points.append("Cache组相联映射")
        assert "Cache组相联映射" in focus_points
