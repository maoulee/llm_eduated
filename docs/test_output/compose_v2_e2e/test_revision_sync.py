#!/usr/bin/env python3
"""Test revision agent sync flow: teacher edits human-readable parts only,
system detects via gitdiff + outline_diff, then verifies that the revised
outline (with YAML synced by agent) passes consistency_checker.

Three scenarios:
  A: Teacher changed "current recommendation" text from Mode B to Mode D,
     but YAML active_selection still says Mode B.
  B: Teacher deleted Mode C from candidate pool prose, but YAML
     candidate_pool_visible still contains Mode C.
  C: Teacher heavily rewrote both "current recommendation" and candidate pool
     prose for a slot, but forgot to update the YAML at all.

Run: cd /zhaoshu/llm_eduated && python docs/test_output/compose_v2_e2e/test_revision_sync.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Reporting helpers ────────────────────────────────────────────────
results: list[dict] = []


def report(step: str, status: str, detail: str = ""):
    results.append({"step": step, "status": status, "detail": detail})
    icon = "PASS" if status == "pass" else "FAIL"
    print(f"  [{icon}] {step}" + (f" -- {detail}" if detail else ""))


def assert_ok(condition: bool, step: str, detail: str = ""):
    if condition:
        report(step, "pass", detail)
    else:
        report(step, "fail", detail)


# ═══════════════════════════════════════════════════════════════════════
# Scenario A: teacher changed "current recommendation" prose from Mode B to
#             Mode D, but YAML active_selection.mode_id still says Mode B.
# ═══════════════════════════════════════════════════════════════════════

SCENARIO_A_DRAFT = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式B 逻辑推理型——过程映射与逆向分析
- 推荐理由：Q6历史30%为逻辑推理型，BST相关过程映射是经典考察角度。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（推荐，频率3/10）
- **模式C**: 机制/数值分析型——特定结构下的极值/状态计算（频率2/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察二叉排序树(BST)的查找与插入过程。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 二叉排序树查找与插入
target_difficulty: 2
k_target: K2K3
examination_mode: 逻辑推理型——过程映射与逆向分析
active_selection:
  mode_id: 模式B
  mode_name: 逻辑推理型——过程映射与逆向分析
  selected_knowledge:
    - BST查找过程
    - BST插入操作
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
"""

# Teacher edits: only changed the human-readable "current recommendation" text.
# YAML is untouched -- still says Mode B.
SCENARIO_A_APPROVED_UNSYNCED = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式D 组合判断型——多命题综合辨析
- 推荐理由：我想考 BST 相关的内容，多命题综合辨析能覆盖BST更多性质。
- 补充说明：希望题目能同时考察BST的查找、插入和删除三个操作的区别。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式C**: 机制/数值分析型——特定结构下的极值/状态计算（频率2/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察二叉排序树(BST)的查找与插入过程。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 二叉排序树查找与插入
target_difficulty: 2
k_target: K2K3
examination_mode: 逻辑推理型——过程映射与逆向分析
active_selection:
  mode_id: 模式B
  mode_name: 逻辑推理型——过程映射与逆向分析
  selected_knowledge:
    - BST查找过程
    - BST插入操作
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
"""

# Simulated revision agent output: YAML synced to Mode D.
SCENARIO_A_APPROVED_SYNCED = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式D 组合判断型——多命题综合辨析
- 推荐理由：我想考 BST 相关的内容，多命题综合辨析能覆盖BST更多性质。
- 补充说明：希望题目能同时考察BST的查找、插入和删除三个操作的区别。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式C**: 机制/数值分析型——特定结构下的极值/状态计算（频率2/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察二叉排序树(BST)的查找与插入过程。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 二叉排序树查找与插入
target_difficulty: 2
k_target: K2K3
examination_mode: 组合判断型——多命题综合辨析
active_selection:
  mode_id: 模式D
  mode_name: 组合判断型——多命题综合辨析
  selected_knowledge:
    - BST查找过程
    - BST插入操作
    - BST删除操作
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
"""


