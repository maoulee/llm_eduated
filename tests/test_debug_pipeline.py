"""Tests for core_new.debug_pipeline.PipelineDebugger."""

import json
import os
import tempfile

from core_new.debug_pipeline import PipelineDebugger, _safe_serialize


class TestSafeSerialize:
    """Tests for the _safe_serialize helper."""

    def test_primitives(self):
        assert _safe_serialize("hello") == "hello"
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14
        assert _safe_serialize(True) is True
        assert _safe_serialize(False) is False
        assert _safe_serialize(None) is None

    def test_dict(self):
        data = {"a": 1, "b": "two", "c": None}
        result = _safe_serialize(data)
        assert result == {"a": 1, "b": "two", "c": None}

    def test_nested_dict(self):
        data = {"outer": {"inner": [1, 2, 3]}}
        result = _safe_serialize(data)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_list(self):
        assert _safe_serialize([1, "x", None]) == [1, "x", None]

    def test_tuple_becomes_list(self):
        result = _safe_serialize((1, 2, 3))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_non_serializable_becomes_str(self):
        class CustomObj:
            def __str__(self):
                return "custom"
        result = _safe_serialize(CustomObj())
        assert result == "custom"

    def test_dict_with_non_string_keys(self):
        data = {1: "one", 2: "two"}
        result = _safe_serialize(data)
        assert result == {"1": "one", "2": "two"}

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": [1, {"d": 2}]}}}
        result = _safe_serialize(data)
        assert result == {"a": {"b": {"c": [1, {"d": 2}]}}}

    def test_empty_containers(self):
        assert _safe_serialize({}) == {}
        assert _safe_serialize([]) == []
        assert _safe_serialize(()) == []


class TestPipelineDebugger:
    """Tests for PipelineDebugger dump methods."""

    def _make_debugger(self, tmpdir):
        return PipelineDebugger(os.path.join(tmpdir, "debug"))

    def test_creates_debug_dir(self, tmp_path):
        debug_dir = os.path.join(str(tmp_path), "my_debug")
        PipelineDebugger(debug_dir)
        assert os.path.isdir(debug_dir)

    def test_dump_step_basic(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        dbg.dump_step("Q01", "design", 0, {"stem": "test stem"}, timing_s=1.23)

        filepath = os.path.join(dbg.debug_dir, "Q01_design_r0.json")
        assert os.path.exists(filepath)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["slot_id"] == "Q01"
        assert data["step"] == "design"
        assert data["round"] == 0
        assert data["timing_s"] == 1.23
        assert data["output"] == {"stem": "test stem"}

    def test_dump_step_with_input(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        dbg.dump_step(
            "Q01", "design", 0,
            output={"stem": "hello"},
            input_data={"blueprint": {"slot_id": "Q01"}},
        )
        filepath = os.path.join(dbg.debug_dir, "Q01_design_r0.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["input"] == {"blueprint": {"slot_id": "Q01"}}
        assert data["output"] == {"stem": "hello"}

    def test_dump_step_no_timing(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        dbg.dump_step("Q01", "design", 0, {"stem": "x"})
        filepath = os.path.join(dbg.debug_dir, "Q01_design_r0.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["timing_s"] is None

    def test_dump_step_timestamp_format(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        dbg.dump_step("Q01", "design", 0, {})
        filepath = os.path.join(dbg.debug_dir, "Q01_design_r0.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        # ISO format with seconds precision
        assert "T" in data["timestamp"]

    def test_dump_step_handles_non_serializable(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))

        class Obj:
            def __str__(self):
                return "obj_str"
        dbg.dump_step("Q01", "step", 0, {"val": Obj()})
        filepath = os.path.join(dbg.debug_dir, "Q01_step_r0.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["output"]["val"] == "obj_str"

    def test_dump_full_run(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        final_q = {"stem": "what is X?"}
        solver = {"python_exec_count": 3}
        review = {
            "status": "pass",
            "overall_quality": 8,
            "_raw_text": "looks good" * 50,
        }
        dbg.dump_full_run("Q01", final_q, solver, review, total_time_s=5.67, rounds=2)

        filepath = os.path.join(dbg.debug_dir, "Q01_summary.json")
        assert os.path.exists(filepath)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert data["slot_id"] == "Q01"
        assert data["type"] == "pipeline_summary"
        assert data["total_time_s"] == 5.67
        assert data["rounds"] == 2
        assert data["final_stem"] == "what is X?"
        assert data["solver_execs"] == 3
        assert data["review_status"] == "pass"
        assert data["review_quality"] == 8

    def test_dump_full_run_stem_truncated(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        long_stem = "x" * 1000
        dbg.dump_full_run(
            "Q43", {"stem": long_stem},
            {"python_exec_count": 0},
            {"status": "pass", "overall_quality": 7, "_raw_text": ""},
            total_time_s=10.0, rounds=1,
        )
        filepath = os.path.join(dbg.debug_dir, "Q43_summary.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["final_stem"]) <= 500

    def test_dump_step_none_output_and_input(self, tmp_path):
        dbg = self._make_debugger(str(tmp_path))
        dbg.dump_step("Q01", "step", 0, None)
        filepath = os.path.join(dbg.debug_dir, "Q01_step_r0.json")
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        assert "output" not in data
        assert "input" not in data
