# Doc Pipeline 优化 Spec v1 (2026-06-04)

## Context

Codex 完成了 6 项架构一致性修复。在此基础上，进行 6 项优化以提升可维护性、可观测性和类型安全。
测试基线：235 passed, 16 skipped。

## 优先级与依赖

```
O6 (experiments)  ← 无依赖，先做
O2 (manifest)     ← 无依赖
O5 (统一路由)      ← 无依赖
O1 (模块拆分)     ← O3/O4 的前置
O4 (类型合约)     ← O1 之后
O3 (run-scoping)  ← O1/O4 之后，最高风险
```

## O6: 移动根目录 test_*.py 到 experiments/

**目标**: 8 个实验脚本移出根目录，避免 `pytest` 根目录收集报错。

**操作**:
1. 创建 `experiments/` 目录
2. 移动 8 个文件，去掉 `test_` 前缀
3. 给缺少 `if __name__ == "__main__":` 的文件加 guard
4. 添加 `experiments/README.md`

**文件清单**:
| 原文件 | 新文件 |
|--------|--------|
| `test_adversarial_review.py` | `experiments/adversarial_review.py` |
| `test_analysis_ab.py` | `experiments/analysis_ab.py` |
| `test_glm_q43.py` | `experiments/glm_q43.py` |
| `test_hybrid_outline.py` | `experiments/hybrid_outline.py` |
| `test_model_compare.py` | `experiments/model_compare.py` |
| `test_question_ab.py` | `experiments/question_ab.py` |
| `test_sc_question_local.py` | `experiments/sc_question_local.py` |
| `test_self_adversarial.py` | `experiments/self_adversarial.py` |

**风险**: 低。无 import 依赖。tests/test_doc_pipeline.py 不受影响。
**验证**: `pytest tests/ -q` 仍 235 passed；`pytest .` 不再收集根目录实验脚本。

---

## O2: compose/ 增加 manifest.md

**目标**: 记录组卷快照元数据，generate 阶段可验证而非 glob 猜测。

**操作**:
1. `run_compose()` 末尾写入 `compose/manifest.md`
2. `load_compose_artifacts()` 优先读 manifest，无 manifest 时 fallback 到 glob
3. manifest 用 markdown table（用户偏好 MD 而非 JSON）

**manifest.md 格式**:
```markdown
# Compose Run Manifest
- run_id: 2026-06-04T14-30-00
- routing_profile: all_local
- total_slots: 2
- compose_time_s: 25.3

## Slots
| Slot | Mode | Difficulty | Assembled Chars | Hash |
|------|------|-----------|-----------------|------|
| Q12  | 计算型 | 3        | 14111          | a1b2c3d4 |
| Q13  | 概念型 | 3        | 11203          | e5f6g7h8 |
```

**风险**: 低。纯增量，向后兼容（无 manifest 时 glob fallback）。
**验证**: compose 后检查 manifest.md 存在且格式正确；generate 无 manifest 时仍工作。

---

## O5: 统一路由配置

**目标**: 消除 `provider_router.py` 与 `config/pipeline.yaml` 的重复配置，YAML 为唯一权威。

**操作**:
1. 删除 `provider_router.py` 中硬编码的 `AGENT_ROUTING` dict
2. 删除硬编码常量 `FALLBACK_PROVIDER`, `LOCAL_PROVIDER`, `HEALTH_CHECK_TTL`
3. 改为 lazy init 从 `PIPELINE_CONFIG` 读取
4. `set_routing_profile()` 简化为只更新 `_active_routing`
5. `doc_format` 等不在 YAML profile 中的角色，用 profile 的 `_default` 值

**关键文件**:
- `core_new/provider_router.py` — 主要改动
- `config/pipeline.yaml` — 无改动（已是权威）
- `core_new/doc_pipeline/pipeline_config.py` — fallback 默认值保留

