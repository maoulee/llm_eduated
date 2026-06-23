# core_new/slot_prompts.py
"""Prompts for slot-template driven extraction, composition, and generation.

Extraction (slot_extractor.py):
  SLOT_SINGLE_EVAL_PROMPT_SC/COMP — per-question K-rating evaluation
  SLOT_SYNTHESIS_PROMPT_SC/COMP — per-slot pattern synthesis

Composition (compose/):
  PAPER_OUTLINE_PROMPT — paper outline from slot contracts
  OUTLINE_REVISION_PROMPT — outline revision prompt

Generation (doc_pipeline AgentMD):
  Agents defined in core_new/doc_pipeline/agents/*.md

Knowledge:
  K_RADAR_DEFINITIONS — K1-K5 cognitive radar scoring rubrics
"""

SLOT_SINGLE_EVAL_PROMPT_SC = """你是一位408考研教研专家。请对以下**选择题**进行深度分析，产出单题经验文档。

{cognitive_radar_scale}

---

{_syllabus_ref}

---

## 题目信息

- **年份**: {year}
- **题位**: {slot_id}
- **考点**: {primary_target_name}
- **知识领域**: {target_family}

## 题干原文

{question_stem}

## 分析参考

- **正确答案原因**: {why_correct}
- **错误选项分析**: {why_wrong_options}
- **干扰项模式**: {distractor_patterns}
- **陷阱风格**: {trap_style}
- **选项风格**: {option_style}
- **推理形态**: {reasoning_shape}

---

## 分析要求

选择题的考察逻辑不是"第一步、第二步"的线性轨迹，而是**选项级考察**——每个选项是一个独立的命题/计算结果，学生需要逐一判断。请按以下维度分析：

### Part A: K1-K5 评分
### Part B: 选项级分析 — 每个选项考察什么，针对什么错误认知
### Part C: 考察模式分类（从以下5种中选择最匹配的）：
  - Mode_A 计算型：题干给参数，4个选项是4个计算结果，只有一个算对
  - Mode_B 概念辨析型：选项是命题判断，需识别正确/错误命题
  - Mode_C 机制理解型：选项对应不同的底层机制理解
  - Mode_D 代码/数据分析型：题干给代码或数据，选项是分析结论
  - Mode_E 组合判断型：题干列多个陈述I/II/III，选项是不同组合

### Part D: 考纲映射

---

请严格按以下 Markdown 格式输出：

## evaluation
- **K1**: N — （理由 + 为什么不是N-1或N+1）
- **K2**: N — （理由 + 为什么不是N-1或N+1）
- **K3**: N — （理由 + 为什么不是N-1或N+1）
- **K4**: N — （理由 + 为什么不是N-1或N+1）
- **K5**: N — （理由 + 为什么不是N-1或N+1）
- **radar_shape_name**: 根据最高分维度命名（如 K4陷阱型、K3推演型、K1概念型、K2计算型）
- **reasoning_shape**: one_formula / multi_step / elimination / simulation
- **reasoning_shape_reason**: 为什么是这个推理形式（一句话）

## 知识点与考纲
- **知识点**: 本题考察的核心知识点（1-3个，逗号分隔）
- **考纲对应**: 考纲章节路径（如：第三章 存储器层次结构 → Cache → 映射方式）
- **knowledge_tags**: 从细纲中选择本题**正确答案所涉及**的核心知识点（1-3个，最多3级层级，用 > 分隔，逗号分隔多项。只标记正确选项对应的知识域，干扰项涉及的次要知识点不要列入。如：CO-2 > 定点数的运算 > 补码加减运算, CO-1 > 计算机系统概述）

## 选项级分析
- **选项A**: [正确/干扰] — 针对什么认知错误，哪类学生会选
- **选项B**: [正确/干扰] — 针对什么认知错误，哪类学生会选
- **选项C**: [正确/干扰] — 针对什么认知错误，哪类学生会选
- **选项D**: [正确/干扰] — 针对什么认知错误，哪类学生会选
- **干扰策略**: 并行陷阱（各干扰项独立）/ 嵌套陷阱（核心误解层层递进）/ 渐进陷阱（看似合理的错误推理链）
- **干扰策略说明**: （一句话）

## 考察模式
- **mode_label**: Mode_A / Mode_B / Mode_C / Mode_D / Mode_E
- **mode_name**: 计算型 / 概念辨析型 / 机制理解型 / 代码数据分析型 / 组合判断型
- **mode_reason**: 为什么是这个模式（一句话）

## 核心陷阱
- **核心陷阱**: 题目中设计的主要陷阱
- **错误路径**: 学生容易走错的路径

## 考察能力
（一句话总结这道题考察的核心能力）
"""

# ═══════════════════════════════════════════════════════════════
# Per-question evaluation — Comprehensive Questions (COMP)
# ═══════════════════════════════════════════════════════════════

