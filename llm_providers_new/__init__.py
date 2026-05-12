# llm_providers_new/__init__.py

"""
LLM Provider 工厂模块。
提供一个函数，用于根据配置动态创建和返回一个LLM provider实例。
"""

import logging
from typing import Dict, Any

from .base import BaseLLMProvider
from .local_batch import LocalVLLMProvider
from .remote_api import RemoteAPIProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider:
    """
    根据配置字典创建并返回一个LLM provider实例。
    所有返回的实例都实现了 BaseLLMProvider 接口。

    Args:
        config (dict): 包含LLM配置的字典。
                       必需: 'provider_type' ('local' or 'api')。
                       其他参数根据 provider_type 变化。

    Returns:
        一个 BaseLLMProvider 的子类实例。
    """
    provider_type = config.get("provider_type")
    if not provider_type:
        raise ValueError("Provider configuration must include 'provider_type'.")

    logger.info(f"Attempting to initialize LLM Provider of type: '{provider_type}'")

    if provider_type == "local":
        # 对于本地模式，我们提取vLLM特定的参数
        model_path = config.get("model_path")
        if not model_path:
            raise ValueError("Local provider config must include 'model_path'.")
        
        # 提取所有非核心的配置项作为vLLM的kwargs
        vllm_kwargs = {
            k: v for k, v in config.items() 
            if k not in ["provider_type", "model_path"]
        }
        return LocalVLLMProvider(model_name=model_path, **vllm_kwargs)
    
    elif provider_type == "api":
        model_name = config.get("model_path")
        api_url = config.get("api_url")
        api_key = config.get("api_key", "EMPTY")
        
        if not model_name or not api_url:
            raise ValueError("API provider config must include 'model_path' and 'api_url'.")
            
        return RemoteAPIProvider(
            model_name=model_name,
            api_base_url=api_url,
            api_key=api_key
        )
        
    else:
        raise ValueError(f"Unsupported provider type: '{provider_type}'. Choose 'local' or 'api'.")