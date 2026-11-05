# Doc Pipeline 优化 Spec v1 (2026-06-04) — 已完成

## Context

在 Codex 6 项架构修复基础上，完成了 6 项优化 + 4 项后续修复。
测试基线：238 passed, 13 skipped。

---

## v2 更新 (2026-06-05) — 跨科目 + 重试强化

### V2-1: 四科目全覆盖

**问题**: 流水线仅支持计算机组成原理（CO），slot 模板、经验卡、知识图谱均硬编码为 CO。

**修复**:
- `scripts/extract_all_slots.py` 从 2058 份 question experience 中自动抽取 47 个题位的模板和经验卡
- `data/slot_templates_all.json` — 47 个 slot 覆盖全部 4 科：数据结构(Q1-Q11,Q41-Q42)、组成原理(Q12-Q22,Q43-Q44)、操作系统(Q23-Q32,Q45-Q47)、计算机网络(Q33-Q40)
- `data/slot_experiences_all/` — 47 份经验卡 markdown
- `data/数据结构.md`、`data/操作系统.md`、`data/计算机网络.md` — 三科知识图谱

**科目映射**:
```
Q1-Q11   → 数据结构 (DS)
Q12-Q22  → 计算机组成原理 (CO)
Q23-Q32  → 操作系统 (OS)
Q33-Q40  → 计算机网络 (CN)
Q41-Q42  → 数据结构 (DS, 综合题)
Q43-Q44  → 计算机组成原理 (CO, 综合题)
Q45-Q47  → 操作系统 (OS, 综合题)
```

### V2-2: 科目编码翻译

**问题**: 知识图谱和 outline 使用缩写编码（DS-1, CO-3 等），面向教师的文档需要中文名。

**修复**: `core_new/subject_map.py`
- `CHAPTER_MAP`: 缩写 → 科目章节名（如 `DS-3 → "数据结构-3"`，不含主题名避免重复）
- `translate_code(text)`: 正则替换文本中的缩写编码
- `SUBJECT_MAP`: 科目缩写 → 全名（`DS → 数据结构`）

### V2-3: 多科目知识图谱路由

**问题**: `artifact_store.py` 仅路由到 `computer_organization.md`。

**修复**: `_KG_FILE_MAP` 四科目路由：
```python
_KG_FILE_MAP = {"CO": "computer_organization.md", "DS": "数据结构.md",
                "OS": "操作系统.md", "CN": "计算机网络.md"}
```

### V2-4: slot_contract 科目修复

**修复**: 改为 `lines.append(f"- **科目**: {subj}")`，直接使用模板中的 `subject_stability` 字段。

### V2-5: GLM5.1 重试机制强化

**修复** (`core_new/llm_gateway.py` + `config.py`):

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| 客户端 HTTP 重试 | `max_retries=0` | `max_retries=5`（OpenAI SDK 层） |
| 网关退避策略 | 固定 3s + jitter | 固定 5s |
| 异常分类 | 字符串匹配兜底 | 显式分类（timeout > connection > rate_limit > internal） |

### V2-6: model_routing `_default` 支持

**修复**: `provider_name = model_routing.get(role) or model_routing.get("_default")`

### V2-7: exp_dir 参数传递修复

### V2-8: 跨科目测试验证

| 测试 | 题位 | 科目 | 模型 | 结果 |
|------|------|------|------|------|
| 跨科目单选题 | Q1, Q23, Q33 | DS, OS, CN | Qwen 本地 | ✓ |
| GLM5.1 综合题 | Q41, Q45 | DS, OS | GLM5.1 远程 | ✓ |

---

## 已完成优化 (O1-O6)

- O1: 拆分 run_slot_composition.py → compose/ 包
- O2: compose/ manifest.md
- O3: Workspace Run-Scoping
- O4: 类型合约 (SlotBlueprint, ComposeArtifact, PipelineResult)
- O5: 统一路由配置 (provider_router.py)
- O6: 移动根目录 test_*.py 到 experiments/

---

## 后续修复 (F1-F4)

- F1: 路由 default_routing 修复
- F2: debug 子命令 run_id 支持
- F3: run_id 微秒精度
- F4: 实验脚本 sys.path 修复
