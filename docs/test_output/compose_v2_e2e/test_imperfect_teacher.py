"""Test outline consistency checker robustness against imperfect teacher edits.

6 scenarios covering edge cases where a teacher edits the outline imperfectly,
verifying that consistency_checker catches real issues and stays quiet on benign ones.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from compose.outline_consistency_checker import (
    ConsistencyIssue,
    ConsistencyResult,
    check_outline_consistency,
)
from compose.outline_contract_parser import SlotContract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_contract(
    slot_id: str = "Q6",
    question_type: str = "single_choice",
    score: int = 2,
    examination_mode: str = "closed_book",
    active_selection: dict | None = None,
    candidate_pool_visible: list[str] | None = None,
    excluded_modes: list[str] | None = None,
    excluded_knowledge: list[str] | None = None,
) -> SlotContract:
    return SlotContract(
        slot_id=slot_id,
        question_type=question_type,
        score=score,
        examination_mode=examination_mode,
        active_selection=active_selection or {},
        candidate_pool_visible=candidate_pool_visible or [],
        excluded_modes=excluded_modes or [],
        excluded_knowledge=excluded_knowledge or [],
    )


def _run(contract: SlotContract) -> ConsistencyResult:
    """Run checker with a single contract and empty experience map."""
    return check_outline_consistency([contract], {})


def _failed_checks(result: ConsistencyResult) -> list[str]:
    return [i.check for i in result.issues if i.status == "fail"]


def _passed_checks(result: ConsistencyResult) -> list[str]:
    return [i.check for i in result.issues if i.status == "pass"]


# ---------------------------------------------------------------------------
# Scenario 1: Teacher deleted candidate mode C but didn't update excluded
#   - candidate_pool_visible has no mode C
#   - excluded.modes also has no mode C
#   - active mode is B (which IS in pool)
#   Expected: all checks pass (mode C absence is irrelevant)
# ---------------------------------------------------------------------------

def test_scenario_1():
    contract = _make_contract(
        active_selection={
            "mode_id": "模式B",
            "selected_knowledge": ["树与二叉树转换", "左孩子右兄弟表示"],
        },
        candidate_pool_visible=["模式A", "模式B"],
        excluded_modes=[],
        excluded_knowledge=[],
    )
    result = _run(contract)
    failed = _failed_checks(result)
    assert result.status == "pass", (
        f"Scenario 1: expected pass, got {result.status}. "
        f"Failed checks: {failed}"
    )
    assert len(failed) == 0, f"Scenario 1: expected 0 failures, got {failed}"
    print("[PASS] Scenario 1: deleted mode C not in pool, no active conflict -- OK")


# ---------------------------------------------------------------------------
# Scenario 2: Teacher deleted the active mode from candidate pool
#   - active_selection.mode_id = 模式C
#   - candidate_pool_visible = [模式A, 模式B]  (no 模式C)
#   Expected: needs_sync -- mode_in_pool and pool_contains_active both fail
# ---------------------------------------------------------------------------

def test_scenario_2():
    contract = _make_contract(
        active_selection={
            "mode_id": "模式C",
            "selected_knowledge": ["树与二叉树转换"],
        },
        candidate_pool_visible=["模式A", "模式B"],
        excluded_modes=[],
        excluded_knowledge=[],
    )
    result = _run(contract)
    failed = _failed_checks(result)
    assert result.status == "needs_sync", (
        f"Scenario 2: expected needs_sync, got {result.status}"
    )
    assert "mode_in_pool" in failed, (
        f"Scenario 2: expected mode_in_pool to fail, failed={failed}"
    )
    assert "pool_contains_active" in failed, (
        f"Scenario 2: expected pool_contains_active to fail, failed={failed}"
    )
    print(f"[PASS] Scenario 2: active mode removed from pool -- detected "
          f"mode_in_pool + pool_contains_active failures")


# ---------------------------------------------------------------------------
# Scenario 3: Teacher changed human-readable text but machine contract not synced
#   - The machine contract still says mode_id=模式B
#   - Human text says "推荐模式D" (but we can't test this via SlotContract)
#   Expected: checker only validates machine contract internals.
#   Discovery: system does NOT cross-validate human text vs machine contract.
# ---------------------------------------------------------------------------

def test_scenario_3():
    # Machine contract is internally consistent (mode B is in pool)
    contract = _make_contract(
        active_selection={
            "mode_id": "模式B",
            "selected_knowledge": ["树与二叉树转换"],
        },
        candidate_pool_visible=["模式A", "模式B", "模式C"],
        excluded_modes=[],
        excluded_knowledge=[],
    )
    result = _run(contract)
    assert result.status == "pass", (
        f"Scenario 3: expected pass (machine-only check), got {result.status}"
    )
    print("[PASS] Scenario 3: human/machine mismatch invisible to checker")
    print("       DISCOVERY: system does NOT cross-validate human-readable text "
          "against machine contract. A teacher can change the prose recommendation "
          "without the checker noticing.")


# ---------------------------------------------------------------------------
# Scenario 4: Teacher deleted a knowledge point from selected but didn't add to excluded
#   - selected_knowledge = ["树与二叉树转换"]
#   - "左孩子右兄弟表示" is gone from selected
#   - excluded.knowledge does NOT contain "左孩子右兄弟表示"
#   Expected: pass -- deletion from selected is not enforced to be in excluded
# ---------------------------------------------------------------------------

def test_scenario_4():
    contract = _make_contract(
        active_selection={
            "mode_id": "模式A",
            "selected_knowledge": ["树与二叉树转换"],
        },
        candidate_pool_visible=["模式A", "模式B"],
        excluded_modes=[],
        excluded_knowledge=[],
    )
    result = _run(contract)
    assert result.status == "pass", (
        f"Scenario 4: expected pass, got {result.status}. "
        f"Failed: {_failed_checks(result)}"
    )
    print("[PASS] Scenario 4: knowledge point removed from selected without "
          "excluded entry -- checker stays quiet, as expected")


# ---------------------------------------------------------------------------
# Scenario 5: Teacher put same knowledge point in both selected and excluded
#   - selected_knowledge contains "KMP"
#   - excluded_knowledge also contains "KMP"
#   Expected: needs_sync -- no_knowledge_overlap fails
# ---------------------------------------------------------------------------

def test_scenario_5():
    contract = _make_contract(
        active_selection={
            "mode_id": "模式A",
            "selected_knowledge": ["KMP"],
        },
        candidate_pool_visible=["模式A"],
        excluded_modes=[],
        excluded_knowledge=["KMP"],
    )
    result = _run(contract)
    failed = _failed_checks(result)
    assert result.status == "needs_sync", (
        f"Scenario 5: expected needs_sync, got {result.status}"
    )
    assert "no_knowledge_overlap" in failed, (
        f"Scenario 5: expected no_knowledge_overlap to fail, failed={failed}"
    )
    print(f"[PASS] Scenario 5: knowledge in both selected and excluded -- "
          f"no_knowledge_overlap correctly detected")


# ---------------------------------------------------------------------------
# Scenario 6: Excluded modes contain ALL candidates (extreme contradiction)
#   - candidate_pool_visible = [模式C]
#   - excluded_modes = [模式C]
#   - active_selection.mode_id = 模式C
#   Expected: multiple failures -- excluded_not_active fails at minimum
#   Also: mode_in_pool and pool_contains_active pass (mode C is technically in pool)
# ---------------------------------------------------------------------------

def test_scenario_6():
    contract = _make_contract(
        active_selection={
            "mode_id": "模式C",
            "selected_knowledge": ["树与二叉树转换"],
        },
        candidate_pool_visible=["模式C"],
        excluded_modes=["模式C"],
        excluded_knowledge=[],
    )
    result = _run(contract)
    failed = _failed_checks(result)
    assert result.status == "needs_sync", (
        f"Scenario 6: expected needs_sync, got {result.status}"
    )
    assert "excluded_not_active" in failed, (
        f"Scenario 6: expected excluded_not_active to fail, failed={failed}"
    )
    # mode_in_pool and pool_contains_active should still pass (C is in pool)
    assert "mode_in_pool" not in failed, (
        f"Scenario 6: mode_in_pool should pass (C is in pool), but it failed"
    )
    assert "pool_contains_active" not in failed, (
        f"Scenario 6: pool_contains_active should pass (C is in pool), but it failed"
    )
    print(f"[PASS] Scenario 6: all candidates excluded + active conflict -- "
          f"excluded_not_active detected, {len(failed)} total failures: {failed}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scenarios = [
        ("Scenario 1: deleted candidate mode not in pool", test_scenario_1),
        ("Scenario 2: active mode removed from pool", test_scenario_2),
        ("Scenario 3: human/machine text mismatch", test_scenario_3),
        ("Scenario 4: deleted knowledge not in excluded", test_scenario_4),
        ("Scenario 5: knowledge in selected AND excluded", test_scenario_5),
        ("Scenario 6: all candidates excluded (extreme)", test_scenario_6),
    ]

    passed = 0
    failed = 0
    findings = []

    print("=" * 70)
    print("Imperfect Teacher Edit Robustness Test")
    print("=" * 70)
    print()

    for name, fn in scenarios:
        print(f"--- {name} ---")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {name}: {type(e).__name__}: {e}")
            failed += 1
        print()

    # Collect findings
    findings.append(
        "1. Scenario 3 discovery: The consistency checker ONLY validates the "
        "machine contract (YAML block). It does NOT cross-validate human-readable "
        "prose (e.g. 'current recommendation') against the machine contract. "
        "If a teacher updates the prose but not the YAML, the mismatch is invisible. "
        "RECOMMENDATION: Consider adding a human/machine cross-validation check, "
        "or at minimum a warning when prose mentions mode IDs not in active_selection."
    )
    findings.append(
        "2. Scenario 4 finding: Deleting a knowledge point from selected_knowledge "
        "without adding it to excluded is silently accepted. This is correct behavior "
        "(excluded is for explicit opt-out, not automatic audit trail), but teachers "
        "should be aware that previously-selected knowledge points can disappear "
        "without trace."
    )

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Passed:  {passed}/{len(scenarios)}")
    print(f"  Failed:  {failed}/{len(scenarios)}")
    print()
    print("Findings & Recommendations:")
    for f in findings:
        print(f"  {f}")
    print()

    if failed > 0:
        print("OVERALL: FAIL -- some scenarios did not produce expected results")
        sys.exit(1)
    else:
        print("OVERALL: PASS -- consistency checker behaves as expected in all scenarios")
        sys.exit(0)


if __name__ == "__main__":
    main()
