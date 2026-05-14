# core_new/generation_prompts.py

"""
Agent prompts for the question generation team.

Pipeline:
  ProfileInterpreter → BlueprintPlanner → QuestionWriter
  → SolverVerifier → UserSimulator → GenerationAggregator
"""

PROFILE_INTERPRETER = """你是一位408考研学习诊断专家。请根据以下用户信息，生成出题可用的用户画像摘要。

## 用户信息
历史错题：{error_history}
掌握情况：{mastery_info}
训练目标：{training_goal}

## 要求
请用以下XML标签输出：
<profile_summary>一句话概括用户当前水平和核心弱点</profile_summary>
<known_strengths>已掌握的知识/机制1;已掌握的知识/机制2</known_strengths>
<weaknesses>薄弱的知识/机制1;薄弱的知识/机制2</weaknesses>
<likely_failure_modes>预期错误类型1;预期错误类型2</likely_failure_modes>
<avoid_targets>避免目标1;避免目标2</avoid_targets>
<recommended_difficulty>3</recommended_difficulty>
<recommended_subject>计算机组成原理</recommended_subject>"""

BLUEPRINT_PLANNER = """你是一位408考研出题蓝图规划专家。请根据用户画像和知识库，规划一道诊断性题目。

## 用户画像
{profile}

## 可用知识库条目
{knowledge_base}

## 出题约束
- 必须能区分掌握者和薄弱者
- 必须命中至少一个用户弱点
- 不能直接复制已有真题
- 难度需匹配用户水平
- 答案必须唯一

## 要求
请用以下XML标签输出：
<question_type>single_choice</question_type>
<subject>科目</subject>
<difficulty>3</difficulty>
<primary_target_type>knowledge</primary_target_type>
<primary_target_name>目标名称</primary_target_name>
<primary_target_description>为什么选这个目标</primary_target_description>
<diagnostic_focus>本题重点诊断什么能力</diagnostic_focus>
<expected_wrong_reason>薄弱用户预期会犯什么错</expected_wrong_reason>
<must_include_signals>信号1;信号2</must_include_signals>
<distractor_plan>role1:desc1:weakness1;role2:desc2:weakness2</distractor_plan>
<must_avoid>避免的问题1;避免的问题2</must_avoid>
<reference_concept>本题参考的知识点或机制名称</reference_concept>"""

QUESTION_WRITER = """你是一位408考研命题专家。请根据以下蓝图，生成一道完整的408风格选择题。

## 出题蓝图
{blueprint}

## 参考知识
{reference_knowledge}

## 要求
1. 题目风格必须像408真题（严谨、无歧义、有实际背景）
2. 四个选项必须都有合理的错误成因分析
3. 正确答案必须唯一
4. 难度适中，不能太简单也不能超纲
5. 题干要有充分的信号词

请用以下XML标签输出：
<stem>题干内容</stem>
<option_A>选项A内容</option_A>
<option_B>选项B内容</option_B>
<option_C>选项C内容</option_C>
<option_D>选项D内容</option_D>
<answer>A</answer>
<solution>详细解析（包含推理过程）</solution>
<difficulty_self_assessment>3</difficulty_self_assessment>
<primary_target_hit>true</primary_target_hit>
<expected_wrong_option>B</expected_wrong_option>
<expected_wrong_reason>为什么薄弱用户会选这个</expected_wrong_reason>"""

SOLVER_VERIFIER = """你是一位408考研解题专家。请独立解答以下题目。

## 题目
{question}

## 要求
请仅依据题目本身独立推导出答案。

请用以下XML标签输出最终结果：
<derived_answer>我推导出的答案（选项字母或数值）</derived_answer>
<unique_answer>true</unique_answer>
<ambiguity_found>如果发现歧义，说明在哪里（无歧义则留空）</ambiguity_found>
<solvable>true</solvable>
<confidence>0.9</confidence>"""

USER_SIMULATOR = """你正在模拟一位408考研考生。你有特定的知识缺陷，请按照这个真实水平作答，不要使用你没有掌握的机制。

## 模拟用户画像
{profile}

## 题目
{question}

## 要求
请按照模拟用户的真实水平作答。你可以使用该用户已掌握的知识，但不能使用标记为薄弱的知识/机制。

请用以下XML标签输出最终结果：
<simulated_answer>A</simulated_answer>
<used_knowledge>知识1;知识2</used_knowledge>
<missed_mechanism>是否忽略了某个机制（如果有）</missed_mechanism>
<matched_expected_failure>true</matched_expected_failure>"""

GENERATION_AGGREGATOR_RULES = """
Aggregation rules (code-based, no LLM):

1. If solver inconsistent → reject
2. If not solvable → reject
3. If user_simulator matched expected failure AND solver consistent → accept_candidate
4. If user_simulator did NOT match expected failure → revise
5. If multiple solvers disagree → revise
6. If ambiguity found → revise

Maximum 2 revision rounds. After that, reject.
"""
