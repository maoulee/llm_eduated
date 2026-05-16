# core_new/slot_prompts.py
"""Prompts for slot-template driven extraction, composition, and generation.

Extraction:
  SLOT_BATCH_ANALYSIS_PROMPT — per-slot observation + template extraction

Composition:
  PAPER_COMPOSER_PROMPT — generates PaperBlueprint from SlotTemplates
  SLOT_BLUEPRINT_REFINER — refines single SlotBlueprint

Generation:
  SLOT_QUESTION_WRITER — generates question from SlotBlueprint + experience card

Review:
  PAPER_QUALITY_REVIEWER — reviews generated paper against templates
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
# Composition prompts
# ═══════════════════════════════════════════════════════════════

PAPER_COMPOSER_PROMPT = """你是一位408考研组卷专家。你的任务是基于题位模板规划一套完整的模拟试卷。

## 用户需求
{user_requirements}

## 可用题位模板
{slot_templates_json}

## 你的任务

为每个题位生成一个SlotBlueprint，即该题位应该出什么样的题。请严格遵循模板中定义的难度范围、功能角色和知识领域。

输出格式（XML）：

<paper_blueprint>
  <paper_type>408模拟卷</paper_type>
  <total_questions>{total_slots}</total_questions>
  <difficulty_target>整体难度目标（1-5）</difficulty_target>

  <difficulty_distribution>
    level_1: 数量, level_2: 数量, level_3: 数量, level_4: 数量, level_5: 数量
  </difficulty_distribution>

  <role_distribution>
    foundation_check: 数量, mechanism_trigger: 数量, pattern_execution: 数量, trap_diagnosis: 数量, calculation_stability: 数量, cross_topic_integration: 数量, difficulty_separator: 数量
  </role_distribution>

  <slots>
    <slot_blueprint slot_id="Q12">
      <target_subject>科目</target_subject>
      <target_family>知识领域</target_family>
      <primary_target_name>具体考点（从该题位经验卡中选择，不要和真题重复）</primary_target_name>
      <target_depth>knowledge 或 mechanism 或 pattern</target_depth>
      <paper_role>功能角色</paper_role>
      <target_difficulty>目标难度1-5</target_difficulty>
      <difficulty_profile>JSON格式的6维难度画像</difficulty_profile>
      <distractor_requirements>干扰项要求，JSON数组</distractor_requirements>
      <must_include>题目必须包含的要素，逗号分隔</must_include>
      <must_avoid>题目必须避免的要素，逗号分隔</must_avoid>
      <reference_experience>参考哪几年的真题经验</reference_experience>
    </slot_blueprint>

    ...（每个题位一个slot_blueprint）
  </slots>

  <composition_rationale>整卷组卷思路说明（2-3句话）</composition_rationale>
</paper_blueprint>
"""

SLOT_QUESTION_WRITER = """你是一位408考研出题专家。请严格按照以下SlotBlueprint生成一道完整的题目。

## 出题蓝图
{slot_blueprint_json}

## 经验卡参考
{experience_card_md}

## 参考真题（风格参考，请勿照抄）
{reference_questions}

## 输出要求

请生成一道完全原创的题目，风格和难度匹配蓝图要求。严格按以下XML格式输出：

<question slot_id="{slot_id}">
  <stem>题干全文（包含所有条件和问题）</stem>
  <option_A>选项A内容</option_A>
  <option_B>选项B内容</option_B>
  <option_C>选项C内容</option_C>
  <option_D>选项D内容</option_D>
  <correct_answer>正确选项字母</correct_answer>
  <explanation>详细解析</explanation>
  <solution_steps>解题步骤，分号分隔</solution_steps>
  <difficulty_self_assessment>1-5自评难度</difficulty_self_assessment>
  <trap_description>陷阱设计说明</trap_description>
  <knowledge_points>考查的知识点，逗号分隔</knowledge_points>
</question>
"""

PAPER_QUALITY_REVIEWER = """你是一位408考研试卷质量评审专家。请评审以下生成的模拟卷。

## 整卷蓝图
{paper_blueprint_json}

## 生成的题目
{generated_questions_json}

## 题位模板（用于对照）
{slot_templates_json}

## 评审要点

请逐一检查：
1. 每道题是否符合自己的SlotBlueprint（难度、功能、知识点）
2. 整体难度曲线是否合理（前易后难，逐步提升）
3. 题目功能分布是否均衡
4. 是否有重复考查的知识点
5. 题目质量和原创性
6. 是否和参考真题过于相似

