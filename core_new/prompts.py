# core_new/prompts.py

"""
集中管理与 LLM 交互的 Prompt 模板。

2026 版本的默认解题流程不再使用去年的重约束 MCTS/多代码投票式流程，
而是采用更适合当前强开源模型的轻量链路：

1. 单次结构化推理；
2. 按需生成一份代码做验证；
3. 一致性检查；
4. 基于解题轨迹做后置知识点标注。
"""

# ==============================================================================
# 现代解题流程 Prompts
# ==============================================================================

MODERN_REASONING_PROMPT = """你是一位严谨的 408 考研解题专家。请只完成“解题推理”，不要做知识点标注，也不要写代码。

你需要利用当前开源大模型较强的推理能力，直接完成题目理解、关键条件提取、推导和最终作答。

输出必须是 JSON 对象，不要添加额外文字。字段要求：
{{
  "answer": "最终答案；选择题写选项，计算题写关键结果",
  "confidence": 0.0,
  "reasoning_steps": [
    "步骤1：提取题干关键条件",
    "步骤2：基于条件进行推导",
    "步骤3：得到结论"
  ],
  "key_conditions": ["题干中的关键条件"],
  "needs_code_verification": true,
  "verification_targets": ["需要用代码验证的计算/枚举/模拟点"],
  "final_response": "面向用户的完整解题说明，包含最终答案"
}}

判断是否需要代码验证：
- 需要：涉及计算、枚举、算法模拟、地址/Cache/分页/调度/网络窗口等可程序验证的题；
- 不需要：纯概念、定义判断、简单事实题。

---
[题目]
{question}

---
[可参考的候选知识点与常见陷阱]
{knowledge_and_pitfalls}
---

请输出 JSON：
"""

CODE_VERIFICATION_PROMPT = """你是一位用于辅助 408 解题的 Python 验证工程师。你的任务不是重新解题，而是根据已有推理，写一份最小可执行 Python 代码验证其中可计算、可枚举或可模拟的部分。

要求：
1. 只写一份代码，不要生成多版本代码。
2. 代码必须自包含，不能读写外部文件，不能访问网络。
3. 若题目不适合代码验证，请输出空代码块，并在注释中说明原因。
4. 代码必须打印关键验证结果，格式尽量清晰，例如 `print("answer=B")` 或 `print("page_no=... offset=...")`。
5. 将所有代码包裹在 `<execute_code>` 和 `</execute_code>` 标签之间。

---
[题目]
{question}

---
[模型自然语言推理 JSON]
{reasoning_json}

---
[需要验证的目标]
{verification_targets}
---

请输出验证代码：
"""

ANSWER_VERIFICATION_PROMPT = """你是一位严格的 408 考研答案仲裁员。现在同一道题有两个信息源：
- 自然语言推理结果
- 可选的代码验证结果

你的任务是判断二者是否一致，并给出最终采用策略。你不能做知识点标注。

请严格输出 JSON 对象，不要添加额外文字。字段要求：
{{
  "consistency": "consistent | inconsistent | code_skipped | code_failed | unknown",
  "preferred_source": "reasoning | code | uncertain",
  "needs_remote_judge": true,
  "final_answer": "如果能明确最终答案，写在这里；否则为 null",
  "reason": "简要说明为什么这样判断",
  "disagreements": ["列出关键不一致点"]
}}

判断原则：
1. 代码跳过且推理完整时，preferred_source 为 reasoning。
2. 代码执行成功且验证结果与推理答案一致时，needs_remote_judge 为 false。
3. 代码执行成功但与推理冲突时，needs_remote_judge 为 true。
4. 代码失败时，不要直接否定推理，除非失败暴露了推理不可执行或条件缺失。

---
[题目]
{question}

---
[自然语言推理结果]
{reasoning_result}

---
[代码验证结果]
{code_result}
---

请输出 JSON：
"""

TRACE_ANNOTATION_PROMPT = """你是一位 408 考研真题知识点标注员。你的任务是基于原题、候选检索知识、自然语言推理轨迹、代码验证结果和一致性检查结果进行知识点标注。

重要边界：
1. 你不能重新解题，也不能修改答案。
2. 你只能做标注：科目、主知识点、次知识点、难度、考点层级、题型模式、常见错误、推理能力要求。
3. 如果推理轨迹里出现某个知识点，但它不是题目真正考查目标，不要标为主知识点。
4. 主知识点通常是决定最终答案所必需的知识；辅助计算、单位换算、基础定义通常只能作为次知识点。

请严格输出 JSON 对象，不要添加额外文字。字段要求：
{{
  "subject": "数据结构 | 计算机组成原理 | 操作系统 | 计算机网络 | unknown",
  "primary_knowledge_points": [
    {{
      "id": "可为空字符串，若没有稳定 taxonomy id",
      "name": "知识点名称",
      "weight": 0.0,
      "exam_level": "浅层知识 | 基础应用 | 核心考点 | 综合迁移"
    }}
  ],
  "secondary_knowledge_points": [],
  "difficulty": 1,
  "exam_level": "浅层知识 | 基础应用 | 核心考点 | 综合迁移",
  "question_pattern": "例如：选择题-计算推导、选择题-概念判断、综合题-算法设计",
  "common_error_tags": ["常见错误标签"],
  "reasoning_requirements": ["完成本题需要具备的推理能力"],
  "label_confidence": 0.0,
  "review_status": "auto_pass | needs_review",
  "annotation_reason": "简要说明标注依据"
}}

---
[原题]
{question}

---
[检索得到的候选知识点与常见陷阱]
{retrieved_candidates}

---
[自然语言推理轨迹]
{reasoning_result}

---
[代码验证结果]
{code_result}

---
[一致性检查结果]
{verification}
---

请输出 JSON：
"""

# ==============================================================================
# 辅助流程 Prompts
# ==============================================================================

QUESTION_CLASSIFICATION_PROMPT = """你是一个专业的 408 解题策略分析师。请判断题目最适合的解题路径。

输出必须是 JSON 对象：
{{
  "question_type": "direct | reasoning",
  "reason": "简要说明"
}}

分类标准：
- direct：纯概念、定义、事实判断，不需要复杂推导；
- reasoning：需要推导、计算、枚举、算法模拟或多条件判断。

---
[题目]
{question_prompt}
---

请输出 JSON：
"""

DIRECT_ANSWER_PROMPT = """你是一位知识渊博、表达清晰的 408 考研专家。请直接、准确回答以下问题。

要求：
1. 不做知识点标注。
2. 若答案是数值或关键短语，请使用 `\\boxed{{}}` 包裹。
3. 若是选择题，请明确给出选项和简要理由。

---
[问题描述]
{new_question_prompt}

---
[相关知识点与常见陷阱参考]
{knowledge_and_pitfalls}
---

请给出答案：
"""

SCORING_PROMPT = """你是一位严格、公正的计算机考研题阅卷人。你的任务是对比“AI生成的答案”和“标准答案”，并给出一个介于 0.0 到 1.0 之间的分数。

评分标准：
- 1.0：完全正确。核心结论、关键数值、逻辑推理完全一致。
- 0.7-0.9：基本正确。核心结论正确，但解释存在轻微瑕疵。
- 0.4-0.6：部分正确。最终结论错误，但部分思路正确。
- 0.1-0.3：严重错误。只提及少量相关概念。
- 0.0：完全错误或无关。

输出格式：
<reasoning>
这里是简要评分理由。
</reasoning>
<score>
\\boxed{{这里只填写一个0.0到1.0之间的数字}}
</score>

---
[AI生成的答案]
{response}
---
[标准答案]
{ground_truth}
---

请评分：
"""
