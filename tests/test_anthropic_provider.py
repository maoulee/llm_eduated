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
