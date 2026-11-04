## status
needs_fix

## stage
question

## issue_type
stem_conflict

## findings
- [通过条件自洽] 通过条件1 叶子列举不完整：原文写"至少有 4 个叶子结点（D、H、I、F、G）"，括号内列举了 5 个字母但前面说"4 个"，数量词与列举不一致。通过条件5 正确写明"5 个叶子结点（D、H、I、F、G）"，两处矛盾。
- [设计一致性] sub_question_structure 与 design_card 不一致：design_card 规定 Q1=定义二叉链表结点类型（约2分）、Q2=描述算法思想（约4分）、Q3=写出C/C++代码并注释（约10分）；但 question.md 实际结构为 Q1=算法设计思想（4分）、Q2=C/C++代码（10分）、Q3=示例树+路径输出（2分）。结点类型定义被直接放入题干而非作为独立小问，且多出一个 design_card 未规划的示例小问（Q3）。

## fix_instructions
- 修改对象：通过条件1
  - 修改位置：通过条件第1条
  - 当前问题："至少有 4 个叶子结点（D、H、I、F、G）"——数量词"4"与括号内5个列举不一致
  - 修改目标：统一为"5 个叶子结点（D、H、I、F、G）"，与通过条件5保持一致
  - 最小修改指令：将"至少有 4 个"改为"5 个"

- 修改对象：sub_question_structure（二选一）
  - 方案A（改 question.md）：将结点类型定义从题干中移出，作为独立 Q1（约2分），原 Q1/Q2 顺延为 Q2/Q3，原 Q3 示例题顺延为 Q4；总分相应调整为 18 分或压缩分值
  - 方案B（改 design_card）：将 design_card 的 sub_question_structure 更新为 question.md 实际结构（Q1=算法思想、Q2=代码、Q3=示例），删除"定义结点类型"作为独立小问的要求，因为类型定义作为题干前置信息对算法设计题更合理
  - 建议：方案B（question.md 当前结构更合理，改 design_card 对齐即可）

## keep_unchanged
- 二叉链表结点类型定义（BiTNode）内容本身
- 先序遍历序列 `A B D # # E H # # I # # C F # # G # #`
- 通过条件2-5（路径以A结尾、回溯正确、叶子判定、示例树唯一性）
- 考察知识点、考察模式、难度定位

## routing
design_direct
