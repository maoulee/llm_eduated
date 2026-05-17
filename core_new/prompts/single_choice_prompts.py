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

SC_DRAFT_PROMPT = """你是一位408考研出题专家。请根据以下蓝图和经验卡，**仅生成题干（stem）**。不要生成选项，不要给出答案。

## 出题蓝图
{slot_blueprint_json}

## 经验卡参考
{experience_card_md}

## 约束
- stem_length必须符合蓝图要求（short<=50字，medium<=100字，long<=150字）
- condition_count必须符合蓝图要求的已知条件数量
- 考点必须是primary_target_name指定的知识点
- reasoning_shape决定解题路径，题干应引导该路径
- 题目必须原创，不与经验卡中的真题雷同

请严格按以下markdown格式输出：

## stem
- **stem**: 题干全文（包含所有条件和问题）
- **stem_length**: short 或 medium 或 long
- **condition_count**: 已知条件数量
- **reasoning_hint**: 预期解题路径提示（一句话）
"""

# ═══════════════════════════════════════════════════════════════
# Options: 4 options + distractor intent
# ═══════════════════════════════════════════════════════════════

SC_OPTIONS_PROMPT = """你是一位408考研出题专家。请根据以下题干和蓝图要求，生成4个选项（A/B/C/D），其中恰好有1个正确答案。

## 题干
{stem}

## 蓝图要求
{slot_blueprint_json}

## 约束
- option_style决定选项格式（数字结果→具体数值或表达式；概念判断→命题判断或概念辨析）
- distractor_strategy指导每个错误选项的设计方向
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
