# 智能体信息流审计报告

## 审计维度
对每个智能体检查：**输入（能获得什么）→ Prompt（要求输出什么）→ 解析（实际提取什么）→ 缺失处理（没产出怎么办）**

---

## 1. 全链路信息流图

```
Blueprint → Design → [Options(SC)] → Gate → Solver → Verify → Format → Rubric → FinalReview → FinalFixer → Summary → Assemble → Export
```

---

## 2. 逐智能体审计

### 2.1 DesignAgent（QuestionDesignerAgent）

| 维度 | 详情 |
|------|------|
| **输入** | `current_blueprint`（蓝图要求）、`experience_card`（参考题）、`stem_fix_instruction`（修订指令，可选） |
| **Prompt 请求** | `stem`、`sub_questions`(JSON数组)、`given_conditions`、`difficulty_self_assessment`、`knowledge_points`、`parameter_notes`、`reasoning_form`、`sub_q1~3_intent`、`trap_design`、`sub_question_logic`、5项自检清单 |
| **实际提取** | 以上大部分字段，含 fallback：JSON → Markdown sections → regex → 空 dict |
| **缺失处理** | stem 缺失有检查；**sub_questions 为空无检查**；slot_id 仅从标题正则提取，无 fallback |
| **⚠ GAP** | ① sub_questions 验证不强制非空 ② 硬编码 sub_q1~3，不支持可变数量 ③ given_conditions 解析不保证数组类型 |

### 2.2 OptionsAgent（仅 SC）

| 维度 | 详情 |
|------|------|
| **输入** | `sc_draft_result`（stem）、`question_design`（设计方案） |
| **Prompt 请求** | `option_A~D`、`distractor_intent_A~D`、`correct_answer`、`option_style_used` |
| **实际提取** | 全部提取，含 3 层 fallback：JSON → structured_output → regex |
| **缺失处理** | 部分结果会被返回（不报错）；下游 `structural_validate` 检查 4 选项 |
| **⚠ GAP** | ① 不验证选项互斥性 ② correct_answer 未提取时不报错 ③ distractor_intent 缺失无影响但影响题目质量 |

### 2.3 StemBlueprintGate

| 维度 | 详情 |
|------|------|
| **输入** | `stem`、`options`、`blueprint`、`question_design`、`experience_radar` |
| **Prompt 请求** | `status`(pass/needs_fix)、`severity`、`next_action`、`fix_target`、22 项检查、`evidence`、`code_verification`、`fix_detail` |
| **实际提取** | verdict 全字段 + checks 全字段 + evidence + fix_instruction |
| **缺失处理** | 空输出 → needs_fix+critical；缺 severity → 默认 critical；最健壮的 agent |
| **⚠ GAP** | ① actual_K1~K5 缺失无默认值 ② check 值不验证 pass/fail/warn |

### 2.4 FileCodeSolverAgent

| 维度 | 详情 |
|------|------|
| **输入** | `question_draft`（stem）、`options`（SC）、`sub_questions`（Comp）、`question_type`、`slot_id` |
| **Prompt 请求** | Python 代码块 + `# final_answer` JSON + 步骤打印 |
| **实际提取** | `CodeSolution`：code_files、outputs、computed_results、python_exec_count |
| **缺失处理** | 无代码 → 追加 NO_CODE prompt；执行错误 → 显示 stderr；超时 → FORCE_FINAL |
| **⚠ GAP** | ① 不验证计算正确性（信任执行结果）② `_has_process_output()` 关键词匹配脆弱 ③ RuntimeFileCodeSolver vs FileCodeSolverAgent 路径不一致 |

### 2.5 SolverVerifyAgent

| 维度 | 详情 |
|------|------|
| **输入** | `stem`、`options`、`question_design`、`solver_result`、`question_type`、`blueprint` |
| **Prompt 请求** | `status`、`next_action`、`fix_target`、13+ 检查字段、`trusted`、`computed_answer`、`evidence`、`fix_detail` |
| **实际提取** | 全字段 + fallback regex + 中文 section 名映射 |
| **缺失处理** | 空输出 → needs_fix + fix_target=solver；质量分硬编码 8/5 |
| **⚠ GAP** | ① 不验证计算正确性 ② quality 硬编码无依据 ③ computed_answer 不与 solver 交叉验证 |

