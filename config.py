# config.py

import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR_PATH = os.path.join(PROJECT_ROOT, "data")
ARTIFACTS_DIR_PATH = os.path.join(PROJECT_ROOT, "artifacts")
LOG_DIR_PATH = os.path.join(PROJECT_ROOT, "log")


class PathSettings(BaseModel):
    data_dir: str = DATA_DIR_PATH
    artifacts_dir: str = ARTIFACTS_DIR_PATH
    log_dir: str = LOG_DIR_PATH

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

    # API protocol:
    # - openai_chat: OpenAI-compatible /v1/chat/completions. Use this for GLM 5.1.
    # - openai_completions_batch: OpenAI-compatible /v1/completions with prompt=[...]. Use this for vLLM online batch.
    api_protocol: str = "openai_chat"
    batch_size: int = 8
    request_timeout: float = 120.0
    max_retries: int = 2
    supports_response_format: bool = True
    prompt_template_style: str = "qwen"

    tensor_parallel_size: int = 2
    gpu_memory_utilization: float = 0.7
    thinking_control_method: str = "prompt"
    quantization: Optional[str] = None
    max_model_len: int = 10000
    serve_as_api: bool = False

    temperature: float = 0.6
    top_p: float = 0.9
    default_max_tokens: int = 4096


class GlobalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_", env_file=".env", extra="ignore")
    paths: PathSettings = PathSettings()
    servers: ServerSettings = ServerSettings()

    providers: Dict[str, ProviderSettings] = {
        "local": ProviderSettings(
            provider_type="local",
            model_path=os.getenv("LOCAL_MODEL_PATH", "/zhaoshu/llm/qwen3-32b/"),
            thinking_control_method="prompt",
            tensor_parallel_size=int(os.getenv("LOCAL_TENSOR_PARALLEL_SIZE", "2")),
        ),
        "api_vllm": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("VLLM_MODEL", "/zhaoshu/llm/qwen3-32b/"),
            api_url=os.getenv("VLLM_API_BASE", f"http://127.0.0.1:{ServerSettings().vllm_api_port}/v1"),
            api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
            api_protocol="openai_completions_batch",
            batch_size=int(os.getenv("VLLM_BATCH_SIZE", "16")),
            prompt_template_style=os.getenv("VLLM_PROMPT_TEMPLATE_STYLE", "qwen"),
            thinking_control_method="prompt",
            supports_response_format=False,
            default_max_tokens=int(os.getenv("VLLM_DEFAULT_MAX_TOKENS", "4096")),
        ),
        "glm5.1": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("GLM_MODEL", "glm-5.1"),
            api_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/"),
            api_key=os.getenv("GLM_API_KEY"),
            api_protocol="openai_chat",
            batch_size=int(os.getenv("GLM_BATCH_SIZE", "4")),
            thinking_control_method="none",
            supports_response_format=True,
            default_max_tokens=int(os.getenv("GLM_DEFAULT_MAX_TOKENS", "4096")),
        ),
        "gptoss": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("GPTOSS_MODEL", "gpt-oss:20b"),
            api_url=os.getenv("GPTOSS_API_BASE", "http://localhost:8000/v1"),
            api_key=os.getenv("GPTOSS_API_KEY", "ollama"),
            api_protocol="openai_chat",
            thinking_control_method="prompt",
        ),
        "qwen3": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("QWEN3_MODEL", "/data/amax/home/E22101006/.cache/modelscope/hub/models/Qwen/Qwen3-8B/"),
            api_url=os.getenv("QWEN3_API_BASE", "http://localhost:8000/v1"),
            api_key=os.getenv("QWEN3_API_KEY", "EMPTY"),
            api_protocol="openai_chat",
            thinking_control_method="prompt",
        ),
        "qwen3local_api": ProviderSettings(
            provider_type="local",
            model_path=os.getenv("QWEN3_LOCAL_MODEL_PATH", "/data/amax/home/E22101006/.cache/modelscope/hub/models/Qwen/Qwen3-8B/"),
            thinking_control_method="prompt",
            tensor_parallel_size=1,
            serve_as_api=True,
        ),
    }

    embedding_model_path: str = os.getenv("EMBEDDING_MODEL_PATH", "/data/amax/home/E22101006/model/bge-m3/")
    retrieval_k: int = 3
    evaluation_runs: int = 3


settings = GlobalSettings()

os.makedirs(settings.paths.data_dir, exist_ok=True)
os.makedirs(settings.paths.artifacts_dir, exist_ok=True)
os.makedirs(settings.paths.log_dir, exist_ok=True)


def get_provider_config(provider_name: str) -> Dict[str, Any]:
    if provider_name not in settings.providers:
        raise ValueError(f"Provider '{provider_name}' not found in configuration.")
    return settings.providers[provider_name].model_dump(exclude_none=True)


def get_retrieval_api_url() -> str:
    return f"http://{settings.servers.host}:{settings.servers.retrieval_api_port}"
