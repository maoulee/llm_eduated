# 交互智能体 Spec：信息收集 + 需求交接 + 设计分离

> 日期: 2026-06-09
> 状态: Phase 1 已实现（commit 806cf84）
> 前置: compose 三路线已实现（可复用为工具层）
> 实现: interact agent + knowledge_index + grep_search_tool + scheduler 集成

## 1. 核心问题

### 1.1 当前架构的问题

当前 compose 层用 Python 硬编码了三条路线（topic_search.py, free_compose.py, compose_runner.py 的 determine_route），本质是在用代码模拟智能体该做的事。

但 **GLM-5.1 就是运行 Claude Code 的模型** — 我们在本次对话中已经调用了 266+ 次工具，证明 GLM-5.1 完全具备工具调用和编排能力。

### 1.2 目标

将交互层从"Python 硬编码路线"转变为"Claude Code 式的智能体环境"：
- 智能体通过 skill 获得流程知识
- 智能体通过工具执行具体操作
- 智能体自己决策该做什么（读文件、grep、呈现信息）
- 教师通过聊天界面交互

## 2. 边界定义

### 2.1 三层文档模型

```
第一层：信息收集文档（给老师看/改）
  ↓ 老师确认
第二层：需求交接文档（给后端读）
  ↓ 后端处理
第三层：正式蓝图文档（驱动出题流水线）
```

| 层次 | 产物 | 谁生成 | 谁消费 |
|------|------|--------|--------|
| 信息收集 | slot_option_cards.md, topic_mode_options.md, outline_proposal.md | 交互智能体 | 教师 |
| 需求交接 | paper_request.yaml, slot_blueprint.yaml | 交接智能体 | 组卷智能体 |
| 正式蓝图 | outline.md, design_card.md, paper_selection.yaml | 组卷/设计智能体 | 出题流水线 |

### 2.2 智能体边界

#### 交互智能体（面向教师）

```
职责：
- 读教师的消息
- 调工具找信息（grep、KG、经验卡）
- 生成可编辑的 md 文档（含 √/x 标记位）
- 教师在文档上直接标注，智能体读取标注结果
- 最终调用 write_file 输出 paper_request.yaml / slot_blueprint.yaml

不负责：
- 不生成正式蓝图（outline.md 含 CONTRACT）
- 不写 design_card
- 不替教师做最终决策
```

#### 交接方式

不单独设交接智能体。交互智能体直接输出 yaml（通过 write_file 工具），或者输出带标记的 md 由 Python 抽取为 yaml。

两种路径：
- **路径 A**：智能体 write_file 直接生成 yaml — 简单，但 yaml 格式对教师不友好
- **路径 B**：智能体 write_file 生成 md，教师编辑后 Python extract_from_marked_doc() 抽取为 yaml — 推荐

选择 **路径 B**：md 对教师可读可编辑，Python 处理结构化转换。

#### 组卷/设计智能体（面向流水线）

```
职责：
- 读取需求交接文档
- 生成正式蓝图（outline.md + CONTRACT YAML）
- 或生成 design_card

不负责：
- 不与教师交互
- 不收集需求
```

### 2.3 关键原则

> **交互层是信息收集与人类裁剪层，不是正式组卷设计层。**
> 它可以生成初步材料，但初步材料只用于帮助教师表达需求，不能直接等同于后端蓝图。

## 3. 现有代码资产分析

### 3.1 保留为工具（Python 函数）

| 函数 | 来源 | 用途 |
|------|------|------|
| `search_questions(keywords)` | **knowledge_index.py** | 结构化标签索引搜索（已替代 grep） |
| `grep_question_bank(keywords)` | topic_search.py | 薄包装 → 委托 knowledge_index |
| `load_kg_for_subjects(subjects)` | compose_runner.py | 按需加载 KG |
| `load_experience_for_slots(slot_ids)` | compose_runner.py | 按需加载经验卡 |
| `extract_slot_recommendation(card)` | compose_runner.py | 从经验卡提取推荐 |
| `auto_complete_from_kg(kps, kg)` | free_compose.py | KG 自动补全 |
| `generate_outline_from_cards()` | outline_yaml_generator.py | slot_cards → outline |
| `generate_from_topic_mode()` | outline_yaml_generator.py | topic_mode → outline |
| `KnowledgeRetriever.search()` | knowledge_retriever.py | 知识点检索 |
| `compute_statistics()` | knowledge_retriever.py | K值统计 |

