# Doc Pipeline 优化 Spec v1 (2026-06-04) — 已完成

## Context

在 Codex 6 项架构修复基础上，完成了 6 项优化 + 4 项后续修复。
测试基线：238 passed, 13 skipped。

---

## 已完成优化

### O6: 移动根目录 test_*.py 到 experiments/ ✓

8 个实验脚本移到 `experiments/`，去掉 `test_` 前缀，加 `sys.path` 指向 repo root。

**实际文件**:
```
experiments/
├── README.md
├── adversarial_review.py
├── analysis_ab.py
├── glm_q43.py
├── hybrid_outline.py
├── model_compare.py
├── question_ab.py
├── sc_question_local.py
└── self_adversarial.py
```

---

### O2: compose/ 增加 manifest.md ✓

`_write_manifest()` 在 compose 结束时写入 `compose/manifest.md`，`load_compose_artifacts()` 优先读 manifest、无 manifest 时 fallback 到 glob。

**manifest 格式** (markdown):
```markdown
# Compose Run Manifest
- run_id: 2026-06-04T17-35-12-905837
- routing_profile: all_local
- total_slots: 2
- compose_time_s: 25.3

## Slots
| Slot | Mode | Difficulty | Assembled Chars | Hash |
|------|------|-----------|-----------------|------|
| Q12  | 计算型 | 3        | 14111          | a1b2c3d4 |
```

---

### O5: 统一路由配置 ✓

`provider_router.py` 消除了所有硬编码常量（`AGENT_ROUTING`、`FALLBACK_PROVIDER`、`LOCAL_PROVIDER`、`HEALTH_CHECK_TTL`），改为 lazy init 从 `PIPELINE_CONFIG` 读取。

**关键机制**:
- `_get_config()` — deferred import + cache
- `_ensure_routing_initialized()` — 从默认 profile 初始化 `_active_routing`
- `_default_routing` — 缓存 profile 的 `_default` 值，未在 YAML 中显式出现的 role（design、formatter、doc_analysis 等）也遵循 profile 默认
- `set_routing_profile()` — 切换 profile 时更新 `_active_routing` + `_default_routing`

**路由 fallback 链**: `role_routing[role]` → `_default_routing` → local unavailable → `fallback_provider`

---

### O1: 拆分 run_slot_composition.py ✓

1207 行 monolith → `compose/` 包（5 模块 + 29 行 shim）。

```
compose/
├── __init__.py              # re-export 公共 API
├── artifact_store.py        # assemble_slot_experience_doc + _extract_* helpers
├── compose_runner.py        # compose_paper, _compose_hybrid/_local, outline parsing, manifest
├── generate_runner.py       # run_generate, _generate_slots, _generate_doc, load_compose_artifacts
├── debug_runner.py          # run_debug + _resolve_debug_workspace
└── cli.py                   # main, run_composition, CLI 子命令

run_slot_composition.py      # thin shim, re-exports from compose
```

**注意**: 内部模块间通过 module-level import 引用（`compose_runner.run_compose`），而非 direct function import，确保 monkeypatch 可工作。

---

### O4: 类型合约 ✓

`core_new/doc_pipeline/contracts.py` 定义三个 dataclass：

- **SlotBlueprint** — slot 蓝图（12 字段），`_parse_outline_to_blueprint()` 返回 `list[SlotBlueprint]`
- **ComposeArtifact** — 组装产物（slot_id, assembled_md, assembled_path），`load_compose_artifacts()` 返回 `dict[str, ComposeArtifact]`
- **PipelineResult** — 流水线结果（11 字段），`orchestrator.run_pipeline()` 返回 `PipelineResult`

调用方统一用 attribute access（`result.ok`、`result.review_status`），不做 subscriptable hack。下游需要 dict 的地方用 `dataclasses.asdict()` 在边界转换。

---

### O3: Workspace Run-Scoping ✓

workspace 路径改为 `{output_dir}/workspace/{run_id}/{slot_id}/`，隔离不同运行。

**实现**:
- `run_compose()` 生成微秒级 `run_id`：`datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")`
- `run_generate()` 接受 `run_id` 参数，workspace 路径拼接 `run_id`
- CLI `generate --run-id` 指定 run；未指定时从 `compose/manifest.md` 读取
- `debug --run-id` 支持；未指定时自动发现最新 run_id 目录
- `pipeline.yaml` 的 `path_pattern` 不需改动 — `{workspace}` 已包含 `run_id`

---

## 后续修复（Codex 审核发现）

