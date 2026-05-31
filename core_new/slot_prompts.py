# core_new/slot_prompts.py
"""Prompts for slot-template driven extraction, composition, and generation.

Extraction:
  SLOT_BATCH_ANALYSIS_PROMPT — per-slot observation + template extraction

Composition:
  PAPER_COMPOSER_PROMPT — generates PaperBlueprint from SlotTemplates
  BLUEPRINT_REVIEWER_PROMPT — reviews blueprint before sending to writers

Generation:
  SLOT_QUESTION_WRITER — generates question from SlotBlueprint + experience card
  QUESTION_FIXER_PROMPT — fixes specific issues in questions

Review:
  PAPER_REVIEWER_PROMPT — whole-paper review with issue categorization
"""

SLOT_BATCH_ANALYSIS_PROMPT = """你是一位408考研教研专家，专精于试卷结构和题位分析。

以下是2009-2023年408考研真题中**第{slot_num}题**（共{count}道）的完整数据。
请完成以下三重分析任务。

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
  <K1_demand>1-5整数。1=微弱常识, 2=基础名词, 3=标准需记忆, 4=易混辨析, 5=纯概念题</K1_demand>
  <K2_demand>1-5整数。1=极简心算, 2=一步简单代入, 3=标准公式计算, 4=复杂单步换算, 5=纯卡计算</K2_demand>
  <K3_demand>1-5整数。1=无需推演, 2=两步内极简, 3=标准3-5步固定推演, 4=长程>5步推演, 5=极长程易断链</K3_demand>
  <K4_demand>1-5整数。1=题面即全部, 2=常规注意点, 3=明确陷阱词需切换机制, 4=深隐含前提需本质理解, 5=专为反直觉设计</K4_demand>
  <K5_demand>1-5整数。1=单一系统, 2=提及他系统无关联, 3=单向数据传递, 4=系统状态异常互相影响, 5=多系统深度耦合双向推演</K5_demand>
  <radar_shape_name>根据雷达最高分维度命名，如：K4陷阱型、K3推演型、K5跨域联动型、K1概念型</radar_shape_name>
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
  <difficulty_anchor>各认知维度的众数和范围，JSON格式如 {{"K1_mode":2,"K1_range":[1,3],"K2_mode":3,"K2_range":[2,4],"K3_mode":2,"K3_range":[1,3],"K4_mode":2,"K4_range":[1,3],"K5_mode":1,"K5_range":[1,2]}}</difficulty_anchor>
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
  <expected_shape>该类型题目的预期形态，JSON格式，包含reasoning_steps、stem_length、condition_count、calculation_load、option_style</expected_shape>
  <suitable_targets>适合的知识点列表，JSON数组</suitable_targets>
  <distractor_style>干扰项设计风格，JSON数组</distractor_style>
  <bad_examples>不应该出现的特征，JSON数组</bad_examples>
</type_difficulty_guide>
```

---

请严格按照上述XML格式输出，确保每个标签都有内容。不要输出XML标签以外的额外解释。"""

# ═══════════════════════════════════════════════════════════════
# Per-question K1-K5 evaluation
# ═══════════════════════════════════════════════════════════════

SLOT_SINGLE_EVAL_PROMPT = """你是一位408考研教研专家。请对以下真题进行 K1-K5 认知雷达评分。

{cognitive_radar_scale}

## 题目信息

- **年份**: {year}
- **题位**: {slot_id}
- **考点**: {primary_target_name}
- **知识领域**: {target_family}
- **题型**: {question_type}
- **解题步骤**: {solution_steps}
- **正确答案原因**: {why_correct}
- **错误选项分析**: {why_wrong_options}
- **干扰项模式**: {distractor_patterns}
- **陷阱风格**: {trap_style}
- **选项风格**: {option_style}
- **推理形态**: {reasoning_shape}
- **题干长度**: {stem_length}
- **条件数量**: {condition_count}
- **出题角色**: {paper_role}（{paper_role_reason}）

## 评分要求

请根据上述信息，对这道题的 K1-K5 五个维度分别评分（1-5 整数）。
每个维度必须：
1. 给出评分值（1-5）
2. 给出判定理由（引用题目中的具体证据）
3. 说明为什么是这个分数而不是相邻分数

请严格按以下 Markdown 格式输出：

## evaluation
- **K1**: N — （理由 + 题干中触发基础认知需求的具体证据）
- **K2**: N — （理由 + 涉及什么类型的计算/转换）
- **K3**: N — （理由 + 推理链描述，几步，在哪容易断）
- **K4**: N — （理由 + 是否有陷阱/隐含前提/机制切换）
- **K5**: N — （理由 + 是否跨系统，什么数据传递）
- **radar_shape_name**: 根据最高分维度命名（如 K4陷阱型、K3推演型）
- **reasoning_shape**: one_formula / multi_step / elimination / simulation（这道题的主要推理形式）
- **reasoning_shape_reason**: 为什么是这个推理形式（一句话说明推理过程）
- **summary**: 一句话总结这道题的核心认知特点
"""

