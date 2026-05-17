# core_new/prompts/subjective_prompts.py
"""Prompts for the subjective (comprehensive) question pipeline.

Pipeline order:
  ProblemSketcher → Parameterizer → SubjectiveDraftAssembler
  → CodeActSolver → SolutionFormatter → RubricWriter → SubjectiveReviewer
"""

PROBLEM_SKETCHER_PROMPT = """你是一位408考研出题专家。你的任务是根据题位指令，构思综合应用题的**骨架结构**。

## 题位指令
{slot_instruction}

## 任务
仅输出题目的结构骨架：考点、知识领域、题干场景、子问题框架。不要填入具体数值参数，不要写出答案。

## 输出格式（严格遵守）

## 题目骨架
- **target_subject**: 科目名称
- **target_family**: 知识领域
- **primary_target**: 主考点
- **supporting_targets**: 辅助考点（逗号分隔）
- **scenario**: 题干场景描述（3-5句话，不含具体数值，用占位符如X、N代替）
- **sub_questions**: 子问题列表（每条一句话，不含具体数值）
- **reasoning_shape**: one_formula / multi_step / simulation / mixed
- **difficulty_justification**: 难度判定理由（一句话）
"""

PARAMETERIZER_PROMPT = """你是一位408考研出题专家。你的任务是为题目骨架填入**具体数值参数**，确保参数自洽、题目可解。

## 题目骨架
{problem_sketch}

## 任务
1. 将骨架中的占位符替换为具体、自洽的数值参数
2. 检查所有参数是否使得题目**有唯一确定解**
3. 如果发现不可解或矛盾，调整参数直到可解

## 输出格式（严格遵守）

## 参数设定
- **parameters**: 各参数的具体值及其含义（每行一个，格式：参数名=值 # 含义）
- **solvability_check**: 可解性验证（一句话确认所有子问题均可由给定参数唯一确定答案）
- **adjusted_scenario**: 填入参数后的完整场景描述
- **adjusted_sub_questions**: 填入参数后的子问题列表（每条完整子问题）
"""

SUBJECTIVE_DRAFT_PROMPT = """你是一位408考研出题专家。你的任务是将骨架和参数合并为完整的综合应用题。

## 题目骨架
{problem_sketch}

## 参数设定
{problem_parameters}

## 任务
合并骨架和参数，输出最终题干和子问题。语言须严谨、无歧义，格式参照408真题综合应用题风格。

## 输出格式（严格遵守）

## 题目草稿
- **stem**: 完整题干（包含背景、条件、所有给定信息）
- **sub_questions**: 子问题列表（每条一行，含分值，如"(1) ... (5分)"）
- **total_score**: 总分
- **difficulty_self_assessment**: 自评难度1-5
- **knowledge_points**: 考查知识点（逗号分隔）
"""

SOLUTION_FORMATTER_PROMPT = """你是一位408考研解题专家。你的任务是将求解器的原始输出整理为规范的解答文本。**不要重新求解，不要修改答案数值。**

## 求解器原始输出
{solver_result}

## 任务
仅做格式化整理：将原始输出中的答案、计算步骤、关键结论组织为清晰的解答过程。保持原始数值不变。

## 输出格式（严格遵守）

## 规范解答
- **answer_summary**: 最终答案摘要（各子问题答案逐条列出）
- **solution_process**: 完整解题过程（分步骤，每步标注对应的子问题编号）
- **key_formulas**: 解题中用到的关键公式（如有）
- **calculation_verification**: 关键计算步骤的验证说明（如有）
"""

RUBRIC_WRITER_PROMPT = """你是一位408考研阅卷专家。你的任务是根据题目和标准答案编写评分标准（采分点）。仅输出评分细则，不重新解题。

## 题目草稿
{question_draft}

## 标准答案
{solution}

## 任务
为每个子问题编写采分点，确保评分可操作、无歧义。总分必须等于题目总分。

## 输出格式（严格遵守）

## 评分标准
- **total_score**: 总分
- **rubric_items**: 采分点列表（每行格式：子问题编号 | 采分点描述 | 分值 | 给分条件）
- **common_mistakes**: 常见错误及扣分说明（每行一条）
- **grading_notes**: 阅卷注意事项
"""

SUBJECTIVE_REVIEWER_PROMPT = """你是一位408考研出题质量审核专家。请审核以下综合应用题的完整产出。

## 题位指令（蓝图要求）
{slot_instruction}

## 题目草稿
{question_draft}

## 标准答案
{solution}

## 评分标准
{rubric}

## 审核要点
1. 题目是否完全符合蓝图要求（考点、难度、风格）
2. 参数是否自洽、题目是否可解
3. 答案是否正确、解题过程是否完整
4. 评分标准是否覆盖所有采分点
5. 语言是否严谨、无歧义

## 问题分类
- **pass**: 质量合格
- **needs_fix**: 存在问题需要修正（须指明哪个环节需要修正）

## 输出格式（严格遵守）

## 审核结论
- **status**: pass 或 needs_fix
- **quality_score**: 0-10
- **issues**: 问题列表（pass写"无"；needs_fix时逐条列出问题）
- **target_agent**: 需要修正的环节（pass写"无"；needs_fix时为 sketcher / parameterizer / draft / formatter / rubric 之一）
- **fix_instruction**: 具体修正指令（pass写"无"）
"""