### 3.2 保留为基础设施

| 模块 | 行数 | 保留原因 |
|------|------|---------|
| agent_loader.py | 281 | agent MD + skill MD 加载机制 |
| scheduler.py | ~1800 | 工具注册 + agent 调度 + 流式执行 + 多轮对话 |
| knowledge_index.py | ~286 | 结构化标签反向索引（2058 文件，1772 标签段） |
| grep_search_tool.py | ~92 | 搜索题库工具（OpenAI tool schema 封装） |
| doc_pipeline/orchestrator.py | 658 | 5层出题流水线 |
| session_manager.py | 405 | FSM 会话管理 |
| knowledge_retriever.py | 369 | 纯 Python 知识检索 |
| blueprint_synthesizer.py | 654 | 数据注入 + 组装 |
| artifact_store.py | ~300 | 经验文档组装 |

### 3.3 重构为 skill 知识

| 现有代码 | 变为 |
|---------|------|
| topic_search.py 的 prompt（generate_grep_keywords、classify_by_modes） | skill MD 中的流程知识 |
| free_compose.py 的 prompt（generate_knowledge_draft） | skill MD 中的流程知识 |
| compose_runner.py 的 _OUTLINE_SYSTEM_PROMPT | skill MD 中的格式规范 |
| intent_router.py 的 INTENT_ROUTER_SYSTEM_PROMPT | skill MD 中的意图识别知识 |

### 3.4 删除（智能体自己编排）

| 代码 | 删除原因 |
|------|---------|
| `determine_route()` | 智能体自己判断路线 |
| `compose_route_2()` | 智能体自己编排 grep+分类 |
| `compose_route_3()` | 智能体自己编排 GLM初稿+grep |
| `run_topic_search()` | 智能体自己协调步骤 |
| `run_free_compose()` | 智能体自己协调步骤 |

## 4. 智能体设计

### 4.1 交互智能体 agent MD（已实现）

```yaml
---
name: interact
phase: 0.5
description: "教师交互智能体 — 收集需求、检索信息、呈现选项、教师标注后生成交接文档"
output_file: interact_response.md
required_tools:
  - read_file
  - write_file
  - grep_search
  - exec_python
required_sections:
  - interact_status
  - scenario
  - teacher_annotations
status_values:
  - collecting
  - reviewing
  - confirmed
behavior: artifact_writer
skills:
  - interact_core
---
```

#### agent MD body（已实现，见 `agents/interact.md`）

核心约束：
- 3 状态 FSM：collecting → reviewing → confirmed（LLM 自行判断转换）
- output_policy：collecting/reviewing 阶段禁止写入交接 yaml，仅 confirmed 阶段输出恰好一个交接文档
- 暂停点：生成草案后立即停止等待教师标注
- interact_status.yaml 跟踪会话状态

### 4.2 interact_core skill MD（核心流程知识）

