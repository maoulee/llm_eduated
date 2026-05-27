"""Gate review prompts for the multi-gate review system.

Gate 1: Knowledge/Slot Gate — validates knowledge points before stem generation
Gate 2: Stem Gate (3 lenses) — validates stem before options/solver
Gate 3: (uses existing reviewer prompts, restricted to options/answers)

All prompts activate adversarial review posture to counter the model's
default "benevolent interpretation" tendency.
"""

# ── Gate 1: Knowledge/Slot Gate ──────────────────────────────────────

KNOWLEDGE_SLOT_GATE_PROMPT = """\
你是一位严格的 408 考试命题审稿人。现在只审核题目规划中的知识点和 slot 适配性，不审核题干、选项、答案或解析。

你的任务是判断：当前题目规划是否符合大纲范围、slot 意图和题位经验。

请注意：
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

请输出 markdown 格式，包含以下字段：

## overall_decision
（pass / warning / blocked 之一）

## severity
（pass / warning / blocking 之一）

## issue_types
列出所有发现的问题类型（可能包含以下类型）：
- slot_mismatch
- outline_scope_violation
- terminology_imprecision
- knowledge_combination_instability
- slot_intent_mismatch

## evidence
详细说明发现的问题及依据

## required_fix
（如果需要修改，给出具体修改建议；如通过则为空）

## approved_knowledge_terms
列出审核通过的知识点术语

## rejected_or_risky_terms
列出有问题或风险的知识点术语及原因
"""

# ── Gate 2a: Stem Semantic Frame Review ──────────────────────────────

STEM_SEMANTIC_FRAME_PROMPT = """\
你是一位非常严格的 408 考试命题审稿人。现在只审核题干前置条件和公共场景设定，不看小问、选项、标准答案、解析或评分标准。

你的任务不是证明题干在某种解释下可以成立，而是判断题干是否已经用清晰、唯一、不会误导考生的方式规定了后续问题所依赖的基础模型。

请特别注意：
某些题干中的单个前提单独看是正确的，但作为开头总设定放入题目后，可能会把后续问题带入错误的语义框架。此时即使你能通过"善意解释"把题目算通，也不能直接判定题干合格。你必须判断：这种解释是否由题干明确给出，还是由你替题目补全出来的。

**输出要求（严格遵守）：先输出下面的结构化结论，然后再写详细分析。每个 ## 标题必须单独一行。**

## stem_pass
（true 或 false）

## severity
（pass 或 warning 或 blocking）

## issue_types
（列出发现的问题类型，每行一个，用 - 开头。可选：internal_contradiction / stem_semantic_frame_instability / premise_combination_inconsistency / missing_assumption / insufficient_information / no_stem_issue）

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
（列出作用域不明确的关键术语及其可能的作用域）

---

以上为结论部分。以下为详细分析步骤。

第一步：识别总设定和局部设定
- 哪些条件是题干开头的全局系统设定？
- 哪些条件只是某个局部对象的属性？
- 全局设定是否可能统领或影响后续所有对象、容量、地址、运算或过程的理解？

第二步：识别关键术语的作用域
逐项判断题干中的关键术语和数值分别修饰什么对象（数据宽度/地址宽度/虚拟地址/物理地址/主存容量/Cache映射对象/页面大小等）。题干是否明确说明了这一点？

第三步：进行反善意解释检查
不要只给出最有利于题干成立的解释。主动寻找是否存在另一种自然读法：
- 是否可能有读者把全局设定套用到后续局部对象？
- 是否需要审题者替题干补全关键作用域？
- 是否只需最小修改一个前提，题目就会显著更稳定？

待审核题干：
{stem}

【Slot Blueprint 参考】
{slot_blueprint}
"""

# ── Gate 2b: Stem Condition Participation Review ─────────────────────

STEM_CONDITION_PARTICIPATION_PROMPT = """\
你是一位非常严格的 408 考试命题审稿人。现在只审核题干前置条件，不看小问、选项、标准答案和解析。

请注意：你的任务不是判断题干中的知识点是否"本身正确"，而是判断这些前置条件是否都对当前题目有命题价值。

有些题干会加入一个本身正确的高级技术条件，但当前题目的数据、运算过程或任务并不会触发该条件。此时该条件虽然不一定造成答案错误，但可能构成无效干扰、考点错配或误导性前提。

**输出要求（严格遵守）：先输出下面的结构化结论，然后再写详细分析。每个 ## 标题必须单独一行。**

## stem_condition_pass
（true 或 false）

## severity
（pass 或 warning 或 blocking）

## condition_usage
（逐行列出每个条件：条件名 | 参与解题(是/否) | 影响答案(是/否) | 可删除(是/否) | 风险等级）

## issue_types
（列出问题类型，每行一个，用 - 开头：concept_instance_mismatch / misleading_high_salience_condition）

## minimal_fix
（最小修改建议，如通过则为"无"）

## can_continue_to_later_review
（true 或 false）

---

以上为结论部分。以下为详细分析。

第一步：列出题干中的所有显性技术条件
包括但不限于：字长、编址方式、数据格式、运算规则、舍入方式、存储/地址相关设定、访问方式、缺失/阻塞/溢出/异常等边界条件。

第二步：判断每个条件是否会参与当前题目的解题
对每个条件回答：
1. 它是否会影响当前题目的计算过程？
2. 它是否会影响最终答案？
3. 如果删除该条件，题目是否仍然可以唯一求解？
4. 它是否暗示了某个高级考点，但当前实例并没有真正触发该考点？

第三步：特别检查高级技术条件
警惕：舍入模式、溢出/下溢规则、缺页/Cache缺失/流水线阻塞、中断/DMA等。
不能只说"它本身正确"。必须判断：当前数据是否真的触发它？当前题目是否真的考查它？它是否只是装饰性或误导性信息？

待审核题干：
{stem}
"""

# ── Gate 2c: Stem Terminology Precision Review ───────────────────────

STEM_TERMINOLOGY_PRECISION_PROMPT = """\
你是一位严格的 408 考试命题术语审稿人。现在只审核题干中的专业术语是否准确、标准、完整，不审核答案和解题过程。

请检查：
1. 题干中的专业术语是否符合大纲、教材或标准常用表达；
2. 是否存在口语化简写；
3. 简写是否会省略关键限定条件；
4. 是否可能把一个条件性概念误写成无条件概念；
5. 是否可能让考生误解该术语的作用范围。

**输出要求（严格遵守）：先输出下面的结构化结论，然后再写详细分析。每个 ## 标题必须单独一行。**

## terminology_pass
（true 或 false）

## severity
（pass 或 warning 或 blocking）

## issues
（对每个有问题的术语逐一列出：术语名、问题类型(terminology_imprecision/concept_description_error/ambiguous_term)、详细说明、建议标准表达。如无问题则写"无"）

## can_continue_to_later_review
（true 或 false）

---

以上为结论部分。以下为详细分析。

请特别注意以下术语的精确使用：
- IEEE 754 舍入模式（就近舍入、向零舍入、向正无穷舍入、向负无穷舍入）；
- 补码、移码、原码、反码；
- 机器字长、指令字长、存储字长；
- 虚拟地址、物理地址、逻辑地址；
- Cache 命中、TLB 命中、缺页；
- 中断、异常、系统调用；
- 同步、互斥、阻塞、死锁；
- 码距、纠错、检错；
- 网络中的帧、分组、报文段、报文。

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
  "semantic_frame": "一句话概括题干的语义框架（如：32位VA/28位PA系统中的TLB和Cache地址映射分析）",
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
5. 可报告的问题类型：
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
