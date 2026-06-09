# 信息交互层设计文档 v2.1-final (简化版)

> 基于 Spec v1 的核心思想，经分析简化后的可落地方案。
> v2: 收紧 route_gate，无效需求不进下游 (Codex review 修正)
> v2.1: 补齐 route schema、low 不可直接路由、最小字段定义 (Codex 二审)
> v2.1-final: 应用 Codex 终审 5 补丁 (adapter/skill描述/I0范围/subjects数组/output_policy)
> 日期: 2026-06-09

## 1. 核心原则

1. **KG 全量加载** — 4 个 KG 文件共 100KB，按科目加载进上下文，无需检索工具
2. **题库结构化标签索引** — 2058 个真题经验文件，预解析知识点元数据，标签反向索引精确匹配（已替代加权 grep）
3. **doc_pipeline 零改动，compose_runner 最小适配** — intake 只负责生成输入，下游出题链路不变
4. **对话即状态** — 复用对话上下文管理多轮交互，不造新状态机
5. **无效需求不进下游** — 只有通过 route_gate 的结构化需求才允许进入下游团队
6. **按任务类型输出不同文件** — paper_request / slot_blueprint / retrieval_query 不混用

## 2. 架构总览

```
教师自然语言
  ↓
intake_agent (对话式，加载 KG + 标签索引搜索题库)
  │
  ├─ 识别意图: 组卷 / 单题 / 找题 / 练习集
  │
  ├─ 加载对应科目 KG 到上下文
  │   data/kg/computer_organization.md  (~27KB)
  │   data/kg/data_structure.md         (~28KB)
  │   data/kg/operating_system_knowledge.md (~27KB)
  │   data/kg/computer_network.md       (~20KB)
  │
  ├─ 展示考点候选，教师选择
  │
  ├─ knowledge_index 标签索引搜索题库 (data/question_experiences/)
  │
  ├─ route_gate 检查 ──────────────────────┐
  │   信息完整?  → 生成结构化输出            │
  │   信息不足?  → 追问 (留在前台)          │
  │   信息矛盾?  → 请教师选择 (留在前台)    │
  │   超出范围?  → 推荐替代 (留在前台)      │
  │                                        │
  └─ 通过 gate 后按任务类型输出:            │
      │                                    │
      ├─ paper → paper_request.yaml ──→ compose_runner (不变)
      ├─ single → slot_blueprint.yaml → doc_pipeline (不变)
      └─ retrieval → retrieval_query.yaml → grep 题库返回结果
                                          │
                                    教师审核 outline (现有批注流程不变)
                                          ↓
                                    现有 parser + sidecar + doc_pipeline (不变)
```

## 3. 与 Spec v1 的差异

| 维度 | Spec v1 | 本方案 |
|------|---------|--------|
| 新 agent 数量 | 2 (intake + handoff) | 1 (intake) |
| 新 skill 数量 | 19 | 3 (core + single_q + paper) |
| 新工具 | 5 个 | 0 (KG 直接读，题库 grep) |
| 状态管理 | 3 层嵌套状态机 | 对话上下文 + 单文件 |
| 中间产物 | topic_blueprint 等 | paper_request / slot_blueprint / retrieval_query |
| doc_handoff agent | 独立 agent | 取消，职责合并进 intake |
| 下游改动 | 需要适配 | doc_pipeline 零改动，compose_runner 最小适配 |

## 4. 取消 doc_handoff 的理由

doc_handoff 的核心职责是：读取 task_contract → 读取 KG → 组装 topic_blueprint。

但现有链路已有等价能力：

```
SlotBlueprint → design_card_v1 skill → question_design agent → question.md
```

intake 直接输出 `SlotBlueprint` 格式（或 paper_outline agent 需要的输入格式），
下游无需任何改变。

## 5. intake_agent 设计

### 5.1 角色定位

- 面向教师的对话式智能体
- 加载 KG、检索题库、收集需求
- 输出下游可执行的结构化文档
- **不做**: 写题、写选项、写大纲、写 design_card

### 5.2 输入源

intake agent 可以接收两类输入的合并：

1. **教师实时输入** — 对话中的自然语言需求
2. **预抽取信息** — 系统已收集的考点、题型、难度等结构化数据

合并逻辑：

