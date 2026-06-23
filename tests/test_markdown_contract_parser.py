"""Tests for markdown_contract_parser — 12 robustness scenarios."""
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compose.markdown_contract_parser import (
    parse_outline_to_selection,
    scan_contract_blocks,
    load_yaml_contract,
    normalize_outline_slot,
    validate_outline_slot,
    ContractBlock,
)

# ── Fixtures ──────────────────────────────────────────────

OUTLINE_MARKER = """# 408模拟卷

## Q6（选择题）

### 当前推荐
推荐模式B

### 教师可编辑说明
老师补充：重点考左孩子右兄弟。

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q6 -->
```yaml
slot_id: Q6
question_type: single_choice
score: 2
examination_mode: 逻辑推理型——过程映射与逆向分析
active_selection:
  mode_id: 模式B
  mode_name: 逻辑推理型——过程映射与逆向分析
  selected_knowledge:
    - 树与二叉树转换
    - 左孩子右兄弟表示
candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式D
excluded:
  modes:
    - 模式C
  knowledge:
    - KMP next/nextval
```
<!-- CONTRACT:END slot=Q6 -->

## Q43（综合题）

### 教师可编辑说明

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q43 -->
```yaml
slot_id: Q43
question_type: comprehensive
score: 10
examination_mode: 综合分析型——多约束联立求解
active_selection:
  mode_id: 模式D
  mode_name: 综合分析型
  selected_knowledge:
    - 页面置换算法
    - 缺页率计算
candidate_pool_visible:
  - 模式B
  - 模式D
```
<!-- CONTRACT:END slot=Q43 -->
"""

OUTLINE_LEGACY = """# 408模拟卷

## Q6

### 教师可编辑说明
老师补充说明。

### 机器选择契约
```yaml
slot_id: Q6
question_type: single_choice
score: 2
examination_mode: 计算型——公式应用与单位换算
active_selection:
  mode_id: 模式A
  mode_name: 计算型
  selected_knowledge:
    - Cache命中率计算
candidate_pool_visible:
  - 模式A
  - 模式B
```
"""


# ── Test 1: Standard CONTRACT marker parsing ─────────────

def test_marker_format():
    r = parse_outline_to_selection(OUTLINE_MARKER)
    assert len(r.slots) == 2
    assert r.slots[0].question_type == "single_choice"
    assert r.slots[0].score == 2
    assert r.slots[0].examination_mode == "逻辑推理型——过程映射与逆向分析"
    assert r.slots[0].active_selection.get("mode_id") == "模式B"
    assert r.slots[0].excluded_modes == ["模式C"]
    assert "KMP" in r.slots[0].excluded_knowledge[0]
    assert "左孩子右兄弟" in r.slots[0].teacher_annotation
    assert r.slots[1].question_type == "comprehensive"
    assert r.slots[1].score == 10


# ── Test 2: Renamed heading doesn't affect parsing ───────

def test_renamed_heading():
    md = OUTLINE_MARKER.replace("## Q6（选择题）", "## 第6题 Q6（选择题）")
    r = parse_outline_to_selection(md)
    assert len(r.slots) == 2
    assert r.slots[0].slot_id == "Q6"


# ── Test 3: Multiple yaml blocks, only CONTRACT marker taken ──

def test_multiple_yaml_blocks():
    md = """# 408模拟卷

## Q6

### 当前推荐
推荐模式B

### 教师可编辑说明
老师补充。

Here is some example yaml that is NOT a contract:
```yaml
example: true
value: 42
```

<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q6 -->
```yaml
slot_id: Q6
question_type: single_choice
score: 2
examination_mode: 计算型
active_selection:
  mode_id: 模式A
  selected_knowledge:
    - Cache命中率
candidate_pool_visible:
  - 模式A
```
<!-- CONTRACT:END slot=Q6 -->
"""
    r = parse_outline_to_selection(md)
    assert len(r.slots) == 1
    assert r.slots[0].examination_mode == "计算型"


# ── Test 4: Missing slot_id → error ──────────────────────

def test_missing_slot_id():
    md = """# 408模拟卷
<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q6 -->
```yaml
question_type: single_choice
score: 2
examination_mode: 计算型
active_selection:
  mode_id: 模式A
  selected_knowledge:
    - Cache命中率
```
<!-- CONTRACT:END slot=Q6 -->
"""
    r = parse_outline_to_selection(md)
    errors = [i for i in r.validation.issues if i.severity == "error" and "slot_id" in i.check]
    assert len(errors) > 0


# ── Test 5: slot_id mismatch → warning ───────────────────

def test_slot_id_mismatch():
    block = ContractBlock(
        yaml_text="slot_id: Q99\nquestion_type: single_choice\nscore: 2",
        slot_id="Q6", source="marker",
    )
    loaded = load_yaml_contract(block)
    assert any("mismatch" in w for w in loaded.warnings)


