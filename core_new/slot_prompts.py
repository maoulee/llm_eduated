# core_new/slot_prompts.py
"""Prompts for slot-template driven extraction, composition, and generation.

Extraction:
  SLOT_BATCH_ANALYSIS_PROMPT — per-slot observation + template extraction

Composition:
  PAPER_COMPOSER_PROMPT — generates PaperBlueprint from SlotTemplates
  BLUEPRINT_REVIEWER_PROMPT — reviews blueprint before sending to writers

Generation:
  SLOT_QUESTION_WRITER — generates question from SlotBlueprint + experience card
  QUESTION_FIXER_PROMPT — fixes specific issues in questions

Review:
  PAPER_REVIEWER_PROMPT — whole-paper review with issue categorization
"""

SLOT_BATCH_ANALYSIS_PROMPT = """你是一位408考研教研专家，专精于试卷结构和题位分析。

以下是2009-2023年408考研真题中**第{slot_num}题**（共{count}道）的完整数据。
请完成以下三重分析任务。

---

## 真题数据

{questions_data}

---

## 任务1：逐题 SlotObservation

对每道题，提取以下信息。请用XML标签包裹每道题的分析结果。

对每道题输出如下格式：
```xml
<obs year="20XX">
  <primary_target_type>knowledge 或 mechanism 或 pattern</primary_target_type>
  <primary_target_name>具体考点名称</primary_target_name>
  <target_family>所属知识领域（如：Cache映射与性能计算、指令系统设计、数据表示与运算）</target_family>
  <supporting_targets>辅助考点，分号分隔</supporting_targets>
  <prerequisite_targets>前置知识，分号分隔</prerequisite_targets>
  <target_depth>knowledge 或 mechanism 或 pattern</target_depth>
  <difficulty_overall>1-5整数</difficulty_overall>
  <difficulty_knowledge_depth>1-5整数</difficulty_knowledge_depth>
  <difficulty_mechanism_depth>1-5整数</difficulty_mechanism_depth>
  <difficulty_reasoning_steps>1-5整数</difficulty_reasoning_steps>
  <difficulty_calculation_load>1-5整数</difficulty_calculation_load>
  <difficulty_trap_strength>1-5整数</difficulty_trap_strength>
  <difficulty_cross_topic>0-3整数，0=单知识点，3=跨多个章节</difficulty_cross_topic>
  <difficulty_reason>一句话说明难度判定理由</difficulty_reason>
  <paper_role>以下枚举之一：foundation_check(基础覆盖)、mechanism_trigger(机制触发)、pattern_execution(推理模式执行)、trap_diagnosis(易错陷阱诊断)、calculation_stability(计算稳定性)、cross_topic_integration(综合整合)、difficulty_separator(区分度题)</paper_role>
  <paper_role_reason>一句话说明为什么是这个角色</paper_role_reason>
  <why_correct>标准答案为什么成立</why_correct>
  <why_wrong_options>各错误选项为什么错，用JSON对象格式如 {{"A":"理由","B":"理由"}}</why_wrong_options>
  <solution_steps>解题步骤，分号分隔</solution_steps>
  <distractor_patterns>干扰项设计模式，JSON数组格式</distractor_patterns>
  <stem_length>short 或 medium 或 long</stem_length>
  <condition_count>条件数量，整数</condition_count>
  <option_style>数字结果 或 概念判断 或 代码分析 或 混合</option_style>
  <reasoning_shape>one_formula 或 multi_step 或 elimination 或 simulation</reasoning_shape>
  <trap_style>陷阱类型描述</trap_style>
</obs>
```

---

## 任务2：题位模板 SlotTemplate

分析第{slot_num}题这个位置**跨年份的稳定模式**，输出：

```xml
<slot_template>
  <slot_id>Q{slot_num}</slot_id>
  <section>选择题 或 综合应用题</section>
  <question_type>single_choice 或 comprehensive</question_type>
  <typical_score>该题位通常分值</typical_score>
  <subject_stability>这个题位科目是否稳定，稳定则写科目名，不稳定则写"跨科目"</subject_stability>
  <subject_distribution>各科目出现频率，JSON格式如 {{"计算机组成原理":0.9,"操作系统":0.1}}</subject_distribution>
  <target_family_distribution>出现频率最高的3-5个知识领域，JSON格式</target_family_distribution>
  <target_depth_distribution>knowledge/mechanism/pattern各出现频率</target_depth_distribution>
  <paper_role_distribution>各角色出现频率，JSON格式</paper_role_distribution>
  <difficulty_anchor>各难度维度的众数和范围，JSON格式如 {{"overall_mode":2,"overall_range":[1,3],...}}</difficulty_anchor>
  <style_mode>最常见的风格组合，JSON格式</style_mode>
  <slot_guidance>这个题位的出题指导，2-3句话描述应该出什么类型的题</slot_guidance>
  <should_be>这个题位应该是什么样的题（一句话）</should_be>
  <should_not_be>这个题位不应该是什么样的题（逗号分隔多个）</should_not_be>
  <generation_style>生成风格建议（一句话）</generation_style>
  <stability_assessment>这个题位跨年份的稳定程度评价（一句话）</stability_assessment>
</slot_template>
```

---

## 任务3：TypeDifficultyGuide

基于该题位的典型模式，给出出题类型-难度指导：

```xml
<type_difficulty_guide>
  <guide_id>基于科目+深度+难度命名，如 CO_knowledge_level2_single_choice</guide_id>
  <subject>科目</subject>
  <target_depth>knowledge 或 mechanism 或 pattern</target_depth>
  <difficulty>典型难度等级</difficulty>
  <paper_role>典型功能角色</paper_role>
  <expected_shape>该类型题目的预期形态，JSON格式，包含reasoning_steps、stem_length、condition_count、calculation_load、trap_strength、option_style</expected_shape>
  <suitable_targets>适合的知识点列表，JSON数组</suitable_targets>
  <distractor_style>干扰项设计风格，JSON数组</distractor_style>
  <bad_examples>不应该出现的特征，JSON数组</bad_examples>
</type_difficulty_guide>
```

---

请严格按照上述XML格式输出，确保每个标签都有内容。不要输出XML标签以外的额外解释。"""

