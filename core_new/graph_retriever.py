
# core_new/graph_retriever.py

import json
import logging
import os
import asyncio
from typing import Dict, Any, List, Tuple
from collections import defaultdict # <-- 确保导入

import networkx as nx
import faiss
import numpy as np

from .retrieval_api_client import RetrievalAPIClient
from llm_providers_new.base import BaseLLMProvider
from kcard.prompt import PROMPT_RERANK_KNOWLEDGE, PROMPT_IDENTIFY_KNOWLEDGE_POINTS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeGraphRetriever:
    """
    一个先进的检索器，实现了带“交叉点优先”和“模式开关”的“多路召回-融合-精排”流程。
    """
    def __init__(self, db_dir: str, api_client: RetrievalAPIClient, reranker_llm: BaseLLMProvider):
        self.db_dir = db_dir
        self.api_client = api_client
        self.reranker_llm = reranker_llm
        
        self.knowledge_nodes: Dict[str, Dict] = {}
        self.scene_nodes: Dict[str, Dict] = {}
        self.graph: nx.Graph = None
        
        self.kn_index: faiss.Index = None
        self.kn_id_map: List[str] = []
        self.sc_index: faiss.Index = None
        self.sc_id_map: List[str] = []

        self._load_all()

    def _load_all(self):
        """加载所有数据库、图和索引文件。"""
        logger.info(f"Loading knowledge graph from directory: {self.db_dir}")
        try:
            with open(os.path.join(self.db_dir, "knowledge_nodes.json"), 'r', encoding='utf-8') as f:
                self.knowledge_nodes = json.load(f)
            with open(os.path.join(self.db_dir, "scene_nodes.json"), 'r', encoding='utf-8') as f:
                self.scene_nodes = json.load(f)
            
            self.graph = nx.read_graphml(os.path.join(self.db_dir, "bipartite_graph.graphml"))

            self.kn_index = faiss.read_index(os.path.join(self.db_dir, "knowledge_nodes.faiss"))
            with open(os.path.join(self.db_dir, "kn_id_map.json"), 'r', encoding='utf-8') as f:
                self.kn_id_map = json.load(f)
            
            self.sc_index = faiss.read_index(os.path.join(self.db_dir, "scene_nodes.faiss"))
            with open(os.path.join(self.db_dir, "sc_id_map.json"), 'r', encoding='utf-8') as f:
                self.sc_id_map = json.load(f)
            
            logger.info("Knowledge graph loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load knowledge graph from {self.db_dir}: {e}", exc_info=True)
            raise

    async def retrieve(
        self, 
        query: str,
        mode: str = "full",
        recall_top_k_kn: int = 3,
        recall_top_k_sc: int = 3,
        entity_linking_threshold: float = 0.9,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        执行最终的、带双重精排功能的检索流程。
        """
        logger.info(f"Retrieving and Reranking knowledge for query: '{query[:70]}...'")
        
        # --- Stage 1: Multi-Signal Recall ---
        query_embedding = self.api_client.encode([query])
        if query_embedding.size == 0: return [], []

        logger.info("  - Stage 1: Multi-Signal Recall...")
        
        prompt_identify = PROMPT_IDENTIFY_KNOWLEDGE_POINTS.format(question=query)
        messages = [[{"role": "user", "content": prompt_identify}]]
        json_outputs = await self.reranker_llm.generate_json_batch(messages)
        
        kn_from_llm = set()
        if json_outputs and isinstance(json_outputs[0], dict):
            identified_knowledge = json_outputs[0].get("required_knowledge", [])
            if identified_knowledge:
                identified_names = [item.get("knowledge_name") for item in identified_knowledge if item.get("knowledge_name")]
                logger.info(f"    - Path A (LLM Identify): Identified candidate names: {identified_names}")
                if identified_names:
                    identified_embeddings = self.api_client.encode(identified_names)
                    if identified_embeddings.size > 0:
                        distances, indices = self.kn_index.search(identified_embeddings, 1)
                        for i in range(len(identified_names)):
                            idx, dist = indices[i][0], distances[i][0]
                            similarity = 1 - (dist**2 / 2)
                            if idx != -1 and similarity >= entity_linking_threshold:
                                linked_kn_id = self.kn_id_map[idx]
                                kn_from_llm.add(linked_kn_id)
                                logger.info(f"      - LINKED: '{identified_names[i]}' -> '{linked_kn_id}' (Similarity: {similarity:.4f})")
                            else:
                                logger.info(f"      - DROPPED: '{identified_names[i]}'. Best match similarity {similarity:.4f} < threshold {entity_linking_threshold}.")
        logger.info(f"    - Path A (LLM Identify): Successfully linked {len(kn_from_llm)} knowledge nodes: {kn_from_llm}")

        kn_from_scenes, sc_from_vector = set(), set()
        if mode == "full":
            _, sc_indices = self.sc_index.search(query_embedding, recall_top_k_sc)
            sc_from_vector = {self.sc_id_map[idx] for idx in sc_indices[0] if idx != -1}
            logger.info(f"    - Path B (Scene Vector): Recalled {len(sc_from_vector)} scenes.")
            for scene_id in sc_from_vector:
                for neighbor in self.graph.neighbors(scene_id):
                    if self.graph.nodes[neighbor]['bipartite'] == 1:
                        kn_from_scenes.add(neighbor)
            logger.info(f"    - Path B (Scene Vector): Expanded to {len(kn_from_scenes)} knowledge nodes.")
        else:
            logger.info("    - Path B (Scene Vector): Skipped due to 'knowledge_only' mode.")

        _, kn_indices = self.kn_index.search(query_embedding, recall_top_k_kn)
        kn_from_vector = {self.kn_id_map[idx] for idx in kn_indices[0] if idx != -1}
        logger.info(f"    - Path D (Direct KN Vector): Recalled {len(kn_from_vector)} knowledge nodes.")

        # --- Stage 2: Fusion and Prep for Reranking ---
        recalled_kn_union = kn_from_llm.union(kn_from_scenes).union(kn_from_vector)
        
        all_recalled_lists = [kn_from_llm, kn_from_scenes, kn_from_vector]
        kn_counts = defaultdict(int)
        for kn_list in all_recalled_lists:
            for kn_id in kn_list:
                kn_counts[kn_id] += 1
        intersection_priority_nodes = {kn_id for kn_id, count in kn_counts.items()}
        
        recalled_constraints = []
        for sc_id in sc_from_vector:
            if sc_id in self.scene_nodes:
                scene = self.scene_nodes[sc_id]
                # 确保 scene['constraints'] 是一个列表
                constraints_list = scene.get('constraints', [])
                if not isinstance(constraints_list, list):
                    continue # 如果不是列表，则跳过

                for const in constraints_list:
                    const_with_source = {}
                    # 检查 const 的类型
                    if isinstance(const, dict):
                        # 如果是期望的字典类型，则复制
                        const_with_source = const.copy()
                    elif isinstance(const, str):
                        # 如果是意外的字符串类型，则将其包装成字典
                        #logger.warning(f"Found a string-type constraint in scene '{sc_id[:50]}...'. Wrapping it into a dict.")
                        const_with_source = {
                            "constraint_name": "Unknown Constraint",
                            "description": const
                        }
                    else:
                        # 跳过其他未知类型
                        continue
                    
                    const_with_source['source_example'] = scene['source_question']
                    recalled_constraints.append(const_with_source)
        
        logger.info(f"  - Fusion: Recalled {len(recalled_kn_union)} unique nodes and {len(recalled_constraints)} constraints for reranking.")

        # --- Stage 3: LLM Dual Reranking ---
        logger.info("  - Stage 3: Reranking both knowledge and constraints with LLM...")
        refined_knowledge_list = await self._rerank(
            query, 
            recalled_kn_union, 
            intersection_priority_nodes
        )
        
        # --- Stage 3: 结果组装 (不过滤！) ---
        final_kn_modules = []
        if isinstance(refined_knowledge_list, list):
            # 按平均分从高到低排序
            refined_knowledge_list.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            logger.info(f"  - Final Scored & Sorted Knowledge for Planner: {refined_knowledge_list}")
            
            # 依然使用阈值进行最终筛选
            for item in refined_knowledge_list:
                    kn_id = item.get('canonical_name')
                    if kn_id and kn_id in self.knowledge_nodes:
                        kn_module = self.knowledge_nodes[kn_id].copy()
                        kn_module['relevance_score'] = item['relevance_score']
                        final_kn_modules.append(kn_module)
        else:
            logger.error(f"_rerank method returned an unexpected type: {type(refined_knowledge_list)}. Expected a list.")

        # --- Stage 4: 约束处理与最终结果组装 ---
        # 约束暂时不过滤，直接使用召回的结果
        final_constraints = recalled_constraints

        logger.info(f"Retrieval complete. Passing {len(final_kn_modules)} refined knowledge modules and {len(final_constraints)} constraints to Planner.")
        return final_kn_modules, final_constraints

    async def _rerank(
        self, 
        question: str, 
        recalled_kn_ids: set, 
        priority_ids: set
    ) -> List[Dict]:
        """
        使用LLM进行“集成精排”。
        多次调用Reranker，然后取并集，并计算平均分。
        
        Args:
            question: The user's question.
            recalled_kn_ids: A set of all unique recalled knowledge node IDs.
            priority_ids: A subset of recalled_kn_ids that were recalled by multiple paths.
            num_rerank_runs: The number of times to run the reranking process.
            
        Returns:
            A list of dictionaries, where each dictionary contains 'canonical_name' and 'relevance_score'.
            The list is NOT sorted here.
        """
        if not recalled_kn_ids: 
            return []
        
        num_rerank_runs= 3

        logger.info(f"  - Starting Ensemble Reranking with {num_rerank_runs} runs...")

        # --- 准备一次性的候选列表 ---
        # 这部分代码是之前被省略的
        kn_candidate_list = []
        # 优先添加交叉点
        for kn_id in sorted(list(priority_ids)):
            node = self.knowledge_nodes.get(kn_id)
            if node:
                kn_candidate_list.append({
                    "canonical_name": node["canonical_name"],
                    "summary": node.get("concept_definition", {}).get("summary", ""),
                    "priority": "High (found by multiple methods)"
                })
        
        # 添加其余的
        for kn_id in sorted(list(recalled_kn_ids)):
            if kn_id not in priority_ids:
                node = self.knowledge_nodes.get(kn_id)
                if node:
                    kn_candidate_list.append({
                        "canonical_name": node["canonical_name"],
                        "summary": node.get("concept_definition", {}).get("summary", ""),
                        "priority": "Normal"
                    })
        # ------------------------------------
        
        kn_candidate_list_str = json.dumps(kn_candidate_list, ensure_ascii=False, indent=2)

        prompt = PROMPT_RERANK_KNOWLEDGE.format(
            question=question,
            candidate_knowledge_list_str=kn_candidate_list_str
        )
        
        # --- 并行执行多次精排任务 ---
        tasks = []
        for _ in range(num_rerank_runs):
            # 每次调用使用相同的prompt，依赖模型自身的随机性（如果temperature > 0）
            messages = [[{"role": "user", "content": prompt}]]
            tasks.append(self.reranker_llm.generate_json_batch(messages))
        
        all_run_results = await asyncio.gather(*tasks)
        # ------------------------------------

        # --- 结果聚合与平均分计算 ---
        knowledge_scores = defaultdict(list) # key: canonical_name, value: list of scores
        
        for i, run_result in enumerate(all_run_results):
            if run_result and isinstance(run_result[0], dict):
                # --- FIX: 正确地从 'refined_knowledge' 键中提取列表 ---
                refined_list = run_result[0].get("refined_knowledge", [])
                if isinstance(refined_list, list):
                    for item in refined_list:
                        name = item.get("canonical_name")
                        score = item.get("relevance_score")
                        if name and isinstance(score, (int, float)):
                            knowledge_scores[name].append(score)
                else:
                    logger.warning(f"      - Run {i+1} 'refined_knowledge' field is not a list.")
            else:
                logger.warning(f"      - Run {i+1} failed to produce a valid JSON result.")

        if not knowledge_scores:
            logger.error("Ensemble Reranking failed: All runs returned invalid results. Falling back.")
            # 最终的回退策略：只返回高优先级的知识点，并赋予最高分
            fallback_list = []
            for kn_id in priority_ids:
                fallback_list.append({"canonical_name": kn_id, "relevance_score": 10})
            return fallback_list

        # 计算并集和平均分
        final_refined_list = []
        for name, scores in knowledge_scores.items():
            avg_score = sum(scores) / len(scores)
            final_refined_list.append({
                "canonical_name": name,
                "relevance_score": round(avg_score, 2) # 保留两位小数
            })
        
        logger.info(f"  - Ensemble Reranking complete. Final unique items: {len(final_refined_list)}")
        
        return final_refined_list