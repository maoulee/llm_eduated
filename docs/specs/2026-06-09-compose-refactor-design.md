# Compose 重构设计：三条路线 + 按需加载 + 模型分层路由

> 日期: 2026-06-09
> 状态: 设计中
> 前置: intake layer Phase I0 已完成

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

1. **KG 预加载**：图谱小（~5K/科），作为约束条件常驻
2. **经验卡按需加载**：仅路线1需要，且只加载相关科目的相关slot
3. **检索由 LLM 驱动**：grep 关键词由 LLM 生成，非系统固定规则
4. **LLM 只做三件事**：渲染归纳、grep 检索、自由组卷初稿
5. **决策权在教师**：每个关键节点由教师选择，LLM 不替人做决定
6. **模型分层路由**：简单任务用本地 Qwen，推理任务用远程 GLM

## 3. 三条路线

### 路线1：真题组卷（有经验卡）

**触发条件**：intake 输出为 paper_request，且目标科目有 experience cards。

**流程**：
```
load slot 经验卡(仅相关科目, 仅相关slot)
  → 本地 Qwen 渲染为固定格式表格
    → 教师选择模式/知识点
      → Python 生成 YAML
```

**LLM 参与**：api_vllm (Qwen3.6-27B-FP8) 做渲染归纳（无推理）
**数据加载**：仅加载 paper_request 指定的科目 + slot 范围

**渲染格式示例**（每个slot一张卡片）：
```
## Q12（选择题 · 2分）
推荐模式: 计算型——公式应用与单位换算 (53.8%)
备选模式: 概念辨析型 (23.1%), 组合判断型 (23.1%)
适用知识点: CPU执行时间公式, 单位换算, 性能公式
教师操作: [确认推荐] [改选模式] [排除知识点]
```

### 路线2：单知识点（给定知识点如"二叉树"）

**触发条件**：intake 输出为 slot_blueprint，指定了知识点。

**流程**：
```
知识点 → LLM 生成 grep 关键词
  → grep 检索题库
    → 本地 Qwen 按考察模式分类归纳
      → 教师选择考察模式
        → Python 生成 YAML
```

**LLM 参与**：
- grep 关键词生成：api_vllm（简单）
- 结果归纳：api_vllm（分类任务）
- 或全部用一个 api_vllm 调用完成

**归纳输出格式**：
```
## AVL树旋转（LR型和RL型判断）
相关题目: 23题

模式A: 旋转判断型 (12题)
  考察: 给定插入序列判断失衡类型和旋转方向
  典型题: 2018年408第5题...
  
模式B: 平衡因子计算型 (7题)
  考察: 计算各节点平衡因子，判断是否失衡
  典型题: ...

模式C: 综合应用型 (4题)
  考察: 构造AVL树全过程，含多次旋转
  典型题: ...

教师操作: [选择模式] [组合模式]
```

### 路线3：自由组卷（唯一需要深度思考）

**触发条件**：intake 输出为 paper_request，目标科目无 experience cards，或教师选择自由组卷。

**流程**（多轮交互）：

```
Step 1 [GLM-5.1]: 基于 KG 约束生成知识点初稿
  → 输出: 每个slot建议的知识点 + 考点方向
  
Step 2 [系统]: 自动补全每个知识点的考点详情（从 KG 查）

Step 3 [教师]: 批注/移除不想考的知识点 → 产生 diff

Step 4 [api_vllm]: 读取 diff → 对保留的考点做 grep 检索题库

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
  # 交互层（intake + 渲染 + grep + 归纳）
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
| grep 关键词生成 | ~500 chars | <2s | 简单生成 |
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
    """LLM 驱动的 grep 检索"""
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

### Phase 1：按需加载 + 路线1（投入低，收益大）
- 重构 `_build_shared_header()` → `load_kg_for_subjects()`
- 重构 `_build_slot_contracts_md()` → `load_experience_for_slots()`
- 路线1 实现：经验卡渲染 → 教师选择 → YAML
- api_vllm (Qwen3.6-27B-FP8) 做渲染

### Phase 2：路线2（中等投入）
- LLM 驱动 grep 检索
- api_vllm 归纳
- 教师选择流程

### Phase 3：路线3（高投入，核心功能）
- GLM-5.1 自由组卷初稿
- 系统自动补全考点
- 多轮交互流程（教师 ↔ LLM）
- diff 驱动的检索和归纳

### Phase 4：交互界面
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
| LLM 驱动 grep | 新增 `core_new/doc_pipeline/skills/question_search/SKILL.md` |
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
Step 1 [config:interaction, ~200 chars]: 生成 grep 关键词
  Prompt: "给定知识点'{name}'，生成3-5个grep关键词搜索相关题目"
Step 2 [Python]: grep 检索题库 data/question_experiences/*.md
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
Step 4 [config:interaction, ~5K/知识点]: 对保留知识点执行路线2的 grep+归纳流程
Step 5 [教师]: 选择考察模式
Step 6 [Python]: 生成 outline_draft.md
```

### 9.5 上下文预算总览

| 步骤 | 路线 | 上下文 | 模型来源 | 可并行 |
|------|------|--------|---------|--------|
| 渲染卡片 | 1 | ~2K/slot | config:interaction | 是 |
| grep关键词 | 2 | ~200 chars | config:interaction | 否 |
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
2. 路线2: grep 检索+归纳 <15s
3. 路线3: GLM 初稿 <90s，后续每轮 <15s
4. 总 token 消耗降低 50%+
5. 不再出现 244s 的深度推理超时
