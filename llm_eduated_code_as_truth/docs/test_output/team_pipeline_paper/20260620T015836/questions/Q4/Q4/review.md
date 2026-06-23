## status
needs_fix

## stage
solution

## issue_type
doc_unfaithful

## findings
- [维度D/判据13 单步抄写无误] **solution.md 中 C 的值与 gen.py 不一致**。solution.md 干扰项表（第53行）写 C=1，并解释"该串的最长相等前后缀为 'a'（长度 1）"（第56行）。但 gen.py 中 `C = lps[j-1] = lps[8]`（第60行），即 P[0..8]="abacababc" 整串的最长相等前后缀长度。对 "abacababc" 而言，前缀 "a"（s[0]）与后缀 "c"（s[8]）不匹配，逐步回退后 lps[8]=0，因此 C 应为 **0** 而非 1。solution.md 第56行的解释自身也矛盾——写道"前缀 'a' 与后缀 'c' 不匹配"却得出"k=1"。

- [维度D/判据13] solution.md 第39行完整 next 数组 `[0, 1, 1, 2, 1, 2, 3, 4, 3]` 与 gen.py `nxt[1:]` 一致，A=3、B=2、D=4 均正确，仅 C 值有误。

- [维度B/判据5] gen.py 断言段未对条件3中 C 的特征做独立 assert（仅 assert 了互异、A 正确、B=A-1、D=next[8]、A≥3）。C 的正确值依赖 exec 输出而非 assert 验证——这本身不构成 fail（互异 assert 间接覆盖），但导致 C 值错误未被 assert 拦截。建议补充但非必须。

## fix_instructions
- doc_unfaithful / 修改对象: solution.md / 修改位置: 第53行干扰项表 C 行及第56行 C 的说明段 / 当前问题: C 的值写为 1，实际 gen.py 中 lps[8]=0 / 修改目标: C=0，并修正解释文字 / 最小修改指令: 将第53行 C 的值从 1 改为 0；将第56行的解释修改为："0-based 偏移错误将 P 的字符下标从 0 开始编号，导致计算的是 P[0..j-1]（即 P[0..8] = 整个模式串 'abacababc'）的最长相等前后缀长度。该串最长相等前后缀为 0（前缀 'a' 与后缀 'c' 不匹配），故 C = 0。"；将第62行四选项互异验证更新为 "A=3, B=2, C=0, D=4 → 四个值互不相同"。

## keep_unchanged
- gen.py 代码逻辑和 assert 段（无需修改，exec 输出本身正确）
- solution.md 中 next 数组计算部分（第一步，第1-39行，A/B/D 值均正确）
- question.md 题干和通过条件

## routing
write_solution