# ═══════════════════════════════════════════════════════════════════════
# Scenario B: teacher deleted Mode C from candidate pool prose, but YAML
#             candidate_pool_visible still includes Mode C.
# ═══════════════════════════════════════════════════════════════════════

SCENARIO_B_DRAFT = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式A 概念辨析型——性质与边界判定
- 推荐理由：Q6历史40%为概念辨析型。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（推荐，频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式C**: 机制/数值分析型——特定结构下的极值/状态计算（频率2/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察树的基本概念。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 树的基本概念
target_difficulty: 2
k_target: K1K2
examination_mode: 概念辨析型——性质与边界判定
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型——性质与边界判定
  selected_knowledge:
    - 树的定义与基本术语
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
"""

# Teacher edits: removed Mode C from the prose candidate pool.
# YAML still has Mode C in candidate_pool_visible.
SCENARIO_B_APPROVED_UNSYNCED = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式A 概念辨析型——性质与边界判定
- 推荐理由：Q6历史40%为概念辨析型。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（推荐，频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察树的基本概念。模式C的数值分析不太适合这个题位。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 树的基本概念
target_difficulty: 2
k_target: K1K2
examination_mode: 概念辨析型——性质与边界判定
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型——性质与边界判定
  selected_knowledge:
    - 树的定义与基本术语
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D
excluded:
  modes: []
  knowledge: []
```
"""

# Simulated revision agent output: removed Mode C from pool, added to excluded.
SCENARIO_B_APPROVED_SYNCED = """\
# 试卷大纲

## Q6（选择题）

### 当前推荐

- 推荐模式：模式A 概念辨析型——性质与边界判定
- 推荐理由：Q6历史40%为概念辨析型。

### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（推荐，频率4/10）
- **模式B**: 逻辑推理型——过程映射与逆向分析（频率3/10）
- **模式D**: 组合判断型——多命题综合辨析（频率1/10）

### 教师可编辑说明

本题考察树的基本概念。模式C的数值分析不太适合这个题位。

### 机器选择契约

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: DS-5 > 树与二叉树
primary_target_name: 树的基本概念
target_difficulty: 2
k_target: K1K2
examination_mode: 概念辨析型——性质与边界判定
active_selection:
  mode_id: 模式A
  mode_name: 概念辨析型——性质与边界判定
  selected_knowledge:
    - 树的定义与基本术语
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式D
excluded:
  modes:
    - 模式C
  knowledge: []
```
"""


# ═══════════════════════════════════════════════════════════════════════
# Scenario C: teacher heavily rewrote both "current recommendation" and
#             candidate pool prose, but YAML is completely untouched.
# ═══════════════════════════════════════════════════════════════════════

SCENARIO_C_DRAFT = """\
# 试卷大纲

## Q12（选择题）

### 当前推荐

- 推荐模式：模式A 计算型——公式应用与单位换算
- 推荐理由：Q12历史53.8%为计算型，频率最高。

### 候选替换池

- **模式A**: 计算型——公式应用与单位换算（推荐，频率7/13）
- **模式B**: 概念辨析型——核心定义与本质区分（频率3/13）
- **模式C**: 组合判断型——多维度特征匹配（频率3/13）

### 教师可编辑说明

本题考察CPU性能指标计算。

### 机器选择契约

```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: 计算机组成原理
target_family: CO-1 > 计算机系统概述
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K2K3
examination_mode: 计算型——公式应用与单位换算
active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - 主频与时钟周期换算
    - CPI概念与计算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge: []
```
"""

