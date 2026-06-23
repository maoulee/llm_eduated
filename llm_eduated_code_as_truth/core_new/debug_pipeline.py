"""PipelineDebugger — dump agent I/O to local files for post-hoc analysis."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional


class PipelineDebugger:
    """Lightweight debugger that persists each pipeline step's input/output to JSON."""

    def __init__(self, debug_dir: str):
        self.debug_dir = debug_dir
        os.makedirs(debug_dir, exist_ok=True)
        self._step_times: Dict[str, float] = {}

    def start_timer(self, key: str) -> None:
        self._step_times[key] = time.monotonic()

    def dump_step(
        self,
        slot_id: str,
        step: str,
        round_num: int,
        output: Any,
        timing_s: Optional[float] = None,
        *,
        input_data: Any = None,
    ) -> None:
        record = {
            "slot_id": slot_id,
            "step": step,
            "round": round_num,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "timing_s": round(timing_s, 2) if timing_s else None,
        }
        if input_data is not None:
            record["input"] = _safe_serialize(input_data)
        if output is not None:
            record["output"] = _safe_serialize(output)

        filename = f"{slot_id}_{step}_r{round_num}.json"
        filepath = os.path.join(self.debug_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)

    def dump_full_run(
        self,
        slot_id: str,
        final_question: Dict[str, Any],
        solver_result: Dict[str, Any],
        review: Dict[str, Any],
        total_time_s: float,
        rounds: int,
    ) -> None:
        record = {
            "slot_id": slot_id,
            "type": "pipeline_summary",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_time_s": round(total_time_s, 2),
            "rounds": rounds,
            "final_stem": final_question.get("stem", "")[:500],
            "solver_execs": solver_result.get("python_exec_count", 0),
            "review_status": review.get("status"),
            "review_quality": review.get("overall_quality"),
            "review_raw_text_length": len(review.get("_raw_text", "")),
        }
        filepath = os.path.join(self.debug_dir, f"{slot_id}_summary.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)


def _safe_serialize(obj: Any) -> Any:
    """Ensure object is JSON-serializable."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj]
    return str(obj)