SLOT_SINGLE_EVAL_PROMPT_COMP = """你是一位408考研教研专家。请对以下**综合应用题**进行深度分析，产出单题经验文档。

{cognitive_radar_scale}

---

{_syllabus_ref}

---

## 题目信息

- **年份**: {year}
- **题位**: {slot_id}
- **考点**: {primary_target_name}
- **知识领域**: {target_family}

## 题干原文

{question_stem}

## 分析参考

- **正确答案原因**: {why_correct}
- **解题步骤**: {solution_steps}
- **陷阱风格**: {trap_style}
- **推理形态**: {reasoning_shape}
- **出题角色**: {paper_role}（{paper_role_reason}）

---

## 分析要求

综合应用题具有真正的多步推导轨迹和子问依赖关系。请按以下维度分析：

### Part A: K1-K5 评分
### Part B: 子问依赖 — 各子问之间的逻辑关系（串行/并行/混合）
### Part C: 解题轨迹 — 每步执行什么操作、基于什么规则、得到什么中间结果
### Part D: 条件利用映射 — 每个给定条件在哪个子问中使用
### Part E: 考纲映射

---

请严格按以下 Markdown 格式输出：

## evaluation
- **K1**: N — （理由 + 为什么不是N-1或N+1）
- **K2**: N — （理由 + 为什么不是N-1或N+1）
- **K3**: N — （理由 + 为什么不是N-1或N+1）
- **K4**: N — （理由 + 为什么不是N-1或N+1）
- **K5**: N — （理由 + 为什么不是N-1或N+1）
- **radar_shape_name**: 根据最高分维度命名
- **reasoning_shape**: one_formula / multi_step / elimination / simulation
- **reasoning_shape_reason**: 为什么是这个推理形式（一句话）

## 知识点与考纲
- **知识点**: 本题考察的核心知识点（1-3个，逗号分隔）
- **考纲对应**: 考纲章节路径
- **knowledge_tags**: 从细纲中选择本题**正确答案所涉及**的核心知识点（1-3个，最多3级层级，用 > 分隔，逗号分隔多项。只标记主考点对应的知识域，干扰项涉及的次要知识点不要列入。如：CO-3 > 高速缓冲存储器 Cache, CO-4 > 指令系统）

## 子问依赖
- **sub_q_count**: 子问数量
- **dependency_type**: serial / parallel / mixed
- **sub_q1**: （内容摘要）— （预期解法）— （是否依赖前置子问）
- **sub_q2**: （同上结构）
- （如有更多子问继续列出）

## 解题轨迹
1. （第一步具体操作：执行什么，基于什么规则，得到什么）
2. （第二步具体操作）
3. （继续，直到得到最终答案）

## 条件利用映射
- **条件1**: 在子问X中用于Y
- **条件2**: 在子问X和Z中使用
- **未使用条件**: 无 / （列出）

## 关键考察点
（1-2句话：区分会做和不会做的核心认知要求）

## 陷阱机制
- **核心陷阱**: 主要陷阱设计
- **错误路径**: 学生容易走错的路径

## 考察能力
（一句话总结）
"""

# Keep old name as alias for backward compatibility
SLOT_SINGLE_EVAL_PROMPT = SLOT_SINGLE_EVAL_PROMPT_SC

# ═══════════════════════════════════════════════════════════════
# Per-slot synthesis — Choice Questions (SC)
# ═══════════════════════════════════════════════════════════════

SLOT_SYNTHESIS_PROMPT_SC = """你是一位408考研教研专家。请基于以下选择题题位的所有历史题目，归纳该题位的**考察模式**。

## 核心原则

选择题的考察逻辑是**选项级考察**，而非"第一步、第二步"的线性轨迹。
模式应按**考察方式**（怎么考）分类，知识点只是模式的适用范围。

## 题位信息

- **题位**: {slot_id}
- **科目**: {subject_stability}
- **题型**: 选择题
- **分值**: {typical_score}
- **题目数量**: {question_count}

## 历年题目数据

{evaluations_data}

## 分析任务

基于以上每道题的选项级分析和考察模式，按**考察方式**归纳出该题位的模式分类。

考察模式分类维度：
1. **考察方式**: 计算型（4个选项是4个计算结果）/ 概念辨析型（选项是命题判断）/ 机制理解型（选项对应不同机制理解）/ 代码数据分析型 / 组合判断型（I/II/III组合）
2. **选项架构**: 选项之间的结构关系（四选一竞争 / 真假命题判断 / 范围比较 / 机制匹配）
3. **干扰策略**: 并行陷阱（各干扰项独立）/ 嵌套陷阱（核心误解层层递进）/ 渐进陷阱

请直接输出 Markdown 文档（不要用代码块包裹），按以下结构：

## 考察模式分布

（列出各模式出现频率）

## 模式A: （模式命名，如"计算型——四结果竞争"）
- **出现频率**: X/{question_count}
- **考察方式**: （具体描述题干给出什么，选项是什么结构）
- **选项架构**: （选项之间的关系结构）
- **常见参数类型**: （如主频/CPI、地址/容量、概率/比率）
- **常见陷阱类型**: （如单位换算、比率倒置、符号错误）
- **典型干扰策略**: （描述典型干扰项设计手法）
- **适用知识点范围**: （哪些知识点会使用这个考察方式）
- **参考题**: 使用这个模式的历史题目年份
- **难度范围**: K值典型范围

## 模式B: （另一个考察模式）
（同上结构）

## 往年真题题干（供出题智能体检索参考）

对每道历史题目，给出**完整题干原文**和简要模式标签：

### YYYY年 — 考点名称
**题干**: （完整题干原文）
**考察模式**: Mode_X  **选项架构**: xxx  **雷达形状**: Kx型

### YYYY年 — 考点名称
**题干**: （完整题干原文）
**考察模式**: Mode_X  **选项架构**: xxx  **雷达形状**: Kx型

（每道历史题目一个条目）

## 出题指导
- **should_be**: 这个题位应该出什么样的题
- **should_not_be**: 这个题位不应该出什么样的题
- **建议选项风格分布**: {{"数字结果": X%, "概念判断": Y%, ...}}
- **建议考察模式分布**: {{"计算型": X%, "概念辨析": Y%, ...}}

## slot_synthesis（供程序解析，必须放在最后）

- **K1_mode**: N
- **K1_range**: [x, y]
- **K2_mode**: N
- **K2_range**: [x, y]
- **K3_mode**: N
- **K3_range**: [x, y]
- **K4_mode**: N
- **K4_range**: [x, y]
- **K5_mode**: N
- **K5_range**: [x, y]
- **radar_shape**: 典型雷达形状
- **reasoning_shape_mode**: 最常见推理形式
- **pattern_count**: 归纳出的模式数量
- **representative_years**: 代表年份，逗号分隔
"""

