"""Test: RemoteAPIProvider.stream() reduces an OpenAI-compatible stream to the
unified {content, reasoning_content, tool_calls, finish_reason} shape.

Fake-based (no live endpoint) — glm4flash was removed from the config, so we feed
the provider a fake OpenAI streaming client. Run: python tests/test_remote_api_stream.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_providers_new.remote_api import RemoteAPIProvider


def _chunk(content=None, reasoning=None, finish_reason=None, tool_calls=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)])


class _FakeStream:
    """Async-iterable of OpenAI-style chunks."""
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        c = self._chunks[self._i]
        self._i += 1
        return c


def _make_provider():
    p = RemoteAPIProvider(
        model_name="fake-openai",
        api_base_url="http://example.invalid/v1",
        api_key="EMPTY",
        api_protocol="openai_chat",
        thinking_control_method="none",
        supports_response_format=True,
    )
    p._fake_chunks = []

    async def fake_create(**kwargs):
        return _FakeStream(p._fake_chunks)

    # Replace the real AsyncOpenAI client with a fake (no network).
    p.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
    return p


async def _stream(p, chunks, **params):
    p._fake_chunks = chunks
    base = {
        "model": p.model_name,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 16,
        "thinking_intent": {"enabled": False},
        "stream": True,
    }
    base.update(params)
    return await p.stream(base)


def test_stream_reduces_content_and_finish_reason():
    p = _make_provider()
    res = asyncio.run(_stream(p, [
        _chunk(content="hel"),
        _chunk(content="lo"),
        _chunk(finish_reason="stop"),
    ]))
    assert res["content"] == "hello", res
    assert res["finish_reason"] == "stop", res
    assert res["reasoning_content"] == "", res
    assert res["tool_calls"] is None, res


def test_stream_reduces_reasoning_and_tool_calls():
    p = _make_provider()
    tc = SimpleNamespace(index=0, id="call_1", function=SimpleNamespace(name="add", arguments='{"a": 1}'))
    res = asyncio.run(_stream(p, [
        _chunk(reasoning="thinking..."),
        _chunk(content="done", finish_reason="tool_use", tool_calls=[tc]),
    ]))
    assert res["reasoning_content"] == "thinking...", res
    assert res["content"] == "done", res
    assert res["tool_calls"] is not None and len(res["tool_calls"]) == 1, res
    assert res["tool_calls"][0]["id"] == "call_1", res
    assert res["tool_calls"][0]["type"] == "function", res
    assert res["tool_calls"][0]["function"]["name"] == "add", res
    assert res["tool_calls"][0]["function"]["arguments"] == '{"a": 1}', res


def main():
    test_stream_reduces_content_and_finish_reason()
    print("PASS test_stream_reduces_content_and_finish_reason")
    test_stream_reduces_reasoning_and_tool_calls()
    print("PASS test_stream_reduces_reasoning_and_tool_calls")


if __name__ == "__main__":
    main()