# ═══════════════════════════════════════════════════════════════
# Composition prompts (markdown output)
# ═══════════════════════════════════════════════════════════════

PAPER_COMPOSER_PROMPT = """你是一位408考研组卷专家。你的任务是基于题位契约(SlotContract)规划一套完整的模拟试卷。

## 用户需求
{user_requirements}

## 各题位契约
{slot_contracts_md}

## 规划原则

你的规划必须在题位契约框架内进行：
- **硬约束**：必须绝对遵守，违反即为错误（题型、分值、选项数、答案唯一性、输出格式）
- **强软约束**：默认遵守，如果偏离必须写出偏离理由（难度范围、计算量、推理步数）
- **偏好约束**：尽量满足，不强制（知识领域、paper_role、风格）
- **偏离策略**：允许偏离，但每个偏离都需要说明；重大偏离需要后续审核确认

计算难度定义：
- calculation_load=0: 无计算，纯概念判断
- calculation_load=1: 一步代入、简单比较
- calculation_load=2: 两步以内公式计算、简单单位换算
- calculation_load=3: 三到四步计算，需要中间量
- calculation_load=4: 完整过程模拟（CRC、页面置换、Cache多轮推演）
- calculation_load=5: 跨机制复杂计算

## 关键约束

1. **题型字段区分（硬约束！）**：
   - single_choice题位：option_style为数字结果/概念判断/代码分析，同时输出reasoning_shape、stem_length、condition_count、distractor_strategy
   - comprehensive题位：option_style必须为none，reasoning_shape必须为none，不输出stem_length、condition_count、distractor_strategy，改为输出sub_questions和answer_format
   - 违反此规则视为硬违规

2. **考点复杂度**：primary_target_name应是单个明确考点，避免"A与B综合应用"。辅助考点放在must_include中。

3. **难度不超标**：target_difficulty必须在该题位契约的difficulty_reasonable_range范围内。

4. **题型匹配**：option_style和reasoning_shape必须从经验卡的历年真题模式中选择。

5. **计算难度匹配**：
   - option_style=概念判断时，calculation_load应≤1
   - reasoning_shape=one_formula时，推理步数应≤2

6. **整卷预算一致性**：primary_role_distribution各项之和必须等于total_questions；difficulty_distribution各项之和必须等于total_questions；calculation_load_distribution各项之和必须等于total_questions。

请严格按以下markdown格式输出：

# paper_blueprint

## 整体
- **paper_type**: 408模拟卷
- **total_questions**: {total_slots}
- **difficulty_target**: 整体难度目标（1-5整数）
- **difficulty_distribution**: {{"level_1": 数量, "level_2": 数量, "level_3": 数量, "level_4": 数量, "level_5": 数量}}
- **primary_role_distribution**: {{"foundation_check": 数量, "mechanism_trigger": 数量, "pattern_execution": 数量, "trap_diagnosis": 数量, "calculation_stability": 数量, "cross_topic_integration": 数量, "difficulty_separator": 数量}}（各值之和必须等于total_questions）
- **composition_rationale**: 整卷组卷思路说明（2-3句话）

## 难度预算
- **calculation_load_distribution**: {{"load_0": 数量, "load_1": 数量, "load_2": 数量, "load_3": 数量, "load_4": 数量, "load_5": 数量}}
- **reasoning_steps_distribution**: {{"steps_1": 数量, "steps_2": 数量, "steps_3": 数量, "steps_4": 数量, "steps_5": 数量}}
- **difficulty_curve_strategy**: 前中后段难度策略描述（一句话，如"前段基础稳定，中段机制触发，后段适度区分"）

## Q12（选择题示例）
- **target_subject**: 科目
- **target_family**: 知识领域
- **primary_target_name**: 具体考点（单个明确考点，不要"A与B综合应用"）
- **target_depth**: knowledge 或 mechanism 或 pattern
- **primary_paper_role**: 主功能角色（单个，从foundation_check/mechanism_trigger/pattern_execution/trap_diagnosis/calculation_stability/cross_topic_integration/difficulty_separator中选择）
- **secondary_paper_roles**: 辅助功能标签（逗号分隔，可为空）
- **target_difficulty**: 目标难度1-5
- **difficulty_profile**: {{"knowledge_depth": N, "mechanism_depth": N, "reasoning_steps": N, "calculation_load": N, "trap_strength": N, "cross_topic": N}}
- **option_style**: 数字结果 或 概念判断 或 代码分析
- **reasoning_shape**: one_formula 或 multi_step 或 elimination 或 simulation
- **stem_length**: short 或 medium 或 long
- **condition_count**: 条件数量（整数）
- **distractor_strategy**: 干扰项设计策略
- **must_include**: 要素1, 要素2
- **must_avoid**: 避免项1, 避免项2
- **reference_experience**: 参考哪几年的真题经验
- **has_deviation**: yes 或 no
- **deviation_level**: none 或 minor 或 major
- **deviation_reason**: 偏离理由（无偏离写"无"）

## Q43（综合应用题示例）
- **target_subject**: 科目
- **target_family**: 知识领域
- **primary_target_name**: 具体考点
- **target_depth**: knowledge 或 mechanism 或 pattern
- **primary_paper_role**: 主功能角色（单个）
- **secondary_paper_roles**: 辅助功能标签（逗号分隔，可为空）
- **target_difficulty**: 目标难度1-5
- **difficulty_profile**: {{"knowledge_depth": N, "mechanism_depth": N, "reasoning_steps": N, "calculation_load": N, "trap_strength": N, "cross_topic": N}}
- **option_style**: none
- **reasoning_shape**: none
- **sub_questions**: 子问题数量（整数）
- **answer_format**: 解答过程+最终结果
- **must_include**: 要素1, 要素2
- **must_avoid**: 避免项1, 避免项2
- **reference_experience**: 参考哪几年的真题经验
- **has_deviation**: yes 或 no
- **deviation_level**: none 或 minor 或 major
- **deviation_reason**: 偏离理由（无偏离写"无"）

（每个题位一个 ## 标题的section，格式根据题型选择上面两种之一。注意：综合应用题option_style和reasoning_shape必须为none！）
"""

