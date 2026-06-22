# Compose 重构设计：三条路线 + 按需加载 + 模型分层路由

> 日期: 2026-06-09
> 状态: 三路线代码路径已实现；教师选择 UI/交互闭环仍在接入中
> 前置: intake layer Phase I0 已完成

> **实现注记 (commit 806cf84)**:
> - `grep_question_bank()` 已改为委托 `compose/knowledge_index.py` 的结构化标签索引
> - 底层不再做全文本 grep，而是预解析元数据（知识点、科目、题型）构建反向索引
> - 新增 `grep_search_tool.py` 将搜索注册为 OpenAI tool
> - 新增 `interact` agent + `interact_core` skill（本 spec 的 Phase 1 实现）
> - 数据目录重组：KG → `data/kg/`，配置 → `data/config/`，统计 → `data/statistics/`
> - 后续修补：`compose_route_2()` 兼容当前 `SlotBlueprint` 字段 `target_difficulty`、`excluded_modes`、`excluded_knowledge`

## 1. 核心发现

当前 compose 流程将 46K 上下文（4科KG + 全部experience cards）一次性塞给 GLM-5.1，
触发深度推理，导致：
- 耗时 244s，reasoning 占 66% token 预算
- LLM 被迫"全局规划整张试卷"，而非做简单的信息组织

实测对比：
| 方式 | 耗时 | content | reasoning |
|------|------|---------|-----------|
| 复杂prompt (46K上下文) | 244s | 34% | 66% |
| 简单prompt (无约束) | 92s | 50% | 50% |

**结论**：大部分 compose 任务是信息组织而非推理，应按需加载、分步执行、本地模型优先。

## 2. 设计原则

1. **交互层是信息拆分器和选择界面生成器**：不承担深度推理，只做归纳和呈现
2. **先卡片，后 YAML**：LLM 输出卡片让教师选择，确认后才转正式机器文档
3. **KG 预加载**：图谱小（~5K/科），作为约束条件常驻
4. **经验卡按需加载**：仅路线1需要，且只加载相关科目的相关slot
5. **检索由 LLM 驱动**：搜索关键词由 LLM 生成，非系统固定规则；底层使用结构化标签索引而非全文 grep
6. **决策权在教师**：每个关键节点由教师选择，LLM 不替人做决定
7. **模型配置驱动**：所有模型选择通过 pipeline.yaml 配置，代码不硬编码
8. **权限边界**：proposal 阶段禁止生成 CONTRACT/paper_selection/question/solution
9. **决策准则**：当前阶段应该生成什么给老师看？

## 2.1 交互层职责定义

> **交互层负责信息拆分、信息归纳、选择呈现。不负责最终规划正确性，也不负责题目设计推理。**
> 深度推理留给题目设计、求解和终审。

LLM 在交互层只做归纳和呈现，核心能力是：
- **标签索引检索**：由 `grep_search` / `grep_question_bank` 兼容命名入口按知识点搜索题库，底层为结构化标签索引
- **文档读写**：读取 KG/经验卡 → 归纳 → 写出卡片
- **格式化**：将已有数据组织为教师可读格式

## 3. 三条路线

### 路线1：真题组卷（有经验卡）

**触发条件**：intake 输出为 paper_request，且目标科目有 experience cards。

**流程**：
```
load slot 经验卡(仅相关科目, 仅相关slot)
  → 渲染为 slot_cards
    → 教师选择模式/知识点
      → Python 生成 YAML
```

**LLM 参与**：api_vllm 做渲染归纳（无推理）
**数据加载**：仅加载 paper_request 指定的科目 + slot 范围

**slot_card 输出格式**（每个slot一张卡片）：
```yaml
slot_card:
  slot_id: Q12
  type: single_choice
  score: 2
  recommended_mode: 计算型——公式应用与单位换算
  recommended_frequency: 53.8%
  recommended_reason: 该模式在Q12题位出现频率最高，适合考察计算能力
  alternatives:
    - mode: 概念辨析型——核心定义与本质区分
      frequency: 23.1%
    - mode: 组合判断型——多维度特征匹配
      frequency: 23.1%
  applicable_knowledge:
    - CPU执行时间公式
    - 单位换算
    - 性能公式
  teacher_actions: [confirm | change_mode | exclude_knowledge | remove]
```

