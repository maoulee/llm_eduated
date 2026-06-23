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
