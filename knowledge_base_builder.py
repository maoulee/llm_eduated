# knowledge_base_builder.py (API Client Version)

import json
import logging
import os
import argparse
import re
from typing import Dict, Any, List, Tuple

import networkx as nx
import numpy as np

# --- 修改导入 ---
# 从本地Retriever改为导入API客户端
from core_new.retrieval_api_client import RetrievalAPIClient
from config import settings # 导入配置以获取API地址

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[\(（].*?[\)）]', '', text) # 移除括号及其内容
    text = re.sub(r'[\s\-_\/]', '', text) # 移除空格和分隔符
    text = re.sub(r'(原理|方法|计算|表示法)$', '', text) # 移除常见后缀
    return text


class KnowledgeBaseBuilder:
    """
    一个用于从 knowledge_base.json 构建结构化知识超图数据库的类。
    此版本集成了 alias_map.json 以实现高质量的实体对齐。
    """
    def __init__(self, api_client: RetrievalAPIClient, alias_map_path: str):
        logger.info("Initializing KnowledgeBaseBuilder...")
        self.api_client = api_client
        self.alias_map = self._load_alias_map(alias_map_path)
        
        self.knowledge_nodes: Dict[str, Dict] = {}
        self.scene_nodes: Dict[str, Dict] = {}
        self.edges: List[Tuple[str, str]] = []
        
        # 用于回退的规则驱动对齐缓存
        self.name_to_canonical_fallback: Dict[str, str] = {}

    def _load_alias_map(self, path: str) -> Dict[str, str]:
        """加载由LLM精炼生成的别名映射文件。"""
        if os.path.exists(path):
            logger.info(f"Loading alias map from {path}")
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse alias map file {path}: {e}. Proceeding without it.")
        else:
            logger.warning(f"Alias map file not found at {path}. Proceeding with rule-based alignment only.")
        return {}

    def _get_canonical_name(self, name: str) -> str:
        """
        对知识点名称进行对齐，返回其唯一的首选名称。
        优先级: LLM别名映射 > 规则驱动的缓存 > 新建。
        """
        # 1. 优先使用大模型生成的别名映射
        if name in self.alias_map:
            return self.alias_map[name]

        # --- 如果别名映射中没有，则回退到规则驱动的对齐 ---
        # 2. 检查回退缓存
        if name in self.name_to_canonical_fallback:
            return self.name_to_canonical_fallback[name]
        
        normalized_name = normalize_text(name)
        if normalized_name in self.name_to_canonical_fallback:
            canonical_name = self.name_to_canonical_fallback[normalized_name]
            self.name_to_canonical_fallback[name] = canonical_name
            return canonical_name
        
        # 3. 如果是全新的，则它自己就是首选名称
        # 注意：这里我们使用原始名称作为首选名称，因为它更具可读性
        self.name_to_canonical_fallback[name] = name
        self.name_to_canonical_fallback[normalized_name] = name
        return name

    def build_from_source(self, source_file: str):
        """从源 JSON 文件解析并构建节点和边。"""
        logger.info(f"Loading and parsing source file: {source_file}")
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load or parse {source_file}: {e}")
            return

        for source_question, kb_content in data.items():
            if not kb_content or "universal_knowledge_modules" not in kb_content:
                continue

            scene_id = source_question
            self.scene_nodes[scene_id] = {
                "source_question": source_question,
                "constraints": kb_content.get("problem_specific_constraints", [])
            }

            for kn_module in kb_content["universal_knowledge_modules"]:
                original_name = kn_module.get("knowledge_point_name")
                if not original_name: continue
                
                # --- 使用我们升级后的对齐函数 ---
                canonical_name = self._get_canonical_name(original_name)
                
                if canonical_name not in self.knowledge_nodes:
                    # 如果是新的首选实体，则创建节点
                    self.knowledge_nodes[canonical_name] = {
                        "canonical_name": canonical_name,
                        "aliases": {original_name}, # 使用集合以自动去重
                        "concept_definition": kn_module.get("concept_definition"),
                        "python_implementation": kn_module.get("python_implementation")
                    }
                else:
                    # 如果已存在，则只更新别名
                    self.knowledge_nodes[canonical_name]["aliases"].add(original_name)

                self.edges.append((scene_id, canonical_name))
        
        # 将别名集合转换为列表以便JSON序列化
        for node in self.knowledge_nodes.values():
            node["aliases"] = sorted(list(node["aliases"]))

        logger.info(f"Parsing complete. Found {len(self.knowledge_nodes)} unique (aligned) knowledge nodes and {len(self.scene_nodes)} scene nodes.")

    def save_databases(self, output_dir: str):
        # ... (此函数保持不变) ...
        os.makedirs(output_dir, exist_ok=True)
        kn_db_path = os.path.join(output_dir, "knowledge_nodes.json")
        sc_db_path = os.path.join(output_dir, "scene_nodes.json")
        with open(kn_db_path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_nodes, f, ensure_ascii=False, indent=4)
        with open(sc_db_path, 'w', encoding='utf-8') as f:
            json.dump(self.scene_nodes, f, ensure_ascii=False, indent=4)
        logger.info(f"Saved knowledge nodes to {kn_db_path}")
        logger.info(f"Saved scene nodes to {sc_db_path}")
        graph_path = os.path.join(output_dir, "bipartite_graph.graphml")
        B = nx.Graph()
        B.add_nodes_from(self.scene_nodes.keys(), bipartite=0)
        B.add_nodes_from(self.knowledge_nodes.keys(), bipartite=1)
        B.add_edges_from(self.edges)
        nx.write_graphml(B, graph_path)
        logger.info(f"Saved bipartite graph to {graph_path}")

    def create_and_save_indexes(self, output_dir: str):
        """通过API获取 embeddings，然后在客户端创建并保存 FAISS 索引。"""
        if not self.knowledge_nodes or not self.scene_nodes:
            logger.warning("No nodes to index. Skipping FAISS index creation.")
            return

        # 1. 索引知识节点
        logger.info("Requesting embeddings for knowledge nodes from API...")
        kn_ids = list(self.knowledge_nodes.keys())
        kn_texts = [
            f"{node['canonical_name']} [SEP] {node['concept_definition'].get('summary', '')}"
            for node in self.knowledge_nodes.values()
        ]
        kn_embeddings = self.api_client.encode(kn_texts)
        if kn_embeddings.size == 0:
            logger.error("Failed to get embeddings for knowledge nodes from API. Aborting index creation.")
            return
        
        kn_map_path = os.path.join(output_dir, "kn_id_map.json")
        kn_index_path = os.path.join(output_dir, "knowledge_nodes.faiss")
        with open(kn_map_path, 'w', encoding='utf-8') as f:
            json.dump(kn_ids, f, ensure_ascii=False)
        self.api_client.build_index_from_embeddings(kn_embeddings, kn_index_path)
        logger.info(f"Saved knowledge node FAISS index to {kn_index_path}")

        # 2. 索引场景节点
        # ... [这部分逻辑保持不变] ...
        logger.info("Requesting embeddings for scene nodes from API...")
        sc_ids = list(self.scene_nodes.keys())
        sc_texts = [node["source_question"] for node in self.scene_nodes.values()]
        sc_embeddings = self.api_client.encode(sc_texts)
        if sc_embeddings.size == 0:
            logger.error("Failed to get embeddings for scene nodes from API. Aborting index creation.")
            return
        sc_map_path = os.path.join(output_dir, "sc_id_map.json")
        sc_index_path = os.path.join(output_dir, "scene_nodes.faiss")
        with open(sc_map_path, 'w', encoding='utf-8') as f:
            json.dump(sc_ids, f, ensure_ascii=False)
        self.api_client.build_index_from_embeddings(sc_embeddings, sc_index_path)
        logger.info(f"Saved scene node FAISS index to {sc_index_path}")


def main(args: argparse.Namespace):
    """主执行函数。"""
    api_url = f"http://{settings.servers.host}:{settings.servers.retrieval_api_port}"
    api_client = RetrievalAPIClient(base_url=api_url)
    
    builder = KnowledgeBaseBuilder(api_client=api_client, alias_map_path=args.alias_map_file)
    builder.build_from_source(args.input_file)
    builder.save_databases(args.output_dir)
    builder.create_and_save_indexes(args.output_dir)
    logger.info("Knowledge base construction complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a structured knowledge base from a generated knowledge_base.json file, using an alias map for alignment.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--input-file", 
        type=str, 
        default="knowledge_base.json", 
        help="Path to the input knowledge_base.json file."
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="structured_knowledge_base", 
        help="Directory to save the structured database files (nodes, graph, indexes)."
    )
    # --- NEW: Argument for the alias map ---
    parser.add_argument(
        "--alias-map-file",
        type=str,
        default="alias_map.json",
        help="Path to the alias map file generated by the refinement script. If not found, will use rule-based alignment."
    )
    
    args = parser.parse_args()
    main(args)