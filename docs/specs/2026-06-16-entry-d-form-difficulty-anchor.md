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

**关键事实（已订正 2026-06-17）**：`thinking_token_budget` 是 vLLM **引擎层**有效控制（非 placebo）。机制：reasoning parser 数 token，到 budget 强制注入 `reasoning_end_str` 截断思考块（实测 budget=200→reasoning 707字符，budget=2000→3512字符，比例~3.5字符/token）。需 vLLM serve 带 `--reasoning-parser qwen3` + `--reasoning-config`（当前部署已配）。

- `enable_thinking`：开/关二元（chat_template 变量）
- `thinking_token_budget`：数值思考深度（vLLM 引擎层，reasoning parser 实现）——**这才是精细控制旋钮**

⚠️ **注意**：budget 单位是 token，不是字符。2000 token ≈ 6000-7000 中文字符的思考量，足够浅推理。早期曾误判 budget 无效，根因是拿 reasoning 字符数（~2233）与 token 预算（2000）直接比较，实际 2233 字符仅 ~640 token，远未触达预算。

**⚠️ 线上模型注意**：budget 仅对本地 vLLM 生效（依赖 reasoning parser）。线上 API 模型无此能力，`_supports_thinking_budget` 会挡掉，传了等于没传。

## ✅ 已修复：Entry D 轮次循环 bug（2026-06-17）

**验证**（session `entry_d_fix`，关思考）：
- Turn 1：出 `[PHASE: combined]` 草案，3 套方案、每题考法级（`[ ]` 细粒度考点）。skill 改动生效。
- Turn 2：教师"选方案C，生成交接文档进入出题" → 1 次 LLM 调用直接产 `paper_request.yaml`（18 slot 全字段、含 expected_form）。**无重生成、无自动 `[✓]`、无卡死**。循环 bug 消失，方案①（combined 一轮）生效。

### 修复内容（3 处）

1. **`interact_core/SKILL.md`**：Entry D 归 `[PHASE: combined]`（`:89`）；Step6 草案头改 combined；Step7→Step8 直连（选完方案即 handoff，禁进 examination 轮、禁重生成）；加红线#9「禁自动 `[✓]`」。
2. **`agents/interact.md`**：`:103` handoff 触发放宽到意图级（含"生成交接/进入出题/确认"即触发，不要求精确短语或"系统消息"）；关键规则补「禁替教师勾选」。
3. **per-role 配置 + thinking_budget 膨胀治理**（修 Turn 2 超长 bug）：
   - 根因：interact 无 per-role 配置 → `thinking_budget` 兜底 `DEFAULT_THINKING_BUDGET`(10000) → `llm_gateway:539` 把 max_tokens 膨胀 `max(16000, 10000+16000)=26000` → 叠 54k input 超 80k。
   - `scheduler.py` interact 路径：补 `enable_thinking` 从 ROLE_PARAMS 读取；关思考时 `thinking_budget=None`（不触发膨胀）；工具循环 `_streaming_chat_call` 传 `enable_thinking`。
   - `pipeline.yaml` roles 补 `interact: { enable_thinking: false }`（max_tokens 不设，保留 scheduler 的 D=16000/其他=8192 逻辑）。
   - **结论：interact 关思考**（历史 entry_d_test1-4 全关思考跑通；开则 Qwen3.6 thinking 无界循环）。检索(grep_search)随 interact 关——检索是读+归纳，开思考只浪费时间。

---

### 旧记录（现象，保留供回溯）

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
