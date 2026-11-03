## status
pass

## stage
solution

## issue_type
none

## findings
- [维度A·建模忠实] solve() 建模正确：`to_complement_double` 用 `value % mod`（Python 对负数取模天然正确）生成 8 位双符号位补码；`full_add_bits` 标准 LSB→MSB 逐位进位加法；`judge_overflow_double_sign` 检测双符号位是否一致，规则映射忠实题干。变量 A=-50/B=-40/n=7 与题干参数一致，无错配。（gen.py L8-17, L20-44, L47-61）
- [维度B·断言合适] 三个通过条件均有对应 assert，无弱化、无恒真：
  - 条件1（A+B 溢出）：`assert overflow_ab == True` + `assert sum_ab[0] != sum_ab[1]`（L204-205），检出双符号位不一致。
  - 条件2（A−B 不溢出）：`assert overflow_asub == False` + `assert sum_asub[0] == sum_asub[1]`（L210-211），检出双符号位一致。
  - 条件3（[-B]补 连同符号位全取反加一）：`assert negB_comp == negB_check`（用取模法交叉验证）+ `assert interpret_value(negB_comp, n_data) == 40`（L219, L221），忠实覆盖减数转换考点。
  - 额外验证：`assert interpret_value(A_comp,...) == A` / `== B`（L224-225），保证补码本身正确。无 `assert True` 类废话断言。
- [维度C·充分性合围] exec 事实输出满足全部通过条件：
  - A+B：|A|+|B|=90 > 64，代码 assert `90 > 2**(n-1)` 通过，overflow_ab=True，双符号位 `10` 不一致 → 溢出被真实触发，参数未退化。
  - A−B：||A|−|B||=10 < 64，代码 assert `10 < 2**(n-1)` 通过，overflow_asub=False，双符号位 `11` 一致 → 不溢出被真实触发。
  - [-B]补 转换：交叉验证通过。三种情形（一溢一不溢一转换）全部覆盖，符合 design_card 考察意图。
- [维度D·文档忠实] solution.md 逐步数值与 gen.py 逻辑一致：
  - [A]补 = 11001110（=206=(-50)%256），[B]补 = 11011000（=216=(-40)%256）✓
  - A+B 逐位和 = 10100110，双符号位 10 → 负溢出 ✓
  - [-B]补 = 00101000（11011000 全取反 00100111 +1），对应真值 40 ✓
  - A−B 逐位和 = 11110110，双符号位 11 → 不溢出，真值 −10 ✓
  - 求解形式（绝对值取反→加一→拼符号位；减数全取反加一）与 gen.py 计算路径一致，无捏造步骤。
- [维度E·题面规范性] 题型为两子问计算题，(1)(2) 齐全无截断，条件明确无歧义。符合声明题型。

## routing
none
