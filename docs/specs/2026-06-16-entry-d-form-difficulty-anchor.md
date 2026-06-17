# Entry D 形式锚点(expected_form)+难度锚定(K值检索) — 实施规格 + 状态

> 本文件是 Entry D 改造的**单一信息源**，含：设计、实施状态、已知问题、根因分析、修复方向。
> 供跨会话/跨工具(zcode 等)接手用。最近更新 2026-06-17。

## Context（为什么做）

Entry D（往年期末卷参考）测试暴露三个漂移：形式（算法分析"给代码分析"可能出成非代码题）、难度（期末卷换成考研级考点）、知识点（被换成别的）。根因：前端用参数知识现编没真检索题库；检索工具不返 K 值无法按难度筛；题干设问形式无锚点。

## 设计决策（定稿）

- **expected_form**：对标考研题位经验卡「考察方式」字段——1-3 句散文（题干给什么/要求什么/核心点）。**仅考察方式散文**。**D-only、nullable**；Entry A 用考研预抽取考察模式，Entry C 留空；下游非空才约束。
- **难度锚定**：`retrieve_anchored_references` 按 K 值门 `D(c)≤D(t)+ε` + MAE 排序，从 question_experiences(2058 题) 检索参考题填 reference_questions（code-as-truth，来源无关）。
- **范围**：Part A（expected_form 全链）+ Part B（K 值检索）。

## 实施状态（已完成并验证，5 个提交）

| commit | 内容 | 验证 |
|---|---|---|
| `a06ceb9` | feat: expected_form 全链(SlotBlueprint/SlotContract 字段 + 通道) + K值检索(retrieve_anchored_references 门控+MAE) + review 审 expected_form + interact_core Entry D + scheduler trace | 单题 design 全链跑通，design_card 含 expected_form 并驱动骨架，review "expected_form 贴合度" pass |
| `9c45ffe` | perf: 组装文档移除 K-radar 评分标准 rubric 段（出题节点用已打好 K 值，不需 rubric；省 1.2KB/节点×3） | compose 测试无回归 |
| `986c28b` | perf: httpx 加传输重试(retries=3)+TCP keepalive，对齐 Claude Code 网络韧性（同网络 CC 不断、流水线易断的根因：默认 transport retries=0 无 keepalive） | provider 构造 OK |
| `1df22e3` | feat: per-role 生成+思考配置（enable_thinking/max_tokens 每 role 独立，scheduler 动态取用）——Qwen3.6 上唯一有效的思考控制 | 单题 408s→200s（2× 提速），窄任务关思考 |
| `df3746f` | fix: 修 `_gateway` typo（scheduler:713），传输错误处理不再崩（踩中"线上断线"场景） | test_node 全 pipeline 跑通不崩 |

**关键事实**：`thinking_budget`（数值上限）对 Qwen3.6 **无效**（chat_template 无 thinking_budget 变量，只有 enable_thinking 开关）。原 thinking_budget 配置是 placebo。per-role `enable_thinking`（开/关）才是真控制。

## 🔴 已知问题：Entry D 轮次循环 bug（系统层状态错误）

**现象**（前端实测，会话 `workspace/2a633e384b39`，计算机组成原理 A 卷）：
```
[0] teacher 上传卷
[1] agent Round1(knowledge): 出3套方案
[2] teacher: "选方案C，生成交接文档进入出题"
[3] agent: 裁剪留C, 没handoff, "等待确认"  ← 进了 Round2
[4] teacher 重复选方案C（被迫第2次）
[5] agent: 自动[✓]全选, "等待系统允许生成交接"  ← 还没handoff
draft头: [ROUND:2][PHASE:examination]，但内容仍是知识点级
```
agent 不读教师选择去推进 handoff，反而重新生成 + 自动 [✓]，循环卡死。教师被迫选 3 次。

### 系统层根因（两处冲突）

