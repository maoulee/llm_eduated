# 问题智能体技能

**核心原则（最高优先级）：**
1. **参数可行性由 param_design.py 验证，不由你在自然语言中证明。**
2. 你只负责定义槽位结构、提供种子值、填写代码骨架 — 不负责证明约束可行性。
3. param_design.py 模板是结构骨架，你根据具体题目填入领域特定验证逻辑。

---

## Step 1a：设计题干框架

### 执行

1. read_file(assembled.md) 提取知识点、考察模式、K难度、should_be / should_not_be
2. write_file(question.md)

### 输出要求

题干中所有数值用占位符 `⟨P1⟩ ⟨P2⟩ ...` 代替。在 `## 参数槽位` 中声明每个占位符。

```markdown
# 题目标题

## 题干
（完整叙述，数值用 ⟨P1⟩ ⟨P2⟩ 等占位）

## 子问题（或 ## 选项）
（完整设问，数值用占位符）

## 参数槽位
⟨P1⟩:
  role: seed
  type: sequence[int]
  seed_hint: positive_unique_ints
  used_by: （该参数在题目中的用途）
  checks:
    - unique
    - custom_domain_check

⟨P2⟩:
  role: derived
  expr: len(P1)
  used_by: （用途说明）

⟨P3⟩:
  role: seed
  type: int
  seed_hint: power_of_2_range_4_to_64
  used_by: （用途说明）
  checks:
    - range
    - custom_domain_check

## 设计说明
- 考察结构模式、子问依赖关系
- should_be / should_not_be 对齐
- K 值对齐说明
- 槽位用途说明（不写约束推导理由）
```

### seed_hint 通用词表

| 类别 | 示例值 |
|------|--------|
| 整数 | `positive_int`, `small_positive_int`, `power_of_2`, `int_1_to_100` |
| 序列 | `positive_unique_ints`, `sorted_ascending_ints`, `binary_sequence` |
| 浮点 | `positive_float`, `probability_0_to_1` |

### checks 通用词表

| 类别 | 示例值 |
|------|--------|
| 结构 | `unique`, `sorted`, `length_eq`, `range`, `positive`, `power_of_2` |
| 领域 | `custom_domain_check`（具体名称由题目领域决定） |

### 设计要点

- **题目风格**：读起来像 408 真题，设问直接
- **设问方式**：子问递进（基础→核心→区分度）
- **知识点覆盖**：与蓝图规划一致
- **K难度对齐**：实际 K1-K5 与目标差异不超过 1 级
- **槽位声明**：只写 role/type/seed_hint/used_by/checks，不证明可行性

### 红线

- 禁止出现任何具体数值
- 禁止写参数约束推导理由
- 禁止在自然语言中解释为什么某个参数能通过验证

### 完成后

**立即停止并等待系统指令。**

---

## Step 1b：参数填充（短代码合约）

### 判定

read_file(question.md)，搜索占位符和参数类型：

- **无 `⟨P` 占位符** → 跳到 Step 2（概念题或数值已直接写入）
- **有 `⟨P` 且参数全部是简单数值** → 跳过 param_design.py，直接在题干中替换为合理值
- **有 `⟨P` 且参数涉及序列、结构、派生关系** → 继续参数填充

**跳过规则**：纯文本概念题、数值可直接确定的题目，不需要参数验证代码。

### 核心思路

**你只填种子，代码算派生，代码做验证。**

- 你凭经验给 1-3 个候选种子值（大胆选，不求最优）
- 代码自动计算派生参数
- 代码自动验证约束
- 验证通过 → 用结果替换占位符

### 执行

1. read_file(question.md) 提取参数槽位
2. write_file(param_design.py) — 只填 SEEDS 区，代码自动算派生和验证
3. exec_file(param_design.py)
4. write_file(question.md) — 用代码输出替换所有占位符

### param_design.py 模板（结构骨架）

```python
# ===== 1. 经验种子（你只填这里，大胆给值）=====
CANDIDATES = [
    {"P1": ..., "P3": ...},   # 候选1
    {"P1": ..., "P3": ...},   # 候选2
    {"P1": ..., "P3": ...},   # 候选3
]

# ===== 2. 派生参数（代码计算，不要手写）=====
def derive(seeds):
    params = dict(seeds)
    # 根据题目槽位声明填入派生逻辑
    return params

# ===== 3. 约束检查（代码验证）=====
def validate(params):
    checks = []
    # 通用检查 + 领域特定检查
    return checks

# ===== 4. 自动选择通过验证的候选 =====
result = None
for seeds in CANDIDATES:
    params = derive(seeds)
    checks = validate(params)
    if all(ok for _, ok in checks):
        result = params
        break

if result is None:
    result = derive(CANDIDATES[0])
    print("WARNING: no candidate passed all checks, using first")

# ===== 5. 输出 =====
for k, v in result.items():
    print(f"{k}={v}")
```

### 红线

- **模型只允许改 CANDIDATES 区和骨架中的占位逻辑**
- 禁止在 Markdown 中解释为什么这个种子会通过验证
- 派生参数必须由代码计算，不能手写
- 禁止搜索/枚举（禁止 itertools.permutations、range 遍历、random 试探）
- param_design.py 只写一次
- 检查失败时，下一轮只改 CANDIDATES 中的值，不改验证函数

### 完成后

**立即停止并等待系统指令。**

---

## Step 2：独立求解

### 执行

1. read_file(question.md) — 只读题干和子问题（禁止读设计说明）
2. 数值题：write_file(solve.py) → exec_file(solve.py) → 用题面参数独立求解
3. 若计算结果不匹配题干/选项，先定位最小不一致，再 edit question.md 中的数值、单位或选项值
4. write_file(solution.md)
5. 数值题复跑 solve.py，对比 solution.md 答案
6. 不一致则做最小修正；不得为了匹配选项而枚举搜索参数

### solution.md 格式

```markdown
## status
solved

## 求解过程

### 子问题(1)
（推理/计算过程）

## 最终答案
- (1) ...
- (2) ...
```

### solve.py 模板（数值题）

```python
# ===== 题目参数定义 =====
param_a = ...
param_b = ...

# ===== 子问题(1) =====
result_1 = ...
print(f"ANSWER: {final_answer}")
```

### 代码规范

- 仅用标准库：math, decimal, fractions, itertools, collections, struct, random
- 严禁硬编码答案值
- 必须打印 ANSWER: ... 行

### 完成后

**立即停止并等待系统指令。**

---

## Step 3：组装最终交付

终审通过后，write_file(final.md)。

```markdown
## 题目
{question.md 题干原文}

## 子问题（或 ## 选项）
{原文}

## 求解过程
{solution.md 关键步骤}

## 答案
{最终答案}

## 设计说明（可选）
{内容}
```

**final.md 不包含审核元数据**（status、summary、score 等）。
