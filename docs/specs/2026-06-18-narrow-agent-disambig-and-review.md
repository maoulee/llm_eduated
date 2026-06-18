# 窄 agent 三步架构 + 双点审核 — 设计规格

> 本文件是 write_gen 消歧方案 + 系统性不确定性治理的**单一信息源**。
> 含：根因证据、确定性原理、6 步架构、review 合并 agent、write_gen 消歧、退回机制。
> 最近更新 2026-06-18。供跨会话/跨工具接手用。

## Context（为什么做）

write_gen（建模码智能体）对补码除法这类**有版本歧义的算法题**巨想崩溃：reasoning 飙到 89064 字撑爆 max_tokens、content=0、无产出。经过一整天定位，根因不是任务本质困难，而是**不确定性**的系统性问题。本 spec 给出从根因到完整架构的解法。

## 根因证据（已实证）

### 实验 1：干净 loop 排除"行为控制"假设

绕开 DocScheduler 全部行为控制（no_output 重试/丢弃 reasoning/trim），用干净 agent loop（保留每轮 reasoning、不 trim、不丢弃）跑同一题：

| | reasoning | 产出 |
|---|---|---|
| DocScheduler(write_gen) | 60K-89K 撑爆 | ❌ |
| 干净 loop | r1=89064(撑爆) r2=90119(撑爆) | ❌ |

**结论**：行为控制不是杠杆。scheduler/干净 loop 两条路径、reasoning 保留与否，都拦不住巨想。证伪"思考丢弃致重想"假设。

### 实验 2：reasoning 内容分析（为何这么久）

89064 字 reasoning 的内部结构（量化）：

| 重复信号 | 次数 |
|---|---|
| "Actually"（自我推翻） | 26 |
| "Wait"（重新想） | 21 |
| "补码加减交替法"重述算法 | 17 |
| "different version/textbook"（版本横跳） | 7 |
| R₁=（同一余数重算） | 12 |
| shift left（重算验证） | 18 |

被截断时仍在算算法（7 分钟、2.3 万字后没进入写码）。

**结论**：根因 = **版本歧义**。补码除法在不同教材有多版本（n步/n+1步、恒置1/余数恢复、符号位单独定/首商即符号），模型横跳 7 次无法裁定唯一正确版本 → 反复重算验证 → 巨想崩溃。

### 实验 3：消歧验证（方案可行性的决定性证据）

控制变量（同模型、同 skill、同题），唯一变量 = 是否注入消歧信息（钉死算法版本的标准步骤+自派示例）：

| 实验 | 第1轮 reasoning | 耗时 | 产出 |
|---|---|---|---|
| 无消歧 | 89064（撑爆） | 两轮撑爆 | ❌ 0 产出 |
| 消歧-示例有矛盾 | 51947 | 261s | ✅ 150 行 |
| **消歧-示例自洽** | **24921** | **129s** | ✅ 116 行 |

关键发现：
- 自派示例让 reasoning 从 89064 砍到 **24921（-72%）**。
- "different version" 信号 7→0（版本歧义彻底消除）。
- 第1轮直接产出 write_file，第2轮 4 秒 exec 通过。
- **矛盾示例反而制造新纠结**（模型校验矛盾花 5 万字）→ 消歧信息自洽是生命线。

**结论**：消歧方案有效。版本歧义是根因，自洽的消歧信息能根治。模型自主选了最优建模方式（整数取模），"模拟硬件 vs numpy"不是问题。

## 确定性原理（核心·整个架构的逻辑根基）

> **确定性答案 = 题干自洽 × 建模可行**

code-as-truth：gen.py 是确定性的，给定正确建模，exec 输出就是确定答案。所以：

- **不审"答案对错"**——它无法直接判（无标准答案参照，自洽但错版本的答案会通过任何"一致性"检查）。
- **审两个前置正确性**：
  1. **题干自洽**（输入正确）：知识点无冲突、参数不耦合、条件自洽、符合 design_card 要求。
  2. **建模可行**（过程正确）：按这个建模思路，步骤走得通、变量对、逻辑链完整。
- 答案正确性是这两个的**自动推论**（exec 保证），不在审核范围。

这把"难以验证的答案正确性"转化为"可验证的两个前置正确性"。