```
预抽取信息 (如果有)
  + 教师实时输入
  = intake_result (内部状态)
  → 根据 task_type 分流输出:
     paper           → paper_request.yaml
     single_question → slot_blueprint.yaml
     retrieval       → retrieval_query.yaml
```

典型场景：

- **408 组卷**: 预抽取 408 考纲 + 题位分布，教师只需确认/微调
- **期末出题**: 预抽取课程大纲覆盖范围，教师选择重点章节
- **单题生成**: 无预抽取，纯教师输入
- **找题**: 无预抽取，关键词检索

### 5.3 KG 加载策略

按科目选择性加载，不一次性加载全部：

```yaml
kg_loading:
  data_structure:
    file: data/data_structure.md
    size: 28KB
    load_when: 科目包含"数据结构"
  computer_organization:
    file: data/computer_organization.md
    size: 27KB
    load_when: 科目包含"组成原理"
  operating_system:
    file: data/operating_system_knowledge.md
    size: 27KB
    load_when: 科目包含"操作系统"
  computer_network:
    file: data/computer_network.md
    size: 20KB
    load_when: 科目包含"计算机网络"
```

408 全科目时总计 ~100KB，仍可全部加载。

### 5.4 KG 使用边界

KG 是知识点名词库，提供层级和属性，**不提供**定义、公式、组合方式或真题风格。

intake 可以用 KG 做：
- 知识点对齐 (用户说"Cache"，映射到 KG 中的具体节点)
- 子知识点候选展示 (KG h4 层级的考点列表)
- 排除项识别 (用户说"不考X"，KG 确认 X 的范围)
- 相近考点推荐 (KG 兄弟节点)

intake **不可以**用 KG 做：
- 不从 KG 编造考法或出题模式
- 不从 KG 推断题目难度或干扰项
- 不把 KG 兄弟节点自动写成教师已确认的需求

复杂考法仍由下游承担：题库经验 / slot experience / paper_outline / question_design。

### 5.5 KG 节点分区规则

```yaml
kg_node_classification:
  confirmed_nodes:
    # 用户明确选择或安全默认确认的节点
    # → 可进入 focus_points / selected_knowledge
  candidate_nodes:
    # KG 子树中展示给用户选择的节点
    # → 只进入 candidate_options
  neighbor_nodes:
    # KG 兄弟节点和邻近节点
    # → 只能用于替代推荐或 forbidden_shift 判断
    # → 不得直接进入 focus_points / selected_knowledge
```

硬规则: KG 兄弟/邻居节点不得直接写入 focus_points。只有用户明确选择后才能升级为 confirmed。

### 5.6 题库检索策略（已实现 → `compose/knowledge_index.py`）

不构建向量检索，使用结构化标签反向索引（预解析元数据，替代全文本 grep）：

```python
# 已实现：compose/knowledge_index.py
class KnowledgeIndex:
    """预构建的知识点反向索引：tag_segment → [file_names]"""

    def search(self, query, max_results=30, subject=None) -> list[SearchHit]:
        # 评分策略：
        # 精确匹配知识点: +10
        # 子串匹配知识点: +5
        # 匹配标签叶节点: +5
        # 匹配标签段:     +3
        # 匹配文件名:     +2
        ...

# 使用方式
from compose.knowledge_index import search_questions
hits = search_questions(["AVL树", "旋转"], max_results=20)
```

实测：
- 2058 文件已索引，1772 个标签段
- 精确匹配知识点比全文本 grep 更准确（避免正文噪音）
- 支持按科目过滤

注: 同义词问题 (Cache地址映射/Cache字段划分/主存块映射) 第一版可接受，
后续可加同义词映射表补充，不需要上向量检索。

### 5.7 paper_request.yaml Schema (组卷)

仅用于 task_type=paper：