```markdown
# interact_core 技能

## 场景识别与信息收集流程

根据教师输入和系统已有数据，选择不同的信息收集方式：

### 场景 A：408 组卷（有预抽取信息）

教师说："出一套408模拟卷"
系统有：经验卡、KG、题位模板

```
Step 1 [工具调用]: read_file 加载经验卡（仅相关题位）
Step 2 [工具调用]: exec_python 调用 extract_slot_recommendation() 解析经验卡
Step 3 [LLM]: 将经验卡数据渲染为带标记位的 md 文档
Step 4 [暂停]: 教师在文档上标记 √/x、写批注
Step 5 [LLM]: 读取教师标注，生成 paper_request.yaml
```

信息来源：系统预抽取（经验卡 + KG），LLM 只做渲染和归纳。

### 场景 B：知识点出题

教师说："出一道 AVL 树旋转题"
系统有：题库、KG

```
Step 1 [LLM]: 基于知识点名称生成 grep 关键词（简短推理）
Step 2 [工具调用]: grep_search 搜索题库
Step 3 [LLM]: 将检索结果按考察模式分类归纳
Step 4 [工具调用]: write_file 生成带标记位的 md 文档
Step 5 [暂停]: 教师在文档上选择考察模式
Step 6 [LLM]: 读取教师选择，生成 slot_blueprint.yaml
```

信息来源：grep 检索 + LLM 归纳。

### 场景 C：自由组卷（无预信息）

教师说："出一套数据结构期末卷" 或 "出一套组成原理月考"
系统无：经验卡、预抽取信息

```
Step 1 [LLM，不加外部上下文]:
  让一个没有阅读外部文档的 LLM，纯粹基于自身内部知识，
  为每个题位分配大类知识点，并标注每个知识点有哪些考察方式。

  输出格式（md 表格）：
  | 题号 | 题型 | 大类知识点 | 考察方式选项 | 难度 |

  例如：
  | Q1 | 选择题 | 栈与队列 | 栈的操作序列/队列的应用场景/双端队列辨析 | 3 |
  | Q2 | 选择题 | 二叉树遍历 | 前中后序遍历/层序遍历/遍历序列还原 | 3 |

Step 2 [LLM]: 选中每个题位的推荐考察方式
Step 3 [工具调用]: write_file 生成带标记位的 md 文档
Step 4 [暂停]: 教师在文档上标记 √/x、改知识点、加批注
Step 5 [工具调用]: 对教师保留的知识点，grep_search 检索题库
Step 6 [LLM]: 归纳检索结果，更新文档中的考察方式详情
Step 7 [暂停]: 教师确认最终方案
Step 8 [LLM]: 读取确认结果，生成 paper_request.yaml
```

信息来源：LLM 内部知识（初稿）→ 教师筛选 → grep 验证和补充。

**关键点**：场景 C 的 Step 1 不加载 KG、不加载经验卡。
LLM 纯粹基于自身知识出大纲，快且不触发深度思考。
只有教师确认后，才对保留的知识点做精确检索。

## 会话状态（3 个状态，LLM 自行判断）

| 状态 | 含义 | 进入条件 | 离开条件 |
|------|------|---------|---------|
| collecting | 收集教师需求 | 教师首次发消息 | 信息足够生成草案 |
| reviewing | 教师审阅草案 | 草案已生成并展示 | 教师确认提交 |
| confirmed | 需求已确认 | 教师确认 | 触发后端流水线 |

状态转换由 LLM 判断，不硬编码规则。
LLM 根据对话上下文自行决定当前处于什么状态。

## 工具使用指南

### grep_search：搜索题库
- 输入：关键词列表
- 用于：找到相关题目，按考察模式分类
- 示例：grep_search(["AVL", "平衡二叉树", "旋转"])

### read_file：读取系统数据
- KG 文件：data/computer_organization.md
- 经验卡：data/slot_experiences/Q{N}_experience.md
- 题目经验：data/question_experiences/{id}.md

### exec_python：执行数据处理
- KG 补全、经验卡解析、slot 聚合等

### write_file：输出文档
- 信息收集阶段：输出带 [✓]/[✗] 标记位的 md 文档
- 教师确认后：输出 paper_request.yaml 或 slot_blueprint.yaml

## 文档格式（教师可编辑）

### 草案文档（信息收集阶段）

## Q12（选择题·2分）
[✓] 计算型——公式应用与单位换算 (53.8%)
[ ] 概念辨析型——核心定义与本质区分 (23.1%)
[ ] 组合判断型——多维度特征匹配 (23.1%)
适用知识点: CPU执行时间公式、单位换算、性能公式

教师直接在文档上：
- 把 [ ] 改为 [✓] = 选中
- 把 [ ] 改为 [✗] = 排除
- 添加 > 批注行 = 附加说明
- 删除整个题位节 = 移除

### 确认后输出（交接阶段）

智能体读取教师编辑后的文档，调用 Python 抽取函数，
或直接用 write_file 生成 yaml。

## 暂停点

生成草案文档后停止，等待教师在文档上标注。
收到教师确认消息后继续。
```

