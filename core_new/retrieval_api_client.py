# core_new/retrieval_api_client.py

"""
API客户端模块。
提供一个类用于与后端的检索服务进行HTTP通信。
"""

import logging
from typing import List, Dict, Union, Optional

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import faiss

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RetrievalAPIClient:
    """
    一个健壮的客户端，用于与FastAPI嵌入和检索服务交互。
    这个类模拟了本地Retriever的接口，但所有操作都通过API调用完成。
    """
    def __init__(self, base_url: str = "http://localhost:8001", timeout: int = 60):
        if not base_url:
            raise ValueError("base_url cannot be empty.")
        self.base_url = base_url.rstrip('/')
        self.embed_url = f"{self.base_url}/embed"
        self.search_url = f"{self.base_url}/search"
        self.batch_search_url = f"{self.base_url}/batch_search"
        self.timeout = timeout
        
        # --- 增强：配置健壮的HTTP会话 ---
        self.session = requests.Session()
        # 配置重试策略：对于GET和POST请求，如果遇到5xx错误，会重试3次
        retries = Retry(
            total=3,
            backoff_factor=0.5, # 重试间隔时间: {backoff factor} * (2 ** ({number of total retries} - 1))
            status_forcelist=[500, 502, 503, 504], # 只对这些状态码重试
            allowed_methods=["POST", "GET"] # 对POST请求也启用重试
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        logger.info(f"RetrievalAPIClient initialized for base_url: {self.base_url}")

    def _post(self, url: str, payload: dict) -> Optional[Union[List, Dict]]:
        """通用的POST请求方法，包含详细的错误处理和日志记录。"""
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则抛出HTTPError
            return response.json()
        except requests.exceptions.HTTPError as e:
            # 服务端返回的业务逻辑错误
            logger.error(f"HTTP Error from {url}: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.ConnectionError as e:
            # 网络连接错误
            logger.error(f"Connection Error to {url}: {e}")
        except requests.exceptions.Timeout as e:
            # 请求超时
            logger.error(f"Request to {url} timed out after {self.timeout} seconds: {e}")
        except requests.exceptions.RequestException as e:
            # 其他所有requests相关的异常
            logger.error(f"An unexpected API call error to {url} occurred: {e}", exc_info=True)
            
        return None # 发生任何异常都返回None

    def encode(self, texts: List[str], max_length: int = 512) -> np.ndarray:
        """通过API批量获取文本的嵌入向量。"""
        payload = {"texts": texts, "max_length": max_length}
        embeddings_list = self._post(self.embed_url, payload)
        
        # 即使API调用失败返回None，也安全地返回空数组
        if embeddings_list is None:
            return np.array([], dtype='float32')
            
        return np.array(embeddings_list, dtype='float32')

    def search(self, query_prompts: Union[str, List[str]], k: int = 3) -> Union[List[Dict], List[List[Dict]], None]:
        """
        通过API智能处理单个或批量查询。
        """
        if isinstance(query_prompts, str):
            payload = {"query": query_prompts, "k": k}
            return self._post(self.search_url, payload)
        elif isinstance(query_prompts, list):
            payload = {"queries": query_prompts, "k": k}
            return self._post(self.batch_search_url, payload)
        else:
            logger.error(f"Invalid type for query_prompts: {type(query_prompts)}. Must be str or list.")
            raise TypeError("query_prompts must be a string or a list of strings.")
        
    def build_index_from_embeddings(self, embeddings: np.ndarray, output_index_path: str):
        """
        在客户端侧，根据从API获取的embeddings构建FAISS索引并保存。
        """
        if faiss is None:
            raise ImportError("The 'faiss-cpu' or 'faiss-gpu' package is required to build indexes on the client side. Please install it.")
            
        if not isinstance(embeddings, np.ndarray) or embeddings.size == 0:
            raise ValueError("Embeddings must be a non-empty numpy array.")
            
        dimension = embeddings.shape[1]
        logger.info(f"Client-side: Building FAISS index with dimension {dimension} from embeddings...")
        
        index = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIDMap(index)
        
        logger.info("Client-side: Adding vectors to the FAISS index...")
        faiss_ids = np.arange(len(embeddings))
        index.add_with_ids(embeddings, faiss_ids)

        faiss.write_index(index, output_index_path)
        logger.info(f"Client-side: FAISS index with {index.ntotal} vectors saved to {output_index_path}")

    # --- 以下方法用于保持与本地Retriever的接口一致性，但在这里是空操作 ---
    def load_index(self, *args, **kwargs):
        """客户端模式下的空操作，因为索引由服务器管理。"""
        logger.info("In API client mode, index is managed by the server. `load_index` call is ignored.")
        pass
    
    def build_index(self, *args, **kwargs):
        """客户端模式下的空操作，因为索引构建应在服务器端执行。"""
        logger.info("In API client mode, `build_index` should be run on the server side.")
        pass