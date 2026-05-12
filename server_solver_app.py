# server_solver_app.py

"""
独立的、生产级的推理API服务器。
它在启动时加载模型和工作流引擎，并提供一个'/solve'端点来处理单个问题。
"""
import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field

# 从重构后的模块导入
from config import settings, get_provider_config, get_retrieval_api_url
from core_new.workflow import IterativeSolverWorkflow
from llm_providers_new import get_llm_provider
from core_new.retrieval_api_client import RetrievalAPIClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI 生命周期管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """在应用启动时加载资源，在关闭时清理。"""
    logger.info("🚀 API服务启动中，开始加载资源...")
    
    # 默认加载 'api_vllm' provider，因为它最适合服务器模式
    # 可以通过环境变量或启动参数进行修改
    provider_name = "api_vllm" 
    logger.info(f"Pre-loading provider: '{provider_name}'")
    
    provider_config = get_provider_config(provider_name)
    llm_provider = get_llm_provider(provider_config)
    retriever_client = RetrievalAPIClient(base_url=get_retrieval_api_url())
    
    # 将工作流引擎实例存储在 app.state 中，以便在请求之间共享
    app.state.workflow_engine = IterativeSolverWorkflow(llm_provider, retriever_client)
    
    logger.info("🎉 API服务已就绪，可以接收请求!")
    yield
    logger.info("🔌 API服务正在关闭...")
    app.state.workflow_engine = None

# --- FastAPI 应用和数据模型定义 ---
app = FastAPI(
    title="Intelligent Solver API",
    description="An API that solves complex questions using a multi-agent workflow.",
    version="3.1.0",
    lifespan=lifespan
)

class SolveRequest(BaseModel):
    prompt: str = Field(..., description="The user's question to be solved.")
    workflow_mode: str = Field(
        "full",
        enum=["full", "direct", "hybrid"],
        description="The workflow to use. Use 'hybrid' for reasoning + code verification + trace-based annotation."
    )
    max_tokens: int = Field(8192, ge=512, le=32768, description="Maximum tokens for model generation.")

class SolveResponse(BaseModel):
    response: str
    metadata: dict

# --- API 端点 ---
@app.post("/solve", response_model=SolveResponse)
async def solve_endpoint(request: SolveRequest, http_request: Request):
    """接收问题并启动推理工作流。"""
    engine: IterativeSolverWorkflow = http_request.app.state.workflow_engine
    if not engine:
        raise HTTPException(status_code=503, detail="Workflow engine is not initialized.")
        
    logger.info(f"Received solve request for prompt: {request.prompt[:70]}...")
    try:
        result = await engine.run(
            prompt=request.prompt,
            workflow_mode=request.workflow_mode,
            max_tokens=request.max_tokens,
        )
        logger.info("Request processed successfully.")
        return result
    except Exception as e:
        logger.error(f"An error occurred while processing the request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", summary="Health Check")
def health_check(request: Request):
    status = "ok" if request.app.state.workflow_engine else "loading"
    return {"status": status}

if __name__ == "__main__":
    uvicorn.run(
        "server_solver_app:app",
        host=settings.servers.host,
        port=settings.servers.solver_api_port,
        reload=False # 生产环境禁用reload
    )