输出格式（XML）：

<paper_review>
  <overall_status>pass 或 revise 或 reject</overall_status>
  <overall_score>0-100分</overall_score>
  <overall_comment>总体评价（2-3句话）</overall_comment>

  <slot_reviews>
    <slot_review slot_id="Q12">
      <status>pass 或 regenerate 或 revise</status>
      <quality_score>0-10分</quality_score>
      <blueprint_compliance>是否符合蓝图（是/否+理由）</blueprint_compliance>
      <difficulty_match>难度是否匹配（是/否+理由）</difficulty_match>
      <issue>存在的问题（如果没有则写"无"）</issue>
      <revision_instruction>修改指令（如果需要重出，给出具体要求）</revision_instruction>
    </slot_review>
    ...（每道题一个slot_review）
  </slot_reviews>

  <distribution_check>
    <difficulty_curve>难度曲线评价</difficulty_curve>
    <role_balance>功能角色分布评价</role_balance>
    <knowledge_overlap>知识点重叠问题（如有）</knowledge_overlap>
    <originality>原创性评价</originality>
  </distribution_check>
</paper_review>
"""

# ═══════════════════════════════════════════════════════════════
# Blueprint review + question fix + whole-paper review
# ═══════════════════════════════════════════════════════════════

BLUEPRINT_REVIEWER_PROMPT = """你是一位408考研组卷审核专家。请审核以下组卷蓝图的质量。

## 用户需求
{user_requirements}

## 组卷蓝图
{paper_blueprint_json}

## 题位模板（用于对照）
{slot_templates_json}

## 审核要点

逐一检查每个SlotBlueprint：
1. 考点是否在题位模板的常见范围内
2. 难度是否在模板定义的合理范围内
3. 功能角色是否符合该题位的典型分布
4. 整卷知识点是否覆盖均匀，有无重叠
5. 难度曲线是否合理（前易后难）
6. 干扰项要求是否明确可执行

输出格式（XML）：

<blueprint_review>
  <overall_status>pass 或 revise</overall_status>
  <overall_comment>总体评价（2-3句话）</overall_comment>

  <slot_reviews>
    <slot_review slot_id="Q12">
      <status>pass 或 revise</status>
      <issue>问题描述（无问题写"无"）</issue>
      <revision_instruction>修改建议（如需修改）</revision_instruction>
    </slot_review>
    ...
  </slot_reviews>

  <global_issues>整卷层面的问题（如有）</global_issues>
</blueprint_review>
"""

QUESTION_FIXER_PROMPT = """你是一位408考研出题专家。以下题目整体质量不错，但存在需要修正的具体问题。请只修复指出的错误，保持题干、考点、风格不变。

## 原始题目
{question_json}

## 需要修复的问题
{fix_instructions}

## 输出要求

严格按以下XML格式输出修正后的完整题目（包含未修改的部分）：

<question slot_id="{slot_id}">
  <stem>题干全文（通常不变）</stem>
  <option_A>选项A</option_A>
  <option_B>选项B</option_B>
  <option_C>选项C</option_C>
  <option_D>选项D</option_D>
  <correct_answer>正确答案字母</correct_answer>
  <explanation>修正后的解析</explanation>
  <solution_steps>解题步骤</solution_steps>
  <fix_summary>修改了什么，为什么修改</fix_summary>
</question>
"""

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

输出格式（XML）：

<paper_review>
  <overall_status>pass 或 has_issues</overall_status>
  <overall_score>0-100</overall_score>
  <overall_comment>总体评价</overall_comment>

  <slot_reviews>
    <slot_review slot_id="Q12">
      <status>pass 或 content_mismatch 或 answer_error</status>
      <quality_score>0-10</quality_score>
      <blueprint_compliance>是否符合蓝图</blueprint_compliance>
      <issue>问题描述（pass写"无"）</issue>
      <fix_instruction>具体修复指令（answer_error时指出错在哪、正确答案应该是什么；content_mismatch时说明应该如何调整）</fix_instruction>
    </slot_review>
    ...
  </slot_reviews>

  <distribution_check>
    <difficulty_curve>难度曲线评价</difficulty_curve>
    <role_balance>功能角色分布</role_balance>
    <knowledge_overlap>知识点重叠</knowledge_overlap>
    <originality>原创性</originality>
  </distribution_check>
</paper_review>
"""
