"""K-radar data extraction: read 5D cognitive dimension scores from data sources.

Provides three data paths:
  1. Slot experience card K值锚点 (highest priority)
  2. Question experience file aggregation (medium priority)
  3. Heuristic fallback based on examination mode (lowest priority)

Usage:
    from compose.k_radar_reader import resolve_k_radar
    k_radar, source = resolve_k_radar(slot_id="Q14")
    # → ({"K1": 3, "K2": 3, "K3": 2, "K4": 4, "K5": 1}, "experience_card")
"""

from __future__ import annotations

import math
import re
from pathlib import Path

# ── Regex patterns ──────────────────────────────────────────────

# Slot experience card: "- **K1**: 众数=3 [2, 4]"
_RE_SLOT_K = re.compile(r"\*\*K(\d)\*\*:\s*众数=(\d)")

# Question experience file: "- **K1 = 3**: 评分理由..."
_RE_QUESTION_K = re.compile(r"\*\*K(\d)\s*=\s*(\d)")

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── K1.1: Slot experience card reader ───────────────────────────

def read_slot_k_radar(slot_id: str, data_dir: str | Path = "data/slot_experiences") -> dict[str, int]:
    """Read 5D K-radar from slot experience card's K值锚点 section.

    Parses format: - **K1**: 众数=3 [2, 4]

    Returns:
        dict like {"K1": 3, "K2": 1, "K3": 1, "K4": 2, "K5": 3}
        Empty dict if file not found or no K data.
    """
    exp_path = _PROJECT_ROOT / data_dir / f"{slot_id}_experience.md"
    if not exp_path.exists():
        return {}

    text = exp_path.read_text(encoding="utf-8")
    matches = _RE_SLOT_K.findall(text)
    if not matches:
        return {}

    result = {}
    for dim_str, val_str in matches:
        result[f"K{dim_str}"] = int(val_str)
    return result


# ── K1.2: Question experience file aggregator ───────────────────

def read_question_k_radar(question_path: str | Path) -> dict[str, int]:
    """Read K-radar from a single question experience file.

    Parses format: - **K1 = 3**: 评分理由...
    """
    path = Path(question_path)
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    matches = _RE_QUESTION_K.findall(text)
    if not matches:
        return {}

    result = {}
    for dim_str, val_str in matches:
        result[f"K{dim_str}"] = int(val_str)
    return result


def aggregate_question_k_radar(
    question_files: list[str | Path],
) -> dict[str, int]:
    """Aggregate K-radar from multiple question experience files.

    Takes the average of each K dimension across all files, rounded to int.

    Returns:
        dict like {"K1": 2, "K2": 4, "K3": 1, "K4": 3, "K5": 1}
        Empty dict if no valid data found.
    """
    if not question_files:
        return {}

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}

    for qf in question_files:
        k_data = read_question_k_radar(qf)
        if not k_data:
            continue
        for dim, val in k_data.items():
            sums[dim] = sums.get(dim, 0.0) + val
            counts[dim] = counts.get(dim, 0) + 1

    if not sums:
        return {}

    # Average and round
    return {dim: round(sums[dim] / counts[dim]) for dim in sums}


# ── K1.3: Heuristic fallback ───────────────────────────────────

# Simplified heuristic mapping based on examination mode keywords
_HEURISTIC_RULES: list[tuple[list[str], dict[str, int]]] = [
    # (keywords, default radar)
    (["概念辨析", "定义", "辨析", "判断正误", "特性"], {"K1": 4, "K2": 1, "K3": 1, "K4": 3, "K5": 1}),
    (["公式", "代入", "单步", "一步推导"], {"K1": 1, "K2": 4, "K3": 1, "K4": 2, "K5": 1}),
    (["多步", "推演", "流程", "模拟", "时空图"], {"K1": 1, "K2": 2, "K3": 4, "K4": 2, "K5": 1}),
    (["陷阱", "组合", "综合分析", "多知识点", "交叉"], {"K1": 2, "K2": 2, "K3": 2, "K4": 4, "K5": 2}),
    (["综合运用", "设计", "开放", "方案设计"], {"K1": 1, "K2": 2, "K3": 2, "K4": 3, "K5": 4}),
]

# Default radar for unknown modes
_DEFAULT_RADAR: dict[str, int] = {"K1": 2, "K2": 3, "K3": 2, "K4": 2, "K5": 1}


def estimate_k_radar_heuristic(
    examination_mode: str = "",
    difficulty_rationale: str = "",
) -> dict[str, int]:
    """Estimate K-radar from examination mode and rationale using heuristic rules.

    This is a fallback when no data sources are available. It uses keyword matching
    to produce a reasonable 5D profile.

    Returns:
        dict like {"K1": 2, "K2": 4, "K3": 1, "K4": 3, "K5": 1}
    """
    text = f"{examination_mode} {difficulty_rationale}"

    for keywords, radar in _HEURISTIC_RULES:
        if any(kw in text for kw in keywords):
            return dict(radar)

    return dict(_DEFAULT_RADAR)


# ── K1.4: Unified entry point ──────────────────────────────────

def resolve_k_radar(
    slot_id: str | None = None,
    question_files: list[str | Path] | None = None,
    examination_mode: str = "",
    difficulty_rationale: str = "",
) -> tuple[dict[str, int], str]:
    """Resolve K-radar from available data sources, by priority.

    Priority:
      1. Slot experience card K值锚点 → source="experience_card"
      2. Question experience file aggregation → source="question_aggregate"
      3. Heuristic estimation → source="heuristic"

    Returns:
        (k_radar_dict, source_str)
        k_radar_dict is like {"K1": 3, "K2": 3, "K3": 2, "K4": 4, "K5": 1}
    """
    # Priority 1: Slot experience card
    if slot_id:
        k_radar = read_slot_k_radar(slot_id)
        if k_radar:
            return k_radar, "experience_card"

    # Priority 2: Question file aggregation
    if question_files:
        k_radar = aggregate_question_k_radar(question_files)
        if k_radar:
            return k_radar, "question_aggregate"

    # Priority 3: Heuristic fallback
    k_radar = estimate_k_radar_heuristic(examination_mode, difficulty_rationale)
    return k_radar, "heuristic"


def compute_k_dominant(k_radar: dict[str, int]) -> str:
    """Return the K dimension with the highest score.

    If tied, returns the first one in K1-K5 order.
    Returns "K3" as default if k_radar is empty.
    """
    if not k_radar:
        return "K3"
    return max(k_radar, key=lambda k: k_radar.get(k, 0))