**"我也会出错"的兜底**：模型自定版本（消歧兜底情况）→ VERSION 标记 → 人类专家审。这是最后一道，且只对兜底情况触发（参考题消歧已外部锚定，不需人工）。

## 6 步架构

```
① design_direct  → question.md
        ↓
② review（阶段=审题干）
   ├─ 题干自洽？参数/条件/知识点冲突？符合 design_card？
   ├─ pass → 继续
   └─ needs_fix → 退回 design_direct 修题
        ↓
③ write_gen → gen.py（消歧拉参考题定版本/兜底自定+VERSION标记）→ exec
        ↓
④ write_solution → solution.md（纯整理 gen 输出，确定）
        ↓
⑤ review（阶段=审求解：建模可行 + 题干合围）
   ├─ 建模可行 + 结果与题干合围 → 确定（题干自洽 × 建模可行 = 答案确定）
   ├─ 建模问题 → 退回 write_gen 修建模
   ├─ 合围失败-A（参数缺陷）→ 退回 design_direct 改参数
   └─ 合围失败-B（设问问题）→ 退回 design_direct 改设问
        ↓
⑥ final（最终交付）
```

**两个审核点各管一头，互不重叠：**
- review 阶段1（审题干）：审**输入**自洽性。
- review 阶段2（审求解）：审**过程可行性**。

## review agent（合并设计·单 agent + 单 skill + 阶段参数）

合并理由：审题干与审求解职责不冲突（一个审输入、一个审过程，维度不同）。合并为单 agent，由 orchestrator 传入阶段参数让它知道审哪个。GLM-5.2 是强模型，单 skill 写清两阶段判据即可，不用搞两套 skill。

### 契约（agent md）

```
name: review
phase: 2
output_file: review.md   # 两阶段都写 review.md（覆盖前一轮）
required_tools: [write_file, read_file]
required_sections: [status]
multi_turn: false
behavior: dual_reviewer
skills: [dual_review]
```

### dual_review skill（两阶段判据）

**阶段1：审题干（输入 design_card + question.md）**
- 判据（任一 fail → needs_fix，退回 design_direct）：
  1. 知识点无冲突：题干考的知识点之间不矛盾。
  2. 参数不耦合：给定参数之间无不兼容（如位宽与数值范围冲突）。
  3. 条件自洽：所有给定条件能同时成立、无冗余/缺失。
  4. 符合 design_card：考察意图、should_be/should_not_be、hard_constraints 都被尊重。
- 红线：**不审答案**（此阶段无解）；**不判断算法版本对错**（那是 write_gen 的事）。

**阶段2：审求解（输入 question.md + gen.py + solution.md，可选 design_card 供考察意图）**

审2 审两个不冲突的维度——**过程可行** + **结果与题干合围**：

*维度1·建模可行（审"过程"）*：
  1. 建模思路可行：按 gen.py 的算法方式，步骤逻辑上走得通（循环终止、分支覆盖、终止条件正确）。
  2. 变量正确：gen.py 的输入参数对应题干给定值，无错配/遗漏。
  3. 逻辑链完整：从初始状态到答案的每一步可追溯，无跳步。
  4. 实现忠实：gen.py 的实现与其声明的 VERSION 一致，无偷工/错规则。

*维度2·题干合围（审"结果与输入"）*：
  5. exec 结果与题干给定条件能否同时成立？能合围 → 此项 pass。无法合围 → 判 A 还是 B：
     - **B 设问方式问题**：无法合围是算法固有特性导致（如恒置1法精度损失、补码除法余数需修正）。算法对、参数也对，但设问要了算法给不了的东西。fix：改设问措辞（接受算法特性）或换算法。
     - **A 参数缺陷**：非算法特性（算法本应合围却没合围）。输入参数选得不好（除不尽/边界值/中间步骤退化）。fix：改参数值。

*退回路由*（合围维度判 A/B 后）：
  - 维度1 fail（建模问题）→ 退回 write_gen 修建模。
  - 维度2 fail-A（参数缺陷）→ 退回 design_direct 改参数。
  - 维度2 fail-B（设问问题）→ 退回 design_direct 改设问。
  - fix_instructions 必须明确标注 fail 类型（建模/参数/设问）+ 具体修改对象/位置/目标。

