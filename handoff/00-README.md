# 交接指南 — 给 VSCode Claude Code

> **本文档面向 VSCode 的 Claude Code（全新会话）。**
> 你将接管一个已经在 brainstorming + planning 阶段完成的项目，执行 12 个 TDD 任务。
> 读完本文档 + 下列文件，你就有完整上下文，无需询问历史。

---

## 你要做什么

**一句话**：执行 `docs/superpowers/plans/2026-06-22-llm-gateway-anthropic-provider.md` 里的 12 个 TDD 任务（Task 1 已完成，从 Task 2 开始）。

**项目**：llm_eduated（408 考试生成系统），Windows，Python 3.14，git 仓库（分支 `feature/hybrid-solver-annotation`）。

**目标**：为 LLM 调用层增加 anthropic 端点支持（新写 `AnthropicProvider`）、agent 维度路由（新写 `agent_router`）、指数退避重试（改 gateway），让上层 agent loop 能按 agent 名（write_gen / design_direct）自动获得匹配的 provider 和思考强度。

---

## 必读文件（按顺序）

1. **本目录的 `01-SPEC.md`** —— 设计 spec（v3，已定稿）。理解"为什么这么做"。
2. **本目录的 `02-PLAN.md`** —— 实现 plan（12 个 TDD 任务）。**这是你的工作清单**。
3. **本目录的 `03-STATUS.md`** —— 当前进度（Task 1 已完成，Task 2-12 待办）。
4. **本目录的 `04-ENVIRONMENT.md`** —— 环境信息（已装依赖、git 配置、关键路径、坑点）。

> 这 4 个文件是自包含的，你不需要读项目里的其他文件就能开始（plan 里每个 task 都给了精确的代码和文件路径）。

---

## 执行规则

### TDD 节奏（每个 task）
1. 写失败测试
2. 跑测试看它失败：`python -m pytest tests/xxx.py -v`
3. 写最小实现
4. 跑测试看它通过
5. commit（用 plan 里给的中文 commit message）

### 执行顺序（依赖关系）
```
Task 1 ✅ 已完成
Task 2 → Task 3（3 依赖 2）
Task 4（独立，可现在做）
Task 5（核心，独立，可现在做）
Task 6（依赖 Task 5 的 AnthropicProvider 类存在）
Task 7（独立，可现在做）
Task 8（依赖 Task 5 的 anthropic SDK 装好）
Task 9（独立于 5/6/7）
Task 10（依赖 Task 4 的 RemoteAPIProvider.stream() + Task 9 的 thinking_effort）
Task 11（依赖 Task 7 的 glm5.2 provider）
Task 12（端到端，依赖前面所有）
```

**建议顺序**：Task 2 → 3 → 7 → 4 → 5 → 6 → 8 → 9 → 10 → 11 → 12

### 关键约束
- **Windows cmd.exe 环境**：没有 `head`/`tail`/`sed`/`grep` 这些 Unix 命令。用 Python 或 Windows 原生命令。
- **git 不在默认 PATH**：要用完整路径 `C:\Users\11325\AppData\Roaming\MobaXterm\slash\bin\git.exe`，或先 `set PATH=C:\Users\11325\AppData\Roaming\MobaXterm\slash\bin;%PATH%`。详见 `04-ENVIRONMENT.md`。
- **e2e 测试消耗 API 额度**：Task 5 Step 6、Task 12 的 e2e 测试会真调 GLM API。用户已同意（"额度够"），但你要清楚这一点。
- **不要碰批量标注路径**：`llm_providers_new/local_batch.py` 和 `RemoteAPIProvider` 的 batch 接口（`generate_with_think_and_parse_batch`/`generate_json_batch`）是批量标注用的，本次不动。

### 完成判定
- 12 个 task 的测试全绿（unit + e2e）
- 每个 task 都有独立 commit
- 最后跑一遍全量测试：`python -m pytest tests/ -v -k "not e2e"`（e2e 单独跑：`python -m pytest tests/ -v -m e2e`）

---

## 如果遇到问题

- **测试跑不起来**：检查 `04-ENVIRONMENT.md` 的依赖清单
- **anthropic SDK 报错**：Task 5 的流式解析可能有 SDK 版本差异，看 `01-SPEC.md` 的 §3.5 和附录 A 的实测数据
- **e2e 失败**：检查 `.env` 的 `GLM_API_KEY` 和 `GLM_API_BASE`（应该是 `/api/anthropic`）
- **plan 里的代码不对**：plan 是基于 spec 写的，回查 `01-SPEC.md` 对应章节

---

## 与原会话的关系

原会话（ZCode CLI）完成了：
- brainstorming（需求澄清、端点实测）
- spec v3 定稿（已 commit: `74a523d`）
- plan 编写（已 commit: `5b75e94`）
- Task 1 执行（pyproject.toml 加 pyyaml，commit: `0d5f2cc`）

原会话**无法继续执行**的原因：ZCode 的 Agent 工具只有只读 Explore 子智能体，不能写代码。所以交接给 VSCode Claude Code（能写代码、能 commit）。

你（VSCode Claude Code）是全新会话，但通过读本目录的 4 个文件就能获得全部上下文。原会话的对话历史你不需要看——所有结论都已沉淀在 spec 和 plan 里。
