# Interact V2 架构设计文档

> 版本: 2.0 | 日期: 2026-06-11
> 状态: **已实现** — 两层澄清 + 服务拆分 + 持久化
> 前置文档: `2026-06-10-interact-web-api-design.md`（V1 spec，部分已过时）

---

## 1. 核心设计原则

### 1.1 两条路线 + 两层澄清

系统不是先设计前端，也不是先设计后端，而是先把"用户模糊出题需求"澄清成一个可批注、可逐层收敛的需求过程。

**两条路线**：

| 路线 | 候选来源 | 场景 |
|------|---------|------|
| 固定 408 出题 | 历年经验、题位结构、408 知识图谱 | Scenario A |
| 自由形式出题 | 用户输入、检索结果、大模型内部经验 | Scenario B（单知识点）/ C（组卷） |

**两层澄清**（所有路线统一）：

```
第一层：确定每道题考哪个"粗知识点"
  ↓
第二层：确定这个知识点"考察什么"（具体考察方式）
  ↓
最终：生成固定格式的组装文档（paper_request.yaml / slot_blueprint.yaml）
```

### 1.2 交互层定位

> **交互层不是出题层，也不是大纲生成层。**
> 交互层的唯一职责：把模糊需求通过两层澄清转化为后端可消费的最小需求文档。

- 大纲生成 → 专门工具（`generate_knowledge_draft()`、经验卡解析）
- 交互层 → 调工具获取方案 → 检索补充 → 呈现给教师 → 读取标注 → 生成交接文档

---

## 2. 系统架构

### 2.1 服务拆分

```
api/services/
├── interact_v2_service.py          # 门面（~800行）— 编排入口
├── interact_session_manager.py     # 会话管理（~460行）— CRUD + 消息持久化 + 磁盘恢复
├── interact_clarification.py       # 澄清拦截（~150行）— Scenario C 检测 + GLM outline
├── draft_parser.py                 # 草案解析（~470行）— MD → JSON
├── pipeline_trigger.py             # 流水线触发（~360行）— handoff → DocPipeline
└── display_result_service.py       # 结果展示（~200行）— 题目渲染 + 试卷 Markdown
```

**模块边界**：

| 模块 | 职责 | 不做 |
|------|------|------|
| `InteractV2Service` | 编排 send_turn、draft/annotation 管理、pipeline 触发 | 不直接操作 session dict |
| `SessionManager` | 会话 CRUD、消息持久化、磁盘恢复、pending_clarification 持久化 | 不调用 agent |
| `ClarificationHandler` | Scenario C 正则检测、需求合并、GLM outline 预生成 | 不管理会话状态 |
| `DraftParser` | MD → DraftData JSON、PHASE/ROUND/SCENARIO 标记解析 | 不与 agent 交互 |

### 2.2 核心交互循环

```
前端                    V2 Service (门面)        子模块                Scheduler/Agent
  │                        │                       │                       │
  │ POST /turn             │                       │                       │
  │───────────────────────►│                       │                       │
  │                        │─── ClarificationHandler: Scenario C 检测      │
  │                        │    ├─ 需要澄清? → 追问（不进 agent）           │
  │                        │    └─ 有结构? → _pregenerate_outline()         │
  │                        │                       │                       │
  │                        │─── SessionManager: 消息记录                     │
  │                        │                       │                       │
  │                        │─── 修订守卫: 批注 → quarantine yaml            │
  │                        │                       │                       │
  │                        │──────────────────────────────────────────────►│
  │                        │         run_conversation_turn()               │
  │                        │                       │    工具循环:           │
  │                        │                       │    read_file           │
  │                        │                       │    grep_search         │
  │                        │                       │    write_file          │
  │                        │◄──────────────────────────────────────────────│
  │                        │                       │                       │
  │                        │─── DraftParser: 解析草案 MD                     │
  │                        │─── SessionManager: 更新状态                     │
  │                        │─── PipelineTrigger: auto-trigger（如 confirmed）│
  │                        │                       │                       │
  │ ◄──────────────────────│                       │                       │
  │ {response, has_draft,  }│                      │                       │
  │ {has_result, state}    │                       │                       │
```

---

## 3. 会话状态机

