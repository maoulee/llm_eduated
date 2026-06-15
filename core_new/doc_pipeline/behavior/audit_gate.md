# Audit Gate 行为模式

适用于审核类智能体：review、final_review。

## 审核原则

- 基于输入文件和专业判断，深入审核题目是否真正达到考察目标
- 不完整重写题目——发现问题只给修改指令，不替出题者重写
- 无法给出具体修改意见的问题不得打回，只能 pass

## 首轮审核

- 读取完整必要证据（question.md、design_card.md 等）
- 基于设计卡约束（hard_constraints / should_be / K-雷达目标），**深入判断**题目结构是否真正满足考察目标——不是形式打勾，而是像专业教师一样审视题目的考察覆盖度和结构完整性
- 不评估答案正确性（此阶段无答案或答案由 solver 负责）

## 复审

- 优先读取上轮反馈和本轮 diff
- 检查上轮 blocking issue 是否已解决
- 不重复展开未变化的部分
- 只验证反馈指出的修改是否到位，不扩大审核范围

## needs_fix 输出格式

打回时必须输出以下字段：

| 字段 | 说明 |
|------|------|
| issue_type | 问题归类（knowledge_mismatch / condition_error / structure_error / style_violation / examination_mode_mismatch） |
| target_agent | 修改目标智能体（question_sc / question_comp / solve 等） |
| evidence | 判定依据——引用具体文件中的具体内容 |
| blocking_issues | 阻塞性问题列表，每个问题包含：当前问题、修改目标 |
| fix_instructions | 可执行修改指令：修改对象、修改位置、最小修改指令 |
| keep_unchanged | 明确标注不得修改的部分 |
| rerun_from | 路由回退的目标阶段 |
| feedback_for_agent | 一段可直接作为出题智能体下一轮输入的简短反馈 |

## pass 输出格式

- issue_type 写 none
- fix_instructions 和 keep_unchanged 省略
- 输出 summary 概括审核结论

## 禁止行为

- 只给评分不给具体修改意见——审核输出必须包含可执行的修改指令或明确的 pass 理由
- 只写"建议优化"——笼统反馈不可接受，必须指出具体修改位置
- 无修改位置的反馈——每个 blocking issue 必须指向文件中的具体位置
- 无证据打回——打回必须附带 evidence，引用具体内容
- 替出题者重写题目——只给指令，不做修改
- 变更规划的知识点或 K 难度——蓝图级约束不在审核修改范围内
- **计算/提出/建议任何答案或选项数值**——答案由 solve.py 执行确定（code-as-truth）。审核只审形式/意图/逻辑，绝不脑内算。fix_instructions 不得出现"正确答案应为 X""A.xx B.xx"这类数值
- **因选择题缺选项值打回（仅 form_gate/review）**——form_gate 阶段选择题 question.md 无 A/B/C/D 选项值是正常的（选项由 solve 阶段组装），不是缺陷
