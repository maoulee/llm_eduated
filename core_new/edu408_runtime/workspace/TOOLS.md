# Tools

可用工具由 `core_new.edu408_runtime.tools.build_408_tools()` 注册。

- `python_exec`: 执行 Python 验算代码（MCP 沙箱），支持 persist 落盘和 file_path 重跑。
- `check_question_408`: 对 PaperBlueprint 或单题执行确定性结构检查。
- `search_knowledge_408`: 搜索本地 408 经验卡、真题抽取和 k-card 文档。
- `read_workspace_file`: 读取 workspace 内 AGENTS/TOOLS/SLOT_POLICY/SKILL.md。

不要把通用 shell、web、文件任意写入工具注册到第一阶段 runtime。