```
                    教师首次发消息
                         │
                         ▼
                 ┌─────────────┐
                 │  collecting  │◄──────────────────────────┐
                 │  收集需求    │                            │
                 └──────┬──────┘                            │
                        │                                   │
            ┌───────────┴───────────┐                      │
            │                       │                      │
     Scenario C 澄清拦截      其他场景直进 agent             │
     (后端正则检测)           (A/B/C 直接生成草案)
            │                       │                      │
            ▼                       ▼                      │
     追问题量/题型结构       has_draft=true                  │
     (不进 agent)                  │                      │
            │                       ▼                      │
     教师补充结构           ┌─────────────┐                │
            │               │  reviewing   │                │
            └──────────────►│  审阅草案    │                │
                            └──────┬──────┘                │
                                   │                       │
                          ┌────────┴────────┐             │
                          │                 │             │
                   教师批注修订        教师选择确认          │
                   (有 annotation)    (无批注)              │
                          │                 │             │
                          ▼                 ▼             │
                   修订草案              has_result=true   │
                   (quarantine yaml)        │              │
                          │                 ▼              │
                          │          ┌─────────────┐      │
                          │          │  confirmed   │      │
                          │          │  触发出题    │      │
                          │          └─────────────┘      │
                          │                               │
                          └───────────────────────────────┘
```

**状态判定规则**：

| 条件 | 状态转换 |
|------|---------|
| `has_result=true` | → `confirmed` + auto-trigger pipeline |
| `has_draft=true` 且当前是 `collecting` | → `reviewing` |
| 教师批注提交 | 保持 `reviewing` + quarantine 旧 yaml |
| Agent 回复中无草案也无结果 | 保持 `collecting` |

---

## 4. 三个场景的完整流程

### 4.1 场景 A：408/考研组卷（有经验卡）

**一轮完成**，选项粒度 = 考察模式 × 具体考点。

```
教师: "出一套408计算机组成原理模拟卷"
  ↓
Turn 1:
  Agent: read_file 加载 Q12-Q16 经验卡
  Agent: exec_python read_slot_k_radar() 获取 K-radar
  Agent: LLM 整理 → write_file 草案

  草案格式 ([PHASE: combined]):
  ## Q1（选择题·2分）考察方向
  [ ] 计算型 · CPU执行时间公式计算（参考7题）
  [ ] 计算型 · 性能指标单位换算（参考5题）
  [ ] 概念辨析型 · 冯诺依曼特征辨析（参考2题）

  ↓
Turn 2: 教师选择 → Agent 生成 paper_request.yaml
  - examination_mode: "计算型——公式应用与单位换算"
  - examination_focus: "CPU执行时间公式计算"
  - reference_questions: [...]
  - k_radar: {...}
```

**关键**：题型由 `slot_templates.json` 固定，草案不含题型选择。

### 4.2 场景 B：知识点出题

**一轮完成**，含题型选择（唯一需要教师选题型的场景）。

```
教师: "出一道AVL树旋转的选择题"
  ↓
Turn 1:
  Agent: grep_search ["AVL", "平衡二叉树", "旋转"]
  Agent: LLM 归纳考察模式 → write_file 草案

  草案格式 ([PHASE: combined]):
  ## Q1 考察方向
  [ ] AVL单旋转 · 失衡判断与旋转方向（检索到5道相关题）
  [ ] AVL双旋转 · LR/RL型操作序列（检索到3道相关题）
  ## Q1 题型
  [ ] 选择题
  [ ] 综合应用题

  ↓
Turn 2: 教师选择 → Agent 生成 slot_blueprint.yaml
```

### 4.3 场景 C：自由组卷（先澄清 + 两轮草案）

**后端先拦截追问**，然后 **GLM 预生成大纲**，最后 **两轮草案**。

```
教师: "我想出关于数据结构的期末考卷"
  ↓
═══ 后端拦截（不进 agent）═══
  ClarificationHandler._needs_scenario_c_clarification() → True
  返回追问题量/题型结构
  写入 pending_clarification.json

教师: "12题，5选择、3填空、2简答、2算法，总分100"
  ↓
═══ GLM 预生成大纲 ═══
  _has_scenario_c_structure() → True
  _pregenerate_outline() → 调用 GLM-5.1 + KG
  注入大纲到 agent 上下文
  清除 pending_clarification.json

═══ Round 1: 粗知识域 + 题型 ([PHASE: knowledge]) ═══

Turn N: Agent 生成第一轮草案
  ## Q1 考察范围
  [ ] 线性表 — 顺序表/链表基本操作
  [ ] 栈和队列 — 受限线性结构应用
  [ ] 树和二叉树 — 结构性质与遍历
  ## Q1 题型
  [ ] 选择题
  [ ] 填空题

Turn N+1: 教师选择粗知识域 + 确认题型

═══ Round 2: 考察方式细化 ([PHASE: examination]) ═══

Turn N+2: Agent 对选中知识域 grep_search → 归纳考察方式
  ## Q1（选择题）考察方式
  [ ] 二叉树遍历 · 递归序列推导（检索到12道相关题）
  [ ] 二叉树遍历 · 非递归算法分析（检索到8道相关题）

Turn N+3: 教师选择 → Agent 生成 paper_request.yaml
```

