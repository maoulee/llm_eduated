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
