# config.py

import os
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, BaseModel

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR_PATH = os.path.join(PROJECT_ROOT, "data")
ARTIFACTS_DIR_PATH = os.path.join(PROJECT_ROOT, "artifacts")
LOG_DIR_PATH = os.path.join(PROJECT_ROOT, "log")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
MODELSCOPE_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "modelscope", "hub", "models")


class PathSettings(BaseModel):
    data_dir: str = DATA_DIR_PATH
    artifacts_dir: str = ARTIFACTS_DIR_PATH
    log_dir: str = LOG_DIR_PATH

    evaluation_questions: str = os.path.join(DATA_DIR_PATH, "evaluation_questions.json")
    seed_questions: str = os.environ.get("SEED_QUESTIONS_FILE", os.path.join(DATA_DIR_PATH, "full_question.json"))

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
    # - vllm_chat_batch: vLLM /v1/chat/completions/batch with messages as a list of conversations.
    # - openai_completions_batch: legacy /v1/completions with prompt=[...].
    api_protocol: str = "openai_chat"
    batch_size: int = 8
    request_timeout: float = 120.0
    max_retries: int = 2
    supports_response_format: bool = True
    prompt_template_style: str = "qwen"

    tensor_parallel_size: int = 2
    gpu_memory_utilization: float = 0.7

    # Thinking control method:
    # - none: do not control thinking.
    # - prompt: append /no_think when thinking is disabled.
    # - param: send provider-specific thinking parameter.
    # - chat_template_kwargs: send vLLM chat_template_kwargs.enable_thinking.
    thinking_control_method: str = "prompt"
    # reasoning_effort control (GLM coding/paas/v4): inject extra_body={"reasoning_effort": ...}
    reasoning_effort: Optional[str] = None
    preserve_thinking: bool = True
    quantization: Optional[str] = None
    max_model_len: int = 10000
    serve_as_api: bool = False

    temperature: float = 0.6
    top_p: float = 0.9
    top_k: int = -1
    default_max_tokens: int = 4096


class GlobalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_", env_file=".env", extra="ignore")
    paths: PathSettings = PathSettings()
    servers: ServerSettings = ServerSettings()

    providers: Dict[str, ProviderSettings] = {
        "glm5.2": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("GLM_MODEL", "glm-5.2"),
            api_url=os.getenv("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4"),
            api_key=os.getenv("GLM_API_KEY"),
            api_protocol="openai_chat",          # single-protocol: OpenAI client at coding/paas/v4
            batch_size=int(os.getenv("GLM_BATCH_SIZE", "4")),
            request_timeout=float(os.getenv("GLM_REQUEST_TIMEOUT", "600")),
            max_retries=int(os.getenv("GLM_MAX_RETRIES", "0")),
            thinking_control_method=os.getenv("GLM_THINKING_CONTROL_METHOD", "reasoning_effort"),
            reasoning_effort=os.getenv("GLM_REASONING_EFFORT", "high"),   # high=轻思考, max=深度
            preserve_thinking=os.getenv("GLM_PRESERVE_THINKING", "true").lower() == "true",
            supports_response_format=os.getenv("GLM_SUPPORTS_RESPONSE_FORMAT", "true").lower() == "true",
            default_max_tokens=int(os.getenv("GLM_DEFAULT_MAX_TOKENS", "30000")),
            temperature=float(os.getenv("GLM_TEMPERATURE", "1.0")),
            top_p=float(os.getenv("GLM_TOP_P", "0.95")),
        ),
        "qwen36_a35": ProviderSettings(
            provider_type="api",
            model_path=os.getenv("QWEN36_A35_MODEL", "Qwen3.6-35B-A3B"),
            api_url=os.getenv("QWEN36_A35_API_BASE", "http://localhost:8000/v1"),
            api_key=os.getenv("QWEN36_A35_API_KEY", "EMPTY"),
            api_protocol=os.getenv("QWEN36_A35_API_PROTOCOL", "vllm_chat_batch"),
            batch_size=int(os.getenv("QWEN36_A35_BATCH_SIZE", "4")),
            thinking_control_method=os.getenv("QWEN36_A35_THINKING_CONTROL_METHOD", "chat_template_kwargs"),
            prompt_template_style="qwen",
            request_timeout=float(os.getenv("QWEN36_A35_REQUEST_TIMEOUT", "600")),
            temperature=float(os.getenv("QWEN36_A35_TEMPERATURE", "0.7")),
            top_p=float(os.getenv("QWEN36_A35_TOP_P", "0.9")),
            default_max_tokens=int(os.getenv("QWEN36_A35_DEFAULT_MAX_TOKENS", "8192")),
        ),
    }

    embedding_model_path: str = os.getenv("EMBEDDING_MODEL_PATH", os.path.join(MODELS_DIR, "bge-m3"))
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
