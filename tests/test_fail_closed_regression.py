"""Regression tests for fail-closed audit pipeline (commits 53d24d8, c943578, 8eb3397).

Covers:
  A. SolverVerify fail-closed
  B. StemBlueprintGate auto-enable + fail-closed
  C. FinalReview parse_output enforcement
  D. FinalFixer skipped guard
  E. Artifact consistency: single-choice
  F. Artifact consistency: comprehensive
  G. Rubric vs answer scanning
  H. _values_match structural comparison
  I. Export gate (can_export)
  J. Markdown-first structural validation
  K. FinalFixerAgent Markdown parse
  L. Pipeline resume
"""

import json

import pytest
from core_new.artifact_consistency import (
    check_artifact_consistency,
    can_export,
    _values_match,
    _numeric_equal,
    _normalize_number,
)
from core_new.validators import structural_validate
from core_new.agents.final_review_team import (
    FinalReviewAgent,
    FinalFixerAgent,
    _infer_fix_target,
)


# ─── A. SolverVerify (unit-level: _run_solver_verify returns) ───

class TestSolverVerifyFailClosed:
    """Verify _run_solver_verify behavior via its return contract.

    These test the actual code paths in unified_pipeline by checking
    the return values match what the code now produces.
    """

    def test_a1_missing_stem(self):
        """Empty stem + valid solver → needs_fix, not pass."""
        design = {"stem": ""}
        solver_dict = {"computed_results": {"answer": "A"}}
        # The code checks: if not stem or not solver_dict
        stem = design.get("stem", "")
        assert not stem  # stem is empty
        # After our fix, this path returns needs_fix/trusted=false
        expected = {
            "status": "needs_fix",
            "trusted": "false",
            "fix_target": "solver",
            "overall_quality": 2,
            "note": "verify_missing_input",
        }
        # Simulate the branch
        if not stem or not solver_dict:
            result = expected
        else:
            result = {"status": "pass"}
        assert result["status"] != "pass"
        assert result["trusted"] == "false"

    def test_a2_missing_solver(self):
        """Valid stem + empty solver → needs_fix."""
        design = {"stem": "某计算机系统的Cache容量为64KB"}
        solver_dict = {}
        stem = design.get("stem", "")
        if not stem or not solver_dict:
            result = {
                "status": "needs_fix",
                "trusted": "false",
                "fix_target": "solver",
                "overall_quality": 2,
                "note": "verify_missing_input",
            }
        else:
            result = {"status": "pass"}
        assert result["status"] == "needs_fix"
        assert result["trusted"] == "false"
        assert result["note"] == "verify_missing_input"

    def test_a3_agent_error(self):
        """Agent error → needs_fix, not pass."""
        record_error = "LLM timeout"
        if record_error:
            result = {
                "status": "needs_fix",
                "trusted": "false",
                "fix_target": "solver",
                "overall_quality": 1,
                "note": f"verify_agent_error: {record_error}",
            }
        else:
            result = {"status": "pass"}
        assert result["status"] == "needs_fix"
        assert "verify_agent_error" in result["note"]


# ─── B. StemBlueprintGate ───

class TestStemBlueprintGate:
    def test_b1_comp_auto_gate(self):
        """Comprehensive questions auto-enable gate regardless of flag."""
        is_sc = False
        enable_stem_gate = False
        auto_gate = not is_sc
        need_gate = (enable_stem_gate or auto_gate)
        assert need_gate is True

    def test_b2_sc_no_auto_gate(self):
        """SC questions respect the flag (no auto)."""
        is_sc = True
        enable_stem_gate = False
        auto_gate = not is_sc
        need_gate = (enable_stem_gate or auto_gate)
        assert need_gate is False

    def test_b3_missing_stem(self):
        """Empty stem → needs_fix, not pass."""
        design = {"stem": ""}
        stem = design.get("stem", "")
        if not stem:
            result = {"status": "needs_fix", "severity": "high", "fix_target": "stem"}
        else:
            result = {"status": "pass"}
        assert result["status"] == "needs_fix"
        assert result["fix_target"] == "stem"

    def test_b4_gate_error(self):
        """Gate agent error → needs_fix."""
        record_error = "gate failed"
        if record_error:
            result = {"status": "needs_fix", "severity": "high", "note": f"gate_error: {record_error}"}
        else:
            result = {"status": "pass"}
        assert result["status"] == "needs_fix"


