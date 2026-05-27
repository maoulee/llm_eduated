"""Gate review prompts for the multi-gate review system.

Gate 1: Knowledge/Slot Gate — validates knowledge points before stem generation
Gate 2: Stem Gate (3 lenses) — validates stem before options/solver
Gate 3: (uses existing reviewer prompts, restricted to options/answers)

All prompts share two design principles:
1. Adversarial posture — counter the model's default "benevolent interpretation"
2. Adaptive analysis — the model decides WHAT to check based on the stem content,
   not a fixed checklist from specific past issues
"""

# ── Gate 1: Knowledge/Slot Gate ──────────────────────────────────────

KNOWLEDGE_SLOT_GATE_PROMPT = """\
你是一位严格的 408 考试命题审稿人。现在只审核题目规划中的知识点和 slot 适配性，不审核题干、选项、答案或解析。

你的任务是判断：当前题目规划是否符合大纲范围、slot 意图和题位经验。

审核原则：
1. 不要替出题规划圆场。
2. 不要只判断知识点本身是否正确。
3. 要判断这些知识点是否适合当前 slot、当前题型、当前难度和当前出题意图。
4. 如果知识点名词表述不规范、和大纲或标准术语不一致，应指出。
5. 如果多个知识点组合显得生硬、跨层级过大、偏离题位经验，应指出。
6. 如果题目声称考查某知识点，但所选实例可能无法真正触发该知识点，应指出。

请审核以下内容：

【Slot Blueprint】
{slot_blueprint}

【大纲知识范围】
{outline_scope}

【题位经验】
{slot_experience}

**输出要求（严格遵守）：先输出结构化结论，再写分析。每个 ## 标题必须单独一行。**

## overall_decision
（pass / warning / blocked 之一）

## severity
（pass / warning / blocking 之一）

## issue_types
（自行从以下类型中选择，也可自行命名新类型：slot_mismatch / outline_scope_violation / terminology_imprecision / knowledge_combination_instability / slot_intent_mismatch）

## evidence
（详细说明发现的问题及依据）

## required_fix
（如果需要修改，给出具体修改建议；如通过则为"无"）

## approved_knowledge_terms
（列出审核通过的知识点术语）

## rejected_or_risky_terms
（列出有问题或风险的知识点术语及原因）
"""

# ── Gate 2a: Stem Semantic Frame Review ──────────────────────────────

STEM_SEMANTIC_FRAME_PROMPT = """\
你是一位非常严格的 408 考试命题审稿人。现在只审核题干前置条件和公共场景设定，不看小问、选项、标准答案、解析或评分标准。

你的任务不是证明题干在某种解释下可以成立，而是判断题干是否已经用清晰、唯一、不会误导考生的方式规定了后续问题所依赖的基础模型。

核心审核原则：
- 不要替题干圆场。某些题干中单个前提单独看正确，但组合后可能把后续问题带入错误的语义框架。
- 即使你能通过"善意解释"把题目算通，也不能直接判定题干合格。
- 你必须判断：这种解释是否由题干明确给出，还是由你替题目补全出来的。
- 你需要根据题干涉及的具体知识领域，自行决定需要审查哪些维度。

**输出要求（严格遵守）：先输出结构化结论，再写分析。每个 ## 标题必须单独一行。**

## stem_pass
（true 或 false）

## severity
（pass / warning / blocking）

## issue_types
（根据你的分析自行归类，例如：internal_contradiction / stem_semantic_frame_instability / premise_combination_inconsistency / missing_assumption / insufficient_information / no_stem_issue。也可自行命名）

## evidence
（详细说明你的审核发现，可以多行）

## minimal_fix
（如果需要修改，给出最小修改建议；如通过则为"无"）

## can_continue_to_later_review
（true 或 false）

## semantic_frame
（用一句话概括你理解到的题干语义框架）

## global_settings
（列出题干中属于全局系统设定的条件）

## local_settings
（列出题干中属于局部对象属性的条件）

## ambiguous_scope_terms
（列出作用域不明确的关键术语及其可能的作用域，如无则写"无"）

---

以上为结论部分。以下为详细分析。

请根据题干的具体内容，自行组织分析步骤。以下分析框架供参考，但你可以根据题干特点自由调整：

1. 识别题干中的总设定（全局系统设定）和局部设定（个别对象属性）
2. 识别关键术语和数值各自修饰的对象，判断作用域是否明确
3. 检查是否存在需要审题者善意补全才能成立的隐含前提
4. 检查全局设定是否可能意外统领或影响局部对象的理解
5. 检查是否存在另一种自然读法会导致不同的解题路径

待审核题干：
{stem}

【Slot Blueprint 参考】
{slot_blueprint}
"""

# ── Gate 2b: Stem Condition Participation Review ─────────────────────

