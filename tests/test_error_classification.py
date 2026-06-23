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