### 路线2：单知识点（给定知识点如"二叉树"）

**触发条件**：intake 输出为 slot_blueprint，指定了知识点。

**流程**：
```
知识点 → LLM 生成搜索关键词
  → grep_question_bank / knowledge_index 检索题库
    → 本地 Qwen 按考察模式分类归纳
      → 教师选择考察模式
        → Python 生成 YAML
```

**LLM 参与**：
- 搜索关键词生成：api_vllm（简单）
- 结果归纳：api_vllm（分类任务）
- 或全部用一个 api_vllm 调用完成

**topic_mode_card 输出格式**：
```yaml
topic_mode_card:
  id: avl_rotation_judgment
  title: 旋转类型判断
  knowledge: AVL树旋转操作
  sources:
    - kg_node: 数据结构 > 树与二叉树 > 平衡二叉树 > 旋转操作
    - question_bank_matches: 12
    - experience_references: 3
  modes:
    - name: 旋转类型判断型
      count: 7
      description: 给定插入序列或局部结构，判断 LL/LR/RL/RR 旋转类型
      suitable_types: [single_choice, comprehensive]
      difficulty: medium
      examples: [2018年408第5题, 2020年408第4题]
    - name: 平衡因子计算型
      count: 3
      description: 计算各节点平衡因子，判断是否失衡
      suitable_types: [single_choice]
      difficulty: easy
  teacher_actions: [select_mode | combine_modes | change_knowledge]
```

### 路线3：自由组卷（唯一需要深度思考）

**触发条件**：intake 输出为 paper_request，目标科目无 experience cards，或教师选择自由组卷。

**流程**（多轮交互）：

```
Step 1 [GLM-5.1]: 基于 KG 约束生成知识点初稿
  → 输出: 每个slot建议的知识点 + 考点方向
  
Step 2 [系统]: 自动补全每个知识点的考点详情（从 KG 查）

Step 3 [教师]: 批注/移除不想考的知识点 → 产生 diff

Step 4 [api_vllm]: 读取 diff → 对保留的考点做标签索引检索题库

Step 5 [api_vllm]: 归纳检索结果为考察模式

Step 6 [教师]: 选择考察模式 → Python 生成 YAML
```

**多轮交互核心**：
- LLM 先提知识点（如 Cache、流水线、中断）
- 系统自动补全考点详情（Cache映射方式、替换算法...）
- 教师移除不想考的
- LLM 只对保留的做深入检索和归纳
- 每轮上下文小，不会触发深度思考

**Step 1 prompt 示例**（精简版）：
```
基于以下知识点图谱，为一套计算机组成原理期末考试（10选择+4简答+2计算+1综合）
规划每个题位的考点。只输出知识点和考察方向，不需要详细内容。

知识点图谱:
{仅相关科目的KG}

输出格式:
| 题号 | 题型 | 知识点 | 考察方向 | 难度 |
```

## 4. 模型路由（配置驱动，不硬编码）

**核心原则**：模型选择由 `config/pipeline.yaml` 中的 `model_routing` 配置决定，代码中不绑定具体模型。
用户可以自由配置：交互层用 qwen 还是 glm，自由组卷用哪个模型，全部通过配置切换。

### pipeline.yaml 配置示例

```yaml
model_routing:
  # 交互层（intake + 渲染 + 标签索引检索 + 归纳）
  interaction: api_vllm       # 可改为 glm5.1 / glm4flash / qwen36_a35 等

  # 自由组卷初稿（路线3 Step1，唯一可能需要强模型的任务）
  free_compose: glm5.1        # 可改为 api_vllm 如果本地模型够用

  # 以下是默认推荐，但完全可配置
  # interaction: api_vllm     # 本地模型，快速，低成本
  # free_compose: glm5.1      # 远程模型，推理能力强
```

### 路由逻辑

```python
def get_model_for_task(task: str) -> str:
    """从 pipeline.yaml 读取模型配置，不硬编码。"""
    routing = pipeline_config.get("model_routing", {})
    return routing.get(task, routing.get("interaction", "api_vllm"))
```

### 任务上下文预算（模型无关）