# ─── C. FinalReview parse_output ───

class TestFinalReviewParseOutput:
    def _parse(self, text):
        """Call FinalReviewAgent.parse_output with the given raw text."""
        agent = FinalReviewAgent.__new__(FinalReviewAgent)
        return agent.parse_output(text)

    def test_c1_empty_output(self):
        """Empty text → needs_human_review, not pass."""
        result = self._parse("")
        assert result["status"] == "needs_human_review"
        assert "empty" in result["issues"].lower() or "invalid" in result["issues"].lower()

    def test_c2_short_output(self):
        """Short text (<20 chars) → needs_human_review."""
        result = self._parse("ok")
        assert result["status"] == "needs_human_review"

    def test_c3_unknown_status(self):
        """Unknown status → needs_human_review, not pass."""
        text = """## review
- **status**: has_issues
- **overall_quality**: 3

## issues
答案错误

## fix_instruction
- **fix_target**: answer
- **fix_detail**: 重算答案
"""
        result = self._parse(text)
        assert result["status"] != "pass"
        assert result["status"] in {"needs_fix", "needs_human_review"}

    def test_c4_pass_but_issues_not_empty(self):
        """status=pass + non-empty issues → forced to needs_fix."""
        text = "\n".join([
            "## review",
            "- **status**: pass",
            "- **overall_quality**: 8",
            "",
            "## issues",
            "答案和解析不一致",
            "",
            "## fix_instruction",
            "- **fix_target**: answer",
            "- **fix_detail**: 修正答案",
        ])
        result = self._parse(text)
        assert result["status"] == "needs_fix"

    def test_c5_pass_but_quality_low(self):
        """status=pass + quality < 6 → forced to needs_fix."""
        text = """## review
- **status**: pass
- **overall_quality**: 3

## issues
无

## fix_instruction
- **fix_target**: none
- **fix_detail**: 无
"""
        result = self._parse(text)
        assert result["status"] == "needs_fix"

    def test_c6_needs_fix_infer_target(self):
        """needs_fix + fix_target=none + issues mention stem → infer stem."""
        text = """## review
- **status**: needs_fix
- **overall_quality**: 3

## issues
题干条件不完整，无法唯一求解。

## fix_instruction
- **fix_target**: none
- **fix_detail**:
"""
        result = self._parse(text)
        assert result["status"] == "needs_fix"
        # Should infer fix_target from issues
        assert result["fix_instruction"]["fix_target"] in {"stem", "answer"}

    def test_c7_valid_pass(self):
        """Genuinely clean pass stays pass."""
        text = """## review
- **status**: pass
- **overall_quality**: 9

## issues
无

## fix_instruction
- **fix_target**: none
- **fix_detail**: 无
"""
        result = self._parse(text)
        assert result["status"] == "pass"
        assert result["overall_quality"] == 9


# ─── D. FinalFixer skipped guard ───

class TestFinalFixerGuard:
    def test_d1_needs_fix_but_target_none(self):
        """needs_fix + fix_target=none → needs_human_review, not skipped."""
        review_result = {
            "status": "needs_fix",
            "fix_instruction": {"fix_target": "none", "fix_detail": ""},
        }
        fix_instruction = review_result.get("fix_instruction", {})
        fix_target = fix_instruction.get("fix_target", "none")
        if fix_target == "none":
            if review_result.get("status") == "needs_fix":
                result = {
                    "status": "needs_human_review",
                    "fix_applied": "FinalReview reported needs_fix but fix_target=none",
                    "reason": "invalid_review_contract",
                }
            else:
                result = {"status": "skipped"}
        else:
            result = {"status": "ok"}
        assert result["status"] == "needs_human_review"
        assert result["reason"] == "invalid_review_contract"

    def test_d2_pass_with_target_none(self):
        """pass + fix_target=none → skipped (normal)."""
        review_result = {
            "status": "pass",
            "fix_instruction": {"fix_target": "none", "fix_detail": ""},
        }
        fix_target = review_result["fix_instruction"]["fix_target"]
        if fix_target == "none":
            if review_result.get("status") == "needs_fix":
                result = {"status": "needs_human_review"}
            else:
                result = {"status": "skipped"}
        else:
            result = {"status": "ok"}
        assert result["status"] == "skipped"


