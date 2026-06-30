# Skill: dual_review（审核）

你收到一个审核任务。**先读 task 里的阶段标记，只执行标记对应的那一段。** 阶段有两段：

- `审题干`（阶段1，write_gen 之前）→ 只执行【阶段1】（**对抗三 pass：A 符号合规 / B 歧义多解 / C 对抗批判**，三次独立判定、互不参考）
- `审求解`（阶段2，write_gen 完成 gen.py+solution.md 之后）→ 只执行【阶段2】（**看数据流审核**，一次过）

做完判据 → 写 review.md → 完事。不展开无界推演。

---

## 通用纪律（两阶段适用）

- **审核是对照判据做判断，不是重新解题。** 读 → 判断（符合/不符合）→ 记录。
- **阶段2 的审核靠看数据流**：读 gen.py **底部打印的数据流**（建模后一次性产出的中间值/过程/结果）+ 场景规则文件 → 验"模型忠实场景"。看数据流本身就是审核，不需要另起一遍"不代入算数值"的脑内模拟。
- **不重跑 gen.py**——exec 已跑通，数据流已由 gen.py 底部打印。读打印 + 场景规则文件对照即可（gen.py 最多 read 一次看结构，**禁止用 offset/limit 反复分页通读完整 gen.py**）。读完立即 write_file(review.md)，**审核 2 轮内必出 review.md**——不要把轮次耗在读代码上。
- findings 必须有证据（引用题干原文 / gen.py 代码行 / 打印的数据流 / exec 输出）。

---

## 概念题特例（题型为"概念题"时）

概念题**不走场景规则/数据流**那套——概念题没有 gen.py 建模、没有参数约束、没有数据流。只审两条：

- **无模糊**：表述不导致多种可能解读。
- **无事实错误**：定义/性质陈述与既定事实一致。

其余（场景规则、Pass-A/Pass-B、阶段2 数据流对照）**全部不适用**。概念题只跑这两条判据，pass/needs_fix 即出。

---

# 【阶段1】审题干（task 标记"审题干"时执行）

**输入**：design_card + question.md +（设计阶段写入的）场景规则
**时机**：write_gen 之前。审题干自洽唯一 + 场景规则合格。

阶段1 拆成**对抗两 pass**（同一个 agent 跑两次，**两次独立判定、互不参考**）。两 pass 都过才算阶段1 pass；任一 fail → needs_fix。

---

## Pass-A 符号合规（自洽）

只看符号层面是否自洽：符号定义、公式下标、初始条件、参数范围是否互相打架。

判据（任一 fail → needs_fix，issue_type=`question_error`，routing=`design_direct`）：

1. 知识点无冲突（题干考的知识点之间不矛盾）。
2. 参数不耦合（给定参数无不兼容，如位宽与数值范围冲突）。
3. **符号/公式自洽**：递推定义的符号之间、与初始条件/外部输入之间不冲突。
   - 典型反例：进位链 `C_i = G_i + P_i·C_{i-1}`，同时把 `C_0` 当外部输入 → `C_0` 既由递推算又由外部给，冲突 → **fail**。
4. 条件自洽（所有条件能同时成立、无冗余/缺失）。
5. 符号范围/量纲一致（同一符号在题内含义统一，下标/单位不漂移）。

---

## Pass-B 歧义多解（唯一解）

只看条件是否充分到推出**唯一解**——有没有"多解/歧义"导致答案不唯一或多解读。

判据（任一 fail → needs_fix，issue_type=`question_spec_error`，routing=`design_direct`）：

6. **前提清单齐全**：影响求解路径的前提是否都已声明。常见遗漏清单：
   - Cache 映射方式（直接/组相联/全相联）、组内替换策略
   - 进程调度是否可抢占、调度算法、到达时间是否给定
   - 编址方式（按字节/按字编址）、地址线/数据线口径
   - 容量口径（寻址空间容量 / 实际使用容量 / 存储容量）
   - 浮点位数（单/双精度、是否规格化、舍入模式）
   - 缺前提 → 同一题干能推出多个合法答案 → **fail**。
7. **条件充分→唯一解**：给定全部前提后，答案是否唯一？存在多解（如"最大容量"按可寻址空间 vs 实际使用都能成立）→ **fail**。
8. **无歧义表述**：题干文字是否唯一解读，无"可这样也可那样"的歧义句。
   - 典型反例："最大容量"未指明是可寻址空间还是实际使用容量 → 两个数都合法 → **fail**。
9. 符合 design_card（考察意图、should_be/should_not_be、hard_constraints 被尊重）。

---

## Pass-C 对抗批判（换读法 / 查漏位，题就崩）

Pass-A/B 是**正向验证**（能否推出唯一解）。Pass-C 是**对抗性批判**：换一种标准读法、或查一个漏位，题是否还成立？专抓正向验证的盲区——内容/答案可能"对"，但题干不鲁棒。

判据（任一 fail → needs_fix）：

