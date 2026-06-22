# 408 自适应出题与经验库系统设计报告

## 1. 背景与目标

本项目的长期目标不是单纯构建一个能够回答 408 题目的解题模型，而是构建一个面向 408 考研学习场景的自适应训练系统。

当前本地 35B 级模型在单纯解题任务上已经达到较强水平，具备稳定解题、生成推理轨迹、辅助验证和低成本批量实验的能力。GLM5.1 等第一梯度线上大模型更适合承担高质量出题、复杂结构化分析、审题、知识体系归纳和经验总结任务。

因此系统的核心目标应调整为：

```text
基于真题和用户作答轨迹，构建题目结构化数据库、知识点体系、触发规则库、推理模式库和用户经验库，最终为用户生成符合其能力状态和学习缺口的个性化题目。
```

解题只是中间能力，最终产品价值来自于：

1. 知道一道题真正考什么；
2. 知道用户为什么错；
3. 知道用户缺的是概念、操作、机制、触发规则还是推理模式；
4. 能基于这些信息生成恰当难度、恰当考点、恰当错误诱发点的训练题。

---

## 2. 核心设计原则

### 2.1 解题和标注分离

系统应保持如下边界：

```text
Solver 只负责解题、推理、代码验证和一致性判断。
Annotator 只基于原题、标准答案、推理轨迹、验证结果进行结构化标注。
Critic 只负责审查标注和生成题质量，不修改原始答案。
```

这样可以避免模型在解题时为了迎合标签而污染推理，也可以避免标注阶段重新解题导致标签和原始 trace 不一致。

### 2.2 经验不是工程调用经验

本系统中的“经验”不是 vLLM、GLM、接口调用、部署等工程经验，而是从题目、模型推理轨迹和用户作答中沉淀出来的学习经验与推理经验，包括：

1. 知识缺口经验；
2. 用户错误经验；
3. 推理模式经验；
4. 触发规则经验；
5. 出题设计经验。

### 2.3 出题是最终目标

单纯答题只要求模型给出正确答案；出题则要求题目满足用户需求、考点明确、难度合适、干扰项有效、答案唯一且符合 408 风格。

因此出题系统必须依赖：

1. 题目结构化数据库；
2. 知识单元体系；
3. 触发规则库；
4. 推理模式库；
5. 用户画像；
6. 题目质量门。

---

## 3. 模型分工

### 3.1 本地 35B 模型

本地 35B 模型不应被视为弱模型。它在本系统中承担低成本、大批量、可重复运行的核心任务：

1. 常规解题；
2. 生成结构化 reasoning trace；
3. 进行可选代码验证；
4. 初步知识点标注；
5. 推理模式匹配；
6. 用户错误初步诊断；
7. 出题后的第一轮解题验证；
8. 通过不同提示条件做 ablation 实验，判断某类知识或经验是否真正影响解题。

35B 模型尤其适合用于对同一道题进行多种条件下的实验：

```text
A. 无提示解题
B. 只给浅层知识解题
C. 给浅层知识 + 机制知识解题
D. 给浅层知识 + 机制知识 + 触发规则 + 推理模式解题
```

如果 A/B 错、C/D 对，说明关键在机制知识。如果 A/B/C 错、D 对，说明关键在触发规则或推理模式。

### 3.2 GLM5.1

GLM5.1 负责高价值任务：

1. 真题结构化建库；
2. 知识点体系归纳；
3. 触发规则抽取；
4. 推理模式抽象；
5. 高质量出题；
6. 审题与质量控制；
7. 复杂错误经验总结；
8. 题目难度与教学目标校准。

出题阶段应以 GLM5.1 为主力，本地 35B 作为解题验证器、错误预估器和低成本质量筛查器。

---

## 4. 知识体系设计

原先的“浅层知识 / 深层知识”二分不够精细。根据测试观察，模型和人类常出现的问题不是完全不知道知识，而是没有在题干中触发正确机制。例如 DRAM 地址引脚题中，模型能正确计算地址位数，但如果没有触发“DRAM 行列地址复用”，最终仍会答错。

因此建议将知识拆为六类知识单元。

### 4.1 K1：概念知识 Concept

知道一个术语是什么。

示例：

```text
页面、页号、页内偏移、Cache 行、DRAM、地址线、位扩展、字扩展
```

