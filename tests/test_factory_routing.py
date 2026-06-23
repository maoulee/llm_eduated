"""Test: glm5.2 provider config (single-protocol openai_chat at coding/paas/v4).
Run: python tests/test_factory_routing.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_provider_config


def test_glm52_provider_config():
    cfg = get_provider_config("glm5.2")
    assert cfg["api_protocol"] == "openai_chat", cfg
    assert cfg["model_path"] == "glm-5.2", cfg
    assert "/api/coding/paas/v4" in cfg["api_url"], cfg
    assert cfg["thinking_control_method"] == "reasoning_effort", cfg
    assert cfg.get("reasoning_effort") == "high", cfg


def test_factory_routes_glm52_to_remote():
    from llm_providers_new import get_llm_provider
    from llm_providers_new.remote_api import RemoteAPIProvider
    cfg = get_provider_config("glm5.2")
    prov = get_llm_provider(cfg)
    assert isinstance(prov, RemoteAPIProvider), type(prov)
    assert "coding/paas/v4" in prov.api_base_url, prov.api_base_url
    assert prov.thinking_control_method == "reasoning_effort"
    assert prov.reasoning_effort == "high"


def main():
    test_glm52_provider_config()
    print("PASS test_glm52_provider_config")
    test_factory_routes_glm52_to_remote()
    print("PASS test_factory_routes_glm52_to_remote")


if __name__ == "__main__":
    main()