- **关键红线（防纠结）**：审"**可行性 + 合围**"，**明令禁止判断"版本是否最优/是否唯一正确"**。判 A/B 是"找矛盾来源"（算法特性 vs 参数），不是"裁版本对错"——不会触发歧义纠结。exec 已跑通，审2 不重跑，只审逻辑 + 合围。
- 合围判据的实证依据：补码除法恒置1法，真值 X/Y=-0.846 但恒置1商=-0.8125，差 0.034——这是算法固有特性（B），不是参数错（A）。强模型（GLM-5.2）推理能力足够判这个，只要给它明确的 A/B 判据 + 回退步骤。

### 阶段切换

orchestrator 调用 review 时传入 `stage` 参数（在 task 里写明"本轮审题干"或"本轮审求解"）。skill 据此切换判据。两阶段都写 review.md（后写覆盖前写）。

## write_gen 消歧流程（func_model skill 升级）

```
write_gen 拿到 question.md
  ① 先快速判断：题目是否有"多种解法/版本歧义"？
     否（直接计算/单步推导）→ 直接建模
     是 → ②
  ② 消歧：从 design_card 读 reference_questions 路径
     → read_file 拉 data/question_experiences/xxx.md（含题干+解题轨迹，自洽）
     → 照参考题演示的算法版本/步骤定版本（方法锁定）
  ③ 兜底（拉不到/参考题无相关算法/仍纠结）：
     自己选一个版本，gen.py 顶部注释声明 VERSION（如 # VERSION: 补码除法-恒置1法-n+1步）
     不纠结，直接写码
  ④ 建模方式：整数取模（补码=取模运算），勿逐位模拟硬件、不引入 numpy。
  ⑤ exec 验证。
```

**认知红线（防过载，承继已验证的）**：
- 方法锁定后不重选版本、不在 reasoning 里重推算法、不手算验证（exec 会验）。
- 消歧信息必须自洽（矛盾的标准会重新制造纠结，实证）。

## 退回机制（orchestrator）

```python
# review 阶段1 失败 → 退回 design_direct
review_q = await run_review(stage="question")
if review_q.status == "needs_fix":
    await run_design_direct(fix_instructions=review_q.fix_instructions)  # 带 fix 意见重跑
    review_q = await run_review(stage="question")  # 再审（上限2轮）

# review 阶段2 失败 → 退回 write_gen
review_s = await run_review(stage="solution")
if review_s.status == "needs_fix":
    await run_write_gen(fix_instructions=review_s.fix_instructions)  # 带 fix 意见重跑
    review_s = await run_review(stage="solution")  # 再审（上限2轮）
```

退回带 fix_instructions（review 产出的具体问题：哪冲突、哪变量错），上游据此最小修改。

## VERSION 标记 → 人类专家审（兜底）

- write_gen 兜底自定版本时，gen.py 顶部必写 `# VERSION: <算法>-<变体>-<关键规则>`。
- 终审/final 环节扫描 VERSION 标记，在交付物里点出"此处为模型自定版本，请人工复核算法变体选择"。
- 只对**兜底情况**触发（无参考题消歧时）。参考题消歧已外部锚定版本，不需人工。

## 实施清单（待做）

1. **func_model skill 升级**：加消歧流程（先判断→read_file 拉参考题→方法锁定）+ 兜底（自定版本+VERSION标记）+ 整数取模建模指令。
2. **write_gen agent**：确认 read_file 在工具列表（已有）；加"题干冲突前置校验"（审1 的一部分可前置到 write_gen，冲突直接退回不强行建模）。
3. **dual_review skill 新建**：两阶段判据 + 防纠结红线（审可行不审版本）。
4. **review agent md**：behavior=dual_reviewer，skills=[dual_review]。
5. **orchestrator**：串 6 步流程 + 两处退回循环（上限2轮）+ 阶段参数传 review。
6. **终审/final**：扫 VERSION 标记点给人类审。

## 已验证事实（锚点）

- 消歧自派示例：reasoning 89064→24921，2 轮产出 116 行 gen.py，exec 通过。
- 整数取模建模是模型自主最优选择（gen.py 实证），无需 numpy。
- `thinking_budget` 是 vLLM 参数，线上 GLM 忽略（只认 enable_thinking 开关）。
- `data/question_experiences/` 有补码相关题但**无补码加减交替法除法**（数据缺口，靠兜底+VERSION过渡）。
- `reference_questions` 字段（contracts.py:36）是前端检索→后端的桥梁，assemble 据此拉完整参考题。