# ═══════════════════════════════════════════════════════════════
# Per-slot synthesis — Comprehensive Questions (COMP)
# ═══════════════════════════════════════════════════════════════

SLOT_SYNTHESIS_PROMPT_COMP = """你是一位408考研教研专家。请基于以下综合应用题题位的所有历史题目，归纳该题位的**结构性考察模式**。

## 核心原则

综合应用题具有真正的多步推导轨迹。模式描述的是"第一步做什么、第二步做什么"的**结构性考察逻辑**。
不同知识点的题目可能共享同一种考察结构（如"先算基础参数→再模拟过程→最后分析结果"），你需要识别这种跨知识点的结构共性。

## 题位信息

- **题位**: {slot_id}
- **科目**: {subject_stability}
- **题型**: 综合应用题
- **分值**: {typical_score}
- **题目数量**: {question_count}

## 历年题目数据

{evaluations_data}

## 分析任务

基于以上每道题的解题轨迹和子问依赖，按**考察结构**归纳出该题位的结构性模式。

每种模式应回答：这个题位下，题目是如何"一步步考察"学生的？子问之间什么依赖关系？

请直接输出 Markdown 文档（不要用代码块包裹），按以下结构：

## 子问模式
- **典型子问数量**: 2-4
- **典型依赖类型**: 串行推进 / 混合（哪些串行，哪些并行）
- **典型子问角色分布**:
  - 第一问: 参数计算 / 机制推导（基础）
  - 中间问: 过程模拟 / 状态跟踪（核心）
  - 最后一问: 结果分析 / 比较 / 边界讨论（区分度）

## 考察结构模式

### 模式A: （模式命名）
- **考察逻辑**: 这个模式的总考察逻辑（一句话）
- **第一步**: 第一步让学生做什么
- **第二步**: 第二步做什么
- **第三步**: （如有更多步骤继续列出）
- **典型陷阱**: 这个模式中最常见的陷阱类型
- **适用知识点**: 哪些知识点会使用这个考察结构
- **参考题**: 使用这个模式的历史题目年份
- **难度范围**: K值典型范围

### 模式B: （另一个结构性模式）
（同上结构）

## 往年真题题干（供出题智能体检索参考）

对每道历史题目，给出**完整题干原文**和简要模式标签：

### YYYY年 — 考点名称
**题干**: （完整题干原文）
**结构模式**: 模式X  **子问数**: N  **依赖类型**: serial/parallel/mixed  **雷达形状**: Kx型

（每道历史题目一个条目）

## 出题指导
- **should_be**: 这个题位应该出什么样的题
- **should_not_be**: 这个题位不应该出什么样的题

## slot_synthesis（供程序解析，必须放在最后）

- **K1_mode**: N
- **K1_range**: [x, y]
- **K2_mode**: N
- **K2_range**: [x, y]
- **K3_mode**: N
- **K3_range**: [x, y]
- **K4_mode**: N
- **K4_range**: [x, y]
- **K5_mode**: N
- **K5_range**: [x, y]
- **radar_shape**: 典型雷达形状
- **reasoning_shape_mode**: 最常见推理形式
- **pattern_count**: 归纳出的模式数量
- **representative_years**: 代表年份，逗号分隔
"""

# Keep old name as alias
SLOT_SYNTHESIS_PROMPT = SLOT_SYNTHESIS_PROMPT_SC

# ═══════════════════════════════════════════════════════════════
# V1: Legacy composition prompt (20+ fields/slot, design-level decisions)
# DEPRECATED: Use PAPER_OUTLINE_PROMPT instead (8 fields/slot, outline only)
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
- **difficulty_profile**: {{"knowledge_depth": N, "reasoning_steps": N, "calculation_load": N}}
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
- **difficulty_profile**: {{"knowledge_depth": N, "reasoning_steps": N, "calculation_load": N}}
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

# ═══════════════════════════════════════════════════════════════
# V2: Outline-based composition (decoupled from question design)
# ═══════════════════════════════════════════════════════════════

