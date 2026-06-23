"""Pipeline resume utilities — load debug dumps and replay from a specific stage."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Stage ordering for prerequisite resolution
STAGE_ORDER = [
    "design", "options", "gate", "solve", "verify",
    "format", "rubric", "final_review", "final_fixer",
]

# What each resume-from stage requires as prerequisites
STAGE_PREREQUISITES = {
    "gate":            ["design"],
    "solve":           ["design"],
    "verify":          ["design", "solve"],
    "format":          ["design", "solve"],
    "rubric":          ["design", "solve", "format"],
    "final_review":    ["design", "solve", "format"],
    "final_fixer":     ["design", "solve", "format", "final_review"],
    "summary":         ["design", "solve", "format"],
    "consistency":     ["design", "solve", "format"],
}


def load_debug_state(
    debug_dir: str,
    slot_id: str,
    resume_from: str,
) -> Dict[str, Any]:
    """Load pipeline state from debug dump JSON files.

    Args:
        debug_dir: Path to the debug dump directory (e.g. debug/Q43_20260531_xxx)
        slot_id: Slot identifier (e.g. "Q43")
        resume_from: Stage name to resume from (determines which dumps to load)

    Returns:
        Dict mapping step names to their loaded output data.
    """
    state: Dict[str, Any] = {}

    prerequisites = STAGE_PREREQUISITES.get(resume_from, ["design", "solve", "format"])

    for step in prerequisites:
        dump = _load_latest_dump(debug_dir, slot_id, step)
        if dump:
            state[step] = dump
            logger.info("Loaded %s from debug dump (round %d)", step, dump.get("_round", 0))
        else:
            logger.warning("No debug dump found for step=%s slot=%s", step, slot_id)

    # Also load summary if available
    summary_file = os.path.join(debug_dir, f"{slot_id}_summary.json")
    if os.path.exists(summary_file):
        with open(summary_file, "r", encoding="utf-8") as f:
            state["pipeline_summary"] = json.load(f)

    return state


def _load_latest_dump(
    debug_dir: str,
    slot_id: str,
    step: str,
) -> Optional[Dict[str, Any]]:
    """Load the latest (highest round) dump for a given step."""
    candidates: List[tuple] = []
    for fname in os.listdir(debug_dir):
        if fname.startswith(f"{slot_id}_{step}_r") and fname.endswith(".json"):
            try:
                round_num = int(fname.split("_r")[1].split(".")[0])
                candidates.append((round_num, fname))
            except (ValueError, IndexError):
                continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    latest = candidates[0][1]

    filepath = os.path.join(debug_dir, latest)
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    output = raw.get("output", {})
    output["_round"] = candidates[0][0]
    output["_timestamp"] = raw.get("timestamp", "")
    output["_timing_s"] = raw.get("timing_s")
    return output


def rebuild_blackboard_state(
    state: Dict[str, Any],
    is_sc: bool,
) -> Dict[str, Any]:
    """Convert loaded debug state into the format expected by pipeline.run() resume_state.

    Maps dump outputs to the variable names used in the pipeline's run() method.
    """
    resume: Dict[str, Any] = {"is_sc": is_sc}

    if "design" in state:
        resume["design"] = state["design"]
    if "options" in state:
        resume["options"] = state["options"]
    if "solve" in state:
        resume["solver_dict"] = state["solve"]
    if "format" in state:
        resume["solution"] = state["format"]
    if "rubric" in state:
        resume["rubric"] = state["rubric"]
    if "gate" in state:
        resume["gate_result"] = state["gate"]
    if "verify" in state:
        resume["verify_result"] = state["verify"]
        resume["review"] = state["verify"]
    if "final_review" in state:
        resume["final_review"] = state["final_review"]

    return resume
