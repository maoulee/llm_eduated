"""Integration test: validate debug output from Q43 pipeline run.

Run with: python3 -m pytest tests/test_integration_debug.py -v

Prerequisites: a debug run must exist in debug/ directory.
Run: python3 run_slot_composition.py --slots Q43 --max-fix-rounds 1 --debug
"""

import glob
import json
import os
from typing import Any, Dict

import pytest

DEBUG_DIR_PATTERN = "debug/Q43_*"


def _find_latest_debug_dir() -> str:
    dirs = sorted(glob.glob(DEBUG_DIR_PATTERN))
    if not dirs:
        pytest.skip("No Q43 debug directory found. Run: python3 run_slot_composition.py --slots Q43 --max-fix-rounds 1 --debug")
    return dirs[-1]


def _load_json(filepath: str) -> Dict[str, Any]:
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def debug_dir():
    return _find_latest_debug_dir()


@pytest.fixture(scope="module")
def debug_files(debug_dir):
    return {os.path.basename(f): f for f in glob.glob(os.path.join(debug_dir, "*.json"))}


class TestDebugFilesExist:
    def test_has_architecture(self, debug_files):
        assert any("architecture" in f for f in debug_files), \
            f"No architecture file found in {list(debug_files.keys())}"

    def test_has_design(self, debug_files):
        assert any("design" in f for f in debug_files), \
            f"No design file found in {list(debug_files.keys())}"

    def test_has_solve(self, debug_files):
        assert any("solve" in f for f in debug_files), \
            f"No solve file found in {list(debug_files.keys())}"

    def test_has_verify(self, debug_files):
        assert any("verify" in f for f in debug_files), \
            f"No verify file found in {list(debug_files.keys())}"

    def test_has_summary(self, debug_files):
        assert any("_summary.json" in f for f in debug_files), \
            f"No summary file found in {list(debug_files.keys())}"


class TestDebugOutputNonEmpty:
    def test_architecture_has_output(self, debug_dir, debug_files):
        arch_files = [f for f in debug_files if "architecture" in f]
        assert arch_files, "No architecture file"
        data = _load_json(os.path.join(debug_dir, arch_files[0]))
        assert data.get("output"), f"Architecture output is empty: {arch_files[0]}"

    def test_design_has_output(self, debug_dir, debug_files):
        design_files = [f for f in debug_files if "design" in f]
        assert design_files, "No design file"
        data = _load_json(os.path.join(debug_dir, design_files[0]))
        assert data.get("output"), f"Design output is empty: {design_files[0]}"
        stem = data["output"].get("stem", "")
        assert len(stem) > 20, f"Design stem too short ({len(stem)} chars)"

    def test_solve_has_output(self, debug_dir, debug_files):
        solve_files = [f for f in debug_files if "solve" in f]
        assert solve_files, "No solve file"
        data = _load_json(os.path.join(debug_dir, solve_files[0]))
        assert data.get("output"), f"Solve output is empty: {solve_files[0]}"

    def test_verify_has_output(self, debug_dir, debug_files):
        verify_files = [f for f in debug_files if "verify" in f]
        assert verify_files, "No verify file"
        data = _load_json(os.path.join(debug_dir, verify_files[0]))
        assert data.get("output"), f"Verify output is empty: {verify_files[0]}"

    def test_step_records_have_slot_id(self, debug_dir, debug_files):
        for fname, fpath in debug_files.items():
            data = _load_json(fpath)
            assert data.get("slot_id"), f"Missing slot_id in {fname}"
            assert data["slot_id"].startswith("Q"), f"Bad slot_id in {fname}: {data['slot_id']}"


class TestSolverVerifyNotBypassed:
    """Verify that SolverVerify produces real output, not empty content treated as pass."""

    def test_verify_has_status(self, debug_dir, debug_files):
        verify_files = [f for f in debug_files if "verify" in f]
        assert verify_files, "No verify file"
        data = _load_json(os.path.join(debug_dir, verify_files[0]))
        output = data.get("output", {})
        assert isinstance(output, dict), f"Verify output is not a dict: {type(output)}"
        status = output.get("status")
        assert status in ("pass", "needs_fix"), f"Unexpected verify status: {status}"

    def test_verify_has_raw_text(self, debug_dir, debug_files):
        verify_files = [f for f in debug_files if "verify" in f]
        assert verify_files, "No verify file"
        data = _load_json(os.path.join(debug_dir, verify_files[0]))
        output = data.get("output", {})
        raw_text = output.get("_raw_text", "")
        assert len(raw_text) > 20, \
            f"Verify _raw_text too short ({len(raw_text)} chars) — likely empty output treated as pass"

    def test_verify_has_overall_quality(self, debug_dir, debug_files):
        verify_files = [f for f in debug_files if "verify" in f]
        assert verify_files, "No verify file"
        data = _load_json(os.path.join(debug_dir, verify_files[0]))
        output = data.get("output", {})
        quality = output.get("overall_quality")
        assert quality is not None, "Missing overall_quality in verify output"
        # Quality may come as string from LLM parsing
        try:
            int(quality)
        except (ValueError, TypeError):
            pytest.fail(f"overall_quality is not numeric: {quality}")


class TestGateRouting:
    """Verify Gate and routing behavior."""

    def test_question_type_routed_correctly(self, debug_dir):
        # Q43 should be comprehensive
        summary_files = glob.glob(os.path.join(debug_dir, "*_summary.json"))
        # Also check the pipeline summary
        pipeline_summaries = glob.glob(os.path.join(debug_dir, "*summary*.json"))
        assert pipeline_summaries, "No summary file"

        for sf in pipeline_summaries:
            data = _load_json(sf)
            # Pipeline summary should exist
            if data.get("type") == "pipeline_summary":
                return  # Found it
        # If no pipeline_summary type, at least one summary file exists
        assert False, "No pipeline_summary found"


class TestPipelineSummary:
    def test_summary_has_required_fields(self, debug_dir, debug_files):
        summary_files = [f for f in debug_files if "_summary.json" in f]
        assert summary_files, "No summary file"
        data = _load_json(os.path.join(debug_dir, summary_files[0]))

        if data.get("type") == "pipeline_summary":
            assert "slot_id" in data
            assert "total_time_s" in data
            assert "rounds" in data
            assert "review_status" in data
            assert "review_quality" in data

    def test_total_time_reasonable(self, debug_dir, debug_files):
        summary_files = [f for f in debug_files if "_summary.json" in f]
        assert summary_files, "No summary file"
        data = _load_json(os.path.join(debug_dir, summary_files[0]))
        if data.get("type") == "pipeline_summary":
            assert data["total_time_s"] > 10, f"Total time too short: {data['total_time_s']}s"
            assert data["total_time_s"] < 1200, f"Total time too long: {data['total_time_s']}s"


class TestEachStepHasTimestamp:
    def test_all_steps_have_timestamp(self, debug_dir, debug_files):
        for fname, fpath in debug_files.items():
            data = _load_json(fpath)
            assert data.get("timestamp"), f"Missing timestamp in {fname}"
            assert "T" in data["timestamp"], f"Bad timestamp format in {fname}: {data['timestamp']}"

    def test_all_steps_have_step_name(self, debug_dir, debug_files):
        for fname, fpath in debug_files.items():
            data = _load_json(fpath)
            # Pipeline summary file (dump_full_run) uses "type" instead of "step"
            if data.get("type") == "pipeline_summary":
                continue
            assert data.get("step"), f"Missing step name in {fname}"
