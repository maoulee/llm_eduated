# LLM Gateway Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GLM-5.2 Anthropic-protocol provider, a protocol-agnostic `provider.stream()` interface on the gateway, exponential-backoff retries, an agent→gateway router, and neutral thinking-intent plumbing — all validated by real online GLM-5.2 calls.

**Architecture:** The gateway stops touching SDK/protocol details directly. `_build_chat_params` emits a protocol-neutral `thinking_intent`; each provider's `stream(params)` owns message preparation + thinking-field translation + stream parsing, returning a unified `{content, reasoning_content, tool_calls, finish_reason}`. A new `agent_router` maps agent names → provider + thinking config (driven by `config/agents_llm.yaml`), positioned alongside the existing `provider_router`.

**Tech Stack:** Python ≥3.12, `anthropic>=0.90` (SDK surfaces verified against 0.96.0; `pip install -e .` resolves to the latest, e.g. 0.111.0 — the surfaces used are stable), `openai>=2.0`, `httpx`, `pydantic`, `pyyaml>=6.0`. Tests are script-style (`python tests/test_x.py`, `asyncio.run(main())`), real online GLM-5.2 calls, no mocks.

## Global Constraints

- **Python ≥3.12** (pyproject `requires-python`). The default shell `python3` is anaconda 3.10 with a broken `typing_extensions` — `import anthropic` FAILS under it, so it is unusable. The working 3.12 interpreter is `/data/amax/home/E22101006/miniconda3/bin/python3.12` (3.12.4); it has `venv` but NO project deps yet. Task 0 provisions a `.venv` from it. Every `Run:` command below assumes the activated `.venv` (where `python` resolves to 3.12). anthropic 0.96.0 source is also on disk at `~/.local/lib/python3.10/site-packages/anthropic/`.
- **No local model.** All E2E tests use the online GLM-5.2 `/api/anthropic` endpoint (`.env`: `GLM_API_BASE=https://open.bigmodel.cn/api/anthropic/`, `GLM_MODEL=glm-5.2`, `GLM_THINKING_CONTROL_METHOD=none`). `glm5.1` is dead (shares these env vars; openai_chat protocol ≠ anthropic endpoint).
- **Real API key lives in `.env`** (gitignored, NOT committed). Tests `load_dotenv`. Never hardcode the key.
- **`anthropic>=0.90` + `pyyaml>=6.0` already in core deps** — do NOT touch pyproject dependencies.
- **GLM anthropic endpoint facts (附录 A, verified 2026-06-22):** `thinking.type: enabled` (bare, no budget) → ~132 thinking tokens; `enabled` + `extra_body={"reasoning_effort":"high"}` → ~173 tokens; bare `reasoning_effort` without `thinking.type` → ignored (0 tokens). The anthropic SDK (≥0.90; behavior verified against the 0.96.0 source on disk — `pip install` will fetch a newer compatible release) supports `extra_body` (merged to `extra_json`); `ThinkingConfigEnabledParam.budget_tokens` is `Required` for static typecheck only, NOT runtime-enforced.
- **No mocks** except where no live endpoint exists (none needed here — `glm4flash` on paas/v4 covers the OpenAI path).
- **Test style:** script-style, `python tests/<file>.py`, each prints PASS/FAIL and exits non-zero on failure.

---

## File Structure

| File | Op | Responsibility |
|------|----|----------------|
| `core_new/agent_roles.py` | Modify | Add `base`/`max_wait` to `TransportRetryPolicy` |
| `core_new/llm_gateway.py` | Modify | Exponential backoff; neutral `thinking_intent`; `_read_chat_stream`→`provider.stream()`; anthropic error classification |
| `config.py` | Modify | Add `glm5.2` provider (`api_protocol="anthropic_messages"`) |
| `.env.example` | Restore+Modify | Update template to anthropic+glm-5.2 (currently deleted in working tree) |
| `llm_providers_new/anthropic_provider.py` | Create | Anthropic Messages protocol adapter + `stream()` |
| `llm_providers_new/remote_api.py` | Modify | Add `stream(params)` (extract OpenAI stream parsing from gateway) |
| `llm_providers_new/__init__.py` | Modify | Route `anthropic_messages` → `AnthropicProvider` |
| `core_new/agent_router.py` | Create | agent name → gateway + thinking config (YAML-driven) |
| `config/agents_llm.yaml` | Create | agent → provider + thinking mapping |
| `tests/test_backoff.py` | Create | T1+T2 |
| `tests/test_anthropic_provider.py` | Create | T4 (unit + E2E test 4) |
| `tests/test_factory_routing.py` | Create | T3+T5 |
| `tests/test_remote_api_stream.py` | Create | T6 (E2E via glm4flash) |
| `tests/test_gateway_thinking.py` | Create | T7 (E2E test 2) |
| `tests/test_error_classification.py` | Create | T8 |
| `tests/test_agent_router.py` | Create | T9 (test 3) |

**Dependency order:** T0 → T1 → T2 ; T0 → T4 → T5 → T7 ; T3 → T5 ; T6 → T7 ; T0 → T8 ; T3 → T9. T0 and T3 are unblocked.

---

## Task 0: Environment prerequisite

**Files:** none (verification only)

**Interfaces:** Produces: a working `anthropic` import under Python ≥3.12, and confirmation `.env` has `GLM_API_KEY`.

- [ ] **Step 1: Provision a Python 3.12 venv with project deps (BLOCKER — do this first)**

The default `python3` (anaconda 3.10) has a broken `typing_extensions` and CANNOT `import anthropic`. The working 3.12 is at an absolute path, NOT on PATH. Provision a venv from it:

Run (from repo root `/data/amax/home/E22101006/llm_edu/llm_eduated`):
```bash
/data/amax/home/E22101006/miniconda3/bin/python3.12 -m venv .venv
source .venv/bin/activate
python --version
pip install -e .
python -c "import anthropic, openai, httpx, pydantic, yaml, dotenv; print('deps OK; anthropic', anthropic.__version__)"
```
Expected: `Python 3.12.4`, install output, then `deps OK; anthropic <version>` where `<version>` is ≥0.90 (resolver picks latest, e.g. `0.111.0` — not 0.96.0; the surfaces used are stable across these).

**Fallback if that interpreter is absent:** locate any 3.12 via `ls /data/amax/home/E22101006/miniconda3/bin/python3.* /opt/anaconda3/bin/python3.* /usr/bin/python3.* 2>/dev/null` and substitute its absolute path for the `venv` command above. If NO 3.12 exists anywhere, STOP — this plan cannot run (every E2E task needs it).