## 5. 工具注册（已实现）

### 5.1 复用现有工具系统

`doc_pipeline` 的 `scheduler.py` 已有工具注册机制。interact 智能体工具通过 agent MD frontmatter 的 `required_tools` 声明，由 `run_conversation_turn()` 动态注册：

```python
# interact agent MD frontmatter 声明
required_tools: [read_file, write_file, grep_search, exec_python]

# run_conversation_turn() 中动态注册
registry = ToolRegistry()
registry.register(WriteFileTool(workspace=ws))
registry.register(ReadFileTool(workspace=ws))
if "exec_python" in required_tools:
    registry.register(ExecPythonTool(timeout=PYTHON_EXEC_TIMEOUT))
if "grep_search" in required_tools:
    registry.register(GrepSearchTool())
```

### 5.2 grep_search 工具（已实现 → `grep_search_tool.py`）

底层使用 `knowledge_index.py` 的结构化标签索引，不再做全文本 grep：

```python
class GrepSearchTool(Tool):
    """搜索题库工具 — 基于结构化知识点标签索引"""

    async def execute(self, params: dict) -> dict:
        query = params.get("query", "")
        max_results = params.get("max_results", 20)
        subject = params.get("subject")
        hits = search_questions(query, max_results=max_results, subject=subject)
        return {
            "ok": True,
            "count": len(hits),
            "results": [
                {"file": h.file_name, "score": round(h.score, 1),
                 "snippet": h.snippet[:200], "matched_tags": h.matched_tags}
                for h in hits
            ]
        }
```

### 5.3 knowledge_index 模块（新增 → `compose/knowledge_index.py`）

替代全文本 grep 的结构化标签反向索引：

- 预解析 2058 个题目经验文件的元数据（知识点、科目、题型、年份）
- 按知识点标签段建立反向索引（1772 个标签段）
- 评分策略：精确匹配(+10) > 子串匹配(+5) > 标签段匹配(+3) > 文件名(+2)
- 单例模式，`data_dir` 变更时自动重建

### 5.4 scheduler 新增（已实现）

| 新增 | 位置 | 说明 |
|------|------|------|
| `InteractSession` | scheduler.py | 多轮对话会话跟踪 |
| `run_conversation_turn()` | scheduler.py | 单轮对话执行（session 管理 + LLM 调用 + 工具执行） |
| `_trim_context()` | scheduler.py | 上下文压缩（替代已删除的 commit-only 模式） |
| `GrepSearchTool` 注册 | scheduler.py | interact 角色工具注册 |

## 6. 交互界面设计

### 6.1 设计决策

- **不做选项卡**：题目和知识点太多，选项卡反而麻烦
- **做文档编辑器**：教师直接在文档上标记 √/x、编辑内容、写批注
- **双栏布局**：左侧聊天区 + 右侧文档区
- **智能体写 md → 教师直接编辑 md → Python 从 md 抽取 yaml**

### 6.2 界面布局

```
┌─────────────────────────────────────────────┐
│  左侧: 聊天区           │  右侧: 文档编辑区  │
│                          │                    │
│  教师: 出一套组成原理     │  # 试卷大纲草案    │
│                          │                    │
│  智能体: 我检索了题库，   │  ## Q1（选择题）   │
│  生成了初始方案，请查看   │  [✓] CPU性能指标   │
│  右侧文档并标注。        │  [✓] 浮点数表示    │
│                          │  [✗] 指令流水线    │
│  教师: 我把流水线删了，   │  [✓] Cache映射     │
│  加了中断系统            │  > 批注: 中断系统  │
│                          │  > 要考硬件中断    │
│  智能体: 已收到，更新了   │                    │
│  文档，请确认最终方案    │  [保存] [确认提交]  │
│                          │                    │
└─────────────────────────────────────────────┘
```