---

## 5. 草案阶段模型

### 5.1 文件头标记

每个草案文件必须在开头包含标记行：

```markdown
[SCENARIO: C]
[ROUND: 1]
[PHASE: knowledge]
```

| 标记 | 含义 |
|------|------|
| `[SCENARIO: A/B/C]` | 场景标识 |
| `[ROUND: 1/2]` | 当前轮次（场景 C 两轮） |
| `[PHASE: knowledge]` | 第一层：选粗知识域 |
| `[PHASE: examination]` | 第二层：选具体考察方式 |
| `[PHASE: combined]` | 合并：知识点×考察方式一次选完 |
| `[PHASE: question_type]` | 题型选择（与 knowledge 同轮） |

### 5.2 DraftSlot.phase 字段

```python
class DraftSlot(BaseModel):
    slot_id: str          # "Q1" 或 "Q1_type"（题型 section）
    display_id: str       # "1" 或 "1 · 题型"
    title: str
    phase: Literal["knowledge", "examination", "combined", "question_type"]
    options: list[DraftOption]
    annotation: str = ""
```

前端根据 `phase` 差异化渲染：
- `knowledge` / `combined` → 标准选项卡片
- `examination` → 细化选项（第二轮）
- `question_type` → 题型选择卡片

---

## 6. 持久化与恢复

### 6.1 会话消息持久化

```
SessionManager._append_session_message()
  → workspace/{session_id}/compose/session_messages.json
  → 格式: [{role, content, created_at}, ...]
```

### 6.2 pending_clarification 持久化

```
设置时: _persist_pending_clarification()
  → workspace/{session_id}/compose/pending_clarification.json
  → 格式: {"kind": "scenario_c_structure", "requirements": "..."}

恢复时: _restore_sessions_from_disk()
  → 读取 pending_clarification.json
  → 恢复 session["pending_clarification"]

清除时: clarification 完成
  → 删除 pending_clarification.json
```

### 6.3 磁盘恢复策略

服务重启时，`SessionManager._restore_sessions_from_disk()` 扫描 workspace 目录：

| workspace 文件状态 | 恢复的 session state |
|------------------|---------------------|
| `questions/` 存在 | `completed` |
| `paper_request.yaml` / `slot_blueprint.yaml` 存在 | `confirmed` |
| `interact_draft.md` 存在 | `reviewing` |
| `pending_clarification.json` 存在 | `collecting` + 恢复 pending |
| 其他 | `collecting` |

---

## 7. 批注修订守卫

### 7.1 问题

教师提交批注时，如果前端误发"生成交接文档"，可能导致教师还没满意就开始出题。

### 7.2 解决方案：三层防护

**第一层：前端按钮变化**
- 草案有批注 → 按钮变为"提交批注 · 调整草案"
- 提交后只请求修订草案，不进入出题

**第二层：后端 quarantine**
```python
_annotation_requests_revision() → True
  → _quarantine_result_files()
  → paper_request.yaml → paper_request.yaml.blocked.annotation-revision.{timestamp}
```

**第三层：消息包装**
```python
_build_revision_turn_message()
  → 包装教师消息，附加系统约束：
  "本轮唯一允许的产物是修订后的 compose/interact_draft.md"
  "禁止生成 paper_request.yaml、slot_blueprint.yaml"
```

---

