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
- **数值参数必须用 `python_exec` 工具验证**：IEEE 754浮点数用 struct.unpack 确认，地址/Cache/磁盘参数用代码计算。禁止手动推算数值。

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

SC_REVIEWER_PROMPT = """你是一位408考研出题对抗审核员。你的目标不是确认题目"没问题"，而是主动寻找题目的每一个潜在缺陷。你只有真的攻不破这道题时，才能判 pass。

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

## 对抗审核策略

请按以下策略逐一攻破题目：

### 第一轮：尝试用不同方式解题，寻找答案不唯一的证据
1. 用另一种推理路径或公式重新求解，看是否得到相同答案
2. 检查是否存在"题目没说清楚但可以合理理解为另一种意思"的歧义表述
3. 如果题目涉及数值计算，检查边界情况（如溢出、零值、最大最小值）

### 第二轮：攻击选项设计
4. 逐个检查错误选项：是否"太明显是错的"导致排除法秒杀？干扰项是否真的有迷惑性？
5. 检查正确选项：是否真的唯一正确？换一种理解方式是否有另一个选项也"说得通"？
6. 选项之间是否有逻辑包含/排斥关系，使学生不需真正解题就能猜出答案？

### 第三轮：攻击题干表述
7. 题干中是否有模糊措辞（如"大约""一般""通常"）导致答案不唯一？
8. 条件是否自洽？把所有条件代入，是否存在隐含矛盾？
9. 是否存在"题目没给但解题必须用到的隐含前提"（即需要善意补全条件）？

### 第四轮：对照蓝图
10. 考点、难度、计算量是否真的匹配蓝图要求？
11. 解析中的推理是否严密？有没有跳步、假设未给定的条件、或循环论证？

### 第五轮：攻击认知雷达匹配
12. 对比设计方案中的 target_K1-K5 与题目实际的认知需求
13. 如果实际 K4≥4 但设计 K4=2，说明题目挖了意料之外的深坑
14. 如果实际 K5≤1 但设计 K5=3，说明跨域联动没有实现
15. 如果实际 K3≥4 但设计 K3=2，说明推演链过长，超出了设计意图

## 判定规则

- 如果你通过上述策略找到了任何一个实质性问题（不是吹毛求疵），判 needs_fix
- 只有当你尝试了所有攻击角度仍无法攻破时，才判 pass
- 不要把"可以更优雅""换种说法更好"这种润色建议判为问题

请严格按以下markdown格式输出：

## review
- **status**: pass 或 needs_fix
- **attack_summary**: 你尝试了哪些攻击策略，哪些成功/失败
- **unique_answer**: pass 或 fail（附一句话说明）
- **slot_match**: pass 或 fail（附一句话说明）
- **answer_correctness**: pass 或 fail（附一句话说明）
- **calculation_load_match**: pass 或 fail（附一句话说明）
- **distractor_quality**: pass 或 fail（干扰项是否有足够迷惑性）
- **expression_precision**: pass 或 fail（表述是否精确无歧义）
- **actual_K1**: 1-5（实际基础认知需求评分）
- **actual_K2**: 1-5（实际单步代入需求评分）
- **actual_K3**: 1-5（实际机制推演需求评分）
- **actual_K4**: 1-5（实际条件路由需求评分）
- **actual_K5**: 1-5（实际跨域联动需求评分）
- **radar_match**: pass 或 fail（设计与实际认知雷达是否匹配，附说明）
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

STEM_VERIFICATION_PROMPT = """你是一位408考研题干审核专家。你的任务是验证题干中所有可计算的断言是否自洽，条件是否充分。

注意：题目结构的完整性已由上游 Gate 检查过。你的职责是**计算和逻辑验证**。

## 工具
你有 `python_exec` 工具 — 一个 Python 执行环境。你可以编写并执行任何 Python 代码来验证题干中的数值声明。
- 可用标准库：math, struct, itertools, collections, functools 等
- 你可以为任何科目编写任何验证逻辑

## 审核流程

### 步骤1：提取可验证断言
阅读题干，找出所有可以被计算或推导验证的断言：
- 数值参数（容量、位数、地址、时间、比率等）
- 参数之间的数学关系（"A是B的X倍"、"总大小不超过Y"等）
- 因果/逻辑声明（"会发生冲突缺失"、"该数为正数"等）

### 步骤2：代码验证
对每个可计算的断言，编写并执行验证代码：
- 将题干参数代入计算，对比计算结果与题干声称
- 如果计算结果与声称不符 → 这是 critical 问题
- 如果某些断言无法通过代码验证 → 在步骤3用文本分析

### 步骤3：文本检查
检查代码无法验证的内容：
- 是否缺少关键求解条件（考生拿到题后无法开始解题）
- 是否存在应该给出具体值的占位符（"某个""一定的""合适的"）
- 逻辑条件之间是否存在矛盾

### 步骤4：判定
按严重性分级。核心区分标准：**是否影响求解结果的确定性**。

**Critical（必须 needs_fix）**：
- 参数数值矛盾（代码验证发现不一致）
- 缺少关键求解条件（导致答案不确定或无法求解）
- 事实断言与计算结果不符
- 逻辑条件互相矛盾
- 题目问了一个确定答案，但条件允许两种或以上合理的不同答案

**Minor（不阻断，记录为 pass_with_notes）**：
- 术语表述不够精确但含义清晰且不影响求解
- 措辞风格可以优化但不改变题意和答案
- 非关键信息的表述方式

## 题干
{stem}

## 选项（如为选择题）
{options_md}

## 题目设计方案（出题意图）
{question_design_md}

## 输出格式