### 6.3 文档标记规范

教师在文档上直接操作：

```markdown
## Q1（选择题·2分）
[✓] CPU性能指标 — 公式计算 (难度3)
[✓] 浮点数表示 — IEEE754标准 (难度4)
[✗] 指令流水线 — 冲突检测 (难度3)
[✓] Cache映射 — 地址翻译 (难度5)
> 教师批注: Cache映射要考直接映射和组相联的对比

## Q2（选择题·2分）
[✓] 中断系统 — 中断处理流程 (难度3)
> 教师批注: 要考硬件中断和软件中断的区别
```

标记含义：
- `[✓]` = 保留这个知识点/模式
- `[✗]` = 排除这个知识点/模式
- `> 教师批注:` = 教师附加说明

### 6.4 Python 抽取：md → yaml

交接智能体（或 Python 函数）从教师编辑后的 md 中：

1. 识别 `[✓]`/`[✗]` 标记 → 确定 selected/excluded
2. 识别 `> 教师批注:` → 提取 teacher_annotation
3. 解析结构化字段（题号、题型、知识点、难度）
4. 生成 paper_request.yaml 或 slot_blueprint.yaml

```python
def extract_from_marked_doc(edited_md: str) -> dict:
    """从教师标注后的 md 文档抽取结构化需求。"""
    slots = []
    for section in split_by_heading(edited_md):
        selected = extract_marked(section, "✓")
        excluded = extract_marked(section, "✗")
        annotation = extract_annotations(section)
        slots.append({
            "slot_id": extract_slot_id(section),
            "selected_knowledge": selected,
            "excluded_knowledge": excluded,
            "teacher_annotation": annotation,
        })
    return {"slots": slots, ...}
```

### 6.5 交互流程

```
教师发送消息（"出一套计算机组成原理期末卷"）
  ↓
API: POST /api/sessions/{id}/message
  ↓
智能体读消息 → 调工具检索 → write_file 生成草案 md
  ↓
右侧文档区自动刷新显示草案
  ↓
教师直接在文档上标记 √/x、写批注、编辑内容
  ↓
教师点击 [确认提交] 或 发送消息 "确认"
  ↓
Python extract_from_marked_doc() 从编辑后的 md 抽取
  ↓
生成 paper_request.yaml / slot_blueprint.yaml
  ↓
后端组卷智能体读取 yaml → 生成正式蓝图
```

### 6.6 现有前端资产

已存在 Vue.js 前端（可复用/扩展）：
- `frontend/src/components/ChatMessage.vue` — 消息气泡 → 复用
- `frontend/src/components/Composer.vue` — 输入框 → 复用
- `frontend/src/views/SessionView.vue` — 会话视图 → 扩展为双栏
- `frontend/src/components/OutlineEditor.vue` — 蓝图编辑 → 改造为文档编辑器
- `api/routes/interact.py` — 交互 API → 扩展文档提交接口

## 7. 迁移策略

### 7.1 渐进式迁移（不推翻重来）

**Phase 1：验证概念**
- 创建 interact agent MD + interact_core skill MD
- 注册 grep_search、read_file、write_file 工具
- 用 `scheduler.run_agent()` 执行交互智能体
- 与现有 FSM 并行运行，不替换

**Phase 2：替换路线分发**
- 交互智能体自己决定场景（不调用 determine_route）
- Python 工具保留，编排逻辑从 Python 迁移到 agent
- 保留 compose_runner 的机械后处理（outline 解析、artifact 组装）

**Phase 3：替换 FSM**
- SessionManager 的状态管理改为智能体驱动的多轮对话
- intent_router 改为 skill 内的意图识别（不单独调用 LLM）
- 保留前端 API 接口不变

### 7.2 风险控制

