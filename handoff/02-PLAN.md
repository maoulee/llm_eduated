# LLM Gateway 增强 + Anthropic Provider 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 llm_eduated 项目的 LLM 调用层增加 anthropic 端点支持、agent 维度路由、指数退避重试，让上层 agent loop 能按 agent 名（如 write_gen / design_direct）自动获得匹配的 provider 和思考强度配置。

**Architecture:** 就地增强 `core_new/llm_gateway.py`（gateway 层不再直接碰 SDK，改调 `provider.stream(params)`）+ 新写 `llm_providers_new/anthropic_provider.py`（封装 GLM `/api/anthropic` 端点的 Messages 协议）+ 新增 `core_new/agent_router.py`（配置驱动的 agent→provider 路由薄层）。gateway 对协议无感，provider 各自封装 SDK。

**Tech Stack:** Python 3.12+，anthropic SDK（`AsyncAnthropic`），httpx（连接池/重试），PyYAML（配置），pytest（测试）。

**Spec:** `docs/superpowers/specs/2026-06-22-llm-gateway-enhancement-design.md`（v3）

---

## 文件结构（改动地图）

### 新建文件
| 文件 | 职责 |
|------|------|
| `llm_providers_new/anthropic_provider.py` | GLM anthropic 端点 provider（anthropic SDK，Messages 协议，thinking.type + reasoning_effort） |
| `core_new/agent_router.py` | agent 名 → gateway 路由薄层（读 YAML，lru_cache 复用） |
| `config/agents_llm.yaml` | agent → provider + thinking 配置映射 |
| `tests/test_anthropic_provider.py` | anthropic provider 端到端测试 |
| `tests/test_agent_router.py` | agent_router 路由 + 缓存测试 |
| `tests/test_gateway_enhancements.py` | 指数退避 + thinking_effort 测试 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `core_new/agent_roles.py` | `TransportRetryPolicy` 加 `backoff_base` / `backoff_max_wait` 数值字段 |
| `core_new/llm_gateway.py` | `_wait_with_backoff` 指数退避；`stream_chat`/`_build_chat_params` 加 `thinking_effort`；`_read_chat_stream` 重构为调 `provider.stream()`；`_classify_exception` 加 anthropic 分支 |
| `llm_providers_new/remote_api.py` | 加 `stream(params)` 方法（从 gateway 搬现有 OpenAI 流式逻辑） |
| `llm_providers_new/__init__.py` | `get_llm_provider` 工厂加 `anthropic_messages` 协议分支 |
| `config.py` | 新增 `glm5.2` provider；清除 `api_vllm` 的 32B 默认 |
| `pyproject.toml` | `anthropic` 从 optional 移到 core dependencies |

### 不改文件
- `.env`（GLM_API_BASE 已正确指向 /api/anthropic）
- `llm_providers_new/local_batch.py`（批量标注独立，不并入）

---

## Task 1: 环境准备 — anthropic SDK 装入核心依赖

**Files:**
- Modify: `pyproject.toml`
- Test: 无（环境配置）

- [ ] **Step 1: 确认 anthropic 当前依赖位置**

Read `pyproject.toml`，确认 `anthropic>=0.90` 当前在 `[project] dependencies`（core）还是某个 optional group。

- [ ] **Step 2: 把 anthropic 移到/保持在 core dependencies**

确保 `pyproject.toml` 的 `[project] dependencies` 列表含 `"anthropic>=0.40"`（降低版本下限到 0.40，因为 thinking + streaming API 在 0.40+ 已稳定；不要用 0.90 以免过度收紧）：

```toml
[project]
dependencies = [
    "openai>=2.0",
    "anthropic>=0.40",
    "httpx[socks]>=0.27",
    # ... 其余保持不变
]
```

- [ ] **Step 3: 安装依赖**

Run: `pip install -e .`
Expected: anthropic 装上，无错误。

- [ ] **Step 4: 验证 anthropic 可导入**

Run: `python -c "import anthropic; print(anthropic.__version__)"`
Expected: 打印版本号（如 `0.40.0` 或更高），无 ImportError。

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: anthropic SDK 移入核心依赖（供 anthropic provider 使用）"
```

---

## Task 2: TransportRetryPolicy 加退避参数

**Files:**
- Modify: `core_new/agent_roles.py:43-59`（`TransportRetryPolicy` dataclass）
- Test: `tests/test_agent_roles.py`（新建）

- [ ] **Step 1: 写失败测试**

Create `tests/test_agent_roles.py`:

```python
"""TransportRetryPolicy 退避参数测试。"""
from core_new.agent_roles import TransportRetryPolicy


def test_default_backoff_params():
    """默认值：base=2.0, max_wait=30.0。"""
    p = TransportRetryPolicy()
    assert p.backoff_base == 2.0
    assert p.backoff_max_wait == 30.0


def test_custom_backoff_params():
    """可自定义。"""
    p = TransportRetryPolicy(backoff_base=1.5, backoff_max_wait=60.0)
    assert p.backoff_base == 1.5
    assert p.backoff_max_wait == 60.0