PAPER_OUTLINE_PROMPT = """你是一位408考研组卷专家，以教师的视角规划试卷大纲。大纲同时面向教师阅读和下游出题智能体。

上方已展示共享参考信息（K1-K5认知雷达评分标准 + 知识点图谱），下方是各题位信息。

## 用户需求
{user_requirements}

## 各题位信息
{slot_contracts_md}

## 规划原则

1. **锚定题位**：每个题位有固定的题型和分值，为每个题位指定具体考点和考察方向
2. **知识点编排**：参考上方的知识点图谱，确保整套试卷覆盖主要知识域（CO-1 到 CO-7），避免连续多题考同一知识点
3. **难度曲线**：前段基础稳定，中段适度区分，后段拉开差距
4. **考察模式选择（最严格约束）**：每个题位信息中有"可选考察模式"列表，格式如 `### 模式A: 计算型——xxx (7/13, 53.8%)`。你的 examination_mode 必须是模式标题中 `### 模式X:` 后面的**完整名称**（不含频率括号）。禁止任何变形：
   - 禁止：只写"计算型"、"概念辨析型"（丢失了细粒度描述）
   - 禁止：添加英文翻译
   - 禁止：自创模式名
   - 正确：`计算型——公式应用与单位换算`、`概念辨析型——核心定义与本质区分`
5. **知识点选择**：每个模式都有"适用知识点"字段，你的 primary_target_name 应该是该模式适用知识点中的一个具体考点

## 输出格式（Outline v2）

请严格按以下格式输出完整大纲。大纲包含**人读层**（教师可读）和**机器契约层**（系统解析）。

```markdown
# 试卷大纲

## 整体规划
- **difficulty_target**: 整体难度目标（1-5整数）
- **composition_rationale**: 整卷组卷思路（2-3句话）

## 1. 教师阅读版总览

用2-3段自然语言描述整卷定位、知识点覆盖策略和难度分布逻辑。
附题位总览表格：

| 题位 | 题型 | 主考点 | 难度 | 考察目标 |
|------|------|--------|------|----------|
| Q12 | 选择题 | CPU执行时间公式 | 3 | 公式应用与单位换算 |

## Q12（选择题）

### 当前推荐

- **考察模式**: 计算型——公式应用与单位换算
- **核心知识点**: CPU执行时间公式、单位换算（性能公式、CPI、时钟频率）
- **推荐理由**: 该模式在Q12题位出现频率53.8%，结合K1-K2平衡型，适合考察学生对基础公式的掌握和计算能力

### 候选替换池

- **模式A**: 计算型——公式应用与单位换算（适合考察CPU性能公式、存储容量计算）
- **模式B**: 概念辨析型——核心定义与本质区分（适合考察指令系统、中断机制等概念）
- **模式C**: 逻辑推理型——指令执行过程分析（适合考察指令流水线、中断响应流程）
- **模式D**: 综合判断型——多场景方案选择（适合考察Cache映射策略、替换算法选择）

### 教师可编辑说明

用自然语言描述：考查什么知识点、定位什么难度、对学生的能力要求、可能的风险点。教师可在此区域添加备注或修改意见。

### 机器选择契约
```yaml
slot_id: Q12
question_type: single_choice
score: 2
target_subject: CO
target_family: 计算机组成原理 > CPU > 性能指标
primary_target_name: CPU执行时间公式
target_difficulty: 3
k_target: K2
examination_mode: 计算型——公式应用与单位换算

active_selection:
  mode_id: 模式A
  mode_name: 计算型——公式应用与单位换算
  selected_knowledge:
    - CPU执行时间公式
    - 单位换算
    - 性能公式

candidate_pool_visible:
  - 模式A
  - 模式B
  - 模式C
  - 模式D

excluded:
  modes: []
  knowledge: []
```

## Q13（选择题）
（每个题位同上，含当前推荐 + 候选替换池 + 教师可编辑说明 + 机器选择契约）
```

注意：
- **examination_mode 必须精确复制自题位的"可选考察模式"标题，不含频率括号**
- 综合应用题（Q43-Q45）的 examination_mode 写模式标题（如"存储层次地址翻译与映射模拟"）
- 每个 `## Qxx` 标题后注明题型
- **候选替换池**列出该题位所有可选模式（模式A/B/C/D），教师可删除不想考的模式
- **机器选择契约**的 YAML 代码块必须完整，字段名和格式不可变更
- 系统只解析机器选择契约，不从教师的自然语言描述猜测结论
- 不要输出选项风格、干扰策略、推理形式等设计级决策——这些由出题团队自主决定
"""

OUTLINE_REVISION_PROMPT = """你是一位408考研组卷专家。教师对以下试卷大纲提出了修订意见，请根据意见修订大纲。

## 修订规则

1. **只修改被标注的题位**：未变更的题位保持原样，完整输出不要省略
2. **同步更新四个层次**：
   - `### 当前推荐`：反映修订后的考察模式和知识点选择
   - `### 候选替换池`：如教师删除了某个模式，将其从池中移除
   - `### 教师可编辑说明`：用自然语言反映修订后的意图
   - `### 机器选择契约`：YAML 字段同步更新
3. **根据 diff 同步 active_selection**：
   - 如果教师在候选替换池中删除了某个模式，将其加入 `excluded.modes`
   - 如果教师在当前推荐中删除了某个知识点，将其加入 `excluded.knowledge`
   - 如果教师切换了模式，更新 `active_selection.mode_id` 和 `mode_name`
   - `candidate_pool_visible` 只保留未被教师删除的模式
4. **不恢复教师删除的内容**：如果教师明确删除了某个模式或知识点，不要在修订中恢复
5. **契约合法性**：examination_mode 必须仍在题位可选列表中，target_difficulty 在 1-5 范围内
6. **连带更新**：如果修订影响整卷难度分布，也更新 `## 整体规划` 和 `## 1. 教师阅读版总览`

## 修订前大纲
{original_outline}

## 检测到的变更（diff 格式）
{detected_changes}

## 各题位信息（用于验证 examination_mode 合法性）
{slot_contracts_md}

## 输出
输出完整的修订后大纲（格式与修订前一致）。不要省略未修改的题位，完整输出所有题位。
"""

