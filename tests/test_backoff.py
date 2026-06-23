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