```yaml
schema_version: paper_request_v1

# 来源
source:
  intake_type: human_input | pre_extracted | merged
  pre_extracted_data: null  # 预抽取信息的引用或内嵌

# 评估配置
assessment:
  type: kaoyan_408 | course_final | topic_practice
  subjects: ["计算机组成原理"]  # 单科用单元素数组，408 全科用四元素数组
  total_score: 45
  duration_minutes: null

# 知识范围
knowledge_scope:
  primary_chapters: []       # KG h3 层级的主要章节
  focus_points: []           # 教师指定的重点考点
  excluded_points: []        # 教师排除的考点
  coverage_strategy: balanced | focus_heavy | exam_weighted

# 题型配置
question_config:
  types:
    - type: single_choice
      count_range: [10, 15]
      score_per: 2
    - type: comprehensive
      count_range: [2, 3]
      score_range: [8, 13]

# 难度配置
difficulty:
  target: medium
  distribution:
    easy: 30
    medium: 50
    hard: 20
  anchor_source: kaoyan_408

# 题库策略
retrieval_policy:
  prefer_existing: true        # 优先使用题库已有题
  generate_gap: true           # 题库不足时生成补足
  max_scan: 2000
  top_k_per_slot: 3

# 教师偏好
teacher_preferences:
  require: []                  # 必须考的知识点
  avoid: []                    # 不能考的知识点
  style_notes: ""              # 风格备注

# 约束
constraints:
  allow_similar_to_past: false  # 是否允许与历年真题相似
  min_knowledge_diversity: 3    # 最少覆盖的知识子域数
```

### 5.8 slot_blueprint.yaml Schema (单题)

仅用于 task_type=single_question。复用现有 `SlotBlueprint` dataclass：

```yaml
schema_version: slot_blueprint_v1
slot_id: TOPIC_001
question_type: single_choice | comprehensive
score: 2
target_subject: 数据结构
target_family: 数据结构 > 查找 > 字符串模式匹配
primary_target_name: KMP算法
difficulty_level: 3
k_target: ""
examination_mode: ""
teacher_annotation: ""
active_selection:
  mode_id: topic_selected
  mode_name: ""
  selected_knowledge:
    - KMP算法
    - next数组构造
candidate_pool_visible: []
excluded:
  modes: []
  knowledge: []
confidence:
  level: high | medium
routing:
  can_route: true
  next_action: run_single_pipeline
```

注: 字段名以现有 `contracts.py` 中 `SlotBlueprint` dataclass 为准。
此处 schema 用于 route_gate 校验和 skill 输出规范。

### 5.9 retrieval_query.yaml Schema (找题)

仅用于 task_type=retrieval。不进生成流水线：

```yaml
schema_version: retrieval_query_v1
task_type: retrieval

query:
  keywords: [Cache, 地址映射]
  knowledge_tags: []
  subject: ""
  assessment_type: ""
  question_type: ""
  difficulty: ""

policy:
  max_scan: 2000
  top_k: 10
  search_fields:
    knowledge: 5
    title: 3
    body: 1

routing:
  can_route: true
  next_action: retrieve
```

### 5.10 retrieval_result.md 格式

检索结果的标准输出格式：

```markdown
# retrieval_result

## query_summary
- keywords: Cache, 地址映射
- subject: 计算机组成原理
- top_k: 10

## results

### R1
- path: data/question_experiences/2016_Q45.md
- score: 8
- matched_fields: knowledge=Cache组相联映射, title=Cache
- knowledge: Cache组相联映射, 主存块号计算, 组号计算
- difficulty: 中等
- question_type: comprehensive
- recommendation_reason: 知识点高度匹配，综合性强
```

### 5.11 与现有 compose_runner 的衔接

compose_runner 当前输入：

```python
# compose_runner.py 的 run_compose()
# 当前从 CLI 参数获取科目、模式等信息
# 新增: 如果 compose_dir 中有 paper_request.yaml，优先读取
```

衔接方式：

```
intake_agent 输出 paper_request.yaml
  ↓
compose_runner 检测到 paper_request.yaml
  ↓
提取科目、范围、难度、题型配置
  ↓
传给 paper_outline_agent 生成 outline 初稿
  ↓ (现有流程不变)
```

**对 compose_runner 的最小改动**: 增加一个 `load_paper_request()` 函数，
读取 paper_request.yaml 并映射到现有参数。如果文件不存在，走现有逻辑。

### 5.12 单题与 generate_runner 的衔接 (single_question_adapter)

单题路径不经过 compose_runner，而是直接进入 doc_pipeline 的 generate_runner：

```
intake_agent 输出 slot_blueprint.yaml
  ↓
single_question_adapter (轻量适配层):
  - 读取 slot_blueprint.yaml
  - 构造 BlueprintMap: {slot_id: SlotBlueprint}
  - 调用 generate_runner.run_generate(blueprint_map, ...)
  ↓
doc_pipeline 现有流程 (question_design → question_writer → solver → final_review)
```

