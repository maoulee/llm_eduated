## status
pass

## stage
solution

## issue_type
none

## findings
- [维度1·建模忠实] gen.py 中 compute_next_1based 正确实现 1-based next 数组定义（next[1]=0，next[j]=最长真前后缀长度+1）；compute_nextval_1based 正确实现 nextval 递推规则（P[j]==P[next[j]] 时递归）。变量映射（pattern[jj-1]↔P[jj]）正确。
- [维度2·断言合适] gen.py 包含完整的通过条件验证（条件1-6），覆盖参数约束、值域、选项互异、next≠nextval、唯一性、干扰项对应关系。选择题专属断言（len({A,B,C,D})==4、A!=D）齐全。
- [维度C·充分性] 手动推演 gen.py 逻辑：next=[0,1,1,2,3,4,1,2]，nextval=[0,1,0,1,0,4,0,1]。选项值 A=3, B=2, C=4, D=0，四者互异；next[5]=3∈[2,4]；next[5]≠nextval[5]（3≠0）。全部通过条件满足。
- [维度C·设计一致性] exec 产出结构（next/nextval 数组、4个干扰项）与 design_card 的 core_knowledge_intent（K1/K2/K3）和 expected_form（选择题）对齐。
- [维度D·文档忠实] solution.md 求解过程与 gen.py exec 输出逐一对应：next 数组表格（[0,1,1,2,3,4,1,2]）一致；next[5] 计算步骤（"abab" 枚举 k=1/2/3）一致；干扰项 B=next[4]=2、C=4（硬编码错误路径）、D=nextval[5]=0 均与 gen.py 一致；无幻觉内容。

## routing
none