# ═══════════════════════════════════════════════════════════════
# Per-slot K1-K5 synthesis
# ═══════════════════════════════════════════════════════════════

SLOT_SYNTHESIS_PROMPT = """你是一位408考研教研专家，专精于试卷结构和题位分析。请基于以下题位的历史题目数据，产出该题位的**设计经验和出题指导**。

## 题位信息

- **题位**: {slot_id}
- **科目**: {subject_stability}
- **题型**: {question_type}
- **分值**: {typical_score}
- **题目数量**: {question_count}

## 历年题目 K1-K5 评价

{evaluations_data}

## 分析任务

请基于以上数据，产出该题位的设计经验和出题指导。注意：逐题的 K 评分已在上面的数据中给出，你不需要重复列出每题的 K 值，而是要聚焦于**跨年份的模式总结和设计指导**。

请直接输出 Markdown 文档（不要用代码块包裹），按以下结构：

## 往年案例

对每道历史题目，给出简要但深入的分析（每题 3-4 句话）：

### YYYY年 — 考点名称
- **核心考点**: 这道题考什么
- **分析**: 解题路径、陷阱设计、干扰项策略
- **值得借鉴**: 这道题有什么值得学习的设计手法

## 设计理念

基于历史题目的出题模式，总结如果为这个题位出题应遵循的设计原则：

### 题干设计
应该给什么情境、什么已知条件。

### 条件给法
哪些条件该显式给出、哪些应留给学生推导。

### 难度控制
基础/中等/高等难度分别怎么设计。

### 适合的知识点特征
什么样的知识点适合放在这个题位。

## 推理形式分析

- 该题位最常见的推理形式（one_formula / multi_step / elimination / simulation）
- 各推理形式出现频率
- 为什么这个题位适合这种推理形式

## 选项设计经验

### 正确答案的典型特征

### 干扰项的常见设计手法
列出 3-5 种常见的干扰项设计手法，每种附一个往年的具体例子。

## 出题指导

- **should_be**: 这个题位应该出什么样的题
- **should_not_be**: 这个题位不应该出什么样的题
- **K值建议**: 建议的 K1-K5 范围和理由
- **推理形式建议**: 建议使用什么推理形式

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
- **representative_years**: 代表年份，逗号分隔
"""

# ═══════════════════════════════════════════════════════════════
# Composition prompts (markdown output)
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

BLUEPRINT_REVIEWER_PROMPT = """你是一位408考研组卷审核专家。请审核以下组卷蓝图的质量，区分硬违规和软偏离。

## 用户需求
{user_requirements}

## 组卷蓝图
{paper_blueprint_json}

## 题位契约（用于对照）
{slot_contracts_md}

## 审核分类标准

对每个SlotBlueprint，按以下标准判定：

**hard_violation（硬违规，必须修复）**：
- 题型错误（如应该是single_choice却规划了综合题格式）
- 分值错误
- 多个正确答案或无法作答
- 输出格式缺失
- 综合应用题的option_style不为none（必须为none）

**soft_deviation（软偏离）**：
- major: 难度超出合理范围、计算量明显高于soft_max、primary_paper_role属于discouraged、考点属于should_not_be
- minor: 轻微偏离偏好约束但仍在合理范围内

**acceptable（可接受）**：
- 完全符合或仅有minor偏离且理由合理

## 审核要点

1. 硬约束是否全部满足（题型、分值、选项数）
2. 难度是否在合理范围内
3. 计算量是否匹配题型和难度
4. primary_paper_role是否合理
5. 整卷知识点是否覆盖均匀、无重叠
6. 难度曲线是否合理（前易后难）
7. 偏离理由是否合理（如果有偏离）
8. 整卷预算一致性：primary_role_distribution之和、difficulty_distribution之和、calculation_load_distribution之和是否都等于total_questions

请严格按以下markdown格式输出：

# blueprint_review

## 总体
- **status**: pass 或 revise
- **hard_violation_count**: 硬违规数量
- **major_deviation_count**: 重大偏离数量
- **minor_deviation_count**: 轻微偏离数量
- **comment**: 总体评价（2-3句话）

## Q12
- **status**: pass 或 revise
- **hard_violation**: yes 或 no
- **soft_deviation**: none 或 minor 或 major
- **deviation_fields**: 偏离的字段（无偏离写"无"）
- **issue**: 问题描述（无问题写"无"）
- **revision_instruction**: 修改建议（无写"无"）

（每个题位一个 ## 标题的section，格式同上）

## 全局问题
整卷层面的问题描述（无问题写"无"）
"""

