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


def test_factory_routes_glm52_to_anthropic():
    from llm_providers_new import get_llm_provider
    from llm_providers_new.anthropic_provider import AnthropicProvider
    cfg = get_provider_config("glm5.2")
    prov = get_llm_provider(cfg)
    assert isinstance(prov, AnthropicProvider), type(prov)
    assert prov.api_base_url.rstrip("/").endswith("/api/anthropic"), prov.api_base_url


def main():
    test_glm52_provider_config()
    print("PASS test_glm52_provider_config")
    test_factory_routes_glm52_to_anthropic()
    print("PASS test_factory_routes_glm52_to_anthropic")


if __name__ == "__main__":
    main()