# DEPRECATED: References old blueprint format with design-level fields (option_style, reasoning_shape etc.)
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

SUBJECTIVE_DRAFT_ONLY_PROMPT = """你是一位408考研出题专家。请根据以下设计方案，出一道综合应用题。

## 题目设计方案
{question_design_md}

## 出题要求
- 综合应用题不设计选项，只有题干和子问
- 严格按照设计方案中的子问设计出题，每个子问对应方案的考察内容
- 参数必须自洽，确保题目有唯一确定解
- 题目必须完全原创
- 只出题和写设计意图，不写答案
- **禁止在stem中输出任何编程语言代码**（如C语言main函数、Python函数、#include、print语句等）。如需展示指令序列，使用伪指令格式（如 `ADD R1, R2, R3`），不要使用任何编程语言的完整代码结构

## 设计意图（重要！）
你必须写清楚：
1. 每个子问期望考察什么知识点/能力
2. 预期的解题路径是什么（用什么公式/方法/步骤）
3. 陷阱设计（如果有的话，学生容易犯什么错）
4. 各子问之间的逻辑关系

请严格按以下markdown格式输出：

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

SUBJECTIVE_QUESTION_REVIEW_PROMPT = """你是一位408考研出题对抗审核员。你的目标是主动攻破这道综合应用题，而不是确认它"没问题"。只有你真的找不到可以攻破的点时，才判 pass。

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

## 对抗审核策略

### 第一轮：攻击题目条件
1. 把所有给定条件放在一起，检查是否存在参数矛盾或隐含冲突
2. 检查是否缺少关键条件（需要善意补全才能求解的条件）
3. 尝试对题干做不同理解，看是否能得到不同答案

### 第二轮：攻击解题结果
4. 不信任解题结果。自己重新推导关键计算步骤，看是否与给出答案一致
5. 检查子问题之间的逻辑链是否完整，有没有跳步或隐含假设
6. 检查边界情况（零值、溢出、极端参数）是否被正确处理

### 第三轮：攻击设计与蓝图匹配
7. 考点是否真的匹配蓝图？还是表面匹配实质偏离？
8. 难度和计算量是否与蓝图一致？
9. 评分标准是否覆盖了所有子问的关键步骤？

### 第四轮：攻击认知雷达匹配
10. 对比设计方案的 target_K1-K5 与题目实际的认知需求
11. 实际 K4≥4 但设计 K4=2 → 题目挖了意料之外的深坑
12. 实际 K5≤1 但设计 K5=3 → 跨域联动没有实现
13. 实际 K3≥4 但设计 K3=2 → 推演链过长超出设计意图

## 修复路由（关键！）

请按以下优先级判断 fix_target：

1. **参数矛盾**：题目的给定条件自相矛盾或物理上不可能 → fix_target=question
2. **设计偏离**：题目设计不符合蓝图（考点偏了、难度不对、子问题数量不对）→ fix_target=question
3. **结构缺陷**：子问题缺失、编号错误、缺少关键已知条件 → fix_target=question
4. **答案计算错误**：题目设计合理但解题者计算出错 → fix_target=answer
5. **如果都攻不破** → pass

注意：不要因为答案错误就盲目路由到 answer。先检查题目条件是否合理，如果题目本身有问题，必须路由到 question。

请严格按以下markdown格式输出：

# review {slot_id}

## 结果
- **status**: pass 或 revise
- **score**: 0-100
- **needs_fix**: yes 或 no
- **attack_summary**: 你尝试了哪些攻击策略，哪些成功/失败

## 检查
- **design_vs_blueprint**: pass 或 fail（题目设计是否符合蓝图要求）
- **intent_vs_answer**: pass 或 fail（出题意图与解题结果是否匹配）
- **answer_correctness**: pass 或 fail（答案计算是否正确）
- **sub_question_count_match**: pass 或 fail
- **calculation_load_match**: pass 或 fail
- **rubric_match**: pass 或 fail
- **actual_K1**: 1-5（实际基础认知需求）
- **actual_K2**: 1-5（实际单步代入需求）
- **actual_K3**: 1-5（实际机制推演需求）
- **actual_K4**: 1-5（实际条件路由需求）
- **actual_K5**: 1-5（实际跨域联动需求）
- **radar_match**: pass 或 fail（设计与实际认知雷达是否匹配，附说明）

## 修复指令（pass时写"无"）
- **issue**: 具体问题描述
- **fix_target**: question（题目设计问题，需重新出题）或 answer（答案问题，只需重新解题）
- **fix_instruction**: 具体修复指令
"""

# ═══════════════════════════════════════════════════════════════
# Merged Design prompt (Architecture + Design in one step)
# ═══════════════════════════════════════════════════════════════

SUBJECTIVE_DESIGN_MERGED_PROMPT = """你是一位408考研出题专家。你需要直接基于题位考察理念和蓝图要求，为一道综合应用题完成从结构规划到题目撰写的全部工作。

{k_definitions}

---

## 题位设计哲学

{slot_philosophy}

---

## 工具指引

1. 设计哲学已预注入上方，**不需要调用 `read_slot`**。直接基于上方设计哲学和蓝图出题。
2. 结合下方蓝图要求，完成出题
3. 你是纯设计环节，**不使用任何工具**。参数验证由后续 ParameterVerifier 步骤完成。

## 参数设计要求

设计数值参数时，请确保：
- 参数之间逻辑自洽（如地址位数足够、容量参数匹配）
- 题目有唯一确定解
- 给出的条件充分且无矛盾