# ── Test 7: selected_knowledge overlaps excluded → error ─

def test_knowledge_excluded_overlap():
    data = {
        "slot_id": "Q6",
        "question_type": "single_choice",
        "score": 2,
        "examination_mode": "计算型",
        "active_selection": {
            "mode_id": "模式A",
            "selected_knowledge": ["KMP", "Cache"],
        },
        "excluded": {"knowledge": ["KMP"]},
    }
    result = validate_outline_slot(data)
    errors = [i for i in result.issues if i.check == "knowledge_overlap"]
    assert len(errors) == 1
    assert errors[0].severity == "error"


# ── Test 8: comprehensive not defaulting to single_choice ─

def test_comprehensive_question_type():
    r = parse_outline_to_selection(OUTLINE_MARKER)
    comp = [s for s in r.slots if s.slot_id == "Q43"][0]
    assert comp.question_type == "comprehensive"


# ── Test 9: Teacher prose mentions KMP but YAML says tree → warning ──

def test_prose_yaml_mismatch_not_auto_fixed():
    # Parser does NOT auto-fix; YAML is authoritative
    md = OUTLINE_MARKER.replace(
        "老师补充：重点考左孩子右兄弟。",
        "建议改成考KMP算法。",
    )
    r = parse_outline_to_selection(md)
    q6 = r.slots[0]
    # YAML still says 树转换, not KMP
    assert "KMP" not in str(q6.active_selection.get("selected_knowledge", []))
    assert "树与二叉树转换" in q6.active_selection.get("selected_knowledge", [])
    # Teacher annotation preserved as-is
    assert "KMP" in q6.teacher_annotation


# ── Test 10: Legacy format still works + warning ──────────

def test_legacy_format():
    r = parse_outline_to_selection(OUTLINE_LEGACY)
    assert len(r.slots) == 1
    assert r.slots[0].question_type == "single_choice"
    has_legacy = any("legacy" in w.message for w in r.validation.warnings)
    assert has_legacy


# ── Test 11: YAML syntax error → error, not silent {} ────

def test_yaml_syntax_error():
    md = """# 408模拟卷
<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q6 -->
```yaml
slot_id: Q6
question_type: [broken yaml
```
<!-- CONTRACT:END slot=Q6 -->
"""
    r = parse_outline_to_selection(md)
    assert r.validation.status == "error"
    has_yaml_error = any("YAML syntax" in e.message for e in r.validation.errors)
    assert has_yaml_error
    assert len(r.slots) == 0


# ── Test 12: Deleted candidate pool but active retained ──

def test_deleted_pool_active_retained():
    md = """# 408模拟卷
<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot=Q6 -->
```yaml
slot_id: Q6
question_type: single_choice
score: 2
examination_mode: 计算型
active_selection:
  mode_id: 模式A
  selected_knowledge:
    - Cache命中率
candidate_pool_visible: []
```
<!-- CONTRACT:END slot=Q6 -->
"""
    r = parse_outline_to_selection(md)
    assert len(r.slots) == 1
    assert r.slots[0].candidate_pool_visible == []
    assert r.slots[0].active_selection.get("mode_id") == "模式A"
    # Should have warning about empty pool
    has_pool_warn = any("pool_empty" in i.check for i in r.validation.issues)
    assert has_pool_warn


# ── Test: Sidecar generation round-trip ───────────────────

def test_sidecar_roundtrip():
    r = parse_outline_to_selection(OUTLINE_MARKER)
    from compose.outline_contract_parser import write_paper_selection

    tmpdir = tempfile.mkdtemp()
    try:
        path = os.path.join(tmpdir, "paper_selection.yaml")
        write_paper_selection(r.slots, path)
        assert os.path.exists(path)

        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data) == 2
        assert data[0]["slot_id"] == "Q6"
        assert data[0]["question_type"] == "single_choice"
        assert data[1]["question_type"] == "comprehensive"

        # generate_runner can read sidecar
        from compose.generate_runner import _load_blueprint_map
        bp_map = _load_blueprint_map(tmpdir)
        assert "Q6" in bp_map
        assert bp_map["Q6"].question_type == "single_choice"
        assert bp_map["Q43"].question_type == "comprehensive"
    finally:
        shutil.rmtree(tmpdir)


# ── Test: Normalizer flattens aliases ─────────────────────

def test_normalizer():
    data = {
        "slot_id": "Q6",
        "difficulty_level": 4,
        "active_selection": {"mode": "模式B"},
        "excluded_knowledge": ["KMP"],
    }
    result = normalize_outline_slot(data)
    assert result.get("target_difficulty") == 4
    assert result.get("active_selection", {}).get("mode_id") == "模式B"
    assert "KMP" in result.get("excluded", {}).get("knowledge", [])
