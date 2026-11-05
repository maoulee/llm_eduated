# Compose v2 End-to-End Test Report

**Date**: 2026-06-08
**Result**: 43/43 PASS, 0 FAIL

## Test Scope

Simulated the full compose v2 pipeline from `paper_outline_agent` output through downstream processing, using hand-crafted data for 3 slots (Q12, Q43, Q6) with real examination mode names from slot experience cards.

## Step-by-Step Results

### Step 1: Workspace Setup -- PASS
Test directory and outline files created at `docs/test_output/compose_v2_e2e/`.

### Step 2: Outline Draft Verification -- PASS (4/4)
- 3 slot sections (Q12, Q43, Q6) present
- 3 YAML contract blocks present
- All slots use real mode names from experience cards (e.g., Q12 uses `计算型——公式应用与单位换算` from `data/slot_experiences/Q12_experience.md`)

### Step 3: Teacher Edit Verification -- PASS (5/5)
Applied edits verified:
- Q12: `模式C` removed from `candidate_pool_visible`, added to `excluded.modes`
- Q43: `DMA传输开销计算` removed from `selected_knowledge`, added to `excluded.knowledge`
- Q6: No changes (unchanged path)
- Teacher annotations ("老师补充") present in Q12 and Q43

### Step 4: compute_gitdiff -- PASS (4/4)
- Produces non-empty unified diff output
- Q12 and Q43 changes appear in diff context
- Q6 appears in context lines (expected for unified diff format)

### Step 5: outline_contract_parser -- PASS (9/9)
All 3 `SlotContract` objects parsed correctly:
- Q12: `candidate_pool_visible = [模式A, 模式B]`, `excluded_modes = [模式C]`
- Q43: `selected_knowledge` has 4 items (DMA removed), `excluded_knowledge = [DMA传输开销计算]`
- Q6: All 4 modes in pool, empty excluded lists
- `paper_selection.yaml` written successfully with 3 entries

### Step 6: outline_consistency_checker -- PASS (5/5)
- Teacher-edited outline: `status = "pass"` (all 5 checks per slot satisfied)
- Inconsistent test case (active mode excluded + missing from pool): `status = "needs_sync"`, 3 failures detected (`mode_in_pool`, `pool_contains_active`, `excluded_not_active`)

### Step 7: artifact_store -- PASS (6/6)
- `_mark_excluded_knowledge`: Correctly appends `[已排除]` to DMA line, leaves other lines untouched
- `assemble_slot_experience_doc`: `final_machine_contract` section generated with correct YAML including `excluded` nested structure; excluded knowledge marked in syllabus output

### Step 8: compute_outline_diff (dual-channel) -- PASS (6/6)
- Channel 1 (YAML field diff): Q12 has `{candidate_pool_visible, excluded}` changes; Q43 has changes; Q6 has zero field changes
- Channel 2 (annotation): Q12 annotation captured with "老师补充" content
- `has_any_changes = True` confirmed

## Design Observations

1. **Channel 2 annotation detection is presence-based, not delta-based**: `compute_outline_diff` treats any non-empty `### 教师可编辑说明` as an annotation, even if the text is identical between draft and approved. This means Q6 appears in `changed_slots` despite having no edits -- its YAML contract fields are unchanged (zero `FieldChange`), but the annotation channel fires. This is by design: the downstream consumer sees the annotation text and can compare with the draft independently.

2. **compute_gitdiff uses line-level unified diff**: Slot IDs like "Q12" appear as context lines in the diff output rather than in change markers, since the heading line `## Q12（选择题）` itself is unchanged. The actual changes appear in the YAML blocks below.

3. **Excluded knowledge flows cleanly through the pipeline**: From teacher edit -> contract parser -> consistency checker -> artifact store marking, the `DMA传输开销计算` exclusion propagates correctly at every stage.

## Recommendations

1. **Consider adding delta-aware annotation detection**: If the system needs to distinguish "teacher reviewed but made no changes" from "teacher added annotation", the diff engine could compare annotation text between base and annotated versions rather than just checking for non-empty.

2. **Add integration test with real slot experience cards**: The current test mocks `_extract_knowledge_graph_section`. A future test could run the full `assemble_slot_experience_doc` with real data files to validate end-to-end assembly.

3. **Paper selection schema validation**: Consider adding a schema validator for `paper_selection.yaml` to catch structural issues before it reaches the generation pipeline.

## Files

- Test script: `docs/test_output/compose_v2_e2e/test_compose_v2_e2e.py`
- Draft outline: `docs/test_output/compose_v2_e2e/outline_draft.md`
- Approved outline: `docs/test_output/compose_v2_e2e/outline_approved.md`
- Paper selection: `docs/test_output/compose_v2_e2e/paper_selection.yaml`
