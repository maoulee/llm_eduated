# LLM Gateway 增强 + Agent 路由层 + Anthropic Provider 设计

**日期**：2026-06-22
**子项目**：A（地基层）—— 5 大设计点重构的第 1 个
**版本**：v3（基于 anthropic 端点实测，最终方案）
**状态**：已通过 brainstorming，待写实现计划

---

## 1. 背景与动机

### 1.1 项目整体重构（5 大设计点）

服务器丢失后从零重建 llm_eduated 项目架构。经 brainstorming 拆解为 3 个按依赖顺序的子项目：

```
子项目 A（地基层）：#4 LLM 调用统一层 + #3 端点分流      ← 本文档
子项目 B（行为机制）：#2 思考准则外化（可执行闸 skill 框架）
子项目 C（业务流水线）：#1 code as truth 两段式 + #5 审核规则
```

本文档聚焦**子项目 A**：LLM 调用统一层 + 端点分流。

### 1.2 现状盘点（关键发现）

读完 `core_new/llm_gateway.py`（1120 行）后发现：**网关已实现约 70% 需求**，不是"从零重建"。

| 需求 | 现状 | 评价 |
|------|------|------|
| 统一抽象层 + `LLMResult` | ✅ `LLMGateway` + `get_gateway()` | 已有 |
| httpx 握手保持（连接池） | ✅ `max_keepalive_connections` + `keepalive_expiry` | 已有 |
| 错误分类 | ✅ `_classify_exception`（timeout/rate_limit/server_error/connection_error） | 已有 |
| 重试 | ⚠️ 有，但 `_wait_with_backoff` 是固定 3 秒，非指数退避 | **需改** |
| agent loop + 工具调用 | ✅ `generate_with_tools`（断路器、轮次预算）+ `stream_chat` | 已有 |
| 本地 `thinking_budget` | ✅ `_supports_thinking_budget` + `thinking_token_budget` 注入 | 已有 |
| anthropic 端点支持 | ❌ 现有 `RemoteAPIProvider` 只支持 OpenAI 兼容协议 | **需新写** |
| agent 名 → 模型映射 | ⚠️ 只有 `get_gateway(provider_name)`，无 agent 维度路由 | **缺失** |

**关键事实**：
- `core_new/llm_gateway.py` 是较新的、已在 agent loop 路径上工作的网关（非去年遗留）
- 去年遗留的是 `llm_providers_new/RemoteAPIProvider`（OpenAI 兼容批量接口，服务批量标注）——**本次不并入，但保留**
- 现有代码**零用过 anthropic SDK**（全仓 `import anthropic` 零匹配）

### 1.3 当前环境约束

- 只有在线 GLM-5.2（无本地 vLLM）
- 已验证 `reasoning_effort: high` 符合"保留基本思考但不要深度思考"的需求
- `reasoning_effort: max` 是 GLM-5.2 默认值（不显式传 effort 时模型用 max，深度思考）
- 本地 `thinking_budget` 暂无环境（保留字段位，不实现路由）

### 1.4 端点实测结论（2026-06-22 实测，决定技术方案）

GLM 平台有三个端点，用真实 key 实测：

| 端点 | 协议 | 测试参数 | 思考是否生效 |
|------|------|---------|------------|
| `/api/coding/paas/v4` | OpenAI chat completions | `reasoning_effort: high` | ✅ 生效（147 tokens 思考） |
| `/api/anthropic` | Anthropic Messages | `thinking.type: disabled` | ✅ 关思考生效（0 思考） |
| `/api/anthropic` | Anthropic Messages | `thinking.type: enabled`（无 budget） | ✅ 生效（132 tokens 思考） |
| `/api/anthropic` | Anthropic Messages | `thinking.type: enabled` + `reasoning_effort: high` | ✅ **生效（173 tokens 思考）** |
| `/api/anthropic` | Anthropic Messages | 仅 `reasoning_effort: high`（无 thinking.type） | ❌ 被静默忽略（0 思考） |

