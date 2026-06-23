# Doc Pipeline Spec v3 (2026-06-06) — 风格控制 + GLM5.1/GPT 双基座

## Context

在 v2 跨科目支持基础上，完成三项核心改造：
1. 出题智能体 SC/COMP 拆分 + 风格控制体系
2. 经验卡 LLM 重抽取（34 slots）
3. GLM5.1 出题 + GPT 终审双基座测试

---

## V3-1: 出题智能体 SC/COMP 拆分

### 问题

原有 `question.md` 单一智能体处理选择题和综合题，格式约束混在一起，无法精细控制不同题型的输出风格。

### 修复

| 文件 | 操作 |
|------|------|
| `agents/question.md` | 保留（向后兼容） |
| `agents/question_sc.md` | **新建** — 选择题专用 |
| `agents/question_comp.md` | **新建** — 综合题专用 |
| `skills/question_create/question_sc_skill.md` | **新建** — SC 领域规范 |
| `skills/question_create/question_comp_skill.md` | **新建** — COMP 领域规范 |

### question_type 解析链

```
orchestrator._question_role() 四级解析:
1. 显式参数 question_type
2. slot_data["question_type"] 或 slot_data["section"]
3. assembled doc 头部内容检测（"综合应用题"）
4. slot_id 模式匹配（Q41-Q47 → comp）
```

### 参数透传

`DocPipeline.run()` → `DocPipelineOrchestrator.run_pipeline()` 透传 `question_type` 参数。

---

## V3-2: 风格控制体系

### 三层修复

**问题**: 出题风格不受控 — 选项格式出现在综合题、背景故事出现在选择题等。

**根因**:
1. `agent_loader.py` 丢弃 agent MD body（身份+约束信息丢失）
2. 无格式红线约束
3. 审核者无经验卡对齐检查

**修复**:

#### 层1: Agent MD body 保留

`agent_loader.py` 修复：
```python
# Before: body discarded
self.prompt = _BEHAVIOR_CORE + "\n" + variant_text + suffix

# After: body preserved
identity = body.strip() if body.strip() else ""
if identity:
    self.prompt = _BEHAVIOR_CORE + "\n\n" + identity + "\n\n" + variant_text + suffix
```

#### 层2: 格式红线

**SC 格式红线** (5 条):
1. 禁止子问题格式（不得拆为(1)(2)(3)）
2. 禁止编程代码
3. 禁止冗长题干（≤3句话、80字）
4. 禁止答案出现在题目中
5. 禁止背景故事

**COMP 格式红线** (5 条):
1. 禁止选项格式（无A/B/C/D）
2. 禁止独立子问（必须有逻辑依赖）
3. 禁止编程代码题干
4. 禁止背景故事
5. 禁止答案出现在题目中

#### 层3: 经验卡对齐审核

`agents/review.md` 新增审核维度：
- **5.7 风格合规**: 格式红线逐条检查
- **5.8 经验卡对齐**: should_be/should_not_be 逐项对照

### 风格控制链

```
经验卡 (should_be/should_not_be/考察模式/选项风格)
  ↓ 结构化提取
出题智能体 (question_sc/comp_skill.md)
  ↓ 格式红线约束
题目输出 (question.md)
  ↓ 风格合规 + 经验卡对齐
审核智能体 (review.md 5.7 + 5.8)
```

---

## V3-3: 经验卡 LLM 重抽取

### 问题

原有 34 个 slot 的经验卡缺失（仅 13/47 用 regex 抽取），且 regex 质量不稳定。

### 修复

`scripts/resynthesize_slots.py` — 使用 LLM (Qwen3.6-27B) 从 question_experiences 合成经验卡：
- 过滤：仅使用真题文件（`(19|20)\d{2}_(Q\d+)` 格式）
- 提示语：`SLOT_SYNTHESIS_PROMPT_SC` / `SLOT_SYNTHESIS_PROMPT_COMP`
- 结果：33/33 slot 成功，经验卡 2700-8900 字符

### 数据源

```
data/question_experiences/    ← 2058 文件（682 真题 + 1036 练习）
data/slot_experiences/        ← 47 份 LLM 合成经验卡
```

---

## V3-4: GLM5.1 + GPT 双基座路由

### 路由配置

`config/pipeline.yaml` 新增 `glm_gpt_review` profile:
```yaml
glm_gpt_review:
  _default: "{fallback}"        # GLM5.1 为默认
  model_routing:
    final_review: webgpt         # GPT 做终审
```

### WebGPT 配置

```
WebGPT 网关: http://localhost:3000 (WebAI2API)
API Key: WEBGPT_API_KEY (配置在 .env)
模型: gpt-thinking
```

### 关键修复

