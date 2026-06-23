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


def main():
    test_policy_has_backoff_fields()
    print("PASS test_policy_has_backoff_fields")
    test_wait_with_backoff_is_exponential_capped()
    print("PASS test_wait_with_backoff_is_exponential_capped")


if __name__ == "__main__":
    main()