**关键结论**：
- **GLM 的 anthropic 端点支持 `thinking.type`（开关）+ `reasoning_effort`（档位）协同工作**——这与 GLM 官方文档一致：`extra_body = {"thinking": {"type": "enabled"}, "reasoning_effort": "max"}`
- `reasoning_effort` 必须配合 `thinking.type: enabled` 才生效（单独传 effort 被忽略）
- **选定 `/api/anthropic` 端点**：与你 .env 现有配置（`GLM_API_BASE=/api/anthropic`）对齐，无需改 .env 的 URL

**GLM-5.2 的 effort 档位语义**（来自官方文档）：
- `max`：最高推理强度（**默认值**，不显式传时模型用 max）
- `high`：较高推理强度（本项目用这个，"保留基本思考不深度"）
- `low`/`medium`：映射为 high
- `none`/`minimal`：跳过思考（用 `thinking.type: disabled` 替代）
- `xhigh`：映射为 max

---

## 2. 设计方案

**选定方案**：就地增强 `llm_gateway.py` + 新写 `anthropic_provider.py` + 新增 `agent_router.py`

### 2.1 架构总览与职责边界

```
┌─────────────────────────────────────────────────────────┐
│  上层（doc_pipeline scheduler / agents）                │
│    调用方式：router.get_gateway_for("write_gen")        │
└────────────────────────┬────────────────────────────────┘
                         │ agent 名
                         ▼
┌─────────────────────────────────────────────────────────┐
│  agent_router.py（新，薄层）                             │
│    职责：agent 名 → (provider_name, thinking 配置)       │
│    读：config/agents_llm.yaml（配置驱动）                │
│    返回：LLMGateway 实例（带缓存的 provider 复用）        │
└────────────────────────┬────────────────────────────────┘
                         │ provider_name
                         ▼
┌─────────────────────────────────────────────────────────┐
│  llm_gateway.py（增强）                                  │
│    职责：单 provider 的调用 + 重试 + 思考控制 + 限流      │
│    新增/改：                                             │
│      - _wait_with_backoff: 固定3秒 → 指数退避            │
│      - stream_chat/_build_chat_params: 加 reasoning_effort│
│      - _read_chat_stream: 抽象成 provider.stream() 统一  │
│      - 复用现有：断路器/错误分类/LLMResult/连接池         │
└────────────────────────┬────────────────────────────────┘
                         │ 统一的 stream() 抽象
                         ▼
┌─────────────────────────────────────────────────────────┐
│  providers（协议适配层）                                 │
│  ├─ anthropic_provider.py（新）                          │
│  │   职责：anthropic Messages 协议适配                   │
│  │   用 anthropic SDK，传 thinking.type + reasoning_effort│
│  │   实现 provider.stream() 供 gateway 调用              │
│  └─ remote_api.py（不改）                                │
│      职责：OpenAI 兼容协议（批量标注 + 旧通路）          │
│      实现 provider.stream()（新增方法，供 gateway 调用） │
└─────────────────────────────────────────────────────────┘
```

**职责单一性**：
- `agent_router`：只管"哪个 agent 用哪个 provider+思考配置"
- `llm_gateway`：只管"一个 provider 怎么调、怎么重试、怎么控制思考"——**不碰协议细节**
- `anthropic_provider`/`remote_api`：只管"协议字段怎么拼、流式响应怎么解析"

**关键架构决策**：gateway 不再直接调 `provider.client.chat.completions.create`（OpenAI 专有），改为调 `provider.stream(params)`——provider 各自封装协议。这样 gateway 对协议无感，新加协议只需新写 provider。

---

## 3. 详细设计

### 3.1 配置驱动的 agent → 模型映射

**新建配置文件** `config/agents_llm.yaml`：

```yaml
# config/agents_llm.yaml
# agent 名 → provider + 思考配置的映射
# provider 必须在 config.py 的 get_provider_config() 里已定义

# 默认配置（未显式列出的 agent 用这个）
default: &default
  provider: glm5.2                # 对应 config.py 里新增的 glm5.2 provider
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

**设计要点**：

1. **`thinking.effort` vs `thinking.budget` 二选一**：本次用 `effort`（high 档）。budget 字段保留（anthropic 端点原生支持 budget_tokens），但本次不接通——effort 档位已能满足"保留基本思考不深度"。

2. **YAML 锚点 `&default`**：避免重复，agent 配置只写差异。

3. **`provider` 字段必须对应 `config.py` 里已定义的 provider_name**：启动时校验，缺失即报错（fail-fast）。本次需在 `config.py` 新增 `glm5.2` provider（详见 §3.6）。

4. **思考控制是"档位"而非"开关"**：反映调试期核心发现。`enabled: false` 等价于 `thinking.type: disabled`（关思考），`enabled: true + effort: high` 是"保留基本思考"。

### 3.2 增强 1：指数退避重试

**现状**（`llm_gateway.py:186-189`）：
```python
async def _wait_with_backoff(self, attempt: int) -> None:
    """Fixed 3s backoff."""
    logger.info("Transport retry attempt %d, waiting 3.0s", attempt + 1)
    await asyncio.sleep(3.0)