| 问题 | 修复 |
|------|------|
| `question_sc`/`question_comp` 无 context 注入 | `pipeline.yaml` + `pipeline_config.py` 添加 role_bindings |
| `pipeline.yaml` 使用 "remote" 字面值 | 改为 `"{fallback}"` 模板变量 |
| `DocPipeline.run()` 不透传 `question_type` | 添加参数并传递到 orchestrator |

---

## V3-5: 测试验证

### Q12 测试 (GLM5.1 出题+审核+求解, GPT 终审)

| 层 | 模型 | 耗时 | 结果 |
|----|------|------|------|
| L2 Question | GLM5.1 | ~90s | CPU 执行时间计算题，质量 9/10 |
| L3 Review | GLM5.1 | ~88s | pass（首次），经验卡对齐 ✓ |
| L4 Solve | GLM5.1 | ~24s | C: 80μs，求解正确 |
| L5 Final Review | 本地回退* | ~30s | pass |

*注: L5 因 `WEBGPT_API_KEY` 未配置回退到本地 vLLM。已修复。

**题目质量**:
- 题干: "某计算机主频为2GHz，程序P共执行了40000条指令，其中60%的指令CPI为2，20%的指令CPI为4，20%的指令CPI为10。程序P的执行时间是（）。"
- 参数: 全 2^n 友好值，中间结果均为整数
- 干扰项: 各针对一种典型错误认知
- should_be/should_not_be: 逐项通过

### 测试脚本

- `scripts/test_glm_gpt_review.py` — GLM5.1 出题 + GPT 终审端到端测试

---

## 当前架构

```
config/pipeline.yaml              ← 路由 + 参数 + context injection + 题型 role_bindings
    ↓
core_new/doc_pipeline/
    ├── orchestrator.py            ← 5 层流程 + question_type 解析 + 条件路由
    ├── scheduler.py               ← DocScheduler (GLM5.1/WebGPT/本地三路模型)
    ├── agent_loader.py            ← agent MD body 保留 + SC/COMP 行为变体
    ├── context.py                 ← ContextRegistry (question_sc/question_comp 绑定)
    ├── pipeline_config.py         ← YAML 加载 + 默认 role_bindings
    ├── contracts.py               ← SlotBlueprint, PipelineResult
    ├── agents/
    │   ├── question_sc.md         ← 选择题智能体
    │   ├── question_comp.md       ← 综合题智能体
    │   ├── review.md              ← 审核（含风格合规 + 经验卡对齐）
    │   ├── solve.md               ← 求解
    │   └── final_review.md        ← 终审
    └── skills/
        ├── question_create/
        │   ├── question_sc_skill.md    ← SC 格式红线 + 风格模板
        │   └── question_comp_skill.md  ← COMP 格式红线 + 子问模式
        └── audit_fix/
            └── review_skill.md
    ↓
compose/                           ← 组卷模块
core_new/webgpt_client.py         ← GPT (WebAI2API) 网关客户端
core_new/llm_gateway.py           ← GLM5.1 + vLLM 双基座
```

### 模型配置

| Provider | 用途 | 配置 |
|----------|------|------|
| api_vllm | 本地 Qwen3.6-27B | localhost:8000 |
| glm5.1 | 远程 GLM5.1 | open.bigmodel.cn |
| webgpt | GPT (WebAI2API) | localhost:3000 |

### 环境变量

```bash
# .env
VLLM_API_BASE=http://127.0.0.1:8000/v1
GLM_API_KEY=<key>
GLM_MODEL=glm-5.1
WEBGPT_API_KEY=sk-chatgpt-team-key123
```

---

## 已清理 (2026-06-06)

- `agents/question.md` — 已删除（被 question_sc/comp 替代）
- `skills/question_create/question_skill.md` — 已删除（被 sc/comp 替代）
- `agents_gpt/coding.md` — 已删除（被 solve 替代）
- `data/数据结构.md` — 已删除（指向 `data_structure.md`）
- `data/操作系统.md` — 已删除（指向 `operating_system_knowledge.md`）
- `data/计算机网络.md` — 已删除（指向 `computer_network.md`）
- `artifact_store.py` _KG_FILE_MAP — 已修正为英文文件名
- `compose_runner.py` subject_files — 已修正为英文文件名

---

## 知识图谱文件规范

| 科目 | 文件 | 行数 | 来源 |
|------|------|------|------|
| CO | `data/computer_organization.md` | 1362 | 计组思维导图 PDF |
| DS | `data/data_structure.md` | 1467 | 数据结构知识点 |
| OS | `data/operating_system_knowledge.md` | 1533 | 操作系统知识点 |
| CN | `data/computer_network.md` | 1023 | 计网思维导图 PDF |
| 大纲 | `data/dagang.md` | — | 2025 408 考研大纲 |

**规则**: 知识图谱文件名统一使用英文。中文命名的图谱文件已删除。
