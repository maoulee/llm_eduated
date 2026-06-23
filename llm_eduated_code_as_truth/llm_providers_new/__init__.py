# llm_providers_new/__init__.py

"""
LLM Provider 工厂模块。
根据配置动态创建并返回统一的 LLM provider 实例。
"""

import logging
from typing import Dict, Any

from .base import BaseLLMProvider
from .remote_api import RemoteAPIProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider:
    provider_type = config.get("provider_type")
    if not provider_type:
        raise ValueError("Provider configuration must include 'provider_type'.")

    logger.info("Initializing LLM provider type: %s", provider_type)

    if provider_type == "local":
        from .local_batch import LocalVLLMProvider

        model_path = config.get("model_path")
        if not model_path:
            raise ValueError("Local provider config must include 'model_path'.")

        vllm_kwargs = {
            k: v for k, v in config.items()
            if k not in {"provider_type", "model_path", "api_url", "api_key", "api_protocol", "batch_size"}
        }
        return LocalVLLMProvider(model_name=model_path, **vllm_kwargs)

    if provider_type == "api":
        model_name = config.get("model_path")
        api_url = config.get("api_url")
        api_key = config.get("api_key", "EMPTY")

        if not model_name or not api_url:
            raise ValueError("API provider config must include 'model_path' and 'api_url'.")

        provider_kwargs = {
            k: v for k, v in config.items()
            if k not in {"provider_type", "model_path", "api_url", "api_key"}
        }
        return RemoteAPIProvider(
            model_name=model_name,
            api_base_url=api_url,
            api_key=api_key,
            **provider_kwargs,
        )

    raise ValueError(f"Unsupported provider type: '{provider_type}'. Choose 'local' or 'api'.")