| 任务 | 典型上下文 | 典型耗时 | 备注 |
|------|-----------|---------|------|
| 渲染经验卡（路线1） | ~2K/slot | <5s | 纯格式化 |
| 搜索关键词生成 | ~500 chars | <2s | 简单生成 |
| 检索结果归纳 | ~3-5K | <10s | 分类任务 |
| 自由组卷初稿（路线3 Step1） | ~5-8K | 视模型 | 唯一可能需要推理的任务 |
| diff 后检索归纳（路线3 Step4-5） | ~3-5K/知识点 | <10s | 检索+分类 |
| YAML 生成 | N/A | <1s | Python，不经过LLM |

**注意**：config.py 中的 `local` (Qwen3-32B) 是废弃配置。当前实际可用的本地模型为 `api_vllm` (Qwen3.6-27B-FP8)。
**原则**：所有模型选择通过配置文件驱动，代码中只引用 `get_model_for_task()` 返回的 provider name。

## 5. 数据加载策略

```python
# 当前（全量加载）
def _build_shared_header():
    # 加载 4 科 KG → ~20K chars
    # 加载 K-radar → ~1K chars

def _build_slot_contracts_md():
    # glob *_experience.md → 加载所有 slot → ~16K chars
    # 总计 ~46K chars 一次塞给 LLM

# 重构后（按需加载）
def load_kg_for_subjects(subjects: list[str]) -> str:
    """只加载指定科目的 KG"""
    # 408: 加载 4 科 KG → ~20K (给路线3 Step1 的 GLM)
    # 组原: 只加载 1 科 KG → ~5K

def load_experience_for_slots(slot_ids: list[str]) -> dict[str, str]:
    """只加载指定 slot 的经验卡"""
    # 路线1: 按需加载 → 展示给教师
    # 路线2/3: 不加载

def search_question_bank(keywords: list[str], subject: str) -> list[dict]:
    """LLM 驱动的题库检索（底层为 knowledge_index 标签索引）"""
    # 路线2: 知识点相关题目
    # 路线3 Step4: 保留考点的相关题目
```

## 6. 与 intake layer 的衔接

intake 输出决定走哪条路线：

| intake 输出 | 路线 | 说明 |
|-------------|------|------|
| paper_request + 有经验数据 | 路线1 | 真题组卷 |
| slot_blueprint（指定知识点） | 路线2 | 单知识点 |
| paper_request + 无经验数据 | 路线3 | 自由组卷 |

route_gate 已在 intake 层实现路由判断，compose 层读取 route_gate 结果即可。

## 7. 实施计划

### Phase 1：按需加载 + 路线1（已实现）
- 重构 `_build_shared_header()` → `load_kg_for_subjects()`
- 重构 `_build_slot_contracts_md()` → `load_experience_for_slots()`
- 路线1 实现：经验卡渲染 → 教师选择 → YAML
- api_vllm (Qwen3.6-27B-FP8) 做渲染

### Phase 2：路线2（代码路径已实现，教师选择闭环待接入）
- LLM 驱动标签索引检索
- api_vllm 归纳
- 教师选择流程

### Phase 3：路线3（代码路径已实现，真实多轮交互待接入）
- GLM-5.1 自由组卷初稿
- 系统自动补全考点
- 多轮交互流程（教师 ↔ LLM）
- diff 驱动的检索和归纳

### Phase 4：交互界面（待接入）
- 基于 Phase 1-3 的流程设计 UI
- 教师选择界面
- diff 展示界面
- YAML 预览界面

## 8. Skills & Agent MD 同步要求

> **原则**：行为变更必须同步更新对应的 skill 和 agent MD，否则 LLM 行为与系统实现不一致。

| 变更内容 | 需同步更新 |
|---------|-----------|
| compose 三路线分流 | `core_new/doc_pipeline/skills/outline_v2/SKILL.md` — 新增路线判断逻辑 |
| 路线1 渲染格式 | `core_new/doc_pipeline/agents/paper_outline.md` — 更新输出格式规范 |
| 路线3 多轮交互 | 新增 `core_new/doc_pipeline/skills/compose_free/SKILL.md` |
| LLM 驱动检索 | 新增或更新 `core_new/doc_pipeline/skills/question_search/SKILL.md`，并说明底层为 `knowledge_index` |
| 经验卡按需加载 | `compose_runner.py` 中加载逻辑重构，agent MD 中说明数据范围 |
| YAML 生成改为 Python | `core_new/doc_pipeline/skills/outline_v2/SKILL.md` 中移除 YAML 生成的 LLM 指令 |

