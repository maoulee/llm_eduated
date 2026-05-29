"""Prompts for the single-choice question pipeline.

Agents:
  SC_DRAFT_PROMPT            — SlotBlueprint + experience card -> question stem
  SC_OPTIONS_PROMPT          — Stem -> 4 options with distractor intent
  SC_SOLUTION_FORMATTER_PROMPT — Solver result + stem + options -> formatted solution
  SC_REVIEWER_PROMPT         — Full question + solution + blueprint -> review
"""

# ═══════════════════════════════════════════════════════════════
# Draft: stem only
# ═══════════════════════════════════════════════════════════════

SC_DRAFT_PROMPT = """你是一位408考研出题专家。请根据以下题目设计方案，**仅生成题干（stem）**。不要生成选项，不要给出答案。

## 题目设计方案
{question_design_md}

## 约束
- 题干必须严格匹配设计方案中的考察维度、难度设定和题干设计要求
- 题目必须完全原创
- 题干应引导设计方案中指定的推理路径

请严格按以下markdown格式输出：

## stem
- **stem**: 题干全文（包含所有条件和问题）
- **reasoning_hint**: 预期解题路径提示（一句话）
"""

# ═══════════════════════════════════════════════════════════════
# Options: 4 options + distractor intent
# ═══════════════════════════════════════════════════════════════

SC_OPTIONS_PROMPT = """你是一位408考研出题专家。请根据以下题干和设计方案，生成4个选项（A/B/C/D），其中恰好有1个正确答案。

## 题干
{stem}

## 题目设计方案
{question_design_md}

## 约束
- 按设计方案中选项策略部分的option_style决定选项格式
- 每个干扰项严格按照设计方案中的干扰项策略设计
- 每个干扰项必须有明确的"为什么有人会选错"的理由
- 4个选项不能有歧义，正确答案必须唯一

请严格按以下markdown格式输出：

## options
- **option_A**: 选项A内容
- **option_B**: 选项B内容
- **option_C**: 选项C内容
- **option_D**: 选项D内容

## distractors
- **distractor_intent_A**: 错误选项A的设计意图（为什么有人会误选）
- **distractor_intent_B**: 错误选项B的设计意图（为什么有人会误选）
- **distractor_intent_C**: 错误选项C的设计意图（为什么有人会误选）
- **distractor_intent_D**: 如果D是正确选项则写"正确选项"，否则写误选原因

## answer
- **correct_answer**: 正确选项字母（A/B/C/D）
- **option_style_used**: 数字结果 或 概念判断 或 代码分析
"""

# ═══════════════════════════════════════════════════════════════
# Solution formatter: clean explanation from solver result
# ═══════════════════════════════════════════════════════════════

SC_SOLUTION_FORMATTER_PROMPT = """你是一位408考研解析编写专家。请根据以下题目和求解器结果，编写一份清晰规范的解析。**不要重新求解，只整理和格式化已有结果。**

## 题目
{stem}

## 选项
{options_md}

## 求解器结果
{solver_result_json}

## 约束
- 解析必须基于求解器的计算结果，不得自行推导矛盾结论
- 如果求解器结果明确指出正确答案，以此为准
- solution_steps应分步清晰，每步一句话
- explanation应先给出结论，再展开分析
- 语言简洁规范，符合考研真题解析风格
- **严禁**在explanation中出现自我修正、犹豫、反复推演（如"等等"、"不对"、"让我们重新审视"、"如果我们将"等表述）
- explanation必须是干净的最终定稿，不得暴露思考过程

请严格按以下markdown格式输出：

## solution
- **correct_answer**: 正确选项字母
- **explanation**: 完整解析（先结论后分析）
- **solution_steps**: 步骤1; 步骤2; 步骤3（分号分隔）
- **difficulty_self_assessment**: 1-5自评难度
- **trap_description**: 本题陷阱设计说明
- **knowledge_points**: 知识点1, 知识点2（逗号分隔）
"""

# ═══════════════════════════════════════════════════════════════
# Reviewer: review complete question
# ═══════════════════════════════════════════════════════════════

