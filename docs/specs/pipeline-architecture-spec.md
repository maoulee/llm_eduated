# Doc Pipeline 架构 Spec — 智能体、路由与协作模式

> 最后更新: 2026-06-07 (v3.6: 工具调用两阶段协议、commit-only 收敛、提示语工具名统一)
> 本文档固化流水线核心设计，避免跨会话信息丢失。

---

## 1. 三种模型模式

### 模式 A: 全本地 (Qwen)

```
config: _default: local  →  api_vllm (localhost:8000)
所有层使用 Qwen3.6-27B，通过 tool calls 交互
```

### 模式 B: 全远程 (GLM5.1)

```
config: _default: "{fallback}"  →  glm5.1 (open.bigmodel.cn)
所有层使用 GLM5.1，通过 tool calls 交互
远程模型 max_tokens 自动提升到 40000（推理 token 计入限额）
```

### 模式 C: 混合协作 (GPT 生成 → Qwen 中继)

```
config: role: hybrid
Step 1: GPT (WebGPT) 生成内容（无 tool calls，直接输出）
Step 2: Qwen 接收 GPT 输出 + agents_gpt/{role}.md 中继规范
        → 校验格式、标准化 status、对齐术语
        → 通过 write_file 写入最终文件
```

**混合协作的关键**: GPT 不直接写文件。Qwen 作为中继层，确保格式一致。

---

## 2. 智能体架构

### 2.1 本地模型智能体 (`agents/*.md`)

| 文件 | 角色 | 层 | 输出文件 | 工具 |
|------|------|---|----------|------|
| `outline.md` | 规划 | L1 | outline.md, assembled.md | write_file |
| `question_sc.md` | 选择题 | L2 | question.md | write_file, exec_python |
| `question_comp.md` | 综合题 | L2 | question.md | write_file, exec_python |
| `review.md` | 题目审核 | L3 | review.md | write_file |
| `solve.md` | 独立求解 | L4 | solution.md | write_file, exec_python |
| `final_review.md` | 终审 | L5 | final_review.md | write_file, exec_python |

### 2.2 GPT 中继智能体 (`agents_gpt/*.md`)

| 文件 | 用途 |
|------|------|
| `paper_composer.md` | Qwen 中继：校验 GPT 组卷大纲 |
| `question_sc.md` | Qwen 中继：校验 GPT 选择题 + 格式红线验证 |
| `question_comp.md` | Qwen 中继：校验 GPT 综合题 + 格式红线验证 |
| `review.md` | Qwen 中继：校验 GPT 审核 |
| `solve.md` | Qwen 中继：校验 GPT 求解 + 行为合规检查 |
| `final_review.md` | Qwen 中继：校验 GPT 终审 |

中继智能体职责：
- **不修改 GPT 的审核结论** — 只调整格式
- 校验必要章节是否存在（## status, ## summary 等）
- 标准化 status 值（"通过"→ pass, "需要修改"→ needs_fix）
- 格式红线验证 + 行为合规检查
- 通过 write_file 写入文件

### 2.3 Prompt 组装顺序 (agent_loader.py)

```
_BEHAVIOR_CORE           ← 通用行为控制（逐步执行、工具纪律）
    ↓
Agent MD body            ← 角色身份 + 约束（从 agents/*.md 加载）
    ↓
Behavior variant         ← 领域模式（question_sc/question_comp 等）
    ↓
Write_file suffix        ← 强制工具调用指令
```

**关键**: Agent MD body 必须保留，不能丢弃。之前有 bug 导致 body 被丢弃，已修复。

---

## 3. 调度器路由 (scheduler.py)

### 3.1 统一网关 (Unified Gateway)

```
所有 LLM 调用通过单一 LLMGateway 实例:
  - DocScheduler._get_gateway_for_role(role) → 始终返回 self.gateway
  - model_routing 仅控制 GPT 系统提示选择和 WebGPT 行为
  - 不再为不同 role 创建新的 gateway 实例

Provider 职责分离:
  - RemoteAPIProvider (api_vllm) → 异步 HTTP → 出题流水线（主力）
  - LocalVLLMProvider (local)    → 同步批处理 → 信息抽取（非出题）
  - WebGPT (webgpt)              → GPT API → 混合协作模式

Gateway 并发控制:
  - _remote_sem: asyncio.Semaphore 控制 API 并发数
  - _local_sem: asyncio.Semaphore 控制本地模型并发数
  - 多题目并行: asyncio.gather() + gateway semaphore
```

### 3.2 三种执行路径

```
run_agent() 调度逻辑:

1. hybrid 模式? (_uses_hybrid_for_role)
   → _run_hybrid_agent()
     Step 1: GPT 生成 → WebGPT API
     Step 2: Qwen 中继 → 本地 vLLM + agents_gpt/ 规范

2. webgpt 直接模式? (_uses_webgpt_for_role)
   → _run_webgpt_direct_agent()
     GPT 直接输出，scheduler 写文件（无 Qwen 中继）

3. 默认: gateway tool-call 模式
   → 标准 tool-call 循环（write_file, exec_python）
   → 支持 local (api_vllm) 和 remote (glm5.1)
```

### 3.3 混合模式详细流程

```python
async def _run_hybrid_agent():
    # Step 1: GPT 生成
    gpt_system = _GPT_SYSTEM_PROMPTS[role]   # GPT 看到的系统提示
    gpt_raw = await webgpt_client.delegate(
        system_prompt=gpt_system,
        content=task,                          # 含注入上下文的完整任务
    )
    gpt_content = _extract_direct_output(gpt_raw)

    # Step 2: Qwen 中继
    hybrid_spec = _load_hybrid_spec(role)      # agents_gpt/{role}.md
    qwen_messages = [
        {"role": "system", "content": hybrid_spec},
        {"role": "user", "content": f"GPT产出:\n{gpt_content}\n\n原始任务参考:..."},
    ]
    # Qwen 通过 tool calls 写入最终文件
```

