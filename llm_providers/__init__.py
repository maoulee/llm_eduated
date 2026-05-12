# llm_providers/__init__.py

import os
from .local_batch import LLMService
from .remote_api import VLLMAPIClient

def get_llm_provider(config: dict):
    """
    根据配置返回一个LLM提供者实例。
    
    Args:
        config (dict): 包含LLM配置的字典。
                       需要 'provider_type' ('local' or 'api')。
                       以及其他相关参数，如 'model_path' 或 'api_url'。
                       
    Returns:
        一个实现了LLM服务接口的对象 (LLMService or VLLMAPIClient)。
    """
    provider_type = config.get("provider_type", "local").lower() # 默认为本地批量

    if provider_type == "local":
        print("Initializing LLM Provider: Local Batch Mode (LLMService)")
        model_path = config.get("model_path")
        if not model_path:
            raise ValueError("Configuration must include 'model_path' for local provider.")
        # 这里可以传递更多LLMService的初始化参数
        return LLMService(model_name=model_path)
    
    elif provider_type == "api":
        print("Initializing LLM Provider: Remote API Mode (Asynchronous)")
        model_name = config.get("model_path")
        api_url = config.get("api_url", "http://localhost:8000/v1")
        if not model_name:
            raise ValueError("Configuration must include 'model_path' (as model identifier) for api provider.")
        return VLLMAPIClient(model_name=model_name, api_base_url=api_url)
    elif provider_type == "glm4.5":
        print("Initializing LLM Provider: Remote API Mode (Asynchronous)")
        model_name = config.get("model_path")
        api_url = config.get("api_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
        api_token=config.get("api_key",'EMPTY')
        if not model_name:
            raise ValueError("Configuration must include 'model_path' (as model identifier) for api provider.")
        return VLLMAPIClient(model_name=model_name, api_base_url=api_url,api_key=api_token)
    
    else:
        raise ValueError(f"Unknown LLM provider type: {provider_type}. Choose 'local' or 'api'.")