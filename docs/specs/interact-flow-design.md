# 教师交互出题 — 后端流程设计文档

> 版本: 1.0 | 日期: 2026-06-10
> 核心原则：教师只说话和裁剪，系统做一切检索、推理、文档生成

---

## 1. 系统角色

| 角色 | 职责 | 技术组件 |
|------|------|---------|
| **教师** | 说话（描述需求）、裁剪（删除不想要的选项） | 前端界面 |
| **Interact Agent** | 理解需求、检索数据、生成草案、读取标注、生成交接文档 | `interact.md` + `SKILL.md` |
| **Scheduler** | 管理对话轮次、执行工具调用、维护会话状态 | `DocScheduler` |
| **V2 Service** | MD↔JSON 转换、会话管理、标注回写 | `interact_v2_service.py` |
| **Draft Parser** | 解析 agent 输出的 markdown 为结构化数据 | `draft_parser.py` |
| **下游流水线** | 消费交接文档，生成正式题目 | `compose/` + `generate/` |

---

## 2. 核心交互循环

整个系统围绕一个循环运转：

```
教师发消息 → Agent 处理 → 返回结果 → 教师看到结果 → 教师决定下一步
     ↑                                                    │
     └────────────────────────────────────────────────────┘
```

**每一步的数据流**：

```
前端                    V2 Service              Scheduler              Agent
  │                        │                       │                    │
  │ POST /turn {message}   │                       │                    │
  │───────────────────────►│ run_conversation_turn │                    │
  │                        │──────────────────────►│ 执行工具循环        │
  │                        │                       │ read_file           │
  │                        │                       │ grep_search         │
  │                        │                       │ exec_python         │
  │                        │                       │ write_file          │
  │                        │                       │────────────────────►│
  │                        │    {response_text,    │                    │
  │                        │     files_written}    │                    │
  │                        │◄──────────────────────│                    │
  │                        │                       │                    │
  │                        │ GET /draft (可选)      │                    │
  │                        │ 解析 agent 写出的 md   │                    │
  │                        │ → DraftData JSON      │                    │
  │                        │                       │                    │
  │  {response_text,       │                       │                    │
  │   has_draft,           │                       │                    │
  │   has_result}          │                       │                    │
  │◄───────────────────────│                       │                    │
```

---

## 3. 会话状态机

```
                    教师首次发消息
                         │
                         ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  collecting  │───►│  reviewing   │───►│  confirmed   │
│  收集需求    │    │  审阅草案    │    │  已确认      │
└─────────────┘    └──────┬──────┘    └─────────────┘
     ▲                 │  │
     │                 │  │ has_draft=true
     │                 │  ▼
     │  教师未确认，    │ ┌─────────────┐
     │  继续追问       │ │  reviewing   │
     └─────────────────┘ │  (有草案)    │
                         └─────────────┘
                              │
                    POST /annotate
                    + POST /turn "已标注"
                              │
                              ▼
                         ┌─────────────┐
                         │  confirmed   │
                         │  交接文档就绪 │
                         └─────────────┘
```

**状态判定规则**（V2 Service 自动判断）：

| 条件 | 状态转换 |
|------|---------|
| `has_result=true` | → `confirmed` |
| `has_draft=true` 且当前是 `collecting` | → `reviewing` |
| Agent 回复中无草案也无结果 | 保持 `collecting` |

---

## 4. 三个场景的完整流程

### 4.1 场景 A：有经验卡（408/期末组卷）

**触发条件**：教师说 "出一套408模拟卷" / "出一套组成原理期末卷"，且系统有对应的经验卡。

