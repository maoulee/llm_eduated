# Skill: dual_review（审核）

你收到一个审核任务。**先读 task 里的阶段标记，只执行标记对应的那一段。** 阶段有两段：

- `审题干`（阶段1，write_gen 之前）→ 只执行【阶段1】
- `审求解`（阶段2，write_gen 完成 gen.py+solution.md 之后）→ 只执行【阶段2】（**合并审核**，一次过）

做完判据 → 写 review.md → 完事。不展开无界推演、不代入参数算数值、不重跑 gen.py。

---

## 通用纪律（两阶段适用）

- **审核是对照判据做判断，不是重新解题。** 读 → 判断（符合/不符合）→ 记录。
- **不代入参数算数值**——数值正确性由 exec 保证，不归你审。发现自己在算"X 代入后等于多少"→ 停。
- **不重跑 gen.py**——exec 已跑通，读它的输出对照即可。
- findings 必须有证据（引用题干原文 / gen.py 代码行 / exec 输出）。

---

# 【阶段1】审题干（task 标记"审题干"时执行）

**输入**：design_card + question.md
**时机**：write_gen 之前。审题干自洽 + **通过条件是否合格**。

判据（任一 fail → needs_fix，routing=design_direct）：
1. 知识点无冲突（题干考的知识点之间不矛盾）。
2. 参数不耦合（给定参数无不兼容，如位宽与数值范围冲突）。
3. 条件自洽（所有条件能同时成立、无冗余/缺失）。
4. 符合 design_card（考察意图、should_be/should_not_be、hard_constraints 被尊重）。
5. **通过条件已声明且合格**（核心判据）：
   - **存在**：题干有没有声明"本题成立 ⇔ 期待结果的可机检特征"？
   - **可证伪**：特征是能被 exec 检出"没满足"的具体断言，不是"结构合法""合理"这类空话。
   - **覆盖考察目标**：特征能不能检出"考点没被参数真的触发"？
     - 反例：题干说考旋转辨析，但通过条件只写"树保持平衡"——零旋转也满足，没覆盖考点 → **fail**。应声明"至少触发 1 次旋转"。

- fail → routing=`design_direct`，issue_type=`stem_conflict`（含通过条件缺陷）。
- **不碰 gen.py / solution.md**（此时还没产出）。不审答案。

---

# 【阶段2】审求解（task 标记"审求解"时执行）

**输入**：question.md + gen.py + solution.md（+ gen.py 的 exec 输出）
**时机**：write_gen 完成 gen.py+solution.md 之后。**合并审核**——建模忠实 + 断言合适 + 充分性 + 设计一致性 + 文档忠实，一次过。

判据（任一 fail → needs_fix）：

### 维度A 建模忠实（routing=write_gen）
1. solve() 建的模对应题干要算的东西（函数结构 vs 题干要求，不代入数值）。
2. 规则映射正确：题干运算规则是否忠实代码化（对照规则文本看代码，不在脑内跑一遍）。
3. 变量对应：参数对应题干输入，无错配/遗漏。
4. 无结构性错误：循环终止、边界、符号处理（看代码逻辑，不代入算）。

### 维度B 断言合适（routing=write_gen）——这次的重点
5. **通过条件被 assert 覆盖**：题干声明的每个通过条件，gen.py 是否都有对应 assert？漏一个 = 漏译 → fail。
6. **assert 没弱化**：有没有把"考旋转"弱化成 `assert is_balanced(tree)` 这类结构判据（零旋转也过）？弱化 = 让坏题静默放行 → fail。
7. **assert 非恒真**：有没有 `assert True` / `assert len(x) >= 0` 这类永远成立的废话断言凑数？→ fail。
8. **选择题专属**：选项通过条件是否被 assert？应有 `assert len({A,B,C,D})==4`（互异）+ `assert A==correct`（A 标的是正确值）。漏 → fail。

### 维度C 充分性 + 设计一致性（routing=write_gen 或 design_direct）——堵根因的关键
9. **充分性（合围）**：gen.py exec 的**事实输出**，满足题干声明的通过条件吗？读 exec 输出比对声明特征——
   - 例：声明"至少 1 次旋转"，exec 显示 0 次旋转 → **充分性 fail**（参数没触发考点）。
   - 这是"参数打败考点"的唯一可靠卡口（零旋转 defect 就是这里漏的）。
