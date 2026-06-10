# interact_core 技能

## 目标

教师交互核心技能，负责场景识别、信息检索、文档生成和教师标注读取。
根据教师输入和系统已有数据，选择不同的信息收集方式，生成带标记位的 md 文档，
教师标注后读取结果生成交接 yaml。

## 场景识别

### 判断规则

```
有预抽取经验卡（408/期末/模拟卷）  → 场景 A
教师指定知识点（AVL/Cache/KMP）    → 场景 B
教师只给科目+考试类型（无经验卡）   → 场景 C
```

多场景命中 → 优先 A > B > C（有经验卡优先使用）。

### 场景 A：408 组卷（有预抽取信息）

教师说："出一套408模拟卷" 或 "出一套组成原理期末卷"
系统有：经验卡（含每题位的考察模式统计）、KG、题位模板

经验卡已预总结考察模式（如"Q{N}: {考察模式1}占比%、{考察模式2}占比%"），因此可以**一轮完成**。

```
Step 1 [read_file]: 加载经验卡（仅相关题位）
Step 2 [exec_python]: 调用 extract_slot_recommendation() 解析经验卡
Step 3 [LLM 渲染]: 为每个题位展示知识点+考察模式（从经验卡提取）

  <!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
  每个题位格式：
  ## Q{N}（{题型}·{分值}分）
  [ ] {知识点A} — {考察模式1}：{描述}（{认知特征}）
  [ ] {知识点A} — {考察模式2}：{描述}（{认知特征}）
  [ ] {知识点B} — {考察模式3}：{描述}（{认知特征}）

  关键：每个选项 = 知识点 × 考察模式，不是单独的知识点。
  经验卡中已按知识点分组的考察模式直接渲染，不编造。

Step 4 [暂停]: 教师在文档上标记 √/x、写批注
Step 5 [read_file]: 读取教师标注后的文档
Step 6 [exec_python 或 LLM]: 解析标注，抽取知识点+考察模式
Step 7 [write_file]: 生成 paper_request.yaml（每个slot含 k_radar + k_dominant + k_source + difficulty_rationale）
```

信息来源：系统预抽取（经验卡 + KG）。LLM 只做渲染和归纳，不编造信息。

**下游对接**：paper_request.yaml 中的 `examination_mode` + `excluded_knowledge`
决定下游 artifact_store 取哪段经验卡、标记排除哪些知识点和往年题。

### 场景 B：知识点出题

教师说："出一道 AVL 树旋转题" 或 "考 Cache 映射"
系统有：题库、KG

```
Step 1 [LLM]: 基于知识点名称生成 grep 关键词（简短推理，不加载外部上下文）
Step 2 [grep_search]: 搜索题库
Step 3 [LLM 归纳]: 将检索结果按考察模式分类
Step 4 [write_file]: 生成带标记位的 md 文档
Step 5 [暂停]: 教师在文档上选择考察模式、写批注
Step 6 [read_file]: 读取教师标注后的文档
Step 7 [write_file]: 生成 slot_blueprint.yaml
```

信息来源：grep 检索 + LLM 归纳。

### 场景 C：自由组卷（无预信息）

教师说："出一套数据结构期末卷"（系统无经验卡）
系统无：经验卡、预抽取信息

无经验卡时缺少考察模式数据，需**两轮迭代**：先选知识点，再展开考察模式。