- **回退路径**：每个 Phase 保留旧代码作为 fallback
- **性能基准**：对比硬编码路线 vs 智能体路线的延迟
- **质量基准**：对比两种方式的输出质量

## 8. 已做的决策

| 问题 | 决策 | 理由 |
|------|------|------|
| 交接智能体是否独立 | **不独立** — 交互智能体直接输出，或 Python 抽取 | GLM-5.1 能力足够，多一个智能体增加复杂度 |
| FSM 状态数 | **3 个** — collecting / reviewing / confirmed | LLM 自行判断状态转换，不需要 7 个硬编码状态 |
| 前端交互方式 | **文档编辑器 + √/x 标记**，不做选项卡 | 题目太多，选项卡反而麻烦；文档直接标注更高效 |
| yaml 生成方式 | **md → Python 抽取**（路径 B） | md 对教师可读可编辑，Python 处理结构化转换 |

## 9. 待验证的假设

1. ~~**GLM-5.1 在 scheduler 工具循环中的可靠性**~~：对话中证明了能力，但需要在 scheduler 的流式执行环境中测试
2. **上下文窗口管理**：已实现 `_trim_context()` 压缩历史，需在真实多轮对话中验证效果
3. **错误恢复**：智能体调错工具或生成错误信息时，如何恢复
4. **md 标记规范的可解析性**：[✓]/[✗] 标记在教师编辑后是否仍然可靠解析

### Phase 1 验证结果

- knowledge_index 索引 2058 文件，1772 标签段，搜索精度高于全文本 grep
- scheduler `run_conversation_turn()` 集成完成，工具注册和执行链路通过单测
- commit-only 模式已移除，替换为更温和的上下文修剪
- 366 测试通过，0 失败

## 10. 与现有模块的兼容

- `interact/orchestrator.py` — 重构（解耦 FSM 和流水线调用）
- `interact/intent_router.py` — 合并到 skill（智能体自己判断意图）
- `interact/session_manager.py` — 简化为 3 状态
- `interact/blueprint_synthesizer.py` — 保留（数据注入逻辑有价值）
- `interact/knowledge_retriever.py` — 路径已更新（`data/kg/`、`data/config/`）
- `compose/topic_search.py` — `grep_question_bank()` 已改为委托 `knowledge_index.search_questions()`
- `compose/knowledge_index.py` — 新增，结构化标签反向索引
- `compose/free_compose.py` — Python 函数保留为工具，prompt 迁移到 skill
- `compose/compose_runner.py` — 路径已更新，保留机械后处理

### 数据目录重组（已完成）

```
data/
├── kg/                          # 知识图谱（从 data/ 根目录迁入）
│   ├── computer_organization.md
│   ├── data_structure.md
│   ├── operating_system_knowledge.md
│   ├── computer_network.md
│   └── dagang.md
├── config/                      # 配置文件（从 data/ 根目录迁入）
│   ├── slot_templates.json
│   ├── slot_templates_all.json
│   └── type_difficulty_guides.json
├── statistics/                  # 统计文件（从 data/ 根目录迁入）
│   ├── per_question_k_ratings.json
│   ├── slot_observations.json
│   ├── slot_statistics.json
│   ├── tag_normalization_map.json
│   └── knowledge_registry.json
├── question_experiences/        # 2058 个题目经验文件（80+ 已修复）
└── structured_questions/        # 结构化题目 JSON（修复数据源）
```

## 11. 与 Codex 讨论的对照

Codex 提出的核心边界：
> 交互层是信息收集与人类裁剪层，不是正式组卷设计层

本 spec 的对应：
- 信息收集文档 = 第一层（智能体生成 md，教师直接标注）
- 需求交接文档 = 第二层（Python 从标注后的 md 抽取 yaml）
- 正式蓝图文档 = 第三层（组卷智能体生成，流水线消费）

Codex 提出的"两个智能体"：
- 人类交互智能体 → 本 spec 的 interact agent
- 文档交接智能体 → 简化为 Python extract_from_marked_doc()