你不需要手动计算或验证数值，只需确保参数设计意图合理。后续 ParameterVerifier 会用代码验证参数一致性。

## 蓝图要求

{blueprint_md}

---

## 出题核心规则

### 条件一致性（红线）

- **禁止"复杂条件+简化假设"反模式**：不允许在题干前半部分描述复杂的机制/约束/条件，然后在后半部分用一句"简化模型""假设xxx"将这些条件全部作废。所有给出的条件必须在解题中被实质性使用。
- **条件利用率100%**：每个给定条件都必须在解题路径中发挥作用。不允许出现"给了但不用"的废弃条件。如果一个条件对解题没有影响，就不要给出。
- **条件无矛盾**：所有条件之间不得存在逻辑冲突或物理上不可能的组合。

### 条件给法

严格遵循题位设计理念中的条件分层：
- **显式给出**：设计理念中标注"应显式给出"的参数和数据
- **隐含/推导**：设计理念中标注"应留给学生推导"的内容，不在题干中直接揭示
- **留白**：设计理念中标注"留白"的部分，通过描述物理过程而非给公式来引导学生建模

### 出题约束

- 综合应用题不设计选项，只有题干和子问
- 子问数量、分值由蓝图参数控制
- 参数必须自洽，确保题目有唯一确定解
- 题目必须完全原创
- 只出题和写设计意图，不写答案
- **禁止在stem中输出任何编程语言代码**（如C语言main函数、Python函数、#include、print语句等）。如需展示指令序列，使用伪指令格式（如 `ADD R1, R2, R3`），不要使用任何编程语言的完整代码结构

---

## 输出格式

请严格按以下markdown格式输出（不要用代码块包裹）：

# question {{slot_id}}

## 题目
- **stem**: 题干全文（包含所有已知条件和背景描述）
- **sub_questions**: 子问列表，JSON数组格式，如 ["(1) 子问1内容", "(2) 子问2内容", "(3) 子问3内容"]
- **given_conditions**: 题目给出的所有已知条件，JSON数组格式
- **difficulty_self_assessment**: 1-5自评难度
- **knowledge_points**: 知识点1, 知识点2
- **parameter_notes**: 参数设计说明（为什么选这些参数，确保可解性）

## 推理模式
- **reasoning_form**: multi_step / simulation / one_formula / elimination（本题的主要推理形式）
- **reasoning_rationale**: 选择这个推理形式的理由（一句话说明解题过程的结构特征）
- **condition_utilization**: 每个给定条件如何在解题中被使用（逐条说明，确保无废弃条件）

## 设计意图
- **sub_q1_intent**: 第1问期望考察什么知识点/能力，预期解题路径
- **sub_q2_intent**: 第2问期望考察什么知识点/能力，预期解题路径
- **sub_q3_intent**: 第3问期望考察什么知识点/能力，预期解题路径（如有更多子问继续列出）
- **trap_design**: 陷阱设计说明（学生容易犯的错误，无陷阱写"无"）
- **sub_question_logic**: 各子问之间的逻辑关系（递进/并列/依赖，一句话说明）

## 自检清单
- **parameter_consistency**: PASS/FAIL — 说明（参数之间是否自洽，有无矛盾）
- **no_contradiction**: PASS/FAIL — 说明（所有条件之间是否存在逻辑冲突）
- **unique_solution**: PASS/FAIL — 说明（题目是否有唯一确定解）
- **reasoning_path_complete**: PASS/FAIL — 说明（推理路径是否完整无跳步）
- **all_conditions_used**: PASS/FAIL — 说明（每个条件是否都在解题中被使用，列出每个条件的用途）

**重要**：自检清单中任何一项为 FAIL 时，必须修改题目直到全部 PASS 后再输出。
"""

# ═══════════════════════════════════════════════════════════════
# Merged SC Design prompt (Draft + Options + Self-check in one step)
# ═══════════════════════════════════════════════════════════════

SC_MERGED_DESIGN_PROMPT = """你是一位408考研出题专家。你需要基于题位考察理念和蓝图要求，一次完成选择题的题干、选项和干扰策略设计。

{k_definitions}

---

## 题位设计哲学

{slot_philosophy}

---

## 蓝图要求

{blueprint_md}

---

## 出题核心规则

### 条件一致性
- 每个给定条件都必须在解题中被使用，不允许废弃条件
- 所有条件之间不得存在逻辑冲突

### 选项设计规则
- 4个选项中恰好1个正确答案，答案必须唯一确定
- 每个干扰项必须有明确的"为什么有人会选错"的理由
- 选项格式根据蓝图的 option_style 决定（数字结果/概念判断/组合判断）
- 数字型选项的4个值应覆盖常见错误路径（如：漏算系数、公式倒置、单位混淆）
- 概念型选项应使用易混淆的相似概念作为干扰

### 数值参数
- 参数设计只需确保意图合理，不需要手动精确计算
- 后续代码求解器会验证所有数值的准确性
- 避免需要超出常规精度的数值（如超过8位有效数字的浮点数）

### 其他约束
- 题目必须完全原创
- **禁止在题干中出现任何编程语言代码**（如C语言main函数、Python函数等）
- 题干应简洁精炼，避免冗长的背景描述

---

## 输出格式

请严格按以下markdown格式输出（不要用代码块包裹）：

# question {slot_id}

