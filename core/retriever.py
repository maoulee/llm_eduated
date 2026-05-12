# core/retriever.py

import json
import os
from typing import Dict, List, Union

import faiss
import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel


class Retriever:
    def __init__(self, model_name="BAAI/bge-m3", device=None):
        print("Initializing Retriever...")
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        
        print(f"Loading embedding model {model_name} to device '{self.device}'...")
        self.model = BGEM3FlagModel(model_name, use_fp16=True, device=self.device)
        
        self.index = None
        self.metadata_db = None
        self.id_map = []
        
        self.warmup()

    def warmup(self):
        """对模型进行预热，以完成JIT编译并避免首次推理的巨大延迟。"""
        print("Warming up the embedding model... This may take a minute.")
        try:
            self.model.encode(["warmup query"], batch_size=1, max_length=128)
            print("Embedding model is ready and warmed up.")
        except Exception as e:
            print(f"An error occurred during embedding model warmup: {e}")

    def build_index(self, metadata_db_path, output_index_path):
        """根据元数据构建FAISS索引。"""
        if not os.path.exists(metadata_db_path):
            raise FileNotFoundError(f"Metadata DB not found at {metadata_db_path}")
            
        with open(metadata_db_path, 'r', encoding='utf-8') as f:
            self.metadata_db = json.load(f)

        corpus = [f"{data['original_prompt']} [SEP] {' '.join(data['key_entities'])}" for data in self.metadata_db.values()]
        self.id_map = list(self.metadata_db.keys())

        print("Encoding corpus with BGE-M3...")
        embeddings = self.model.encode(corpus, batch_size=12, max_length=8192)['dense_vecs']
        embeddings = embeddings.astype('float32')
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index = faiss.IndexIDMap(self.index)
        
        faiss_ids = np.array(range(len(self.id_map)))
        self.index.add_with_ids(embeddings, faiss_ids)

        faiss.write_index(self.index, output_index_path)
        print(f"FAISS index built and saved to {output_index_path}")

    def load_index(self, metadata_db_path, index_path):
        """从文件加载FAISS索引和元数据。"""
        if not os.path.exists(index_path) or not os.path.exists(metadata_db_path):
            raise FileNotFoundError("Index or Metadata DB file not found. Please build them first.")
        self.index = faiss.read_index(index_path)
        with open(metadata_db_path, 'r', encoding='utf-8') as f:
            self.metadata_db = json.load(f)
        self.id_map = list(self.metadata_db.keys())

    def search(self, query_prompts: Union[str, List[str]], k: int = 3) -> Union[List[Dict], List[List[Dict]]]:
        """
        接收单个或多个查询，返回检索结果。
        
        Args:
            query_prompts (Union[str, List[str]]): 单个查询字符串或一个查询字符串列表。
            k (int): 每个查询要返回的结果数量。

        Returns:
            - 如果输入是单个字符串，返回一个结果列表 List[Dict]。
            - 如果输入是一个列表，返回一个结果的列表的列表 List[List[Dict]]。
        """
        is_single_query = isinstance(query_prompts, str)
        prompts = [query_prompts] if is_single_query else query_prompts

        query_embeddings = self.model.encode(prompts, batch_size=32)['dense_vecs']
        query_embeddings = query_embeddings.astype('float32')
        
        distances, indices_matrix = self.index.search(query_embeddings, k)
        
        batch_results = []
        for i in range(len(prompts)):
            single_query_results = []
            for j in indices_matrix[i]:
                if j != -1:
                    q_id = self.id_map[j]
                    single_query_results.append(self.metadata_db[q_id])
            batch_results.append(single_query_results)
            
        return batch_results[0] if is_single_query else batch_results