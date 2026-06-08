# Outline Schema v2 Specification

## Overview

Outline v2 extends the existing outline format to support **human-editable mode selection** while maintaining **machine-parsable contracts**. Each question (slot) in the outline now contains 4 sections:

1. **当前推荐** (Recommended) — Human-readable recommendation with mode, knowledge points, and rationale
2. **候选替换池** (Candidate Pool) — Human-readable list of 4 alternative modes for teacher selection
3. **教师可编辑说明** (Editable Description) — Natural language description for teachers
4. **机器选择契约** (Machine Contract) — YAML code block with structured data for system parsing

## Per-Question Structure

Each question (`## Qxx`) MUST contain these 4 subsections in order:

### 1. 当前推荐

Human-readable section describing:
- Active examination mode (mode name)
- Selected knowledge points
- Rationale for this recommendation

**Example:**
```markdown
### 当前推荐

- **考察模式**: 逻辑推理型——过程映射与逆向分析
- **核心知识点**: 树与二叉树转换、左孩子右兄弟表示、根结点边界处理
- **推荐理由**: 该模式在Q6题位出现频率30%，结合K3逻辑推演，适合考察学生对树转换机制的深度理解
```

### 2. 候选替换池

Human-readable list of 4 alternative modes. Teachers can delete modes they don't want to test.

**Example:**
```markdown
### 候选替换池

- **模式A**: 概念辨析型——性质与边界判定（适合考察哈夫曼树性质、前缀编码定义）
- **模式B**: 逻辑推理型——过程映射与逆向分析（适合考察树转换、DFS/BFS机制）
- **模式C**: 机制分析型——特定状态下的极值计算（适合考察KMP算法、复杂度分析）
- **模式D**: 组合判断型——多命题综合辨析（适合考察BST操作性质、复杂算法行为）
```

**Teacher Edit Behavior:**
- Teacher can delete entire mode lines to exclude them
- Teacher edits in this section are informational only
- **System does NOT parse this section** — it's for human readability

### 3. 教师可编辑说明

Free-form natural language section for teachers to add notes, constraints, or preferences.

**Example:**
```markdown
### 教师可编辑说明

本题重点考察树与二叉树转换的边界条件处理。需要注意根结点在转换中的特殊性（无兄弟但在二叉树中无右孩子）。
```

### 4. 机器选择契约

YAML code block containing the structured contract that the system parses.

**Required Fields:**

```yaml
slot_id: Q6
question_type: single_choice
score: 2
target_subject: DS
target_family: 数据结构 > 树与二叉树
primary_target_name: 树转二叉树后的结点性质推断
target_difficulty: 3
k_target: K3
examination_mode: 逻辑推理型——过程映射与逆向分析

active_selection:
  mode_id: 模式B
  mode_name: 逻辑推理型——过程映射与逆向分析
  selected_knowledge:
    - 树与二叉树转换
    - 左孩子右兄弟表示
    - 根结点边界处理

candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D

excluded:
  modes: []
  knowledge: []
```

**Field Definitions:**

| Field | Type | Description |
|-------|------|-------------|
| `slot_id` | string | Question slot identifier (e.g., "Q6") |
| `question_type` | string | Question type: "single_choice" or "comprehensive" |
| `score` | int | Point value (default: 2 for single-choice, 10-11 for comprehensive) |
| `target_subject` | string | Subject code: "DS", "CO", "OS", "CN" |
| `target_family` | string | Knowledge family path with ">" separator |
| `primary_target_name` | string | Primary learning objective name |
| `target_difficulty` | int | Difficulty level 1-5 |
| `k_target` | string | K-radar target: K1-K5 |
| `examination_mode` | string | Full examination mode name (must match template exactly) |
| `active_selection` | dict | Currently active selection |
| `active_selection.mode_id` | string | Mode identifier (e.g., "模式B") |
| `active_selection.mode_name` | string | Full mode name |
| `active_selection.selected_knowledge` | list[str]| Selected knowledge points for this mode |
| `candidate_pool_visible` | list[str]| List of visible mode IDs (e.g., ["模式A", "模式B"]) |
| `excluded.modes` | list[str]| Excluded mode IDs (teacher deleted from candidate pool) |
| `excluded.knowledge` | list[str]| Excluded knowledge points (teacher deleted from active) |

## Teacher Editing Rules

### Deleting a Mode from Candidate Pool

When teacher deletes a mode from **候选替换池**:
1. They remove the entire line for that mode (e.g., `- **模式C**: ...`)
2. System detects the deletion via diff
3. System adds the mode ID to `excluded.modes` in the YAML contract
4. System sets `needs_sync` flag for downstream synchronization

### Deleting Knowledge from Active Selection

When teacher deletes a knowledge point from **当前推荐**:
1. They remove the knowledge point line
2. System detects the deletion via diff
3. System adds the knowledge point to `excluded.knowledge` in the YAML contract
4. System sets `needs_sync` flag for downstream synchronization

### System Parsing Behavior

- **System ONLY parses** the YAML contract in `### 机器选择契约`
- **System does NOT guess** from teacher's natural language
- If teacher edits natural language but NOT the YAML contract, system uses the YAML as source of truth
- Diff/revision logic detects changes between base outline and annotated outline

## Backward Compatibility

v1 outlines (without `active_selection`, `candidate_pool_visible`, `excluded`) continue to work:
- New fields use default values (empty list/dict)
- Parsing logic gracefully handles missing fields
- Existing compose pipeline remains functional

## Full Example

See `docs/specs/outline_example_Q6.md` for a complete Q6 example in v2 format.
