# server_solver_app.py

"""
独立的、生产级的推理 API 服务器。
它在启动时加载模型和工作流引擎，并提供 `/solve` 端点来处理单个问题。
"""
import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field

from config import settings, get_provider_config, get_retrieval_api_url
from core_new.workflow import IterativeSolverWorkflow
from llm_providers_new import get_llm_provider
from core_new.retrieval_api_client import RetrievalAPIClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在应用启动时加载资源，在关闭时清理。"""
    logger.info("API service is starting, loading resources...")

    provider_name = "api_vllm"
    logger.info(f"Pre-loading provider: {provider_name}")

    provider_config = get_provider_config(provider_name)
    llm_provider = get_llm_provider(provider_config)
    retriever_client = RetrievalAPIClient(base_url=get_retrieval_api_url())
    app.state.workflow_engine = IterativeSolverWorkflow(llm_provider, retriever_client)

    logger.info("API service is ready.")
    yield
    logger.info("API service is shutting down...")
    app.state.workflow_engine = None


app = FastAPI(
    title="Intelligent Solver API",
    description="408 solver API using modern reasoning, optional code verification, and trace-based annotation.",
    version="3.2.0",
    lifespan=lifespan,
)


class SolveRequest(BaseModel):
    prompt: str = Field(..., description="The question to be solved.")
    workflow_mode: str = Field(
        "full",
        enum=["full", "direct", "modern", "hybrid"],
        description="Use 'modern' or 'hybrid' for reasoning + optional code verification + trace-based annotation.",
    )
    max_tokens: int = Field(8192, ge=512, le=32768, description="Maximum tokens for model generation.")


class SolveResponse(BaseModel):
    response: str
    metadata: dict


@app.post("/solve", response_model=SolveResponse)
async def solve_endpoint(request: SolveRequest, http_request: Request):
    """接收问题并启动解题工作流。"""
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
        reload=False,
    )