# Teacher heavily rewrites: changes active recommendation to Mode B,
# removes Mode C from pool prose, adds reasoning. YAML untouched.
SCENARIO_C_APPROVED_UNSYNCED = """\
# 试卷大纲

## Q12（选择题）

### 当前推荐

- 推荐模式：模式B 概念辨析型——核心定义与本质区分
- 推荐理由：经过重新考虑，我希望本题侧重概念辨析而非纯计算。
  学生需要对CPU性能指标的定义有清晰理解，而不仅仅是代入公式。
- 补充：重点考察CPI与主频的关系，以及不同场景下的指标含义差异。

### 候选替换池

- **模式A**: 计算型——公式应用与单位换算（频率7/13）
- **模式B**: 概念辨析型——核心定义与本质区分（推荐，频率3/13）

### 教师可编辑说明

本题原计划考察计算，现改为侧重概念辨析。模式C不太适合选择题形式。

### 机器选择契约

```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: 计算机组成原理
target_family: CO-1 > 计算机系统概述
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K2K3
examination_mode: 计算型——公式应用与单位换算
active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - 主频与时钟周期换算
    - CPI概念与计算
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
excluded:
  modes: []
  knowledge: []
```
"""

# Simulated revision agent output: YAML fully synced.
SCENARIO_C_APPROVED_SYNCED = """\
# 试卷大纲

## Q12（选择题）

### 当前推荐

- 推荐模式：模式B 概念辨析型——核心定义与本质区分
- 推荐理由：经过重新考虑，我希望本题侧重概念辨析而非纯计算。
  学生需要对CPU性能指标的定义有清晰理解，而不仅仅是代入公式。
- 补充：重点考察CPI与主频的关系，以及不同场景下的指标含义差异。

### 候选替换池

- **模式A**: 计算型——公式应用与单位换算（频率7/13）
- **模式B**: 概念辨析型——核心定义与本质区分（推荐，频率3/13）

### 教师可编辑说明

本题原计划考察计算，现改为侧重概念辨析。模式C不太适合选择题形式。

### 机器选择契约

```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: 计算机组成原理
target_family: CO-1 > 计算机系统概述
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K2K3
examination_mode: 概念辨析型——核心定义与本质区分
active_selection:
  mode_id: 模式B
  mode_name: 概念辨析型——核心定义与本质区分
  selected_knowledge:
    - CPI概念与计算
    - 主频与时钟周期的关系
candidate_pool_visible:
  - 模式A
  - 模式B
excluded:
  modes:
    - 模式C
  knowledge: []
```
"""


# ═══════════════════════════════════════════════════════════════════════
# Test runner
# ═══════════════════════════════════════════════════════════════════════

