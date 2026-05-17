# Tools

可用工具由 `core_new.edu408_runtime.tools.build_408_tools()` 注册。

- `compose_paper_408`: 调用现有 `PaperComposerAgent` 生成 PaperBlueprint。
- `generate_question_408`: 调用现有 `SingleChoicePipeline` 或 `HybridSubjectivePipeline` 生成单题。
- `code_exec_408`: 统一执行 Python 验算代码，支持 sandbox 和 persisted subprocess 两种模式。
- `check_question_408`: 对 PaperBlueprint 或单题执行确定性结构检查。
- `search_knowledge_408`: 搜索本地 408 经验卡、真题抽取和 k-card 文档。
- `read_workspace_file`: 读取 workspace 内 AGENTS/TOOLS/SLOT_POLICY/SKILL.md。

不要把通用 shell、web、文件任意写入工具注册到第一阶段 runtime。
