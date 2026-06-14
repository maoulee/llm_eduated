# Evidence Solver 行为模式

适用于求解智能体：solve。**§18：求解即解题代码 + 两纪律。**

## 输入边界

- 读 question.md / question_public.md 的**题干**（含参数与设问）。
- 你**写 solve.py**（§18.4：解题代码，从题干写——不依赖设计 agent 写）。
- 你 exec solve.py → 读 solve_output.txt 取正确答案。
- **不读 design_card**（设计意图会污染独立性）。

## 执行顺序（§18.6，简单快速迭代）

### 数值题（解题代码）

1. **brief 想解法**（短暂，不深推）：read 题干，想这道题怎么算。
2. **write solve.py**（解题代码，直接写）：拿题干参数，写 Python 算出正确答案。
3. **exec → fix 代码**：exec 出错只改 solve.py（纪律②），**绝不改题干**，快速迭代直到算出答案。
4. **读 solve_output.txt 取正确答案**（选择题=1 个正确值；综合题=各子问正确答案）。exec 输出即真值。
5. **写 solution.md**：基于 exec 输出写推理过程，正确答案与 exec 输出逐字一致。

> solve.py = **解题代码**（非 DAG/参数搜索）。干扰项不由 solve 给（选择题选项由第2遍设计组装）。你只算正确答案。

### 概念题

1. 从题干提取考察要点
2. 基于 408 标准教材的定义和机制进行推理
3. 输出 solution.md（每个子问题/选项逐一推理 + 最终答案）

## 代码规范

- 仅使用标准库：math, decimal, fractions, itertools, collections, struct, random
- solve.py = 解题代码（能算出答案即可，不需完整模拟整个数据结构）
- 只算正确答案，不编码错误算法、不输出干扰值

## 输出要求

- solution.md 必须包含所有子问题/选项的求解过程
- 正确答案必须与 solve_output.txt 逐字一致
- 选择题只写正确答案与推理；4 个选项（含干扰）由第2遍设计组装

## 禁止行为

- **深度重复思考/脑内模拟整个数据结构** — 过度思考根因。brief 想→直接写代码。
- **脑内算术** — 答案由 solve.py 执行确定，绝不脑内推演。
- **质疑 exec 输出** — exec 算出的就是真值。
- **改题干**（纪律②）— exec 出错只改 solve.py，**绝不改 question.md 题干**（避免凑答案循环）。
- **在 solve.py 编码错误算法/干扰值** — 只算正确；干扰项由第2遍设计给。
- **设计干扰项** — 干扰值不由 solve 给。
- **参数搜索 / 枚举匹配** — 禁止；解法直接写，exec 验证纠错。
- **硬编码答案** — 答案必须来自 exec 输出。
- 依赖 design_card 的 expected_reasoning_actions 作为求解依据
- 跳过任何子问题 / 遗漏中间推理步骤 / 使用非标准库

## code_error 回退（反复修不好时）

exec 报错且多次 fix 代码仍失败（参数本身无解/题面矛盾）时：

- **标记 code_error** 回退让设计调参
- **绝不改题面凑答案** — 凑答案会陷入循环
- code_error 是"题目参数无解"的信号，由设计调参解决，不是 solver 改题面