```
Turn 1: 教师发消息
─────────────────────────────────────────────────────────────
教师:  "出一套408计算机组成原理模拟卷，选择题Q12-Q16"

Scheduler 做了什么:
  1. 加载 system prompt (interact.md)
  2. 检测到 "组成原理" → 注入 KG 知识图谱
  3. Agent 调用 read_file 加载 Q12-Q16 经验卡
  4. Agent 调用 exec_python read_slot_k_radar("Q14") 获取K-radar数据
  5. Agent 基于经验卡数据，为每个题位生成 "知识点×考察模式" 选项
  6. Agent 调用 write_file 写入 compose/interact_draft.md

Agent 输出（response_text）:
  "好的，我已为您检索到Q12-Q16的经验数据。以下是各题位的考察模式草案："

V2 Service 做了什么:
  1. 收到 response_text + files_written=["compose/interact_draft.md"]
  2. has_draft=true → 读取 compose/interact_draft.md
  3. 调用 parse_draft_md() 解析为 DraftData JSON
  4. 返回 {has_draft: true, session_state: "reviewing"}

前端收到:
  response_text = "好的，我已为您检索到..."
  has_draft = true
  → 自动调用 GET /draft 获取结构化草案数据
  → 渲染为卡片列表

─────────────────────────────────────────────────────────────
草案内容 (interact_draft.md):

## Q12（选择题·2分）
[ ] CPU性能指标 — 计算型：给定主频/CPI计算MIPS
[ ] CPU性能指标 — 概念辨析：判断性能指标描述正误
[ ] 浮点数表示 — 计算型：IEEE754编码转换

## Q13（选择题·2分）
[ ] 指令系统 — 概念辨析：RISC/CISC特征对比
[ ] 指令系统 — 计算型：指令格式字段划分

...

─────────────────────────────────────────────────────────────
教师操作（前端）:
  - 查看每个题位的选项卡片
  - 点击 ✕ 删除不想要的考察模式
  - 每个题位只保留 1 个选项
  - 可选：在批注框输入要求
  - 点击 "确认提交"

─────────────────────────────────────────────────────────────
Turn 2: 教师标注后
─────────────────────────────────────────────────────────────
前端发送:
  1. POST /annotate {draft_id, slots: [{kept_options, removed_options, annotation}]}
  2. POST /turn {message: "已标注，请生成交接文档"}

V2 Service 做了什么:
  1. validate session_id (hex 格式)
  2. validate draft_id (匹配当前草案)
  3. render_annotated_md() 将标注转回 markdown
  4. 写入 compose/interact_draft.md（覆盖原草案）
  5. 调度 run_conversation_turn("已标注，请生成交接文档")

Agent 做了什么:
  1. read_file 读取裁剪后的 interact_draft.md
  2. 按标注解读规则提取选择：残留选项 = 教师选择
  3. 对每个 slot 调用 exec_python resolve_k_radar() 获取 K-radar
  4. 生成 paper_request.yaml（每个slot含k_radar + k_dominant + k_source）
  5. write_file 写入 paper_request.yaml

V2 Service:
  1. has_result=true → _find_result_path() 找到 YAML
  2. 返回 {has_result: true, session_state: "confirmed"}

前端收到:
  has_result = true
  → 调用 GET /result 获取解析后的 YAML
  → 渲染结果预览（题位摘要 + K-radar 柱状图）
```

### 4.2 场景 B：知识点出题

**触发条件**：教师说 "出一道AVL树旋转题" / "考Cache映射"

```
Turn 1: 教师: "出一道AVL树旋转的选择题"

Scheduler:
  1. 检测到 "AVL树" → 场景 B
  2. Agent 调用 grep_search ["AVL", "平衡二叉树", "旋转"] subject="数据结构"
  3. Agent 归纳检索结果中的考察模式
  4. Agent 调用 exec_python aggregate_question_k_radar(matched_files) 获取 K-radar
  5. Agent write_file 写入草案

Turn 2: 教师裁剪 + 确认 → Agent 生成 slot_blueprint.yaml
```

### 4.3 场景 C：自由组卷（无经验卡，两轮迭代）

**触发条件**：教师说 "出一套数据结构期末卷"，系统无对应经验卡。