### 4.2 K2：事实 / 公式知识 Fact

知道一个结论、规则或公式。

示例：

```text
容量 = 存储单元数 × 每单元位数
地址位数 = log2(存储单元数)
页面大小 = 2^n 时，页内偏移为 n 位
```

### 4.3 K3：操作知识 Operation

知道如何把概念和公式用于一步计算或判断。

示例：

```text
根据页面大小求偏移位数
根据逻辑地址拆页号和页内偏移
根据 Cache 容量、块大小、组相联度求组号位数
根据存储芯片容量求地址线位数
```

### 4.4 K4：机制知识 Mechanism

知道系统机制如何影响推导。

示例：

```text
DRAM 行列地址复用会减少地址引脚数
组相联 Cache 地址需要拆为 tag / set index / block offset
虚拟地址到物理地址转换需要经过页表
流水线冲突会影响 CPI
TCP 滑动窗口约束发送方可发送范围
```

### 4.5 K5：触发知识 Trigger / Discriminator

触发知识是本系统最关键的知识类型。它回答：

```text
题干中的什么条件决定应该调用哪个机制或推理模式？
什么时候不能套普通公式？
哪个词会改变解题路径？
```

示例：

```text
题干问“DRAM 芯片地址引脚数”时，要触发行列地址复用。
题干问“地址线根数”而不是“地址位数”时，要区分引脚复用。
题干出现“组相联”时，不能按直接映射拆地址。
题干出现“按字节编址”时，容量换算要以字节为单位。
题干出现“到达时间不同”时，调度题不能只看服务时间。
```

### 4.6 K6：推理模式 Pattern

推理模式是一套完整的可复用解题流程。

示例：

```text
页式存储地址转换四步法
Cache 地址拆分模式
DRAM 芯片地址引脚计算模式
Dijkstra 适用性判断模式
进程调度甘特图推理模式
TCP 滑动窗口边界推理模式
```

### 4.7 对外展示映射

如果产品侧仍希望使用“浅层 / 深层”表达，可以映射为：

```text
浅层知识：concept + fact
中层做题知识：operation
深层知识：mechanism + trigger + pattern
```

其中 trigger 和 pattern 是最应优先建设的部分。

---

## 5. DRAM 地址复用案例

示例题：

```text
某 DRAM 芯片容量为 4M×8 位，问地址引脚数是多少？
```

普通错误推理：

```text
4M = 2^22，因此地址位数是 22，所以地址引脚数是 22。
```

正确推理：

```text
4M = 2^22，完整地址位数为 22。
但题目问的是 DRAM 地址引脚数。
DRAM 通常采用行列地址分时复用，因此地址引脚数约为 22/2 = 11。
```

结构化标注应为：

```json
{
  "concepts": ["DRAM", "地址线", "存储芯片容量"],
  "facts": ["4M = 2^22", "地址位数 = log2(存储单元数)"],
  "operations": ["由芯片容量计算完整地址位数"],
  "mechanisms": ["DRAM 行列地址复用"],
  "triggers": [
    {
      "trigger": "题干问 DRAM 芯片地址引脚数",
      "selected_mechanism": "DRAM 行列地址复用",
      "if_missed": "会把完整地址位数误当成地址引脚数"
    }
  ],
  "reasoning_patterns": ["DRAM 地址引脚数计算模式"],
  "common_errors": [
    "忽略 DRAM 地址复用",
    "把地址位数和地址引脚数混淆",
    "把 4M×8 中的数据位宽 8 误算进地址位数"
  ]
}
```

这类结构化结果能够直接用于用户诊断和出题蓝图生成。

---

## 6. 核心数据库设计

第一阶段建议构建以下核心库：

1. `questions`：题目基础库；
2. `question_structures`：题目结构化库；
3. `knowledge_units`：知识单元库；
4. `trigger_rules`：触发规则库；
5. `reasoning_patterns`：推理模式库；
6. `experience_cards`：经验卡片库；
7. `model_runs`：模型解题轨迹库；
8. `ablation_results`：模型提示实验结果库；
9. `user_profiles`：用户画像库；
10. `user_attempts`：用户作答记录库。

第一版实现建议使用 PostgreSQL + JSONB + pgvector。图谱关系可以先用边表表达，后续再考虑 Neo4j。