---

## 4. 五层流水线 (orchestrator.py)

### Layer 1: Outline（规划）

```
输入: slot_data + experience_doc + k_definitions
输出: outline.md + assembled.md
跳过: 当 assembled_experience_doc 提供时跳过
      → 直接写入 blueprint.md 和 assembled.md
```

### Layer 2: Question（出题）

```
角色选择: _question_role() 四级解析
  1. 显式 question_type 参数
  2. slot_data["question_type"] 或 slot_data["section"]
  3. assembled doc 头部内容检测（"综合应用题"）
  4. slot_id 模式匹配（Q41-Q47 → comp）

上下文注入: assembled.md + review_comments（如存在）
内部流程: 先 exec_python 校验参数闭合性 → write_file 输出
注意: 不写答案！答案由 Solve Agent 独立产出
```

### Layer 3: Review（审核）

```
输入: assembled.md + question.md
审核维度:
  5.1 知识点覆盖
  5.2 K难度评估（实际 vs 目标，差异≥2级 → needs_fix）
  5.3 条件充分性
  5.4 题干清晰度
  5.5 选项质量（选择题）
  5.6 子问题结构（综合题）
  5.7 风格合规（格式红线检查）
  5.8 经验卡对齐（should_be/should_not_be 逐项对照）

循环: pass → L4, needs_fix → 返回 L2（最多 2 轮）
```

### Layer 4: Solve（求解）

```
策略: 判断题目类型
  - 概念/逻辑题 → 直接写 solution.md
  - 数值题 → solve.py + exec_python + solution.md

约束:
  - 禁止阅读设计说明，只看题干
  - 所有结果从题干参数推导
  - 数值题代码只用标准库
```

### Layer 5: Final Review（终审）

```
输入: assembled.md + question.md + solution.md + solve_output.txt
审核: 求解正确性 + 答案唯一性 + 条件利用率 + 答案自洽性

路由判定:
  pass            → 完成，输出 final.md
  expression_fix  → 就地修正措辞/格式
  question_error  → 返回 L2（重新出题 + 重新求解）
  solution_error  → 返回 L4（最小修改求解）

expression_fix 执行方式:
  本地模型: 直接用 edit_file/write_file 修正
  混合模式: Qwen 执行 GPT 给出的修改指令
```

---

## 5. 就地修正与路由

### 5.1 expression_fix（措辞修正）

```
终审发现措辞/格式问题 → expression_fix
  ↓
本地模式: 终审智能体直接用 edit_file 修正
混合模式: Qwen 根据 GPT 的 corrections 执行修正
  ↓
修正后输出 final.md（含修正后的题目 + 求解 + 审核）
```

### 5.2 question_error（题目根本错误）

```
终审发现参数矛盾/条件缺失 → question_error
  ↓
提取 routing_feedback 中的修正要求
  ↓
返回 Layer 2: Question Agent 重新出题（附修正反馈）
  ↓
自动重新 Layer 4: Solve（题目变了，需重新求解）
  ↓
重新 Layer 5: Final Review
```

### 5.3 solution_error（求解错误）

```
终审发现计算/逻辑错误 → solution_error
  ↓
提取 routing_feedback 中的具体错误描述
  ↓
返回 Layer 4: Solve Agent 最小修改（仅修正错误部分）
  ↓
重新 Layer 5: Final Review
```

---

## 6. 上下文注入 (context.py + pipeline.yaml)

### 6.1 Provider 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| FileProvider | 从 workspace 文件读取 | `{workspace}/{slot_id}/blueprint.md` |
| InlineProvider | 从 runtime_args 读取 | experience_doc, k_definitions |

### 6.2 Role Bindings

```yaml
# config/pipeline.yaml
role_bindings:
  outline:        [experience_doc, k_definitions]
  question:       [assembled, review_comments]
  question_sc:    [assembled, review_comments]
  question_comp:  [assembled, review_comments]
  review:         [assembled, question]
  solve:          [question]
  final_review:   [assembled, question, solution, solve_output]
```

### 6.3 Phase 约束

每个 provider 定义允许注入的层：
- assembled: phases [2, 3, 5] — 出题/审核/终审可见
- question: phases [3, 4, 5] — 审核/求解/终审可见
- solution: phases [5] — 仅终审可见

---

## 7. 配置结构 (config/pipeline.yaml)

### 7.1 路由 Profile

| Profile | 默认 | 特殊路由 | 用途 |
|---------|------|----------|------|
| all_local | local | 无 | 全 Qwen |
| all_remote | remote | 无 | 全 GLM5.1 |
| hybrid | local | question/solve/review → hybrid | GPT 生成 → Qwen 中继 |
| glm_gpt_review | {fallback} | final_review → hybrid | GLM5.1 + GPT 终审 |
| glm_gen_qwen_review | remote | doc_review/review → local | GLM 出题 + Qwen 审核 |
| qwen_gpt_core | local | question/review/solve → webgpt | Qwen + GPT 直出 |

### 7.2 模板变量

- `{fallback}` → 替换为 providers.fallback（默认 "glm5.1"）
- `{local}` → 替换为 providers.local（默认 "api_vllm"）

### 7.3 Provider 配置

```
providers:
  fallback: "glm5.1"           # {fallback} 模板变量
  local: "api_vllm"            # {local} 模板变量
  health_check_ttl: 60
```

