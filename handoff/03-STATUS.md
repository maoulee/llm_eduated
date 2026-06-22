# 当前进度（2026-06-22 交接时）

## 已完成

### Task 1: pyproject.toml 加 pyyaml ✅
- **Commit**: `0d5f2cc`
- **改动**: `pyproject.toml` 的 `[project] dependencies` 末尾加 `"pyyaml>=6.0"`
- **说明**: anthropic SDK (`>=0.90`) 已在 dependencies 里（原本就有），不需要动。pyyaml 是 agent_router 读 YAML 配置需要的。
- **验证**: `python -c "import anthropic, yaml; print(anthropic.__version__)"` → `0.111.0` ✅

## 待办（你接手后的工作）

### Task 2: TransportRetryPolicy 加退避字段 ⏳
- 改 `core_new/agent_roles.py` 的 `TransportRetryPolicy` dataclass
- 加两个字段：`backoff_base: float = 2.0`、`backoff_max_wait: float = 30.0`
- 新建 `tests/test_agent_roles.py`（3 个测试）
- 详见 `02-PLAN.md` Task 2

### Task 3: gateway 指数退避重试 ⏳
- 改 `core_new/llm_gateway.py` 的 `_wait_with_backoff` 方法（约 line 186-189）
- 从固定 3 秒改为 `base * 2^attempt + jitter`，cap 在 max_wait
- 新建 `tests/test_gateway_enhancements.py`（2 个测试）
- 依赖 Task 2 的 `backoff_base`/`backoff_max_wait` 字段

### Task 4: RemoteAPIProvider 加 stream() ⏳
- 改 `llm_providers_new/remote_api.py`，给 `RemoteAPIProvider` 加 `stream(params)` 方法
- 逻辑从 `llm_gateway.py:548-634` 的 `_read_chat_stream` 搬过来
- 新建 `tests/test_remote_api_stream.py`（2 个测试，mock SDK）

### Task 5: 新建 AnthropicProvider ⭐ 核心任务 ⏳
- 新建 `llm_providers_new/anthropic_provider.py`（约 180 行）
- 用 anthropic SDK 的 `AsyncAnthropic`，走 Messages API
- 实现 `stream(params)` 供 gateway 调用
- 处理 anthropic 流式事件（text/thinking/tool_use 三类块）
- 新建 `tests/test_anthropic_provider.py`（5 个 unit + 2 个 e2e）
- **e2e 测试会真调 GLM API**（用户已同意）

### Task 6: get_llm_provider 工厂分支 ⏳
- 改 `llm_providers_new/__init__.py`
- 加 `api_protocol == "anthropic_messages"` 分支，路由到 `AnthropicProvider`
- 新建 `tests/test_provider_factory.py`（2 个测试）
- 依赖 Task 5

### Task 7: config.py glm5.2 + 清 32B ⏳
- 改 `config.py`，新增 `glm5.2` provider（`api_protocol="anthropic_messages"`）
- 改 `api_vllm` 的 model_path 默认（从 `Qwen3.6-27B-AWQ-INT4` 改为空占位）
- 新建 `tests/test_config_providers.py`（3 个测试）

### Task 8: _classify_exception anthropic 分支 ⏳
- 改 `core_new/llm_gateway.py` 的 `_classify_exception` 函数
- 在最前面加 anthropic SDK 异常分类（try/except ImportError 兜底）
- 追加测试到 `tests/test_gateway_enhancements.py`（3 个测试）
- 依赖 anthropic SDK（Task 1 已装）

### Task 9: stream_chat 加 thinking_effort ⏳
- 改 `core_new/llm_gateway.py` 的 `stream_chat` 签名 + `_build_chat_params`
- 加 `thinking_effort` 参数，构造 `thinking={type:enabled} + reasoning_effort` 字段
- 追加测试到 `tests/test_gateway_enhancements.py`（2 个测试）

### Task 10: _read_chat_stream 重构 ⏳
- 改 `core_new/llm_gateway.py` 的 `_read_chat_stream` 方法
- 从直接调 `provider.client.chat.completions.create` 改为调 `provider.stream(params)`
- 这样 gateway 对协议无感（anthropic/openai 都走 provider.stream()）
- 依赖 Task 4（RemoteAPIProvider.stream）+ Task 5（AnthropicProvider.stream）+ Task 9（thinking_effort）

### Task 11: agent_router + YAML ⏳
- 新建 `core_new/agent_router.py`（约 80 行）
- 新建 `config/agents_llm.yaml`
- 新建 `tests/test_agent_router.py`（5 个测试）
- 依赖 Task 7（glm5.2 provider 存在）

### Task 12: 端到端集成测试 ⏳
- 新建 `tests/test_e2e_integration.py`（3 个 e2e 测试）
- 真调 GLM API 验证全链路：agent_router → gateway → anthropic_provider → API
- 依赖前面所有 task

---

## Git 状态（交接时）

- 分支：`feature/hybrid-solver-annotation`
- 最新 commit：`0d5f2cc`（Task 1）
- 工作区：干净（除 `handoff/` 目录，那是交接资料）
- 之前的 commits（本会话产物）：
  - `5b75e94` plan
  - `74a523d` spec v3
  - `8fd20ef` spec v2
  - `08ab2f7` spec v1

## 建议执行顺序

```
Task 2 → Task 3（3 依赖 2 的字段）
Task 7（独立）
Task 4（独立）
Task 5（核心，独立）
Task 6（依赖 5）
Task 8（依赖 anthropic SDK）
Task 9（独立）
Task 10（依赖 4 + 9）
Task 11（依赖 7）
Task 12（端到端，依赖全部）
```

每个 task 完成后 commit，commit message 用 `02-PLAN.md` 里给定的中文文案。