BLUEPRINT_REVIEWER_PROMPT = """你是一位408考研组卷审核专家。请审核以下组卷蓝图的质量，区分硬违规和软偏离。

## 用户需求
{user_requirements}

## 组卷蓝图
{paper_blueprint_json}

## 题位契约（用于对照）
{slot_contracts_md}

## 审核分类标准

对每个SlotBlueprint，按以下标准判定：

**hard_violation（硬违规，必须修复）**：
- 题型错误（如应该是single_choice却规划了综合题格式）
- 分值错误
- 多个正确答案或无法作答
- 输出格式缺失
- 综合应用题的option_style不为none（必须为none）

**soft_deviation（软偏离）**：
- major: 难度超出合理范围、计算量明显高于soft_max、primary_paper_role属于discouraged、考点属于should_not_be
- minor: 轻微偏离偏好约束但仍在合理范围内

**acceptable（可接受）**：
- 完全符合或仅有minor偏离且理由合理

## 审核要点

1. 硬约束是否全部满足（题型、分值、选项数）
2. 难度是否在合理范围内
3. 计算量是否匹配题型和难度
4. primary_paper_role是否合理
5. 整卷知识点是否覆盖均匀、无重叠
6. 难度曲线是否合理（前易后难）
7. 偏离理由是否合理（如果有偏离）
8. 整卷预算一致性：primary_role_distribution之和、difficulty_distribution之和、calculation_load_distribution之和是否都等于total_questions

请严格按以下markdown格式输出：

# blueprint_review

## 总体
- **status**: pass 或 revise
- **hard_violation_count**: 硬违规数量
- **major_deviation_count**: 重大偏离数量
- **minor_deviation_count**: 轻微偏离数量
- **comment**: 总体评价（2-3句话）

## Q12
- **status**: pass 或 revise
- **hard_violation**: yes 或 no
- **soft_deviation**: none 或 minor 或 major
- **deviation_fields**: 偏离的字段（无偏离写"无"）
- **issue**: 问题描述（无问题写"无"）
- **revision_instruction**: 修改建议（无写"无"）

（每个题位一个 ## 标题的section，格式同上）

## 全局问题
整卷层面的问题描述（无问题写"无"）
"""