SC_REVIEWER_PROMPT = """你是一位408考研出题审核专家。请审核以下完整的单选题，检查其质量。

## 题目
- **题干**: {stem}
- **选项A**: {option_A}
- **选项B**: {option_B}
- **选项C**: {option_C}
- **选项D**: {option_D}

## 解析
{solution_md}

## 出题蓝图（用于对照）
{slot_blueprint_json}

## 审核检查项

请逐一检查以下维度：

1. **unique_answer**: 是否有且仅有1个正确答案，无歧义
2. **slot_match**: 考点、难度、风格是否匹配蓝图要求
3. **answer_correctness**: 答案和解析是否正确、计算是否准确
4. **calculation_load_match**: 实际计算量是否匹配蓝图的calculation_load

请严格按以下markdown格式输出：

## review
- **status**: pass 或 needs_fix
- **unique_answer**: pass 或 fail（附一句话说明）
- **slot_match**: pass 或 fail（附一句话说明）
- **answer_correctness**: pass 或 fail（附一句话说明）
- **calculation_load_match**: pass 或 fail（附一句话说明）
- **overall_quality**: 1-10质量评分
- **comment**: 总体评价（2-3句话）

## fix_instruction
（如果status为needs_fix，说明哪个环节需要修正及具体指令；pass则写"无"）
- **fix_target**: draft 或 options 或 solution 或 none
- **fix_detail**: 具体修复指令（pass写"无"）
"""

# ═══════════════════════════════════════════════════════════════
# Stem Verification: pre-solve consistency check
# ═══════════════════════════════════════════════════════════════

STEM_VERIFICATION_PROMPT = """你是一位408考研出题审核专家。你的任务是在**解题之前**审查题干（stem），检查题干本身是否存在问题。你**不需要解题**，只需要审查题干的结构和内容是否合理。

## 题干
{stem}

## 选项（如为选择题）
{options_md}

## 题目设计方案（出题意图）
{question_design_md}

## 审查维度

请逐一检查以下维度，**注意：你不需要计算或求解，只需判断条件是否自洽**：

1. **参数一致性**: 题干中给出的所有数值参数是否彼此兼容？
   - 例如：如果提到"4KB页面"和"32位地址"，那么页表项数应该合理
   - 例如：如果提到"容量为128MB"和"按字节编址"，地址位数应该匹配
   - 数值之间不能有隐含的矛盾

2. **术语准确性**: 题干中的专业术语、缩写、概念名称是否准确？
   - 例如：不应将"虚拟地址"写成"虚地址空间"
   - 例如：IEEE 754相关的字段名（符号位、阶码、尾数）是否正确
   - 变量名和概念名必须符合408考试标准表述

3. **条件充分性**: 题干给出的条件是否足以确定唯一答案？
   - 不能缺少关键条件（如要求计算结果但未给出必要参数）
   - 条件不能有多余的歧义（如"大约"、"左右"等模糊表述）

4. **条件自洽性**: 题干中任意两个条件之间是否矛盾？
   - 不能同时要求互斥的条件
   - 隐含的逻辑推导不应产生矛盾

5. **信息指向性**: 题干的条件是否清晰地指向需要求解的问题？
   - 条件和问题之间应有明确的逻辑链
   - 不应包含与问题无关的干扰信息（除非是故意设计的陷阱条件）

请严格按以下markdown格式输出：

## verification
- **status**: pass 或 needs_fix
- **parameter_consistency**: pass 或 fail（附说明）
- **naming_accuracy**: pass 或 fail（附说明）
- **condition_completeness**: pass 或 fail（附说明）
- **condition_sufficiency**: pass 或 fail（附说明）
- **no_self_contradiction**: pass 或 fail（附说明）
- **information_direction**: pass 或 fail（附说明）
- **overall_comment**: 总体判断（1-2句话）

## fix_instruction
（如果status为needs_fix，说明问题所在及修复方向；pass则写"无"）
- **fix_target**: stem 或 none
- **fix_detail**: 具体问题描述和修复建议（pass写"无"）
- **contradiction_detail**: 如有矛盾，列出具体是哪些条件之间存在矛盾（无矛盾写"无"）
"""

