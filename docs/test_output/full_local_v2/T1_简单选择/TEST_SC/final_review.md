## status
question_error

## summary
题干结构错误：答案"135"直接嵌入题干（第17行加粗），而非以问句形式呈现。选择题应提问而非陈述答案。数值计算正确（solution=135, solve_output=135），求解过程完整。

## detailed_feedback
- 证据核对：[一致] solution=135, solve_output=135
- 答案唯一性：[通过] 树结构给定，计算路径确定
- 条件利用率：[通过] 所有条件均被使用
- 答案自洽性：[通过] 推理链完整无矛盾
- 蓝图匹配：[通过] N=8,L=4,H=3,WPL=135均在约束范围内

## issue_type
question_error

## evidence_check
- core_knowledge_intent 覆盖：[是] WPL定义、路径长度计算、仅叶子节点参与均被考查
- expected_reasoning_actions 出现：[是] 识别叶子→计算路径→加权求和→验证，四步完整
- terminology constraints 满足：[是] 使用"带权路径长度""叶子节点""路径长度"，定义清晰

## design_card_alignment
参数全部满足硬约束（N=8∈[5,10], L=4∈[3,5], H=3∈[3,4], WPL=135∈[50,500]）。求解过程完整覆盖 expected_reasoning_actions。唯一问题是题干结构——答案直接写在题干中而非以问句+选项形式呈现。

## routing_feedback
1. [question.md 第17行]: "该二叉树的带权路径长度 WPL 为 **135**" → 改为 "该二叉树的带权路径长度 WPL 为（ ）。" → 保留第19行WPL定义注释不变
2. [question.md]: 补充4个选项 A/B/C/D，其中正确选项为135，3个干扰项分别对应：①计入非叶子节点 ②路径长度从1开始计数 ③权值与路径对应错误
