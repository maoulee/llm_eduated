# 终审技能

> 行为约束（路由判定、输出格式、禁止行为）已定义在 agents/final_review.md。
> 本文件定义终审执行步骤、验证维度和输出格式。

## 审核焦点

终审在 review（题干风格审核）和 solve（求解+参数校验）之后执行：
- **review 已审过**：风格、考察形式表面结构
- **solve 已做过**：参数校验、数值修订、代码验证
- **终审必须基于 design_card + solve evidence 复核**：
  - 目标知识点是否真正进入求解链条
  - expected_reasoning_actions 是否在 solution / solve_output 中出现
  - terminology constraints 是否被题干满足
  - 若题面看似符合但求解未体现目标动作，应判 question_error

## 数值题 vs 概念题路径

### 数值题
1. read_file 读取 solution.md，提取最终答案
2. read_file 读取 solve_output.txt（代码执行结果）
3. 对比：solution 答案 vs solve_output 数值
4. 一致 → pass；不一致 → solution_error（打回 solve）

### 概念题
1. read_file 读取 question.md + solution.md
2. 检查：每个子问题/选项是否都有对应推理
3. 检查：答案唯一性（是否存在合理替代答案）
4. 检查：推理是否基于408标准定义
5. 通过 → pass；推理有误 → solution_error

## 终审执行步骤

### Step 1：读取全部输入
read_file 读取 question.md、solution.md。

### Step 2：证据核对（数值题）
- read_file 读取 solve.py、solve_output.txt
- 从 solution.md 提取最终答案中的数值
- 从 solve_output.txt 提取代码输出的数值
- 对比是否一致

### Step 3：答案唯一性
- 题目条件是否足以推导唯一答案
- 是否存在合理但不同的解答路径导致不同答案

### Step 4：条件利用率
- 题干中所有给定条件是否在求解中被使用

### Step 5：答案自洽性
- 推理链无跳步、无矛盾
- 中间结果与最终答案一致

### Step 6：蓝图匹配
- 知识点覆盖 vs 规划
- K难度实际 vs 目标（差异>=2级需标记）

### Step 7：判定路由
- 一致且无根本问题 → pass → 写 final_review.md + final.md
- 仅表述问题 → expression_fix → final.md 中修正 + 写 final_review.md
- 题目设计有误 → question_error → 写 final_review.md（不写 final.md）
- 数值不一致/求解有误 → solution_error → 写 final_review.md（不写 final.md）

---

## 修复反馈格式

当判定为 question_error 或 solution_error 时，routing_feedback 必须包含：

```markdown
## 错误定位
- 文件: question.md 或 solution.md
- 位置: 具体章节/子问题
- 错误类型: 参数矛盾/条件缺失/计算错误/推理错误

## 具体问题
1. （精确描述问题）

## 修正建议
- （具体可操作的修正方向）
```

---

## 输出格式

**长度限制：final_review.md 总内容不超过 1500 字。** 详细分析留在思考中，输出只写结论。

```markdown
## status
pass / expression_fix / question_error / solution_error

## summary
1-2句话总结：最终裁定 + 关键发现

## detailed_feedback
每个维度1行，仅写结论+少量关键词理由：
- 证据核对：[一致/不一致] （数值题：solution=9, solve_output=9）
- 答案唯一性：[通过/偏差] （关键词）
- 条件利用率：[通过/偏差] （关键词）
- 答案自洽性：[通过/偏差] （关键词）
- 蓝图匹配：[通过/偏差] （关键词）

## issue_type（仅非 pass 时）
pass 时省略。非 pass 时填写：question_error / solution_error / expression_fix

## evidence_check
逐条列出 design_card 核心约束的验证结果：
- core_knowledge_intent 覆盖：[是/否] + 证据
- expected_reasoning_actions 出现：[是/否] + 哪些缺失
- terminology constraints 满足：[是/否] + 偏差

## design_card_alignment
design_card 要求 vs 实际产出的对齐总结（1-3行）。

## routing_feedback（仅 question_error / solution_error 时）
1. [位置]: 当前值 → 应改为 → 不要动的部分
```

### 额外文件输出（仅 pass / expression_fix 时）

通过 `write_file(path="final.md", ...)` 写入 final.md：
```markdown
## 题目
{题干原文}

## 选项（选择题）或 ## 子问题（综合题）
{原文}

## 求解过程
{从 solution.md 提取的关键步骤}

## 答案
{最终答案}

## 设计说明（可选）
{内容}
```

final.md 中不包含审核元数据。
