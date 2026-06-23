"""Simulation tests for intake layer: 3 teacher interaction scenarios.

Validates intake behavior without LLM calls — directly exercises
validation, confidence gating, output policy, and compose_runner integration.

Scenario A: Info sufficient -> direct route to compose_runner
Scenario B: Info insufficient -> follow-up, no downstream files
Scenario C: Out of scope -> reject, frontdesk_only
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_intake_layer import (
    validate_paper_route_gate,
    can_route_by_confidence,
    check_output_policy,
)
from compose.compose_runner import load_paper_request, map_paper_request_to_params


# ---------------------------------------------------------------------------
# Intent recognition helper (simulated, rule-based)
# ---------------------------------------------------------------------------

def recognize_intent(text: str) -> str:
    """Simulate keyword-based intent recognition."""
    rules = [
        ("paper", ["一套", "试卷", "期末卷", "模拟卷"]),
        ("single_question", ["出一道", "生成", "设计", "原创"]),
        ("retrieval", ["找题", "推荐", "有没有", "帮我找"]),
    ]
    for intent, keywords in rules:
        for kw in keywords:
            if kw in text:
                return intent
    return "unknown"


# ---------------------------------------------------------------------------
# KG scope check helper (simulated)
# ---------------------------------------------------------------------------

SUPPORTED_SUBJECTS = {
    "计算机组成原理", "数据结构", "操作系统", "计算机网络",
}

SUPPORTED_TOPICS = {
    "Cache", "虚拟存储器", "KMP算法", "AVL树", "最短路径",
    "进程调度", "内存管理", "路由算法", "可靠传输",
    "存储系统", "树与二叉树", "图", "查找", "排序",
    "字符串模式匹配", "浮点数", "指令流水线",
}


def kg_scope_check(topic: str) -> bool:
    """Check if a topic is within the KG coverage."""
    # Check if topic or any sub-part is in supported topics
    for supported in SUPPORTED_TOPICS | SUPPORTED_SUBJECTS:
        if supported in topic or topic in supported:
            return True
    return False


# ---------------------------------------------------------------------------
# Scenario A: Info sufficient -> direct route
# ---------------------------------------------------------------------------

class TestScenarioA_InfoSufficient:
    """Input: '组一套数据结构期末卷，100分，120分钟，全书，中等难度'

    Expected: route_gate passes, confidence=high, paper_request.yaml written
    and loadable by compose_runner.
    """

    def test_intent_recognized_as_paper(self):
        text = "组一套数据结构期末卷，100分，120分钟，全书，中等难度"
        intent = recognize_intent(text)
        assert intent == "paper", f"Expected 'paper', got '{intent}'"

    def test_route_gate_passes(self):
        paper_request = {
            "task_type": "paper",
            "assessment": {
                "type": "course_final",
                "subjects": ["数据结构"],
                "total_score": 100,
                "duration_minutes": 120,
            },
            "knowledge_scope": {
                "primary_chapters": ["全书"],
                "focus_points": [],
                "excluded_points": [],
                "coverage_strategy": "balanced",
            },
            "question_config": {
                "types": [
                    {"type": "single_choice", "count_range": [15, 20], "score_per": 2},
                    {"type": "comprehensive", "count_range": [4, 6], "score_range": [8, 15]},
                ]
            },
            "difficulty": {
                "target": "medium",
                "distribution": {"easy": 30, "medium": 50, "hard": 20},
            },
        }
        passed, missing = validate_paper_route_gate(paper_request)
        assert passed, f"Route gate should pass, missing: {missing}"

    def test_confidence_high_can_route(self):
        assert can_route_by_confidence("high") is True

    def test_output_policy_allows_paper_request(self):
        ok, msg = check_output_policy(True, "paper", ["paper_request.yaml"])
        assert ok, f"Output policy should allow paper_request.yaml: {msg}"

    def test_yaml_write_and_compose_runner_roundtrip(self, tmp_path):
        """Write paper_request.yaml, load via compose_runner, verify mapping."""
        paper_request = {
            "schema_version": "paper_request_v1",
            "task_type": "paper",
            "assessment": {
                "type": "course_final",
                "subjects": ["数据结构"],
                "total_score": 100,
                "duration_minutes": 120,
            },
            "knowledge_scope": {
                "primary_chapters": ["树与二叉树", "图", "查找", "排序"],
                "focus_points": ["AVL树", "最短路径"],
                "excluded_points": [],
                "coverage_strategy": "balanced",
            },
            "question_config": {
                "types": [
                    {"type": "single_choice", "count_range": [15, 20], "score_per": 2},
                    {"type": "comprehensive", "count_range": [4, 6], "score_range": [8, 15]},
                ]
            },
            "difficulty": {
                "target": "medium",
                "distribution": {"easy": 30, "medium": 50, "hard": 20},
            },
            "teacher_preferences": {
                "require": [],
                "avoid": [],
                "style_notes": "",
            },
        }

        # Write to tmp_path/compose/ to simulate compose_dir structure
        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()
        yaml_path = compose_dir / "paper_request.yaml"
        yaml_path.write_text(yaml.dump(paper_request, allow_unicode=True), encoding="utf-8")

        # Load via compose_runner
        loaded = load_paper_request(str(compose_dir))
        assert loaded is not None, "load_paper_request should return data"
        assert loaded["assessment"]["subjects"] == ["数据结构"]
        assert loaded["difficulty"]["target"] == "medium"
        assert loaded["knowledge_scope"]["primary_chapters"] == ["树与二叉树", "图", "查找", "排序"]

        # Map to params
        mapped = map_paper_request_to_params(loaded)
        assert "数据结构" in mapped["user_requirements"], \
            f"Expected '数据结构' in user_requirements, got: {mapped['user_requirements']}"
        assert "data_structure.md" in mapped["subject_files"], \
            f"Expected 'data_structure.md' in subject_files, got: {mapped['subject_files']}"
        assert mapped["slot_templates_hints"][0]["question_type"] == "single_choice"
        # medium difficulty should NOT trigger hybrid routing
        assert mapped["model_routing"] == {}, \
            f"Medium difficulty should not set model_routing, got: {mapped['model_routing']}"


# ---------------------------------------------------------------------------
# Scenario B: Info insufficient -> follow-up, no downstream files
# ---------------------------------------------------------------------------

class TestScenarioB_InfoInsufficient:
    """Input: '组一套数据结构期末卷，100分'

    Expected: route_gate fails (missing knowledge_scope, difficulty.target),
    confidence=low, no downstream files written.
    """

    def test_intent_recognized_as_paper(self):
        text = "组一套数据结构期末卷，100分"
        intent = recognize_intent(text)
        assert intent == "paper"

    def test_route_gate_fails_missing_fields(self):
        partial_request = {
            "task_type": "paper",
            "assessment": {
                "type": "course_final",
                "subjects": ["数据结构"],
                "total_score": 100,
            },
            # Missing: knowledge_scope (primary_chapters / focus_points)
            # Missing: difficulty.target
        }
        passed, missing = validate_paper_route_gate(partial_request)
        assert not passed, "Route gate should fail for incomplete request"
        assert len(missing) >= 2, \
            f"Expected at least 2 missing fields, got: {missing}"

    def test_confidence_low_cannot_route(self):
        assert can_route_by_confidence("low") is False

    def test_output_policy_blocks_downstream_when_gate_not_passed(self):
        """Only intake_response.md + intake_result.yaml allowed, no paper_request.yaml."""
        written_files = ["intake_response.md", "intake_result.yaml"]
        ok, msg = check_output_policy(False, "paper", written_files)
        assert ok, f"Policy should allow intake-only files: {msg}"

    def test_output_policy_rejects_downstream_when_gate_not_passed(self):
        """paper_request.yaml must NOT be written when gate fails."""
        written_files = ["intake_response.md", "intake_result.yaml", "paper_request.yaml"]
        ok, msg = check_output_policy(False, "paper", written_files)
        assert not ok, "Policy must reject downstream file when gate not passed"

    def test_no_paper_request_yaml_written(self, tmp_path):
        """Simulate: write only intake files, verify paper_request.yaml absent."""
        intake_dir = tmp_path / "intake_output"
        intake_dir.mkdir()

        # Write only allowed files
        (intake_dir / "intake_response.md").write_text(
            "请补充章节范围和难度倾向", encoding="utf-8"
        )
        intake_result = {
            "intake_status": "needs_user_choice",
            "confidence": {"level": "low", "missing_fields": ["knowledge_scope", "difficulty.target"]},
            "routing": {"can_route": False, "next_action": "ask_user"},
        }
        (intake_dir / "intake_result.yaml").write_text(
            yaml.dump(intake_result, allow_unicode=True), encoding="utf-8"
        )

        # Verify paper_request.yaml does NOT exist
        assert not (intake_dir / "paper_request.yaml").exists(), \
            "paper_request.yaml must NOT be written when gate not passed"

        # Verify no downstream files at all
        downstream = {"paper_request.yaml", "slot_blueprint.yaml", "retrieval_query.yaml"}
        actual_files = set(os.listdir(intake_dir))
        leaked = actual_files & downstream
        assert not leaked, f"No downstream files expected, found: {leaked}"


# ---------------------------------------------------------------------------
# Scenario C: Out of scope -> reject
# ---------------------------------------------------------------------------

class TestScenarioC_OutOfScope:
    """Input: '出一道量子计算题'

    Expected: intent=single_question, KG check fails (unsupported scope),
    confidence=unsupported, intake_status=frontdesk_only, no downstream files.
    """

    def test_intent_recognized_as_single_question(self):
        text = "出一道量子计算题"
        intent = recognize_intent(text)
        assert intent == "single_question", f"Expected 'single_question', got '{intent}'"

    def test_kg_scope_check_fails(self):
        """Quantum computing is not in any KG."""
        assert not kg_scope_check("量子计算"), \
            "量子计算 should not be in KG scope"
        # Sanity: known topics should pass
        assert kg_scope_check("Cache"), "Cache should be in KG scope"
        assert kg_scope_check("KMP算法"), "KMP算法 should be in KG scope"

    def test_confidence_unsupported_cannot_route(self):
        assert can_route_by_confidence("unsupported") is False

    def test_intake_status_frontdesk_only(self):
        """unsupported confidence -> frontdesk_only status."""
        intake_result = {
            "intake_status": "frontdesk_only",
            "confidence": {
                "level": "unsupported",
                "unverified_scope": True,
                "notes": "量子计算不在当前知识图谱范围内",
            },
            "routing": {
                "can_route": False,
                "next_action": "recommend_alternatives",
            },
        }
        assert intake_result["intake_status"] == "frontdesk_only"
        assert intake_result["confidence"]["level"] == "unsupported"
        assert intake_result["confidence"]["unverified_scope"] is True
        assert intake_result["routing"]["can_route"] is False

    def test_output_policy_blocks_all_downstream(self):
        """No downstream files for frontdesk_only status."""
        written_files = ["intake_response.md", "intake_result.yaml"]
        ok, msg = check_output_policy(False, "single_question", written_files)
        assert ok, f"Policy should allow intake-only files: {msg}"

    def test_output_policy_rejects_slot_blueprint(self):
        """slot_blueprint.yaml must NOT be written for unsupported scope."""
        written_files = ["intake_response.md", "intake_result.yaml", "slot_blueprint.yaml"]
        ok, msg = check_output_policy(False, "single_question", written_files)
        assert not ok, "Policy must reject slot_blueprint.yaml for unsupported scope"

    def test_no_downstream_files_written(self, tmp_path):
        """Simulate: write only intake files, verify no downstream files."""
        intake_dir = tmp_path / "intake_output"
        intake_dir.mkdir()

        (intake_dir / "intake_response.md").write_text(
            "量子计算不在当前知识图谱和题库范围内，因此不会调用后端出题流水线。\n\n"
            "可以改成以下支持方向：\n"
            "1. 计算机组成原理：并行处理、存储系统、CPU\n"
            "2. 操作系统：进程调度、内存管理\n"
            "3. 数据结构：图算法、查找、排序\n"
            "4. 计算机网络：可靠传输、路由算法",
            encoding="utf-8",
        )
        intake_result = {
            "intake_status": "frontdesk_only",
            "confidence": {
                "level": "unsupported",
                "unverified_scope": True,
                "notes": "量子计算不在当前知识图谱范围内",
            },
            "routing": {
                "can_route": False,
                "next_action": "recommend_alternatives",
            },
        }
        (intake_dir / "intake_result.yaml").write_text(
            yaml.dump(intake_result, allow_unicode=True), encoding="utf-8"
        )

        # Verify no downstream files
        downstream = {"paper_request.yaml", "slot_blueprint.yaml", "retrieval_query.yaml"}
        actual_files = set(os.listdir(intake_dir))
        leaked = actual_files & downstream
        assert not leaked, f"No downstream files expected, found: {leaked}"


# ---------------------------------------------------------------------------
# Bonus: integration check with real docs/compose/ directory
# ---------------------------------------------------------------------------

class TestBonusIntegration:
    """Verify load_paper_request works with the actual compose directory."""

    def test_load_from_actual_compose_dir(self):
        """If a valid paper_request.yaml existed in docs/compose/, compose_runner
        should be able to load it. Currently no paper_request.yaml there,
        so load_paper_request should return None (backward compat)."""
        compose_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "compose")
        compose_dir = os.path.abspath(compose_dir)

        if not os.path.isdir(compose_dir):
            pytest.skip("docs/compose/ does not exist")

        result = load_paper_request(compose_dir)
        # No paper_request.yaml in real compose dir currently
        assert result is None, \
            "Expected None (no paper_request.yaml in real compose dir), but got data"

    def test_roundtrip_from_actual_compose_dir(self, tmp_path):
        """Simulate writing paper_request.yaml to a compose-like dir and loading it."""
        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()

        paper_request = {
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
            "difficulty": {"target": "medium"},
        }
        yaml_path = compose_dir / "paper_request.yaml"
        yaml_path.write_text(yaml.dump(paper_request, allow_unicode=True), encoding="utf-8")

        loaded = load_paper_request(str(compose_dir))
        assert loaded is not None
        mapped = map_paper_request_to_params(loaded)
        assert "数据结构" in mapped["user_requirements"]
        assert "data_structure.md" in mapped["subject_files"]