- [ ] **Step 2: Confirm `.env` has a GLM key (venv activated)**

Run:
```bash
python -c "from dotenv import load_dotenv; load_dotenv(); import os; k=os.getenv('GLM_API_KEY'); print('GLM_API_KEY set' if k else 'MISSING'); print('base', os.getenv('GLM_API_BASE')); print('model', os.getenv('GLM_MODEL'))"
```
Expected: `GLM_API_KEY set`, `base https://open.bigmodel.cn/api/anthropic/`, `model glm-5.2`.

**Note:** All subsequent `Run:` commands assume the `.venv` is activated (`python` → 3.12). No commit for this task.

---

## Task 1: TransportRetryPolicy backoff fields

**Files:**
- Modify: `core_new/agent_roles.py:43-59` (`TransportRetryPolicy`)
- Test: `tests/test_backoff.py`

**Interfaces:**
- Produces: `TransportRetryPolicy.base: float = 2.0`, `TransportRetryPolicy.max_wait: float = 30.0` (consumed by Task 2).

- [ ] **Step 1: Write the failing test**

Create `tests/test_backoff.py`:
```python
"""Test: TransportRetryPolicy backoff fields + exponential _wait_with_backoff.
Run: python tests/test_backoff.py
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.agent_roles import TransportRetryPolicy
from core_new.llm_gateway import LLMGateway


def test_policy_has_backoff_fields():
    p = TransportRetryPolicy()
    assert p.base == 2.0, f"base default wrong: {p.base}"
    assert p.max_wait == 30.0, f"max_wait default wrong: {p.max_wait}"
    # frozen dataclass still allows constructing with overrides
    p2 = TransportRetryPolicy(base=1.5, max_wait=10.0)
    assert p2.base == 1.5 and p2.max_wait == 10.0


def main():
    test_policy_has_backoff_fields()
    print("PASS test_policy_has_backoff_fields")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_backoff.py`
Expected: FAIL — `AttributeError: 'TransportRetryPolicy' object has no attribute 'base'` (or AssertionError on `.base`).

- [ ] **Step 3: Implement — add the two fields**

In `core_new/agent_roles.py`, replace the `TransportRetryPolicy` dataclass:
```python
@dataclass(frozen=True)
class TransportRetryPolicy:
    max_attempts: int = 10
    backoff: str = "exponential_jitter"
    base: float = 2.0          # exponential base in seconds (NEW)
    max_wait: float = 30.0     # backoff cap in seconds (NEW)
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_backoff.py`
Expected: `PASS test_policy_has_backoff_fields`

- [ ] **Step 5: Commit**
```bash
git add core_new/agent_roles.py tests/test_backoff.py
git commit -m "feat(gateway): add base/max_wait backoff fields to TransportRetryPolicy"
```

---

## Task 2: Exponential backoff in `_wait_with_backoff`

**Files:**
- Modify: `core_new/llm_gateway.py:186-189` (`_wait_with_backoff`)
- Test: `tests/test_backoff.py` (append)

**Interfaces:**
- Consumes: `TransportRetryPolicy.base`, `.max_wait` (Task 1).
- Produces: `_wait_with_backoff` honors `base * 2^attempt + jitter`, capped at `max_wait`.

- [ ] **Step 1: Write the failing test (append to `tests/test_backoff.py`)**

Add inside the file, before `def main()`:
```python
def test_wait_with_backoff_is_exponential_capped():
    import core_new.llm_gateway as gw
    gw_mod = sys.modules["core_new.llm_gateway"]
    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)

    # Patch asyncio.sleep used inside the module, and random.uniform (deterministic jitter=0)
    orig_sleep = asyncio.sleep
    asyncio.sleep = fake_sleep
    import random
    orig_uniform = random.uniform
    random.uniform = lambda a, b: 0.0

    try:
        from core_new.agent_roles import TransportRetryPolicy as TP
        g = LLMGateway.__new__(LLMGateway)
        g._transport_retry = TP(base=2.0, max_wait=30.0)
        asyncio.run(g._wait_with_backoff(0))
        asyncio.run(g._wait_with_backoff(1))
        asyncio.run(g._wait_with_backoff(2))
        asyncio.run(g._wait_with_backoff(10))  # would be huge → capped
    finally:
        asyncio.sleep = orig_sleep
        random.uniform = orig_uniform

    assert sleeps[0] == 2.0, sleeps        # 2 * 2^0 + 0
    assert sleeps[1] == 4.0, sleeps        # 2 * 2^1 + 0
    assert sleeps[2] == 8.0, sleeps        # 2 * 2^2 + 0
    assert sleeps[3] == 30.0, sleeps       # capped at max_wait
```
And update `main()`:
```python
def main():
    test_policy_has_backoff_fields()
    print("PASS test_policy_has_backoff_fields")
    test_wait_with_backoff_is_exponential_capped()
    print("PASS test_wait_with_backoff_is_exponential_capped")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_backoff.py`
Expected: FAIL — `assert sleeps[0] == 2.0` fails because current impl always sleeps `3.0`.

- [ ] **Step 3: Implement — rewrite `_wait_with_backoff`**