环境变量 (.env):
```bash
VLLM_API_BASE=http://127.0.0.1:8000/v1
GLM_API_KEY=<key>
GLM_MODEL=glm-5.1
WEBGPT_API_KEY=sk-chatgpt-team-key123
WEBGPT_BASE_URL=http://localhost:3000  # 默认值
WEBGPT_MODEL=gpt-thinking              # 默认值
```

---

## 8. 风格控制链

```
经验卡 (data/slot_experiences/{slot_id}_experience.md)
  ↓ 出题指导: should_be, should_not_be, 考察模式分布, 选项风格分布
  ↓
出题智能体 (question_sc/comp_skill.md)
  ↓ 格式红线: 5 条禁止规则
  ↓ 题干风格模板: 计算型/概念辨析型/组合判断型
  ↓
题目输出 (question.md)
  ↓ 设计说明: should_be 对照 + should_not_be 排查
  ↓
审核智能体 (review.md 5.7 + 5.8)
  ↓ 风格合规检查 + 经验卡对齐检查
  ↓
pass / needs_fix
```

### SC 格式红线 (5 条)
1. 禁止子问题格式
2. 禁止编程代码
3. 禁止冗长题干（≤3 句话、80 字）
4. 禁止答案出现在题目中
5. 禁止背景故事

### COMP 格式红线 (5 条)
1. 禁止选项格式（无 A/B/C/D）
2. 禁止独立子问（必须有逻辑依赖）
3. 禁止编程代码题干
4. 禁止背景故事
5. 禁止答案出现在题目中

---

## 9. 关键文件索引

### 流程控制
- `core_new/doc_pipeline/orchestrator.py` — 5 层编排 + 条件路由
- `core_new/doc_pipeline/scheduler.py` — 智能体执行 + provider 路由 + hybrid/direct 模式
- `core_new/doc_pipeline/agent_loader.py` — Agent MD 加载 + prompt 组装
- `core_new/doc_pipeline/context.py` — ContextRegistry + FileProvider/InlineProvider
- `core_new/doc_pipeline/pipeline_config.py` — YAML 配置加载
- `core_new/doc_pipeline/contracts.py` — SlotBlueprint, PipelineResult
- `core_new/doc_pipeline/doc_parser.py` — 文档解析（含 bare-header fallback）

### 智能体定义
- `core_new/doc_pipeline/agents/*.md` — 本地模型智能体（7 个）
- `core_new/doc_pipeline/agents_gpt/*.md` — GPT 中继智能体（4 个）

### 领域知识
- `core_new/doc_pipeline/skills/question_create/question_sc_skill.md` — SC 领域规范
- `core_new/doc_pipeline/skills/question_create/question_comp_skill.md` — COMP 领域规范
- `core_new/doc_pipeline/skills/audit_fix/review_skill.md` — 审核领域规范

### 工具
- `core_new/doc_pipeline/tools/write_file.py` — 文件写入
- `core_new/doc_pipeline/tools/exec_python.py` — Python 执行
- `core_new/doc_pipeline/tools/edit_file.py` — 文件编辑

### 模型接入
- `core_new/llm_gateway.py` — 统一 LLM 网关（api_vllm + glm5.1）
- `core_new/webgpt_client.py` — WebGPT 客户端（GPT via WebAI2API）
- `config/pipeline.yaml` — 路由 + 参数 + context injection

### 交互式出题层
- `interact/orchestrator.py` — 顶层协调器（knowledge_point + compose 双模式）
- `interact/session_manager.py` — FSM 多轮会话管理（8 状态 + 批注循环）
- `interact/intent_router.py` — Qwen 意图分类（compose/knowledge_point/clarify）
- `interact/blueprint_synthesizer.py` — 数据注入 + LLM 教学决策（含修订模式）
- `interact/knowledge_retriever.py` — 知识图谱检索 + KG 回退搜索

### 组卷流程
- `compose/compose_runner.py` — Phase A: 大纲生成 + 经验文档组装
- `compose/generate_runner.py` — Phase B: 批量出题 + 格式化导出
- `compose/artifact_store.py` — 经验文档组装 + 知识图谱抽取

### 数据
- `data/slot_experiences/` — 47 份 LLM 合成经验卡
- `data/question_experiences/` — 2058 份原始真题分析
- `data/slot_templates_all.json` — 47 个 slot 模板

### 测试脚本
- `scripts/test_glm_gpt_review.py` — GLM5.1 + GPT 终审测试
- `scripts/test_cross_subject.py` — 跨科目测试
- `scripts/test_glm_comprehensive.py` — GLM5.1 综合题测试
- `scripts/resynthesize_slots.py` — 经验卡 LLM 重抽取

---

## 10. 知识图谱文件

| 科目 | 文件 | 用途 |
|------|------|------|
| CO | `data/computer_organization.md` | 计算机组成原理 |
| DS | `data/data_structure.md` | 数据结构 |
| OS | `data/operating_system_knowledge.md` | 操作系统 |
| CN | `data/computer_network.md` | 计算机网络 |
| 大纲 | `data/dagang.md` | 2025 408 考研大纲 |

路由: `artifact_store.py._KG_FILE_MAP` 和 `compose_runner.py.subject_files` 均指向英文文件名。

---

## 11. 安全加固与修复 (2026-06-06 v2)

### 11.1 Solve 智能体隔离

```
问题: Solve Agent (L4) 能看到 question.md 中的「设计说明」和「参数选择理由」，
      导致求解不是独立推导而是"自圆其说"。

修复: orchestrator 在调用 solve 前生成 question_public.md:
      - 仅保留: 题干、选项（SC）/ 子问题（COMP）
      - 剥离: 设计说明、参数选择理由、K值对齐说明
      - Solve Agent 读取 question_public.md 而非 question.md
```

