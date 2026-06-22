# Interact Agent Web API 设计文档

> 日期: 2026-06-10
> 状态: **已实现并复核** — V2 API、schema/service、draft parser 已落地
> 前置: K-radar 升级 + 端到端验证通过

## 1. 目标

将 interact agent 从 CLI 测试模式升级为 Web 前后端交互模式：
- 教师在聊天界面中说需求（不需要知道文件路径）
- 系统展示可点击的卡片选项（不是编辑 markdown 文件）
- 标注通过**裁剪（删除不想要的）**完成，不是 [✓]/[✗] 标记
- 最终交接文档可在界面预览和下载

## 2. 代码现状分析

### 2.1 两套系统共存

| 系统 | 入口 | FSM 状态 | 用途 |
|------|------|---------|------|
| **V1** (`interact/`) | `InteractiveOrchestrator` → `SessionManager` | 8态: idle→collecting→blueprint_ready→annotating→approved→generating→complete/error | 当前 API 使用 |
| **V2** (`core_new/doc_pipeline/scheduler.py`) | `Scheduler.run_conversation_turn(session_id, teacher_message)` | 3态: collecting→reviewing→confirmed | CLI 测试使用，含工具循环 |

**关键差异**：
- V1 用 LLM 做 intent routing + blueprint synthesis，没有工具循环
- V2 有完整的 `read_file`/`write_file`/`grep_search`/`exec_python` 工具循环，能检索经验卡和题库
- K-radar 数据驱动只在 V2 中实现
- 两轮流程（场景 C）只在 V2 中实现

### 2.2 当前 API 结构

```
api/
├── app.py              # FastAPI 主应用，CORS 已配
├── deps.py             # 单例注入：LLMGateway → InteractiveOrchestrator
├── schemas.py          # SendMessageRequest/Response, SessionInfo 等
├── persistence.py      # SQLite SessionStore（存 V1 SessionData）
├── event_bus.py        # SSE 事件推送
└── routes/
    ├── interact.py     # POST /api/sessions/{id}/message — V1 路由
    ├── session.py      # Session CRUD
    ├── compose.py      # 组卷
    ├── artifacts.py    # 产物
    ├── events.py       # SSE
    └── health.py       # 健康检查
```

### 2.3 V2 Scheduler 关键接口

```python
# core_new/doc_pipeline/scheduler.py
@dataclass
class InteractSession:
    session_id: str
    messages: list[dict]        # 对话历史
    status: str                 # "collecting" | "reviewing" | "confirmed"
    scenario: str               # "A_408_exp" | "B_knowledge_point" | "C_free_compose"
    files_written: list[str]    # 已写文件列表
    read_cache: dict[str, str]  # 文件去重缓存
    turn_count: int
    last_draft_write_turn: int

async def run_conversation_turn(session_id: str, teacher_message: str) -> dict:
    """核心入口 — 一个教师消息 → agent 回复、写入文件列表、状态"""
```

## 3. 实施策略

**Scheduler 低侵入适配**：最新 scheduler 已提供 `InteractSession`、`run_conversation_turn()`、工具循环和上下文裁剪能力；Web API 层不再追加修改 scheduler 行为，只做 HTTP/JSON 适配。API 层负责：
1. 接收前端请求 → 转为 `teacher_message` 字符串
2. 调用 `run_conversation_turn()`
3. 解析 agent 回复中的草案 markdown → 结构化 JSON
4. 接收前端标注 JSON → 写回 `compose/interact_draft.md` → 继续对话

**双模式兼容**：
- `ui_mode="file"` — CLI/测试（当前模式不变）
- `ui_mode="api"` — Web UI（新增）

## 4. API 端点设计

### 4.1 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v2/interact/sessions` | 创建交互会话 |
| `POST` | `/api/v2/interact/sessions/{id}/turn` | 发送教师消息 + 获取回复 |
| `GET` | `/api/v2/interact/sessions/{id}/draft` | 获取结构化草案 JSON |
| `POST` | `/api/v2/interact/sessions/{id}/annotate` | 提交裁剪标注 |
| `GET` | `/api/v2/interact/sessions/{id}/result` | 获取交接 YAML |