## 题目
- **stem**: 题干全文（包含所有已知条件和问题）
- **given_conditions**: 题目给出的所有已知条件，JSON数组格式
- **difficulty_self_assessment**: 1-5自评难度
- **knowledge_points**: 知识点1, 知识点2

## 选项
- **option_A**: 选项A内容
- **option_B**: 选项B内容
- **option_C**: 选项C内容
- **option_D**: 选项D内容
- **correct_answer**: 正确选项字母（A/B/C/D）
- **option_style_used**: 数字结果 或 概念判断 或 组合判断

## 干扰策略
- **distractor_intent_A**: 误选原因（正确选项写"正确选项"）
- **distractor_intent_B**: 误选原因
- **distractor_intent_C**: 误选原因
- **distractor_intent_D**: 误选原因（正确选项写"正确选项"）

## 自检清单
- **blueprint_compliance**: PASS/FAIL — 考点是否匹配蓝图要求
- **difficulty_alignment**: PASS/FAIL — 难度是否匹配蓝图的 difficulty_level
- **option_uniqueness**: PASS/FAIL — 正确答案是否唯一确定
- **no_contradiction**: PASS/FAIL — 所有条件之间是否存在矛盾
- **reasoning_hint**: 预期解题路径（一句话）

**重要**：自检清单中任何一项为 FAIL 时，必须修改题目直到全部 PASS 后再输出。"""

# ═══════════════════════════════════════════════════════════════
# V2: Outline-driven question generation (3-stage pipeline)
# ═══════════════════════════════════════════════════════════════

SC_QUESTION_PROMPT = """你是一位408考研出题专家。请按以下三步流程完成出题。

参考文档中已包含本次出题要求（考点、难度、考察模式）和选定模式的完整资料（考察方式、选项架构、陷阱类型、参考真题、K锚点、K雷达定义）。

你有 `python_exec` 工具可用于代码验证。

---

{reference_doc}

---

## 工作流程（严格按顺序执行）

### Step 1: 选定知识点
阅读参考文档，从中选定本题考察的具体知识点组合：
- 从"本次出题要求"获取考点和难度目标
- 从"模式概览"获取考察方式和选项架构
- 从"往年真题经验"中参考同类题的知识点选取
- 从"相关细纲"中确认知识点的精确范围
- 自主决定必含和避免的内容

### Step 2: 设计完整题目
基于 Step 1 的知识点选择，一次性设计：
- 题干：具体参数和情境（数字型参数确保意图合理）
- 4个选项：参考模式概览的"常见陷阱类型"和"典型干扰策略"
- 正确答案
- 干扰策略说明
- 选项形式自主选择（数字结果 / 概念判断 / 组合判断）

### Step 3: 代码验证与调整
对涉及数值计算的题目，使用 python_exec 工具验证：
- **只调用一次 python_exec**，在一段代码中同时验证所有选项的计算结果
- 如果代码结果与设计答案不一致，**以代码结果为准**调整题目
- 检查所有给定条件是否都被使用，是否存在矛盾
- 纯概念题（无计算）可跳过代码验证，基于逻辑自洽判断

### 出题规则
- 条件一致性：每个给定条件都必须在解题中被使用，不允许废弃条件
- 选项唯一性：4个选项中恰好1个正确答案，答案必须唯一确定
- 题目必须完全原创
- **禁止在题干中出现任何编程语言代码**
- 题干应简洁精炼，避免冗长的背景描述

---

## 输出格式

完成三步后，按以下markdown格式输出最终题目（不要用代码块包裹）：

# question {slot_id}

## 题目
- **stem**: 题干全文（包含所有已知条件和问题）
- **given_conditions**: 题目给出的所有已知条件，JSON数组格式
- **difficulty_self_assessment**: 1-5自评难度
- **knowledge_points**: 知识点1, 知识点2
- **selected_knowledge_rationale**: 为什么选这些知识点（一句话）

## 选项
- **option_A**: 选项A内容
- **option_B**: 选项B内容
- **option_C**: 选项C内容
- **option_D**: 选项D内容
- **correct_answer**: 正确选项字母（A/B/C/D）
- **option_style_used**: 数字结果 或 概念判断 或 组合判断

## 干扰策略
- **distractor_intent_A**: 误选原因（正确选项写"正确选项"）
- **distractor_intent_B**: 误选原因
- **distractor_intent_C**: 误选原因
- **distractor_intent_D**: 误选原因（正确选项写"正确选项"）

## 验证结果
- **code_verified**: true 或 false（是否经过代码验证）
- **verified_answer**: 代码验证的正确答案（未验证则与 correct_answer 一致）
- **adjustment_summary**: 代码验证后做了哪些调整（未调整写"无"）
"""

SC_CODE_VERIFY_PROMPT = """你是一位408考研题目校验专家。请用 Python 代码独立计算本题的正确答案，与声称的答案对比。

## 题目
{stem}

## 选项
- A: {option_A}
- B: {option_B}
- C: {option_C}
- D: {option_D}

## 声称的正确答案
{claimed_answer}

## 工具
你有 `python_exec` 工具。请编写代码计算正确答案。

## 规则
- 编写代码独立计算正确答案
- 如果代码结果与声称答案一致 → confirmed
- 如果代码结果与声称答案冲突 → 以代码结果为准，标记 overridden
- 如果无法通过代码验证（纯概念题），基于逻辑推理判断

请严格按以下markdown格式输出：