In `core_new/llm_gateway.py` replace the method (lines 186-189):
```python
    async def _wait_with_backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter: base * 2^attempt + jitter, capped at max_wait."""
        policy = self._transport_retry
        delay = min(policy.base * (2 ** attempt) + random.uniform(0, 1), policy.max_wait)
        logger.info("Transport retry attempt %d, waiting %.1fs", attempt + 1, delay)
        await asyncio.sleep(delay)
```
(`random` and `asyncio` are already imported at the top of the module — verified.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_backoff.py`
Expected: both `PASS` lines.

- [ ] **Step 5: Commit**
```bash
git add core_new/llm_gateway.py tests/test_backoff.py
git commit -m "feat(gateway): exponential backoff with jitter in _wait_with_backoff"
```

---

## Task 3: `glm5.2` provider in config + `.env.example`

**Files:**
- Modify: `config.py:81-180` (add `glm5.2` to `GlobalSettings.providers`)
- Restore+Modify: `.env.example` (currently deleted in working tree)
- Test: `tests/test_factory_routing.py`

**Interfaces:**
- Produces: `get_provider_config("glm5.2")` → dict with `api_protocol="anthropic_messages"`, `api_url=https://open.bigmodel.cn/api/anthropic`, `model_path="glm-5.2"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_factory_routing.py`:
```python
"""Test: glm5.2 provider config + factory routing to AnthropicProvider.
Run: python tests/test_factory_routing.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_provider_config


def test_glm52_provider_config():
    cfg = get_provider_config("glm5.2")
    assert cfg["api_protocol"] == "anthropic_messages", cfg
    assert cfg["model_path"] == "glm-5.2", cfg
    assert "/api/anthropic" in cfg["api_url"], cfg
    assert cfg["thinking_control_method"] == "none", cfg
    assert cfg["supports_response_format"] is False, cfg


def main():
    test_glm52_provider_config()
    print("PASS test_glm52_provider_config")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_factory_routing.py`
Expected: FAIL — `ValueError: Provider 'glm5.2' not found in configuration.`

- [ ] **Step 3: Restore `.env.example` from HEAD, then update it**

Run:
```bash
git restore .env.example
```
Then in `.env.example`, replace the GLM block (the `# GLM 5.1 OpenAI-compatible API` section, lines ~27-35) with:
```
# GLM-5.2 via Anthropic Messages protocol (/api/anthropic)
# NOTE: glm5.1 (openai_chat / paas/v4) shares these vars and is therefore NOT
# usable while GLM_API_BASE points at the anthropic endpoint. glm5.1 provider
# definition is retained but effectively dead in this config.
GLM_API_BASE=https://open.bigmodel.cn/api/anthropic/
GLM_API_KEY=your_glm_api_key_here
GLM_MODEL=glm-5.2
GLM_BATCH_SIZE=4
GLM_THINKING_CONTROL_METHOD=none
GLM_SUPPORTS_RESPONSE_FORMAT=false
GLM_DEFAULT_MAX_TOKENS=20000
```

- [ ] **Step 4: Implement — add the `glm5.2` provider**

In `config.py`, inside `GlobalSettings.providers` (add right after the `"glm5.1": ProviderSettings(...)` block, before `"glm4flash"`):
```python
        "glm5.2": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("GLM_MODEL", "glm-5.2"),
            api_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/anthropic"),
            api_key=os.getenv("GLM_API_KEY"),
            api_protocol="anthropic_messages",   # routes to AnthropicProvider
            batch_size=int(os.getenv("GLM_BATCH_SIZE", "4")),
            request_timeout=float(os.getenv("GLM_REQUEST_TIMEOUT", "600")),
            max_retries=int(os.getenv("GLM_MAX_RETRIES", "0")),
            thinking_control_method=os.getenv("GLM_THINKING_CONTROL_METHOD", "none"),
            supports_response_format=False,      # anthropic protocol; OpenAI response_format N/A
            default_max_tokens=int(os.getenv("GLM_DEFAULT_MAX_TOKENS", "30000")),
            temperature=float(os.getenv("GLM_TEMPERATURE", "1.0")),
            top_p=float(os.getenv("GLM_TOP_P", "0.95")),
        ),
```

Also clear the stale `api_vllm` 32B default (spec §3.6). In the same `config.py`, change the `api_vllm` provider's `model_path` (~line 90) from:
```python
            model_path=os.getenv("VLLM_MODEL", os.path.join(MODELS_DIR, "Qwen3.6-27B-AWQ-INT4")),
```
to:
```python
            model_path=os.getenv("VLLM_MODEL", ""),
```
(This default is never resolved to a real model — no local vLLM exists — but spec §3.6 requires clearing it.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python tests/test_factory_routing.py`
Expected: `PASS test_glm52_provider_config`

- [ ] **Step 6: Commit**
```bash
git add config.py .env.example tests/test_factory_routing.py
git commit -m "feat(config): add glm5.2 anthropic_messages provider; refresh .env.example"
```

---

## Task 4: `AnthropicProvider`

**Files:**
- Create: `llm_providers_new/anthropic_provider.py`
- Test: `tests/test_anthropic_provider.py`

**Interfaces:**
- Consumes: `BaseLLMProvider` (from `.base`), `anthropic.AsyncAnthropic`.
- Produces: `AnthropicProvider(model_name, api_base_url, api_key="EMPTY", **kwargs)` with `.stream(params) -> {content, reasoning_content, tool_calls, finish_reason}`, `._prepare_messages(messages) -> (msgs, system)`, `._convert_tools(openai_tools) -> anthropic_tools`. `params` carries `thinking_intent={"enabled":bool, "effort":str|None, "budget":int|None}` and raw `messages`.

- [ ] **Step 1: Write the failing unit tests + E2E test**

Create `tests/test_anthropic_provider.py`:
```python
"""Test: AnthropicProvider message prep, tool conversion, and real GLM stream.
Run: python tests/test_anthropic_provider.py
"""
import asyncio, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from llm_providers_new.anthropic_provider import AnthropicProvider


def _make_provider():
    return AnthropicProvider(
        model_name=os.getenv("GLM_MODEL", "glm-5.2"),
        api_base_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/anthropic/"),
        api_key=os.environ["GLM_API_KEY"],
    )


def test_prepare_messages_separates_system():
    p = _make_provider()
    msgs, system = p._prepare_messages([
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "really brief"},
        {"role": "assistant", "content": "yo"},
    ])
    assert system == "be brief\n\nreally brief", system
    assert [m["role"] for m in msgs] == ["user", "assistant"], msgs


def test_prepare_messages_no_system():
    p = _make_provider()
    msgs, system = p._prepare_messages([{"role": "user", "content": "hi"}])
    assert system is None
    assert msgs == [{"role": "user", "content": "hi"}]


def test_convert_tools_openai_to_anthropic():
    p = _make_provider()
    out = p._convert_tools([{
        "type": "function",
        "function": {"name": "add", "description": "add nums", "parameters": {"type": "object", "properties": {"a": {"type": "number"}}}},
    }])
    assert out == [{
        "name": "add",
        "description": "add nums",
        "input_schema": {"type": "object", "properties": {"a": {"type": "number"}}},
    }], out


async def _stream_simple(p):
    params = {
        "model": p.model_name,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "max_tokens": 512,
        "thinking_intent": {"enabled": False},
    }
    return await p.stream(params)


async def _stream_thinking_with_tool(p):
    params = {
        "model": p.model_name,
        "messages": [{"role": "user", "content": "What is 7*6? Use the multiply tool."}],
        "max_tokens": 2048,
        "thinking_intent": {"enabled": True, "effort": "high"},
        "tools": [{
            "type": "function",
            "function": {"name": "multiply", "description": "multiply a*b", "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]}},
        }],
    }
    return await p.stream(params)


def test_stream_disabled_thinking_no_reasoning():
    p = _make_provider()
    res = asyncio.run(_stream_simple(p))
    assert "pong" in (res["content"] or "").lower(), res
    assert (res["reasoning_content"] or "") == "", res
    assert res["finish_reason"], res


def test_stream_enabled_thinking_has_reasoning_and_parses_tool():
    p = _make_provider()
    res = asyncio.run(_stream_thinking_with_tool(p))
    assert res["reasoning_content"], f"expected thinking tokens, got: {res}"
    # tool_use should be parsed into OpenAI shape (arguments is a JSON string)
    if res["tool_calls"]:
        tc = res["tool_calls"][0]
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "multiply", tc
        json.loads(tc["function"]["arguments"])  # must be valid JSON


def main():
    for name, fn in [
        ("test_prepare_messages_separates_system", test_prepare_messages_separates_system),
        ("test_prepare_messages_no_system", test_prepare_messages_no_system),
        ("test_convert_tools_openai_to_anthropic", test_convert_tools_openai_to_anthropic),
        ("test_stream_disabled_thinking_no_reasoning", test_stream_disabled_thinking_no_reasoning),
        ("test_stream_enabled_thinking_has_reasoning_and_parses_tool", test_stream_enabled_thinking_has_reasoning_and_parses_tool),
    ]:
        fn()
        print("PASS", name)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_anthropic_provider.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm_providers_new.anthropic_provider'`.

- [ ] **Step 3: Implement — create the provider**

Create `llm_providers_new/anthropic_provider.py`:
```python
# llm_providers_new/anthropic_provider.py
"""GLM anthropic endpoint provider (Anthropic Messages protocol).

Thinking control: thinking.type (on/off) + reasoning_effort (GLM extension via extra_body).
Message preparation and thinking-field translation live HERE (gateway is protocol-agnostic).
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import httpx

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """GLM /api/anthropic provider implementing BaseLLMProvider + stream()."""

    def __init__(self, model_name: str, api_base_url: str, api_key: str = "EMPTY", **kwargs):
        self.model_name = model_name
        self.provider_type = "api"
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.request_timeout = float(kwargs.get("request_timeout", 300.0))
        self.max_retries = int(kwargs.get("max_retries", 2))
        self.thinking_control_method = kwargs.get("thinking_control_method", "none")
        self.supports_response_format = False
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
        # GLM's anthropic endpoint: SDK appends /v1/messages to base_url.
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.request_timeout,
            max_retries=self.max_retries,
            http_client=self.http_client,
        )
        logger.info("AnthropicProvider initialized: model=%s base_url=%s", model_name, self.api_base_url)

    def _prepare_messages(self, messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """OpenAI-style messages -> (anthropic messages, system). anthropic requires system separate."""
        system_parts: List[str] = []
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                converted.append({"role": role, "content": content})
        return converted, ("\n\n".join(system_parts) if system_parts else None)

    def _convert_tools(self, openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for tool in openai_tools:
            fn = tool.get("function", tool)
            out.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def _thinking_kwargs(self, intent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Translate neutral thinking_intent -> anthropic request kwargs.

        Default enabled shape is bare {"type": "enabled"} — exactly what 附录 A test 3
        verified (~173 thinking tokens at effort=high). budget_tokens is ONLY added when
        the caller explicitly passes a budget; the SDK does not runtime-enforce it
        (ThinkingConfigEnabledParam.budget_tokens is Required for typecheck only), and
        GLM's anthropic-compatible endpoint accepts bare enabled.
        """
        kw: Dict[str, Any] = {}
        if not intent:
            return kw
        if intent.get("enabled"):
            thinking: Dict[str, Any] = {"type": "enabled"}
            if intent.get("budget") is not None:
                thinking["budget_tokens"] = max(1024, int(intent["budget"]))
            kw["thinking"] = thinking
            if intent.get("effort"):
                kw["extra_body"] = {"reasoning_effort": intent["effort"]}
        else:
            kw["thinking"] = {"type": "disabled"}
        return kw

    async def stream(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unified stream interface. params has: model, messages, max_tokens?, temperature?,
        thinking_intent?, tools?, stream?. Returns {content, reasoning_content, tool_calls, finish_reason}.

        Streaming only: the gateway always passes stream=True, so non-stream is out of
        scope (the gateway is the sole consumer). A `stream` key in params is ignored,
        never forwarded to messages.stream().
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
        kwargs.update(self._thinking_kwargs(params.get("thinking_intent")))
        if params.get("tools"):
            kwargs["tools"] = self._convert_tools(params["tools"])
        return await self._read_stream(kwargs)

    async def _read_stream(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Run messages.stream() and reduce the final message to the unified shape."""
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        finish_reason: Optional[str] = None
        async with self.client.messages.stream(**kwargs) as s:
            final = await s.get_final_message()
        finish_reason = final.stop_reason
        for block in final.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                content_parts.append(getattr(block, "text", ""))
            elif btype == "thinking":
                reasoning_parts.append(getattr(block, "thinking", ""))
            elif btype == "tool_use":
                tool_calls.append({
                    "id": getattr(block, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(block, "name", ""),
                        "arguments": json.dumps(getattr(block, "input", {})),
                    },
                })
        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls or None,
            "finish_reason": finish_reason,
        }

    # BaseLLMProvider batch interface — not supported (batch annotation uses remote_api)
    async def generate_with_think_and_parse_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider does not support batch; use remote_api")

    async def generate_json_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider does not support batch; use remote_api")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_anthropic_provider.py`
Expected: all five `PASS` lines. (The two stream tests make real GLM-5.2 calls — they need the key in `.env` and network.)

**Note on thinking shape:** `_thinking_kwargs` sends bare `thinking={"type":"enabled"}` + `extra_body={"reasoning_effort":...}` — exactly the 附录 A test 3 payload that produced ~173 tokens. `budget_tokens` is NOT sent unless a budget is explicitly passed (the gateway never passes one for glm5.2, since `_supports_thinking_budget` is False for remote providers). If the test still fails, double-check `.env` (`GLM_API_BASE`/`GLM_MODEL`) and the streamed kwargs via a `logger.debug`.

- [ ] **Step 5: Commit**
```bash
git add llm_providers_new/anthropic_provider.py tests/test_anthropic_provider.py
git commit -m "feat(provider): AnthropicProvider for GLM /api/anthropic with stream()"
```

---

## Task 5: Factory routing `anthropic_messages` → `AnthropicProvider`

**Files:**
- Modify: `llm_providers_new/__init__.py:38-55` (the `provider_type == "api"` arm)
- Test: `tests/test_factory_routing.py` (append)

**Interfaces:**
- Consumes: `AnthropicProvider` (Task 4), `glm5.2` config (Task 3).
- Produces: `get_llm_provider(get_provider_config("glm5.2"))` returns an `AnthropicProvider`.

- [ ] **Step 1: Write the failing test (append)**

Add to `tests/test_factory_routing.py`:
```python
def test_factory_routes_glm52_to_anthropic():
    from llm_providers_new import get_llm_provider
    from llm_providers_new.anthropic_provider import AnthropicProvider
    cfg = get_provider_config("glm5.2")
    prov = get_llm_provider(cfg)
    assert isinstance(prov, AnthropicProvider), type(prov)
    assert prov.api_base_url.rstrip("/").endswith("/api/anthropic"), prov.api_base_url
```
And extend `main()`:
```python
def main():
    test_glm52_provider_config()
    print("PASS test_glm52_provider_config")
    test_factory_routes_glm52_to_anthropic()
    print("PASS test_factory_routes_glm52_to_anthropic")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_factory_routing.py`
Expected: FAIL — `isinstance(prov, AnthropicProvider)` is False (factory still returns `RemoteAPIProvider`).

- [ ] **Step 3: Implement — add the protocol branch**

In `llm_providers_new/__init__.py`, replace the `if provider_type == "api":` block:
```python
    if provider_type == "api":
        model_name = config.get("model_path")
        api_url = config.get("api_url")
        api_key = config.get("api_key", "EMPTY")

        if not model_name or not api_url:
            raise ValueError("API provider config must include 'model_path' and 'api_url'.")

        provider_kwargs = {
            k: v for k, v in config.items()
            if k not in {"provider_type", "model_path", "api_url", "api_key"}
        }

        # Protocol routing: anthropic_messages -> AnthropicProvider, else OpenAI-compatible.
        if config.get("api_protocol") == "anthropic_messages":
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                model_name=model_name,
                api_base_url=api_url,
                api_key=api_key,
                **provider_kwargs,
            )

        return RemoteAPIProvider(
            model_name=model_name,
            api_base_url=api_url,
            api_key=api_key,
            **provider_kwargs,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_factory_routing.py`
Expected: both `PASS` lines.

- [ ] **Step 5: Commit**
```bash
git add llm_providers_new/__init__.py tests/test_factory_routing.py
git commit -m "feat(factory): route anthropic_messages protocol to AnthropicProvider"
```

---

## Task 6: `RemoteAPIProvider.stream()`

**Files:**
- Modify: `llm_providers_new/remote_api.py` (add `stream()` method on `RemoteAPIProvider`)
- Test: `tests/test_remote_api_stream.py`

**Interfaces:**
- Consumes: existing `_prepare_messages`, `_extra_body_for_thinking`, `self.client`, `self.sampling_params`.
- Produces: `RemoteAPIProvider.stream(params) -> {content, reasoning_content, tool_calls, finish_reason}`. `params` carries `thinking_intent`, raw `messages`, `model`, optional `max_tokens/temperature/tools/tool_choice/response_format`.

- [ ] **Step 1: Write the failing test (E2E via glm4flash — live OpenAI-compatible endpoint)**

Create `tests/test_remote_api_stream.py`:
```python
"""Test: RemoteAPIProvider.stream() parses an OpenAI-compatible stream.
Uses glm4flash on paas/v4 (live). Run: python tests/test_remote_api_stream.py
"""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from config import get_provider_config
from llm_providers_new import get_llm_provider


def _make_provider():
    # glm4flash = openai_chat on paas/v4; reachable with GLM_API_KEY.
    cfg = get_provider_config("glm4flash")
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ["GLM_API_KEY"]
    return get_llm_provider(cfg)


def test_stream_returns_content_and_finish_reason():
    p = _make_provider()
    params = {
        "model": p.model_name,
        "messages": [{"role": "user", "content": "Reply with exactly: hello"}],
        "max_tokens": 256,
        "thinking_intent": {"enabled": False},
        "stream": True,
    }
    res = asyncio.run(p.stream(params))
    assert "hello" in (res["content"] or "").lower(), res
    assert res["finish_reason"], res
    assert res["tool_calls"] is None, res


def main():
    test_stream_returns_content_and_finish_reason()
    print("PASS test_stream_returns_content_and_finish_reason")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_remote_api_stream.py`
Expected: FAIL — `AttributeError: 'RemoteAPIProvider' object has no attribute 'stream'`.

- [ ] **Step 3: Implement — add `stream()` to `RemoteAPIProvider`**

In `llm_providers_new/remote_api.py`, add this method to the `RemoteAPIProvider` class (e.g. right after `_chat_call`, ~line 244):
```python
    async def stream(self, params):
        """Unified stream interface for the gateway.

        Owns message preparation + thinking translation (gateway no longer preps).
        params: model, messages, max_tokens?, temperature?, thinking_intent?, tools?,
                tool_choice?, response_format?, stream?
        Returns {content, reasoning_content, tool_calls, finish_reason}.
        """
        ti = params.get("thinking_intent") or {}
        enable_thinking = ti.get("enabled", True)
        json_mode = bool(params.get("response_format"))
        processed = self._prepare_messages(
            params["messages"], enable_thinking=enable_thinking, json_mode=json_mode
        )

        sampling = {k: v for k, v in self.sampling_params.items() if k != "top_k"}
        for k in ("temperature", "top_p", "max_tokens"):
            if k in params:
                sampling[k] = params[k]

        req = {"model": params["model"], "messages": processed, "stream": True, **sampling}
        if params.get("max_tokens"):
            req["max_tokens"] = params["max_tokens"]
        if params.get("tools"):
            req["tools"] = params["tools"]
        if params.get("tool_choice") and params.get("tools"):
            req["tool_choice"] = params["tool_choice"]
        if json_mode and self.supports_response_format:
            req["response_format"] = params["response_format"]
        extra_body = dict(params.get("extra_body") or {})  # carry thinking_token_budget etc. from gateway
        eb = self._extra_body_for_thinking(enable_thinking)
        if eb:
            extra_body.update(eb)
        if extra_body:
            req["extra_body"] = extra_body

        content_parts, reasoning_parts = [], []
        tool_calls_accum: Dict[int, Dict[str, str]] = {}
        finish_reason = None

        chunk_stream = await self.client.chat.completions.create(**req)
        async for chunk in chunk_stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            if delta.content:
                content_parts.append(delta.content)
            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
            if reasoning:
                reasoning_parts.append(reasoning)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_accum[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_accum[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_accum[idx]["arguments"] += tc.function.arguments

        tool_calls = None
        if tool_calls_accum:
            tool_calls = [
                {"id": v["id"], "type": "function",
                 "function": {"name": v["name"], "arguments": v["arguments"]}}
                for _, v in sorted(tool_calls_accum.items())
            ]
        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_remote_api_stream.py`
Expected: `PASS test_stream_returns_content_and_finish_reason`.

- [ ] **Step 5: Commit**
```bash
git add llm_providers_new/remote_api.py tests/test_remote_api_stream.py
git commit -m "feat(provider): RemoteAPIProvider.stream() unified OpenAI streaming interface"
```

---

## Task 7: Gateway refactor — neutral `thinking_intent` + `provider.stream()`

**Files:**
- Modify: `core_new/llm_gateway.py`:
  - `stream_chat` (line 440): add `thinking_effort` param + thread it through.
  - `_build_chat_params` (line 490): emit neutral `thinking_intent`; stop calling `provider._prepare_messages` and `provider._extra_body_for_thinking`.
  - `_read_chat_stream` (line 548): delegate to `provider.stream(params)`.
- Test: `tests/test_gateway_thinking.py`

**Interfaces:**
- Consumes: `provider.stream(params)` from Tasks 4 & 6; `glm5.2` config (Task 3).
- Produces: `gateway.stream_chat(..., thinking_effort="high")`; gateway is protocol-agnostic.

- [ ] **Step 1: Write the failing test (E2E test 2)**

Create `tests/test_gateway_thinking.py`:
```python
"""Test: gateway stream_chat with neutral thinking_intent through glm5.2 (anthropic).
Confirms thinking on (effort=high) yields reasoning; off yields none.
Run: python tests/test_gateway_thinking.py
"""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from core_new.llm_gateway import get_gateway


async def _call(thinking_effort, enable_thinking):
    gw = get_gateway("glm5.2")
    return await gw.stream_chat(
        messages=[{"role": "user", "content": "What is 15 + 27? Think briefly then answer."}],
        max_tokens=2048,
        enable_thinking=enable_thinking,
        thinking_effort=thinking_effort,
    )


def test_thinking_on_vs_off_differ():
    on = asyncio.run(_call(thinking_effort="high", enable_thinking=True))
    off = asyncio.run(_call(thinking_effort=None, enable_thinking=False))

    assert on["content"], on
    assert (on["reasoning_content"] or "") != "", "effort=high should produce thinking tokens"
    assert (off["reasoning_content"] or "") == "", "disabled should produce no thinking"
    # unified shape intact
    for k in ("content", "reasoning_content", "tool_calls", "finish_reason"):
        assert k in on, on


async def _call_openai():
    # glm4flash = openai_chat on paas/v4 (live). Confirms the refactored gateway still
    # drives RemoteAPIProvider.stream() end-to-end, not just the anthropic provider.
    gw = get_gateway("glm4flash")
    return await gw.stream_chat(
        messages=[{"role": "user", "content": "Reply with exactly: ok"}],
        max_tokens=256,
        enable_thinking=False,
    )


def test_gateway_openai_path_still_works():
    res = asyncio.run(_call_openai())
    assert "ok" in (res["content"] or "").lower(), res
    assert res["finish_reason"], res


def main():
    test_thinking_on_vs_off_differ()
    print("PASS test_thinking_on_vs_off_differ")
    test_gateway_openai_path_still_works()
    print("PASS test_gateway_openai_path_still_works")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_gateway_thinking.py`
Expected: FAIL — `TypeError: stream_chat() got an unexpected keyword argument 'thinking_effort'`.

- [ ] **Step 3: Implement — refactor the three methods**

**3a.** In `stream_chat` (line 440), add the parameter and pass it through. Replace the signature + the `_build_chat_params` call:
```python
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        thinking_effort: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        sampling_overrides: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Run one streaming chat request through the shared gateway policy."""
        provider = self._provider
        max_tokens = self._floor_max_tokens(max_tokens, bool(enable_thinking))
        params = self._build_chat_params(
            provider,
            messages,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            thinking_effort=thinking_effort,
            tools=tools,
            tool_choice=tool_choice,
            sampling_overrides=sampling_overrides,
            json_mode=json_mode,
            stream=True,
        )

        last_exc: Exception | None = None
        attempts = max(1, self._transport_retry.max_attempts)
        for attempt in range(attempts):
            async with self._get_sem():
                try:
                    return await self._read_chat_stream(provider, params)
                except Exception as exc:
                    if not self._is_retryable_stream_error(exc) or attempt >= attempts - 1:
                        raise
                    last_exc = exc

            await self._wait_with_backoff(attempt)

        raise last_exc or RuntimeError("stream_chat failed without an exception")
```

**3b.** Replace `_build_chat_params` (line 490) entirely:
```python
    def _build_chat_params(
        self,
        provider,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int],
        enable_thinking: Optional[bool],
        thinking_budget: Optional[int],
        thinking_effort: Optional[str],
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Any],
        sampling_overrides: Optional[Dict[str, Any]],
        json_mode: bool,
        stream: bool,
    ) -> Dict[str, Any]:
        # Message preparation is now the provider's job (provider.stream()).
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

        # effort and budget are mutually exclusive (spec §3.3 contract) — guard it.
        assert not (thinking_effort and thinking_budget), \
            "thinking_effort and thinking_budget are mutually exclusive"

        # Neutral thinking intent — provider.stream() translates per protocol.
        if enable_thinking is True and thinking_effort:
            params["thinking_intent"] = {"enabled": True, "effort": thinking_effort}
        elif enable_thinking is True:
            params["thinking_intent"] = {"enabled": True}
        elif enable_thinking is False:
            params["thinking_intent"] = {"enabled": False}

        # Local vLLM thinking-budget path — PRESERVE existing behavior verbatim
        # (spec §7: "不做 thinking_budget 的自动膨胀 max_tokens 逻辑调整（现有逻辑保留）").
        # Emit the OpenAI extra_body field AND inflate max_tokens so reasoning tokens
        # don't consume the output budget. RemoteAPIProvider.stream() must MERGE this
        # extra_body (see T6), not overwrite it.
        if thinking_budget and self._supports_thinking_budget(provider):
            params["thinking_intent"] = {"enabled": True, "budget": thinking_budget}
            params.setdefault("extra_body", {})["thinking_token_budget"] = thinking_budget
            current_max = params.get("max_tokens", 0)
            if current_max and current_max > 0:
                params["max_tokens"] = max(current_max, thinking_budget + 16000)

        return params
```

**3c.** Replace `_read_chat_stream` (line 548) with delegation:
```python
    async def _read_chat_stream(self, provider, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate stream parsing to the provider (protocol-agnostic)."""
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
            len(result.get("content") or ""),
            len(result.get("reasoning_content") or ""),
            len(result.get("tool_calls") or []),
            result.get("finish_reason"),
        )
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_gateway_thinking.py`
Expected: `PASS test_thinking_on_vs_off_differ` (real GLM-5.2 calls).

- [ ] **Step 5: Re-run the full gateway regression to ensure the OpenAI path still works**

Run: `python tests/test_gateway_thinking.py && python tests/test_remote_api_stream.py && python tests/test_anthropic_provider.py`
Expected: all pass — `test_gateway_thinking.py` now drives BOTH protocols through the refactored gateway (glm5.2 anthropic + glm4flash openai), `test_remote_api_stream.py` covers the provider directly.

- [ ] **Step 6: Commit**
```bash
git add core_new/llm_gateway.py tests/test_gateway_thinking.py
git commit -m "refactor(gateway): neutral thinking_intent + delegate stream to provider.stream()"
```

---

## Task 8: Anthropic error classification

**Files:**
- Modify: `core_new/llm_gateway.py`:
  - `_is_retryable_stream_error` (line 648): add anthropic exception branch.
  - `_classify_exception` (line 994): add anthropic branch.
- Test: `tests/test_error_classification.py`

**Interfaces:** none new (internal helpers).

- [ ] **Step 1: Write the failing test**

Create `tests/test_error_classification.py`:
```python
"""Test: anthropic SDK exceptions classify correctly.
Run: python tests/test_error_classification.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from core_new.llm_gateway import _classify_exception, LLMGateway


def test_classify_anthropic():
    import httpx
    req = httpx.Request("GET", "https://x")
    assert _classify_exception(anthropic.APITimeoutError(request=req)) == "timeout"
    assert _classify_exception(anthropic.RateLimitError("e", response=httpx.Response(429, request=req), body=None)) == "rate_limit"
    assert _classify_exception(anthropic.InternalServerError("e", response=httpx.Response(500, request=req), body=None)) == "server_error"


def test_is_retryable_anthropic():
    import httpx
    req = httpx.Request("GET", "https://x")
    assert LLMGateway._is_retryable_stream_error(anthropic.APIConnectionError(request=req)) is True
    assert LLMGateway._is_retryable_stream_error(
        anthropic.InternalServerError("e", response=httpx.Response(500, request=req), body=None)
    ) is True


def main():
    test_classify_anthropic()
    print("PASS test_classify_anthropic")
    test_is_retryable_anthropic()
    print("PASS test_is_retryable_anthropic")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_error_classification.py`
Expected: FAIL on the `RateLimitError` and `InternalServerError` assertions — pre-impl they fall through to the `str()`-heuristic (`llm_gateway.py` ~line 1029) and return `"api_error"`, not `"rate_limit"`/`"server_error"`. (The `APITimeoutError` assertion already passes pre-impl because its message contains "timed out" — that's expected; the test still goes red→green via the other two assertions.)

- [ ] **Step 3: Implement — add anthropic branches**

**3a.** In `_is_retryable_stream_error` (line 648), insert at the very top of the method body (before the openai block):
```python
    @staticmethod
    def _is_retryable_stream_error(exc: Exception) -> bool:
        # anthropic SDK (lazy; ignored if not installed)
        try:
            import anthropic
            if isinstance(exc, (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
                anthropic.InternalServerError,
            )):
                return True
        except ImportError:
            pass
        # OpenAI SDK exceptions (APITimeoutError inherits APIConnectionError, order matters)
        if isinstance(exc, (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        )):
            return True
        # ... rest unchanged (httpx / status_code / name heuristics) ...
```
(Leave the existing httpx/status_code/name-matching tail exactly as-is.)

**3b.** In `_classify_exception` (line 994), insert an anthropic branch near the top (after the function signature/docstring, before the openai handling):
```python
def _classify_exception(error: Exception) -> str:
    # anthropic SDK (lazy)
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
            status = getattr(error, "status_code", None)
            if status == 429:
                return "rate_limit"
            if status in {408, 425}:
                return "timeout"
            if status is not None and status >= 500:
                return "server_error"
            return "api_error"
    except ImportError:
        pass
    # ... existing openai/httpx classification unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_error_classification.py`
Expected: both `PASS` lines.

- [ ] **Step 5: Commit**
```bash
git add core_new/llm_gateway.py tests/test_error_classification.py
git commit -m "feat(gateway): classify anthropic SDK exceptions for retry/routing"
```

---

## Task 9: `agent_router` + `config/agents_llm.yaml`

**Files:**
- Create: `core_new/agent_router.py`
- Create: `config/agents_llm.yaml`
- Test: `tests/test_agent_router.py`

**Interfaces:**
- Consumes: `get_gateway` (`core_new.llm_gateway`), `glm5.2` provider (Task 3).
- Produces: `get_gateway_for(agent_name) -> LLMGateway`, `get_thinking_config(agent_name) -> dict` (e.g. `{"enabled": bool, "effort": str}`).

- [ ] **Step 1: Write the failing test (test 3)**

Create `tests/test_agent_router.py`:
```python
"""Test: agent_router maps agent names to gateway + thinking config.
Run: python tests/test_agent_router.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.agent_router import get_gateway_for, get_thinking_config


def test_write_gen_disabled_design_default_high():
    assert get_thinking_config("write_gen") == {"enabled": False}, get_thinking_config("write_gen")
    tc = get_thinking_config("design_direct")
    assert tc.get("enabled") is True and tc.get("effort") == "high", tc


def test_gateway_for_returns_glm52_and_caches():
    g1 = get_gateway_for("write_gen")
    g2 = get_gateway_for("write_gen")
    assert g1._provider_name == "glm5.2", g1._provider_name
    assert g1 is g2, "lru_cache should return the same gateway instance"


def test_cross_agent_shares_gateway_for_same_provider():
    # design_direct and write_solution both -> glm5.2: ONE shared gateway instance
    a = get_gateway_for("design_direct")
    b = get_gateway_for("write_solution")
    assert a is b, "agents on the same provider must share one gateway (spec §3.4 dedup)"


def test_unknown_agent_falls_back_to_default():
    tc = get_thinking_config("does_not_exist")
    assert tc.get("enabled") is True and tc.get("effort") == "high", tc


def main():
    test_write_gen_disabled_design_default_high()
    print("PASS test_write_gen_disabled_design_default_high")
    test_gateway_for_returns_glm52_and_caches()
    print("PASS test_gateway_for_returns_glm52_and_caches")
    test_cross_agent_shares_gateway_for_same_provider()
    print("PASS test_cross_agent_shares_gateway_for_same_provider")
    test_unknown_agent_falls_back_to_default()
    print("PASS test_unknown_agent_falls_back_to_default")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_agent_router.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'core_new.agent_router'`.

- [ ] **Step 3: Implement — create the YAML config**

Create `config/agents_llm.yaml`:
```yaml
# config/agents_llm.yaml
# agent name -> provider + thinking config. provider must exist in config.py.
default: &default
  provider: glm5.2
  thinking:
    enabled: true
    effort: high        # "keep basic thinking, not deep" (observed ~173 tokens)

agents:
  design_direct:
    <<: *default        # high — sets the stem/structure
  write_gen:
    provider: glm5.2
    thinking:
      enabled: false    # writing complex algorithm code; verify via exec, no thinking
  write_solution:
    <<: *default        # high — tidy the output
  dual_review:
    <<: *default        # high — auditing
```

- [ ] **Step 4: Implement — create `agent_router.py`**

Create `core_new/agent_router.py`:
```python
# core_new/agent_router.py
"""Agent name -> LLMGateway router (thin layer).

Reads config/agents_llm.yaml. Per-agent thinking config is returned separately;
callers pass it into gateway.stream_chat(thinking_effort=...). This is the
canonical router for the agent pipeline going forward; provider_router.py
(role -> local/remote acceleration) is retained for legacy/experiments — there
is no local model in the current environment, so this layer routes to glm5.2
directly.
"""
from functools import lru_cache
from pathlib import Path

import yaml

from core_new.llm_gateway import get_gateway

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "agents_llm.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _agent_cfg(agent_name: str) -> dict:
    cfg = _load_config()
    return cfg.get("agents", {}).get(agent_name, cfg.get("default", {}))


@lru_cache(maxsize=None)
def _gateway_for_provider(provider_name: str):
    """Single provider -> gateway cache (shared across all agents on that provider)."""
    return get_gateway(provider_name)


def get_gateway_for(agent_name: str):
    """Return the gateway bound to this agent's provider.

    Cached per PROVIDER name (not per agent), so all agents bound to the same provider
    (e.g. every agent on glm5.2) share one gateway/connection pool — per spec §3.4's
    cache-dedup requirement.
    """
    provider_name = _agent_cfg(agent_name)["provider"]
    return _gateway_for_provider(provider_name)


def get_thinking_config(agent_name: str) -> dict:
    """Return this agent's thinking config, e.g. {"enabled": bool, "effort": str}."""
    return _agent_cfg(agent_name).get("thinking", {})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python tests/test_agent_router.py`
Expected: all three `PASS` lines.

- [ ] **Step 6: Commit**
```bash
git add core_new/agent_router.py config/agents_llm.yaml tests/test_agent_router.py
git commit -m "feat(router): agent_router + agents_llm.yaml for per-agent provider/thinking"
```

---

## Task 10: Integration verification

**Files:** none (verification + optional manual spec test 1)

- [ ] **Step 1: Run the entire new test suite**

Run:
```bash
for t in test_backoff test_factory_routing test_anthropic_provider test_remote_api_stream test_gateway_thinking test_error_classification test_agent_router; do
  echo "=== $t ==="; python tests/$t.py || { echo "FAILED: $t"; break; }
done
```
Expected: every file prints its `PASS` lines and exits 0.

- [ ] **Step 2: Run the pre-existing suite to confirm no regression**

Run:
```bash
python tests/test_glm5_review_fix.py 2>&1 | tail -5
```
Expected: runs without import/attribute errors from the gateway refactor. (It uses `get_gateway` + batch methods, which are untouched. If it requires a now-dead `glm5.1`, note it but it is pre-existing — glm5.1 is dead by design this round.)

- [ ] **Step 3: Manual spec test 1 (backoff timing) — optional but recommended**

Temporary bad URL, observe exponential waits in logs:
```bash
GLM_API_BASE=https://open.bigmodel.cn/api/anthropic-definitely-bad/ python -c "
import asyncio
from core_new.llm_gateway import get_gateway
async def main():
    gw = get_gateway('glm5.2')
    try:
        await gw.stream_chat([{'role':'user','content':'hi'}], max_tokens=16, enable_thinking=False)
    except Exception as e:
        print('final error:', type(e).__name__)
asyncio.run(main())
" 2>&1 | grep -E "waiting|error"
```
Expected: log lines `waiting 2.x s`, `waiting 4.x s`, `waiting 8.x s` … before the final connection error. (Confirms exponential backoff under real transport failure.)

- [ ] **Step 4: Final commit (if any scratch fixups) + summary**
```bash
git status --short
```
Expected: clean tree (all changes committed across Tasks 1–9). No final commit needed unless Step 2/3 surfaced a fix.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §3.2 exponential backoff → T1, T2 ✓
- §3.3 `thinking_effort` + neutral intent + `_read_chat_stream`→`provider.stream()` → T7 ✓
- §3.4 `agent_router` + provider_router positioning → T9 (positioning in module docstring) ✓
- §3.5 `AnthropicProvider` → T4 ✓
- §3.6 `glm5.2` config + `.env.example` → T3 ✓
- §4 anthropic error classification → T8 ✓
- §5 tests 1–4 → T10 (test1), T7 (test2), T9 (test3), T4 (test4) ✓
- §6 file list → all 13 source files covered (pyproject intentionally unchanged) ✓

**2. Placeholder scan** — every code step shows complete code; no TBD/TODO/"add error handling". The one conditional instruction (T4 Step 4 budget_tokens fallback) gives the exact code change to make if the E2E test fails.

**3. Type consistency** — `thinking_intent` shape `{"enabled": bool, "effort"?: str, "budget"?: int}` is identical across `_build_chat_params` (T7), `AnthropicProvider._thinking_kwargs` (T4), and `RemoteAPIProvider.stream` (T6). `provider.stream(params)` return shape `{content, reasoning_content, tool_calls, finish_reason}` is identical across both providers and matches the gateway's consumer (`_read_chat_stream` in T7). `AnthropicProvider.__init__(model_name, api_base_url, api_key="EMPTY", **kwargs)` matches the factory's call site (T5) and mirrors `RemoteAPIProvider.__init__`. `get_gateway_for` / `get_thinking_config` signatures match the T9 test and the §3.4 usage example.

---
