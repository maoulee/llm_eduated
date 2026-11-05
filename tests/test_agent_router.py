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