---

## 7. 题目结构化库

每道题都应包含题干、选项、答案、题目结构、知识单元、错误画像和难度画像。

示例 schema：

```json
{
  "question_id": "408_2023_co_12",
  "source": "408真题",
  "year": 2023,
  "subject": "计算机组成原理",
  "question_type": "single_choice",
  "stem": "...",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "answer": "B",
  "question_structure": {
    "given_conditions": [],
    "asked_target": "",
    "hidden_constraints": [],
    "unit_constraints": [],
    "distractor_logic": []
  },
  "knowledge_units": {
    "concepts": [],
    "facts": [],
    "operations": [],
    "mechanisms": [],
    "triggers": [],
    "reasoning_patterns": []
  },
  "difficulty_profile": {
    "concept_difficulty": 1,
    "operation_difficulty": 2,
    "mechanism_difficulty": 3,
    "trigger_difficulty": 4,
    "pattern_difficulty": 3,
    "overall_difficulty": 3
  },
  "error_profile": {
    "common_model_errors": [],
    "common_student_errors": [],
    "critical_breakpoints": []
  }
}
```

题目结构化库回答：

```text
这道题给了什么？
问什么？
隐含条件是什么？
干扰项分别诱导哪些错误？
它真正考哪些知识单元？
它的难点在概念、操作、机制、触发还是模式？
```

---

## 8. 知识单元库

知识单元表建议包含如下字段：

```json
{
  "knowledge_unit_id": "CO_MEMORY_DRAM_ADDRESS_MULTIPLEXING",
  "name": "DRAM 行列地址复用",
  "subject": "计算机组成原理",
  "unit_type": "mechanism",
  "parent": "CO_MEMORY_DRAM",
  "description": "DRAM 为减少地址引脚，通常将行地址和列地址分时复用输入",
  "prerequisites": [],
  "related_triggers": [],
  "common_errors": []
}
```

`unit_type` 取值：

```text
concept
fact
operation
mechanism
trigger
pattern
```

知识体系不应只是树，而应是图：

```text
页面大小 -> 决定页内偏移位数
逻辑地址位数 -> 决定页号位数
页表项 -> 决定物理页框号
页框号 + 页内偏移 -> 得到物理地址
```

---

## 9. 触发规则库

触发规则库是本系统的核心壁垒之一。

示例：

```json
{
  "trigger_id": "TRG_CO_DRAM_ADDRESS_PIN",
  "name": "DRAM 地址引脚数触发地址复用",
  "trigger_conditions": [
    "题干出现 DRAM",
    "题干询问地址引脚数或地址线根数",
    "题目给出芯片容量"
  ],
  "required_mechanism": "CO_MEMORY_DRAM_ADDRESS_MULTIPLEXING",
  "wrong_if_missing": [
    "直接用 log2(存储单元数) 作为答案",
    "把地址位数误当成地址引脚数"
  ],
  "diagnostic_value": "high",
  "generation_value": "high"
}
```

触发规则直接服务于两件事：

1. 诊断用户不是不会概念，而是没有触发正确机制；
2. 生成专门测试某个 trigger 的题目。

---

## 10. 推理模式库

推理模式是比知识点更高层的解题程序。

示例：

```json
{
  "pattern_id": "PAT_CO_DRAM_ADDRESS_PIN_CALC",
  "name": "DRAM 地址引脚数计算模式",
  "subject": "计算机组成原理",
  "applicable_conditions": [
    "题目给出 DRAM 芯片容量",
    "题目询问地址引脚数或地址线根数"
  ],
  "required_units": {
    "concepts": ["DRAM", "地址引脚", "存储单元"],
    "facts": ["地址位数 = log2(存储单元数)"],
    "mechanisms": ["DRAM 行列地址复用"],
    "triggers": ["DRAM 地址引脚数触发地址复用"]
  },
  "reasoning_steps": [
    "从芯片容量中提取存储单元数",
    "计算完整地址位数 n",
    "判断题目问的是地址位数还是地址引脚数",
    "若为 DRAM 地址引脚数，则考虑行列地址复用",
    "输出约 n/2 个地址引脚"
  ],
  "common_breakpoints": [
    "把数据位宽误算进地址位数",
    "没有触发 DRAM 地址复用",
    "混淆地址位数和地址引脚数"
  ],
  "verification": {
    "can_verify_with_code": true,
    "verification_type": "bit_count_calculation"
  },
  "generation_hooks": {
    "can_generate_diagnostic_question": true,
    "target_errors": ["忽略地址复用", "混淆地址位数与地址引脚数"]
  }
}
```

