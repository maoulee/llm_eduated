## status
pass

## stage
solution

## issue_type
none

## findings
- [维度1 建模忠实] gen.py 的 compute_next / compute_nextval 逻辑与题干定义一致：next[j] 取 s[0..j-1] 的最长相等真前后缀长度（length 遍历 1..len(sub)-1），nextval 按标准优化规则计算。
- [维度2 断言合适] gen.py 断言覆盖通过条件核心：correct>=2（非平凡）、选项互异（len==4）、D 值正确（d_val==len(sub)）。B/C 的构造为确定性赋值（nextval[k] / correct-1），无需额外断言。
- [维度3 充分性] exec 输出：next=[0,0,0,1,2,3]，nextval=[0,0,0,0,0,0]，选项 {A=3, B=0, C=2, D=5} 互异且 ≥2，满足全部通过条件。
- [维度3 选择题充分性] 4 选项值 {3,0,2,5} 互异，正确值 A=3 唯一，干扰项 B=0（nextval 混淆）、C=2（算错1）、D=5（忘真前后缀）均为 KMP 常见误算产物，具有区分度。
- [维度3 设计一致性] exec 产出（next 数组、nextval 数组、4 选项）与 design_card 的 core_knowledge_intent（真前后缀理解）和 expected_form（选择题）一致。
- [维度D 文档忠实] solution.md 的 next 数组逐位计算与 gen.py exec 输出 [0,0,0,1,2,3] 一致；nextval 数组 [0,0,0,0,0,0] 一致；各选项值 A=3/B=0/C=2/D=5 一致；无幻觉内容。

## routing
none