### 2.6 FormatSC（SCSolutionFormatterAgent）

| 维度 | 详情 |
|------|------|
| **输入** | `sc_draft_result`、`sc_options_result`、`sc_solver_result` |
| **Prompt 请求** | `correct_answer`、`explanation`、`solution_steps`、`difficulty_self_assessment`、`trap_description`、`knowledge_points` |
| **实际提取** | 通过 parse_structured_output + JSON fallback |
| **缺失处理** | 解析失败返回空 dict，**无字段级验证** |
| **⚠ GAP** | ① explanation 不与 solver 结果交叉验证 ② correct_answer 不与 options 结果交叉验证 ③ 缺失字段无默认值 |

### 2.7 FormatComp（HybridSolutionFormatter）

| 维度 | 详情 |
|------|------|
| **输入** | `question_design`、`solver_result` |
| **Prompt 请求** | `answers`(JSON)、`total_score`、每题解答过程 |
| **实际提取** | try_parse_json_object + parse_md_sections + sub_answer_details |
| **缺失处理** | JSON 失败用 Markdown fallback；**无字段级验证** |
| **⚠ GAP** | ① answers 不与 solver computed_results 交叉验证 ② total_score 无验证 ③ **这是 answer 为空的根因之一**：format 不产出 answer → summary 没有 → consistency 报错 |

### 2.8 RubricAgent（HybridRubricWriter）

| 维度 | 详情 |
|------|------|
| **输入** | `question_design`、`formatted_solution`、`current_blueprint` |
| **Prompt 请求** | `point_1~N`（评分点）、总分、评分说明 |
| **实际提取** | 仅提取"评分点"和"评分说明"section |
| **缺失处理** | 无 section → 返回空 dict |
| **⚠ GAP** | ① 不验证分数与 sub_questions 对应 ② 不验证总分 = blueprint typical_score ③ 缺失返回空 dict 但不报错 |

### 2.9 FinalReviewAgent

| 维度 | 详情 |
|------|------|
| **输入** | `sc_draft_result`/`sc_design`、`sc_options_result`、`sc_solution_result`、`solver_result`、`is_sc`、`content_to_review`（可选覆盖） |
| **Prompt 请求** | `status`、`overall_quality`(1-10)、7 个质量维度（condition_utilization、numerical_consistency、logic_chain、sub_question_logic、option_quality、expression_quality）、`issues`、`fix_target`、`fix_detail` |
| **实际提取** | **仅提取**：status、overall_quality、issues、fix_target、fix_detail |
| **缺失处理** | 空输出 → needs_human_review；缺 quality → FieldExtractor 或默认 0；缺 fix_target → 从 issues 推断 |
| **⚠ GAP** | ① **7 个质量维度全部丢弃！** Prompt 请求但 parse_output 不提取。condition_utilization、numerical_consistency 等审查结果未传递给 FinalFixer ② issues 用全文 fallback 但可能丢失结构化信息 |

### 2.10 FinalFixerAgent

| 维度 | 详情 |
|------|------|
| **输入** | `sc_design`、`sc_options_result`、`sc_solution_result`、`solver_result`、`final_review_result`（issues + fix_instruction） |
| **Prompt 请求** | `status`、`fix_applied`、`fixed_stem`、`fixed_answer`、`fixed_options`、`fixed_sub_questions` |
| **实际提取** | 全字段 + 3 层 fallback：结构化 dict → 纯文本 by fix_target → 降级为 failed |
| **缺失处理** | 空 → failed；无 section → failed；status=ok 但无内容 → 降级 failed |
| **⚠ GAP** | ① **不接收 FinalReview 的 7 个质量维度**，只有 issues 文本和 fix_detail，无法做精准修复 ② 修复后无法触发重新验证（只 patch 字段就结束） |

### 2.11 SummaryAgent（QuestionSummaryAgent）