```
═══ Round 1：知识点选择（粗筛）═══

Turn 1: 教师: "出一套数据结构期末卷，5道选择题"

Scheduler:
  1. 检测到 "数据结构" 但无经验卡 → 场景 C
  2. Agent 不加载 KG、不检索题库（纯内部知识）
  3. Agent 基于自身知识为 Q1-Q5 分配知识点候选
  4. 每个题位只列知识点，不展开考察模式：

  ## Q1（选择题·2分）
  [ ] 栈与队列 — 操作序列/应用场景
  [ ] 二叉树遍历 — 前中后序/层序
  [ ] 线性表 — 顺序表/链表操作

  5. write_file 写入 Round 1 草案

Turn 2: 教师为每个题位选一个知识点

═══ Round 2：考察模式展开（细筛）═══

Turn 3: 前端发送: /annotate Round1 + /turn "已选择知识点"

Scheduler:
  1. Agent 读取教师选择的知识点
  2. 对每个选中的知识点调用 grep_search 检索题库
  3. 基于检索结果归纳考察模式：

  ## Q1 栈与队列 — 考察模式
  [ ] 栈的操作序列合法性判断（需多步推演）
  [ ] 队列的应用场景辨析（概念辨析）
  [ ] 双端队列的操作特性（概念辨析）

  4. write_file 更新草案（Round 2）
  5. current_round 字段变为 2

Turn 4: 教师为每个题位选一个考察模式

Turn 5: /annotate Round2 + /turn "已标注"
→ Agent 生成 paper_request.yaml
```

---

## 5. 数据在各层间的流转

### 5.1 草案数据的生命周期

```
Agent 生成 markdown
    │
    ▼
interact_draft.md (在 scheduler workspace 内)
    │
    ▼ V2 Service 读取文件
parse_draft_md()
    │
    ▼
DraftData JSON (内存 + GET /draft 返回给前端)
    │
    ▼ 教师裁剪后
AnnotationSubmission JSON (前端 POST /annotate)
    │
    ▼ V2 Service 转换
render_annotated_md()
    │
    ▼
interact_draft.md (覆写为裁剪后版本)
    │
    ▼ Scheduler 下一轮
Agent read_file 读取裁剪后的草案
    │
    ▼
Agent 生成 paper_request.yaml / slot_blueprint.yaml
```

### 5.2 K-radar 数据的获取链路

```
Agent 需要为某个 slot 获取 K-radar
    │
    ▼
exec_python 调用
    │
    ├─ 有经验卡 → read_slot_k_radar("Q14")
    │              → 读取 data/slot_experiences/Q14_experience.md
    │              → 解析 "K1: 众数=3" 格式
    │              → 返回 {K1:3, K2:3, K3:2, K4:4, K5:1}
    │              → k_source = "experience_card"
    │
    ├─ 有 grep 结果 → aggregate_question_k_radar(files)
    │                  → 读取多道题的经验文件
    │                  → 取平均四舍五入
    │                  → k_source = "question_aggregate"
    │
    └─ 无数据 → resolve_k_radar(examination_mode="计算型")
                 → 关键词启发式估算
                 → k_source = "heuristic"
    │
    ▼
写入交接 YAML:
  k_radar: {K1:3, K2:3, K3:2, K4:4, K5:1}
  k_dominant: "K4"
  k_source: "experience_card"
  difficulty_rationale: "..."
```

### 5.3 标注回写路径

```
前端提交 AnnotationSubmission
    │
    ▼
V2 Service.submit_annotation()
    │
    ├── validate_session_id()        # 防 ../../path
    ├── validate draft_id 匹配       # 防旧草案覆盖
    ├── render_annotated_md()        # JSON → markdown
    │       │
    │       ├── 保留 kept_options 的选项文本
    │       ├── 应用 modified_text（教师修改）
    │       ├── 保留 cognitive_desc（去重处理）
    │       └── 添加 > 教师批注: ...
    │
    └── write_file 到 scheduler workspace
        path: {workspace}/{session_id}/compose/interact_draft.md
    │
    ▼
Scheduler 下一轮 run_conversation_turn()
    Agent 调用 read_file("compose/interact_draft.md")
    Agent 按裁剪规则解读：
      - 残留选项 = 教师选择
      - 被删除的 = 教师排除
      - 批注 = 附加要求
    Agent 生成交接 YAML
```