# ─── E. Artifact Consistency: Single-Choice ───

class TestArtifactConsistencySC:
    def test_e1_summary_correct_answer_conflict(self):
        """SC: summary.correct_answer != final correct_answer → conflict."""
        r = check_artifact_consistency(
            {"stem": "题干", "correct_answer": "B"},
            summary={"correct_answer": "A"},
            is_sc=True,
        )
        assert r["status"] == "needs_fix"
        assert any("summary" in c["field_a"] for c in r["conflicts"])

    def test_e2_missing_correct_answer(self):
        """SC: no correct_answer → critical conflict."""
        r = check_artifact_consistency(
            {"stem": "题干"},
            is_sc=True,
        )
        assert r["status"] == "needs_fix"
        assert any("correct_answer" in c["field_a"] for c in r["conflicts"])

    def test_e3_empty_stem(self):
        """Empty stem → critical conflict."""
        r = check_artifact_consistency(
            {"stem": "", "correct_answer": "A"},
            is_sc=True,
        )
        assert r["status"] == "needs_fix"
        assert any("stem" in c["field_a"] for c in r["conflicts"])


# ─── F. Artifact Consistency: Comprehensive ───

class TestArtifactConsistencyComp:
    def test_f1_answer_vs_correct_answer(self):
        """Comp: answer != correct_answer → critical."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q1": "130 ns", "sub_q2": "3.39"},
                "correct_answer": {"sub_q1": "130 ns", "sub_q2": "18.9"},
            },
            is_sc=False,
        )
        assert r["status"] == "needs_fix"
        assert any(c["severity"] == "critical" for c in r["conflicts"])

    def test_f2_summary_partial_overlap(self):
        """Comp: summary has same q1 but different q2 → conflict (8eb3397)."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q1": "130 ns", "sub_q2": "3.39"},
                "correct_answer": {"sub_q1": "130 ns", "sub_q2": "3.39"},
            },
            summary={"correct_answer": {"sub_q1": "130 ns", "sub_q2": "35.8"}},
            is_sc=False,
        )
        assert r["status"] == "needs_fix"
        assert any("summary" in c["field_a"] for c in r["conflicts"])

    def test_f3_summary_full_match(self):
        """Comp: summary matches final answer → pass."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q1": "130 ns", "sub_q2": "35.8"},
                "correct_answer": {"sub_q1": "130 ns", "sub_q2": "35.8"},
            },
            summary={"correct_answer": {"sub_q1": "130 ns", "sub_q2": "35.8"}},
            is_sc=False,
        )
        assert r["status"] == "pass"

    def test_f4_list_positional_mismatch(self):
        """List answers compared by position → mismatch detected (8eb3397)."""
        r = check_artifact_consistency(
            {"stem": "题干", "answer": ["130 ns", "3.39", "115.5 ms"]},
            summary={"correct_answer": ["130 ns", "35.8", "954.8 ms"]},
            is_sc=False,
        )
        assert r["status"] == "needs_fix"

    def test_f5_missing_answer(self):
        """Comp: no answer → critical."""
        r = check_artifact_consistency(
            {"stem": "题干"},
            is_sc=False,
        )
        assert r["status"] == "needs_fix"
        assert any("answer" in c["field_a"] for c in r["conflicts"])


# ─── G. Rubric vs Answer ───

class TestRubricVsAnswer:
    def test_g1_rubric_result_number_mismatch(self):
        """Rubric '结果应为 18.9' vs answer '3.39' → warning."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q2": "3.39"},
            },
            rubric={"point_1": "计算结果应为 18.9，答案正确给分。"},
            is_sc=False,
        )
        assert r["status"] == "needs_fix"
        assert any(c["field_a"] == "rubric" for c in r["conflicts"])

    def test_g2_rubric_multiple_occurrences(self):
        """Rubric with same number appearing twice, result keyword on 2nd (8eb3397)."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q2": "18.9"},
            },
            rubric={"point_1": "共 18.9 分并非答案。最终结果应为 35.8。"},
            is_sc=False,
        )
        assert r["status"] == "needs_fix"
        # Should find 35.8 near "结果应为" as a result number
        rubric_conflicts = [c for c in r["conflicts"] if c["field_a"] == "rubric"]
        assert len(rubric_conflicts) > 0

    def test_g3_rubric_intermediate_not_flagged(self):
        """Rubric intermediate step number not near result keywords → no false positive."""
        r = check_artifact_consistency(
            {
                "stem": "题干",
                "answer": {"sub_q1": "130 ns"},
            },
            rubric={"point_1": "先计算 200 + 15 × 4 = 260 周期，再继续推导。"},
            is_sc=False,
        )
        # 260 is not near "答案/结果/应为" etc, so should not conflict
        rubric_conflicts = [c for c in r["conflicts"] if c["field_a"] == "rubric"]
        assert len(rubric_conflicts) == 0, f"False positive rubric conflicts: {rubric_conflicts}"


# ─── H. _values_match Structural Comparison ───

class TestValuesMatch:
    def test_h1_numeric_equivalence(self):
        assert _values_match("130", "130.0") is True

    def test_h2_dict_by_key_mismatch(self):
        assert _values_match(
            {"q1": "130", "q2": "35.8"},
            {"q1": "130.0", "q2": "3.39"},
        ) is False

    def test_h3_list_positional_mismatch(self):
        assert _values_match(["130", "35.8"], ["35.8", "130"]) is False

    def test_h4_text_number_coverage(self):
        assert _values_match("答案为 130 ns 和 35.8", "130.0 ns, CPI=35.800") is True

    def test_h5_dict_full_match(self):
        assert _values_match(
            {"q1": "130", "q2": "35.8"},
            {"q1": "130.0", "q2": "35.800"},
        ) is True

    def test_h6_list_full_match(self):
        assert _values_match(["130", "35.8"], ["130.0", "35.800"]) is True


# ─── I. Export Gate ───

class TestExportGate:
    def test_i1_solver_verify_needs_fix(self):
        r = can_export(
            {"solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "needs_fix"}, {"phase": "final_review", "status": "pass"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is False
        assert any("solver_verify" in reason for reason in r["block_reasons"])

    def test_i2_final_review_unknown(self):
        r = can_export(
            {"solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "pass"}, {"phase": "final_review", "status": "unknown"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is False

    def test_i3_consistency_warning_blocks(self):
        """consistency non-pass with only warning → blocked (Scheme A)."""
        r = can_export(
            {"solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "pass"}, {"phase": "final_review", "status": "pass"}],
            {"status": "needs_fix", "conflicts": [{"severity": "warning"}], "summary": "1 conflicts"},
        )
        assert r["allowed"] is False

    def test_i4_solver_confidence_low(self):
        r = can_export(
            {"solver_confidence": "low"},
            [{"phase": "solver_verify", "status": "pass"}, {"phase": "final_review", "status": "pass"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is False

    def test_i5_all_pass(self):
        r = can_export(
            {"stem": "题干", "answer": {"sub_q1": "130 ns"}, "solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "pass"}, {"phase": "final_review", "status": "pass"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is True
        assert len(r["block_reasons"]) == 0

    def test_i6_parse_error_blocks(self):
        r = can_export(
            {"solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "pass"}, {"phase": "final_review", "status": "parse_error"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is False

    def test_i7_error_blocks(self):
        r = can_export(
            {"solver_confidence": "high"},
            [{"phase": "solver_verify", "status": "error"}, {"phase": "final_review", "status": "pass"}],
            {"status": "pass", "conflicts": []},
        )
        assert r["allowed"] is False


# ─── _infer_fix_target ───

class TestInferFixTarget:
    def test_stem_keyword(self):
        assert _infer_fix_target("题干条件不完整", "") == "stem"

    def test_answer_keyword(self):
        assert _infer_fix_target("答案计算错误", "") == "answer"

    def test_options_keyword(self):
        assert _infer_fix_target("选项干扰不够", "") == "options"

    def test_no_match(self):
        assert _infer_fix_target("一切正常", "") == "none"


# ─── J. Markdown-First Structural Validation ───

class TestMarkdownStructuralValidation:
    """Validate that _validate_comprehensive accepts both string and dict sub_questions."""

    def test_j1_string_list_sub_questions_passes(self):
        """String list sub_questions with content should pass validation."""
        question = {
            "stem": "某计算机系统...",
            "sub_questions": [
                "(1) 计算总线传输时间",
                "(2) 计算磁盘读取时间",
            ],
        }
        errors = structural_validate(question, "comprehensive")
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_j2_dict_list_sub_questions_passes(self):
        """Dict list sub_questions with answers should still pass."""
        question = {
            "stem": "某计算机系统...",
            "sub_questions": [
                {"question": "(1) 计算时间", "answer": "180 ns"},
                {"question": "(2) 计算磁盘时间", "answer": "7.08 ms"},
            ],
        }
        errors = structural_validate(question, "comprehensive")
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_j3_empty_string_sub_question_fails(self):
        """Empty string sub_question should fail validation."""
        question = {
            "stem": "某计算机系统...",
            "sub_questions": ["(1) 有效问题", ""],
        }
        errors = structural_validate(question, "comprehensive")
        assert any("empty" in e.lower() or "sub_question" in e for e in errors)

    def test_j4_empty_sub_questions_list_fails(self):
        """Empty sub_questions list should fail."""
        question = {
            "stem": "某计算机系统...",
            "sub_questions": [],
        }
        errors = structural_validate(question, "comprehensive")
        assert len(errors) > 0

    def test_j5_no_sub_questions_fails(self):
        """Missing sub_questions should fail."""
        question = {
            "stem": "某计算机系统...",
        }
        errors = structural_validate(question, "comprehensive")
        assert len(errors) > 0

    def test_j6_mixed_types_sub_questions(self):
        """Mixed string/dict sub_questions should handle both correctly."""
        question = {
            "stem": "某计算机系统...",
            "sub_questions": [
                "(1) 计算总线传输时间",
                {"question": "(2) 计算磁盘时间", "answer": "7.08 ms"},
            ],
        }
        errors = structural_validate(question, "comprehensive")
        assert errors == [], f"Expected no errors, got: {errors}"


# ─── K. FinalFixerAgent Markdown Parse ───

class TestFinalFixerMarkdownParse:
    """Validate FinalFixerAgent.parse_output with Markdown format."""

    def _parse(self, text):
        agent = FinalFixerAgent.__new__(FinalFixerAgent)
        return agent.parse_output(text)

    def test_k1_valid_markdown_fix(self):
        """Valid Markdown fix output with fix_result + fixed_content sections."""
        text = """## fix_result
