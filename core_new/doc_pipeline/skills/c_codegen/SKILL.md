# 融合出题技能（代码一次性产出，C 方案）

> 模型能力足够（glm5.2 能独立工作 8 小时）。过度思考源于行为边界不清。
> 本 skill 精确设置每一步边界：做什么、做完必做什么、不做什么。

## 核心原则：代码即推演

所有数值计算/结构推演/合法性校验**全部由 gen.py 代码 exec 完成**。
你**不脑内算、不脑内构造树、不脑内推演旋转**。
你只做 3 件事：**①规划 ②写代码 ③组装题目**。

## 三步流程（每步有明确入口和出口）

### Step 1：规划（1 轮，只读不写）

**入口**：收到任务 + assembled.md（规划文档，含考察要求/K-雷达/经验缓存）。

**做**：
- read assembled.md（或题位规划文档）
- 确定：要构造什么数据（AVL树/资源矩阵/图）+ 约束条件 + 设问指向

**出口**：用 1-2 句话写出"gen.py 要生成什么"（如"生成一棵 7 节点初始 AVL 树 + 插入 4 节点触发 2 种旋转"）。
**做完必做**：进入 Step 2（write gen.py）。
**不做**：不在脑内构造具体的树/节点值/旋转过程。不 grep_search（除非 assembled 完全无经验）。

### Step 2：写 gen.py + exec 验证（代码即推演）

**入口**：Step 1 的规划结论。

**做**：
- write_file(gen.py)：一个完整 Python 脚本，**exec 后 print 以下 4 段**（用 `=====` 分隔）：

```
===== 参数 =====
[构造的具体数据：节点集合、插入序列、资源矩阵等]

===== 题干描述 =====
[人类可读的题干，可直接复制进 question.md。含数据描述 + 设问]

===== 求解路径 =====
[逐步推演过程：每次操作后的状态变化、中间结果]

===== 答案 =====
[每个设问的最终答案值]
```

- **exec_file(gen.py)**：立即执行。
- **read exec 输出**：确认 4 段都有 + 数据合法（如初始树是 AVL、旋转类型≥2种）。

**出口**：exec 通过 + 4 段完整 + 合法 → 进入 Step 3。
**做完必做**：exec。**不 exec 就不进 Step 3。**
**exec 失败**：edit gen.py 改 bug → 再 exec。循环直到通过。
**不做**：不脑内验证 gen.py 对不对（exec 说了算）。不反复重写 gen.py（写完 exec，错了改 bug 不是重写）。

### Step 3：组装 question.md + solution.md（复制，不重算）

**入口**：Step 2 的 exec 输出（4 段）。

**做**：
- write_file(question.md)：复制 exec 输出的「题干描述」段 + 补设计说明。**不含答案**。
- write_file(solution.md)：复制 exec 输出的「求解路径」+「答案」段。

**出口**：question.md + solution.md 都写入。
**不做**：不重新算答案（gen.py 已算）。不写 solve.py（gen.py 就是求解）。不脑内验证。

## 红线（违反即判定失败）

- **不得脑内算数值/构造结构/推演过程** — 全部由 gen.py exec。
- **不得跳过 exec** — gen.py 写完必须 exec 验证才能组装题目。
- **不得反复重写 gen.py** — 写完 exec，错了改 bug（edit），不是重写（write 覆盖）。
- **不得在 question.md 写答案** — 答案只在 solution.md。
- **不得写 solve.py** — gen.py 已经是求解（它构造参数时算了答案）。
- **不得使用非标准库**（仅 math/decimal/fractions/itertools/collections/struct/random）。

## 行为边界总结

| 步骤 | 轮数 | 做什么 | 做完必做 | 不做什么 |
|------|------|--------|---------|---------|
| Step 1 规划 | 1 轮 | 读 assembled + 确定构造方案 | → write gen.py | 不脑内构造 |
| Step 2 代码 | 2-4 轮 | write gen.py → exec → read 输出 | exec 通过才进 Step 3 | 不脑内验证 |
| Step 3 组装 | 1-2 轮 | 复制 exec 输出写 question+solution | 两个文件写入 | 不重算 |
