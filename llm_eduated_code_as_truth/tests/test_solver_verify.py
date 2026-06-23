"""Tests for core_new.agents.solver_verify — parse_output and helpers."""

from core_new.agents.solver_verify import (
    SolverVerifyAgent,
    _parse_verify_sections,
    _extract_text,
    _dump_blueprint_for_verify,
    _dump_options_md,
)


class TestParseVerifySections:
    """Tests for _parse_verify_sections helper."""

    def test_full_markdown(self):
        text = (
            "## Verdict\n"
            "- **status**: pass\n"
            "- **next_action**: continue\n"
            "- **fix_target**: none\n"
            "\n"
            "## Checks\n"
            "- **formula_correct**: pass\n"
            "- **overall_quality**: 8\n"
            "\n"
            "## Evidence\n"
            "The solver used correct formula.\n"
            "Verification passed.\n"
            "\n"
            "## Verified Result\n"
            "- **trusted**: true\n"
            "- **computed_answer**: B\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: 无\n"
        )
        sections = _parse_verify_sections(text)
        assert sections["verdict"]["status"] == "pass"
        assert sections["checks"]["formula_correct"] == "pass"
        assert sections["checks"]["overall_quality"] == "8"
        assert "correct formula" in sections["evidence"]["text"]
        assert sections["verified_result"]["trusted"] == "true"
        assert sections["verified_result"]["computed_answer"] == "B"
        assert sections["fix_instruction"]["fix_detail"] == "无"

    def test_section_name_normalization(self):
        text = (
            "## Verified result\n"
            "- **trusted**: false\n"
            "\n"
            "## Fix instruction\n"
            "- **fix_detail**: rerun\n"
        )
        sections = _parse_verify_sections(text)
        assert "verified_result" in sections
        assert "fix_instruction" in sections

    def test_empty_input(self):
        assert _parse_verify_sections("") == {}

    def test_no_sections(self):
        assert _parse_verify_sections("plain text\nmore text") == {}

    def test_evidence_accumulates(self):
        text = (
            "## Evidence\n"
            "line one\n"
            "line two\n"
        )
        sections = _parse_verify_sections(text)
        assert "line one" in sections["evidence"]["text"]
        assert "line two" in sections["evidence"]["text"]

    def test_unknown_section(self):
        text = (
            "## Custom\n"
            "- **key**: val\n"
        )
        sections = _parse_verify_sections(text)
        assert "custom" in sections
        assert sections["custom"]["key"] == "val"


class TestSolverVerifyParseOutput:
    """Tests for SolverVerifyAgent.parse_output().

    parse_output is a pure function — skip __init__ by calling unbound method.
    """

    @staticmethod
    def _parse(raw):
        # parse_output doesn't use self, so pass None
        return SolverVerifyAgent.parse_output(None, raw)

    def test_empty_input_returns_needs_fix_solver(self):
        result = self._parse("")
        assert result["status"] == "needs_fix"
        assert result["fix_target"] == "solver"
        assert result["overall_quality"] == 3
        assert result["next_action"] == "rerun_solver"

    def test_short_input_returns_needs_fix(self):
        result = self._parse("tiny")
        assert result["status"] == "needs_fix"
        assert result["overall_quality"] == 3

    def test_none_input_returns_needs_fix(self):
        result = self._parse(None)
        assert result["status"] == "needs_fix"

    def test_normal_pass_output(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
            "- **next_action**: continue\n"
            "- **fix_target**: none\n"
            "\n"
            "## Checks\n"
            "- **formula_correct**: pass\n"
            "- **computation_valid**: pass\n"
            "- **overall_quality**: 9\n"
            "\n"
            "## Evidence\n"
            "Solver computation is correct.\n"
            "\n"
            "## Verified Result\n"
            "- **trusted**: true\n"
            "- **computed_answer**: C\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: 无\n"
        )
        result = self._parse(raw)
        assert result["status"] == "pass"
        assert result["trusted"] == "true"
        assert result["computed_answer"] == "C"
        assert result["overall_quality"] == "9"
        assert "correct" in result["evidence"]

    def test_needs_fix_defaults_fix_target_to_solver(self):
        raw = (
            "## Verdict\n"
            "- **status**: needs_fix\n"
            "\n"
            "## Checks\n"
            "- **overall_quality**: 4\n"
            "\n"
            "## Evidence\n"
            "Computation error detected.\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: rerun solver\n"
        )
        result = self._parse(raw)
        assert result["status"] == "needs_fix"
        assert result["fix_target"] == "solver"

    def test_needs_fix_explicit_fix_target(self):
        raw = (
            "## Verdict\n"
            "- **status**: needs_fix\n"
            "- **fix_target**: stem\n"
            "\n"
            "## Checks\n"
            "- **overall_quality**: 3\n"
        )
        result = self._parse(raw)
        assert result["fix_target"] == "stem"

    def test_overall_quality_from_checks(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
            "\n"
            "## Checks\n"
            "- **overall_quality**: 7\n"
        )
        result = self._parse(raw)
        assert result["overall_quality"] == "7"

    def test_overall_quality_default_pass(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
        )
        result = self._parse(raw)
        assert result["overall_quality"] == 8

    def test_overall_quality_default_needs_fix(self):
        raw = (
            "## Verdict\n"
            "- **status**: needs_fix\n"
            "- **fix_target**: solver\n"
        )
        result = self._parse(raw)
        assert result["overall_quality"] == 5

    def test_missing_verified_result_defaults_trusted_true(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
        )
        result = self._parse(raw)
        assert result["trusted"] == "true"
        assert result["computed_answer"] == ""

    def test_raw_text_attached(self):
        raw = "## Verdict\n- **status**: pass\n" + "padding " * 10
        result = self._parse(raw)
        assert result["_raw_text"] == raw.strip()

    def test_comment_truncated_to_300(self):
        long_evidence = "e" * 500
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
            "\n"
            "## Evidence\n"
            f"{long_evidence}\n"
        )
        result = self._parse(raw)
        assert len(result["comment"]) <= 300


class TestExtractText:
    def test_dict_with_text(self):
        assert _extract_text({"text": "hello"}) == "hello"

    def test_dict_without_text(self):
        assert _extract_text({"key": "val"}) == ""

    def test_string(self):
        assert _extract_text("hello") == "hello"

    def test_none(self):
        assert _extract_text(None) == ""

    def test_number(self):
        assert _extract_text(42) == "42"


class TestDumpBlueprintForVerify:
    def test_empty(self):
        assert _dump_blueprint_for_verify({}) == "（无蓝图）"
        assert _dump_blueprint_for_verify(None) == "（无蓝图）"

    def test_basic(self):
        bp = {
            "primary_target_name": "虚拟内存",
            "target_difficulty": 4,
            "question_type": "comprehensive",
        }
        md = _dump_blueprint_for_verify(bp)
        assert "虚拟内存" in md
        assert "comprehensive" in md


class TestDumpOptionsMd:
    def test_no_options(self):
        assert _dump_options_md(None) == "（综合应用题，无选项）"
        assert _dump_options_md({}) == "（综合应用题，无选项）"

    def test_dict_options(self):
        opts = {"option_A": "A text", "option_B": "B text"}
        md = _dump_options_md(opts)
        assert "A text" in md
        assert "B text" in md

    def test_non_dict(self):
        assert _dump_options_md("just text") == "just text"