**风险**: 中。注意循环 import（用 deferred import pattern）。Module load 时不能 eager 读 config。
**验证**: 所有 6 个 routing profile 切换正确；无 YAML 时 fallback 到硬编码默认值。

---

## O1: 拆分 run_slot_composition.py

**目标**: 1101 行 monolith → 5 个模块 + 入口 shim。

**模块划分**:
```
compose/
├── __init__.py              # re-export run_compose, run_generate, run_composition
├── compose_runner.py        # compose_paper, _compose_hybrid, _compose_local, outline parsing
├── artifact_store.py        # assemble_slot_experience_doc, _extract_* helpers
├── generate_runner.py       # run_generate, _generate_slots, _generate_doc, load_compose_artifacts
├── debug_runner.py          # _run_debug
└── cli.py                   # main, _filter_templates, _build_type_hint, run_composition
```

`run_slot_composition.py` → thin shim:
```python
from compose.cli import main
if __name__ == "__main__":
    asyncio.run(main())
```

**风险**: 中。需更新 tests/test_doc_pipeline.py 中 monkeypatch 路径。
**验证**: `pytest tests/ -q` 通过；CLI 各子命令 `--help` 正常。

---

## O4: 类型合约

**目标**: 用 dataclass 替代裸 dict，提供 IDE 补全和运行时验证。

**新增文件**: `core_new/doc_pipeline/contracts.py`

```python
@dataclass
class SlotBlueprint:
    slot_id: str
    target_subject: str = ""
    target_family: str = ""
    primary_target_name: str = ""
    target_difficulty: int = 3
    examination_mode: str = ""
    k_target: str = ""
    difficulty_rationale: str = ""
    question_type: str = "single_choice"

@dataclass
class ComposeArtifact:
    slot_id: str
    assembled_md: str
    assembled_path: str

@dataclass
class PipelineResult:
    slot_id: str
    ok: bool
    pipeline_type: str = "doc_4layer"
    total_time_s: float = 0.0
    analysis_iterations: int = 0
    review_status: str = "?"
    error: str = ""
    files: dict[str, str] = field(default_factory=dict)
    final_content: str = ""
```

**迁移策略**:
1. orchestrator.py 返回 PipelineResult
2. _parse_outline_to_blueprint 返回 list[SlotBlueprint]
3. load_compose_artifacts 返回 dict[str, ComposeArtifact]
4. 调用方改为属性访问（`result.ok` 而非 `result["ok"]`）
5. 不做 subscriptable hack — 干净切换

**风险**: 中。所有 caller 需要从 dict access 改为 attribute access。
**验证**: `pytest tests/ -q` 通过；orchestrator 返回类型为 PipelineResult。

---

## O3: Workspace Run-Scoping

**目标**: `workspace/<run_id>/<slot>` 隔离不同运行，resume 绑定特定 run。

**操作**:
1. run_compose() 生成 run_id (ISO timestamp: `20260604-143000`)
2. workspace 路径改为 `{output_dir}/workspace/{run_id}/{slot_id}/`
3. compose manifest 记录 run_id
4. generate --run-id 指定 run（或从 compose_dir 推断）
5. resume-from 绑定到 run_id 目录
6. config/pipeline.yaml 的 path_pattern 加 `{run_id}` 占位符

**风险**: 高。所有文件路径变化。ContextRegistry path_pattern 需更新。Tests 需调整。
**验证**: 两次运行同一 slot 不互相覆盖；resume-from 绑定正确 run_id。

---

## 设计决策

| 问题 | 决策 |
|------|------|
| compose/ 包位置 | 仓库根目录（与 run_slot_composition.py 平级） |
| 旧 workspace 迁移 | 不迁移，clean break |
| PipelineResult subscriptable | 不做，直接改 attribute access |
| doc_format 路由 | 纳入 profile 驱动（非硬编码 local） |
| 实验脚本重命名 | 去掉 test_ 前缀 |
