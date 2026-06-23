## status
pass

## stage
solution

## issue_type
none

## findings
- [维度A-建模忠实] gen.py 忠实实现题干要求：散列函数 `h = key % m`、头插法 `table[h].insert(0, key)`、ASL 成功（链中位置 1-indexed）、ASL 失败（链长 / m），规则映射正确，变量对应无误。
- [维度B-断言合适] 5 条通过条件均有对应 assert：
  - 条件1（至少2条链≥2）→ `assert chains_ge2 >= 2` ✓
  - 条件2（最长链∈[2,4]）→ `assert 2 <= max_chain <= 4` ✓
  - 条件3（ASL成功分母为n）→ `assert asl_success == asl_success_num / n` ✓
  - 条件4（ASL失败分母为m）→ `assert asl_failure == asl_failure_num / m` ✓
  - 条件5（非空链表∈[2,4]）→ `assert 2 <= non_empty <= 4` ✓
  无弱化、无恒真凑数（条件3/4的断言虽为变量自洽验证，但对应通过条件的公式声明性质，非废话凑数）。
- [维度C-充分性] 对照 solution.md（即 gen.py exec 输出）：
  - 链长度≥2 的有 2 条（桶2长度4、桶5长度4）→ 满足条件1 ✓
  - 最长链长度 4 ∈ [2,4] → 满足条件2 ✓
  - 非空链表 4 条（桶2/4/5/7）∈ [2,4] → 满足条件5 ✓
  - ASL_success = 22/10 = 2.2，分母为 n=10 ✓
  - ASL_failure = 10/13，分母为 m=13 ✓
  参数成功触发考点（冲突确实发生，分布合理），充分性通过。
- [维度C-设计一致性] exec 产出对齐 design_card：散列函数应用 ✓、拉链法头插冲突处理 ✓、ASL 成功/失败计算及分母区别 ✓。
- [维度D-文档忠实] solution.md 与 gen.py exec 输出逐一对应：
  - 插入过程表格：10 个关键字的 H(key)、桶号、插入后链表均一致 ✓
  - 散列表结构：桶2(67→54→41→28)、桶4(17)、桶5(44→31→18→5)、桶7(33)，其余为空 ✓
  - ASL 成功：各关键字链中位置与比较次数一致，总和 22/10 = 2.2 ✓
  - ASL 失败：各桶链长与失败比较次数一致，总和 10/13 ✓
  无幻觉、无抄写错误。

## routing
none
