# config.py (FIXED)

import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel # 确保导入 BaseModel

# --- 基础路径设置 ---
# 将这些定义为模块级别的常量
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR_PATH = os.path.join(PROJECT_ROOT, "data")
ARTIFACTS_DIR_PATH = os.path.join(PROJECT_ROOT, "artifacts")
LOG_DIR_PATH = os.path.join(PROJECT_ROOT, "log")

class PathSettings(BaseModel):
    # 这里只定义目录，作为配置项
    data_dir: str = DATA_DIR_PATH
    artifacts_dir: str = ARTIFACTS_DIR_PATH
    log_dir: str = LOG_DIR_PATH

    # 完整路径直接使用上面的常量构建，不再需要复杂的 default_factory
    evaluation_questions: str = os.path.join(DATA_DIR_PATH, "evaluation_questions.json")
    seed_questions: str = os.path.join(DATA_DIR_PATH, "full_question.json")
    
    batch_results_template: str = os.path.join(DATA_DIR_PATH, "batch_results_{run_name}.json")
    evaluation_report_template: str = os.path.join(DATA_DIR_PATH, "evaluation_report_{run_name}.json")
    
    metadata_db: str = os.path.join(ARTIFACTS_DIR_PATH, "metadata_db_full.json")
    faiss_index: str = os.path.join(ARTIFACTS_DIR_PATH, "faiss_index_full.bin")

class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    retrieval_api_port: int = 8001
    vllm_api_port: int = 8000
    solver_api_port: int = 8080

class ProviderSettings(BaseModel):
    provider_type: str = Field(..., enum=["local", "api"])
    model_path: str
    api_url: Optional[str] = None
    api_key: Optional[str] = Field(None, validate_default=False)
    tensor_parallel_size: int = 2
    gpu_memory_utilization: float = 0.7 # 稍微调高一点，vLLM通常能很好地管理内存
    thinking_control_method: str
    # quantization 默认为 None，只有显式提供值时才生效
    quantization: Optional[str] = None
    
    max_model_len: int = 10000
    
    # 新增开关：是否将此本地模型作为API服务启动
    serve_as_api: bool = False

class GlobalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='MYAPP_', env_file='.env', extra='ignore')
    paths: PathSettings = PathSettings()
    servers: ServerSettings = ServerSettings()
    
    providers: Dict[str, ProviderSettings] = {
        "local": ProviderSettings(
            provider_type="local", 
            model_path="/zhaoshu/llm/qwen3-32b/",
            thinking_control_method='prompt',
            tensor_parallel_size=2
        ),
        "api_vllm": ProviderSettings(
            provider_type="api", 
            model_path="/zhaoshu/llm/qwen3-32b/",
            # 这里也直接使用 ServerSettings 的默认值
            thinking_control_method='prompt',
            api_url=f"http://{ServerSettings().host}:{ServerSettings().vllm_api_port}/v1"
        ),
        "glm4.6": ProviderSettings(
            provider_type="api",
            model_path="glm-4.6",
            api_url="https://open.bigmodel.cn/api/paas/v4/",
            api_key="",
            thinking_control_method='param',
        ),
        "gptoss": ProviderSettings(
            provider_type="api",
            model_path="gpt-oss:20b",
            api_url="http://localhost:8000/v1",
            api_key="ollama",
            thinking_control_method='prompt',
        ),
        "qwen3": ProviderSettings(
            provider_type="api",
            model_path="/data/amax/home/E22101006/.cache/modelscope/hub/models/Qwen/Qwen3-8B/",
            api_url="http://localhost:8000/v1",
            thinking_control_method='prompt',
            api_key="empty"
        ),
        "qwen3local_api": ProviderSettings(
            provider_type="local", # 它的本质依然是本地模型
            model_path="/data/amax/home/E22101006/.cache/modelscope/hub/models/Qwen/Qwen3-8B/",
            thinking_control_method='prompt',
            tensor_parallel_size=1, # 8B模型通常tp=1即可
            serve_as_api=True, # 启用API服务开关

            # 如果需要默认开启量化，在这里指定。否则保持为None，让脚本控制。
            # quantization="awq" 
        ),
    }
    
    embedding_model_path: str = "/data/amax/home/E22101006/model/bge-m3/"
    retrieval_k: int = 3
    evaluation_runs: int = 3

# 创建一个全局可用的配置实例
settings = GlobalSettings()

# 确保目录存在
os.makedirs(settings.paths.data_dir, exist_ok=True)
os.makedirs(settings.paths.artifacts_dir, exist_ok=True)
os.makedirs(settings.paths.log_dir, exist_ok=True)

# 便捷函数保持不变
def get_provider_config(provider_name: str) -> Dict[str, Any]:
    if provider_name not in settings.providers:
        raise ValueError(f"Provider '{provider_name}' not found in configuration.")
    return settings.providers[provider_name].model_dump(exclude_none=True)

def get_retrieval_api_url() -> str:
    return f"http://{settings.servers.host}:{settings.servers.retrieval_api_port}"