## 8. API 端点完整列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v2/interact/sessions` | 创建会话（thinking=True 默认） |
| `GET` | `/api/v2/interact/sessions` | 列出所有会话 |
| `GET` | `/api/v2/interact/sessions/{id}` | 获取会话信息 |
| `DELETE` | `/api/v2/interact/sessions/{id}` | 删除会话 + 工作区 |
| `POST` | `/api/v2/interact/sessions/{id}/turn` | 发送教师消息 |
| `GET` | `/api/v2/interact/sessions/{id}/draft` | 获取结构化草案 |
| `POST` | `/api/v2/interact/sessions/{id}/annotate` | 提交标注 |
| `GET` | `/api/v2/interact/sessions/{id}/result` | 获取交接 YAML |
| `GET` | `/api/v2/interact/sessions/{id}/display-result` | 获取教师端题目结果 |
| `GET` | `/api/v2/interact/sessions/{id}/pipeline-progress` | 获取出题进度 |
| `GET` | `/api/v2/interact/sessions/{id}/paper.md` | 下载试卷 Markdown |
| `GET` | `/api/v2/interact/sessions/{id}/history` | 获取聊天历史 |
| `POST` | `/api/v2/interact/sessions/{id}/questions/{slot_id}/annotation` | 单题批注 |

---

## 9. 数据模型（已更新）

### 9.1 关键变更

| 模型 | 新增字段 | 说明 |
|------|---------|------|
| `DraftSlot` | `display_id: str` | 教师端显示编号 |
| `DraftSlot` | `phase: Literal[...]` | 草案阶段标识 |
| `DraftOption` | `status: "selected"` | 新增 selected 状态 |
| `SlotAnnotation` | `selected_option_id: Optional[str]` | 前端单选偏好 |
| `InteractSessionCreate` | `thinking: bool = True` | 默认开启思考模式 |
| `InteractSessionCreate` | `user_id: str` | 测试者命名空间 |
| `InteractSessionInfo` | `thinking`, `user_id`, `title` | 新增元数据 |

### 9.2 新增模型

- `DisplayQuestion` — 单题展示（含 stem/options/answer/explanation）
- `DisplayResult` — 聚合结果（含 paper_markdown）
- `QuestionAnnotationRequest/Response` — 单题批注

---

## 10. 设计哲学：从"规则拦截"到"模型驱动收敛"

### 10.1 GPT 核心意见

> **既然配置了前端模型，可以利用多轮追问逐步缩小信息。**
> 各种强约束不如先让模型引导多问询几轮，再检索再问询，再优化。
> 即最开始的一两轮特别粗的，可以直接让模型给予自己的参数知识来做；
> 后面到粒度比较细的时候再让工具来做。
> **让模型判断什么时候调取工具获取信息。**

### 10.2 当前实现 vs 理想方向

| 维度 | 当前实现 | 理想方向 |
|------|---------|---------|
| 澄清方式 | 后端正则拦截，硬编码追问话术 | 模型自主判断信息是否充分，自然追问 |
| 工具调用时机 | SKILL.md 固定步骤（Step 1→2→3...） | 模型自行决定何时 grep_search、何时 read KG |
| 候选来源 | 第一轮就调工具检索 | 粗粒度阶段用模型参数知识，细粒度阶段才调工具 |
| 信息收集粒度 | 每轮缩小多个维度（知识点+题型+难度） | **每轮只缩小一个维度** |
| 默认值处理 | 系统默认值直接写入 | 默认值作为**推荐**展示，必须让用户确认 |

### 10.3 多轮候选收敛模型

```
用户: "我想出数据结构期末卷"

═══ Round 1: 范围收敛（模型参数知识，不调工具）═══
Agent: "数据结构期末卷通常覆盖：线性表、栈队列、树、图、查找、排序。
        你想全覆盖，还是重点考某几块？"
用户: "重点考树、图、排序"

═══ Round 2: 题型结构收敛（模型参数知识）═══
Agent: "更偏常规期末卷、考研风格，还是算法实践风格？
        常规期末卷通常 8-12 题，选择+填空+简答+算法混合。"
用户: "常规期末卷，10题"

═══ Round 3: 具体考法收敛（调工具检索）═══
Agent: grep_search(["二叉树遍历", "图的DFS", "排序算法"], max_results=30)
Agent: 归纳候选考法
Agent: "树可以考：遍历序列推导、哈夫曼编码、AVL 旋转；
        图可以考：DFS/BFS 序列、最短路径、最小生成树；
        排序可以考：复杂度比较、快排过程模拟、堆排序建堆。
        按推荐方案（每类各出 2-3 题）？还是你有偏好？"
用户: "按推荐"

═══ Round 4: 生成草案让用户批注（调工具）═══
Agent: write_file 草案 → 教师批注 → 交付出题团队
```

