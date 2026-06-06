# Doc Pipeline 架构 Spec — 智能体、路由与协作模式

> 最后更新: 2026-06-06 (v2: Codex hardening)
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
| `question.md` | 通用出题 | L2 | question.md | write_file, exec_python |
| `review.md` | 题目审核 | L3 | review.md | write_file |
| `solve.md` | 独立求解 | L4 | solution.md | write_file, exec_python |
| `final_review.md` | 终审 | L5 | final_review.md | write_file, exec_python |

### 2.2 GPT 中继智能体 (`agents_gpt/*.md`)

| 文件 | 用途 |
|------|------|
| `paper_composer.md` | Qwen 中继：校验 GPT 组卷大纲 |
| `question.md` | Qwen 中继：校验 GPT 出题 |
| `review.md` | Qwen 中继：校验 GPT 审核 |
| `final_review.md` | Qwen 中继：校验 GPT 终审 |

中继智能体职责：
- **不修改 GPT 的审核结论** — 只调整格式
- 校验必要章节是否存在（## status, ## summary 等）
- 标准化 status 值（"通过"→ pass, "需要修改"→ needs_fix）
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

### 3.1 Provider 解析链

```
_get_gateway_for_role(role):
  1. model_routing.get(role)     → 角色专属路由
  2. model_routing.get("_default") → 默认路由
  3. 返回 self.gateway           → 主网关（api_vllm）
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

### 12.6 交互测试结果 (2026-06-06, Qwen 本地模型)

| 场景 | 结果 |
|------|------|
| 模糊意图 "帮我出题" | 正确追问科目/难度/题型 |
| 知识点完整 "出3道中断方式选择题" | 28K 蓝图，17 道真题，教学决策准确 |
| 歧义 "出几道Cache" | 正确追问科目 |
| 组卷 "出一张CO试卷" | compose 模式确认 |
| 多轮 TCP | 2 轮收集，知识点正确解析 |

### 12.7 待完成

- 批注循环（用户修改蓝图后重新合成）
- compose_runner 实际调用
- 生成管线实际执行
