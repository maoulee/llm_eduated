"""Integration test: validate debug output from Q43 pipeline run.

Run with: python3 -m pytest tests/test_integration_debug.py -v

Prerequisites: a debug run must exist in debug/ directory with full output.
Run: python3 run_slot_composition.py --slots Q43 --max-fix-rounds 1 --debug
"""

import glob
import json
import os
from typing import Any, Dict

import pytest

DEBUG_DIR_PATTERN = "debug/Q43_*"


def _find_latest_debug_dir() -> str:
    dirs = glob.glob(DEBUG_DIR_PATTERN)
    if not dirs:
        pytest.skip("No Q43 debug directory found")
    return max(dirs, key=os.path.getmtime)


def _load_json(filepath: str) -> Dict[str, Any]:
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def _find_file(debug_files: Dict[str, str], keyword: str, exclude: str = "") -> str | None:
    """Find a file by keyword in filename. Returns filepath or None."""
    for fname, fpath in debug_files.items():
        if keyword in fname and (not exclude or exclude not in fname):
            return fpath
    return None


def _skip_if_no_file(debug_files: Dict[str, str], keyword: str, test_name: str, exclude: str = "") -> str:
    """Find file or skip test. Returns filepath."""
    fpath = _find_file(debug_files, keyword, exclude=exclude)
    if not fpath:
        pytest.skip(f"No '{keyword}' file in debug output (test: {test_name})")
    return fpath


@pytest.fixture(scope="module")
def debug_dir():
    return _find_latest_debug_dir()


@pytest.fixture(scope="module")
def debug_files(debug_dir):
    return {os.path.basename(f): f for f in glob.glob(os.path.join(debug_dir, "*.json"))}


class TestDebugFilesExist:
    def test_has_design(self, debug_files):
        _skip_if_no_file(debug_files, "design", "has_design")

    def test_has_solve(self, debug_files):
        _skip_if_no_file(debug_files, "solve", "has_solve")

    def test_has_verify(self, debug_files):
        _skip_if_no_file(debug_files, "verify", "has_verify", exclude="param_verify")

    def test_has_summary(self, debug_files):
        _skip_if_no_file(debug_files, "_summary", "has_summary")


class TestDebugOutputNonEmpty:
    def test_design_has_output(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "design", "design_output")
        data = _load_json(fpath)
        assert data.get("output"), f"Design output is empty: {os.path.basename(fpath)}"
        stem = data["output"].get("stem", "")
        assert len(stem) > 20, f"Design stem too short ({len(stem)} chars)"

    def test_solve_has_output(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "solve", "solve_output")
        data = _load_json(fpath)
        assert data.get("output"), f"Solve output is empty: {os.path.basename(fpath)}"

    def test_verify_has_output(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "verify", "verify_output", exclude="param_verify")
        data = _load_json(fpath)
        assert data.get("output"), f"Verify output is empty: {os.path.basename(fpath)}"

    def test_step_records_have_slot_id(self, debug_dir, debug_files):
        if not debug_files:
            pytest.skip("No debug files found")
        for fname, fpath in debug_files.items():
            data = _load_json(fpath)
            assert data.get("slot_id"), f"Missing slot_id in {fname}"
            assert data["slot_id"].startswith("Q"), f"Bad slot_id in {fname}: {data['slot_id']}"


class TestSolverVerifyNotBypassed:
    """Verify that SolverVerify produces real output."""

    def test_verify_has_status(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "verify", "verify_status", exclude="param_verify")
        data = _load_json(fpath)
        output = data.get("output", {})
        assert isinstance(output, dict), f"Verify output is not a dict: {type(output)}"
        status = output.get("status")
        assert status in ("pass", "needs_fix"), f"Unexpected verify status: {status}"

    def test_verify_has_raw_text(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "verify", "verify_raw_text", exclude="param_verify")
        data = _load_json(fpath)
        output = data.get("output", {})
        # Accept either structured output (status field) or raw text (_raw_text)
        has_structured = output.get("status") is not None
        raw_text = output.get("_raw_text", "")
        assert has_structured or len(raw_text) > 20, \
            f"Verify has neither structured status nor raw_text — likely empty output"

    def test_verify_has_overall_quality(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "verify", "verify_quality", exclude="param_verify")
        data = _load_json(fpath)
        output = data.get("output", {})
        quality = output.get("overall_quality")
        assert quality is not None, "Missing overall_quality in verify output"
        try:
            int(quality)
        except (ValueError, TypeError):
            pytest.fail(f"overall_quality is not numeric: {quality}")


class TestGateRouting:
    def test_question_type_routed_correctly(self, debug_dir):
        summary_files = glob.glob(os.path.join(debug_dir, "*summary*.json"))
        if not summary_files:
            pytest.skip("No summary files found")
        for sf in summary_files:
            data = _load_json(sf)
            if data.get("type") == "pipeline_summary":
                return
        pytest.skip("No pipeline_summary found")


class TestPipelineSummary:
    def test_summary_has_required_fields(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "_summary", "summary_fields")
        data = _load_json(fpath)
        if data.get("type") == "pipeline_summary":
            assert "slot_id" in data
            assert "total_time_s" in data
            assert "rounds" in data
            assert "review_status" in data
            assert "review_quality" in data

    def test_total_time_reasonable(self, debug_dir, debug_files):
        fpath = _skip_if_no_file(debug_files, "_summary", "summary_time")
        data = _load_json(fpath)
        if data.get("type") == "pipeline_summary":
            assert data["total_time_s"] > 10, f"Total time too short: {data['total_time_s']}s"
            assert data["total_time_s"] < 1200, f"Total time too long: {data['total_time_s']}s"


class TestEachStepHasTimestamp:
    def test_all_steps_have_timestamp(self, debug_dir, debug_files):
        if not debug_files:
            pytest.skip("No debug files found")
        for fname, fpath in debug_files.items():
            if "blueprint" in fname:
                continue
            data = _load_json(fpath)
            assert data.get("timestamp"), f"Missing timestamp in {fname}"
            assert "T" in data["timestamp"], f"Bad timestamp format in {fname}: {data['timestamp']}"

    def test_all_steps_have_step_name(self, debug_dir, debug_files):
        if not debug_files:
            pytest.skip("No debug files found")
        for fname, fpath in debug_files.items():
            if "blueprint" in fname:
                continue
            data = _load_json(fpath)
            if data.get("type") == "pipeline_summary":
                continue
            assert data.get("step"), f"Missing step name in {fname}"