推理模式库服务：

1. 本地模型解题增强；
2. 用户错误诊断；
3. 个性化出题蓝图生成。

---

## 11. 经验卡片库

经验卡片是从题目、模型推理轨迹和用户作答轨迹中总结出的可复用经验。

统一 schema：

```json
{
  "experience_id": "EXP_CO_DRAM_TRIGGER_001",
  "experience_type": "knowledge_gap | user_error | reasoning_pattern",
  "scope": "global | user | model",
  "related_units": [],
  "related_question_patterns": [],
  "trigger_conditions": [],
  "symptoms": [],
  "diagnosis": "",
  "recommended_action": [],
  "source_question_ids": [],
  "source_trace_ids": [],
  "confidence": 0.86,
  "status": "candidate | verified | deprecated"
}
```

经验卡片分三类：

### 11.1 知识缺口经验

描述某类知识缺失会导致什么错误。

### 11.2 用户错误经验

描述某个用户具体容易怎么错。

### 11.3 推理模式经验

描述某类题固定应该怎么推理，以及常见断点。

经验卡片不要直接由模型生成后入正式库，应先进入 `candidate`，经过去重、验证、人工抽检后再升级为 `verified`。

---

## 12. 模型实验与 Ablation 设计

本地 35B 模型可用于经验价值评估。

同一道题运行不同提示条件：

```text
A. 无提示解题
B. 只给 concept + fact
C. 给 concept + fact + mechanism
D. 给 concept + fact + mechanism + trigger + pattern
```

记录：

```json
{
  "question_id": "408_2023_co_12",
  "model": "local_35b",
  "runs": [
    {"mode": "no_hint", "answer": "22", "correct": false},
    {"mode": "concept_fact_only", "answer": "22", "correct": false},
    {"mode": "mechanism_hint", "answer": "11", "correct": true},
    {"mode": "full_pattern_hint", "answer": "11", "correct": true}
  ],
  "diagnosis": "关键提升来自机制/触发知识"
}
```

Ablation 的价值在于判断：

```text
题目到底卡在概念、操作、机制、触发规则还是推理模式？
```

---

## 13. 用户画像设计

用户画像不是单一分数，而是分层能力画像。

建议结构：

```json
{
  "user_id": "u_001",
  "profile_stage": "cold | warming | stable",
  "mastery": {
    "concept": {},
    "fact": {},
    "operation": {},
    "mechanism": {},
    "trigger": {},
    "pattern": {}
  },
  "error_habits": {
    "missed_trigger": 0.0,
    "unit_confusion": 0.0,
    "boundary_condition_missing": 0.0,
    "formula_misuse": 0.0,
    "concept_confusion": 0.0,
    "calculation_error": 0.0
  },
  "difficulty_profile": {
    "preferred_difficulty": 2,
    "current_effective_difficulty": 2,
    "frustration_threshold": 4,
    "target_success_rate": 0.65
  },
  "reasoning_breakpoints": [],
  "training_queue": []
}
```

重点是单独记录：

1. trigger mastery；
2. pattern mastery；
3. error habits；
4. reasoning breakpoints。

这比普通“知识点正确率”更能指导出题。

---

## 14. 没有初始画像时的冷启动策略

没有用户画像时，不应直接做强个性化出题，而应先做诊断型出题。

目标是快速回答：

```text
用户大概处于什么水平？
用户是概念不会、操作不会、机制不会，还是触发规则不会？
用户在哪几个科目有明显短板？
用户适合什么初始难度？
最值得优先训练的缺口是什么？
```

### 14.1 冷启动题类型

建议包括四类题：

1. 水平定位题；
2. 触发规则诊断题；
3. 对照题；
4. 错因诱发题。

对照题示例：

```text
题 1：SRAM 地址线计算
题 2：DRAM 地址引脚数计算
```