def test_frozen_dataclass_still_works():
    """frozen dataclass 加字段后仍可实例化。"""
    p = TransportRetryPolicy(max_attempts=5, backoff_base=2.0, backoff_max_wait=30.0)
    assert p.max_attempts == 5
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_roles.py -v`
Expected: FAIL（`TransportRetryPolicy` 没有 `backoff_base` 属性，AttributeError / TypeError）。

- [ ] **Step 3: 加字段到 TransportRetryPolicy**

Modify `core_new/agent_roles.py`，在 `TransportRetryPolicy` 里加两个数值字段（保持 `backoff: str` 字段不变，向后兼容）：

```python
@dataclass(frozen=True)
class TransportRetryPolicy:
    max_attempts: int = 10
    backoff: str = "exponential_jitter"
    backoff_base: float = 2.0           # 指数退避基数（秒）：base * 2^attempt
    backoff_max_wait: float = 30.0      # 单次退避上限（秒）
    retry_on: tuple[str, ...] = (
        "connection_error",
        "timeout",
        "rate_limit",
        "server_error",
        "empty_content",
        "malformed_envelope",
    )
    not_retry_on: tuple[str, ...] = (
        "validation_error",
        "format_error",
        "domain_error",
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_roles.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add core_new/agent_roles.py tests/test_agent_roles.py
git commit -m "feat: TransportRetryPolicy 加 backoff_base/backoff_max_wait 数值字段"
```

---

## Task 3: gateway 指数退避重试

**Files:**
- Modify: `core_new/llm_gateway.py:186-189`（`_wait_with_backoff` 方法）
- Test: `tests/test_gateway_enhancements.py`（新建）

- [ ] **Step 1: 写失败测试**

Create `tests/test_gateway_enhancements.py`:

```python
"""gateway 增强测试：指数退避、thinking_effort。"""
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from core_new.llm_gateway import LLMGateway
from core_new.agent_roles import TransportRetryPolicy


@pytest.mark.asyncio
async def test_backoff_is_exponential():
    """指数退避：attempt=0 → ~2s, attempt=1 → ~4s, attempt=2 → ~8s（不含 jitter 时）。"""
    # 用极小的 base 让测试快跑
    policy = TransportRetryPolicy(max_attempts=3, backoff_base=0.01, backoff_max_wait=0.1)
    gw = LLMGateway.__new__(LLMGateway)
    gw._transport_retry = policy

    # patch random.uniform 返回 0，去掉 jitter 便于断言
    with patch("core_new.llm_gateway.random.uniform", return_value=0.0):
        t0 = time.monotonic()
        await gw._wait_with_backoff(0)  # 0.01 * 2^0 = 0.01s
        t1 = time.monotonic()
        await gw._wait_with_backoff(1)  # 0.01 * 2^1 = 0.02s
        t2 = time.monotonic()
        await gw._wait_with_backoff(2)  # 0.01 * 2^2 = 0.04s
        t3 = time.monotonic()

    # 第一次间隔 ~0.01s，第二次 ~0.02s（指数增长）
    gap1 = t1 - t0
    gap2 = t2 - t1
    gap3 = t3 - t2
    assert gap1 < gap2 < gap3, f"非单调递增: {gap1}, {gap2}, {gap3}"


@pytest.mark.asyncio
async def test_backoff_capped_at_max_wait():
    """退避不超过 max_wait。"""
    policy = TransportRetryPolicy(max_attempts=10, backoff_base=2.0, backoff_max_wait=0.05)
    gw = LLMGateway.__new__(LLMGateway)
    gw._transport_retry = policy

    with patch("core_new.llm_gateway.random.uniform", return_value=0.0):
        t0 = time.monotonic()
        await gw._wait_with_backoff(20)  # 2 * 2^20 巨大，应被 cap 到 0.05s
        elapsed = time.monotonic() - t0

    assert elapsed < 0.15, f"超过 cap: {elapsed}s（应 ≤0.05s + 误差）"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gateway_enhancements.py::test_backoff_is_exponential tests/test_gateway_enhancements.py::test_backoff_capped_at_max_wait -v`
Expected: FAIL（当前 `_wait_with_backoff` 固定 sleep 3s，第一个测试会超时/不符合指数）。

- [ ] **Step 3: 重写 _wait_with_backoff**

Modify `core_new/llm_gateway.py` 的 `_wait_with_backoff` 方法（约 line 186-189）：

```python
    async def _wait_with_backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter.
        delay = min(backoff_base * 2^attempt + uniform(0,1), backoff_max_wait)
        attempt 从 0 开始：base=2 → ~2s, ~4s, ~8s... capped at max_wait.
        """
        base = self._transport_retry.backoff_base
        max_wait = self._transport_retry.backoff_max_wait
        delay = min(base * (2 ** attempt) + random.uniform(0, 1), max_wait)
        logger.info("Transport retry attempt %d, waiting %.1fs", attempt + 1, delay)
        await asyncio.sleep(delay)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_gateway_enhancements.py::test_backoff_is_exponential tests/test_gateway_enhancements.py::test_backoff_capped_at_max_wait -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add core_new/llm_gateway.py tests/test_gateway_enhancements.py
git commit -m "feat: gateway 重试改为指数退避 + jitter（base=2s, cap=30s）"
```

---

## Task 4: RemoteAPIProvider 加 stream() 统一接口

**Files:**
- Modify: `llm_providers_new/remote_api.py`（加 `stream()` 方法）
- Test: `tests/test_remote_api_stream.py`（新建，单元测试用 mock）

> **背景：** gateway 即将（Task 6）重构为调 `provider.stream(params)`，不再直接碰 OpenAI SDK。`RemoteAPIProvider` 要提供这个方法，把现有 gateway `_read_chat_stream` 里的 OpenAI 流式解析逻辑搬过来。

- [ ] **Step 1: 写失败测试**

Create `tests/test_remote_api_stream.py`:

```python
"""RemoteAPIProvider.stream() 接口测试（mock SDK，不真调 API）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_providers_new.remote_api import RemoteAPIProvider


def _make_provider():
    """构造一个不真连 API 的 provider（mock client）。"""
    p = RemoteAPIProvider(
        model_name="test-model",
        api_base_url="http://localhost:11111/v1",
        api_key="test-key",
        thinking_control_method="none",
    )
    return p


@pytest.mark.asyncio
async def test_stream_method_exists():
    """stream() 方法存在且是 coroutine。"""
    p = _make_provider()
    assert hasattr(p, "stream")
    assert callable(p.stream)


@pytest.mark.asyncio
async def test_stream_returns_unified_dict():
    """stream() 返回 {content, reasoning_content, tool_calls, finish_reason}。"""
    p = _make_provider()
    # mock 一个假的 OpenAI stream 响应
    fake_chunk = MagicMock()
    fake_chunk.choices = [MagicMock()]
    fake_chunk.choices[0].delta.content = "hello"
    fake_chunk.choices[0].delta.tool_calls = None
    fake_chunk.choices[0].delta.reasoning_content = None
    fake_chunk.choices[0].finish_reason = "stop"

    fake_stream = AsyncMock()
    fake_stream.__aiter__ = MagicMock(return_value=iter([fake_chunk]))

    with patch.object(p.client.chat.completions, "create", new_callable=AsyncMock, return_value=fake_stream):
        result = await p.stream({
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        })

    assert set(result.keys()) >= {"content", "reasoning_content", "tool_calls", "finish_reason"}
    assert result["content"] == "hello"
    assert result["finish_reason"] == "stop"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_remote_api_stream.py -v`
Expected: FAIL（`RemoteAPIProvider` 没有 `stream` 方法，AttributeError）。

- [ ] **Step 3: 加 stream() 方法到 RemoteAPIProvider**

Modify `llm_providers_new/remote_api.py`，在 `RemoteAPIProvider` 类里加 `stream()` 方法（放在 `_chat_call` 附近）。逻辑从 `llm_gateway.py:548-634` 的 `_read_chat_stream` 搬过来，参数从 gateway 的 `params` dict 取：

```python
    async def stream(self, params):
        """统一流式接口——供 gateway 调用。
        params 由 gateway._build_chat_params 构造，含 messages/model/thinking/tools 等。
        返回 {content, reasoning_content, tool_calls, finish_reason}。
        """
        content_parts = []
        reasoning_parts = []
        tool_calls_accum = {}
        finish_reason = None

        # params 已由 gateway 构造好，直接透传给 OpenAI SDK
        # 确保 stream=True（默认）
        call_params = dict(params)
        call_params.setdefault("stream", True)

        response = await self.client.chat.completions.create(**call_params)
        async for chunk in response:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            if delta.content:
                content_parts.append(delta.content)
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if reasoning:
                reasoning_parts.append(reasoning)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_accum[idx]["arguments"] += tc_delta.function.arguments

        tool_calls = None
        if tool_calls_accum:
            tool_calls = [
                {
                    "id": tool_calls_accum[idx]["id"],
                    "type": "function",
                    "function": {
                        "name": tool_calls_accum[idx]["name"],
                        "arguments": tool_calls_accum[idx]["arguments"],
                    },
                }
                for idx in sorted(tool_calls_accum)
            ]

        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_remote_api_stream.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add llm_providers_new/remote_api.py tests/test_remote_api_stream.py
git commit -m "feat: RemoteAPIProvider 加 stream() 统一流式接口"
```

---

## Task 5: 新建 AnthropicProvider

**Files:**
- Create: `llm_providers_new/anthropic_provider.py`
- Test: `tests/test_anthropic_provider.py`

> **这是本计划的核心新代码。** 实现 GLM `/api/anthropic` 端点的 Messages 协议适配，用 anthropic SDK。

- [ ] **Step 1: 写失败测试（基础结构）**

Create `tests/test_anthropic_provider.py`:

```python
"""AnthropicProvider 测试。
unit 测试用 mock（不真调 API）；e2e 测试需真 GLM_API_KEY（标 @pytest.mark.e2e）。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm_providers_new.anthropic_provider import AnthropicProvider


def _make_provider():
    """构造测试用 provider（不真连）。"""
    return AnthropicProvider(
        model_name="glm-5.2",
        api_base_url="https://open.bigmodel.cn/api/anthropic",
        api_key="test-key",
        thinking_control_method="none",
        default_max_tokens=1000,
    )


def test_provider_init():
    """初始化：属性正确。"""
    p = _make_provider()
    assert p.model_name == "glm-5.2"
    assert p.provider_type == "api"
    assert p.supports_response_format is False
    assert hasattr(p, "client")  # anthropic AsyncAnthropic 实例


def test_prepare_messages_separates_system():
    """anthropic 要求 system 单独传，messages 只有 user/assistant。"""
    p = _make_provider()
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
    ]
    converted, system = p._prepare_messages(messages)
    assert system == "你是助手"
    assert len(converted) == 1
    assert converted[0] == {"role": "user", "content": "你好"}


def test_prepare_messages_no_system():
    """没有 system 时返回 None。"""
    p = _make_provider()
    messages = [{"role": "user", "content": "hi"}]
    converted, system = p._prepare_messages(messages)
    assert system is None
    assert converted == messages


def test_convert_tools_openai_to_anthropic():
    """OpenAI tools 格式转 anthropic（input_schema vs parameters）。"""
    p = _make_provider()
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读文件",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
    ]
    converted = p._convert_tools(openai_tools)
    assert len(converted) == 1
    assert converted[0]["name"] == "read_file"
    assert converted[0]["description"] == "读文件"
    assert "input_schema" in converted[0]
    assert converted[0]["input_schema"]["properties"]["path"]["type"] == "string"


def test_batch_methods_raise_not_implemented():
    """批量接口不支持（走 remote_api）。"""
    p = _make_provider()
    with pytest.raises(NotImplementedError):
        asyncio_run(p.generate_with_think_and_parse_batch([]))
    with pytest.raises(NotImplementedError):
        asyncio_run(p.generate_json_batch([]))


def asyncio_run(coro):
    """helper：同步跑协程。"""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_anthropic_provider.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'llm_providers_new.anthropic_provider'`）。

- [ ] **Step 3: 创建 anthropic_provider.py**

Create `llm_providers_new/anthropic_provider.py`:

```python
# llm_providers_new/anthropic_provider.py

"""
GLM anthropic 端点 Provider。

用 anthropic SDK 的 AsyncAnthropic 走 Messages API（/api/anthropic）。
思考控制：thinking.type（开关）+ reasoning_effort（档位，GLM 扩展字段，经 extra_body 传）。

实测（2026-06-22）：
- thinking.type=enabled + reasoning_effort=high → 173 tokens 思考 ✅
- thinking.type=disabled → 0 思考 ✅
- 仅 reasoning_effort（无 thinking.type）→ 被静默忽略 ❌
"""

import logging
from typing import Any, Dict, List, Optional

import anthropic
import httpx

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """GLM anthropic 端点 provider。"""

    def __init__(self, model_name: str, api_base_url: str, api_key: str, **kwargs):
        self.model_name = model_name
        self.provider_type = "api"
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.request_timeout = float(kwargs.get("request_timeout", 300.0))

        self.thinking_control_method = kwargs.get("thinking_control_method", "none")
        self.supports_response_format = False  # anthropic 协议不用 OpenAI response_format
        self.batch_size = max(1, int(kwargs.get("batch_size", 4)))

        self.sampling_params = {
            "temperature": float(kwargs.get("temperature", 1.0)),
            "top_p": float(kwargs.get("top_p", 0.95)),
            "max_tokens": int(kwargs.get("default_max_tokens", 30000)),
        }

        timeout = httpx.Timeout(self.request_timeout, connect=30.0)
        limits = httpx.Limits(
            max_connections=int(kwargs.get("max_connections", 20)),
            max_keepalive_connections=int(kwargs.get("max_keepalive_connections", 10)),
            keepalive_expiry=float(kwargs.get("keepalive_expiry", 120)),
        )
        self.http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.request_timeout,
            http_client=self.http_client,
        )
        logger.info(
            "AnthropicProvider initialized: model=%s base_url=%s",
            model_name, self.api_base_url,
        )

    def _prepare_messages(
        self,
        messages: List[Dict[str, Any]],
        enable_thinking: Optional[bool] = None,
        json_mode: bool = False,
    ):
        """OpenAI 风格 messages → anthropic 风格。
        anthropic 要求：system 单独传，messages 只能有 user/assistant。
        返回 (converted_messages, system_str_or_None)。
        """
        system_parts = []
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                converted.append({"role": role, "content": content})
        return converted, ("\n\n".join(system_parts) if system_parts else None)

    def _convert_tools(self, openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """OpenAI tools 格式 → anthropic tools 格式。"""
        converted = []
        for tool in openai_tools:
            fn = tool.get("function", tool)
            converted.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return converted

    async def stream(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """统一流式接口——供 gateway._read_chat_stream 调用。
        params 由 gateway._build_chat_params 构造，含 thinking/effort/tools 等。
        返回 {content, reasoning_content, tool_calls, finish_reason}。
        """
        messages, system = self._prepare_messages(params["messages"])
        kwargs: Dict[str, Any] = {
            "model": params["model"],
            "messages": messages,
            "max_tokens": params.get("max_tokens", self.sampling_params["max_tokens"]),
            "temperature": params.get("temperature", self.sampling_params["temperature"]),
        }
        if system:
            kwargs["system"] = system
        if "thinking" in params:
            kwargs["thinking"] = params["thinking"]
        if "reasoning_effort" in params:
            kwargs["extra_body"] = {"reasoning_effort": params["reasoning_effort"]}
        if params.get("tools"):
            kwargs["tools"] = self._convert_tools(params["tools"])

        return await self._read_stream(kwargs)

    async def _read_stream(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """解析 anthropic 流式响应。
        anthropic SDK 的 messages.stream() 用 async context manager + event 迭代。
        累积 content_blocks 里的 text/thinking/tool_use 三类块。
        """
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: Optional[List[Dict[str, Any]]] = None
        finish_reason: Optional[str] = None

        # anthropic SDK: async with client.messages.stream(**kwargs) as stream
        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                # anthropic 流式事件类型：
                # - message_start: 消息开始
                # - content_block_start: 一个内容块开始（text/thinking/tool_use）
                # - content_block_delta: 内容块增量
                # - content_block_stop: 内容块结束
                # - message_delta: 消息级增量（含 stop_reason）
                # - message_stop: 消息结束
                event_type = getattr(event, "type", "")

                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", None) == "tool_use":
                        # tool_use 块开始：初始化累积
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append({
                            "id": getattr(block, "id", ""),
                            "type": "function",
                            "function": {
                                "name": getattr(block, "name", ""),
                                "arguments": "",
                            },
                        })

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta":
                        content_parts.append(getattr(delta, "text", ""))
                    elif delta_type == "thinking_delta":
                        reasoning_parts.append(getattr(delta, "thinking", ""))
                    elif delta_type == "input_json_delta":
                        # tool_use 的 arguments 增量
                        if tool_calls:
                            tool_calls[-1]["function"]["arguments"] += getattr(delta, "partial_json", "")

                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "stop_reason", None):
                        finish_reason = delta.stop_reason

        # anthropic 的 stop_reason 映射到 OpenAI 风格（供 gateway 上层用）
        if finish_reason == "end_turn":
            finish_reason = "stop"
        elif finish_reason == "max_tokens":
            finish_reason = "length"
        elif finish_reason == "tool_use":
            finish_reason = "tool_calls"

        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }

    # BaseLLMProvider 的 batch 接口——不支持（批量标注走 remote_api）
    async def generate_with_think_and_parse_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider 不支持批量，批量标注请走 RemoteAPIProvider")

    async def generate_json_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider 不支持批量，批量标注请走 RemoteAPIProvider")
```

- [ ] **Step 4: 运行单元测试确认通过**

Run: `python -m pytest tests/test_anthropic_provider.py -v -k "not e2e"`
Expected: 5 passed（init / prepare_messages × 2 / convert_tools / batch_not_implemented）。

- [ ] **Step 5: 写 e2e 测试（真调 API）**

在 `tests/test_anthropic_provider.py` 末尾追加 e2e 测试（需真 key）：

```python
import os
import asyncio

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_thinking_enabled_with_effort():
    """e2e：thinking.type=enabled + reasoning_effort=high 应有思考块。
    需 GLM_API_KEY 环境变量。run: pytest -m e2e
    """
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        pytest.skip("GLM_API_KEY 未设置")

    p = AnthropicProvider(
        model_name="glm-5.2",
        api_base_url="https://open.bigmodel.cn/api/anthropic",
        api_key=api_key,
        default_max_tokens=1000,
    )
    result = await p.stream({
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "1+1="}],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "stream": True,
        "max_tokens": 1000,
    })
    assert result["content"], f"无 content: {result}"
    assert result["reasoning_content"], f"无思考（应有）: {result}"
    assert len(result["reasoning_content"]) > 50, f"思考过短: {result['reasoning_content']}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_thinking_disabled():
    """e2e：thinking.type=disabled 应无思考块。"""
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        pytest.skip("GLM_API_KEY 未设置")

    p = AnthropicProvider(
        model_name="glm-5.2",
        api_base_url="https://open.bigmodel.cn/api/anthropic",
        api_key=api_key,
        default_max_tokens=1000,
    )
    result = await p.stream({
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "1+1="}],
        "thinking": {"type": "disabled"},
        "stream": True,
        "max_tokens": 1000,
    })
    assert result["content"], f"无 content: {result}"
    assert not result["reasoning_content"], f"应无思考但出现: {result['reasoning_content']}"
```

- [ ] **Step 6: 运行 e2e 测试（手动，需 GLM_API_KEY）**

Run: `python -m pytest tests/test_anthropic_provider.py -v -m e2e`
Expected: 2 passed（如果 GLM_API_KEY 已在 .env 加载）。

> 如果 e2e 跑不了（环境没 key），跳过此步，unit 测试已足够保证结构正确。e2e 在集成时验证。

- [ ] **Step 7: Commit**

```bash
git add llm_providers_new/anthropic_provider.py tests/test_anthropic_provider.py
git commit -m "feat: 新建 AnthropicProvider（GLM /api/anthropic 端点，thinking+effort）"
```

---

## Task 6: get_llm_provider 工厂加 anthropic 分支

**Files:**
- Modify: `llm_providers_new/__init__.py`
- Test: `tests/test_provider_factory.py`（新建）

- [ ] **Step 1: 写失败测试**

Create `tests/test_provider_factory.py`:

```python
"""get_llm_provider 工厂测试。"""
import pytest
from llm_providers_new import get_llm_provider
from llm_providers_new.anthropic_provider import AnthropicProvider
from llm_providers_new.remote_api import RemoteAPIProvider


def test_anthropic_messages_protocol_routes_to_anthropic_provider():
    """api_protocol=anthropic_messages → AnthropicProvider。"""
    config = {
        "provider_type": "api",
        "model_path": "glm-5.2",
        "api_url": "https://open.bigmodel.cn/api/anthropic",
        "api_key": "test-key",
        "api_protocol": "anthropic_messages",
    }
    p = get_llm_provider(config)
    assert isinstance(p, AnthropicProvider)


def test_openai_chat_protocol_still_routes_to_remote_api():
    """api_protocol=openai_chat → RemoteAPIProvider（向后兼容）。"""
    config = {
        "provider_type": "api",
        "model_path": "test-model",
        "api_url": "http://localhost:11111/v1",
        "api_key": "test-key",
        "api_protocol": "openai_chat",
    }
    p = get_llm_provider(config)
    assert isinstance(p, RemoteAPIProvider)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: FAIL（`anthropic_messages` 协议不被识别，可能落到 default RemoteAPIProvider 或报错）。

- [ ] **Step 3: 改 get_llm_provider**

Modify `llm_providers_new/__init__.py`，在 `provider_type == "api"` 分支里加 `api_protocol` 判断：

```python
    if provider_type == "api":
        model_name = config.get("model_path")
        api_url = config.get("api_url")
        api_key = config.get("api_key", "EMPTY")
        api_protocol = config.get("api_protocol", "openai_chat")

        if not model_name or not api_url:
            raise ValueError("API provider config must include 'model_path' and 'api_url'.")

        provider_kwargs = {
            k: v for k, v in config.items()
            if k not in {"provider_type", "model_path", "api_url", "api_key"}
        }

        # anthropic Messages 协议 → AnthropicProvider
        if api_protocol == "anthropic_messages":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                model_name=model_name,
                api_base_url=api_url,
                api_key=api_key,
                **provider_kwargs,
            )

        # 默认 OpenAI 兼容协议 → RemoteAPIProvider
        return RemoteAPIProvider(
            model_name=model_name,
            api_base_url=api_url,
            api_key=api_key,
            **provider_kwargs,
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add llm_providers_new/__init__.py tests/test_provider_factory.py
git commit -m "feat: get_llm_provider 工厂支持 anthropic_messages 协议路由"
```

---

## Task 7: config.py 新增 glm5.2 provider + 清除 32B 默认

**Files:**
- Modify: `config.py`（`providers` dict）
- Test: `tests/test_config_providers.py`（新建）

- [ ] **Step 1: 写失败测试**

Create `tests/test_config_providers.py`:

```python
"""config.py provider 配置测试。"""
import pytest
from config import get_provider_config


def test_glm52_provider_exists():
    """glm5.2 provider 存在，model 是 glm-5.2，protocol 是 anthropic_messages。"""
    cfg = get_provider_config("glm5.2")
    assert cfg["model_path"] == "glm-5.2"
    assert cfg["api_protocol"] == "anthropic_messages"
    assert "anthropic" in cfg["api_url"]


def test_glm51_provider_still_exists():
    """glm5.1 保留（向后兼容）。"""
    cfg = get_provider_config("glm5.1")
    assert "glm" in cfg["model_path"]


def test_api_vllm_default_model_path_empty():
    """api_vllm 的 32B 默认已清除（空占位，由 .env 注入）。"""
    import os
    # 临时清掉 VLLM_MODEL 环境变量，验证默认是空
    saved = os.environ.pop("VLLM_MODEL", None)
    try:
        cfg = get_provider_config("api_vllm")
        assert cfg["model_path"] == "", f"应为空占位，实际: {cfg['model_path']}"
    finally:
        if saved is not None:
            os.environ["VLLM_MODEL"] = saved
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config_providers.py -v`
Expected: FAIL（`glm5.2` provider 不存在 → ValueError；api_vllm 默认还是 Qwen3.6-27B）。

- [ ] **Step 3: 改 config.py**

Modify `config.py`：

(a) 在 `providers` dict 里 `glm5.1` 之后加 `glm5.2`：

```python
        "glm5.2": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("GLM_MODEL", "glm-5.2"),
            api_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/anthropic"),
            api_key=os.getenv("GLM_API_KEY"),
            api_protocol="anthropic_messages",
            batch_size=int(os.getenv("GLM_BATCH_SIZE", "4")),
            request_timeout=float(os.getenv("GLM_REQUEST_TIMEOUT", "600")),
            max_retries=int(os.getenv("GLM_MAX_RETRIES", "0")),
            thinking_control_method=os.getenv("GLM_THINKING_CONTROL_METHOD", "none"),
            supports_response_format=False,
            default_max_tokens=int(os.getenv("GLM_DEFAULT_MAX_TOKENS", "30000")),
            temperature=float(os.getenv("GLM_TEMPERATURE", "1.0")),
            top_p=float(os.getenv("GLM_TOP_P", "0.95")),
        ),
```

(b) 修改 `api_vllm` 的 model_path 默认（从 `Qwen3.6-27B-AWQ-INT4` 改为空占位）：

```python
        "api_vllm": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("VLLM_MODEL", ""),  # 32B 默认已清除，由 .env 注入
            api_url=os.getenv("VLLM_API_BASE", f"http://127.0.0.1:{ServerSettings().vllm_api_port}/v1"),
            # ... 其余不变
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config_providers.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config_providers.py
git commit -m "feat: config.py 新增 glm5.2 provider + 清除 api_vllm 32B 默认"
```

---

## Task 8: gateway _classify_exception 加 anthropic 分支

**Files:**
- Modify: `core_new/llm_gateway.py`（`_classify_exception` 函数，约 line 994-1038）
- Test: `tests/test_gateway_enhancements.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `tests/test_gateway_enhancements.py` 追加：

```python
def test_classify_anthropic_timeout():
    """anthropic.APITimeoutError → 'timeout'。"""
    import anthropic
    from core_new.llm_gateway import _classify_exception
    err = anthropic.APITimeoutError(request=MagicMock())
    assert _classify_exception(err) == "timeout"


def test_classify_anthropic_rate_limit():
    """anthropic.RateLimitError → 'rate_limit'。"""
    import anthropic
    from core_new.llm_gateway import _classify_exception
    # anthropic RateLimitError 构造较复杂，用 mock
    err = MagicMock(spec=anthropic.RateLimitError)
    assert _classify_exception(err) == "rate_limit"


def test_classify_anthropic_not_installed_falls_back():
    """anthropic 未装时，现有 openai/httpx 分支仍工作（不崩）。"""
    # 这个测试主要是确认 import 失败被 try/except 兜住
    from core_new.llm_gateway import _classify_exception
    import openai
    err = openai.APITimeoutError(request=MagicMock())
    assert _classify_exception(err) == "timeout"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gateway_enhancements.py -k classify -v`
Expected: FAIL（`_classify_exception` 不认识 anthropic 异常，返回默认 `api_error`）。

- [ ] **Step 3: 加 anthropic 分支到 _classify_exception**

Modify `core_new/llm_gateway.py` 的 `_classify_exception` 函数，**在最前面**（openai 分支之前）加 anthropic 分支：

```python
def _classify_exception(error: Exception) -> str:
    # anthropic SDK（新增，放最前——import 失败时跳过）
    try:
        import anthropic
        if isinstance(error, anthropic.APITimeoutError):
            return "timeout"
        if isinstance(error, anthropic.APIConnectionError):
            return "connection_error"
        if isinstance(error, anthropic.RateLimitError):
            return "rate_limit"
        if isinstance(error, anthropic.InternalServerError):
            return "server_error"
        if isinstance(error, anthropic.APIStatusError):
            status = error.status_code
            if status == 429:
                return "rate_limit"
            if status in {408, 425}:
                return "timeout"
            if status >= 500:
                return "server_error"
            return "api_error"
    except ImportError:
        pass  # anthropic 未装时跳过，走下面 openai/httpx 分支

    # 现有 openai SDK 分支（保持不变）
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    # ... 其余不变
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_gateway_enhancements.py -k classify -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add core_new/llm_gateway.py tests/test_gateway_enhancements.py
git commit -m "feat: _classify_exception 支持 anthropic SDK 异常分类"
```

---

## Task 9: gateway stream_chat 加 thinking_effort + _build_chat_params 重构

**Files:**
- Modify: `core_new/llm_gateway.py`（`stream_chat` 签名 + `_build_chat_params`）
- Test: `tests/test_gateway_enhancements.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `tests/test_gateway_enhancements.py` 追加：

```python
@pytest.mark.asyncio
async def test_build_chat_params_with_thinking_effort():
    """_build_chat_params：enabled+effort → thinking + reasoning_effort。"""
    from unittest.mock import MagicMock
    from core_new.llm_gateway import LLMGateway

    provider = MagicMock()
    provider.model_name = "glm-5.2"
    provider.thinking_control_method = "none"
    provider.sampling_params = {"temperature": 1.0, "top_p": 0.95, "max_tokens": 1000}
    provider.supports_response_format = False
    provider._prepare_messages = MagicMock(side_effect=lambda m, **kw: list(m))

    gw = LLMGateway.__new__(LLMGateway)
    gw._provider_name = "glm5.2"
    gw._model_name = "glm-5.2"

    params = gw._build_chat_params(
        provider,
        [{"role": "user", "content": "hi"}],
        max_tokens=1000,
        enable_thinking=True,
        thinking_budget=None,
        thinking_effort="high",
        tools=None,
        tool_choice=None,
        sampling_overrides=None,
        json_mode=False,
        stream=True,
    )
    assert params.get("thinking") == {"type": "enabled"}
    assert params.get("reasoning_effort") == "high"


@pytest.mark.asyncio
async def test_build_chat_params_disabled():
    """enable_thinking=False → thinking.type=disabled。"""
    from unittest.mock import MagicMock
    from core_new.llm_gateway import LLMGateway

    provider = MagicMock()
    provider.model_name = "glm-5.2"
    provider.sampling_params = {"temperature": 1.0, "top_p": 0.95, "max_tokens": 1000}
    provider._prepare_messages = MagicMock(side_effect=lambda m, **kw: list(m))

    gw = LLMGateway.__new__(LLMGateway)
    gw._provider_name = "glm5.2"
    gw._model_name = "glm-5.2"

    params = gw._build_chat_params(
        provider, [{"role": "user", "content": "hi"}],
        max_tokens=1000, enable_thinking=False, thinking_budget=None,
        thinking_effort=None, tools=None, tool_choice=None,
        sampling_overrides=None, json_mode=False, stream=True,
    )
    assert params.get("thinking") == {"type": "disabled"}
    assert "reasoning_effort" not in params
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_gateway_enhancements.py -k build_chat_params -v`
Expected: FAIL（`stream_chat` / `_build_chat_params` 没有 `thinking_effort` 参数，TypeError）。

- [ ] **Step 3: 改 stream_chat 签名 + _build_chat_params**

Modify `core_new/llm_gateway.py`：

(a) `stream_chat` 方法签名加 `thinking_effort` 参数（约 line 440-451）：

```python
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        thinking_effort: Optional[str] = None,   # ← 新增：GLM effort 档位（high/max）
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        sampling_overrides: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
```

并在 `stream_chat` 内部把 `thinking_effort` 传给 `_build_chat_params`（约 line 462）：

```python
        params = self._build_chat_params(
            provider,
            messages,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            thinking_effort=thinking_effort,   # ← 新增
            tools=tools,
            tool_choice=tool_choice,
            sampling_overrides=sampling_overrides,
            json_mode=json_mode,
            stream=True,
        )
```

(b) `_build_chat_params` 签名加 `thinking_effort`，并重写 thinking 注入逻辑（替换现有的 thinking_budget 段，约 line 490-546）：

```python
    def _build_chat_params(
        self,
        provider,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int],
        enable_thinking: Optional[bool],
        thinking_budget: Optional[int],
        thinking_effort: Optional[str],   # ← 新增
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Any],
        sampling_overrides: Optional[Dict[str, Any]],
        json_mode: bool,
        stream: bool,
    ) -> Dict[str, Any]:
        if enable_thinking is not None and hasattr(provider, "_prepare_messages"):
            processed = provider._prepare_messages(
                messages,
                enable_thinking=enable_thinking,
                json_mode=json_mode,
            )
        else:
            processed = list(messages)

        sampling = {k: v for k, v in getattr(provider, "sampling_params", {}).items() if k != "top_k"}
        if sampling_overrides:
            sampling.update({k: v for k, v in sampling_overrides.items() if v is not None})

        params: Dict[str, Any] = {
            "model": provider.model_name,
            "messages": processed,
            "stream": stream,
            **sampling,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if json_mode and getattr(provider, "supports_response_format", False):
            params["response_format"] = {"type": "json_object"}
        if tools:
            params["tools"] = tools
        if tool_choice and tools:
            params["tool_choice"] = tool_choice

        # ── thinking 控制（统一构造，provider 协议层读这两个字段）──
        # enabled + effort：本项目主路径（GLM anthropic 端点）
        if enable_thinking is True:
            params["thinking"] = {"type": "enabled"}
            if thinking_effort:
                params["reasoning_effort"] = thinking_effort
        elif enable_thinking is False:
            params["thinking"] = {"type": "disabled"}

        # budget：本地 vLLM 或 anthropic budget（本次不接通，留接口）
        if thinking_budget and self._supports_thinking_budget(provider):
            params["thinking"]["budget_tokens"] = thinking_budget
            current_max = params.get("max_tokens", 0)
            if current_max and current_max > 0:
                params["max_tokens"] = max(current_max, thinking_budget + 16000)

        return params
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_gateway_enhancements.py -k build_chat_params -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add core_new/llm_gateway.py tests/test_gateway_enhancements.py
git commit -m "feat: stream_chat 加 thinking_effort 参数 + _build_chat_params 统一 thinking 构造"
```

---

## Task 10: gateway _read_chat_stream 重构为调 provider.stream()

**Files:**
- Modify: `core_new/llm_gateway.py`（`_read_chat_stream` 方法，约 line 548-634）

> **关键：** 现有 `_read_chat_stream` 直接调 `provider.client.chat.completions.create`（OpenAI 专有）。改为调 `provider.stream(params)`，让 provider 封装协议。这是让 gateway 支持 anthropic 的最后一块。

- [ ] **Step 1: 重写 _read_chat_stream 为委托 provider.stream()**

Modify `core_new/llm_gateway.py` 的 `_read_chat_stream` 方法（替换 line 548-634 整个方法）：

```python
    async def _read_chat_stream(self, provider, params: Dict[str, Any]) -> Dict[str, Any]:
        """统一流式读取——委托给 provider.stream()。
        provider 各自封装协议（OpenAI/anthropic），返回统一格式：
        {content, reasoning_content, tool_calls, finish_reason}
        """
        logger.debug(
            "[stream_chat] provider=%s model=%s tool_choice=%s tools=%d max_tokens=%s",
            self._provider_name,
            params.get("model"),
            params.get("tool_choice"),
            len(params.get("tools", [])),
            params.get("max_tokens"),
        )

        result = await provider.stream(params)

        logger.info(
            "[stream_chat] provider=%s content=%d reasoning=%d tool_calls=%s finish_reason=%s",
            self._provider_name,
            len(result.get("content", "")),
            len(result.get("reasoning_content", "")),
            len(result.get("tool_calls") or []),
            result.get("finish_reason"),
        )
        return result
```

- [ ] **Step 2: 验证现有 stream_chat e2e 仍工作（glm5.1 OpenAI 通路）**

> 注意：`glm5.1` provider 仍走 OpenAI 兼容，必须确保 `RemoteAPIProvider.stream()`（Task 4 加的）正确接上。

手动验证（如果有 GLM_API_KEY）：写一个临时脚本

```python
import asyncio
from core_new.llm_gateway import get_gateway

async def main():
    gw = get_gateway("glm5.2")
    result = await gw.stream_chat(
        [{"role": "user", "content": "1+1="}],
        max_tokens=1000,
        enable_thinking=True,
        thinking_effort="high",
    )
    print(f"content: {result['content']!r}")
    print(f"reasoning len: {len(result.get('reasoning_content', ''))}")

asyncio.run(main())
```

Run: `python tmp_test.py`
Expected: 打印 content="2"，reasoning 非空。

- [ ] **Step 3: 运行所有 gateway 测试确认无回归**

Run: `python -m pytest tests/test_gateway_enhancements.py tests/test_remote_api_stream.py -v`
Expected: 全部 passed（确认 Task 3/4 的测试仍通过）。

- [ ] **Step 4: Commit**

```bash
git add core_new/llm_gateway.py
git commit -m "refactor: _read_chat_stream 委托给 provider.stream()（gateway 对协议无感）"
```

---

## Task 11: agent_router.py 路由层 + agents_llm.yaml 配置

**Files:**
- Create: `core_new/agent_router.py`
- Create: `config/agents_llm.yaml`
- Test: `tests/test_agent_router.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_agent_router.py`:

```python
"""agent_router 路由层测试。"""
import pytest
from core_new.agent_router import get_gateway_for, get_thinking_config


def test_get_gateway_for_returns_gateway():
    """get_gateway_for 返回 LLMGateway 实例。"""
    gw = get_gateway_for("write_gen")
    assert gw is not None
    assert hasattr(gw, "stream_chat")


def test_get_gateway_cached():
    """同名 agent 多次调用返回同一实例（lru_cache）。"""
    gw1 = get_gateway_for("write_gen")
    gw2 = get_gateway_for("write_gen")
    assert gw1 is gw2


def test_write_gen_thinking_disabled():
    """write_gen 的 thinking.enabled=false。"""
    tc = get_thinking_config("write_gen")
    assert tc.get("enabled") is False


def test_design_direct_thinking_enabled_high():
    """design_direct 的 thinking.enabled=true, effort=high。"""
    tc = get_thinking_config("design_direct")
    assert tc.get("enabled") is True
    assert tc.get("effort") == "high"


def test_unknown_agent_falls_back_to_default():
    """未配置的 agent 用 default（enabled=true, effort=high）。"""
    tc = get_thinking_config("nonexistent_agent_xyz")
    assert tc.get("enabled") is True
    assert tc.get("effort") == "high"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_router.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'core_new.agent_router'`）。

- [ ] **Step 3: 创建 config/agents_llm.yaml**

Create `config/agents_llm.yaml`:

```yaml
# config/agents_llm.yaml
# agent 名 → provider + 思考配置的映射
# provider 必须在 config.py 的 get_provider_config() 里已定义

# 默认配置（未显式列出的 agent 用这个）
default: &default
  provider: glm5.2                # 对应 config.py 里的 glm5.2 provider（anthropic 端点）
  thinking:
    enabled: true
    effort: high                  # 保留基本思考不深度（实测 173 tokens）
    # budget: 2000                # anthropic budget_tokens，暂不用（effort 已够）

# 各 agent 的显式配置（覆盖 default）
agents:
  design_direct:
    <<: *default                  # high，出题干定结构

  write_gen:
    provider: glm5.2
    thinking:
      enabled: false              # 写复杂算法代码，关思考（凭参数知识写，exec 验证）

  write_solution:
    <<: *default                  # high，整理输出

  dual_review:
    <<: *default                  # high，审核
    # effort: max                 # 审核需最深思考时启用（待后续验证）
```

- [ ] **Step 4: 创建 core_new/agent_router.py**

Create `core_new/agent_router.py`:

```python
# core_new/agent_router.py

"""
Agent 名 → LLMGateway 的路由层（薄层）。

读 config/agents_llm.yaml，按 agent 名返回配置好的 gateway 实例。
thinking 配置由调用方在 stream_chat 时传入（不绑定 gateway——
同一 agent 不同场景可能要不同思考强度）。

调用方使用方式：
    from core_new.agent_router import get_gateway_for, get_thinking_config

    gw = get_gateway_for("write_gen")
    tc = get_thinking_config("write_gen")   # {"enabled": false}
    result = await gw.stream_chat(
        messages, tools=tools,
        enable_thinking=tc.get("enabled", True),
        thinking_effort=tc.get("effort"),
    )
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml

from config import PROJECT_ROOT
from core_new.llm_gateway import LLMGateway, get_gateway

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(PROJECT_ROOT) / "config" / "agents_llm.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    """加载并缓存 YAML 配置（首次调用时读盘）。
    用 lru_cache 保证全进程只读一次。
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"agents_llm.yaml 不存在: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg:
        raise ValueError(f"agents_llm.yaml 内容为空: {_CONFIG_PATH}")
    if "default" not in cfg:
        raise ValueError(f"agents_llm.yaml 缺少 default 配置: {_CONFIG_PATH}")
    logger.info("agents_llm.yaml loaded: %d agents configured", len(cfg.get("agents", {})))
    return cfg


def _resolve_agent_config(agent_name: str) -> dict:
    """查表：agents.<name> → default。"""
    cfg = _load_config()
    agents = cfg.get("agents", {})
    if agent_name in agents:
        return agents[agent_name]
    logger.info("agent %r 未显式配置，用 default", agent_name)
    return cfg["default"]


@lru_cache(maxsize=None)
def get_gateway_for(agent_name: str) -> LLMGateway:
    """按 agent 名返回对应的 gateway（provider 实例缓存复用）。

    查表顺序：agents.<agent_name> → default
    返回的 gateway 已按配置绑定 provider。
    thinking 配置不在 gateway 创建时绑定——调用方用 get_thinking_config() 取，
    在每次 stream_chat 时传（同一 agent 不同场景可不同强度）。
    """
    agent_cfg = _resolve_agent_config(agent_name)
    provider_name = agent_cfg.get("provider")
    if not provider_name:
        raise ValueError(f"agent {agent_name!r} 配置缺 provider 字段")
    return get_gateway(provider_name)


def get_thinking_config(agent_name: str) -> dict:
    """返回该 agent 的思考配置（enabled / effort / budget）。
    调用方据此决定传给 stream_chat 的 thinking_effort / thinking_budget。

    注意：本函数只返回配置，不做 provider 类型校验。
    effort vs budget 的有效性校验由调用方在拿到 gateway 后做
    （调用方同时持有 gateway 和 thinking_config，能判断 provider 类型）。
    """
    agent_cfg = _resolve_agent_config(agent_name)
    return agent_cfg.get("thinking", {"enabled": True})
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_router.py -v`
Expected: 5 passed。

- [ ] **Step 6: Commit**

```bash
git add core_new/agent_router.py config/agents_llm.yaml tests/test_agent_router.py
git commit -m "feat: agent_router 路由层 + agents_llm.yaml 配置（配置驱动 agent→provider）"
```

---

## Task 12: 端到端集成验证

**Files:**
- Test: `tests/test_e2e_integration.py`（新建，标 @pytest.mark.e2e）

> **这是全链路验证**：agent_router → gateway → anthropic_provider → 真 GLM API。验证整个 Task 1-11 的改动协同工作。

- [ ] **Step 1: 写 e2e 测试**

Create `tests/test_e2e_integration.py`:

```python
"""端到端集成测试：agent_router → gateway → anthropic_provider → GLM API。
需 GLM_API_KEY，标 @pytest.mark.e2e。run: pytest -m e2e
"""
import asyncio
import os

import pytest

from core_new.agent_router import get_gateway_for, get_thinking_config


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_write_gen_e2e_thinking_disabled():
    """write_gen 端到端：thinking disabled，应无 reasoning_content。"""
    if not os.getenv("GLM_API_KEY"):
        pytest.skip("GLM_API_KEY 未设置")

    gw = get_gateway_for("write_gen")
    tc = get_thinking_config("write_gen")
    assert tc.get("enabled") is False

    result = await gw.stream_chat(
        [{"role": "user", "content": "1+1="}],
        max_tokens=1000,
        enable_thinking=tc.get("enabled", True),
        thinking_effort=tc.get("effort"),
    )
    assert result["content"], f"无 content: {result}"
    # write_gen 关思考，应无 reasoning（或极短）
    reasoning = result.get("reasoning_content", "")
    assert not reasoning or len(reasoning) < 50, f"write_gen 不应深度思考: {reasoning[:200]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_design_direct_e2e_thinking_high():
    """design_direct 端到端：thinking enabled + high，应有 reasoning_content。"""
    if not os.getenv("GLM_API_KEY"):
        pytest.skip("GLM_API_KEY 未设置")

    gw = get_gateway_for("design_direct")
    tc = get_thinking_config("design_direct")
    assert tc.get("enabled") is True
    assert tc.get("effort") == "high"

    result = await gw.stream_chat(
        [{"role": "user", "content": "1+1="}],
        max_tokens=1000,
        enable_thinking=tc.get("enabled", True),
        thinking_effort=tc.get("effort"),
    )
    assert result["content"], f"无 content: {result}"
    reasoning = result.get("reasoning_content", "")
    assert reasoning, f"design_direct 应有思考: {result}"
    assert len(reasoning) > 50, f"思考过短（应 high 档）: {reasoning[:200]}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_tool_calling_e2e():
    """带工具调用的端到端（验证 anthropic tool_use 格式转换）。"""
    if not os.getenv("GLM_API_KEY"):
        pytest.skip("GLM_API_KEY 未设置")

    gw = get_gateway_for("design_direct")
    tc = get_thinking_config("design_direct")

    tools = [{
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "算数学",
            "parameters": {
                "type": "object",
                "properties": {"expr": {"type": "string"}},
                "required": ["expr"],
            },
        },
    }]

    result = await gw.stream_chat(
        [{"role": "user", "content": "用 calculate 工具算 1+1"}],
        max_tokens=1000,
        enable_thinking=tc.get("enabled", True),
        thinking_effort=tc.get("effort"),
        tools=tools,
    )
    # 应该返回 tool_calls 或 content（模型行为不保证，但不应崩）
    assert result.get("content") or result.get("tool_calls"), f"无产出: {result}"