```
═══ Round 1：知识点选择（粗筛）═══

Step 1 [LLM，不加外部上下文]:
  纯粹基于自身内部知识，为每个题位分配知识点候选。
  不加载 KG、不加载经验卡。快且不触发深度思考。

  <!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
  每个题位只列知识点（不展开考察模式）：
  ## Q{N}（{题型}·{分值}分）
  [ ] {知识点A} — {简要描述}
  [ ] {知识点B} — {简要描述}
  [ ] {知识点C} — {简要描述}

Step 2 [write_file]: 生成带标记位的 md 文档
Step 3 [暂停]: 教师在每个题位选择一个知识点，可修改/添加批注
Step 4 [read_file]: 读取教师标注后的文档

═══ Round 2：考察模式展开（细筛）═══

Step 5 [grep_search]: 对教师选中的知识点检索题库
Step 6 [LLM 归纳]:
  基于检索结果归纳真实考察模式（优先）；
  若检索不足则用 LLM 内部知识补充。
  为每个已选知识点展示 3-5 个考察模式：

  ## Q{N} {知识点} — 考察模式
  [ ] 栈的操作序列合法性判断（需多步推演）
  [ ] 队列的应用场景辨析（概念辨析）
  [ ] 双端队列的操作特性（概念辨析）
  > 教师批注: 重点考操作序列

Step 7 [write_file]: 更新草案文档
Step 8 [暂停]: 教师选择考察模式
Step 9 [read_file]: 读取教师标注后的文档
Step 10 [write_file]: 生成 paper_request.yaml（每个slot含 k_radar + k_dominant + k_source + difficulty_rationale）
```

信息来源：LLM 内部知识（知识点初稿）→ 教师筛选 → grep 验证（考察模式）→ 教师确认。

**关键点**：
- Round 1 不加载 KG、不加载经验卡，纯粹用 LLM 内部知识选知识点
- Round 2 对选中的知识点做精确检索，从检索结果中归纳考察模式
- 若 grep 结果不足（题库未覆盖），fallback 到 LLM 生成考察模式

**下游对接**：同场景 A，examination_mode + excluded_knowledge 决定下游组装范围。

## 工具使用指南

### grep_search：搜索题库

搜索 `data/question_experiences/` 中的题目经验文档。工具名沿用
`grep_search`，但底层不是全文 grep；当前实现委托
`compose/knowledge_index.py` 的结构化标签索引，优先匹配知识点标签、标签叶节点、科目和文件名。

**多关键词批量搜索**：`query` 接受字符串数组，多个关键词在一次调用中搜索。
多关键词命中同一文件时会累加分数，不会重复返回。

<!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
```json
{"query": ["{关键词1}", "{关键词2}", "{关键词3}"], "max_results": 20, "subject": "{科目}"}
```

**重要**：检查多个相关知识点时，务必用数组一次搜索，不要逐个关键词调用。
例如检查多个题位的覆盖情况时：

<!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
```json
{"query": ["{关键词1}", "{关键词2}", "{关键词3}", "{关键词4}"], "max_results": 30}
```

返回格式：
```yaml
ok: true
count: 7
results:
  - file: "2009_Q5.md"
    score: 15.0
    snippet: "..."
    matched_tags: ["平衡二叉树", "旋转"]
```

### read_file：读取系统数据

**注意**：如果 system prompt 中已包含"已加载的知识点图谱"段落，说明 KG 已预加载，
无需再 read_file 读取 KG 文件。

可读取的文件：
- 经验卡：`data/slot_experiences/Q{N}_experience.md`
- 题目经验：`data/question_experiences/{id}.md`
- 教师标注后的文档：`compose/interact_draft.md`

**去重规则**：已读过的文件不会重复返回完整内容。如果文件未修改，系统会返回
"文件未修改，内容已在历史上下文中"。写文件后对应缓存自动失效。

### exec_python：执行数据处理

`exec_python` 接收完整 Python 代码并返回 stdout/stderr。当前没有预注册的
`extract_from_marked_doc()` 全局函数；如果需要从教师标注 md 抽取结构化数据，必须在传入代码中显式实现解析逻辑，或直接由 LLM 根据已读取的标注文档生成交接 YAML。

可复用的现有模块/函数包括：
- `compose.compose_runner.extract_slot_recommendation(card_text)` — 从经验卡提取推荐模式
- `compose.compose_runner.load_kg_for_subjects(subjects)` — 按需加载 KG
- `compose.free_compose.auto_complete_from_kg(knowledge_points, kg_text)` — KG 自动补全
- `interact.knowledge_retriever.KnowledgeRetriever.compute_statistics()` — K 值统计