## 验证结果
- **status**: confirmed 或 overridden 或 unverifiable
- **verified_answer**: 代码验证的正确答案（选项字母）
- **code_summary**: 代码计算过程摘要（1-2句）
- **conflict_detail**: 冲突详情（无冲突写"无"）
"""

SC_REVIEW_PROMPT = """你是一位408考研出题对抗审核员。你的目标不是确认题目"没问题"，而是主动寻找题目的每一个潜在缺陷。

## 大纲要求
{outline_entry_md}

## 题目
- **题干**: {stem}
- **选项A**: {option_A}
- **选项B**: {option_B}
- **选项C**: {option_C}
- **选项D**: {option_D}

## 代码校验结果
{code_verify_result}

## 工具
你有 `python_exec` 工具，可以对有疑问的计算进行独立验证。

## 审核策略

### 第一轮：验证答案
用不同方式重新求解，确认答案唯一正确。如果代码校验已确认且你自己也确认，进入下一轮。

### 第二轮：攻击选项
- 错误选项是否"太明显是错的"？
- 正确答案是否真的唯一？
- 选项之间是否有逻辑包含关系导致排除法秒杀？

### 第三轮：攻击题干
- 是否有歧义表述导致答案不唯一？
- 条件是否自洽？
- 是否缺少必要条件？

### 第四轮：大纲匹配
- 考点是否匹配大纲的 primary_target_name？
- 难度是否匹配 target_difficulty？

## 判定规则
- 找到实质性问题 → needs_fix
- 无法攻破 → pass
- 不要把润色建议判为问题

请严格按以下markdown格式输出：

## review
- **status**: pass 或 needs_fix
- **verified_answer**: 最终确认的正确答案
- **attack_summary**: 尝试了哪些攻击，哪些成功/失败
- **outline_match**: pass 或 fail（考点是否匹配大纲）
- **difficulty_match**: pass 或 fail（难度是否匹配）
- **option_quality**: pass 或 fail（干扰项质量）
- **expression_quality**: pass 或 fail（表述精确性）
- **overall_quality**: 1-10
- **comment**: 总体评价（2-3句话）

## 解析
- **explanation**: 完整解析（先结论后分析）
- **key_steps**: 步骤1; 步骤2; 步骤3（分号分隔）

## fix_instruction
（如果 status=needs_fix，说明需要修复什么；pass 写"无"）
"""

# ── 共享常量 ────────────────────────────────────────────────────

K_RADAR_DEFINITIONS = """\
## K1-K5 认知雷达评分标准（必须严格参照）

K1 基础认知需求（需要调用概念/术语/公式记忆的程度）:
  1=微弱: 仅需日常常识词汇，几乎不需要 408 专业记忆
  2=较低: 需要 408 基础名词，但概念模糊也能顺着题干做
  3=标准: 必须准确记忆某个核心概念/公式的定义才能入题
  4=较高: 需精准辨析极易混淆的概念，或提取冷门细节公式
  5=极高: 纯概念辨析题，全凭记忆准确度，毫无推演绕过余地
  判定锚点：看学生不记忆任何408知识能否入题 → 能则1，需一个核心定义则3，需辨析两个以上易混概念则4-5

K2 单步代入需求（需要执行单次直接计算/转换的程度）:
  1=微弱: 几乎无计算，或仅需极简单心算
  2=较低: 需一步简单公式代入，数字友好（多为 2 的幂）
  3=标准: 需代入常规公式计算，可能涉及非 2 的幂次或小数
  4=较高: 单步计算繁杂/易算错，或需多级单位统一换算
  5=极高: 整题核心就是卡这一步复杂计算，算错全盘皆输
  判定锚点：看最复杂的单步计算是否可能算错 → 2的幂友好计算则2，非2幂次则3，多级换算或精度敏感则4-5

K3 机制推演需求（需要在明确规则下多步串行推演的程度）:
  1=微弱: 无需推演流程，得出答案不需走多步
  2=较低: 仅需 2 步以内的极简推导，路径唯一
  3=标准: 需按固定"说明书"走完 3-5 步流程，路径唯一
  4=较高: 推演步数 >5 步，或需维持动态状态更新
  5=极高: 极长程推演，极度消耗工作记忆，中间错一步全盘皆输
  判定锚点：数从输入到输出需几步 → 1-2步则1-2，3-5步标准流程则3，>5步或需记忆中间状态则4-5

K4 条件路由需求（需要识别隐含前提/避开暗坑/切换机制的程度）:
  1=微弱: 题面字面意思即全部，无任何隐藏陷阱
  2=较低: 存在常规注意点，408 考生基本不会踩坑
  3=标准: 存在明确的陷阱词，不触发就会用错公式
  4=较高: 隐含前提很深，必须依靠对机制本质的理解才能路由
  5=极高: 整题专为反直觉设计，顺向常规思维 100% 掉坑
  判定锚点：看有没有"题面没说但解题必须意识到的条件" → 无则1，有常规注意点则2，有陷阱词则3，隐含前提深则4，反直觉则5

K5 跨域联动需求（需要跨越不同子系统/模块传递状态的程度）:
  1=微弱: 单一知识点内部解决，不涉及其他系统
  2=较低: 提及其他系统名词，但无数据/逻辑实质性关联
  3=标准: 两系统单向拼接，A 的输出直接当 B 的输入
  4=较高: A 系统的状态/异常会改变 B 系统的执行逻辑
  5=极高: 多系统深度耦合，需来回交叉推演与双向验证
  判定锚点：看是否需要在不同子系统之间传递数据或状态 → 单系统则1，提及无关则2，单向传数据则3，状态互影响则4，深度耦合则5
"""