---

## 6. Agent 工具调用详解

Agent 通过 scheduler 的工具循环执行操作。每轮对话可调用最多 15 次工具。

### 6.1 read_file — 读取数据

| 读取目标 | 路径 | 何时调用 |
|---------|------|---------|
| 经验卡 | `data/slot_experiences/Q{N}_experience.md` | 场景 A，获取考察模式统计和 K 值 |
| 题目经验 | `data/question_experiences/{id}.md` | 场景 B/C，获取具体题目数据 |
| 教师标注后的草案 | `compose/interact_draft.md` | 标注确认后，读取裁剪结果 |

**去重机制**：已读过的文件不会重复返回完整内容。写文件后缓存自动失效。

### 6.2 grep_search — 检索题库

搜索 `data/question_experiences/` 中的结构化索引。

```
输入: {query: ["AVL", "平衡二叉树"], max_results: 20, subject: "数据结构"}
输出: [{file: "2009_Q5.md", score: 15.0, matched_tags: ["平衡二叉树", "旋转"]}]
```

**关键规则**：多个关键词用数组一次搜索，不要逐个调用。

### 6.3 exec_python — 数据处理

| 函数 | 用途 |
|------|------|
| `read_slot_k_radar("Q14")` | 从经验卡读 5 维 K-radar |
| `aggregate_question_k_radar(files)` | 从多题聚合 K-radar |
| `resolve_k_radar(slot_id, ...)` | 统一入口，自动 fallback |
| `compute_k_dominant(k_radar)` | 计算主导维度 |
| `extract_slot_recommendation(card)` | 从经验卡提取推荐模式 |

### 6.4 write_file — 输出文档

| 阶段 | 文件 | 格式 |
|------|------|------|
| collecting → reviewing | `compose/interact_draft.md` | 带标记位的 markdown |
| confirmed | `paper_request.yaml` 或 `slot_blueprint.yaml` | YAML |

**硬规则**：reviewing 阶段不得写入任何 .yaml 交接文档。

---

## 7. 错误处理与边界情况

### 7.1 Session 不存在

```
前端 → POST /turn {session_id: "invalid"}
V2 Service → validate_session_id() → ValueError
HTTP → 400 "Invalid session ID format"
```

### 7.2 Draft ID 不匹配（教师用了旧草案）

```
前端 → POST /annotate {draft_id: "old_id"}
V2 Service → draft_id != current_draft.draft_id → ValueError
HTTP → 400 "Draft ID mismatch: got 'old_id', expected 'current_id'"
```

### 7.3 Agent 工具轮次耗尽（15轮）

Scheduler 自动终止工具循环，返回已收集的信息。V2 Service 正常返回 response_text。

### 7.4 Agent 输出无法解析为草案

Draft parser 解析失败 → `raw_md` 回退，前端降级为纯 markdown 渲染。

### 7.5 模型不可用

DocScheduler 构造时 `get_gateway(provider)` 失败 → 500 错误，前端显示错误提示。

---

## 8. 下游衔接

交接文档（paper_request.yaml / slot_blueprint.yaml）生成后的流程：

```
interact confirmed
    │
    ▼
paper_request.yaml (或 slot_blueprint.yaml)
    │
    ▼
compose_runner.run_compose()
    │ 读取 slot 配置 + 经验卡
    │ 为每个 slot 生成组装文档
    ▼
assemble_slot_experience_doc()
    │ 组装：经验卡 + K-radar + 往年题 + 考察模式
    ▼
generate_runner.run_generate()
    │ 调用 LLM 为每个 slot 生成正式题目
    ▼
最终题目 (final_content)
```

**Interact 的终点就是下游的起点**。Interact 只负责需求收集和文档交接，不参与出题本身。