**关键原则**：
1. **粗粒度用模型知识**：第一二轮不调工具，直接用模型参数知识
2. **细粒度用工具检索**：第三轮开始 grep_search / read KG
3. **模型自主决策**：不硬编码"Step N 必须调 grep_search"，让模型判断
4. **每轮只缩小一个维度**：范围 → 题型 → 考法 → 草案

### 10.4 什么时候可以进入出题团队

每个题位至少具备三个要素后才能 handoff：

```yaml
Q1:
  question_type: 选择题        # 要素 1: 题型
  knowledge: 二叉树遍历         # 要素 2: 知识范围
  examination_focus: 遍历序列推导  # 要素 3: 考察方式
```

如果只有 `knowledge: 树`（范围太粗），还不能进入出题。

### 10.5 Handoff 附加决策轨迹

最终交接文档不只是结论，还记录简单决策轨迹：

```yaml
decision_trace:
  - round: 1
    ask_about: "知识范围"
    system_candidates: ["全覆盖", "树图排序重点", "算法重点"]
    user_selected: "树图排序重点"

  - round: 2
    ask_about: "题型风格"
    system_candidates: ["常规期末卷", "考研风格", "算法实践"]
    user_selected: "常规期末卷"

  - round: 3
    ask_about: "具体考法"
    system_candidates:
      树: ["遍历", "哈夫曼", "AVL"]
      图: ["DFS/BFS", "最短路径", "最小生成树"]
    user_selected: "按推荐"
```

### 10.6 对当前架构的改造方向

**短期（不改代码）**：
- 更新 SKILL.md 的沟通策略：明确"粗粒度用模型知识，细粒度用工具检索"
- 放宽 `interact.md` 中的固定步骤约束，允许模型自主决定工具调用时机
- 移除后端 `_scenario_c_clarification` 的硬编码追问，改为让 agent 自己追问

**中期（代码调整）**：
- 后端拦截从"正则检测+硬编码话术"改为"agent 返回 `needs_info` 标记"
- 在 `interact_status.yaml` 中增加 `next_question` 和 `confirmed/rejected` 记录
- `decision_trace` 字段加入 paper_request.yaml

**长期（架构升级）**：
- 引入对话状态追踪：记录 confirmed / rejected / current_candidates / next_question
- 模型自主编排工具调用：不依赖 SKILL.md 的固定步骤
- 前端支持多轮自然对话 UI（不限于"草案卡片"一种交互模式）

---

## 11. 与 GPT 协作讨论的关键问题

以下问题尚待决策，供与 GPT 讨论时参考：

### 10.1 信息收集流程优化

1. **知识点歧义处理**：用户说"考Cache"，交互层如何区分映射方式/替换算法/一致性？
2. **grep_search query 构造策略**：交互层构造 query 时应该包含哪些维度？（知识点、题型、难度、考察方式）
3. **考察方式引导**：当 grep 结果不足时，LLM 补充的考察方式质量如何保证？

### 10.2 两层澄清的粒度

4. **粗知识点粒度**："树"算不算粗知识点？还是必须到"AVL树"？
5. **保守 vs 宽松**：是否允许只完成第一层就进入出题（让下游选考察方式）？

### 10.3 跨场景一致性

6. **paper_request.yaml 与 slot_blueprint.yaml 的字段统一**：examination_focus / reference_questions 是否应该出现在两个格式中？
7. **K-radar 获取策略**：场景 B/C 的 K-radar 聚合质量是否可靠？

### 10.4 前端交互

8. **两轮草案的 UI 衔接**：第一轮选完后，第二轮草案如何无缝展示？
9. **批注修订的反馈**：教师提交批注后，修订进度如何呈现？

---

## 12. 关键配置

| 配置 | 当前值 | 说明 |
|------|--------|------|
| `max_tool_rounds` | 35 | Agent 单轮工具调用上限 |
| `PIPELINE_SLOT_CONCURRENCY` | 2 | 并发出题数 |
| `PIPELINE_JOB_TTL_SECONDS` | 3600 | 进度缓存 TTL |
| thinking mode | `True`（默认） | 本地 vLLM 开启思考 |
| provider | `api_vllm`（interact）/ `glm5.1`（pipeline） | 路由策略 |