> 注意前缀 `/api/v2/` — 与 V1 `/api/` 共存，前端按需切换。

### 4.2 交互流程

```
Frontend                              Backend
   │                                     │
   │  POST /api/v2/interact/sessions     │
   │  {provider: "glm5.1"}              │
   │─────────────────────────────────────►│  → new InteractSession
   │  ← {session_id: "abc"}              │
   │                                     │
   │  POST /api/v2/interact/sessions/abc/turn│
   │  {message: "出一道Cache映射选择题"}   │
   │─────────────────────────────────────►│  → run_conversation_turn()
   │  ← {response_text, has_draft: true} │
   │                                     │
   │  GET /api/v2/interact/sessions/abc/draft│
   │─────────────────────────────────────►│  → parse draft MD → JSON
   │  ← {sections: [{options: [...]}]}   │  ← 渲染为卡片 UI
   │                                     │
   │  POST .../abc/annotate              │
   │  {kept_options: [...],              │
   │   removed_options: [...]}            │
   │─────────────────────────────────────►│  → JSON→MD 回写 draft
   │  ← {ok: true}                       │
   │                                     │
   │  POST .../abc/turn                  │
   │  {message: "已标注，请生成"}          │
   │─────────────────────────────────────►│  → run_conversation_turn()
   │  ← {files_written: [...]}           │
   │                                     │
   │  GET .../abc/result                 │
   │─────────────────────────────────────►│  → 解析 YAML
   │  ← {parsed: {k_radar: {...}}}       │
```

## 5. 数据模型

### 5.1 DraftData（草案结构化）

```python
class DraftOption(BaseModel):
    id: str                    # "opt_1_1"
    text: str                  # 选项文本
    cognitive_desc: str        # "需一步公式推导"（不暴露K值）
    status: str = "unselected" # "unselected" | "kept"

class DraftSlot(BaseModel):
    slot_id: str               # "Q1"
    title: str                 # "Q1（选择题·2分）— 拓扑排序"
    options: list[DraftOption]
    annotation: str = ""       # 教师批注

class DraftData(BaseModel):
    draft_id: str
    title: str                 # "拓扑排序 — 考察模式草案"
    scenario: str              # "A" | "B" | "C"
    current_round: int = 1     # 场景C: 1 或 2
    sections: list[DraftSlot]
    raw_md: str                # 原始 markdown（回退渲染用）
```

### 5.2 裁剪式标注（核心模式）

教师操作方式是**裁剪**：删除不想要的选项卡片，残留的就是选择。

**UI**：
- 每个选项显示为卡片，带 ✕ 按钮
- 教师点 ✕ 移除不想要的
- 保留的卡片就是教师的选择
- 每个题位裁剪到只剩 1 个选项后确认

**API 数据**：

```python
class SlotAnnotation(BaseModel):
    slot_id: str
    kept_options: list[str]     # 保留的 option_id（通常只有 1 个）
    removed_options: list[str]  # 被移除的 option_id
    annotation: str = ""
    modified_text: dict = Field(default_factory=dict)  # {option_id: 修改后的文本}

class AnnotationSubmission(BaseModel):
    draft_id: str
    slots: list[SlotAnnotation]
```

### 5.3 InteractResponse（统一响应）

```python
class InteractTurnResponse(BaseModel):
    response_text: str           # agent 文本回复
    session_state: str           # collecting | reviewing | confirmed
    has_draft: bool              # 是否有可解析的草案
    has_result: bool             # 是否有交接 YAML
    files_written: list[str] = Field(default_factory=list)  # 本轮写入的文件
```

## 6. 文件结构（新增/修改）

```
api/
├── routes/
│   ├── interact.py             # V1 路由（保持不变）
│   └── interact_v2.py          # [NEW] V2 路由 — 调用 scheduler
├── services/
│   └── interact_v2_service.py  # [NEW] 服务层 — session 管理 + draft 解析
├── schemas.py                  # V1 schemas（保持模块文件，避免导入冲突）
├── schemas_interact_v2.py      # [NEW] V2 Pydantic models
├── app.py                      # [MOD] 注册 V2 router
└── deps.py                     # [MOD] 新增 get_scheduler() 依赖

core_new/doc_pipeline/
├── agents/interact.md          # [MOD] 硬编码修复
├── skills/interact_core/SKILL.md  # [MOD] 硬编码修复
└── scheduler.py                # [依赖现有] V2 工具循环入口
```