适配要点：
- `SlotBlueprint` dataclass 已在 `contracts.py` 中定义，slot_blueprint.yaml 通过 `normalize_slot_blueprint_data()` 反序列化为该类型
- `generate_runner._load_blueprint_map()` 当前从 paper_selection.yaml 加载；适配后优先读 intake 输出的单文件
- 无需创建 compose 目录结构，单题直接走 generate 流程

### 5.13 Phase I0 中 paper_request 的作用边界

> **Phase I0 中 `paper_request` 只增强 `user_requirements` 文本和 `model_routing`，
> 不直接改变 slot_template 集合。题位过滤仍由外部 CLI / 组卷入口控制。**

`map_paper_request_to_params()` 返回的 `subject_files` 和 `slot_templates_hints` 为后续 Phase 预留，
Phase I0 中 compose_runner 不消费这两个字段。避免 team 误以为 `question_config` 已能决定题量和题型。

## 6. 意图路由

intake agent 首先识别教师意图，采用规则优先：

```
1. 关键词单命中 → 直接路由
2. 多意图命中 → intake 展示候选并询问
3. 无命中 → needs_user_choice

关键词规则:

"找题 / 推荐 / 有没有 / 帮我找"     → retrieval
"出一道 / 生成 / 设计 / 原创"       → single_question
"类似 / 仿照 / 改编 / 换参数"       → adaptation
"几道 / 一组 / 练习 / 从基础到提高"  → practice_set
"一套 / 试卷 / 期末卷 / 模拟卷"     → paper
```

多意图示例: "给我几道类似真题的新题" → 同时命中 practice_set + adaptation + generation，
由 intake 展示候选让教师选择。

不同意图走不同路径，**输出不同的文件格式**：

```
retrieval       → grep 题库，返回结果 (retrieval_result.md)
single_question → intake → slot_blueprint.yaml → doc_pipeline
practice_set    → intake → 先检索题库 → 不足部分走 doc_pipeline
paper           → intake → paper_request.yaml → compose_runner
adaptation      → intake → 找到原题 → slot_blueprint.yaml(改编约束) → doc_pipeline
```

**重要**: 不同任务类型输出不同的文件，不混用：
- `paper_request.yaml` — 只给组卷
- `slot_blueprint.yaml` — 只给单题 (复用现有 SlotBlueprint dataclass)
- `retrieval_query.yaml` — 只给找题

## 7. 无效需求的回退方案 (Codex review 修正)

### 7.1 核心规则

> **前台 intake 是唯一处理无效、模糊、矛盾需求的智能体。
> 只有通过 route_gate 的结构化需求，才允许进入下游团队。**

下游团队包括：compose_runner、paper_outline_agent、question_design、
question_writer、solver、final_review。这些都不处理"用户到底想干嘛"的问题。

### 7.2 intake 状态

```yaml
intake_status:
  - collecting          # 正在收集信息
  - needs_user_choice   # 需要用户选择候选
  - ready               # 可以路由到下游
  - frontdesk_only      # 只能前台处理，不能进下游
  - rejected            # 超出系统能力，明确拒绝
```

### 7.3 route_gate (分任务 schema)

intake 输出前必须通过对应任务的 route_gate 检查：

**paper_route_gate:**

```yaml
paper_route_gate:
  required:
    - task_type=paper
    - assessment.type
    - assessment.subjects
    - question_config 或 assessment.total_score 或 assessment.duration_minutes
    - knowledge_scope.primary_chapters 或 knowledge_scope.focus_points
    - difficulty.target
  output:
    - paper_request.yaml
```

**single_question_route_gate:**

```yaml
single_question_route_gate:
  required:
    - task_type=single_question
    - target_subject
    - primary_target_name
    - target_family 或 kg_node_path
    - question_type 或 default_question_type
    - difficulty_level 或 difficulty.target
  output:
    - slot_blueprint.yaml
```

**retrieval_route_gate:**

```yaml
retrieval_route_gate:
  required:
    - task_type=retrieval
    - keywords 或 knowledge_tags
  optional:
    - question_type
    - difficulty
    - assessment.type
  output:
    - retrieval_query.yaml
```

只有 route_gate 通过时，才允许生成下游输入文件。

### 7.4 分层回退策略