### C1 前提相干（配置可达 / 前提不打架 / 公式忠实机制）
- 声称的配置 / 各级条数在所述机制下是否**真的可达**？前提之间是否互相打架？
- 建模/求解公式是否**忠实机制**（而非把某部分当独立空间、绕开机制约束）？
- 反例（扩展操作码）：题干"三地址指令**已占满**操作码编码空间" + "二地址 200 条"——扩展操作码是**链式前缀预留**机制（上级留前缀→下级扩展），上级占满则下级无前缀可用；且公式把"二地址 opcode"当成独立 L-2a 位空间（256）是误用，实际空间 = 上级预留前缀 × 2^a。→ **fail**（前提不可行 + 公式不忠实机制）。

### C2 术语精度（换标准读法题是否仍成立）
- 关键术语（n 位 / 补码 / 编址方式 / 容量口径 / 寻址方式）是否有歧义？换"标准读法"是否仍得同一答案？
- 反例（变形补码）：题干"A、B 均在 **n 位补码**可表示范围内"，n=3。标准"n 位补码" = 共 n 位（3 位范围 [-4,+3]，-5/-6 装不下）；出题意图是"n 位数值位的变形补码"。两读、其一失效 → **fail**（消歧，改"n 位数值位的变形补码"）。

### C3 设计完备（未使用位 / 镜像 / 使能覆盖）
- 片选 / 译码 / 地址分配类：未使用的地址位如何处理？是否存在地址镜像（重叠）？使能逻辑是否覆盖全部相关高位？
- 反例（74LS138 片选）：使能只接 A15、A14 未参与 → 12KB 存储区在 4000H~6FFFH 镜像；题干却谎称"保证仅当 A15=0 即地址落在存储区"（A15=0 实为 32KB 半区）。→ **fail**（要么诚实声明部分译码 + 让学生算镜像，要么把 A14 纳入使能做全译码）。

### 门槛（与三档审核一致——核心是拦"真会导致误解/错解"，不是拦一切）
- **error**（前提不可行 / 答案错 / 设计坏，如 C1 扩展操作码、C3 谎称覆盖）→ needs_fix，issue_type=`question_error`，routing=`design_direct`（重设计）。
- **ambiguity**（术语两读会改答案，如 C2）→ needs_fix，issue_type=`question_spec_error`，routing=`design_direct`（消歧）。
- **expression_only**（纯文字润色、不影响求解、无歧义）→ **不拦**，仅在 findings 注明 cosmetic（交由后续 wording_fix 处理，不回退重生成）。

---

## 阶段1 通用补充判据（Pass-A / Pass-B / Pass-C 之外的题干层）

10. **场景规则合格**（核心判据）——场景规则文件（或题干内声明）是否满足：
    - **是参数约束，不是答案配方**：场景规则描述的是"给定参数间必须成立的约束/关系"（如"按字节编址 → 容量_bytes == 2**地址线数"、"商×除数+余数 == 被除数"），**禁止**写成 answer-recipe（如"答案=2MB"/"物理地址=0x4C3F4"/"必须同时用地址线+数据线"）。写成答案配方 → **fail**。
    - **已声明**：题干/场景规则文件里有没有给出本题成立的参数约束？
    - **可验**：约束是能被 gen.py 建模实现、且其数据流打印可供阶段2 直接对照验的具体关系，不是"结构合法""合理"这类空话。
    - 反例：题干说考旋转辨析，场景规则只写"树保持平衡"——零旋转也满足，约束没覆盖考点 → **fail**。应声明"至少触发 1 次旋转"。
    - fail → issue_type=`question_error`，routing=`design_direct`。

- **不碰 gen.py / solution.md**（此时还没产出）。不审答案。
- 概念题不走阶段1 两 pass，见上方"概念题特例"。

---

# 【阶段2】审求解（task 标记"审求解"时执行）

**输入**：question.md + gen.py + solution.md + **gen.py 底部打印的数据流** + 场景规则文件 + **assert_scan.md**（gen.py 写完后的自动自检报告，write_gen 阶段产出）（+ gen.py 的 exec 输出）
**时机**：write_gen 完成 gen.py+solution.md 之后。**看数据流审核**——读 gen.py 底部打印的数据流 + 场景规则，验"模型忠实场景"（触发满不满足、定律成不成立，统一看数据流）。

判据（任一 fail → needs_fix）：

### 维度A 建模忠实（routing=write_gen）
1. solve() 建的模对应题干要算的东西（函数结构 vs 题干要求，**看数据流的中间值流向**判断）。
2. 规则映射正确：题干运算规则是否忠实代码化（对照场景规则看数据流，不在脑内重跑一遍）。
3. 变量对应：参数对应题干输入，无错配/遗漏。
4. 无结构性错误：循环终止、边界、符号处理（看数据流逻辑）。