### write_file：输出文档

- collecting/reviewing 阶段：输出带 `[✓]`/`[✗]` 标记位的 md 文档
- confirmed 阶段：输出交接 yaml（paper_request.yaml / slot_blueprint.yaml）

**硬规则**：reviewing 阶段不得 write_file 任何 .yaml 交接文档。

## 文档标记规范

### 信息收集文档格式

**面向教师的草案只使用自然语言描述认知特征，不使用数字评分或 K 值术语。**

草案格式因场景而异，但核心结构一致：每个选项行用 `[ ]` 标记，括号内标注认知特征话术。

**场景 A/C — 组卷草案（多题位）：**

<!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
```markdown
# 试卷大纲草案

## Q{N}（{题型}·{分值}分）
[✓] {知识点A} — {考察模式}：{描述}（{认知特征}）
[ ] {知识点B} — {考察模式}：{描述}（{认知特征}）
[✗] {知识点C} — {考察模式}：{描述}（{认知特征}）
> 教师批注: {批注内容}

## Q{N+1}（{题型}·{分值}分）
[✓] {知识点D} — {考察模式}：{描述}（{认知特征}）
```

**场景 B — 单题考察模式草案：**

<!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->
```markdown
# {知识点} — 考察模式草案

[ ] {考察模式1}：{描述}（{认知特征}）
[✓] {考察模式2}：{描述}（{认知特征}）
[✗] {考察模式3}：{描述}（{认知特征}）
> 教师批注: {批注内容}
```

**认知特征话术对照（仅内部使用，不暴露给教师）：**

| 考察特征 | 教师看到的话术 | 内部映射 |
|----------|--------------|---------|
| 需记忆概念/术语 | （概念辨析） | K1 |
| 需一步公式代入 | （需一步公式推导） | K2 |
| 需多步流程推演 | （需多步推演） | K3 |
| 需多知识点交叉 | （综合性分析） | K4 |
| 需设计/开放推理 | （综合运用） | K5 |

### 标记含义

| 标记 | 含义 | 系统行为 |
|------|------|---------|
| `[✓]` | 保留这个知识点/模式 | → selected_knowledge |
| `[✗]` | 排除这个知识点/模式 | → excluded.knowledge |
| `[ ]` | 未标记（默认排除） | → 不进入交接文档 |
| `> 教师批注:` | 教师附加说明 | → teacher_annotation |

### 教师操作

- 把 `[ ]` 改为 `[✓]` = 选中
- 把 `[ ]` 改为 `[✗]` = 排除
- 添加 `> 教师批注:` 行 = 附加说明
- 删除整个题位节 = 移除该题位
- 修改知识点名称 = 更新知识点

### Python 抽取

教师确认后，可以在 `exec_python` 传入代码中实现类似
`extract_from_marked_doc(edited_md)` 的解析逻辑，从标注后的 md 抽取：

```python
def extract_from_marked_doc(edited_md: str) -> dict:
    """从教师标注后的 md 文档抽取结构化需求。"""
    # 1. 按标题分割为各题位节
    # 2. 提取 [✓] 行 → selected_knowledge
    # 3. 提取 [✗] 行 → excluded.knowledge
    # 4. 提取 > 教师批注: → teacher_annotation
    # 5. 解析题号、题型、分值
    # 返回 {slots: [{slot_id, selected_knowledge, excluded, teacher_annotation}]}
```

## KG 使用边界

**可以用 KG 做：**
- 知识点对齐（用户说"Cache"，映射到 KG 中的具体节点）
- 子知识点候选展示（KG h4 层级的考点列表）
- 排除项识别（用户说"不考X"，KG 确认 X 的范围）
- 相近考点推荐（KG 兄弟节点）

**不可以用 KG 做：**
- 不从 KG 编造考法或出题模式
- 不从 KG 推断题目难度或干扰项
- 不把 KG 兄弟节点直接写入 selected_knowledge（需教师标记 `[✓]`）