```

- [ ] **Step 2: 运行 e2e 测试**

Run: `python -m pytest tests/test_e2e_integration.py -v -m e2e`
Expected: 3 passed（如果 GLM_API_KEY 已配）。

> 如果 e2e 因环境跑不了，至少确认 unit 测试全绿：

Run: `python -m pytest tests/ -v -k "not e2e"`
Expected: 所有非 e2e 测试 passed。

- [ ] **Step 3: 清理临时测试文件（如有）**

如果 Task 10 Step 2 建了 `tmp_test.py`，删掉。

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_integration.py
git commit -m "test: 端到端集成测试（agent_router→gateway→anthropic→GLM API）"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 要求 | 对应 Task |
|----------|----------|
| §3.2 指数退避重试 | Task 2（policy 字段）+ Task 3（gateway 方法） |
| §3.3 reasoning_effort 参数支持 | Task 9（gateway） |
| §3.4 agent_router.py | Task 11 |
| §3.5 anthropic_provider.py | Task 5 |
| §3.6 config.py glm5.2 + 清 32B | Task 7 |
| §3.6 get_llm_provider 工厂分支 | Task 6 |
| §4 错误处理 anthropic 分支 | Task 8 |
| §3.3 _read_chat_stream 重构 | Task 10 |
| RemoteAPIProvider 加 stream()（§6 文件清单） | Task 4 |
| anthropic SDK 装入依赖 | Task 1 |
| §5 验证策略（测试 1/2/3/4） | Task 3/9/11/5 + Task 12 e2e |

**所有 spec 要求都有对应 Task。** ✅

### 类型/方法名一致性检查

- `get_gateway_for(agent_name)` / `get_thinking_config(agent_name)`：Task 11 定义，Task 12 使用 ✓
- `provider.stream(params)`：Task 4（remote_api）+ Task 5（anthropic）定义，Task 10（gateway）使用 ✓
- `_build_chat_params(..., thinking_effort=...)`：Task 9 定义，Task 10 经 stream_chat 传递 ✓
- `TransportRetryPolicy(backoff_base, backoff_max_wait)`：Task 2 定义，Task 3 使用 ✓
- `api_protocol="anthropic_messages"`：Task 7（config）定义，Task 6（工厂）使用 ✓

**全部一致。** ✅

---

## 执行顺序建议

Task 之间有依赖，建议顺序：

```
Task 1（装 SDK）
  → Task 2（retry policy）
    → Task 3（gateway 退避）—— 可独立验证
  → Task 7（config glm5.2）—— 可独立验证
    → Task 6（工厂分支）
      → Task 5（anthropic provider）—— 核心，可独立 e2e 验证
        → Task 4（remote_api stream）
          → Task 9（gateway thinking_effort）
            → Task 10（gateway _read_chat_stream 重构）
              → Task 11（agent_router）
                → Task 12（端到端集成）
Task 8（错误分类）可在 Task 5 之后任意时间做
```

**关键验证点**：
- Task 5 完成后：anthropic provider 可独立 e2e（`pytest -m e2e`），确认 API 通
- Task 10 完成后：gateway 全链路通（手动跑 tmp 脚本）
- Task 12 完成后：全系统集成验证