如果用户第一题对、第二题错，说明容量计算会，但 DRAM 地址复用 trigger 不会。

### 14.2 冷启动题数量

推荐第一版使用 12 道诊断题：

```text
4 科 × 每科 3 题
覆盖 concept / operation / mechanism / trigger / pattern
难度 2-4 混合
```

也可以提供 24 道标准诊断版本。

---

## 15. 用户作答后的画像更新

每次作答记录不能只存对错。应记录：

```json
{
  "user_id": "u_001",
  "question_id": "408_2023_co_12",
  "user_answer": "A",
  "correct_answer": "B",
  "is_correct": false,
  "time_spent_sec": 95,
  "confidence": 0.8,
  "selected_distractor_error": "missed_dram_address_multiplexing",
  "diagnosed_breakpoint": {
    "type": "trigger",
    "target_id": "TRG_CO_DRAM_ADDRESS_PIN",
    "description": "没有触发 DRAM 行列地址复用"
  }
}
```

如果用户选中了“未考虑 DRAM 地址复用”的干扰项，则不应平均扣所有知识点，而应：

```text
concept 不一定扣
fact 不一定扣
operation 可能不扣
trigger 大幅下降
pattern 中幅下降
error_habits.missed_trigger 上升
```

这能支持更精准的后续出题。

---

## 16. 个性化出题设计

出题不应直接 prompt：

```text
请出一道操作系统题。
```

而应先生成出题蓝图。

示例：

```json
{
  "user_id": "u_001",
  "profile_stage": "warming",
  "training_goal": {
    "target_type": "trigger",
    "target_id": "TRG_CO_DRAM_ADDRESS_PIN",
    "reason": "用户能算地址位数，但没有触发 DRAM 地址复用"
  },
  "difficulty_target": {
    "level": 3,
    "expected_success_rate": 0.65
  },
  "question_constraints": {
    "subject": "计算机组成原理",
    "question_type": "single_choice",
    "must_include": ["DRAM", "芯片容量", "地址引脚数"],
    "must_trigger_error": ["把地址位数当地址引脚数"],
    "distractor_design": [
      "一个选项对应未考虑复用",
      "一个选项对应误把数据位宽算入地址位数",
      "一个选项对应单位换算错误"
    ],
    "must_avoid": ["多个正确答案", "条件不足", "超出408范围"]
  }
}
```

GLM5.1 根据蓝图出题，本地 35B 负责验题和稳定性检测。

---

## 17. 出题质量门

生成题不能直接发给用户，必须通过质量门：

1. 条件完备；
2. 答案唯一；
3. 目标知识点明确；
4. 目标 trigger / pattern 确实被考查；
5. 干扰项对应真实错误；
6. 35B 能解出并给出稳定答案；
7. GLM5.1 审题通过；
8. 难度预测符合用户当前画像；
9. 与已有真题相似度不过高。

其中最关键的是：

```text
生成题是否真的训练目标 trigger / pattern。
```

否则题虽然正确，但不一定适合当前用户。

---

## 18. 出题目标选择算法

每次出题前，先选择训练目标。训练目标可以按以下优先级计算：

```text
priority =
  0.30 * weakness
+ 0.25 * exam_importance
+ 0.20 * prerequisite_importance
+ 0.15 * confidence
+ 0.10 * recency
```

含义：

1. weakness：用户掌握度低；
2. exam_importance：408 高频核心考点；
3. prerequisite_importance：该点是否影响后续知识；
4. confidence：系统对该判断是否有足够证据；
5. recency：用户最近是否反复错。

---

## 19. 第一阶段建设流程

建议第一阶段流程：

```text
Step 1：导入真题
Step 2：35B 无提示解题，生成 reasoning trace
Step 3：35B 可选代码验证
Step 4：GLM5.1 题目结构化
Step 5：GLM5.1 抽取知识单元、触发规则、推理模式
Step 6：35B 做 ablation 测试
Step 7：GLM5.1 基于 ablation 总结经验卡片
Step 8：聚类合并知识点和经验卡片
Step 9：人工抽检 10% - 20%
Step 10：入正式库
```

第一阶段不要直接追求完整用户画像，而应优先稳定：

1. 知识单元库；
2. 触发规则库；
3. 推理模式库；
4. 经验卡片库。

---

## 20. MVP 范围建议