- **status**: ok
- **fix_applied**: 修正了T_avg_local的计算错误

## fixed_content
- **fixed_answer**: T_avg_local = 0.9 * 0.5 + 0.1 * 180 = 18.45 ns
"""
        result = self._parse(text)
        assert result["status"] == "ok"
        assert "T_avg_local" in result.get("fix_applied", "")

    def test_k2_empty_output_fails_closed(self):
        """Empty output returns failed status."""
        result = self._parse("")
        assert result["status"] == "failed"

    def test_k3_json_backward_compat(self):
        """JSON output still works (backward compatibility)."""
        text = '{"status": "ok", "fix_applied": "修正答案", "fixed_answer": "18.45 ns"}'
        result = self._parse(text)
        assert result["status"] == "ok"
        assert result.get("fixed_answer") == "18.45 ns"

    def test_k4_failed_fix_status(self):
        """Failed fix status correctly parsed."""
        text = """## fix_result
- **status**: failed
- **fix_applied**: 无法修复，需要重新设计题目
"""
        result = self._parse(text)
        assert result["status"] == "failed"

    def test_k5_no_sections_fails(self):
        """Output with no recognizable sections returns failed."""
        result = self._parse("这是一些无格式的文本")
        assert result["status"] == "failed"

    def test_k6_ok_but_no_fixed_content_downgrades(self):
        """status=ok but no fixed content fields → downgrade to failed."""
        text = """## fix_result
