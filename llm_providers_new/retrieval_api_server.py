# retrieval_api_server_new.py

"""
独立的、生产级的检索API服务器。
它在启动时加载BGE嵌入模型和FAISS索引，并提供用于文本嵌入和向量搜索的API端点。
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from typing import List, Dict

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


# 导入重构后的核心组件和配置
# 注意：这个独立的服务器只依赖 core/retriever 和 config
from config import settings
from core_new.retriever import Retriever 

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI 生命周期和应用状态 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """在应用启动时加载模型和索引。"""
    logger.info("🚀 Retrieval API Service is starting up, loading resources...")
    
    # 初始化 Retriever 实例
    retriever_instance = Retriever(model_name=settings.embedding_model_path)
    
    # 从统一的配置加载索引和元数据
    try:
        retriever_instance.load_index(
            metadata_db_path=settings.paths.metadata_db,
            index_path=settings.paths.faiss_index
        )
    except FileNotFoundError as e:
        logger.error(f"FATAL: Could not load index or metadata DB. Please build them first. Error: {e}", exc_info=True)
        # 在这种关键资源加载失败的情况下，可以考虑让应用启动失败
        # 但为了服务能启动并报告错误，我们先继续，让健康检查报告问题
        retriever_instance = None # 标记为加载失败
        
    # 将实例存储在 app.state 中
    app.state.retriever = retriever_instance
    
    if app.state.retriever:
        logger.info("🎉 Retrieval API Service is ready to accept requests!")
    else:
        logger.error("🔥 Retrieval API Service started BUT is in a FAILED state. Check logs.")
        
    yield
    
    logger.info("🔌 Retrieval API Service is shutting down...")
    app.state.retriever = None

app = FastAPI(
    title="Embedding & Retrieval Service API",
    description="A high-performance service for text embedding and vector search.",
    version="2.0.0",
    lifespan=lifespan
)

# --- Pydantic API 数据模型 ---
class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., example=["这是第一段文本", "这是第二段文本"])
    max_length: int = 512

class SearchRequest(BaseModel):
    query: str
    k: int = Field(default_factory=lambda: settings.retrieval_k)

class BatchSearchRequest(BaseModel):
    queries: List[str] = Field(..., example=["查询1", "查询2"])
    k: int = Field(default_factory=lambda: settings.retrieval_k)

# --- API 端点定义 ---

@app.post("/embed", response_model=List[List[float]])
async def embed_endpoint(request: EmbedRequest, http_request: Request):
    retriever: Retriever = http_request.app.state.retriever
    if not retriever or not retriever.model:
        raise HTTPException(status_code=503, detail="Service is not ready or model not loaded.")
    
    try:
        # 使用重构后 Retriever 内部的 encode 方法
        embeddings = retriever.encode(request.texts, max_length=request.max_length)
        return embeddings.tolist()
    except Exception as e:
        logger.error(f"Error during embedding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=List[Dict])
async def search_endpoint(request: SearchRequest, http_request: Request):
    retriever: Retriever = http_request.app.state.retriever
    if not retriever or not retriever.index:
        raise HTTPException(status_code=503, detail="Service is not ready or index not loaded.")
        
    try:
        results = retriever.search(request.query, k=request.k)
        return results
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch_search", response_model=List[List[Dict]])
async def batch_search_endpoint(request: BatchSearchRequest, http_request: Request):
    retriever: Retriever = http_request.app.state.retriever
    if not retriever or not retriever.index:
        raise HTTPException(status_code=503, detail="Service is not ready or index not loaded.")
        
    try:
        results = retriever.search(request.queries, k=request.k)
        return results
    except Exception as e:
        logger.error(f"Error during batch search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check(http_request: Request):
    status = "ok" if http_request.app.state.retriever and http_request.app.state.retriever.index else "error_loading_resources"
    return {"status": status}

if __name__ == "__main__":
    uvicorn.run(
        "retrieval_api_server:app",
        host=settings.servers.host,
        port=settings.servers.retrieval_api_port,
        reload=False
    )