### 11.2 Review / Final Review fail-closed

```
问题: doc_parser 解析 status 失败时默认返回 "pass"，导致质量门失效。

修复: 白名单校验:
      - review:      合法值 = ["pass", "needs_fix"]
      - final_review: 合法值 = ["pass", "expression_fix", "question_error", "solution_error"]
      - 不在白名单 → 视为解析失败 → 重试（不默认 pass）
```

### 11.3 知识图谱抽取修复

```
问题: artifact_store 的 translate_code() 污染大纲机器契约内容；
      DS/OS/CN 知识图谱以数字编号为章节标题，正则无法匹配。

修复:
      - translate_code() 不再应用到大纲契约文本
      - KG 抽取支持数字章节标题（如 "## 3. 数据链路层"）
```

### 11.4 final.md 导出结构化

```
问题: final.md 导出时题目内容为空，排版器拿到空字段。

修复: doc_parser 新增 parse_final_sections()，将 question.md 解析为:
      - stem (题干)
      - options (选项，SC)
      - sub_questions (子问题，COMP)
      - answer (答案)
      - explanation (解析)
      排版器使用解析后的结构化字段。
```

### 11.5 混合模式路由补全

```
新增 agents_gpt/ 中继提示:
      - question_sc.md     — GPT→Qwen SC 出题中继
      - question_comp.md   — GPT→Qwen COMP 出题中继
      - solve.md           — GPT→Qwen 求解中继
      - final_review.md    — GPT→Qwen 终审中继（已有，更新）
      - review.md          — GPT→Qwen 审核中继（已有，更新）

删除:
      - agents_gpt/question.md — 被拆分为 question_sc + question_comp
      - agents.py — 完全由 agent_loader.py 替代，不再需要
```

### 11.6 关键文件索引更新

**已删除文件**:
- `core_new/doc_pipeline/agents.py` — 被 `agent_loader.py` + `agents/*.md` 替代
- `core_new/doc_pipeline/agents_gpt/question.md` — 被拆分为 question_sc/question_comp

**新增文件**:
- `core_new/doc_pipeline/agents_gpt/question_sc.md` — SC 混合中继
- `core_new/doc_pipeline/agents_gpt/question_comp.md` — COMP 混合中继
- `core_new/doc_pipeline/agents_gpt/solve.md` — 求解混合中继

**验证状态**: 51 pipeline tests passed, 244 total tests passed。

---

## 12. 交互式出题层 (Interaction Layer)

> 新增: 2026-06-06
> 用户通过自然语言交互，系统自动生成 assembled.md 蓝图并驱动 5 层流水线出题。

### 12.1 架构

```
交互智能体 (Qwen本地, ~50 token LLM) → 意图路由
     ├─ compose → compose_runner (组卷)
     └─ knowledge_point → knowledge_retriever + blueprint_synthesizer → assembled.md
                                                    ↓
                                              沟通智能体 ↔ 用户批注
                                                    ↓
                                              批准后 → 5层流水线并行出题
```

### 12.2 模块结构

```
interact/
├── knowledge_retriever.py   — 纯Python: 图谱检索+题目收集+KG文件回退搜索
├── blueprint_synthesizer.py — Python数据注入+LLM教学决策→assembled.md
├── intent_router.py         — Qwen意图分类 (compose/knowledge_point/clarify)
├── session_manager.py       — FSM多轮会话管理 (8状态)
└── orchestrator.py          — 顶层协调器+生成管线对接
```

### 12.3 设计原则

- **Python 做数据搬运，LLM 做教学决策** — 检索/聚合用 Python，考察角度和难度梯度由 LLM 生成
- **知识图谱子树和历年真题经验原样注入** — LLM 不重写原始知识数据
- **LLM 只生成**: 考察角度、难度梯度、should_be/should_not_be、题型建议
- **assembled.md 格式与 slot 模式完全一致** — 下游 5 层流水线无感

### 12.4 知识检索回退 (Knowledge Retriever)

```
knowledge_registry.json 覆盖:
  - CO (137 tags)
  - DS (partial)

回退策略:
  CN/OS 查询 → KG markdown 文件 heading 级搜索
  示例: "TCP拥塞控制" → CN KG file → "CN-5 > TCP协议 > TCP拥塞控制"
```

### 12.5 会话 FSM

```
IDLE → COLLECTING → BLUEPRINT_READY → ANNOTATING → APPROVED → GENERATING → COMPLETE
                                                       ↑    ↓ (max 3 rounds)
                                                       └────┘
```

- **IDLE**: 等待用户发起
- **COLLECTING**: 收集科目/知识点/难度/题型信息
- **BLUEPRINT_READY**: assembled.md 已生成，等待用户确认
- **ANNOTATING**: 用户批注修改中（最多 3 轮）
- **APPROVED**: 用户批准，准备执行
- **GENERATING**: 5 层流水线执行中
- **COMPLETE**: 出题完成

- **Compose 模式特殊处理**: BLUEPRINT_READY 状态下反馈不进入 ANNOTATING，而是通过 _handle_compose_feedback() 重新提取参数后展示更新确认
- **歧义消解**: pending_candidates 存储候选列表，用户输入编号直接映射

### 12.6 交互测试结果 (2026-06-06, Qwen 本地模型)