## 实测发现（2026-06-18 流水线测试 + 诊断）

### write_gen 兜底场景（无参考题）：skill 文字逐版优化但仍撑爆

| func_model 版本 | r1 reasoning | 结果 |
|---|---|---|
| v1 "自选版本"（提歧义+选） | 65000 撑爆 | ❌ |
| v2 "默认规则"（提歧义+默认） | 44000 撑爆 | ❌ |
| v3 "不提歧义"（普通题） | 40000 撑爆 | ❌ |
| v4 "思考纪律"（定方向不算细节） | 45857 撑爆 | ❌ |
| v5 "思考纪律+1+1引导" | 51939 撑爆 | ❌ |
| **兜底关思考（enable_thinking=False）** | **0** | **✅ 30s 产出 gen.py** |
| 对照：注入外部消歧信息（主路径） | 24921 | ✅ |

结论：skill 文字逐版压低（65000→40000，证明"指令诱导确认"是部分原因），但都跨不过撑爆。**唯一根治兜底的是关思考或注入外部消歧信息。**

### 真实流水线（6步）测试：思考ON 的步骤普遍撞墙

| 步骤 | 思考 | 耗时 | 产出 |
|---|---|---|---|
| ①design_direct | ON | 314s（撞墙重试） | question.md ✓ |
| ②review_question | ON | 211s | review.md pass ✓ |
| ③write_gen | **OFF** | **62s** | gen.py ✓ |
| ④write_solution | ON | 342s（撞墙重试） | solution.md ✓ |
| ⑤review_solution | ON | ~300s+（反复重试） | — |
| 总耗时 | | ~20min | |

**唯一快的步骤是 ③write_gen（关思考）。** 其他思考ON 的步骤（①④⑤）都 reasoning 撑爆、重试，耗时翻 5 倍。

### 关键发现：CORE.md 思考纪律确实注入了，但 GLM 不遵守

`design_direct` 的最终 prompt（agent_loader 拼 CORE.md + agent md）**确实包含**完整的思考纪律：
- "数值/答案由 exec 代码确定，不脑内算、不脑内推演"
- "evidence over assumption"
- "脑内算术/脑内推演求解——禁止（code-as-truth）"

**但 GLM-5.2 思考ON 遇到补码除法，没遵守，照样 reasoning 撑到 37000。**

→ 结论：**skill 文字（无论 CORE 通用纪律还是 func_model 专用纪律）压不住 GLM-5.2 思考ON 对复杂迭代算法的推演本能。** 这是 GLM-5.2 的行为特性，不是 skill 写得不好。

### dual_review skill 验证成功（思考ON 但产出了高质量审核）

单独验证（write_gen 关思考产 gen.py → dual_review 审求解）：
- review.md 产出 ✅，status=needs_fix, routing=write_gen（建模问题退回 write_gen）。
- 精确诊断了 gen.py 的真实 bug（商位5位当6位处理→格式和真值全错），给3条证据+逐步验证。
- A/B 判据正确（合围失败归因到维度1建模bug，没误判成参数A或设问B）。
- 防纠结红线生效（没去裁版本对错）。
- **"审建模可行"真能兜住 write_gen 的错**——架构确定性原理闭环验证。

## 待定决策：思考策略（最核心·未定）

问题：补码除法这类复杂算法题，除 write_gen（已关思考）外，design_direct/write_solution/review 思考ON 都撞墙（~5min/步），总耗时~20min。

正在做的对照实验：用 Claude 子智能体做 design_direct，看 Claude 内在纪律能否压住补码除法推演。
- 若 Claude 压住 → 问题在 GLM 对文字约束的遵从度，需找 Claude 的内在机制外化。
- 若 Claude 也压不住 → 补码除法推演是任务固有负荷，只能靠机制（关思考/max_tokens）。

候选策略（待 Claude 对照结果后定）：
- A. 复杂题全链路关思考，只 review 保留思考。
- B. 各 skill 加精准思考纪律（像 func_model 那样，针对每步的"脑内过度思考"诱因）。
- C. 混合：产题链（design/write_gen/write_solution）关思考，review 思考ON。

