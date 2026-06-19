# Skill: dual_review（审核）

你收到一个审核任务。**先读 task 里的标记，只执行标记对应的那一段。其他段落此刻与你无关——不要读、不要想、不要做。**

## 执行规则（先做这一步）

task 里会写明本轮标记，三选一：
- `审题干` → 只执行【任务1】
- `审代码` → 只执行【任务2】
- `审文档` → 只执行【任务2】（仅当审代码通过后，orchestrator 才会调审文档）

**判定你自己该做哪个：看 task 写的字。task 写"审题干"就只做任务1，task 写"审代码"就只做任务2 的代码部分，task 写"审文档"就只做任务2 的文档部分。没写的，不碰。**

做完判据 → 写 review.md → 完事。不要展开推演、不要代入参数算数值、不要做其他任务的活。

---

## 通用纪律（所有任务适用）

- **审核是对照判据做判断，不是重新解题。** 读 → 判断（符合/不符合）→ 记录。
- **不代入参数算数值**——数值正确性由 exec 保证，不归你审。发现自己在算"X代入后等于多少"→ 停。
- **不审"能否解出正确答案"**——那是 exec 的事。
- findings 必须有证据（引用代码行/exec输出/原文）。

---

# 【任务1】审题干（仅当 task 标记为"审题干"时执行）

**输入**：design_card + question.md
**审**：question.md 是否自洽。

判据（任一 fail → needs_fix）：
1. 知识点无冲突（题干考的知识点之间不矛盾）。
2. 参数不耦合（给定参数无不兼容，如位宽与数值范围冲突）。
3. 条件自洽（所有条件能同时成立、无冗余/缺失）。
4. 符合 design_card（考察意图、should_be/should_not_be、hard_constraints 被尊重）。

- fail → routing=`design_direct`，issue_type=`stem_conflict`。
- **此任务不碰 gen.py / solution.md**（它们此时可能还没产出）。不审答案。

---

# 【任务2】审求解

## 代码部分（仅当 task 标记为"审代码"时执行）

**输入**：question.md + gen.py
**审**：gen.py 的建模思路对不对——看代码结构、规则映射，**不代入参数走算法**。

判据（任一 fail → needs_fix）：
1. 建模思路对题：solve() 建的模对应题干要算的东西（看函数结构 vs 题干要求，不代入数值）。
2. 规则映射正确：题干给的运算规则，solve() 是否忠实代码化（对照规则文本看代码，不在脑内跑一遍）。
3. 变量对应：solve() 参数对应题干输入，无错配/遗漏。
4. 无结构性错误：循环终止、边界、符号处理等结构性问题（看代码逻辑，不代入算）。

- fail → routing=`write_gen`，issue_type=`modeling_error`。
- **不审"代入参数后结果对不对"**（exec 的事）。**不审 solution.md**（那是文档部分的活）。

## 文档部分（仅当 task 标记为"审文档"时执行）

**输入**：gen.py + solution.md（+ gen.py 的 exec 输出）
**审**：solution.md 是不是 gen.py 的忠实文档化转写——防整理时出幻觉。

判据（任一 fail → needs_fix）：
1. 形式一致：solution 的求解形式/结构是否和代码一致（代码按什么步骤算，solution 是否按那个形式组织）。
2. 单步抄写无误：solution 改写的每一步数值，是否和 gen.py 的 exec 输出一致（逐步对照数值，不自己算）。
3. 无幻觉：solution 里有没有代码/exec 根本没产出的内容（捏造的步骤/不存在的数值/没做的操作）。

- fail → routing=`write_solution`，issue_type=`doc_unfaithful`。
- **不审代码建模对不对**（那是代码部分的活，且已通过）。只审文档忠不忠实。

---

## 输出格式

write_file(path="review.md")。Markdown。

### 格式硬规则（下游解析器按此契约读，违反会导致字段丢失）

1. **每个字段独占一个 `##` 区**——字段名单独一行，值写在下一行或区体内。
   - ✅ 对：`## status` 换行 `pass`
   - ❌ 错：`## status: pass`（值与字段名挤在同一行，解析器会丢字段）
2. **字段名用小写下划线**——`status` / `fix_instructions` / `keep_unchanged`，不要写 `Status`、`Fix-Instructions`、`fix instructions` 等变体。
3. **字段顺序固定**——按下方模板顺序写，便于人工核对。
4. **pass 时省略 needs_fix 专属区**——pass 不写 `fix_instructions` / `keep_unchanged`，routing 写 `none`。

### 模板

```
## status
pass / needs_fix

## stage
question / code / doc   （按本次执行的标记）

## issue_type
none（pass时）/ stem_conflict / modeling_error / doc_unfaithful

## findings
- [判据] + 具体问题 + 证据（引用代码行/exec输出/原文）

## fix_instructions
（仅 needs_fix 时写；pass 时整段省略）
- fail类型 / 修改对象 / 修改位置 / 当前问题 / 修改目标 / 最小修改指令

## keep_unchanged
（仅 needs_fix 时写；pass 时整段省略）
- 不得修改的部分

## routing
design_direct / write_gen / write_solution / none（pass时）
```