```
Level 0: 正常需求，可直接路由
  例: "组一套数据结构期末卷，100分，重点考树和图"
  例: "出一道 Cache 地址映射选择题，中等难度"
  处理: intake_status=ready, routing.can_route=true
  进入下游。

Level 1: 信息不足，需要追问
  例: "出一道题"
  例: "组一套卷"
  处理: intake_status=needs_user_choice, routing.can_route=false
  前台追问科目/知识点/题型。
  不进下游。

Level 2: 信息不足，但有安全默认值
  例: "出一道 KMP 题" → 默认数据结构/中等/选择题
  例: "找几道 Cache 题" → 默认组成原理/retrieval
  处理: intake_status=ready, confidence.level=medium
  可以进下游，带默认说明。

Level 3: 信息矛盾，必须用户选择
  例: "出一道 KMP 的组成原理题"
  例: "组一套 408 卷，只考高等数学"
  处理: intake_status=needs_user_choice, confidence.level=blocked
  前台告知矛盾，请教师选择。
  不进下游。

Level 4: 不在系统覆盖范围，前台处理
  例: "出一道量子计算题"
  例: "出一道机器学习反向传播题"
  处理: intake_status=frontdesk_only, confidence.level=unsupported
  前台说明不在覆盖范围，推荐 KG 中相近的可用方向。
  不进下游。不调用任何出题团队。

Level 5: 完全不属于出题系统
  例: "帮我写论文"
  例: "帮我做商业计划书"
  处理: intake_status=rejected
  前台直接拒绝，说明系统能力范围。
  不进任何团队。
```

### 7.5 confidence 字段 (修订版)

```yaml
confidence:
  level: high | medium | low | blocked | unsupported
  missing_fields: []        # 哪些字段用了默认值
  contradictions: []        # 检测到的矛盾
  unverified_scope: false   # 知识点不在 KG 中
  notes: ""                 # 给下游 agent 的提示

warnings: []                # 教师偏好风险提示，例如：
                            # "排除了 Cache 和虚拟内存，可能影响存储系统覆盖"
                            # 前台应向教师确认此类 warning
```

| level       | 是否可进下游 | 含义 |
|-------------|:-----:|------|
| high        | 是 | 信息完整，KG/题库可对齐 |
| medium      | 是 | 有安全默认值且不改变任务性质，教师已确认或已提示 |
| low         | 否 | 信息弱，需要教师确认默认值后升级为 medium |
| blocked     | 否 | 信息矛盾，必须用户选择 |
| unsupported | 否 | 不在系统覆盖范围 |

**硬规则**: `low` 不直接进下游。`low` 只能在教师确认默认值后升级为 `medium` 才能路由。
不再有 `best_effort`。

### 7.6 routing 字段

```yaml
routing:
  can_route: true | false
  next_action: run_compose | run_single_pipeline | retrieve | ask_user | recommend_alternatives | reject
  next_input: paper_request.yaml | slot_blueprint.yaml | retrieval_query.yaml | null
  reason: ""
```

只有三种情况调用团队：

```
1. can_route=true 且 next_action=run_compose
2. can_route=true 且 next_action=run_single_pipeline
3. can_route=true 且 next_action=retrieve
```

其他全部由 intake 前台处理。

### 7.8 output_policy (文件产出约束)

route_gate 的通过与否决定了 intake 允许产出哪些文件，防止中间产物泄漏到下游：

```yaml
output_policy:
  gate_not_passed:
    allowed:
      - intake_response.md      # 给教师的对话回复
      - intake_result.yaml      # 内部状态快照 (intake_status, confidence, routing)
    forbidden:
      - paper_request.yaml
      - slot_blueprint.yaml
      - retrieval_query.yaml

  gate_passed:
    allowed:
      - intake_response.md      # 仍可生成 (确认摘要)
      - 恰好一个 route_output:   # 按 task_type 只生成一种
          paper           → paper_request.yaml
          single_question → slot_blueprint.yaml
          retrieval       → retrieval_query.yaml
    forbidden:
      - 其余两种 route_output   # paper 路径不能同时产 slot_blueprint
```

硬规则: **gate 未通过时，任何下游输入文件 (paper_request / slot_blueprint / retrieval_query) 不得写入磁盘。**

### 7.7 回退文案示例

**模糊需求** — "出一道题"

