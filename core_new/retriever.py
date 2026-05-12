# core_new/retriever.py

"""
本地检索器模块。
负责加载BGE嵌入模型和FAISS索引，并在本地执行向量检索。
这个类主要用于数据准备（构建索引）和需要本地检索的场景。
"""

import json
import os
import logging
from typing import Dict, List, Union

import faiss
import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Retriever:
    """
    一个本地运行的检索器，使用BGE-M3模型和FAISS。
    """
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = None):
        logger.info("Initializing Retriever...")
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        logger.info(f"Loading embedding model '{model_name}' to device '{self.device}'...")
        # 在多GPU环境中，使用device参数可以指定模型加载到哪块卡上
        self.model = BGEM3FlagModel(model_name_or_path=model_name, use_fp16=True, device=self.device,local_files_only=True)
        
        self.index: faiss.Index = None
        self.metadata_db: Dict[str, Dict] = None
        self.id_map: List[str] = []
        
        self.warmup()

    def warmup(self):
        """对模型进行预热，以完成JIT编译并避免首次推理的巨大延迟。"""
        logger.info("Warming up the embedding model... This may take a minute.")
        try:
            # 使用一个有代表性的查询进行预热
            self.model.encode(["warmup query for computer science problems"], batch_size=1, max_length=128)
            logger.info("Embedding model is ready and warmed up.")
        except Exception as e:
            logger.error(f"An error occurred during embedding model warmup: {e}", exc_info=True)
            raise

    def encode(self, texts: List[str], batch_size: int = 32, max_length: int = 512) -> np.ndarray:
        """
        使用加载的模型对文本列表进行编码。

        Returns:
            一个numpy数组，包含了文本的密集向量表示。
        """
        logger.info(f"Encoding {len(texts)} texts with batch size {batch_size}...")
        try:
            embeddings_dict = self.model.encode(texts, batch_size=batch_size, max_length=max_length)
            return embeddings_dict['dense_vecs'].astype('float32')
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}", exc_info=True)
            return np.array([], dtype='float32')

    def build_index(self, metadata_db_path: str, output_index_path: str):
        """
        根据元数据构建FAISS索引，并将其保存到磁盘。
        """
        if not os.path.exists(metadata_db_path):
            raise FileNotFoundError(f"Metadata DB not found at {metadata_db_path}")
            
        with open(metadata_db_path, 'r', encoding='utf-8') as f:
            self.metadata_db = json.load(f)

        # 构建语料库，格式为 "问题 [SEP] 关键实体"
        corpus = [f"{data['original_prompt']} [SEP] {' '.join(data.get('key_entities', []))}" for data in self.metadata_db.values()]
        self.id_map = list(self.metadata_db.keys())

        logger.info(f"Encoding corpus of {len(corpus)} documents...")
        embeddings = self.encode(corpus, batch_size=12, max_length=8192)
        
        if embeddings.size == 0:
            raise ValueError("Corpus encoding failed, resulted in empty embeddings.")
            
        dimension = embeddings.shape[1]
        logger.info(f"Building FAISS index with dimension {dimension}...")
        
        # 使用一个标准的、高效的索引类型 IndexIVFFlat + IndexIDMap
        quantizer = faiss.IndexFlatL2(dimension)
        # 建议 nlist 的值为 4*sqrt(N) 到 16*sqrt(N) 之间, N 是向量数量
        nlist = int(4 * np.sqrt(len(corpus)))
        self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)
        self.index = faiss.IndexIDMap(self.index)
        
        logger.info("Training the FAISS index...")
        self.index.train(embeddings)
        
        logger.info("Adding vectors to the FAISS index...")
        faiss_ids = np.arange(len(self.id_map))
        self.index.add_with_ids(embeddings, faiss_ids)

        faiss.write_index(self.index, output_index_path)
        logger.info(f"FAISS index built with {self.index.ntotal} vectors and saved to {output_index_path}")

    def load_index(self, metadata_db_path: str, index_path: str):
        """从文件加载FAISS索引和元数据。"""
        if not os.path.exists(index_path) or not os.path.exists(metadata_db_path):
            raise FileNotFoundError(f"Index or Metadata DB file not found. Please build them first at {index_path} and {metadata_db_path}")
        
        logger.info(f"Loading FAISS index from {index_path}...")
        self.index = faiss.read_index(index_path)
        logger.info(f"Loading metadata from {metadata_db_path}...")
        with open(metadata_db_path, 'r', encoding='utf-8') as f:
            self.metadata_db = json.load(f)
        self.id_map = list(self.metadata_db.keys())
        logger.info(f"Retriever loaded successfully with {self.index.ntotal} indexed documents.")

    def search(self, query_prompts: Union[str, List[str]], k: int = 3) -> Union[List[Dict], List[List[Dict]]]:
        """
        接收单个或多个查询，返回检索结果。
        """
        if not self.index or not self.metadata_db:
            raise RuntimeError("Retriever index is not loaded. Please call `load_index` or `build_index` first.")

        is_single_query = isinstance(query_prompts, str)
        prompts = [query_prompts] if is_single_query else query_prompts

        logger.info(f"Searching for {len(prompts)} queries with k={k}...")
        query_embeddings = self.encode(prompts, batch_size=32)
        
        if query_embeddings.size == 0:
            return [] if is_single_query else [[] for _ in prompts]

        # `search`方法返回距离和索引矩阵
        distances, indices_matrix = self.index.search(query_embeddings, k)
        
        batch_results = []
        for i in range(len(prompts)):
            single_query_results = []
            # 遍历单个查询返回的 k 个结果的索引
            for j in indices_matrix[i]:
                # FAISS在找不到足够结果时会返回-1
                if j != -1:
                    # 使用内部ID映射找到原始的问题ID
                    q_id = self.id_map[j]
                    single_query_results.append(self.metadata_db[q_id])
            batch_results.append(single_query_results)
        
        logger.info("Search complete.")
        return batch_results[0] if is_single_query else batch_results