## 7. 硬编码修复

SKILL.md 和 interact.md 中的硬编码需改为**通用占位格式**，明确标注为格式参考。

### 7.1 SKILL.md 修改清单

| 行号 | 当前硬编码 | 改为 |
|------|-----------|------|
| 26 | `Q12: 计算型54%` | `Q{N}: {考察模式}占比%` |
| 34 | `## Q12（选择题·2分）` | `## Q{N}（{题型}·{分值}分）` |
| 35-38 | `CPU性能指标`/`浮点数表示`/`Cache映射` | `{知识点} — {考察模式}：{描述}` |
| 86-89 | `栈与队列`/`二叉树遍历`/`线性表` | `{知识点} — {知识范围}` |
| 103 | `## Q1 栈与队列` | `## Q{N} {知识点}` |
| 136-144 | grep `"CPU性能","浮点数","Cache映射"` | `"{关键词1}","{关键词2}"` |
| 202-209 | 文档标记示例 CPU/浮点数 | `{知识点} — {考察模式}（{认知特征}）` |
| 213-219 | AVL树旋转文档标记示例 | `{知识点} — {考察模式草案}` |
| 334-339 | paper_request `Cache` 路径 | `{科目} > {章节} > {知识点}` |
| 368-373 | slot_blueprint `AVL树` 路径 | `{科目} > {章节} > {知识点}` |

### 7.2 interact.md 修改清单

| 行号 | 当前硬编码 | 改为 |
|------|-----------|------|
| 130-134 | `Q12` + `CPU性能指标`/`浮点数` | 同上通用格式 |
| 143-147 | `Q1` + `栈与队列`/`二叉树遍历` | 同上 |
| 152-155 | `Q1 栈与队列 — 考察模式` | 同上 |

### 7.3 修改原则

1. 所有示例前加注释：`<!-- 以下仅为格式参考，实际内容由经验卡/检索结果填充 -->`
2. 用 `{占位符}` 替代具体内容，保留结构
3. 不改动流程逻辑描述，只改示例中的具体学科内容
4. YAML 示例中的 `slot_id`/`target_family` 等也用占位符

## 8. 实施路线

### Phase P0（2-3 天）— 最小可用版

| 任务 | 文件 | 工时 |
|------|------|------|
| 硬编码修复 | SKILL.md + interact.md | 0.5 天 |
| Pydantic schemas | `api/schemas_interact_v2.py` | 0.5 天 |
| Draft 解析器 | `api/services/draft_parser.py` | 0.5 天 |
| V2 路由 + 服务层 | `api/routes/interact_v2.py` + `api/services/interact_v2_service.py` | 1.5 天 |

### Phase P1（1 天）

| 任务 | 说明 |
|------|------|
| SSE 事件推送 | 复用 `event_bus.py`，推送 draft_ready / annotated / confirmed 事件 |
| 会话持久化 | 扩展 `persistence.py` 或新建 `interact_v2_store.py` 存 InteractSession |

### Phase P2（2 天）

| 任务 | 说明 |
|------|------|
| Vue 前端原型 | 卡片式 UI + 裁剪交互 + 聊天框 + YAML 预览 |

### 依赖关系

```
硬编码修复 ←── 无依赖（可独立进行）
schemas ←── 无依赖
draft_parser ←── 依赖 schemas
V2 路由+服务 ←── 依赖 schemas + draft_parser
```

## 9. 约束

- API 层不再改 scheduler 语义 — 依赖现有 `run_conversation_turn()` 和工具循环能力
- vLLM 兼容：system message 只在 position 0，draft hint 追加到 messages[0]
- K 值不暴露给教师 — API 响应中的 draft 不含 K1-K5
- 端口 8888 是代理，业务逻辑不使用
