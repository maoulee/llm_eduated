# 融合出题技能（§22 交错设计+审核）

> 设计和审核交错进行：先出骨架（占位符），审核通过后填参数+求解。

## 流程（design 被调用两次）

- **第一次（design）**：写带占位符的 question.md（题干骨架+子问题），参数用变量（x, y 等）占位
- **第二次（design_solve）**：题干审核通过后 → 建模约束+参数搜索+求解 → write solution.md

根据当前是否存在 solution.md 判断你在哪一次。

---

## 第一次（design：带占位符的题干）

**判断**：如果 solution.md 不存在，你在第一次。

**目标**：基于经验和上游定案，写出题干骨架和子问题结构。参数用占位符（变量名），不填具体值。

### 做

1. **读上游**：design_card.md（hard_constraints + design_rationale）+ assembled.md（经验缓存）+ exam_form.md（考察形式）
2. **write question.md**：题干 + 子问题，参数位置用变量占位

   题干里的参数用变量名占位（如 x, y, 序列S 等），不填具体数值。例如：
   - "依次插入关键字序列 S = [x₁, x₂, ..., xₙ]"
   - "给定初始树结构 T"
   - "页大小为 P 字节"

   子问题结构要完整（问什么、几个问、分值），但具体参数值不填。

3. **设计说明**：写清楚参数的约束要求（从 design_card 的 hard_constraints 提取），让 design_solve 知道参数搜索的目标。

### 边界

- **允许**：基于经验的轻量判断（题怎么设问）
- **禁止**：填具体参数值（用占位符）
- **禁止**：写 gen.py 或求解代码（求解是第二次的事）
- **禁止**：脑内算数值

---

## 第二次（design_solve：参数搜索+求解）

**判断**：如果收到 form_gate 审核通过的信号，你在第二次。

**目标**：读审核反馈 → 建模约束+搜索参数+求解 → 替换占位符 → write solution.md。

### 做

1. **读 form_gate 的审核反馈**（review.md）→ 判断题干表述是否需要微调
   - 需要改 → 改 question.md 的表述（不改结构/设问）
   - 不需要改 → 继续

2. **write gen.py**：建模约束 + 给初始值 + 模拟机制 + 搜索满足约束的参数
   - gen.py 建模 hard_constraints（从 design_card 读取）
   - LLM 给初始值，代码模拟机制得到参数效果
   - 模拟过程同时产出求解数据流

3. **exec gen.py**：验证参数满足约束 + 得到求解数据流
   - 不满足 → 调整初始值 → 重 exec
   - 满足 → 继续

4. **edit question.md**：把占位符（$T$, $S$, $x_i$ 等变量名）替换为 gen.py 搜索出的**实际参数值**
   - 只替换占位符为具体值，不改设问结构/表述

5. **选择题额外步骤——选项构造**（仅 single_choice）：
   - gen.py 在求解路径上**顺手打印 option_plan 锚定的参数的正确值**（这些就是要做选项的值）
   - LLM 读 gen.py 输出的正确值 → 按 option_plan 的错误模式**对正确值做变换**（改某些位/取反/换值）→ 得到错误选项
   - **不算不设计**——正确值由 gen.py 产出，错误值是对正确值的简单变换
   - 把 A/B/C/D 选项填入 question.md

6. **write solution.md**：从 gen.py 的 exec 输出整理为**求解文档**
   - solution.md 是 **Markdown 文档**（逐步求解过程 + 答案），**不是 Python 代码**
   - 选择题额外：标注正确选项 + 每个干扰项的错误原因（对应 option_plan 的错误模式）

### 边界

- **允许**：exec gen.py；调整初始值（约束不满足时）；edit question.md 替换占位符
- **禁止**：改 question.md 的结构/设问（只替换占位符为实际值）
- **禁止**：把代码写入 solution.md（solution 是文档不是代码）
- **禁止**：脑内算数值；枚举/random 尝试参数

---

## 收到审核建议时

审核给的是**建议**（差距+建议），不是否决。逐条看：
- 标注「改题干」的：改 question.md 设问/表述
- 标注「改参数」的：改 gen.py 初始值重 exec

**先改题干（轻量），硬性约束才改参数。**

## 红线

- 不得脑内算数值/构造结构/推演过程 — 全部由 gen.py exec
- 不得在 question.md 写答案 — 答案只在 solution.md
- 不得使用非标准库（仅 math/decimal/fractions/itertools/collections/struct/random）