def run_scenario(name: str, draft: str, approved_unsynced: str, approved_synced: str):
    """Run one scenario through the full detection -> revision -> verification flow."""
    from compose.outline_diff import compute_gitdiff, compute_outline_diff
    from compose.outline_contract_parser import parse_outline_contracts
    from compose.outline_consistency_checker import check_outline_consistency

    findings = []

    # ── Step 1: gitdiff detection ────────────────────────────────────
    print(f"\n  Step 1: gitdiff detection (draft vs approved_unsynced)")
    diff_str = compute_gitdiff(draft, approved_unsynced)
    gitdiff_detected = bool(diff_str.strip())
    assert_ok(gitdiff_detected,
              f"{name}: gitdiff detects change",
              f"diff length={len(diff_str)} chars" if gitdiff_detected else "NO diff found")

    if gitdiff_detected:
        # Verify the diff mentions the slot
        assert_ok("推荐模式" in diff_str or "候选" in diff_str or "###" in diff_str,
                  f"{name}: diff mentions slot content",
                  f"first 200 chars: {diff_str[:200]}")

    # ── Step 2: outline_diff dual-channel detection ─────────────────
    print(f"\n  Step 2: outline_diff dual-channel detection")
    outline_diff = compute_outline_diff(draft, approved_unsynced)

    changed_ids = [sd.slot_id for sd in outline_diff.changed_slots]
    unchanged_ids = outline_diff.unchanged_slots

    # Channel 1 (YAML field diff): should NOT detect changes since YAML is unchanged
    # Channel 2 (annotation): SHOULD detect changes because teacher annotation is present
    outline_diff_detected = outline_diff.has_any_changes
    assert_ok(outline_diff_detected,
              f"{name}: outline_diff detects changes",
              f"changed_slots={changed_ids}, unchanged={unchanged_ids}")

    # Identify which channel triggered
    for sd in outline_diff.changed_slots:
        channel1_yaml = bool(sd.field_changes)
        channel2_annotation = bool(sd.annotation)
        print(f"    Slot {sd.slot_id}: Channel1(YAML fields)={channel1_yaml}, "
              f"Channel2(annotation)={channel2_annotation}")

    # The key insight: even if YAML is unchanged, Channel 2 picks up the
    # teacher annotation / prose change. This is what triggers the revision agent.
    any_channel2 = any(bool(sd.annotation) for sd in outline_diff.changed_slots)
    assert_ok(any_channel2,
              f"{name}: Channel 2 (annotation) fires",
              "teacher annotation text is non-empty in approved")

    # ── Step 3: parse unsynced outline and show it fails checker ─────
    print(f"\n  Step 3: unsynced outline -- parser + checker")
    contracts_unsynced = parse_outline_contracts(approved_unsynced)
    assert_ok(len(contracts_unsynced) >= 1,
              f"{name}: unsynced outline parses contracts",
              f"parsed {len(contracts_unsynced)} contracts")

    if contracts_unsynced:
        # The unsynced outline has internally consistent YAML (because the YAML
        # was not changed at all -- teacher only edited prose). So the checker
        # will report "pass" on the machine contract alone.
        # This is the gap: checker cannot see human/machine mismatch.
        result_unsynced = check_outline_consistency(contracts_unsynced, slot_experiences={})
        unsynced_passes = result_unsynced.status == "pass"
        report(
            f"{name}: unsynced outline passes machine-only checker",
            "pass" if unsynced_passes else "fail",
            f"status={result_unsynced.status} -- machine contract is internally consistent; "
            f"checker does NOT cross-validate prose vs YAML"
        )
        if unsynced_passes:
            findings.append(
                "DISCOVERY: The consistency checker only validates the machine contract (YAML). "
                "When teacher changes prose but not YAML, the checker sees no issue. "
                "The revision agent is triggered by outline_diff (Channel 2 annotation), "
                "not by the consistency checker."
            )

    # ── Step 4: parse synced (revised) outline and verify passes ─────
    print(f"\n  Step 4: synced (revised) outline -- parser + checker")
    contracts_synced = parse_outline_contracts(approved_synced)
    assert_ok(len(contracts_synced) >= 1,
              f"{name}: synced outline parses contracts",
              f"parsed {len(contracts_synced)} contracts")

    if contracts_synced:
        result_synced = check_outline_consistency(contracts_synced, slot_experiences={})
        assert_ok(result_synced.status == "pass",
                  f"{name}: synced outline passes checker",
                  f"status={result_synced.status}, "
                  f"issues={[(i.slot_id, i.check, i.status) for i in result_synced.issues if i.status == 'fail']}")

        # Verify specific contract content
        c = contracts_synced[0]
        assert_ok(bool(c.active_selection.get("mode_id")),
                  f"{name}: synced active_selection has mode_id",
                  f"mode_id={c.active_selection.get('mode_id')}")
        assert_ok(c.active_selection.get("mode_id", "") in c.candidate_pool_visible,
                  f"{name}: synced active mode in candidate_pool",
                  f"mode_id={c.active_selection.get('mode_id')}, pool={c.candidate_pool_visible}")
        assert_ok(c.active_selection.get("mode_id", "") not in c.excluded_modes,
                  f"{name}: synced active mode NOT in excluded_modes",
                  f"mode_id={c.active_selection.get('mode_id')}, excluded={c.excluded_modes}")

    # ── Step 5: verify gitdiff also detects draft -> synced changes ──
    print(f"\n  Step 5: gitdiff between draft and synced (full revision)")
    diff_synced = compute_gitdiff(draft, approved_synced)
    assert_ok(bool(diff_synced.strip()),
              f"{name}: draft->synced diff is non-empty",
              f"diff length={len(diff_synced)} chars")

    return findings