| 场景 | 结果 |
|------|------|
| 模糊意图 "帮我出题" | 正确追问科目/难度/题型 |
| 知识点完整 "出3道中断方式选择题" | 28K 蓝图，17 道真题，教学决策准确 |
| 歧义 "出几道Cache" | 正确追问科目 |
| 组卷 "出一张CO试卷" | compose 模式确认 |
| 多轮 TCP | 2 轮收集，知识点正确解析 |

### 12.7 批注循环 (Annotation Loop)

```
用户反馈 → BLUEPRINT_READY → ANNOTATING
                ↑                    ↓
                │           synthesizer(revision mode)
                │                    ↓
                └────────── BLUEPRINT_READY (修订版)
```

- `BlueprintSynthesizer.synthesize()` 检测 `existing_blueprint` + `feedback` → 使用 `BLUEPRINT_REVISION_SYSTEM_PROMPT`
- 修订模式：LLM 收到当前蓝图 + 统计数据 + 教师反馈，只修改被指出的部分
- 最多 3 轮批注，超过自动批准
- 任意轮次说"确认" → 立即进入 APPROVED → 触发生成

### 审批判断
- 函数式两步检查：先匹配审批词，再扫描前1-2字符检查否定词（不/别/未），后缀检查问句语气词（吗/的）
- 正确拒绝：不能通过、不要批准、可以吗、别同意
- 正确接受：确认、通过、可以、好的、OK

### 12.8 组卷模式对接

交互层 compose 模式完整对接两阶段流程：
- Phase A: `compose_runner.run_compose()` — 大纲生成 + 经验文档组装
- Phase B: `generate_runner.run_generate()` — 批量出题 + 格式化导出
- `_build_compose_requirements()` 将收集的参数转为用户需求字符串
- `_load_compose_assets()` 从 `data/slot_templates.json` + `data/slot_experiences/` 加载数据
- compose 模式反馈通过 `_handle_compose_feedback()` 处理，重新提取参数而非调用蓝图修订

### 12.9 Agent 行为约束分层