**根因1 — Phase 分类冲突**（`interact_core/SKILL.md:89-94`）：
- Entry D 被归入 `[PHASE: knowledge]`（:89），触发 :90-94 的 **"knowledge→examination 两轮"** 逻辑。
- 但这套两轮是**为自由出题(C)/期末卷设计的**（:90-94"无先验→必须先 knowledge 再 examination"，原因是缺知识点先验）。
- Entry D 的方案选项**已带考察方式粒度**（选项是"海明码校验位数计算/CRC检错分析"等具体考法，不是粗知识点）→ Round 2 examination **冗余** → agent 不知道 examination 该干啥 → 重新生成知识点 + 自动 [✓] → 循环。
- 即：Entry D 的方案粒度（已到考法级）与 C 的两轮设计（knowledge 粗→examination 细）**不匹配**，硬套 C 的两轮就乱。

**根因2 — handoff 触发过严**（`interact.md:103`）：
- 触发条件要"没意见了/就这样/确认开始出题"或"系统消息明确要求生成交接文档"。
- 教师说"**生成交接文档进入出题**"没精确匹配上述短语、也不是"系统消息" → agent 判定未触发 → "等待系统允许" → 卡死。

### 修复方向（待做，建议 zcode 接手）

Entry D 不应套用 C 的两轮。两种修法（择一）：

**方案①（推荐）：Entry D 改一轮 combined**
- Entry D 方案选项已到考法级，一轮即可：出 3 套方案（知识点+考察方式+expected_form 都在选项）→ 教师选一套（可批注微调）→ 直接 handoff。
- 改 `interact_core/SKILL.md` Entry D Step6 草案用 `[PHASE: combined]`（非 knowledge）；Step7 选方案 → 直接 Step8 handoff，禁止进 examination 轮。
- 与 Entry A/B 的 combined 一致（它们因经验卡含考法也用 combined）。

**方案②：保留两轮但 Round2 复用选择**
- Round2(examination) **复用** Round1 教师选的方案（不重新生成），只在该方案上展开/确认每题考察方式，让教师二次提交。
- 改 interact_core Entry D Step：明确 Round2 读 Round1 的残留选择、不重新出方案、不自动 [✓]。

**通用修复（两方案都要）**：
- `interact.md:103` handoff 触发条件放宽：教师消息含"生成交接/确认/进入出题"等意图即触发，不要求精确短语或"系统消息"。
- 禁止 agent 自动 [✓] 全选（剥夺教师选择权）。

## 关键文件触点（zcode 改动参考）

- Entry D 流程：`core_new/doc_pipeline/skills/interact_core/SKILL.md`（Entry D 段 Step1-8 + 理念 :85-94 phase 分类）
- handoff 触发：`core_new/doc_pipeline/agents/interact.md:103`（触发条件）
- expected_form 通道：`contracts.py` SlotBlueprint + `compose/{markdown_contract_parser,outline_contract_parser,compose_runner,artifact_store}.py`
- 下游消费：`agents/{question_design,design,review}.md`
- K 值检索：`compose/knowledge_index.py`（retrieve_anchored_references + _extract_k_radar）+ `grep_search_tool.py`
- per-role 配置：`config/pipeline.yaml` roles: + `config.py` ROLE_PARAMS + `scheduler.py` _streaming_chat_call
- 网络韧性：`llm_providers_new/remote_api.py` _resilient_transport
- 单题测试：`scripts/test_node.py`（注入 expected_form + force regen assembled）

## 验证基线
- 单 standard 题（算法设计/AVL）全 pipeline：`scripts/test_node.py --from design_card`，约 200s，result.ok=True，design_card 含 expected_form，review "expected_form 贴合度" pass。
- 前端 Entry D e2e：`scripts/test_interact_cli.py api_vllm <session> --msg "..."`（注意 VLLM_MODEL 需设为 /zhaoshu/llm/Qwen3.6-27B-FP8；缺 socksio 时 pip install socksio）。

## 附：本次会话发现的其他问题（低优先）
- **算法设计题语言不一致**：expected_form 带"用C/C++"，但 design 不一定写进题干（时有时无）——expected_form 是软引导，design 无硬约束保证写语言。
- **reasoning 泄漏**：输出偶尔混入 `I have to give the solution based on the reasoning directly now.</think>` 标记文本（vLLM reasoning parser 偶尔没剥干净）。
- **assemble 多节点注入**：assembled.md 被 design_card/exam_form/design 各 re-prefill（既有设计，非本次引入），是独立优化空间。
- **本地模型 decode ~30 tok/s**（长 thinking 序列下；MTP 已开但长序列降速）——thinking 无界是主因，per-role enable_thinking 已部分缓解。
