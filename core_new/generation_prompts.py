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
请输出JSON：

```json
{{
  "profile_summary": "一句话概括用户当前水平和核心弱点",
  "known_strengths": ["已掌握的知识/机制"],
  "weaknesses": ["薄弱的知识/机制"],
  "likely_failure_modes": ["预期会犯的错误类型"],
  "avoid_targets": ["应该避免的训练目标（已经掌握的）"],
  "recommended_difficulty": 3,
  "recommended_subject": "计算机组成原理 | 操作系统 | 数据结构 | 计算机网络"
}}
```"""

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
请输出JSON：

```json
{{
  "question_type": "single_choice | multi_choice | judgment",
  "subject": "科目",
  "difficulty": 3,
  "primary_target": {{
    "type": "knowledge | mechanism | reasoning_pattern",
    "name": "目标名称",
    "description": "为什么选这个目标"
  }},
  "diagnostic_focus": "本题重点诊断什么能力",
  "expected_wrong_reason": "薄弱用户预期会犯什么错",
  "must_include_signals": ["题干必须包含的信号"],
  "distractor_plan": [
    {{
      "role": "missed_mechanism | unit_error | concept_confusion | wrong_route",
      "description": "这个干扰项诱发的具体错误",
      "targeted_weakness": "对应哪个用户弱点"
    }}
  ],
  "must_avoid": ["不能出现的问题"],
  "reference_concept": "本题参考的知识点或机制名称（用于从知识库检索）"
}}
```"""

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

请输出JSON：

```json
{{
  "stem": "题干",
  "options": {{
    "A": "选项A",
    "B": "选项B",
    "C": "选项C",
    "D": "选项D"
  }},
  "answer": "正确答案字母",
  "solution": "详细解析（包含推理过程）",
  "difficulty_self_assessment": 3,
  "target_mapping": {{
    "primary_target_hit": true,
    "expected_wrong_option": "预期薄弱用户会选的选项",
    "expected_wrong_reason": "为什么薄弱用户会选这个"
  }}
}}
```"""

SOLVER_VERIFIER = """你是一位408考研解题专家。请独立解答以下题目，不依赖给定的标准答案。

## 题目
{question}

## 要求
请独立推导出答案，然后与标准答案比对。

请输出JSON：

```json
{{
  "my_answer": "我推导出的答案",
  "my_reasoning": "详细推导过程",
  "given_answer": "{given_answer}",
  "consistent": true或false,
  "unique_answer": true或false,
  "ambiguity_found": "如果发现歧义，说明在哪里",
  "solvable": true或false,
  "issues": ["发现的问题列表"]
}}
```"""

USER_SIMULATOR = """你正在模拟一位408考研考生。你有特定的知识缺陷，请按照这个真实水平作答，不要使用你没有掌握的机制。

## 模拟用户画像
{profile}

## 题目
{question}

## 要求
请按照模拟用户的真实水平作答。你可以使用该用户已掌握的知识，但不能使用标记为薄弱的知识/机制。

请输出JSON：

```json
{{
  "simulated_answer": "模拟用户选择的答案",
  "reasoning": "模拟用户的推理过程",
  "used_knowledge": ["解题中用到的知识"],
  "missed_mechanism": "是否忽略了某个机制（如果有）",
  "matched_expected_failure": true或false
}}
```"""

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