```

**改为指数退避 + 抖动**：
```python
async def _wait_with_backoff(self, attempt: int) -> None:
    """Exponential backoff with jitter.
    attempt 从 0 开始：base * 2^attempt + jitter
    第1次重试 ~2s，第2次 ~4s，第3次 ~8s，上限 30s。
    """
    base = 2.0
    max_wait = 30.0
    delay = min(base * (2 ** attempt) + random.uniform(0, 1), max_wait)
    logger.info("Transport retry attempt %d, waiting %.1fs", attempt + 1, delay)
    await asyncio.sleep(delay)
```

**为什么加 jitter**：避免多并发请求同时重试造成"惊群"（thundering herd）——Claude Code 重试机制的标准做法。

**配置位置**：base/max_wait 作为 `TransportRetryPolicy`（`agent_roles.py` 里已有）的字段，不硬编码。仅改一个方法，零风险。

### 3.3 增强 2：reasoning_effort 参数支持（gateway 层）

数据流：
```
config/agents_llm.yaml (effort: high)
  → agent_router.py 读取，存入 thinking_config
  → gateway.stream_chat(thinking_effort="high")  新增参数
  → _build_chat_params 注入 thinking 字段
  → provider.stream() 调用（anthropic / openai 各自封装）
```

**改动点 1**：`stream_chat` 加 `thinking_effort` 参数：
```python
async def stream_chat(
    self, messages, *,
    max_tokens=None, enable_thinking=None,
    thinking_budget=None,
    thinking_effort: Optional[str] = None,   # ← 新增
    tools=None, tool_choice=None,
    sampling_overrides=None, json_mode=False,
) -> Dict[str, Any]:
```

**改动点 2**：`_build_chat_params` 注入 thinking（同时支持两种 provider）：
```python
# 思考控制：gateway 层统一构造 thinking 字段
# enabled + effort（本项目主路径）
if enable_thinking is True and thinking_effort:
    params["thinking"] = {"type": "enabled"}
    params["reasoning_effort"] = thinking_effort
# 仅 enabled（无 effort，用模型默认 max）
elif enable_thinking is True:
    params["thinking"] = {"type": "enabled"}
# disabled
elif enable_thinking is False:
    params["thinking"] = {"type": "disabled"}

# budget（本地 vLLM 或 anthropic budget，本次不接通）
if thinking_budget and self._supports_thinking_budget(provider):
    params["thinking"]["budget_tokens"] = thinking_budget
```

**改动点 3**：`_read_chat_stream` 重构为调 `provider.stream(params)`：
```python
async def _read_chat_stream(self, provider, params: Dict[str, Any]) -> Dict[str, Any]:
    """统一流式读取——委托给 provider 协议适配。
    provider.stream() 返回统一的 {content, reasoning, tool_calls, finish_reason}。
    """
    return await provider.stream(params)
```

**关键约束**：`thinking_effort` 和 `thinking_budget` **互斥**——一个 provider 只支持其一。

### 3.4 增强 3：`agent_router.py`（新文件）

```python
# core_new/agent_router.py
"""
Agent 名 → LLMGateway 的路由层（薄层）。
读 config/agents_llm.yaml，按 agent 名返回配置好的 gateway 实例。
"""
from pathlib import Path
import yaml
from functools import lru_cache
from core_new.llm_gateway import get_gateway

_CONFIG_PATH = Path("config/agents_llm.yaml")

@lru_cache(maxsize=1)
def _load_config() -> dict:
    """加载并缓存 YAML 配置（首次调用时读盘）。"""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

