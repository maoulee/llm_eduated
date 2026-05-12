# core/retrieval_api_client.py

import requests
import numpy as np
from typing import List, Dict, Union

class RetrievalAPIClient:
    """
    一个客户端，用于与FastAPI嵌入和检索服务交互。
    这个类模拟了原始Retriever的接口。
    """
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.embed_url = f"{base_url}/embed"
        self.search_url = f"{base_url}/search"
        self.batch_search_url = f"{base_url}/batch_search"
        self.session = requests.Session()

    def _post(self, url: str, payload: dict) -> Union[List, Dict]:
        """通用的POST请求方法"""
        try:
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API call to {url} failed: {e}")
            return []

    def encode(self, texts: List[str], max_length: int = 512) -> np.ndarray:
        """通过API批量获取文本的嵌入向量。"""
        payload = {"texts": texts, "max_length": max_length}
        embeddings_list = self._post(self.embed_url, payload)
        return np.array(embeddings_list, dtype='float32') if embeddings_list else np.array([], dtype='float32')

    def search(self, query_prompts: Union[str, List[str]], k: int = 3) -> Union[List[Dict], List[List[Dict]]]:
        """
        智能处理单个或批量查询。
        """
        if isinstance(query_prompts, str):
            payload = {"query": query_prompts, "k": k}
            return self._post(self.search_url, payload)
        elif isinstance(query_prompts, list):
            payload = {"queries": query_prompts, "k": k}
            return self._post(self.batch_search_url, payload)
        else:
            raise TypeError("query_prompts must be a string or a list of strings.")

    def load_index(self, *args, **kwargs):
        """客户端模式下的空操作。"""
        print("INFO: In API client mode, index is managed by the server. `load_index` call is ignored.")
        pass
    
    def build_index(self, *args, **kwargs):
        """客户端模式下的空操作。"""
        print("INFO: In API client mode, `build_index` should be run directly on the server side or as an offline job.")
        pass