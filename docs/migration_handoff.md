# 项目迁移交接文档

> 分支: `feature/hybrid-solver-annotation`
> 日期: 2026-05-29
> 基础模型: GLM-5.1 (200K input, 128K output)

---

## 1. 项目概述

408考研自动出题系统。输入题位（slot）的考察理念文档，自动生成符合408考研风格的题目（单选 + 综合）。

**当前 Pipeline 流程（综合应用题）：**
```
Architecture → Design → Solve(FileCodeSolver) → Format → Rubric → Review → Final
```

**当前 Pipeline 流程（单选题）：**
```
Architecture → SC Draft → Options → StemVerify → Solve → Format → Review → PostReview → Summary → Assemble
```

---

## 2. 关键架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 输出格式 | **markdown**（非JSON） | GLM-5.1 JSON 输出不稳定，markdown 可靠 |
| 思考控制 | `enable_thinking=False` | 让 GLM-5.1 自主决定思考深度。`True` 会强制深度思考，reasoning_content 消耗大量 token 导致实际输出被截断 |
| 信息获取 | **agent 工具调用**（function calling） | 不在 prompt 中 dump 所有信息，模型通过 `read_slot` 等工具按需自主读取 slot 文件 |
| max_tokens | GENERATOR 16384-32768, 其他 8192 | GLM-5.1 支持 128K output，之前配的 800-4096 太低 |
| 数据流方向 | **计划迁移到 agent 间 messaging** | 当前 Blackboard 全局共享所有状态，不够灵活。目标：agent 间通过 send messages 通信，每个 agent 有内部状态 |

### GLM-5.1 配置要点

- `thinking_control_method = "none"` — 不在 API 请求中加思考参数，模型自己决定
- `temperature = 1.0`, `top_p = 0.95`
- `enable_thinking` 在代码中只影响**响应解析**（`_parse_think_answer`），不影响 API 请求
- 设为 `False` 后，响应解析走简化路径，不做 reasoning 提取

---

## 3. Tool-calling 基础设施（已完成）

### 文件结构

```
core_new/agent_tools.py          — ToolDef, ToolExecutor, SLOT_TOOLS
core_new/llm_gateway.py          — generate_with_tools() 多轮循环
llm_providers_new/remote_api.py  — _chat_call() 支持 tools + tool_calls
core_new/agent_base.py           — AgentConfig.tools, _call_llm_with_tools()
```

### 工作原理

1. Agent 的 `AgentConfig.tools` 列表中注册 ToolDef
2. `BaseAgent._call_llm()` 检测到 `self.config.tools` 非空时，走 `_call_llm_with_tools()`
3. `_call_llm_with_tools()` 创建 ToolExecutor，调用 `gateway.generate_with_tools()`
4. `generate_with_tools()` 运行多轮循环：
   - 发送 messages + tools 给 LLM
   - 如果 LLM 返回 `tool_calls`，执行工具，将结果追加到 conversation，继续循环
   - 如果 LLM 返回纯文本（无 tool_calls），作为最终结果返回
5. 最多 `max_tool_rounds` 轮（ArchitectureAgent 设为 5）

### SLOT_TOOLS（3个内置工具）

```python
SLOT_TOOLS = [
    ToolDef(name="read_slot",   handler=_read_slot_section),  # 读取 slot 文件，支持 section 提取
    ToolDef(name="read_file",   handler=_read_file),          # 读取任意文件
    ToolDef(name="list_files",  handler=_list_directory),     # 列出目录文件
]
```

`read_slot` 支持 `section` 参数，可提取 `## ` 和 `### ` 标题下的内容，如 `考察理念`、`难度维度`、`设计理念`、`往年案例`。

### Slot 文件位置

```
data/slots/Q44_slot.md  — 综合应用题第1题（计算机组成原理，13分）
data/slots/Q43_slot.md  — 综合应用题（计算机组成原理，10分）
data/slots/Q14_slot.md  — 单选题
```

每个 slot 文件包含：`## 基本信息`、`## 考察理念`（含 ### 概念理解/计算要求/过程推演/难度维度）、`## 设计理念`、`## 往年案例`

---

## 4. 已完成的 Agent 改造

### ArchitectureAgent（已完成）

**文件**: `core_new/agents/architecture_agent.py`
**提示语**: `core_new/prompts/architecture_prompts.py`

- 已配置 `tools=SLOT_TOOLS`, `max_tool_rounds=5`
- `build_input()` 只传 slot_id + knowledge_point + blueprint（约 1.3K chars）
- 模型通过 `read_slot` 工具自主读取 考察理念、难度维度、设计理念、往年案例
- 难度设定要求**引用 slot 中的标准定义**，不能只给数字
- `max_tokens=32768`, `enable_thinking=False`

### 全局参数统一

所有 agent 已统一：
- `enable_thinking=False` — 涉及 7 个文件，22 处替换
- `max_tokens` 已归一化：
  - SC Draft, Options: 16384
  - StemVerify, Solution, Review, PostReview, Summary: 8192
  - QuestionDesigner: 32768
  - Hybrid Formatter, Rubric, Reviewer: 8192
  - FileCodeSolver: 16384（默认值 + 3 个调用点）

---

## 5. 待做任务

### 5.1 Socratic 逐个审核 agent 提示语（优先级：高）

ArchitectureAgent 已审核完成。以下 agent 待逐一审核优化：