# ═══════════════════════════════════════════════════════════════
# Generation prompts (markdown output)
# ═══════════════════════════════════════════════════════════════

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

PAPER_REVIEWER_PROMPT = """你是一位408考研试卷对抗审核员。你的目标不是确认试卷"没问题"，而是主动寻找每道题的潜在缺陷。你只有真的攻不破时，才能判 pass。

## 整卷蓝图
{paper_blueprint_json}

## 生成的题目
{generated_questions_json}

## 题位模板（用于对照）
{slot_templates_json}

## 对抗审核策略

对每道题，你必须执行以下攻击：

### 攻击1：换一种理解方式解题
用不同的推理路径重新求解，看是否得到相同答案。如果能得到不同答案，说明题目有歧义。

### 攻击2：寻找表述漏洞
- 题干是否有"可以合理理解为另一种意思"的歧义表述？
- 是否存在需要善意补全但题目没给的条件？
- 数值参数之间是否存在隐含矛盾？

### 攻击3：攻击干扰项
- 错误选项是否"太明显是错的"导致排除法秒杀？
- 正确选项是否真的唯一正确？换种理解是否有其他选项也"说得通"？

### 攻击4：对照蓝图
- 考点/难度/风格是否真的匹配SlotBlueprint？
- 解析推理是否严密？有无跳步、隐含假设、循环论证？

### 攻击5：认知雷达匹配
- 对比设计方案中的 target_K1-K5 与每道题实际的认知需求
- 实际 K4≥4 但设计 K4=2 → 题目挖了意料之外的深坑
- 实际 K5≤1 但设计 K5=3 → 跨域联动没有实现
- 实际 K3≥4 但设计 K3=2 → 推演链过长超出设计意图

## 判定规则
- 找到任何一个实质性问题 → 判对应问题类型
- 尝试所有攻击仍无法攻破 → pass
- 不要把润色建议判为问题

## 问题分类（关键！）

- **content_mismatch**: 考点/难度/风格不符合蓝图要求 → 需要重新出题
- **answer_error**: 内容符合但答案或计算有误 → 只需修复答案
- **pass**: 质量合格（真的攻不破）

请严格按以下markdown格式输出：

# paper_review

## 总体
- **overall_status**: pass 或 has_issues
- **overall_score**: 0-100
- **overall_comment**: 总体评价

## Q12
- **status**: pass 或 content_mismatch 或 answer_error
- **quality_score**: 0-10
- **attack_result**: 你尝试了哪些攻击，结果如何（一句话）
- **blueprint_compliance**: 是否符合蓝图（一句话）
- **actual_K1**: 1-5（实际基础认知需求）
- **actual_K2**: 1-5（实际单步代入需求）
- **actual_K3**: 1-5（实际机制推演需求）
- **actual_K4**: 1-5（实际条件路由需求）
- **actual_K5**: 1-5（实际跨域联动需求）
- **radar_match**: pass 或 fail（设计与实际认知雷达是否匹配）
- **issue**: 问题描述（pass写"无"）
- **fix_instruction**: 具体修复指令（pass写"无"；answer_error时指出错在哪、正确答案应该是什么；content_mismatch时说明应该如何调整）

（每个题位一个 ## 标题的section，格式同上）

## distribution
- **difficulty_curve**: 难度曲线评价
- **role_balance**: 功能角色分布评价
- **knowledge_overlap**: 知识点重叠问题
- **originality**: 原创性评价
"""

# Legacy prompt (kept for backward compatibility)
PAPER_QUALITY_REVIEWER = PAPER_REVIEWER_PROMPT

# ═══════════════════════════════════════════════════════════════
# Hybrid subjective prompts (legacy prompt quality + new pipeline speed)
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

## 工具指引

1. 先用 `read_slot` 工具读取题位 {slot_id} 的完整信息
2. 重点关注：考察理念、认知雷达锚点、设计理念、条件给法、往年案例
3. 结合下方蓝图要求，一次性完成出题

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
