# Entry D 形式锚点（expected_form）+ 难度锚定（K 值检索）— 实施规格

> 原 plan 文件 `/root/.claude/plans/ticklish-shimmying-owl.md` 被 worktree 守卫拦截（仓库外），改存工作树内 `docs/specs/`（项目 spec 惯例）。定稿日期 2026-06-16。

## Context（为什么做）

Entry D（往年期末卷参考）测试（会话 `1e1f7e78068a`，皖西学院数据结构期末 A 卷）暴露三个漂移：形式（算法分析"给代码分析"可能出成非代码题）、难度（期末卷换成考研级考点）、知识点（MST→关键路径、倒数第 k→判环、WPL→路径输出）。

**根因（已取证确认）**：
1. 前端 interact 用**参数知识现编**，没真检索 `question_experiences/`（2058 题，100% 含 K1-K5）；
2. 检索工具 `grep_search` 返回**不含 K 值**（`grep_search_tool.py:121-133`），无法按难度筛；
3. **题干设问形式无锚点**：SlotBlueprint 只有 `examination_mode`（认知模式），没有"题干设问形式"，下游 design 凭认知模式出题 → 难度对、形式错。

**两个关键发现（简化方案）**：
- 下游 `artifact_store.py:135-148` 已把 `reference_questions` 里每道参考题的 K 值+考察模式+题干+陷阱自动装配进 assembled.md 喂 design_card。→ 前端把 K 值过滤后的题填进 `reference_questions`，下游自动拿到难度+形式，**无需新造下游通道**。
- K 值解析正则可复用 `artifact_store._extract_k_values`（:614）。

## 定稿决策
- **expected_form**：对标 `Q13_experience.md` 模式 X 的「考察方式」字段——1-3 句散文（题干给什么/要求什么/核心点）。**仅考察方式散文**（不带陷阱/干扰/参数类型）。**D-only、nullable**；Entry A 用考研预抽取考察模式，Entry C 留空；下游非空才约束。
- **范围**：Part A（expected_form 全链）+ Part B（K 值检索）一起做。

## 三层改动

### ① Format 层（expected_form 字段通道，搭 examination_mode 既有车）
- `core_new/doc_pipeline/contracts.py`：SlotBlueprint 加 `expected_form: str = ""`（:19 附近）
- `compose/markdown_contract_parser.py:319`：解析支持 expected_form（可选，不入 _REQUIRED_FIELDS）；`compose/outline_contract_parser.py:20` 同步
- `compose/compose_runner.py:572/714`：SlotBlueprint 构建映射 expected_form
- `compose/artifact_store.py:73-97`：「本次出题要求」段加一行 expected_form（非空才写）
- `interact_core/SKILL.md`：paper_request.yaml 模板加 expected_form 字段

### ② Skill 层（前端产期望形式 + K 值检索）
`interact_core/SKILL.md` Entry D 段（:265-408）：
- Step 2 加：每题位提取「期望形式」（考察方式式）+ 轻量估 K 值（`slot_extractor.py` 的 `COGNITIVE_RADAR_SCALE` 原文嵌入提示）
- Step 5/8 改：从参数现编 → 真检索（按科目 KG）→ K 值门 `D(c)≤D(t)+ε` 过滤 → MAE 排序 → 填 `reference_questions`；写 expected_form 进 handoff
- Part B：`compose/knowledge_index.py` 的 `QuestionMeta`+`_parse_file`（:227）解析 K1-K5（复用 `_extract_k_values:614` 正则）；`SearchHit`+`search()`（:72）返 `k_radar`；`grep_search_tool.py:121-133` results 加 `k_radar`

### ③ Behavior 层（下游基于期望形式出题）
- `question_design.md:59`：blueprint_contract 摘取加 expected_form；question_structure_plan 按期望形式组织子问链
- `design.md`：P1 读 design_card 的 expected_form，非空时按它组织题干（硬约束）；加 P1 红线"遵守 expected_form"
- `interact.md`：Entry D 职责加"产出期望形式"

### 附：审计缺口
- `scheduler.py:1163` `run_conversation_turn` 补写 trace.jsonl（复用 `run_agent:684` 的 `_write_trace`），让 interact 检索可审计

## 复用点
- K 值解析正则：`compose/artifact_store.py:_extract_k_values`（:614）
- 参考题装配（已含 K 值+考察模式+题干）：`_build_reference_question_entries`（:463）/`_format_reference_entry`（:490）
- K 值评分标准（轻量估）：`slot_extractor.py` 的 `COGNITIVE_RADAR_SCALE`
- K 值聚合：`compose/k_radar_reader.py`
- 字段通道：`examination_mode` 既有 handoff→parser→SlotBlueprint→assembled→design_card 链路

## 验证（前端先行）
1. **前端优先（interact 智能体单独验证）**：重跑 `1e1f7e78068a` 期末卷走 Entry D，检查：
   - 每题位 `expected_form` 非空且形式对（算法分析=给代码、应用题=画图模拟、概念选择=留空）；
   - 每题位 K 值已轻量估出；
   - `reference_questions` 是 K 值过滤后的（考研难题 K-sum≥14 被门挡，合适考研简单/中档+练习+模拟入选）；
   - `trace.jsonl` 有 grep_search 调用记录（前端真检索了，不是参数现编）。
2. **下游验证**：推进一道算法分析题到 design，产出的题干**含代码、子问围绕代码**（expected_form 生效，形式不再漂移）。

## 审核（superpowers 工作流，authoring/review 分离）
- 实现完成后，用 `superpowers:requesting-code-review`（或 OMC code-reviewer agent）做**独立审核 pass**，不自审。
- 重点核查：expected_form 通道端到端不丢字段；K 值检索门控逻辑正确（门+MAE）；interact_core 的 Entry D 改动不破坏 A/B/C；trace.jsonl 不影响既有 run_agent 行为。
