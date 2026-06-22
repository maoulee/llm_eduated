"""Outline consistency checker — verify human edits align with machine contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from compose.outline_contract_parser import SlotContract


@dataclass
class ConsistencyIssue:
    slot_id: str
    check: str
    status: str  # pass | fail
    reason: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class ConsistencyResult:
    status: str  # pass | needs_sync
    issues: list[ConsistencyIssue] = field(default_factory=list)


def check_outline_consistency(
    contracts: list[SlotContract],
    slot_experiences: dict[str, str],
) -> ConsistencyResult:
    """检查 5 项一致性。"""
    issues: list[ConsistencyIssue] = []

    for contract in contracts:
        active_mode = contract.active_selection.get("mode_id", "")
        selected_knowledge = contract.active_selection.get("selected_knowledge", [])
        if isinstance(selected_knowledge, str):
            selected_knowledge = [selected_knowledge]

        # 1. active_selection.mode_id 是否存在于候选池中
        issues.append(_check_mode_in_pool(contract, active_mode))

        # 2. selected_knowledge 是否非空
        issues.append(_check_knowledge_nonempty(contract, selected_knowledge))

        # 3. candidate_pool_visible 是否包含 active mode
        issues.append(_check_pool_contains_active(contract, active_mode))

        # 4. excluded_modes 是否不包含 active mode
        issues.append(_check_excluded_not_active(contract, active_mode))

        # 5. excluded_knowledge 是否不与 selected_knowledge 重叠
        issues.append(_check_no_knowledge_overlap(contract, selected_knowledge))

    failed = [i for i in issues if i.status == "fail"]
    return ConsistencyResult(
        status="needs_sync" if failed else "pass",
        issues=issues,
    )


def _check_mode_in_pool(contract: SlotContract, active_mode: str) -> ConsistencyIssue:
    if not active_mode:
        return ConsistencyIssue(contract.slot_id, "mode_in_pool", "pass", "no active mode to check")
    pool = contract.candidate_pool_visible
    if not pool or active_mode in pool:
        return ConsistencyIssue(contract.slot_id, "mode_in_pool", "pass", "mode in pool or pool empty")
    return ConsistencyIssue(
        contract.slot_id, "mode_in_pool", "fail",
        f"mode_id={active_mode!r} not in candidate_pool_visible",
        evidence=[f"pool={pool}"],
    )


def _check_knowledge_nonempty(contract: SlotContract, selected_knowledge: list) -> ConsistencyIssue:
    if selected_knowledge:
        return ConsistencyIssue(contract.slot_id, "knowledge_nonempty", "pass", "selected_knowledge present")
    return ConsistencyIssue(
        contract.slot_id, "knowledge_nonempty", "fail",
        "selected_knowledge is empty",
    )


def _check_pool_contains_active(contract: SlotContract, active_mode: str) -> ConsistencyIssue:
    if not active_mode:
        return ConsistencyIssue(contract.slot_id, "pool_contains_active", "pass", "no active mode")
    pool = contract.candidate_pool_visible
    if not pool or active_mode in pool:
        return ConsistencyIssue(contract.slot_id, "pool_contains_active", "pass", "active mode in pool")
    return ConsistencyIssue(
        contract.slot_id, "pool_contains_active", "fail",
        f"active mode {active_mode!r} missing from candidate_pool_visible",
        evidence=[f"pool={pool}"],
    )


def _check_excluded_not_active(contract: SlotContract, active_mode: str) -> ConsistencyIssue:
    if not active_mode:
        return ConsistencyIssue(contract.slot_id, "excluded_not_active", "pass", "no active mode")
    if active_mode not in contract.excluded_modes:
        return ConsistencyIssue(contract.slot_id, "excluded_not_active", "pass", "active mode not excluded")
    return ConsistencyIssue(
        contract.slot_id, "excluded_not_active", "fail",
        f"active mode {active_mode!r} is in excluded_modes",
        evidence=[f"excluded_modes={contract.excluded_modes}"],
    )


def _check_no_knowledge_overlap(contract: SlotContract, selected_knowledge: list) -> ConsistencyIssue:
    if not selected_knowledge or not contract.excluded_knowledge:
        return ConsistencyIssue(contract.slot_id, "no_knowledge_overlap", "pass", "no overlap possible")
    overlap = set(selected_knowledge) & set(contract.excluded_knowledge)
    if not overlap:
        return ConsistencyIssue(contract.slot_id, "no_knowledge_overlap", "pass", "no overlap")
    return ConsistencyIssue(
        contract.slot_id, "no_knowledge_overlap", "fail",
        f"selected and excluded knowledge overlap: {overlap}",
        evidence=[f"overlap={sorted(overlap)}"],
    )