每个 Phase 完成时，对应 skill 和 agent MD 必须同步更新并测试。

## 9. Skill / Agent MD 草案

### 9.1 Agent: paper_outline.md（重写为 routing agent）

```markdown
---
name: paper_outline
phase: compose
skills:
  - compose_render_cards    # 路线1: 真题组卷
  - compose_topic_search    # 路线2: 单知识点
  - compose_free_outline    # 路线3: 自由组卷
---
# 组卷大纲调度层

## 路由规则

| 条件 | 路线 | Skill |
|------|------|-------|
| paper_request + 有experience cards | 1 | compose_render_cards |
| slot_blueprint (有 primary_target_name) | 2 | compose_topic_search |
| paper_request + 无experience cards | 3 | compose_free_outline |

## 职责范围
- 读取 intake 输出 → 路由到对应 skill
- 不做全局优化、不生成 YAML、不做设计决策

## 禁止行为
1. 不写具体题目
2. 不设计选项/干扰项
3. 不在单次 LLM 调用中把整张试卷作为一个 prompt
4. 不在教师批准前生成 YAML
```

### 9.2 Skill: compose_render_cards（路线1）

```
Step 1 [Python]: 加载 paper_request → 确定科目和 slot 范围
Step 2 [config:interaction, ~2K/slot, 可并行]: 渲染经验卡为选择卡片
  Prompt: "将以下 slot data 格式化为选择卡片。不要修改、重排或选择。只格式化。"
  输出: ## Q12（选择题·2分）推荐: 计算型 (53.8%) / 备选: ...
Step 3 [教师]: 确认/改选模式，排除知识点
Step 4 [Python]: 教师选择 → outline_draft.md（CONTRACT marker YAML）
```

### 9.3 Skill: compose_topic_search（路线2）

```
Step 1 [config:interaction, ~200 chars]: 生成搜索关键词
  Prompt: "给定知识点'{name}'，生成3-5个关键词搜索相关题目"
Step 2 [Python]: 调用 grep_question_bank()，由 knowledge_index 标签索引检索 data/question_experiences/*.md
Step 3 [config:interaction, ~3-5K]: 按考察模式分类归纳
  Prompt: "将以下N道关于{topic}的题目按考察模式分类。每个模式给：名称、数量、1句话描述、1-2个代表题。"
Step 4 [教师]: 选择考察模式
Step 5 [Python]: 生成 outline_draft.md
```

### 9.4 Skill: compose_free_outline（路线3）

```
Step 1 [config:free_compose, ~5-8K]: 基于 KG 分配知识点
  输入: KG(仅目标科目) + slot模板(类型+分值)
  输出: markdown表格(slot_id | 题型 | 知识点 | 考察方向 | 难度)
Step 2 [Python]: KG 自动补全考点详情(父章节、兄弟知识点、子主题)
Step 3 [教师]: 批注/移除知识点 → 产生 diff
Step 4 [config:interaction, ~5K/知识点]: 对保留知识点执行路线2的检索+归纳流程
Step 5 [教师]: 选择考察模式
Step 6 [Python]: 生成 outline_draft.md
```

### 9.5 上下文预算总览

| 步骤 | 路线 | 上下文 | 模型来源 | 可并行 |
|------|------|--------|---------|--------|
| 渲染卡片 | 1 | ~2K/slot | config:interaction | 是 |
| 搜索关键词 | 2 | ~200 chars | config:interaction | 否 |
| 结果归纳 | 2/3 | ~3-5K | config:interaction | 是(按知识点) |
| 知识点分配 | 3 | ~5-8K | config:free_compose | 否 |
| KG补全 | 2/3 | N/A | Python | 是 |
| YAML生成 | 1/2/3 | N/A | Python | N/A |

## 10. 不修改的文件

- `core_new/doc_pipeline/orchestrator.py` — 不涉及
- `core_new/doc_pipeline/context.py` — 不涉及
- `config/pipeline.yaml` — 路由配置不变

## 11. 验证标准

1. 路线1: 经验卡渲染 <5s，教师选择后 YAML 生成 <1s
2. 路线2: 标签索引检索+归纳 <15s
3. 路线3: GLM 初稿 <90s，后续每轮 <15s
4. 总 token 消耗降低 50%+
5. 不再出现 244s 的深度推理超时
