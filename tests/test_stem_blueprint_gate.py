"""Tests for core_new.agents.stem_blueprint_gate — parse_output and helpers."""

from core_new.agents.stem_blueprint_gate import (
    StemBlueprintGateAgent,
    _parse_gate_sections,
    _extract_text,
    _dump_blueprint_for_gate,
    _dump_options_md,
)


class TestParseGateSections:
    """Tests for _parse_gate_sections helper."""

    def test_full_markdown(self):
        text = (
            "## Verdict\n"
            "- **status**: pass\n"
            "- **severity**: none\n"
            "- **next_action**: continue\n"
            "- **fix_target**: none\n"
            "\n"
            "## Checks\n"
            "- **knowledge_relevance**: pass\n"
            "- **numerical_correct**: pass\n"
            "\n"
            "## Evidence\n"
            "some evidence text here\n"
            "more evidence lines\n"
            "\n"
            "## Code Verification\n"
            "exec result: ok\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: no fix needed\n"
        )
        sections = _parse_gate_sections(text)
        assert "verdict" in sections
        assert sections["verdict"]["status"] == "pass"
        assert sections["verdict"]["severity"] == "none"
        assert "checks" in sections
        assert sections["checks"]["knowledge_relevance"] == "pass"
        assert "evidence" in sections
        assert "some evidence" in sections["evidence"]["text"]
        assert "code_verification" in sections
        assert "exec result" in sections["code_verification"]["text"]
        assert "fix_instruction" in sections
        assert sections["fix_instruction"]["fix_detail"] == "no fix needed"

    def test_section_name_normalization(self):
        text = (
            "## Code verification results\n"
            "- **result**: ok\n"
            "\n"
            "## Fix instruction\n"
            "- **fix_detail**: adjust X\n"
        )
        sections = _parse_gate_sections(text)
        assert "code_verification" in sections
        assert "fix_instruction" in sections

    def test_empty_input(self):
        sections = _parse_gate_sections("")
        assert sections == {}

    def test_no_sections(self):
        sections = _parse_gate_sections("just some random text\nno headers")
        assert sections == {}

    def test_evidence_accumulates(self):
        text = (
            "## Evidence\n"
            "- **line1**: first\n"
            "free text line\n"
            "another line\n"
        )
        sections = _parse_gate_sections(text)
        assert "line1" not in sections["evidence"]  # evidence treats all as text
        assert "first" in sections["evidence"]["text"]
        assert "free text line" in sections["evidence"]["text"]
        assert "another line" in sections["evidence"]["text"]

    def test_unknown_section_name_preserved(self):
        text = (
            "## Custom Section\n"
            "- **key**: value\n"
        )
        sections = _parse_gate_sections(text)
        assert "custom section" in sections
        assert sections["custom section"]["key"] == "value"

    def test_colon_in_value_stripped(self):
        text = (
            "## Verdict\n"
            "- **status**: pass\n"
        )
        sections = _parse_gate_sections(text)
        assert sections["verdict"]["status"] == "pass"


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


