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
系统有：经验卡、KG、题位模板

```
Step 1 [read_file]: 加载经验卡（仅相关题位）
Step 2 [exec_python]: 调用 extract_slot_recommendation() 解析经验卡
Step 3 [LLM 渲染]: 将经验卡数据渲染为带标记位的 md 文档
Step 4 [暂停]: 教师在文档上标记 √/x、写批注
Step 5 [read_file]: 读取教师标注后的文档
Step 6 [exec_python]: 调用 extract_from_marked_doc() 抽取结构化数据
Step 7 [write_file]: 生成 paper_request.yaml
```

信息来源：系统预抽取（经验卡 + KG）。LLM 只做渲染和归纳，不编造信息。

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

```
Step 1 [LLM，不加外部上下文]:
  纯粹基于自身内部知识，为每个题位分配知识点和考察方式。
  不加载 KG、不加载经验卡。快且不触发深度思考。

  输出格式（md 表格）：
  | 题号 | 题型 | 知识点 | 考察方式选项 | 难度 |

  例：
  | Q1 | 选择题 | 栈与队列 | 栈的操作序列/队列的应用场景/双端队列辨析 | 3 |
  | Q2 | 选择题 | 二叉树遍历 | 前中后序遍历/层序遍历/遍历序列还原 | 3 |

Step 2 [write_file]: 生成带标记位的 md 文档
Step 3 [暂停]: 教师在文档上标记 √/x、改知识点、加批注
Step 4 [read_file]: 读取教师标注后的文档
Step 5 [grep_search]: 对教师保留的知识点检索题库
Step 6 [LLM 归纳]: 归纳检索结果，更新文档中的考察方式详情
Step 7 [暂停]: 教师确认最终方案
Step 8 [exec_python]: 调用 extract_from_marked_doc() 抽取结构化数据
Step 9 [write_file]: 生成 paper_request.yaml
```

信息来源：LLM 内部知识（初稿）→ 教师筛选 → grep 验证和补充。

**关键点**：场景 C 的 Step 1 不加载 KG、不加载经验卡。LLM 纯粹基于自身知识出大纲。只有教师确认后，才对保留的知识点做精确检索。

## 工具使用指南

### grep_search：搜索题库

搜索 `data/question_experiences/` 中的题目经验文档。

加权策略：
```
knowledge: +5  # 知识点行
title:    +3  # 标题行
body:     +1  # 正文
```

调用方式：
```
grep_search(["AVL", "平衡二叉树", "旋转"])
```

返回格式：
```yaml
ok: true
count: 7
results:
  - file: "2009_Q5.md"
    score: 15.0
    snippet: "..."
```

### read_file：读取系统数据

可读取的文件：
- KG 文件：`data/kg/computer_organization.md`、`data/kg/data_structure.md`、`data/kg/operating_system_knowledge.md`、`data/kg/computer_network.md`
- 经验卡：`data/slot_experiences/Q{N}_experience.md`
- 题目经验：`data/question_experiences/{id}.md`
- 教师标注后的文档：`compose/interact_draft.md`

### exec_python：执行数据处理

可调用的 Python 函数：
- `extract_slot_recommendation(card_text)` — 从经验卡提取推荐模式
- `extract_from_marked_doc(edited_md)` — 从教师标注后的 md 抽取结构化数据
- `auto_complete_from_kg(knowledge_points, kg_text)` — KG 自动补全
- `load_kg_for_subjects(subjects)` — 按需加载 KG
- `compute_statistics()` — K 值统计

### write_file：输出文档

- collecting/reviewing 阶段：输出带 `[✓]`/`[✗]` 标记位的 md 文档
- confirmed 阶段：输出交接 yaml（paper_request.yaml / slot_blueprint.yaml）

**硬规则**：reviewing 阶段不得 write_file 任何 .yaml 交接文档。

## 文档标记规范

### 信息收集文档格式

```markdown
# 试卷大纲草案

## Q1（选择题·2分）
[✓] CPU性能指标 — 公式计算 (难度3)
[ ] 浮点数表示 — IEEE754标准 (难度4)
[✗] 指令流水线 — 冲突检测 (难度3)
[ ] Cache映射 — 地址翻译 (难度5)
> 教师批注: Cache映射要考直接映射和组相联的对比

## Q2（选择题·2分）
[✓] 中断系统 — 中断处理流程 (难度3)
> 教师批注: 要考硬件中断和软件中断的区别
```

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

教师确认后，调用 `extract_from_marked_doc(edited_md)` 从标注后的 md 抽取：

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
  subjects: ["计算机组成原理"]
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

teacher_preferences:
  require: []
  avoid: []
  style_notes: ""
  annotations: {}
```

### slot_blueprint.yaml（仅用于 task_type=single_question）

```yaml
schema_version: slot_blueprint_v1
slot_id: TOPIC_001
question_type: single_choice
score: 2
target_subject: 数据结构
target_family: 数据结构 > 树与二叉树 > 平衡二叉树
primary_target_name: AVL树旋转
difficulty_level: 3
examination_mode: ""
teacher_annotation: ""
active_selection:
  mode_id: topic_selected
  selected_knowledge:
    - AVL树旋转操作
    - 平衡因子计算
excluded:
  modes: []
  knowledge: []
routing:
  can_route: true
  next_action: run_single_pipeline
```

## Phase 范围

本技能 Phase 0.5 实现场景 A 和 B（有经验卡或有明确知识点）。
场景 C（自由组卷）和 retrieval 路径在后续 Phase 加入。