10. **选择题专属充分性**：读 exec 算出的 4 个选项值——撞值（{A,B,C,D}<4）/ 正确值不唯一（A∈{B,C,D}）/ 干扰项不像声明的错误类型产物 → **adequacy_fail**。这是选择题 defect（坏选项集静默放行）的唯一可靠卡口。
11. **设计一致性**：exec 产出的结构/覆盖面，是否对齐 design_card 的 core_knowledge_intent / expected_form？跑偏 → fail。
   - 充分性/一致性 fail 的 routing 判据（区分两类，避免在 fix_gen/fix_design 间横跳）：
     - **参数没触发**：通过条件在 hard_constraints 下原则可达（存在已知参数组合能触发，只是当前这组没命中）→ `write_gen`（换参数重算）。
     - **通过条件本身定错/不可达**：条件与考察意图矛盾，或在该题型下无解（如要求 AVL 旋转但序列恒平衡无解）→ `design_direct`（重定条件 / 换考点角度）。

### 维度D 文档忠实（routing=write_gen）
12. 形式一致：solution.md 的求解形式/结构是否与 gen.py 一致。
13. 单步抄写无误：solution 改写的每步数值，是否与 gen.py exec 输出一致（逐步对照，不自己算）。
14. 无幻觉：solution 里有没有 exec 根本没产出的内容（捏造步骤/数值/操作）。

### 维度E 题面规范性（routing=write_gen）——L2 结构兜底
15. **题型一致性**：题面（question.md）实际形式与声明**题型**吻合——单选必有 4 选项(A/B/C/D)；填空必有空格且不是四选一；判断必有 对/错/√/× 陈述。**题型错位**（声明填空却出成选择、声明单选却无选项）→ fail。
16. **题干完整性**：选项/空格/子问齐全，**无截断**。单选缺选项、填空缺空格、题干半句断掉（如"下列说法正确的是："后无选项）→ fail。
17. **题意明确性**：无歧义表述（如"最大容量"按可寻址空间还是实际使用容量；条件是否唯一解读）。表述歧义 → fail。
- 维度E fail → issue_type=`structure_defect`，routing=`write_gen`（修 question.md 题面，使形式符合声明题型）。

- 多维度同时 fail → findings 写多条，issue_type 写多个，routing 取**最上游**修复点（如建模错+文档错 → routing=write_gen，文档会随之重算）。

---

## 输出格式

write_file(path="review.md")。Markdown。

### 格式硬规则（下游解析器按此契约读，违反会丢字段）

1. **每个字段独占一个 `##` 区**——字段名单独一行，值写在下一行或区体内。
   - ✅ 对：`## status` 换行 `pass`
   - ❌ 错：`## status: pass`（值与字段名挤同行，解析器会丢字段）
2. **字段名用小写下划线**——`status` / `fix_instructions` / `keep_unchanged` / `routing`，不要写变体。
3. **字段顺序固定**——按下方模板顺序写，便于人工核对。
4. **pass 时省略 needs_fix 专属区**——pass 不写 `fix_instructions` / `keep_unchanged`，routing 写 `none`。

### 模板

```
## status
pass / needs_fix

## stage
question / solution   （按本次执行的阶段标记）

## issue_type
none（pass 时）/ stem_conflict（阶段1）/ modeling_error / assertion_defect / adequacy_fail / doc_unfaithful / structure_defect（阶段2，可多个）
（人工诊断字段——下游 graph 只读 status+routing 做路由，不消费 issue_type；写它是为了审计可追溯）

## findings
- [维度/判据] + 具体问题 + 证据（引用题干原文 / gen.py 代码行 / exec 输出）

## fix_instructions
（仅 needs_fix 时写；pass 时整段省略）
- fail 类型 / 修改对象 / 修改位置 / 当前问题 / 修改目标 / 最小修改指令

## keep_unchanged
（仅 needs_fix 时写；pass 时整段省略）
- 不得修改的部分

## routing
design_direct / write_gen / none（pass 时）
```