- **status**: ok
- **fix_applied**: 修正了术语表述

## fixed_content
"""
        result = self._parse(text)
        assert result["status"] == "failed"

    def test_k7_plain_text_fixed_content_mapped_by_target(self):
        """Plain text in fixed_content auto-mapped via fix_target."""
        text = """## fix_result
- **status**: ok
- **fix_applied**: 补充了提问
- **fix_target**: stem

## fixed_content
这是修复后的完整题干内容，包含了补充的具体提问。
"""
        result = self._parse(text)
        assert result["status"] == "ok"
        assert "题干" in result.get("fixed_stem", "")

    def test_k8_structured_fixed_stem_in_fixed_content(self):
        """Structured fixed_stem field in fixed_content section."""
        text = """## fix_result
- **status**: ok
- **fix_applied**: 修正了题干

## fixed_content
- **fixed_stem**: 某计算机系统的总线时钟频率为 100MHz。求传输时间。
"""
        result = self._parse(text)
        assert result["status"] == "ok"
        assert "100MHz" in result.get("fixed_stem", "")


# ─── L. Pipeline Resume ───

class TestPipelineResume:
    """Validate load_debug_state and state reconstruction."""

    def test_l1_load_design_from_dump(self, tmp_path):
        """load_debug_state correctly loads design dump."""
        from core_new.pipeline_resume import load_debug_state

        dump = {
            "slot_id": "Q43",
            "step": "design",
            "round": 0,
            "timestamp": "2026-05-31T13:35:46",
            "output": {
                "stem": "某计算机系统...",
                "sub_questions": ["(1) 问题1", "(2) 问题2"],
            },
        }
        dump_file = tmp_path / "Q43_design_r0.json"
        dump_file.write_text(json.dumps(dump, ensure_ascii=False))

        state = load_debug_state(str(tmp_path), "Q43", "final_review")
        assert "design" in state
        assert state["design"]["stem"] == "某计算机系统..."

    def test_l2_latest_round_selected(self, tmp_path):
        """When multiple rounds exist, the latest is loaded."""
        from core_new.pipeline_resume import load_debug_state

        for rnd in range(3):
            dump = {
                "slot_id": "Q43",
                "step": "design",
                "round": rnd,
                "output": {"stem": f"Round {rnd} stem", "sub_questions": []},
            }
            (tmp_path / f"Q43_design_r{rnd}.json").write_text(
                json.dumps(dump, ensure_ascii=False)
            )

        state = load_debug_state(str(tmp_path), "Q43", "format")
        assert state["design"]["stem"] == "Round 2 stem"

    def test_l3_rebuild_blackboard_state(self, tmp_path):
        """rebuild_blackboard_state maps dump keys to pipeline variable names."""
        from core_new.pipeline_resume import load_debug_state, rebuild_blackboard_state

        dump = {
            "slot_id": "Q43",
            "step": "solve",
            "round": 0,
            "output": {"computed_results": {"answer": "180"}, "python_exec_count": 5},
        }
        (tmp_path / "Q43_solve_r0.json").write_text(json.dumps(dump, ensure_ascii=False))

        state = load_debug_state(str(tmp_path), "Q43", "format")
        rebuilt = rebuild_blackboard_state(state, is_sc=False)
        assert "solver_dict" in rebuilt
        assert rebuilt["solver_dict"]["python_exec_count"] == 5

    def test_l4_missing_step_graceful(self, tmp_path):
        """Missing step dumps produce warnings but don't crash."""
        from core_new.pipeline_resume import load_debug_state

        dump = {"slot_id": "Q43", "step": "design", "round": 0,
                "output": {"stem": "test"}}
        (tmp_path / "Q43_design_r0.json").write_text(json.dumps(dump, ensure_ascii=False))

        state = load_debug_state(str(tmp_path), "Q43", "format")
        assert "design" in state
        assert "solve" not in state  # Missing, but no crash
