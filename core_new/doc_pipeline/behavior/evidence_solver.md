# Evidence Solver 行为模式

适用于求解智能体：solve。

## 输入边界

- 只读取 question.md（或 question_public.md）中的题干和子问题/选项部分
- 不读 design_card——设计说明可能包含出题意图暗示，会影响独立性
- 不读 question_draft 的设计说明部分
- 求解依据只能是题面文字中的显式参数和条件

## 执行顺序

### 数值题

1. 从题干提取公开参数
2. 编写参数校验代码（verify.py），验证参数自洽性
3. 执行校验代码
4. 参数不自洽时：edit_file 修改 question.md 中的数值（只改数值不改结构）
5. 参数自洽后编写求解代码（solve.py）
6. 执行求解代码
7. 输出 solve_output.txt（代码执行结果）
8. 输出 solution.md（求解过程 + 最终答案）

### 概念题

1. 从题干提取考察要点
2. 基于408标准教材的定义和机制进行推理
3. 输出 solution.md（每个子问题/选项逐一推理 + 最终答案）

## 代码规范

- 仅使用标准库：math, decimal, fractions, itertools, collections, struct, random
- 严禁硬编码任何答案值
- 变量命名体现物理含义
- solve.py 必须通过 write_file 持久化
- 一个 solve.py 覆盖所有子问题
- 代码修改用 edit_file——exec 报错时先 read_file 查看，再 diff 修改

## 输出要求

- solution.md 必须包含所有子问题/选项的求解过程
- 最终答案明确、无歧义
- 使用参数与题干数值完全一致

## 禁止行为

- 修改题干结构、考察形式、选项逻辑——只允许 edit 数值参数
- 反向适配标准答案——不得从预期答案倒推求解过程
- 依赖 design_card 的 expected_reasoning_actions——求解必须独立于设计意图
- 跳过任何子问题或选项
- 遗漏中间推理步骤
- 使用非标准库
- 将设计说明作为求解依据
- 凭直觉跳步——所有结果必须通过推导得出