# ═══════════════════════════════════════════════════════════════
# Post-Review: final quality check after answer is built
# ═══════════════════════════════════════════════════════════════

POST_REVIEW_PROMPT = """你是一位408考研出题终审专家。请分两个阶段审核这道题目：

**阶段1：求解正确性验证** — 先确认答案和解析是否正确
**阶段2：设计意图匹配** — 再确认题目是否达到设计目标

## 出题设计方案（出题意图）
{question_design_md}

## 题目
- **题干**: {stem}
- **选项A**: {option_A}
- **选项B**: {option_B}
- **选项C**: {option_C}
- **选项D**: {option_D}

## 解析与求解过程
{solution_md}

## 求解器代码输出
{solver_output}

## 技术审核结果
{review_summary}

## 审核要求

### 阶段1：求解正确性（优先检查）
请验证求解器的计算过程和结论是否正确：
1. **代码逻辑**: 求解器代码的计算步骤是否正确？有没有逻辑错误、公式用错、变量搞混？
2. **结果合理性**: 计算结果是否合理？是否符合该类问题的已知范围？
3. **答案唯一性**: 是否有且仅有1个正确选项？

**如果阶段1发现问题，直接标记 needs_fix，fix_target=solution，不必继续阶段2。**

### 阶段2：设计意图匹配（阶段1通过后检查）
4. **考察维度匹配**: 题目是否实现了设计方案中指定的考察维度？
5. **难度匹配**: 实际难度是否与设计方案一致？
6. **表述规范**: 题干和选项的表述是否清晰、规范、无错别字？

请严格按以下markdown格式输出：

## post_review
- **status**: pass 或 needs_fix
- **solution_correctness**: pass 或 fail（附说明）
- **code_logic**: pass 或 fail（附说明）
- **result_reasonability**: pass 或 fail（附说明）
- **design_intent_match**: pass 或 fail（附说明）
- **difficulty_match**: pass 或 fail（附说明）
- **expression_quality**: pass 或 fail（附说明）
- **overall_quality**: 1-10
- **comment**: 总体评价（2-3句话）

## fix_instruction
- **fix_target**: solution 或 stem 或 options 或 none
- **fix_detail**: 具体修复指令（pass写"无"）。如果求解错误，说明错在哪里以及应该如何修正。
"""

# ═══════════════════════════════════════════════════════════════
# Question Summary: consolidate all info into final output
# ═══════════════════════════════════════════════════════════════

QUESTION_SUMMARY_PROMPT = """你是一位408考研题目整理专家。请将以下题目的所有信息汇总整理为一份规范的最终输出。

## 题目信息

### 题干
{stem}

### 选项
- A: {option_A}
- B: {option_B}
- C: {option_C}
- D: {option_D}

### 解析
{solution_md}

### 求解器过程
{solver_process}

### 审核信息
{review_summary}

## 要求
请整理输出以下信息：

1. **final_stem**: 整理后的题干（修正错别字、统一术语）
2. **final_options**: 整理后的选项（统一格式）
3. **final_solution**: 整理后的解析（确保逻辑清晰、步骤完整）
4. **knowledge_tags**: 知识点标签（2-3个）
5. **difficulty_summary**: 难度评价（一句话）
6. **quality_notes**: 质量备注（如有什么需要注意的地方）

请严格按以下markdown格式输出：

## summary
- **final_stem**: 整理后的题干全文
- **final_option_A**: 整理后的选项A
- **final_option_B**: 整理后的选项B
- **final_option_C**: 整理后的选项C
- **final_option_D**: 整理后的选项D
- **final_explanation**: 整理后的完整解析
- **final_solution_steps**: 步骤1; 步骤2; 步骤3（分号分隔）
- **correct_answer**: 正确选项字母
- **knowledge_tags**: 标签1, 标签2, 标签3（逗号分隔）
- **difficulty_summary**: 难度评价
- **quality_notes**: 质量备注
"""