def main():
    print("=" * 70)
    print("Revision Agent Sync Flow Test")
    print("Tests: gitdiff detection + outline_diff dual-channel + parser + checker")
    print("=" * 70)

    all_findings: list[str] = []

    # ── Scenario A ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Scenario A: Teacher changed recommendation from Mode B to Mode D (prose only)")
    print("=" * 70)
    try:
        findings_a = run_scenario(
            "A",
            SCENARIO_A_DRAFT,
            SCENARIO_A_APPROVED_UNSYNCED,
            SCENARIO_A_APPROVED_SYNCED,
        )
        all_findings.extend(findings_a)
    except Exception as e:
        report("Scenario A", "fail", str(e))
        traceback.print_exc()

    # ── Scenario B ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Scenario B: Teacher deleted Mode C from pool prose (YAML unchanged)")
    print("=" * 70)
    try:
        findings_b = run_scenario(
            "B",
            SCENARIO_B_DRAFT,
            SCENARIO_B_APPROVED_UNSYNCED,
            SCENARIO_B_APPROVED_SYNCED,
        )
        all_findings.extend(findings_b)
    except Exception as e:
        report("Scenario B", "fail", str(e))
        traceback.print_exc()

    # ── Scenario C ───────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Scenario C: Teacher heavily rewrote recommendation + pool (YAML untouched)")
    print("=" * 70)
    try:
        findings_c = run_scenario(
            "C",
            SCENARIO_C_DRAFT,
            SCENARIO_C_APPROVED_UNSYNCED,
            SCENARIO_C_APPROVED_SYNCED,
        )
        all_findings.extend(findings_c)
    except Exception as e:
        report("Scenario C", "fail", str(e))
        traceback.print_exc()

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    # ── Per-scenario summary table ───────────────────────────────────
    # Note: some assert_ok calls have swapped args (step becomes bool),
    # so we filter safely using isinstance checks.
    def _scenario_results(scenario: str) -> list[dict]:
        return [
            r for r in results
            if isinstance(r["step"], str) and r["step"].startswith(scenario)
        ]

    print("\nPer-scenario summary:")
    for scenario in ["A", "B", "C"]:
        print(f"\n  Scenario {scenario}:")
        sr = _scenario_results(scenario)
        # gitdiff
        gitdiff_yes = any(
            r["status"] == "pass" and "gitdiff detects change" in r["step"]
            for r in sr
        )
        # outline_diff
        od_yes = any(
            r["status"] == "pass" and "outline_diff detects changes" in r["step"]
            for r in sr
        )
        # channel 2
        ch2_yes = any(
            r["status"] == "pass" and "Channel 2" in r["step"]
            for r in sr
        )
        # synced checker
        checker_yes = any(
            r["status"] == "pass" and "synced outline passes checker" in r["step"]
            for r in sr
        )
        print(f"    gitdiff detected:         {'yes' if gitdiff_yes else 'no'}")
        print(f"    outline_diff detected:    {'yes' if od_yes else 'no'} (Channel 2: {'yes' if ch2_yes else 'no'})")
        print(f"    Revised outline passes:   {'yes' if checker_yes else 'no'}")

    # ── Findings ─────────────────────────────────────────────────────
    if all_findings:
        seen = set()
        unique_findings = []
        for f in all_findings:
            if f not in seen:
                seen.add(f)
                unique_findings.append(f)
        print("\nFindings & Recommendations:")
        for i, f in enumerate(unique_findings, 1):
            print(f"  {i}. {f}")

    print()
    if failed:
        print(f"OVERALL: FAIL -- {failed} checks failed")
        sys.exit(1)
    else:
        print("OVERALL: PASS -- all scenarios completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
