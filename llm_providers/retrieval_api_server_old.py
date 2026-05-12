# retrieval_api_server.py
# 这个部分确保无论您如何运行这个脚本，它都能找到项目中的其他模块（如 core）。
import sys
import os

# 1. 计算出项目根目录的绝对路径。
#    对于这个文件，项目根目录就是它的上级目录。
#    (os.path.dirname(__file__) 是 /.../llm_providers, 再 dirname 一次就是 /.../mcts_reason)
try:
    # __file__ 在直接运行时是可用的
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
except NameError:
    # 在某些交互式环境（如某些notebook）中 __file__ 可能不存在
    PROJECT_ROOT = os.path.abspath('.')

# 2. 将项目根目录添加到Python的模块搜索路径列表的最前面。
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    print(f"Added project root to Python path: {PROJECT_ROOT}")
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict
from core.retriever import Retriever

# --- 配置 ---
CONFIG = {
    "embedding_model_path": "/data2/home/E22101006/.cache/modelscope/hub/models/BAAI/bge-m3/",
    "metadata_db_file": "/data2/home/E22101006/mcts_reason/artifacts/metadata_db_full.json",
    "faiss_index_file": "/data2/home/E22101006/mcts_reason/artifacts/faiss_index_full.bin"
}

# --- Pydantic 模型定义 ---
class EmbedRequest(BaseModel):
    texts: List[str] = Field(..., example=["这是第一段文本", "这是第二段文本"])
    max_length: int = 512

class SearchRequest(BaseModel):
    query: str
    k: int = 3

class BatchSearchRequest(BaseModel):
    queries: List[str] = Field(..., example=["查询1", "查询2"])
    k: int = 3

# --- FastAPI 应用初始化 ---
app = FastAPI(
    title="Embedding & Retrieval Service API",
    description="A high-performance service for text embedding and vector search.",
    version="1.0.0"
)

# --- 全局变量：服务核心组件 ---
retriever: Retriever = None

@app.on_event("startup")
def startup_event():
    """
    应用启动时执行的函数，用于加载模型和索引。
    预热在这里自动发生。
    """
    global retriever
    print("Initializing Embedding & Retrieval Service...")
    retriever = Retriever(model_name=CONFIG["embedding_model_path"])
    retriever.load_index(
        metadata_db_path=CONFIG["metadata_db_file"],
        index_path=CONFIG["faiss_index_file"]
    )
    print("Service is ready and warmed up.")

# --- API 端点定义 ---

@app.post("/embed", response_model=List[List[float]])
async def embed_endpoint(request: EmbedRequest):
    """
    接收一批文本，并返回它们的嵌入向量。
    """
    if not retriever or not retriever.model:
        raise HTTPException(status_code=503, detail="Embedding model is not initialized yet.")
    
    try:
        embeddings = retriever.model.encode(
            request.texts,
            batch_size=32,
            max_length=request.max_length
        )['dense_vecs']
        return embeddings.tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during embedding: {e}")

@app.post("/search", response_model=List[Dict])
async def search_endpoint(request: SearchRequest):
    """
    接收单个查询，并返回最相似的k个结果。
    """
    if not retriever or not retriever.index:
        raise HTTPException(status_code=503, detail="Retriever is not initialized yet.")
    
    try:
        results = retriever.search(request.query, k=request.k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during search: {e}")

@app.post("/batch_search", response_model=List[List[Dict]])
async def batch_search_endpoint(request: BatchSearchRequest):
    """
    接收一批查询，并为每个查询返回最相似的k个结果。
    """
    if not retriever or not retriever.index:
        raise HTTPException(status_code=503, detail="Retriever is not initialized yet.")
    
    try:
        results = retriever.search(request.queries, k=request.k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during batch search: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok" if retriever and retriever.index else "loading"}

if __name__ == "__main__":
    uvicorn.run("retrieval_api_server:app", host="0.0.0.0", port=8001, reload=False)