第一版建议：

```text
100 道真题
优先覆盖计算机组成原理和操作系统
生成 300 - 500 个知识单元候选
生成 50 - 100 个 trigger 规则
生成 50 个推理模式
生成 100 - 200 张经验卡片
人工抽检 20%
```

优先题型：

### 计算机组成原理

```text
DRAM 地址复用
Cache 地址拆分
存储芯片容量计算
补码 / 移码边界
流水线冲突
```

### 操作系统

```text
页式存储地址转换
页面置换
进程调度
PV 操作
死锁判断
```

这两个科目可以优先验证 trigger / pattern 体系。

---

## 21. 推荐任务拆分

### T1：Schema 与数据库设计

产出：

```text
questions
question_structures
knowledge_units
trigger_rules
reasoning_patterns
experience_cards
model_runs
ablation_results
user_profiles
user_attempts
```

### T2：真题导入与标准化

产出：

```text
questions.jsonl
标准字段：question_id / subject / stem / options / answer / explanation
```

### T3：35B 解题 trace pipeline

产出：

```text
reasoning_traces.jsonl
code_verification_results.jsonl
```

### T4：GLM5.1 题目结构化 pipeline

产出：

```text
question_structures.jsonl
knowledge_units_candidate.jsonl
trigger_rules_candidate.jsonl
reasoning_patterns_candidate.jsonl
```

### T5：Ablation pipeline

产出：

```text
ablation_results.jsonl
```

### T6：经验卡片抽取 pipeline

产出：

```text
experience_cards_candidate.jsonl
```

### T7：去重、聚类、人工抽检工具

产出：

```text
verified_knowledge_units.jsonl
verified_trigger_rules.jsonl
verified_reasoning_patterns.jsonl
verified_experience_cards.jsonl
```

### T8：冷启动诊断与用户画像更新

产出：

```text
cold_start_question_selector
user_profile_updater
training_queue_generator
```

### T9：个性化出题 pipeline

产出：

```text
question_blueprint_generator
glm_question_generator
local_solver_validator
glm_question_critic
```

---

## 22. 风险与注意事项

### 22.1 强模型结构化结果不能直接入库

GLM5.1 生成的是候选，不是最终真理。必须经过 schema 校验、去重、复核、抽检。

### 22.2 不要把知识点做成普通标签

标签只能说明“考了什么”，但不能说明“为什么错”。必须建设 trigger 和 pattern。

### 22.3 用户画像初期不可信

用户画像要有成熟度：

```text
cold：仅用于诊断
warming：局部个性化
stable：完整个性化出题
```

### 22.4 难度不能只靠模型主观判断

应拆分为：

```text
concept_difficulty
operation_difficulty
mechanism_difficulty
trigger_difficulty
pattern_difficulty
calculation_load
distractor_strength
overall_difficulty
```

### 22.5 出题必须围绕训练目标

不要生成“看起来不错但不训练目标缺口”的题。

---

## 23. 最终闭环

系统最终闭环应为：

```text
真题
  ↓
题目结构化
  ↓
知识单元 / 触发规则 / 推理模式 / 经验卡片
  ↓
冷启动诊断题
  ↓
用户作答
  ↓
用户画像更新
  ↓
选择训练目标
  ↓
生成出题蓝图
  ↓
GLM5.1 出题
  ↓
35B 解题验证
  ↓
GLM5.1 审题
  ↓
用户训练
  ↓
继续更新画像
```

最终目标不是让系统更会答题，而是让系统更会判断：

```text
用户当前最应该练什么题。
```

---

## 24. 当前优先级结论

近期最优先推进：

1. 建立题目结构化 schema；
2. 建立六类知识单元 schema；
3. 建立 trigger_rules schema；
4. 建立 reasoning_patterns schema；
5. 建立 experience_cards schema；
6. 跑 100 道真题做 GLM5.1 结构化候选；
7. 用 35B 做 ablation 验证；
8. 人工抽检后形成第一版 verified 库。

其中最关键的是：

```text
触发规则库 + 推理模式库
```

因为它们直接解释：

1. 为什么模型或用户知道浅层知识仍然会错；
2. 为什么某些题必须识别题干触发条件；
3. 为什么个性化出题不能只按知识点和难度生成。