# ═══════════════════════════════════════════════════════════════
# Generation prompts (markdown output)
# ═══════════════════════════════════════════════════════════════

SLOT_QUESTION_WRITER = """你是一位408考研出题专家。请严格按照以下SlotBlueprint生成一道完整的题目。

## 出题蓝图
{slot_blueprint_json}

## 经验卡参考
{experience_card_md}

## 参考真题（风格参考，请勿照抄）
{reference_questions}

## 出题格式要求（严格遵守蓝图）

- **option_style**决定选项格式：数字结果→选项必须是具体数值或表达式；概念判断→选项是命题判断或概念辨析
- **reasoning_shape**决定解题路径：one_formula→一步公式代入即可得答案；multi_step→需要分步推理；elimination→逐一排除错误选项
- **stem_length**决定题干长度：short≤50字，medium≤100字，long≤150字
- **condition_count**决定已知条件数量，不要多也不要少
- **distractor_strategy**指导每个错误选项的设计方向，确保每个干扰项都有明确的"为什么有人会选错"的理由

## 输出要求

请生成一道完全原创的题目，风格和难度匹配蓝图要求。

**严格禁止**：
- 不要在explanation中出现自我修正、犹豫、反复推演（如"等等"、"不对"、"让我们重新审视"、"如果我们将"等表述）
- explanation必须是最终定稿的规范解析，先给出结论再展开分析
- 严禁暴露思考过程，只输出干净的最终解析

严格按以下markdown格式输出：

# question {slot_id}

## 题目
- **stem**: 题干全文（包含所有条件和问题）
- **option_A**: 选项A内容
- **option_B**: 选项B内容
- **option_C**: 选项C内容
- **option_D**: 选项D内容

## 答案
- **correct_answer**: 正确选项字母
- **explanation**: 详细解析
- **solution_steps**: 步骤1; 步骤2; 步骤3
- **difficulty_self_assessment**: 1-5自评难度
- **trap_description**: 陷阱设计说明
- **knowledge_points**: 知识点1, 知识点2
"""