### 维度B 断言合适（routing=write_gen）
5. **场景规则被 assert 覆盖**：场景规则文件里的每条参数约束，gen.py 是否都有对应 assert？漏一条 = 漏译 → fail。
6. **assert 没弱化**：有没有把"考旋转"弱化成 `assert is_balanced(tree)` 这类结构判据（零旋转也过）？弱化 = 让坏题静默放行 → fail。
7. **assert 非恒真 + 非答案配方**（先读 assert_scan.md）：gen.py 写完后已自动扫过假 todo——
   - **恒真**（不可证伪）：`assert True` / `assert x == x` / `assert len(x) >= 0` 这类永远成立的废话断言。
   - **答案配方**（不可推广）：`assert answer == 2097152` / `assert result == "0x4C3F4"` 这类把答案字面量写死的断言（换参数即失效，等于橡皮图章）。
   - assert_scan.md 标 `[tautology/high]` 或 `[answer_recipe/high]` 的 → **直接 fail**（issue_type=`assertion_defect`，routing=`write_gen`，fix=改成参数约束或删掉）。`med/low` 需你复核定夺。
   - 注：assert_scan 是**语法层初筛**——语义层假 todo（如 `n_int != D` 只对当前参数成立、变量算后未用）仍需你读 gen.py 判断，扫描器不覆盖。
8. **选择题专属**：选项约束在数据流中可验——`assert len({A,B,C,D})==4`（互异）+ 数据流底部打印每选项 {正确值, 实际值, 改错方式}（A=正确值=答案；B/C/D=各自正确值+按设计改错）。不再 `assert A==correct_value`（answer-recipe，已禁）。漏打印/撞值 → fail。

### 维度C 充分性 + 设计一致性（routing=write_gen 或 design_direct）
9. **充分性（合围，看数据流）**：gen.py 底部**打印的数据流**，满足场景规则声明的约束吗？读数据流比对场景规则——
   - 例：场景规则要求"至少 1 次旋转"，数据流显示 rotation_count=0 → **充分性 fail**（参数没触发考点）。
   - 例：场景规则要求"商×除数+余数 == 被除数"，数据流打印的三个值代入不成立 → **充分性 fail**（定律没成立）。
   - 这是"参数打败考点 / 定律没成立"的唯一可靠卡口。
10. **选择题专属充分性**：读数据流算出的 4 个选项值——撞值（{A,B,C,D}<4）/ 正确值不唯一（A∈{B,C,D}）/ 干扰项不像声明的错误类型产物 → **adequacy_fail**。这是选择题坏选项集静默放行的唯一可靠卡口。
11. **设计一致性**：数据流产出的结构/覆盖面，是否对齐 design_card 的 core_knowledge_intent / expected_form？跑偏 → fail。
    - 充分性/一致性 fail 的 routing 判据：
      - **参数没触发**：场景规则在 hard_constraints 下原则可达（存在已知参数组合能触发，只是当前这组没命中）→ `write_gen`（换参数重算）。
      - **场景规则本身定错/不可达**：约束与考察意图矛盾，或在该题型下无解 → `design_direct`（重定场景规则 / 换考点角度）。

### 维度D 文档忠实（routing=write_gen）
12. 形式一致：solution.md 的求解形式/结构是否与 gen.py 一致。
13. 单步抄写无误：solution 改写的每步数值，是否与 gen.py 数据流打印一致（逐步对照，不自己算）。
14. 无幻觉：solution 里有没有数据流根本没产出的内容（捏造步骤/数值/操作）。

### 维度E 题面规范性（routing=write_gen）——L2 结构兜底
15. **题型一致性**：题面（question.md）实际形式与声明**题型**吻合——单选必有 4 选项(A/B/C/D)；填空必有空格且不是四选一；判断必有 对/错/√/× 陈述。**题型错位** → fail。
16. **题干完整性**：选项/空格/子问齐全，**无截断**（如"下列说法正确的是："后无选项）→ fail。
- 注：原"题意明确性"判据已迁移到阶段1 Pass-B（歧义多解），阶段2 不重复审。
- 维度E fail → issue_type=`structure_defect`，routing=`write_gen`。

### 答案层（routing=write_gen）
17. **题干自洽唯一但答案错**：当阶段1 判定题干自洽且唯一解（Pass-A/Pass-B 都过），但数据流算出的答案与正确值不符（模型/求解错，非题干错）→ issue_type=`solution_error`，routing=`write_gen`。

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
none（pass 时）
阶段1：question_error（符号/场景规则自洽缺陷）/ question_spec_error（歧义多解）
阶段2：modeling_error / assertion_defect / adequacy_fail / doc_unfaithful / structure_defect / solution_error（题干自洽唯一但答案错）
（可多个；下游 graph 只读 status+routing 做路由，issue_type 供审计可追溯）

## pass_log（阶段1 专用，记录三 pass 各自结论）
Pass-A 符号合规: pass / fail（简注）
Pass-B 歧义多解: pass / fail（简注）
Pass-C 对抗批判: pass / fail（简注；若 needs_fix 注明 error/ambiguity/expression_only）
（阶段2 不写此区）

## findings
- [Pass-A/Pass-B/维度/判据] + 具体问题 + 证据（引用题干原文 / gen.py 代码行 / 数据流 / exec 输出）

## fix_instructions
（仅 needs_fix 时写；pass 时整段省略）
- fail 类型 / 修改对象 / 修改位置 / 当前问题 / 修改目标 / 最小修改指令

## keep_unchanged
（仅 needs_fix 时写；pass 时整段省略）
- 不得修改的部分

## routing
design_direct / write_gen / none（pass 时）
```