| Agent | 文件 | 当前状态 |
|-------|------|---------|
| QuestionDesignerAgent | `hybrid_subjective_team.py:54` | 使用 `SUBJECTIVE_DRAFT_ONLY_PROMPT`，输出 markdown |
| OptionAndDistractorAgent | `single_choice_team.py:208` | 单选选项生成 |
| StemVerifierAgent | `single_choice_team.py:303` | 题干验证 |
| SCSolutionFormatterAgent | `single_choice_team.py:392` | 单选解析格式化 |
| SingleChoiceReviewerAgent | `single_choice_team.py:448` | 单选审核 |
| PostReviewAgent | `single_choice_team.py:522` | 最终质量审核 |
| QuestionSummaryAgent | `single_choice_team.py:623` | 题目汇总 |
| HybridSolutionFormatter | `hybrid_subjective_team.py:178` | 综合题解析格式化 |
| HybridRubricWriter | `hybrid_subjective_team.py:234` | 评分标准 |
| IntentBasedReviewer | `hybrid_subjective_team.py:279` | 意图审核 |

审核要点：
- 输出格式是否合理，是否有多余字段
- 是否需要接入工具（如 reviewer 需要读 slot 做对比）
- 提示语是否有冲突指令（之前 system prompt 说 JSON 但 user prompt 说 markdown）
- 必填字段（required_fields）是否与实际输出匹配

### 5.2 Agent 间消息通信（优先级：高）

当前所有 agent 通过 Blackboard 共享状态，每个 agent 读写同一个 dict。问题：
- 信息过载（所有信息都放上去）
- 没有私有的 agent 内部状态
- 不够灵活

目标架构：
```
Architecture --[send message]--> Designer --[send message]--> Solver --> ...
```

每个 agent：
- 有自己的内部状态（memory）
- 通过 messages 接收上游结果
- 不依赖全局 Blackboard

这需要重构 pipeline 的编排方式，可能需要引入 agent runtime 或 message bus。

### 5.3 从刚性 pipeline → 自主 agent team（优先级：中）

用户原话："本质上我们这边其实更像是出题team，而非完全写死的工作流，每个智能体内部应该有自己的自主行为"

目标：agent 不再是固定顺序执行，而是：
- Team lead 分配任务
- Agent 自主决定需要什么信息（通过工具获取）
- Agent 间通过消息协作
- 支持动态调整（如 reviewer 说需要修改，自动路由回对应 agent）

### 5.4 Gate agent 格式统一（优先级：中）

当前 gate agent（gate_agents.py）使用 YAML front matter 格式，需要统一为 markdown 格式。

### 5.5 Comp pipeline 端到端验证（优先级：高）

max_tokens 和 enable_thinking 已修复，需要在实际环境运行验证：
- Architecture 能否通过工具正确读取 slot 并生成设计
- Solver 能否正常生成 Python 代码并执行
- 全流程是否跑通

验证命令参考：
```bash
python run_slot_composition.py
# 或
python test_e2e_choice.py
```

---

## 6. 关键文件索引

```
# 核心框架
core_new/agent_base.py           — BaseAgent, AgentConfig, parse_json_text
core_new/agent_tools.py          — ToolDef, ToolExecutor, SLOT_TOOLS
core_new/agent_roles.py          — RoleType, AuditMode, ExecutionPolicy
core_new/blackboard.py           — Blackboard（当前数据共享层）
core_new/llm_gateway.py          — LLMGateway, generate_text/json/reasoned/with_tools

# Agent 实现
core_new/agents/architecture_agent.py     — 架构设计 agent（已接入工具）
core_new/agents/single_choice_team.py     — 单选 pipeline 所有 agent
core_new/agents/hybrid_subjective_team.py — 综合 pipeline 所有 agent
core_new/agents/file_code_solver.py       — Python 代码求解 agent
core_new/agents/gate_agents.py            — Gate 审核 agent
core_new/agents/unified_pipeline.py       — 统一 pipeline 编排器
core_new/agents/slot_agents.py            — Slot 相关 agent

# 提示语
core_new/prompts/architecture_prompts.py       — 架构 agent 提示语
core_new/prompts/single_choice_prompts.py      — 单选 agent 提示语
core_new/prompts/gate_prompts.py               — Gate 提示语
core_new/slot_prompts.py                       — Slot/主观题提示语

# 数据
data/slots/Q44_slot.md  — Q44 题位考察理念（14K chars，内容丰富的 slot）
data/slots/Q43_slot.md  — Q43 题位
data/slots/Q14_slot.md  — Q14 单选题位

# Provider
llm_providers_new/remote_api.py    — OpenAI 兼容 provider，支持 tools
config.py                          — GLM-5.1 配置
```

---

## 7. 已修复的 Bug 记录

1. **GLM-5.1 输出 C 代码而非 JSON** — 提示语冲突（system 说 markdown，user 说 JSON），统一为 markdown
2. **输出截断（85-518 chars）** — max_tokens=2048 太低，GLM-5.1 thinking 消耗全部 token
3. **`FILE_SOLVER_USER` KeyError 'va_bits'** — f-string 中 `{va_bits}` 被 `.format()` 当占位符，已双写花括号
4. **`_format_comp` NameError 'code_solution'** — 变量引用错误，已删除死代码
5. **GLM-5.1 reasoning_content 吞掉 content** — `enable_thinking=True` 强制深度思考的副作用