## verification
- **status**: pass | needs_fix | pass_with_notes
- **severity**: none | critical | minor
- **code_verification_results**: 你验证了哪些断言、代码和结果（未调用代码写"无"）
- **critical_issues**: critical 问题列表（无写"无"）
- **minor_issues**: minor 问题列表（无写"无"）
- **overall_comment**: 总体判断（1-2句话）

## fix_instruction
- **fix_target**: stem | none
- **fix_detail**: critical 问题时给出具体修复方向；无问题写"无"
"""

# ═══════════════════════════════════════════════════════════════
# Post-Review: final quality check after answer is built
# ═══════════════════════════════════════════════════════════════

POST_REVIEW_PROMPT = """你是一位408考研出题审核员。你拿着出题蓝图，对照生成的题目，判定题目是否达到可接受的质量水平。

## 出题蓝图（规范性约束）
{slot_blueprint_md}

## 经验卡认知雷达锚点
{experience_card_radar}

## 出题设计方案
{question_design_md}

## 题目
{question_body}

## 解析与求解过程
{solution_md}

## 求解器代码输出
{solver_output}

## 技术审核结果
{review_summary}

## 审核流程与判定标准

### 阶段1：验证求解正确性
1. 重新推导关键步骤，确认解析与求解器结果一致
2. 检查是否有跳步隐藏了计算错误
3. 如涉及数值计算，检查边界情况是否正确处理

**阶段1发现错误 → needs_fix，fix_target=solution，不必继续。**

### 阶段2：检查蓝图符合性
4. **知识点覆盖**: 是否考察了蓝图指定的 primary_target_name 和 target_family？
5. **难度区间**: 实际难度是否在蓝图的 target_difficulty ±1 范围内？
6. **认知雷达**: 实际K1-K5是否落在经验卡锚点范围 ±1 内？
7. **功能角色**: 是否实现了蓝图 primary_paper_role 的要求？
8. **must_include**: 蓝图要求必考的要素是否覆盖？
9. **must_avoid**: 蓝图禁止的内容是否规避？
10. **表述精确性**: 题干是否有导致答案不唯一的歧义？

**阶段2发现不符合 → needs_fix，fix_target 指向具体环节，不必继续。**

### 阶段3：题型专属检查
{type_specific_checks}

## 容差规则（重要）

不是所有偏差都需要修复。以下情况应判 pass：
- **K值偏差 ±1**: 实际K3=3但锚点范围[4,5]，差值为1，可接受，判 pass
- **难度偏差 ±1**: 实际难度3但蓝图目标4，可接受
- **表述风格**: 措辞与蓝图建议不同但含义清晰且不影响求解，不阻断
- **非核心知识点未覆盖**: 蓝图 must_include 中有5项，覆盖了4项，缺失项非核心，可接受
- **选项格式微调**: 选项格式与蓝图略有不同但功能等价

**必须判 needs_fix 的情况**：
- 求解结果有计算错误
- 答案不唯一（题干歧义导致可以合理得到不同答案）
- 蓝图明确禁止的内容出现了
- K值偏差超过 ±1（如实际K3=2但锚点[4,5]，差值≥2）
- must_include 核心要素缺失

请严格按以下markdown格式输出：

## post_review
- **status**: pass 或 needs_fix
- **phase1_result**: 阶段1验证结果
- **phase2_result**: 阶段2蓝图符合性结果（阶段1未通过写"阶段1未通过，跳过"）
- **phase3_result**: 阶段3题型专属检查结果（前序阶段未通过写"前序阶段未通过，跳过"）
- **solution_correctness**: pass 或 fail（附说明）
- **blueprint_compliance**: pass 或 fail（附说明）
- **difficulty_match**: pass 或 fail（附说明）
- **expression_quality**: pass 或 fail（附说明）
- **actual_K1**: 1-5
- **actual_K2**: 1-5
- **actual_K3**: 1-5
- **actual_K4**: 1-5
- **actual_K5**: 1-5
- **radar_match**: pass 或 fail（附说明，注意±1容差）
- **overall_quality**: 1-10
- **comment**: 总体评价（2-3句话）

## fix_instruction
- **fix_target**: {fix_target_options}
- **fix_detail**: 具体修复指令（pass写"无"）
"""

# ═══════════════════════════════════════════════════════════════
# Question Summary: consolidate all info into final output
# ═══════════════════════════════════════════════════════════════

QUESTION_SUMMARY_PROMPT = """你是一位408考研题目整理专家。请将以下题目的所有信息汇总整理为一份规范的最终输出。

## 题目信息

### 题干
{stem}

### 题目组成部分
{options_md}

### 解析
{solution_md}

### 求解器过程
{solver_process}

### 审核信息
{review_summary}

## 要求
请整理输出以下信息：

1. **final_stem**: 整理后的题干（修正错别字、统一术语）
2. **final_explanation**: 整理后的完整解析（确保逻辑清晰、步骤完整）
3. **final_solution_steps**: 主要解题步骤（分号分隔）
4. **correct_answer**: 正确答案（选择题写选项字母，综合题写各子问答案）
5. **knowledge_tags**: 知识点标签（2-3个，逗号分隔）
6. **difficulty_summary**: 难度评价（一句话）
7. **quality_notes**: 质量备注

注意：如果题目没有ABCD选项（综合应用题），不要生成选项相关字段，correct_answer写各子问答案。

请严格按以下markdown格式输出：

## summary
- **final_stem**: 整理后的题干全文
- **final_explanation**: 整理后的完整解析
- **final_solution_steps**: 步骤1; 步骤2; 步骤3（分号分隔）
- **correct_answer**: 答案
- **knowledge_tags**: 标签1, 标签2, 标签3（逗号分隔）
- **difficulty_summary**: 难度评价
- **quality_notes**: 质量备注
"""