```
我还不能把这个需求交给出题流水线，因为缺少科目和知识点。
你可以直接补充一句，例如：
1. 出一道数据结构 KMP 题
2. 出一道组成原理 Cache 地址映射题
3. 出一道操作系统进程同步题
你也可以说"按 408 默认推荐一个考点"。
```

**矛盾需求** — "出一道 KMP 的组成原理题"

```
这里有冲突：KMP 通常属于数据结构中的字符串模式匹配，不属于计算机组成原理。
请选择一个方向：
1. 按数据结构 KMP 出题
2. 改成组成原理中的相近机制题，例如 Cache 地址映射或指令流水线
3. 只找已有题，不生成新题
```

**超出范围** — "出一道量子计算题"

```
当前出题系统主要覆盖 408 四科及已接入课程 KG，量子计算不在当前知识图谱
和题库范围内，因此不会调用后端出题流水线。

可以改成以下支持方向：
1. 计算机组成原理：并行处理、存储系统、CPU
2. 操作系统：进程调度、内存管理
3. 数据结构：图算法、查找、排序
4. 计算机网络：可靠传输、路由算法
```

## 8. 预抽取与合并流程

### 8.1 场景: 408 组卷

```
系统预抽取:
  - 408 考纲 (dagang.md) 中的科目和分值分布
  - 题位分布 (40 题 choice + 7 题 comprehensive)
  - 各科目 KG 考点列表
  - 历年真题统计

教师输入:
  - "组一套 408 模拟卷，侧重组成原理"
  - 或 "按默认"

合并:
  预抽取的 408 模板 + 教师的偏好调整 → paper_request.yaml
  paper_request.knowledge_scope.focus_points += ["组成原理"]
  paper_request.difficulty.distribution = 考研标准分布
```

### 8.2 场景: 期末卷 + 预抽取

```
系统预抽取:
  - 课程大纲覆盖范围 (从 dagang.md 或教师上传的教学大纲)
  - 已有题库中该课程范围的题
  - 往年期末卷的题型分布

教师输入:
  - "数据结构期末卷，100分，120分钟"
  - "不考图论"

合并:
  预抽取的课程范围 - 教师排除的部分 → paper_request.yaml
```

### 8.3 合并规则

```
1. 教师明确指定的 > 预抽取的默认值
2. 教师说"按默认" = 接受预抽取的全部
3. 教师说"不要 X" = 从预抽取中删除 X
4. 教师说"加上 X" = 在预抽取基础上追加 X
5. 冲突时以教师为准，记录到 confidence.contradictions
```

## 9. Skill 设计 (精简版)

### 9.1 intake_core

```
核心职责:
  - 意图识别 (关键词路由)
  - KG 加载 (按科目)
  - 考点展示 (从 KG h3/h4 提取)
  - 需求收集 (有限追问)
  - intake_result 分流输出 (按 task_type 生成对应文件)

追问规则:
  - 只问改变任务性质的问题
  - 给 2-4 个候选 + 默认推荐
  - 信息够 4/7 核心字段即停止
  - "按默认" = 接受推荐

不负责:
  - 不写题、不写大纲、不做 design_card
```

### 9.2 intake_single_question

```
适用: 教师要出一道题

流程:
  1. 加载对应科目 KG
  2. 展示该知识点的 KG 子树 (考法候选)
  3. grep 题库找相似真题
  4. 教师选择考法/难度
  5. 输出 SlotBlueprint 格式 (复用现有 contracts.py)
  6. 直接进 doc_pipeline

不需要 paper_request，直接输出 SlotBlueprint。
```

### 9.3 intake_paper

```
适用: 教师要组卷

流程:
  1. 加载对应科目 KG (多科目时全加载)
  2. 如有预抽取信息，展示给教师确认
  3. 教师选择/调整考点范围、难度、题型
  4. grep 题库统计已有题覆盖情况
  5. 输出 paper_request.yaml
  6. 传给 compose_runner

compose_runner 检测到 paper_request.yaml → 作为输入生成 outline。
```

### 9.4 后续 Skill (Phase 2)

```
intake_retrieval     — 找题，不进生成流水线
intake_practice_set  — 练习集，先检索后生成
intake_adaptation    — 改编已有题
```

Phase 1 只做 core + single_question + paper。

## 10. 目录结构