| 维度 | 详情 |
|------|------|
| **输入** | `sc_draft_result`/`sc_design`、`sc_options_result`、`sc_solution_result`、`solver_result`、`review`、`is_sc` |
| **Prompt 请求** | `final_stem`、`final_explanation`、`final_solution_steps`、`correct_answer`、`knowledge_tags`、`difficulty_summary`、`quality_notes` |
| **实际提取** | 仅提取 "summary" section |
| **缺失处理** | 无 summary section → 返回空 dict |
| **⚠ GAP** | ① 返回空 dict 不报错，导致 _assemble 没有摘要信息 ② 不验证各字段完整性 ③ 字段名与 _assemble 不一致（knowledge_tags vs knowledge_points） |

### 2.12 _assemble（最终组装）

| 维度 | 详情 |
|------|------|
| **输入** | design、options、code_solution、solution、rubric、summary |
| **输出** | SC：stem + option_A~D + correct_answer + explanation + ...；Comp：stem + sub_questions + answer + rubric + ... |
| **缺失处理** | 优先用 summary，fallback 到各 agent 输出；solver_confidence 有条件判断 |
| **⚠ GAP** | ① **不验证必要字段完整性**（stem 可能为空、answer 可能为空）② knowledge_tags/knowledge_points 命名不一致 ③ Comp 的 answer 来自 solution 但 solution 可能是空 dict |

---

## 3. 关键 GAP 汇总（按严重程度）

### 🔴 Critical（信息断裂，导致链路失败）

| # | Agent | 问题 | 影响 |
|---|-------|------|------|
| C1 | FinalReview → FinalFixer | **7 个质量维度全部丢失**：Prompt 请求 condition_utilization 等 7 个维度，parse_output 完全不提取 | FinalFixer 只拿到 issues 文本，无法做精准修复 |
| C2 | FormatComp | **answer 可能为空**：format 不产出 answer → summary 无 answer → consistency 报 critical → export blocked | 这是 Q43 pipeline 最终 export blocked 的直接原因 |
| C3 | FinalFixer → 无重验证 | 修复后直接进 Summary，**不触发 FinalReview 二次审查** | 修复质量无保障 |
| C4 | _assemble | **不验证必要字段**：stem/answer 为空时照常输出 | 最终题目可能缺少核心内容 |

### 🟡 High（信息丢失，影响质量）

| # | Agent | 问题 | 影响 |
|---|-------|------|------|
| H1 | Design | sub_questions 为空不报错 | 下游全部崩溃 |
| H2 | Summary | 返回空 dict 不报错 | _assemble 没有摘要，直接用原始 agent 输出 |
| H3 | Solver ↔ Verify | computed_answer 不与 solver 交叉验证 | 计算错误无法发现 |
| H4 | Options | correct_answer 缺失不报错 | SC 题目无正确答案 |
| H5 | Rubric | 不验证总分 = blueprint typical_score | 分值不符 |

### 🟢 Medium（健壮性问题）

| # | Agent | 问题 |
|---|-------|------|
| M1 | Design | 硬编码 sub_q1~3，不支持可变数量 |
| M2 | Gate | actual_K1~K5 缺失无默认值 |
| M3 | Solver | _has_process_output() 关键词匹配脆弱 |
| M4 | Summary → Assemble | knowledge_tags vs knowledge_points 命名不一致 |

---

## 4. 修复建议（按优先级）

### P0: 补全 FinalReview → FinalFixer 信息传递
- FinalReview.parse_output 提取全部 7 个质量维度
- FinalFixer.build_input 接收这些维度，写入 prompt
- FinalFixer 修复后触发 FinalReview 二次审查（最多 1 轮）

### P1: _assemble 必要字段验证
- 组装前检查 stem 非空、answer 非空（Comp）/ correct_answer 非空（SC）
- 缺少必要字段 → status=blocked，不 export

### P1: FormatComp answer 产出保障
- format 完成后检查 answer 字段非空
- 为空 → 用 solver computed_results 作为 fallback answer

### P2: Summary 空结果处理
- 返回空 dict 时 log warning
- _assemble 检测空 summary 并用原始数据 fallback

### P2: Design sub_questions 验证
- parse_output 中检查 sub_questions 非空
- 为空 → 触发重试或标记 needs_fix

### P3: 字段命名统一
- 统一 knowledge_tags/knowledge_points
- 统一 answer/correct_answer 在 Comp 题中的命名
