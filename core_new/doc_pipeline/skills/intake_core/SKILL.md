# intake_core 技能

## 目标

核心意图路由和需求收集技能，负责从教师自然语言中识别意图、加载 KG 知识图谱、展示考点候选、检索题库、收集需求信息，并按 task_type 分流输出对应的结构化文件。

## 意图路由规则

### 关键词路由

```
"找题 / 推荐 / 有没有 / 帮我找"     → retrieval
"出一道 / 生成 / 设计 / 原创"       → single_question
"类似 / 仿照 / 改编 / 换参数"       → adaptation
"几道 / 一组 / 练习 / 从基础到提高"  → practice_set
"一套 / 试卷 / 期末卷 / 模拟卷"     → paper
```

### 多意图处理

- 多意图命中 → 展示候选让教师选择
- 无命中 → needs_user_choice
- 不同意图走不同路径，输出不同的文件格式

### 输出文件映射

```
retrieval       → retrieval_query.yaml
single_question → slot_blueprint.yaml
practice_set    → slot_blueprint.yaml (先检索后生成)
paper           → paper_request.yaml
adaptation      → slot_blueprint.yaml (改编约束)
```

## KG 加载规则

### 按科目选择性加载

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

408 全科目时全部加载 (~100KB)

### KG 使用边界

**可以用 KG 做：**
- 知识点对齐 (用户说"Cache"，映射到 KG 中的具体节点)
- 子知识点候选展示 (KG h4 层级的考点列表)
- 排除项识别 (用户说"不考X"，KG 确认 X 的范围)
- 相近考点推荐 (KG 兄弟节点)

**不可以用 KG 做：**
- 不从 KG 编造考法或出题模式
- 不从 KG 推断题目难度或干扰项
- 不把 KG 兄弟节点自动写入教师已确认的需求

### KG 节点分区规则

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

## 题库检索策略

多字段加权 grep on data/question_experiences/*.md:

```python
FIELD_WEIGHTS = {
    "knowledge": 5,   # **知识点** 行
    "title": 3,       # 标题行
    "body": 1,        # 正文
}
```

## route_gate

### paper_route_gate

```yaml
paper_route_gate:
  required:
    - task_type=paper
    - assessment.type
    - assessment.subjects (array)
    - question_config 或 assessment.total_score 或 assessment.duration_minutes
    - knowledge_scope.primary_chapters 或 knowledge_scope.focus_points
    - difficulty.target
  output:
    - paper_request.yaml
```

### single_question_route_gate

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

### retrieval_route_gate

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

Gate NOT passed → output_policy forbids downstream files
Gate passed → output exactly one route_output file

## 追问规则

- 只问改变任务性质的问题
- 给 2-4 个候选 + 默认推荐
- 信息够 4/7 核心字段即停止
- "按默认" = 接受推荐

## confidence 分级

```yaml
confidence:
  level: high | medium | low | blocked | unsupported
  missing_fields: []        # 哪些字段用了默认值
  contradictions: []        # 检测到的矛盾
  unverified_scope: false   # 知识点不在 KG 中
  notes: ""                 # 给下游 agent 的提示
```

| level       | 是否可进下游 | 含义 |
|-------------|:-----:|------|
| high        | 是 | 信息完整，KG/题库可对齐 |
| medium      | 是 | 有安全默认值且不改变任务性质，教师已确认或已提示 |
| low         | 否 | 信息弱，需要教师确认默认值后升级为 medium |
| blocked     | 否 | 信息矛盾，必须用户选择 |
| unsupported | 否 | 不在系统覆盖范围 |

硬规则: `low` 不直接进下游。`low` 只能在教师确认默认值后升级为 `medium` 才能路由。

## routing 字段

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

## output_policy (文件产出约束)

```yaml
output_policy:
  gate_not_passed:
    allowed:
      - intake_response.md      # 给教师的对话回复
      - intake_result.yaml      # 内部状态快照
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

## intake 状态

```yaml
intake_status:
  - collecting          # 正在收集信息
  - needs_user_choice   # 需要用户选择候选
  - ready               # 可以路由到下游
  - frontdesk_only      # 只能前台处理，不能进下游
  - rejected            # 超出系统能力，明确拒绝
```

## 分层回退策略

```
Level 0: 正常需求，可直接路由
  例: "组一套数据结构期末卷，100分，重点考树和图"
  处理: intake_status=ready, routing.can_route=true

Level 1: 信息不足，需要追问
  例: "出一道题"
  处理: intake_status=needs_user_choice, routing.can_route=false

Level 2: 信息不足，但有安全默认值
  例: "出一道 KMP 题" → 默认数据结构/中等/选择题
  处理: intake_status=ready, confidence.level=medium

Level 3: 信息矛盾，必须用户选择
  例: "出一道 KMP 的组成原理题"
  处理: intake_status=needs_user_choice, confidence.level=blocked

Level 4: 不在系统覆盖范围
  例: "出一道量子计算题"
  处理: intake_status=frontdesk_only, confidence.level=unsupported

Level 5: 完全不属于出题系统
  例: "帮我写论文"
  处理: intake_status=rejected
```

## 预抽取与合并流程

### 合并规则

```
1. 教师明确指定的 > 预抽取的默认值
2. 教师说"按默认" = 接受预抽取的全部
3. 教师说"不要 X" = 从预抽取中删除 X
4. 教师说"加上 X" = 在预抽取基础上追加 X
5. 冲突时以教师为准，记录到 confidence.contradictions
```

## 禁止事项

- 不写题、不写大纲、不做 design_card
- 不在 gate 未通过时写入下游文件
- 不混用输出格式（paper 路径不产 slot_blueprint）
- 不把 KG 兄弟节点直接写入 focus_points
- 不从 KG 编造考法或推断难度

## 输出格式示例

### paper_request.yaml (仅用于 task_type=paper)

```yaml
schema_version: paper_request_v1

source:
  intake_type: human_input | pre_extracted | merged
  pre_extracted_data: null

assessment:
  type: kaoyan_408 | course_final | topic_practice
  subjects: ["计算机组成原理"]
  total_score: 45
  duration_minutes: null

knowledge_scope:
  primary_chapters: []
  focus_points: []
  excluded_points: []
  coverage_strategy: balanced | focus_heavy | exam_weighted

question_config:
  types:
    - type: single_choice
      count_range: [10, 15]
      score_per: 2
    - type: comprehensive
      count_range: [2, 3]
      score_range: [8, 13]

difficulty:
  target: medium
  distribution:
    easy: 30
    medium: 50
    hard: 20
  anchor_source: kaoyan_408

retrieval_policy:
  prefer_existing: true
  generate_gap: true
  max_scan: 2000
  top_k_per_slot: 3

teacher_preferences:
  require: []
  avoid: []
  style_notes: ""

constraints:
  allow_similar_to_past: false
  min_knowledge_diversity: 3
```

### slot_blueprint.yaml (仅用于 task_type=single_question)

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

### retrieval_query.yaml (仅用于 task_type=retrieval)

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

## Phase I0 范围

本技能在 Phase I0 中仅实现 paper 路径。

Phase I0 包含：
- 意图路由 (仅识别 paper 意图)
- KG 加载 (按科目)
- route_gate (paper_route_gate)
- 输出 paper_request.yaml

Phase I0 不包含：
- single_question / retrieval 路径
- 题库检索
- 预抽取信息合并

这些功能在后续 Phase (I1/I2/I3) 中加入。