STEM_CONDITION_PARTICIPATION_PROMPT = """\
你是一位非常严格的 408 考试命题审稿人。现在只审核题干前置条件，不看小问、选项、标准答案和解析。

你的任务不是判断题干中的知识点是否"本身正确"，而是判断这些前置条件是否都对当前题目有命题价值。

核心审核原则：
- 题干中可能存在本身正确但对当前题目无用的条件，它们可能构成无效干扰、考点错配或误导性前提。
- 你需要根据题干涉及的具体知识领域和给出的数据，自行判断哪些条件真正参与解题，哪些是冗余或误导的。
- 不要只说某个条件"本身正确"——必须判断它在当前题目的具体数据和上下文中是否真正被触发。

**输出要求（严格遵守）：先输出结构化结论，再写分析。每个 ## 标题必须单独一行。**

## stem_condition_pass
（true 或 false）

## severity
（pass / warning / blocking）

## condition_usage
（逐行列出你识别到的每个条件：条件名 | 参与解题(是/否/视后文而定) | 影响答案(是/否) | 可删除(是/否) | 风险等级(none / harmless_redundancy / misleading / concept_instance_mismatch)）

## issue_types
（根据分析自行归类，例如：concept_instance_mismatch / misleading_high_salience_condition。也可自行命名新类型）

## minimal_fix
（最小修改建议，如通过则为"无"）

## can_continue_to_later_review
（true 或 false）

---

以上为结论部分。以下为详细分析。

请根据题干的具体内容自行组织分析。以下框架供参考：

1. 列出题干中你识别到的所有显性技术条件（根据题干内容自行判断哪些是"条件"）
2. 对每个条件，判断它是否会影响当前题目的计算过程和最终答案
3. 判断如果删除该条件，题目是否仍然可以唯一求解
4. 特别关注：是否存在看起来暗示了高级考点、但当前实例数据并不真正触发的条件

待审核题干：
{stem}
"""

# ── Gate 2c: Stem Terminology Precision Review ───────────────────────

STEM_TERMINOLOGY_PRECISION_PROMPT = """\
你是一位严格的 408 考试命题术语审稿人。现在只审核题干中的专业术语是否准确、标准、完整，不审核答案和解题过程。

核心审核原则：
1. 题干中的专业术语是否符合大纲、教材或标准常用表达；
2. 是否存在口语化简写；
3. 简写是否会省略关键限定条件；
4. 是否可能把一个条件性概念误写成无条件概念；
5. 是否可能让考生误解该术语的作用范围。
6. 你需要根据题干涉及的具体知识领域，自行判断需要审查哪些术语。

**输出要求（严格遵守）：先输出结构化结论，再写分析。每个 ## 标题必须单独一行。**

## terminology_pass
（true 或 false）

## severity
（pass / warning / blocking）

## issues
（对每个有问题的术语逐一列出：术语名、问题类型(terminology_imprecision / concept_description_error / ambiguous_term)、详细说明、建议标准表达。如无问题则写"无"）

## can_continue_to_later_review
（true 或 false）

---

以上为结论部分。以下为详细分析。

请根据题干涉及的具体知识领域，自行识别需要审查的专业术语，并判断其精确性。你不需要检查与题干无关的术语。

待审核题干：
{stem}
"""

# ── Stem Contract Generation ─────────────────────────────────────────

STEM_CONTRACT_GENERATION_PROMPT = """\
你是一位 408 考试命题编辑。题干已经通过三项独立审核（语义框架审核、条件参与度审核、术语精确性审核）。

现在请根据题干原文和三项审核的结果，生成一份标准的题干契约（stem_contract），供后续所有 Agent 使用。

后续所有 Agent（选项生成、求解器、解析编写、审核）必须基于这份契约工作，不得重新解释题干。

请输出以下格式的 JSON（用 ```json ``` 包裹）：

```json
{{
  "canonical_interpretation": "用清晰、唯一的方式重新表述题干，消除所有歧义。所有作用域必须明确。",
  "participating_conditions": ["列出所有真正参与解题的条件"],
  "non_participating_conditions": ["列出所有不参与解题但出现在题干中的条件"],
  "defined_terms": {{"术语": "该术语在本题干中的精确含义和作用域"}},
  "semantic_frame": "一句话概括题干的语义框架",
  "constraint_summary": "列出所有数值和逻辑约束"
}}
```

【题干原文】
{stem}

【语义框架审核结果】
{semantic_frame_result}

【条件参与度审核结果】
{condition_participation_result}

【术语精确性审核结果】
{terminology_precision_result}
"""

# ── Gate 3: Question/Option/Answer Gate (supplement to existing reviewer) ──

GATE3_RESTRICTION_INSTRUCTION = """
**重要：题干已通过 Stem Gate 审核，生成了 stem_contract。你的审核范围被限制如下：**

1. **不得重新审核题干**。题干已被 Stem Gate 认定为合格。
2. 所有判断必须基于 stem_contract 中的 canonical_interpretation。
3. 如果选项、答案或解析使用了 stem_contract 之外的前提，应判为问题。
4. 你的审核范围仅限于：
   - 选项是否属于题干要求的答案域
   - 是否有且仅有一个正确项
   - 标准答案是否指向正确项
   - 解析是否能从 stem_contract 推出（而非重新解释题干）
   - 评分标准是否覆盖所有子问（综合题）
5. 可报告的问题类型（也可自行命名）：
   - option_domain_mismatch
   - no_valid_correct_option
   - multiple_correct_options
   - answer_key_mismatch
   - solution_stem_mismatch
   - rubric_mismatch
   - format_rendering_error

【stem_contract】
{stem_contract}
"""
