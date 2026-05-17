# Edu408 Agents

本 workspace 面向 408 出题系统的 agent runtime。核心原则：

- DeepTutor-style runtime 只负责工具编排、action-observation 循环和上下文组织。
- Slot、组卷、出题、验题与入库规则由现有 408 deterministic pipeline 负责。
- 不要绕过 `check_question_408` 接受题目；slot correctness 必须由确定性检查兜底。
- 不要默认使用通用 shell 或 web 工具；生产工具必须通过 408 ToolRegistry 白名单暴露。

推荐分工：

- `compose-paper-408`: 将教师需求和 slot templates 组织成 PaperBlueprint。
- `generate-question-408`: 根据 SlotBlueprint 生成单题。
- `solve-408`: 使用代码执行工具验证答案。
- `review-question-408`: 结合 slot blueprint、答案证据、结构规则审核题目。