@lru_cache(maxsize=None)
def get_gateway_for(agent_name: str):
    """按 agent 名返回对应的 gateway（provider 实例缓存复用）。

    查表顺序：agents.<agent_name> → default
    返回的 gateway 已按配置绑定 provider；
    thinking 配置由调用方在 stream_chat 时传入（不绑定 gateway）。
    """
    cfg = _load_config()
    agent_cfg = cfg.get("agents", {}).get(agent_name, cfg.get("default", {}))
    provider_name = agent_cfg["provider"]
    return get_gateway(provider_name)

def get_thinking_config(agent_name: str) -> dict:
    """返回该 agent 的思考配置（enabled / effort / budget）。
    调用方据此决定传给 stream_chat 的 thinking_effort / thinking_budget。

    注意：本函数只返回配置，不做 provider 类型校验。
    effort vs budget 的有效性校验由调用方在拿到 gateway 后做
    （调用方同时持有 gateway 和 thinking_config，能判断 provider 类型）。
    """
    cfg = _load_config()
    agent_cfg = cfg.get("agents", {}).get(agent_name, cfg.get("default", {}))
    return agent_cfg.get("thinking", {})
```

**关键设计决策**：

- **gateway 实例缓存**（`lru_cache`）：同一个 provider 只创建一次，复用连接池
- **thinking 配置不绑定 gateway**：gateway 只认 provider，思考强度在每次 `stream_chat` 调用时传
- **查表 fallback 到 default**：新 agent 不必显式配置，自动用默认

**调用方使用方式**（上层 scheduler）：
```python
from core_new.agent_router import get_gateway_for, get_thinking_config

