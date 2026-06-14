# design_card_v1 技能

## 目标
生成符合 schema v1 的 design_card.md。

## 必须包含 10 个 section
1. status
2. blueprint_contract
3. route
4. core_knowledge_intent
5. design_rationale — **设计理念交接（给下游 design 智能体的 spec 交接文档）**
6. expected_reasoning_actions
7. question_structure_plan
8. parameter_plan
9. terminology_and_expression_constraints
10. audit_focus

## design_rationale（设计理念交接）

回答一个问题：**"为什么这样考？"**

用一段话写清楚：
- 本题考察意图与设计逻辑：为什么选这个考点组合、这种设问方式、这个 K-雷达形状
- 它要**区分什么样掌握程度的学生**（如"能完整走完旋转流程并回溯检查的学生 vs 只记得旋转名称的学生"）
- 为什么这个难度/形式是合适的

这是 spec 交接文档——下游 design 智能体读这段理解意图，**只实现题面、不重新推演设计合理性**。写清楚这段，design 就不必自己从头想"为什么这么考才合理"，从而降低 design 的思考强度。

不含具体数值、答案、最终结构。

## route 字段枚举值（必须使用英文原值，不加中文注释）

- question_form: 只能写 `single_choice` 或 `comprehensive`
- question_type: 只能写 `conceptual`、`computational` 或 `mixed`

错误示例：`选择题`、`综合应用题（共享题干）`、`mixed（概念+计算）`
正确示例：`single_choice`、`comprehensive`、`mixed`

## expected_reasoning_actions
- 只写解题动作。
- 不写具体数值答案。
- 不写正确选项。
- 不写最终树结构、最终地址字段数值等结果。
- 格式：每行以 `- ` 开头，或使用编号列表。

## parameter_plan
- 只写参数槽位、候选范围、验证目标。
- 不写 Python 代码。
- 不写 assert 模板。
- 不证明参数自洽。

## terminology_and_expression_constraints
- 写必须使用的标准术语。
- 写必须补充的限定条件。
- 写容易误导的表达及标准改写。

## 教师说明与排除项

- 若输入包含 teacher_annotation，必须在 blueprint_contract 或 audit_focus 中体现其约束
- excluded.modes / excluded.knowledge 不得进入 must_test、expected_reasoning_actions、parameter_plan
- candidate_pool_visible 只表示教师可见候选池，不表示本题需要覆盖
- active_selection 才是本题实际采用的模式和知识点

## 通用干扰模式库（跨题型通用认知错误）

设计卡在规划阶段**选定本题用哪些干扰策略**（写入 question_structure_plan 或 audit_focus），
下游设计智能体只保留这些干扰意图，不自己另选。这些模式跨题型通用，不是选择题专属。

### 计算型干扰（数值题）

- **单位换算陷阱**：正确值的不同单位表示（如 bit/byte、ms/μs、KB/MB 混淆）
- **符号错误**：正确值的相反数、补码、反码
- **偏移错误**：正确值 ±1，或偏离某个固定量（off-by-one）
- **中间值**：计算过程中的某个中间结果当作最终答案
- **倒置**：速度/时间的倒数、比率的分子分母互换
- **非叶节点纳入**：树/图的遍历计数把根或非叶节点算错

### 概念型干扰（概念辨析题）

- **概念混淆**：相似但不同的概念替换（如同步/异步、进程/线程）
- **过度推断**：从正确前提出错误推论
- **条件遗漏**：忽略某个约束后的错误结论
- **张冠李戴**：将 A 概念的特征安在 B 概念上

### 组合判断型干扰

- I/II/III 各代表一个独立命题
- 干扰项是"真命题 + 假命题"的混合组合

## 干扰策略选定规则

- 设计卡选定 3 种干扰类型，对应 3 个干扰选项
- 每种干扰类型对应一个**错误认知路径**（不是随机常量）
- 干扰类型记录在 question_structure_plan，供后续选项组装基于正确答案生成干扰项
- 不预设干扰的**具体数值**
