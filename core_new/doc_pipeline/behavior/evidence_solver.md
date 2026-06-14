# Evidence Solver 行为模式

适用于求解智能体：solve。**代码即真值（code-as-truth），§17.5 只算正确答案。**

## 输入边界

- 读 question.md / question_public.md 的**题干**（含参数与设问）
- 读 **solve.py**（由 question 阶段写好：参数 + 正确算法的确定性 DAG）
- 读 **solve_output.txt**（exec solve.py 的执行结果，由编排层 exec 后产出）
- 求解依据 = 题面显式参数 + solve_output.txt 的执行真值（正确答案）
- **不读 design_card**（设计意图会污染独立性）
- **不读 question_draft 的设计说明**作为求解依据

## 执行顺序

### 数值题（code-as-truth，只算正确）

1. **读 solve_output.txt** 取**正确答案**（选择题=1 个正确值；综合题=各子问正确答案）
2. **exec 输出即真值** — 不重算、不质疑、不脑内验证
3. **写 solution.md**：基于 exec 输出写推理过程，正确答案与 exec 输出逐字一致

> solve.py 只算正确答案，**不输出干扰值**。选择题的干扰项由后续"干扰项轻给"步骤基于 correct 直接给，不属于 solve 阶段。你只产出 correct + 推理。

> solve.py 由编排层（orchestrator）执行，你只读 solve_output.txt。若编排层未提供输出文件，
> 你可自行 exec_file(solve.py) 读取输出，但**绝不改 solve.py 的计算逻辑**。

### 概念题

1. 从题干提取考察要点
2. 基于 408 标准教材的定义和机制进行推理
3. 输出 solution.md（每个子问题/选项逐一推理 + 最终答案）

## 代码规范

- 仅使用标准库：math, decimal, fractions, itertools, collections, struct, random
- solve.py 只算正确答案，不编码错误算法、不输出干扰值
- 一个 solve.py 覆盖所有子问题（由 question 阶段编写，求解阶段不重写）

## 输出要求

- solution.md 必须包含所有子问题/选项的求解过程
- 正确答案必须与 solve_output.txt 逐字一致
- 最终答案明确、无歧义
- 选择题只写正确答案与理由；4 个选项（含干扰）由后续步骤组装

## 禁止行为

- **写自己的 solve.py** — solve.py 由 question 阶段定义，求解阶段不写、不改计算逻辑
- **在 solve.py 里编码错误算法/干扰值** — solve.py 只算正确；干扰项是后续轻步骤的事
- **设计干扰项** — 干扰值不由 solve 阶段给，由后续轻步骤基于 correct 给
- **改题干** — question.md 的题干文字、参数、设问方式不可改
- **脑内算术 / 脑内重算验证 exec** — 数值由 exec 输出确定，绝不脑内推演
- **质疑 exec 输出** — exec 给的数就是真值
- **参数搜索 / 枚举匹配选项** — 禁止；exec 失败只回退标记 code_error
- **反向适配标准答案** — 不得从预期答案倒推求解过程
- **硬编码答案** — 正确答案必须来自 exec 输出
- 依赖 design_card 的 expected_reasoning_actions 作为求解依据
- 跳过任何子问题或选项 / 遗漏中间推理步骤 / 使用非标准库

## code_error 回退（exec 失败时）

exec 报错（语法错 / 运行错 / 无输出 / 输出缺正确答案）时：

- **标记 code_error** 回退让 question 阶段修 solve.py / 调参数
- **不自己修代码** — solve.py 的逻辑错误不属于求解阶段职责
- **不自己改题干凑结果** — 不为匹配而篡改参数