QUESTION_FIXER_PROMPT = """你是一位408考研出题专家。以下题目整体质量不错，但存在需要修正的具体问题。请只修复指出的错误，保持题干、考点、风格不变。

## 原始题目
{question_json}

## 需要修复的问题
{fix_instructions}

## 双重校验要求

如果修复涉及**数值计算**（如CPI、执行时间、地址计算、浮点数转换等），你必须：
1. 用推理给出答案
2. 用Python代码验证计算结果

代码验证格式：在solution_steps后附上Python代码块，用实际数值验证每个关键计算步骤。如果推理和代码结果不一致，以代码计算为准。

如果修复仅涉及**概念辨析**（不涉及数值），则只需要推理，不需要代码。

## 输出要求

严格按以下markdown格式输出修正后的完整题目（包含未修改的部分）：

# question {slot_id}

## 题目
- **stem**: 题干全文（通常不变）
- **option_A**: 选项A内容
- **option_B**: 选项B内容
- **option_C**: 选项C内容
- **option_D**: 选项D内容

## 答案
- **correct_answer**: 正确答案字母
- **explanation**: 修正后的解析
- **solution_steps**: 解题步骤
- **verification_code**: Python验证代码（概念题写"不适用"）
- **verification_result**: 代码验证结果摘要（概念题写"不适用"）
- **fix_summary**: 修改了什么，为什么修改
"""

# ═══════════════════════════════════════════════════════════════
# Review prompt (markdown output)
# ═══════════════════════════════════════════════════════════════

PAPER_REVIEWER_PROMPT = """你是一位408考研试卷质量评审专家。请审核以下生成的模拟卷，区分内容问题和答案问题。

## 整卷蓝图
{paper_blueprint_json}

## 生成的题目
{generated_questions_json}

## 题位模板（用于对照）
{slot_templates_json}

## 审核要点

对每道题审核：
1. 考点是否符合SlotBlueprint（知识点、难度、风格）
2. 答案是否正确（计算是否准确、推理是否严密）
3. 干扰项设计是否合理
4. 题目是否原创（不与真题雷同）

## 问题分类（关键！）

- **content_mismatch**: 考点/难度/风格不符合蓝图要求 → 需要重新出题
- **answer_error**: 内容符合但答案或计算有误 → 只需修复答案
- **pass**: 质量合格

请严格按以下markdown格式输出：

# paper_review

## 总体
- **overall_status**: pass 或 has_issues
- **overall_score**: 0-100
- **overall_comment**: 总体评价

## Q12
- **status**: pass 或 content_mismatch 或 answer_error
- **quality_score**: 0-10
- **blueprint_compliance**: 是否符合蓝图（一句话）
- **issue**: 问题描述（pass写"无"）
- **fix_instruction**: 具体修复指令（pass写"无"；answer_error时指出错在哪、正确答案应该是什么；content_mismatch时说明应该如何调整）

（每个题位一个 ## 标题的section，格式同上）

## distribution
- **difficulty_curve**: 难度曲线评价
- **role_balance**: 功能角色分布评价
- **knowledge_overlap**: 知识点重叠问题
- **originality**: 原创性评价
"""

# Legacy prompt (kept for backward compatibility)
PAPER_QUALITY_REVIEWER = PAPER_REVIEWER_PROMPT

# ═══════════════════════════════════════════════════════════════
# Hybrid subjective prompts (legacy prompt quality + new pipeline speed)
# ═══════════════════════════════════════════════════════════════

SUBJECTIVE_DRAFT_ONLY_PROMPT = """你是一位408考研出题专家。请严格按照以下SlotBlueprint设计一道综合应用题。

## 出题蓝图
{slot_blueprint_json}

## 经验卡参考
{experience_card_md}

## 参考真题（风格参考，请勿照抄）
{reference_questions}

## 出题要求

### 题目设计
- 综合应用题不设计选项，只有题干和子问
- sub_questions决定子问数量，每个子问要有明确的求解目标
- **target_difficulty**决定整体难度，各子问应梯度递进
- **calculation_load**决定计算量，≥3时应包含需多步推演的子问
- **must_include**中的要素必须在题目中体现
- **must_avoid**中的要素绝对不能出现
- 题目必须完全原创，不与任何真题雷同
- 参数必须自洽，确保题目有唯一确定解

### 设计意图（重要！）
你必须写清楚：
1. 每个子问期望考察什么知识点/能力
2. 预期的解题路径是什么（用什么公式/方法/步骤）
3. 陷阱设计（如果有的话，学生容易犯什么错）
4. 各子问之间的逻辑关系

## 输出格式（只出题和解题设计，不写答案）

# question {slot_id}

## 题目
- **stem**: 题干全文（包含所有已知条件和背景描述）
- **sub_questions**: 子问列表，JSON数组格式，如 ["子问1内容", "子问2内容", "子问3内容"]
- **given_conditions**: 题目给出的所有已知条件，JSON数组格式
- **difficulty_self_assessment**: 1-5自评难度
- **knowledge_points**: 知识点1, 知识点2
- **parameter_notes**: 参数设计说明（为什么选这些参数，确保可解性）

## 设计意图
- **sub_q1_intent**: 第1问期望考察什么，预期解题路径
- **sub_q2_intent**: 第2问期望考察什么，预期解题路径
- **sub_q3_intent**: 第3问期望考察什么，预期解题路径（如有更多子问继续列出）
- **trap_design**: 陷阱设计说明（学生容易犯的错误，无陷阱写"无"）
- **sub_question_logic**: 各子问之间的逻辑关系（一句话）
"""