| 层 | 文件 | 职责 |
|----|------|------|
| Agent 行为 (agents/*.md) | 核心行为约束：契约忠实、格式红线、工作流规则、禁止行为 |
| Skill 领域 (skills/*.md) | 408领域模板：题干风格、选项模式、经验卡消费 |
| GPT 提示 (_GPT_SYSTEM_PROMPTS) | GPT 生成时的行为约束注入 |
| GPT 中继 (agents_gpt/*.md) | Qwen 校验 GPT 输出时的行为合规检查 |

所有路径的行为约束对齐：本地模型、GPT生成、GPT中继校验使用同一套规则定义。

---

## 13. 批量完成与并行出题 (2026-06-06 v3.2)

### 13.1 智能体批量完成约束

```
问题: 智能体分步调用 exec_python 后不写文件，导致无意义重试循环。
      例如 question_sc attempt 1 只调 exec_python → retry → attempt 2 才 write_file。

修复: 智能体行为约束新增两条规则:
  1. 一次性批量完成: 同一个 tool_calls 批次中同时调用 exec_python + write_file
     → 先在思考中设计完整内容，然后一次提交验证脚本和输出文件
  2. 一次性全量校验: 一个 exec_python 脚本完成所有参数检查
     → 禁止分多次调用逐步校验，出错则修改参数后一次性重新校验

涉及文件:
  - agents/question_sc.md   — 新增规则 6, 7
  - agents/question_comp.md  — 新增规则 8, 9
  - agents/solve.md          — 新增规则 9, 10
  - scheduler.py _GPT_SYSTEM_PROMPTS — question_sc/comp/solve 均新增
```

### 13.2 调度器重试优化

```
问题: exec_python 已执行但 write_file 未调用时，模型在重试中重复运行 exec_python。

修复: 调度器检测到 exec_python 已执行 → 重试提示改为:
  "exec_python 已执行，但未写入 {file}。请立即调用 write_file，不要再重复 exec_python。"

涉及文件: scheduler.py 第 554-570 行
```

### 13.3 并行出题

```
问题: 多题目生成是顺序执行 (for loop + await)。

修复: interact/orchestrator.py 多题目改为 asyncio.gather() 并行:
  - question_count > 1: asyncio.gather(*[_run_one(i) for i in range(N)])
  - question_count == 1: await _run_one(0)（保持单题简单路径）
  - 每题独立 DocPipeline 实例，共享同一 gateway（由 semaphore 控制并发）
```

### 13.4 Provider 兼容性修复

```
问题: LocalVLLMProvider 将应用级参数 (request_timeout, max_retries 等)
      传给 vLLM EngineArgs，导致 TypeError。

修复: local_batch.py 新增 _NON_VLLM_KEYS 过滤集，__init__ 中过滤后再传给 LLM()。

架构明确:
  - LocalVLLMProvider → 批量信息抽取（同步，本地模型加载）
  - RemoteAPIProvider → 出题流水线（异步 HTTP，semaphore 并发）
  - 两者不混用，出题统一走 RemoteAPIProvider
```

### 13.5 端到端测试验证 (2026-06-06)

**测试 1: 交互层 — Cache 映射选择题**

| 阶段 | 耗时 | 状态 |
|------|------|------|
| Turn 1: 蓝图生成 | 6.2s | blueprint_ready |
| Turn 2: 5层流水线 | 152.7s | complete |
| question_sc | - | exec_python验证 + write_file |
| review | - | pass (K1=3,K2=2,K3=3,K4=2,K5=1) |
| solve | - | 答案B (12,2,6), exec_python交叉验证 |
| final_review | - | pass, 9/10 |

**测试 2: 单题流水线 — AVL树前序遍历**

| 阶段 | 耗时 | 状态 |
|------|------|------|
| question_sc | ~6min (3 attempts, 37K reasoning) | pass |
| review | - | needs_fix (设计说明旋转分析有误) |
| question_sc (fix) | - | pass |
| solve | - | 答案A (30,10,20,50,40) |
| final_review | - | pass, 9/10 |
| **总计** | **718.7s** | **ok=True** |

**质量评估**:
- 题干风格: 接近408真题水平（简洁、参数友好、无冗余）
- 干扰项设计: 精良（每种错误认知对应一个干扰项）
- 已知问题: final.md 格式组装有重复标题 bug → 待修复

---

## 14. WebGPT 会话生命周期管理 (2026-06-06 v3.3)

### 14.1 问题

```
现象: 新 pipeline run 的 GPT 会话中出现 "上个会话怎么怎么样" 的残留上下文。

根因:
  1. pipeline finally 块立即调用 cleanup_webgpt() → 立即删除云端会话
  2. ChatGPT 后端删除会话后，conversation_url 被快速回收
  3. 新 pipeline run 创建新会话时，ChatGPT 可能仍有残留上下文
  4. 同一 slot 内多个 agent 的会话也受影响

用户需求:
  - 不立即删除云端会话，而是累计到一定数量后统一批量删除
  - 本地不需要持久化 conversation_url（可从云端拉取）
  - 核心保证: 新会话不会看到旧会话的上下文
```

### 14.2 延迟批量删除机制

```
WebGPTClient 会话清理流程 (修改后):

pipeline 完成
  ↓
scheduler.cleanup_webgpt(slot_id)
  ↓
client.cleanup(slot_id)          ← 仅释放本地 session 映射
  ↓
conversation_url → _pending_deletions[]   ← 暂存，不删云端
  ↓
len(_pending_deletions) >= _batch_threshold?
  ├─ 否: 结束（会话继续留在 ChatGPT 云端）
  └─ 是: _flush_batch() → DELETE /admin/chatgpt/conversation (批量)
         ├─ 成功: 日志记录
         └─ 失败: URLs 重新入队，下次重试
```

### 14.3 配置参数

```
环境变量:
  WEBGPT_BATCH_DELETE_THRESHOLD — 累计多少条后触发批量删除（默认 10）

内部常量:
  _BATCH_DELETE_THRESHOLD = 10  — 类常量默认值

参数传递:
  get_webgpt_client() → 从环境变量读取 → WebGPTClient(batch_delete_threshold=...)
```

### 14.4 关键 API

```
WebGPTClient:
  cleanup(slot_id)              — 释放本地映射 + 暂存 URL（不删云端）
  flush_pending_deletions()     — 强制立即批量删除所有暂存 URL
  close()                       — 先 flush + 再关闭 HTTP 客户端

_flush_batch() 内部逻辑:
  1. 原子取出 _pending_deletions → urls
  2. DELETE /admin/chatgpt/conversation {"conversation_urls": urls}
  3. 失败时 urls 重新入队（[:0] = urls），下次 cleanup 再尝试
```

### 14.5 调用链覆盖

```
DocPipeline.run() finally 块:
  await scheduler.cleanup_webgpt(slot_id)
    → 遍历该 slot 的所有 session_keys
    → 逐个调用 client.cleanup(slot_id=key)
    → 释放本地映射 + 暂存 URL，不删云端

compose_runner._compose_hybrid():
  slot_id = "compose-{monotonic_ns()}"  ← 每次运行唯一
  finally: client.cleanup(slot_id)      ← 释放 + 暂存

compose_runner._revise_hybrid():
  slot_id = "revise-{monotonic_ns()}"   ← 每次运行唯一
  finally: client.cleanup(slot_id)      ← 释放 + 暂存

进程退出:
  atexit → shutdown_webgpt_client() → flush + close
  保证: 即使 pending 数量低于阈值，退出前也会批量删除
```

### 14.6 涉及文件

```
修改:
  - core_new/webgpt_client.py   — 延迟批量删除 + atexit shutdown hook
  - compose/compose_runner.py   — slot_id 改为 run-scoped + finally cleanup

未修改（接口兼容）:
  - core_new/doc_pipeline/scheduler.py  — cleanup_webgpt() 调用不变
  - core_new/doc_pipeline/__init__.py   — finally 块调用不变
```

---

## 15. final.md 格式组装修复 (2026-06-06 v3.3)

### 15.1 问题

```
final.md 组装时出现两类格式错误:

1. 重复标题: "## 题目\n## 题目" — question.md 使用 ## 题目 而非 ## 题干 时触发
2. 重复设计说明: "## 设计说明" 出现两次
3. 答案内容残留: stem 提取失败时 fallback 到完整 question_text，带入所有 section
```

### 15.2 根因

```
_format_final() 原始逻辑:
  stem = q_sections.get("题干", question_text)  # fallback = 完整文件!

当 question.md 使用 ## 题目 而非 ## 题干 时:
  1. _extract_sections 返回 {"题目": "..."}
  2. q_sections.get("题干") → None → stem = 完整 question_text
  3. 完整 question_text 已含 ## 题目 → 外层再加 ## 题目 → 重复
  4. 完整 question_text 已含 ## 设计说明 → 后续又单独提取一次 → 重复
```

### 15.3 修复

```
stem 提取改为多级精确匹配，不再 fallback 到完整文件:

  stem = (q_sections.get("题干")
          or q_sections.get("题目")
          or extract_h2_section(question_text, "题干")
          or extract_h2_section(question_text, "题目"))

保证:
  - 仅提取题干内容，不含其他 section
  - 兼容 "题干" 和 "题目" 两种标题写法
  - 永远不会 fallback 到包含所有 section 的完整文件

answer 输出也改为条件写入:
  if answer: parts.append(...)  — 避免空答案 section
```

---

## 16. 审核体系加固 (2026-06-06 v3.4)

### 16.1 审核漏洞清单与修复

```
┌─────┬──────────────────────────────────────────┬───────────────────────┐
│  #  │ 漏洞                                     │ 修复                  │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V1  │ Layer 3 最后一次迭代跳过审核，无条件放行  │ 最后迭代也审核，       │
│     │ (MAX_REVIEW_RETRIES=2 → iter=2 跳过)     │ needs_fix → 失败      │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V2  │ "pass with suggestions" 被解析为 pass    │ _PASS_QUALIFIERS 正则  │
│     │ (正则 \bpass\b 匹配嵌入词)               │ "but/with/虽然...但"   │
│     │                                          │ → 降级为 needs_fix    │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V3  │ "无法攻破 → pass" 措辞模糊               │ 8条明确准入条件清单    │
│     │ LLM 理解为"找不出问题就放行"             │ 全部满足才 pass        │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V4  │ 设计说明一致性不在审核维度                │ 新增: 设计说明中的     │
│     │ (Q12 案例已证实)                         │ 考察模式/参数/干扰策略 │
│     │                                          │ 必须与题目实际一致     │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V5  │ "基本通过"/"有条件通过" 被 CN map 漏掉   │ 新增 CN 映射条目:      │
│     │                                          │ "基本通过"→needs_fix  │
│     │                                          │ "有条件通过"→needs_fix│
│     │                                          │ "需要完善"→needs_fix  │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V6  │ compose_runner 固定 slot_id 复用会话      │ run-scoped key:       │
│     │ "compose"/"revise" 跨 run 泄漏上下文     │ compose-{ns()}/       │
│     │                                          │ revise-{ns()} + finally cleanup │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V7  │ _flush_batch HTTP 非 200 丢弃 URLs       │ 非 200 也重新入队     │
├─────┼──────────────────────────────────────────┼───────────────────────┤
│ V8  │ 进程退出前 pending < threshold 不删除     │ atexit →              │
│     │                                          │ shutdown_webgpt_client│
└─────┴──────────────────────────────────────────┴───────────────────────┘
```

### 16.2 Layer 3 审核循环修改

```
修改前 (orchestrator.py):
  for iteration in range(MAX_REVIEW_RETRIES + 1):  # 0,1,2
      ...
      if iteration < MAX_REVIEW_RETRIES:           # iter 0,1 走审核
          review(...)
      else:                                         # iter 2 跳过，无条件放行
          logger.info("Review SKIPPED (final iteration)")

修改后:
  for iteration in range(MAX_REVIEW_RETRIES + 1):  # 0,1,2
      ...
      review(...)                                   # 每次迭代都审核
      if review_status == "pass": break
      if iteration >= MAX_REVIEW_RETRIES:
          return _fail_result("Review still needs_fix after 3 iterations")
      # needs_fix: loop back to question
```

### 16.3 Review Agent pass 准入条件

```
修改 agents/review.md 判定规则:

pass 必须同时满足:
  a. 知识点与规划完全一致
  b. K难度实际值与目标值差异 < 2级
  c. 所有条件均被使用且无矛盾
  d. 题干无歧义
  e. 选项有且仅有1个正确答案（选择题）
  f. 设计说明与题目实际内容一致（考察模式、参数分析、干扰策略均准确）
  g. 未触犯任何 should_not_be 条款
  h. 未违反任何格式红线

新增 hard-block:
  - 设计说明与题目实际不一致 → needs_fix
  - 禁止 "pass with suggestions"：有问题必须写 needs_fix
```

### 16.4 status 解析收紧

```
新增 _PASS_QUALIFIERS 正则 (doc_parser.py):
  匹配: "with suggestions", "with reservations", "but",
        "however", "虽然...但", "通过...但", "合格...但"
  效果: "pass with suggestions" → needs_fix
        "通过，但..." → needs_fix

新增 _STATUS_CN_MAP 条目:
  "基本通过"   → needs_fix
  "有条件通过" → needs_fix
  "需要完善"   → needs_fix
```

### 16.5 涉及文件

```
修改:
  - core_new/doc_pipeline/orchestrator.py     — Layer 3 最后迭代不再跳过审核
  - core_new/doc_pipeline/doc_parser.py       — _PASS_QUALIFIERS + CN map 扩充
  - core_new/doc_pipeline/agents/review.md    — pass 准入条件清单 + hard-block
  - core_new/webgpt_client.py                 — non-200 re-queue + atexit shutdown
  - compose/compose_runner.py                 — run-scoped slot_id + finally cleanup
  - interact/session_manager.py              — compose 提示文案修正
```

---

## 17. 审核职责重设计 (2026-06-06 v3.5)

### 17.1 设计原则

```
三大核心原则:

1. 评分必有理由
   - 每个审核维度的评分/判定必须附具体原因
   - 通过: 说明为什么通过（锚点匹配、条件逐项确认等）
   - 偏差: 说明具体偏差值和原因（如 "K3 实际=1 目标=3，当前只需1步代入"）
   - 禁止只写"通过"或"偏差"不给理由
   - 适用于所有路径: 本地模型、GPT 直接、GPT 混合中继

2. 最小修改原则
   - needs_fix / routing_feedback 必须指出需要修改的最小范围
   - 明确标注已达标、不需要改的部分
   - 修正建议必须是可操作的最小变更（如 "将选项C从X改为Y"）
   - 禁止要求全文重写
   - Question Agent / Solve Agent 基于现有内容做定向修正

3. 题干风格与考察形式审核
   - 考察形式是否与蓝图规划一致
   - 题干是否像408真题（非教科书例题/练习册）
   - 区分度评估（全对/半对/全错的答案分布）
   - 考察形式有效性（是否真正测到目标能力）
```

### 17.2 Layer 3 Review 职责

```
纯守门角色 — 不产出交付件

审核维度 (9项):
  1. 知识点覆盖
  2. K难度评估 (逐项对比 K1-K5)
  3. 条件充分性
  4. 题干清晰度
  5. 选项质量 (选择题)
  6. 子问题结构 (综合题)
  7. 格式红线
  8. 题干风格与考察形式 [新增]
     - 408真题风格还原度
     - 区分度评估
     - 考察形式匹配度
     - 考察形式有效性
  9. 经验卡对齐

needs_fix 输出格式 (强制结构):
  ### 问题 N: [维度名] — [问题摘要]
  - 当前状态: [具体值/内容]
  - 期望状态: [具体应该达到什么]
  - 修正建议: [最小修改方案]
  - 不要修改: [已达标部分]

pass 准入条件 (8条全满足):
  a. 知识点与规划完全一致
  b. K难度差异 < 2级
  c. 所有条件使用且无矛盾
  d. 题干无歧义
  e. 选项有且仅有1个正确 (选择题)
  f. 设计说明与题目实际一致
  g. 未触犯 should_not_be / 格式红线
  h. 题干风格像408真题 + 考察形式匹配规划 [新增]
```

### 17.3 Layer 5 Final Review 职责

```
守门 + 交付件生产

pass / expression_fix 时:
  → 写 final_review.md (审核记录)
  → 写 final.md (最终交付文档) [新增: agent 直接产出]

question_error / solution_error 时:
  → 写 final_review.md (含 routing_feedback)
  → 不写 final.md

final.md 格式 (agent 产出):
  ## 题目        — 题干原文
  ## 选项/子问题  — 原文
  ## 求解过程    — 从 solution.md 提取的关键步骤
  ## 答案        — 最终答案
  ## 设计说明    — 仅保留有教学参考价值的内容 (可选)
  注意: 不包含 status/summary/score 等审核元数据

_format_final() 降级为 fallback:
  orchestrator 检查 final.md 是否已存在
  → 存在: 跳过机械组装 (agent 已产出)
  → 不存在: 使用 _format_final() 兜底
```

### 17.4 涉及文件

```
修改:
  - agents/review.md              — 新增 5.8 题干风格审核 + 评分理由强制 + 最小修改原则
  - agents/final_review.md        — agent 产出 final.md + 评分理由 + 最小修改
  - scheduler.py (_GPT_SYSTEM_PROMPTS) — review/final_review GPT 提示同步更新
  - orchestrator.py               — _format_final() 降级为 fallback

测试: 285 passed
```

---

## 18. 工具调用协议收敛 (2026-06-07 v3.6)

### 18.1 问题

```
现象:
  - question/solve agent 已完成验证，但迟迟不写目标文件
  - retry/intervention 后模型把工具调用写成正文、XML 或空 JSON 数组
  - 多工具 tool_choice=required 时，模型在 write_file / exec_file / edit_file / read_file 间摇摆
  - 结果可能产生超长无效正文，直到 max_tokens 被耗尽

根因:
  系统在“最终提交目标文件”阶段仍暴露验证/编辑/读取工具。
  这让模型继续修验证脚本或尝试非协议工具格式，而不是收敛到目标文件写入。
```

### 18.2 两阶段工具状态机

```
阶段 A: explore/verify
  可用工具: role frontmatter 声明的工具
  典型流程:
    question_*: write_file(verify.py) → exec_file(verify.py) → write_file(question.md)
    solve:      write_file(solve.py)  → exec_file(solve.py)  → write_file(solution.md)

阶段 B: commit-only
  触发条件:
    - 连续 3 轮工具调用仍未写入 expected_fn
    - 或连续 no_output / malformed output 且已有验证循环迹象

  动作:
    1. 丢弃前序 assistant/tool 对话历史，重建短上下文
    2. 保留原始任务、工具执行摘要、工作区已写文件摘要
    3. tools 仅暴露 write_file
    4. tool_choice 强制 {"type":"function","function":{"name":"write_file"}}
    5. 明确禁止 exec_file/edit_file/read_file/XML/正文 JSON 工具调用
```

### 18.3 Secondary Output 规则

```
final_review 需要写两个文件:
  - primary: final_review.md
  - secondary: final.md

primary 写入后，secondary follow-up 也必须使用 commit-only 工具空间:
  tools = [write_file]
  tool_choice = write_file

禁止在 final.md follow-up 阶段重新暴露 exec_file/edit_file/read_file。
```

### 18.4 提示语一致性

```
当前真实工具名:
  - write_file
  - exec_file
  - edit_file
  - read_file

Agent system prompt 不得再出现旧工具名 exec_python。
验证流程必须写成:
  write_file(verify.py/solve.py) → exec_file(...) → write_file(expected_fn)
```

### 18.5 涉及文件

```
修改:
  - core_new/doc_pipeline/scheduler.py     — commit-only recovery + secondary write-only
  - core_new/doc_pipeline/agent_loader.py  — exec_python 提示改为 exec_file
  - tests/test_doc_pipeline.py             — 工具协议回归测试

验证:
  - pytest tests/test_doc_pipeline.py::TestDocSchedulerToolProtocol -q  → 6 passed
  - pytest tests/test_doc_pipeline.py -q                                → 53 passed
  - pytest tests -q                                                     → 287 passed, 13 skipped
```