gw = get_gateway_for("write_gen")
tc = get_thinking_config("write_gen")   # {"enabled": false}
result = await gw.stream_chat(
    messages, tools=tools,
    enable_thinking=tc.get("enabled", True),
    thinking_effort=tc.get("effort"),    # None 时不传
)
```

### 3.5 新写 `anthropic_provider.py`

**职责**：封装 GLM `/api/anthropic` 端点的 Anthropic Messages 协议。

**依赖**：`anthropic` SDK（需 `pip install anthropic`，pyproject 已声明但环境未装）。

**核心接口**（供 gateway 调用）：
```python
# llm_providers_new/anthropic_provider.py
"""
GLM anthropic 端点的 Provider。
用 anthropic SDK 的 AsyncAnthropic，走 Messages API。
思考控制：thinking.type（开关）+ reasoning_effort（档位，GLM 扩展）。
"""
import logging
from typing import Any, Dict, List, Optional
import anthropic
import httpx
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    """GLM anthropic 端点 provider，实现 BaseLLMProvider + stream() 供 gateway 调用。"""

    def __init__(self, model_name: str, api_base_url: str, api_key: str, **kwargs):
        self.model_name = model_name
        self.provider_type = "api"
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.request_timeout = float(kwargs.get("request_timeout", 300.0))
        # GLM anthropic 端点的 base_url 要去掉 /v1（SDK 自己加）
        # /api/anthropic → client 用这个作 base_url
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
        # anthropic SDK 客户端
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.request_timeout,
            http_client=self.http_client,
        )
        logger.info("AnthropicProvider initialized: model=%s base_url=%s", model_name, self.api_base_url)

    def _prepare_messages(self, messages, enable_thinking=None, json_mode=False):
        """OpenAI 风格 messages 转 anthropic 风格。
        anthropic 要求：system 单独传，messages 只能有 user/assistant。
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

    async def stream(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """统一流式接口——供 gateway._read_chat_stream 调用。
        params 由 gateway._build_chat_params 构造，含 thinking/effort/tools 等。
        返回 {content, reasoning_content, tool_calls, finish_reason}。
        """
        messages, system = self._prepare_messages(params["messages"])
        kwargs = {
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
            # GLM 扩展字段，SDK 通过 extra_body 传
            kwargs["extra_body"] = {"reasoning_effort": params["reasoning_effort"]}
        if params.get("tools"):
            kwargs["tools"] = self._convert_tools(params["tools"])
        if params.get("stream", True):
            return await self._read_stream(kwargs)
        else:
            return await self._read_non_stream(kwargs)

    async def _read_stream(self, kwargs) -> Dict[str, Any]:
        """解析 anthropic 流式事件（content_block_start/content_block_delta/tool_use 等）。
        实现要点（实现时对照 anthropic SDK 的 messages.stream() 文档）：
        1. async with self.client.messages.stream(**kwargs) as stream
        2. 遍历 stream，按 event 类型累积：
           - text 块 → content_parts
           - thinking 块 → reasoning_parts
           - tool_use 块 → tool_calls（转成 OpenAI 风格 {id, type:function, function:{name, arguments}}）
        3. stream.get_final_message() 拿 stop_reason
        """
        content_parts, reasoning_parts, tool_calls = [], [], []
        finish_reason = None
        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                # 按 anthropic SDK 的 event 类型分发累积（实现时填）
                pass
            final = await stream.get_final_message()
            finish_reason = final.stop_reason
        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls or None,
            "finish_reason": finish_reason,
        }

    def _convert_tools(self, openai_tools):
        """OpenAI tools 格式转 anthropic tools 格式。"""
        converted = []
        for tool in openai_tools:
            fn = tool.get("function", tool)
            converted.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return converted

    # BaseLLMProvider 的 batch 接口——本次不实现（批量标注走 remote_api）
    async def generate_with_think_and_parse_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider 不支持批量，用 remote_api 走批量标注")

    async def generate_json_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider 不支持批量，用 remote_api 走批量标注")
```

**关键设计决策**：

1. **不继承 OpenAI 的 `_chat_call`/`_extra_body_for_thinking`**：anthropic 协议完全不同，重新实现
2. **新增 `stream(params)` 方法**：统一接口供 gateway 调用。gateway 不再直接碰 SDK
3. **`_prepare_messages` 处理 system 分离**：anthropic 要求 system 单独传，与 OpenAI 的 messages 列表不同
4. **tools 格式转换**：anthropic 的 `input_schema` vs OpenAI 的 `parameters`
5. **batch 接口抛 NotImplementedError**：批量标注不经过 anthropic provider，走旧的 remote_api

**remote_api.py 也要加 `stream()` 方法**：为保持 gateway 的统一调用，`RemoteAPIProvider`（OpenAI 兼容）也要实现 `stream(params)`——内部封装现有的 `client.chat.completions.create(stream=True)` 逻辑（从 `_read_chat_stream` 搬过来）。这是"统一接口"的代价。

### 3.6 config.py 与 .env 修正（前置依赖）

agent_router 依赖 `config.py` 里有 `glm5.2` provider，当前不存在（只有 `glm5.1`）。这是本次的前置改动。

**config.py 改动**：
1. **新增 `glm5.2` provider**（anthropic 协议）：
   ```python
   "glm5.2": ProviderSettings(
       provider_type="api",
       model_path=os.getenv("GLM_MODEL", "glm-5.2"),
       api_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/anthropic"),
       api_key=os.getenv("GLM_API_KEY"),
       api_protocol="anthropic_messages",   # 新协议标识，路由到 AnthropicProvider
       batch_size=int(os.getenv("GLM_BATCH_SIZE", "4")),
       request_timeout=float(os.getenv("GLM_REQUEST_TIMEOUT", "600")),
       max_retries=int(os.getenv("GLM_MAX_RETRIES", "0")),
       thinking_control_method=os.getenv("GLM_THINKING_CONTROL_METHOD", "none"),
       supports_response_format=False,      # anthropic 协议不用 OpenAI response_format
       default_max_tokens=int(os.getenv("GLM_DEFAULT_MAX_TOKENS", "30000")),
       temperature=float(os.getenv("GLM_TEMPERATURE", "1.0")),
       top_p=float(os.getenv("GLM_TOP_P", "0.95")),
   ),
   ```
2. **新增 `api_protocol="anthropic_messages"` 协议标识**：`get_llm_provider()` 工厂按这个标识创建 `AnthropicProvider`（而非 `RemoteAPIProvider`）。
3. **清除 `api_vllm` 的 32B 默认**：`api_vllm` provider 的 `model_path` 默认 `Qwen3.6-27B-AWQ-INT4`（27B/32B 系列，已不用）。**只改默认 model_path 为占位**（如 `os.getenv("VLLM_MODEL", "")`），**不删除 provider 定义**（本地批量标注功能仍依赖 `api_vllm`，将来有本地环境时通过 `.env` 的 `VLLM_MODEL` 注入实际路径）。

**.env 改动**：
- `GLM_API_BASE="https://open.bigmodel.cn/api/anthropic"` ✅（已正确，无需改）
- `GLM_MODEL=glm-5.2` ✅（已正确）
- `GLM_THINKING_CONTROL_METHOD=none` ✅（保持 none，effort 由 gateway 注入，不靠 provider 的 param/prompt 机制）

**为什么 GLM_THINKING_CONTROL_METHOD=none**：现有 `remote_api.py:160-162` 的 `param` 方式传的是 `{"thinking": {"type": "enabled"}}`（开关）。但 anthropic provider 不走这套，thinking 字段完全由 gateway 的 `_build_chat_params` 构造。设为 none 让 provider 不自作主张传思考参数——职责清晰。

---

## 4. 错误处理

现有错误分类已完整（`_classify_exception` 覆盖 timeout/rate_limit/server_error/connection_error + httpx + openai SDK）。本次新增 anthropic SDK，需补充：

| 增强项 | 错误处理 |
|--------|---------|
| 指数退避 | 沿用 `_should_retry` 判定，只改等待时长 |
| anthropic provider | 新增 anthropic SDK 异常分类：`anthropic.APITimeoutError`→timeout，`anthropic.RateLimitError`→rate_limit，`anthropic.APIStatusError`→按状态码分。加到 `_classify_exception` |
| agent_router | 配置缺失 → 启动时 `KeyError` 快速失败（fail-fast） |

**`_classify_exception` 要加 anthropic 分支**（与现有 openai 分支并列）：
```python
def _classify_exception(error: Exception) -> str:
    # anthropic SDK（新增）
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
            if status == 429: return "rate_limit"
            if status in {408, 425}: return "timeout"
            if status >= 500: return "server_error"
            return "api_error"
    except ImportError:
        pass  # anthropic 未装时跳过
    # 现有 openai/httpx 分支保持不变 ...
```

---

## 5. 验证策略

不写 mock，全部**真实 GLM API 端到端验证**。每个测试独立、可单独跑。

### 测试 1（指数退避）
- **触发**：临时把 `api_url` 改成错误地址（强制连接失败）
- **验证**：观察重试间隔是否从 ~2s 增长到 ~4s、~8s（看日志时间戳）
- **不需要真 API key**，只验证退避时序

### 测试 2（thinking + reasoning_effort）
- **方法**：同一 prompt（如"1+1="），分别用以下组合跑一次：
  - `enabled=true, effort=high` → 应有思考块（实测 ~173 tokens）
  - `enabled=false` → 应无思考块（0 tokens）
- **端点**：`/api/anthropic`
- **验证**：返回的 `reasoning_content` 有差异，证明 thinking 字段真被 API 接收并生效

### 测试 3（agent_router）
- **方法**：调用 `get_gateway_for("write_gen")` 和 `get_gateway_for("design_direct")`
- **验证**：
  - 返回的 gateway 实例 provider 正确（都是 glm5.2，但配置不同）
  - `get_thinking_config` 返回的 `enabled` 字段对（write_gen=false, design_direct 默认 true）
  - 调两次同名 agent，验证 `lru_cache` 复用（id 相同）

### 测试 4（anthropic provider 端到端，新增）
- **方法**：直接调 `AnthropicProvider.stream()` 跑一个带工具的 prompt
- **验证**：
  - content/reasoning_content 正确解析
  - tool_calls 格式从 anthropic 正确转成 OpenAI 风格（供 gateway 的 agent loop 用）
  - 流式和非流式都能工作

**不做的测试**：批量回归、200 条压测——本次增强不碰批量路径。

---

## 6. 迁移策略

**关键原则：零强制，渐进式**。不强制上层立即改用 `agent_router`。

| 调用方式 | 状态 |
|---------|------|
| 旧：`get_gateway("glm5.1")` | ✅ 继续可用（glm5.1 provider 保留，向后兼容） |
| 新：`get_gateway_for("write_gen")` | ✅ 新方式，配置驱动 |

本次设计**只提供新接口、不改现有调用点**。等子项目 B（思考准则外化）落地时，scheduler 自然改成按 agent 名路由。

### 代码改动文件清单（精确）

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `config.py` | 改 | ~25 行（新增 `glm5.2` provider + `api_protocol=anthropic_messages` 标识 + 清除 `api_vllm` 的 32B 默认） |
| `.env` | 不改 | 0（GLM_API_BASE 已正确指向 /api/anthropic） |
| `core_new/llm_gateway.py` | 改 | ~60 行（`_wait_with_backoff` 重写 + `stream_chat`/`_build_chat_params` 加 `thinking_effort` + `_read_chat_stream` 重构为调 `provider.stream()` + `_classify_exception` 加 anthropic 分支） |
| `core_new/agent_router.py` | 新建 | ~50 行 |
| `llm_providers_new/anthropic_provider.py` | 新建 | ~180 行（含流式解析、tools 转换、message 适配） |
| `llm_providers_new/remote_api.py` | 改 | ~30 行（加 `stream(params)` 方法，从 gateway 搬现有流式逻辑） |
| `llm_providers_new/__init__.py` | 改 | ~10 行（`get_llm_provider` 工厂加 anthropic_messages 协议分支） |
| `config/agents_llm.yaml` | 新建 | ~25 行 |
| `pyproject.toml` | 改 | ~1 行（确认 anthropic 在 dependencies，非 optional） |
| `tests/test_agent_router.py` | 新建 | ~40 行（测试 3） |
| `tests/test_gateway_enhancements.py` | 新建 | ~60 行（测试 1+2） |
| `tests/test_anthropic_provider.py` | 新建 | ~50 行（测试 4） |

**总改动量：约 530 行**，其中测试约 150 行。

---

## 7. YAGNI 边界（本次不做）

明确列出**本次不做**的，防止 scope creep：

- ❌ 不实现本地 vLLM 通路的 budget 路由（无环境，留字段位）
- ❌ 不实现 `effort: max`（默认即 max，本项目用 high）
- ❌ 不动批量标注路径（`LocalVLLMProvider` + `RemoteAPIProvider` 批量接口继续用）
- ❌ 不强制迁移现有 `get_gateway()` 调用点
- ❌ 不做 thinking_budget 的"自动膨胀 max_tokens"逻辑调整（现有逻辑保留）
- ❌ anthropic provider 不实现 batch 接口（抛 NotImplementedError）
- ❌ 不删除旧 `glm5.1` provider（向后兼容）

---

## 8. 后续衔接

本子项目（A 地基）完成后，将依次进入：
- **子项目 B（行为机制）**：思考准则外化——可执行闸 skill 框架（把 Claude 的内在思考纪律外化成 GLM 能遵守的触发器+终止问句+动作规则）
- **子项目 C（业务流水线）**：code as truth 两段式（design 出骨架+断言 → solve 建模+参数优化）+ 审核规则（审形式+审题干意图+合围+A/B 判定）

这两个子项目会各自走独立的 spec → plan → 实现周期。

---

## 附录 A：端点实测原始数据（2026-06-22）

### A.1 coding/paas/v4 端点（OpenAI 兼容）

**请求**：`POST /api/coding/paas/v4/chat/completions`
```json
{"model":"glm-5.2","max_tokens":1000,"reasoning_effort":"high","messages":[{"role":"user","content":"1+1="}]}
```
**响应**：思考 147 tokens，content "2"

### A.2 anthropic 端点（Anthropic Messages）

**测试 1**：`thinking.type: disabled` → 思考 0 tokens ✅
**测试 2**：`thinking.type: enabled`（无 budget）→ 思考 132 tokens ✅
**测试 3**：`thinking.type: enabled` + `reasoning_effort: high` → 思考 **173 tokens** ✅（选定方案的配置）
**测试 4**：仅 `reasoning_effort: high`（无 thinking.type）→ 思考 0 tokens ❌（effort 必须配 thinking.type）

### A.3 关键发现

`reasoning_effort` 在 anthropic 端点**生效前提**是必须带 `thinking.type: enabled`。这与 GLM 官方文档的推荐用法一致：
```json
{"thinking": {"type": "enabled"}, "reasoning_effort": "max"}
```
