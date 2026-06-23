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


def main():
    test_glm52_provider_config()
    print("PASS test_glm52_provider_config")


if __name__ == "__main__":
    main()