```
core_new/doc_pipeline/
  agents/
    human_intake.md          # 新增

  skills/
    intake_core/SKILL.md     # 新增
    intake_single_question/SKILL.md  # 新增
    intake_paper/SKILL.md    # 新增

  schemas/
    paper_request.schema.yaml  # 新增

compose/
  compose_runner.py          # 小改: 增加 load_paper_request()
```

## 11. 实施阶段

### Phase I0: 最小可用 (paper 路径正式可运行；single/retrieval 仅 schema + 离线验证)

```
目标: 端到端跑通 "教师输入 → intake → paper_request.yaml → compose_runner → outline"

1. 创建 human_intake.md agent (behavior=artifact_writer, skills=[intake_core])
2. 创建 intake_core skill (仅 paper 意图路由)
3. 创建 paper_request.schema.yaml
4. compose_runner 增加 load_paper_request()
5. 测试用例 A/B/C

paper 路径: 正式可运行，compose_runner 实际消费 paper_request。
single_question / retrieval: 仅放 schema 定义 + adapter 代码 + 离线验证测试，
不接入正式 agent 入口。这些在 Phase I3 才正式启用。

不包含: intake_single_question skill、intake_retrieval skill、题库检索、预抽取合并。
```
目标: 端到端跑通 "教师输入 → intake → paper_request.yaml → compose_runner → outline"

1. 创建 human_intake.md agent
2. 创建 intake_core skill (仅 paper 意图路由)
3. 创建 paper_request.schema.yaml
4. compose_runner 增加 load_paper_request()
5. 测试用例 A/B/C

不包含: single_question / retrieval schema 及对应 skill。
这些在 Phase I3 加入，I0 只验证 paper 路径完整链路和 route_gate 机制。
```

验收 A (信息不足不进下游):

```
输入: "组一套数据结构期末卷，100分"
期望:
  - intake_status=needs_user_choice 或 confidence.level=low
  - routing.can_route=false
  - 前台追问章节范围/难度倾向
  - 教师确认后 → confidence 升级为 medium → routing.can_route=true
```

验收 B (信息充足直接路由):

```
输入: "组一套数据结构期末卷，100分，120分钟，全书，中等难度"
期望:
  - intake_status=ready, confidence.level=high
  - routing.can_route=true
  - 输出 paper_request.yaml
  - compose_runner 能读并生成 outline
```

验收 C (超范围拒绝):

```
输入: "出一道量子计算题"
期望:
  - intake_status=frontdesk_only, confidence.level=unsupported
  - routing.can_route=false
  - 不生成任何下游输入文件
```

### Phase I1: KG 集成

```
1. intake_paper skill 加载 KG
2. 展示 KG 考点候选
3. 教师选择后写入 paper_request.knowledge_scope
```

验收: 输入 "组一套组成原理卷，重点考存储系统" → KG 展示存储系统子树 → 教师确认 → paper_request 包含正确的 knowledge_scope。

### Phase I2: 题库检索 + 预抽取

```
1. intake 中集成 grep 检索
2. 支持预抽取信息合并
3. 回退策略 (confidence 字段)
```

验收: 输入 "找几道 Cache 题" → 返回 162 个文件中的 top 10。

### Phase I3: 单题 + 其他意图

```
1. intake_single_question skill
2. 直接输出 SlotBlueprint 进 doc_pipeline
3. retrieval / practice_set / adaptation
```

## 12. 对现有文件的改动清单

| 文件 | 改动 | 说明 |
|------|------|------|
| `core_new/doc_pipeline/agents/human_intake.md` | 新增 | intake agent |
| `core_new/doc_pipeline/skills/intake_core/SKILL.md` | 新增 | 核心意图路由 |
| `core_new/doc_pipeline/skills/intake_single_question/SKILL.md` | 新增 | 单题意图 |
| `core_new/doc_pipeline/skills/intake_paper/SKILL.md` | 新增 | 组卷意图 |
| `core_new/doc_pipeline/schemas/paper_request.schema.yaml` | 新增 | paper_request schema |
| `core_new/doc_pipeline/schemas/slot_blueprint.schema.yaml` | 新增 | 单题 blueprint schema |
| `core_new/doc_pipeline/schemas/retrieval_query.schema.yaml` | 新增 | 找题 query schema |
| `compose/compose_runner.py` | 最小适配 | 增加 `load_paper_request()` |
| doc_pipeline 所有文件 | 无改动 | 出题流水线零影响 |
