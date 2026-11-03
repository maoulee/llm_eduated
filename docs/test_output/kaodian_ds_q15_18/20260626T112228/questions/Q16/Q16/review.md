## status
pass

## stage
solution

## issue_type
none

## findings
- [维度A·建模忠实] solve() 建模对应题干要求：`proc_correct`（L37-41）实现"先递归后输出"→逆序，`proc_wrong_order`（L46-50）实现"先输出后递归"→正序，两者结构忠实映射题干的两语句顺序考察点。链表结点 `LNode`（L18-21）、`build_linked_list` 带头结点构建（L23-31）、调用 `proc_fn(L.next, ...)`（L58）均与题干"带头结点、头指针 L、调用 proc(L->next)"一致。变量对应正确，无错配/遗漏。无结构性错误（终止条件 `if p is None`、递归推进 `p.next`、输出 `p.data` 逻辑完整）。

- [维度B·断言合适] 5 个通过条件均有对应 assert，且无弱化/无恒真：
  - 条件1（①递归调用）：assert 在 L122-123，检查 `"proc(" in blank1 and "p->next" in blank1`。✓
  - 条件2（②输出语句）：assert 在 L128-129，检查 `"printf" in blank2 and "p->data" in blank2`。✓
  - 条件3（顺序约束）：assert 在 L139-140，用 `inspect.getsource` 取 proc_correct 源码，验证 `idx_recurse < idx_print`（递归调用行号先于输出行号），打到"先递归后输出"这一核心特征，非弱化。✓
  - 条件4（功能正确性）：assert 在 L144-145，检查 `correct_out == EXPECTED_REVERSE`（`"5 4 3 2 1 "`）。✓
  - 条件5（第2问要点覆盖）：assert 在 L162-165，机检预置解答文本含"逆序/从尾到头"且含"递归"+"返回/末尾"，非恒真。✓
  - 无 `assert True` 类恒真断言。

- [维度C·充分性+设计一致性] 充分性合围成立：exec 事实输出满足题干声明的通过条件——条件4 的 assert 通过即证明 `proc(L->next)` 对链表 1→2→3→4→5 输出恰好为 `"5 4 3 2 1 "`（逆序），参数真正触发了考点（先递归后访问→逆序）。区分点有效（L149-152 assert 确认 `wrong_out=="1 2 3 4 5 "` 且 `≠ correct_out`），顺序写反确实产生不同结果，非静默放行。与 design_card 的 core_knowledge_intent（单链表+递归，先递归后访问=逆序）完全对齐，未跑偏。

- [维度D·文档忠实] solution.md 与 gen.py exec 输出一致：
  - 填空答案：① `proc(p->next);`、② `printf("%d ", p->data);`，与 gen.py ANSWER（L109-110）一致。✓
  - 递归执行流程逐层列表（solution L49-59）与 gen.py `trace_recursive` 输出格式、数值（5→4→3→2→1）一致。✓
  - 输出结果 `5 4 3 2 1 `（solution L41）与 exec `correct_out` 一致。✓
  - 区分点描述"顺序写反→1 2 3 4 5 正序"（solution L64）与 gen.py `wrong_out` 一致。✓
  - 无幻觉步骤/数值/操作。✓

- [维度E·题面规范性] 第1问为 C 语句填空（两处空白①②），非四选一，符合填空题型；第2问为开放简答。题干完整无截断，调用方式 `proc(L->next)`、头结点、输出格式（每个整数后跟空格）均明确无歧义。✓

## routing
none