## 分层回退策略

```
Level 0: 有经验卡 → 场景 A（直接加载）
Level 1: 有明确知识点 → 场景 B（grep 检索）
Level 2: 只有科目信息 → 场景 C（LLM 内部知识初稿）
Level 3: 信息不足 → collecting 状态，追问教师
Level 4: 超出系统范围 → 拒绝并说明
```

## 禁止事项

- 不写题、不写正式大纲（含 CONTRACT）、不做 design_card
- 不在 reviewing 阶段写入交接 yaml
- 不混用输出格式（paper 路径不产 slot_blueprint）
- 不把 KG 兄弟节点直接写入 selected_knowledge
- 不从 KG 编造考法或推断难度
- 不替教师做最终决策（教师必须标注 `[✓]`/`[✗]`）

## 输出格式示例

### paper_request.yaml（仅用于 task_type=paper）

```yaml
schema_version: paper_request_v1

source:
  intake_type: interact_agent
  scenario: A_408_exp | C_free_compose

assessment:
  type: course_final | kaoyan_408 | topic_practice
  subjects: ["{科目}"]
  total_score: 100
  duration_minutes: 120

knowledge_scope:
  primary_chapters: []
  focus_points: []
  excluded_points: []
  coverage_strategy: balanced

question_config:
  types:
    - type: single_choice
      count_range: [5, 5]
      score_per: 2

difficulty:
  target: medium
  distribution:
    easy: 30
    medium: 50
    hard: 20

slots:
  - slot_id: Q1
    question_type: single_choice
    score: 2
    target_subject: "{科目}"
    target_family: "{科目} > {章节} > {知识点}"
    primary_target_name: "{知识点名称}"
    target_difficulty: 3
    k_radar:
      K1: 2
      K2: 4
      K3: 1
      K4: 3
      K5: 1
    k_dominant: "K2"
    k_source: "{数据来源}"
    difficulty_rationale: "{难度判据描述}"
    examination_mode: "{考察模式描述}"
    teacher_annotation: ""

teacher_preferences:
  require: []
  avoid: []
  style_notes: ""
  annotations: {}
```

**重要**：每个 slot 必须包含 `k_radar`（5 维认知向量）、`k_dominant`、`k_source`
和 `difficulty_rationale`。K 值不向教师展示，仅在交接 YAML 中出现。
获取方式见 interact.md 中的"K-radar 数据获取规则"。

### slot_blueprint.yaml（仅用于 task_type=single_question）

```yaml
schema_version: slot_blueprint_v1
slot_id: TOPIC_001
question_type: single_choice
score: 2
target_subject: "{科目}"
target_family: "{科目} > {章节} > {知识点}"
primary_target_name: "{知识点名称}"
target_difficulty: 3
k_radar:
  K1: 1
  K2: 2
  K3: 4
  K4: 2
  K5: 1
k_dominant: "K3"
k_source: "question_aggregate"
difficulty_rationale: "{难度判据描述}"
examination_mode: ""
teacher_annotation: ""
active_selection:
  mode_id: topic_selected
  selected_knowledge:
    - "{知识点1}"
    - "{知识点2}"
excluded_modes: []
excluded_knowledge: []
routing:
  can_route: true
  next_action: run_single_pipeline
```

兼容说明：下游 `compose/single_question_adapter.py` 仍接受旧字段
`difficulty_level`、`k_target` 和旧嵌套字段 `excluded: {modes, knowledge}`，
但新写出的 `slot_blueprint.yaml` 应优先使用 `k_radar`、`k_dominant`、`k_source`、
`target_difficulty`、`excluded_modes`、`excluded_knowledge`。

## Phase 范围

本技能 Phase 0.5 实现场景 A 和 B（有经验卡或有明确知识点）。
场景 C（自由组卷）和 retrieval 路径在后续 Phase 加入。