### F1: 路由 default_routing 修复

**问题**: `_discover_all_roles()` 只收集 YAML profile 中显式出现的 role。design、doc_analysis、doc_coding、doc_design、formatter 等不在 profile 中，`get_routed_gateway()` 会走 hardcoded `"remote"` 默认值，导致 `all_local` 下这些 role 实际走远端。

**修复**: 新增 `_default_routing` 变量，从 profile 的 `_default` 字段初始化。未在 `_active_routing` 中的 role 用 `_default_routing` 而非 hardcoded `"remote"`。

### F2: debug 子命令 run_id 支持

**问题**: debug 默认找 `{workspace}/{slot}`，run-scoping 后路径变为 `{workspace}/{run_id}/{slot}`，debug 找不到当前 run。

**修复**: 添加 `--run-id` 参数 + `_resolve_debug_workspace()` 优先查找 run_id 目录（ISO timestamp 含 `T`），legacy 扁平布局作为 fallback。

### F3: run_id 微秒精度

**问题**: 秒级时间戳在快速连续 compose 时可能碰撞。

**修复**: 格式改为 `%Y-%m-%dT-%H-%M-%S-%f`（例：`2026-06-04T17-35-12-905837`）。

### F4: 实验脚本 sys.path 修复

**问题**: 脚本移到 `experiments/` 后 import `core_new` 失败。

**修复**: 所有 8 个脚本添加 `sys.path.insert(0, repo_root)` 和/或 `os.chdir(repo_root)`。

---

## 当前架构

```
config/pipeline.yaml          ← 唯一权威配置（路由、参数、context injection）
    ↓
core_new/provider_router.py   ← lazy init 从 YAML 读路由
    ↓
run_slot_composition.py       ← 29 行 shim
    ↓
compose/                      ← 模块化包
    ├── cli.py                ← main(), run_composition() — 编排入口
    ├── compose_runner.py     ← 组卷：outline + assemble + manifest
    ├── generate_runner.py    ← 出题：load artifacts + DocPipeline + format
    ├── artifact_store.py     ← 经验文档组装
    └── debug_runner.py       ← 单 agent 调试
    ↓
core_new/doc_pipeline/
    ├── contracts.py          ← SlotBlueprint, ComposeArtifact, PipelineResult
    ├── orchestrator.py       ← 4-layer workflow, 返回 PipelineResult
    ├── context.py            ← ContextRegistry, FileProvider, InlineProvider
    ├── scheduler.py          ← DocScheduler (agent 执行)
    └── config.py             ← PIPELINE_CONFIG 单例
```

### CLI 用法

```bash
# 组卷 + 出题（完整流程）
python run_slot_composition.py --routing all_local --slots Q12 Q13

# 仅组卷
python run_slot_composition.py compose --routing all_local --slots Q12 Q13

# 仅出题（从 compose 产物加载）
python run_slot_composition.py generate --compose-dir docs/compose --routing all_local

# 出题 + 断点续跑（从 Layer 3 继续）
python run_slot_composition.py generate --compose-dir docs/compose --resume-from 3 --run-id 2026-06-04T17-35-12-905837

# 单 agent 调试
python run_slot_composition.py debug --slot Q12 --agent review --routing all_local --run-id 2026-06-04T17-35-12-905837
```

### 磁盘产物

```
{output_dir}/
├── compose/
│   ├── outline.md
│   ├── manifest.md              ← run_id + routing + slot table
│   ├── Q12_assembled.md
│   └── Q13_assembled.md
├── workspace/{run_id}/
│   ├── Q12/
│   │   ├── blueprint.md
│   │   ├── question.md
│   │   ├── feedback.md
│   │   ├── solve.py
│   │   ├── solve_output.txt
│   │   ├── review.md
│   │   └── final.md
│   └── Q13/...
└── exam_paper_clean.md
```

---

## 设计决策

| 问题 | 决策 |
|------|------|
| compose/ 包位置 | 仓库根目录（与 run_slot_composition.py 平级） |
| 旧 workspace 迁移 | 不迁移，clean break（已删除） |
| PipelineResult subscriptable | 不做，直接改 attribute access |
| doc_format 路由 | 纳入 profile 驱动（非硬编码 local） |
| 实验脚本重命名 | 去掉 test_ 前缀 |
| pipeline.yaml path_pattern | 不加 `{run_id}` — `{workspace}` 已包含 |
| monkeypatch 路径 | tests 直接 patch `compose.*` 模块 |
| 内部模块引用 | module-level import（`compose_runner.run_compose`） |