SUBJECTIVE_SOLUTION_FORMATTER_PROMPT = """你是一位408考研解题专家。请根据以下题目和代码执行结果，整理成标准答案格式。

## 题目
{question_json}

## 代码执行结果（直接从Python脚本输出）
{solver_result_json}

## 要求
- 直接阅读 raw_outputs / last_raw_output 中的Python脚本输出
- 不要重新解题，只整理代码执行得到的结果
- 每个子问给出清晰的解答步骤，数值和计算结果必须来自代码输出
- 步骤要简洁，不要冗长的教学式解释
- 最终结果要醒目标注

请严格按以下markdown格式输出：

# solution {slot_id}

## 标准答案
- **answers**: 各子问最终答案，JSON格式如 {{"sub_q1": "答案1", "sub_q2": "答案2"}}
- **total_score**: 题目总分

## 解答过程

### 第1问
（简洁的解答步骤）

### 第2问
（简洁的解答步骤）

（每个子问一个 ### 小节）
"""

SUBJECTIVE_RUBRIC_PROMPT = """你是一位408考研评分标准制定专家。请根据以下题目和标准答案制定评分标准。

## 题目
{question_json}

## 标准答案
{solution_json}

## 蓝图要求
{slot_blueprint_json}

## 要求
- 评分点要与子问对应
- 每个评分点标明分值
- 关键步骤给分，结果也给分
- 总分应等于蓝图中的typical_score

请严格按以下markdown格式输出：

# rubric {slot_id}

## 评分点
- **point_1**: 评分点描述（X分）
- **point_2**: 评分点描述（X分）
...

## 评分说明
- 总分：X分
- 评分要点概述（1-2句话）
"""

SUBJECTIVE_QUESTION_REVIEW_PROMPT = """你是一位408考研出题审核专家。请审核以下综合应用题。

## 出题设计意图
{design_intent_json}

## 题目
{question_json}

## 解题结果
{solution_json}

## 评分标准
{rubric_json}

## 蓝图要求（用于对照）
{slot_blueprint_json}

## 审核核心：对比出题意图与实际结果

你需要对比三个方面：

1. **题目设计 vs 蓝图要求**：考点、难度、计算量是否符合slot
2. **出题意图 vs 解题结果**：出题者期望考察的知识点，解题者是否正确回答了
3. **答案正确性**：解题结果是否计算正确

## 修复路由（关键！）

- 如果**题目设计**不符合蓝图（考点偏了、难度不对、计算量不对）→ fix_target=question（重新出题）
- 如果**题目设计**没问题但**答案错误**→ fix_target=answer（只重新解题）
- 如果都好 → pass

请严格按以下markdown格式输出：

# review {slot_id}

## 结果
- **status**: pass 或 revise
- **score**: 0-100
- **needs_fix**: yes 或 no

## 检查
- **design_vs_blueprint**: pass 或 fail（题目设计是否符合蓝图要求）
- **intent_vs_answer**: pass 或 fail（出题意图与解题结果是否匹配）
- **answer_correctness**: pass 或 fail（答案计算是否正确）
- **sub_question_count_match**: pass 或 fail
- **calculation_load_match**: pass 或 fail
- **rubric_match**: pass 或 fail

## 修复指令（pass时写"无"）
- **issue**: 具体问题描述
- **fix_target**: question（题目设计问题，需重新出题）或 answer（答案问题，只需重新解题）
- **fix_instruction**: 具体修复指令
"""