class TestStemBlueprintGateParseOutput:
    """Tests for StemBlueprintGateAgent.parse_output().

    parse_output is a pure function on the class — it doesn't use self or
    call the LLM backend, so we skip __init__ (which imports code_exec)
    by calling the unbound method directly.
    """

    @staticmethod
    def _parse(raw):
        # parse_output doesn't use self, so pass None
        return StemBlueprintGateAgent.parse_output(None, raw)

    def test_empty_input_returns_needs_fix_critical(self):
        result = self._parse("")
        assert result["status"] == "needs_fix"
        assert result["severity"] == "critical"
        assert result["fix_target"] == "stem"
        assert result["next_action"] == "revise_stem"

    def test_short_input_returns_needs_fix_critical(self):
        result = self._parse("short")
        assert result["status"] == "needs_fix"
        assert result["severity"] == "critical"
        assert len(result["_raw_text"]) < 20

    def test_none_input_returns_needs_fix_critical(self):
        result = self._parse(None)
        assert result["status"] == "needs_fix"
        assert result["severity"] == "critical"

    def test_normal_pass_output(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
            "- **severity**: none\n"
            "- **next_action**: continue\n"
            "- **fix_target**: none\n"
            "\n"
            "## Checks\n"
            "- **knowledge_relevance**: pass\n"
            "- **numerical_correct**: pass\n"
            "\n"
            "## Evidence\n"
            "All checks passed. Knowledge point matches blueprint.\n"
            "\n"
            "## Code Verification\n"
            "No numerical claims to verify.\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: 无\n"
        )
        result = self._parse(raw)
        assert result["status"] == "pass"
        assert result["severity"] == "none"
        assert result["checks"]["knowledge_relevance"] == "pass"
        assert "All checks passed" in result["evidence"]
        assert result["fix_detail"] == "无"
        assert "_raw_text" in result

    def test_needs_fix_output(self):
        raw = (
            "## Verdict\n"
            "- **status**: needs_fix\n"
            "- **severity**: critical\n"
            "- **next_action**: revise_stem\n"
            "- **fix_target**: stem\n"
            "\n"
            "## Checks\n"
            "- **knowledge_relevance**: fail\n"
            "\n"
            "## Evidence\n"
            "Knowledge point does not match.\n"
            "\n"
            "## Code Verification\n"
            "\n"
            "## Fix Instruction\n"
            "- **fix_detail**: Reword the question\n"
        )
        result = self._parse(raw)
        assert result["status"] == "needs_fix"
        assert result["severity"] == "critical"
        assert result["fix_target"] == "stem"
        assert result["checks"]["knowledge_relevance"] == "fail"
        assert "Knowledge point does not match" in result["evidence"]

    def test_needs_fix_default_severity_critical(self):
        raw = (
            "## Verdict\n"
            "- **status**: needs_fix\n"
            "- **fix_target**: stem\n"
        )
        result = self._parse(raw)
        # When status=needs_fix but severity not in (critical, minor), default to critical
        assert result["severity"] == "critical"

    def test_missing_sections_fallback(self):
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
        )
        result = self._parse(raw)
        assert result["status"] == "pass"
        assert result["checks"] == {}
        assert result["evidence"] == ""
        assert result["code_verification"] == ""
        assert result["fix_detail"] == ""

    def test_comment_truncated_to_300(self):
        long_evidence = "x" * 500
        raw = (
            "## Verdict\n"
            "- **status**: pass\n"
            "\n"
            "## Evidence\n"
            f"{long_evidence}\n"
        )
        result = self._parse(raw)
        assert len(result["comment"]) <= 300

    def test_raw_text_attached(self):
        raw = "## Verdict\n- **status**: pass\n" + "padding " * 10
        result = self._parse(raw)
        assert result["_raw_text"] == raw.strip()


class TestDumpBlueprintForGate:
    def test_empty_blueprint(self):
        assert _dump_blueprint_for_gate({}) == "（无蓝图）"
        assert _dump_blueprint_for_gate(None) == "（无蓝图）"

    def test_basic_blueprint(self):
        bp = {
            "slot_id": "Q01",
            "target_subject": "数据结构",
            "primary_target_name": "二叉树",
            "question_type": "single_choice",
            "target_difficulty": 3,
        }
        md = _dump_blueprint_for_gate(bp)
        assert "Q01" in md
        assert "数据结构" in md
        assert "二叉树" in md
        assert "single_choice" in md

    def test_must_include_list(self):
        bp = {"must_include": ["AVL树", "旋转操作"]}
        md = _dump_blueprint_for_gate(bp)
        assert "AVL树" in md
        assert "旋转操作" in md

    def test_must_avoid_list(self):
        bp = {"must_avoid": ["红黑树"]}
        md = _dump_blueprint_for_gate(bp)
        assert "红黑树" in md

    def test_must_include_string(self):
        bp = {"must_include": "AVL树"}
        md = _dump_blueprint_for_gate(bp)
        assert "AVL树" in md

    def test_difficulty_profile(self):
        bp = {"difficulty_profile": {"knowledge_depth": 3, "reasoning_steps": 5}}
        md = _dump_blueprint_for_gate(bp)
        assert "知识深度=3" in md
        assert "推理步数=5" in md


class TestDumpOptionsMd:
    def test_no_options(self):
        assert _dump_options_md(None) == "（综合应用题，无选项）"
        assert _dump_options_md({}) == "（综合应用题，无选项）"

    def test_dict_options(self):
        opts = {
            "option_A": "answer A",
            "option_B": "answer B",
            "option_C": "answer C",
            "option_D": "answer D",
        }
        md = _dump_options_md(opts)
        assert "A" in md
        assert "answer A" in md

    def test_partial_options(self):
        opts = {"option_A": "only A"}
        md = _dump_options_md(opts)
        assert "answer A" in md or "only A" in md

    def test_non_dict_options(self):
        result = _dump_options_md("some string")
        assert result == "some string"
