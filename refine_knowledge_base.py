# refine_knowledge_base.py (Clustering-Based Final & Complete Version)

import json
import logging
import os
import argparse
import re
from collections import defaultdict
import asyncio

import numpy as np
# 导入聚类和归一化工具
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import normalize as sk_normalize

# 导入项目模块
from core_new.retrieval_api_client import RetrievalAPIClient
from llm_providers_new import get_llm_provider
from config import get_provider_config, settings
from typing import Dict, List

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- LLM 对齐的 Prompt (附带高质量范例) ---
ALIGNMENT_PROMPT = """你是一位顶级的知识图谱构建专家。你的任务是对以下计算机科学领域的“知识点名称”列表进行语义聚类和归一化。

**核心指令**:
1.  **识别同义词**: 识别出那些虽然字面不同，但实际上指向同一个核心概念或算法的名称。
2.  **选择首选名称**: 为每一个语义簇选择一个最简洁、最通用、最具代表性的名称作为“首选名称 (Canonical Name)”。
3.  **保留独特性**: 如果一个名称本身已经足够独特和规范，就让它自成一簇。
4.  **严格的JSON输出**: 你的输出必须是一个JSON对象。其中，键(key)是“首选名称”，值(value)是一个包含所有属于该簇的原始名称的列表。

---
[范例]
这是一个你需要严格模仿的思维过程和输出格式。

**范例输入 (待处理的知识点名称列表)**:
- CRC余数计算 (模2除法)
- 循环冗余校验码计算
- 补码到真值的转换
- 补码表示与转换
- 8位补码系统
- 指令扩展编码原理

**范例输出 (你的目标JSON)**:
```json
{{
  "CRC校验码计算": [
    "CRC余数计算 (模2除法)",
    "循环冗余校验码计算"
  ],
  "补码转换": [
    "补码到真值的转换",
    "补码表示与转换",
    "8位补码系统"
  ],
  "指令扩展编码原理": [
    "指令扩展编码原理"
  ]
}}
```
---
[正式任务]
现在，请为以下的[待处理的知识点名称列表]生成JSON格式的聚类结果。

[待处理的知识点名称列表]
{candidate_names_str}

[输出JSON]：
"""


class KnowledgeAligner:
    """
    一个用于对知识库中的知识点进行对齐和合并的工具类。
    采用 "嵌入 -> DBSCAN聚类 -> LLM精炼" 的流程。
    """
    def __init__(self, api_client: RetrievalAPIClient, llm_provider):
        self.api_client = api_client
        self.llm = llm_provider
        self.all_unique_names: List[str] = []
        self.embeddings: np.ndarray = None

    def load_knowledge_names(self, source_file: str):
        """从 knowledge_base.json 中加载所有唯一的知识点名称。"""
        logger.info(f"--- Stage 1: Loading Unique Names from {source_file} ---")
        unique_names_set = set()
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data.values():
                if item and "universal_knowledge_modules" in item:
                    for module in item["universal_knowledge_modules"]:
                        if "knowledge_point_name" in module:
                            unique_names_set.add(module["knowledge_point_name"])
            self.all_unique_names = sorted(list(unique_names_set))
            logger.info(f"Found {len(self.all_unique_names)} unique knowledge point names.")
        except Exception as e:
            logger.error(f"Failed to load or parse {source_file}: {e}", exc_info=True)

    def encode_names(self):
        """对所有唯一的知识点名称进行嵌入编码。"""
        if not self.all_unique_names:
            logger.warning("No names to encode.")
            return
            
        logger.info(f"--- Stage 2: Encoding {len(self.all_unique_names)} Names via API ---")
        embeddings = self.api_client.encode(self.all_unique_names)
        if embeddings.size > 0:
            self.embeddings = sk_normalize(embeddings, norm='l2')
            logger.info("Successfully encoded and L2-normalized embeddings.")
        else:
            logger.error("Failed to get embeddings from API.")
            self.embeddings = None

    def cluster_names_with_dbscan(self, eps: float, min_samples: int) -> Dict[str, List[str]]:
        """基于嵌入向量使用DBSCAN算法进行类别聚类。"""
        if self.embeddings is None:
            logger.error("Embeddings not available. Cannot perform clustering.")
            return {}
        
        logger.info(f"--- Stage 3: Clustering Names with DBSCAN (eps={eps}, min_samples={min_samples}) ---")
        
        db = DBSCAN(eps=eps, min_samples=min_samples, metric='euclidean').fit(self.embeddings)
        labels = db.labels_
        
        clusters = defaultdict(list)
        for name, label in zip(self.all_unique_names, labels):
            if label != -1: # label = -1 表示是噪音点 (独特的知识点)
                clusters[f"cluster_{label}"].append(name)
        
        logger.info(f"DBSCAN found {len(clusters)} potential clusters to be refined by LLM.")
        for label, names in clusters.items():
            logger.info(f"  - {label}: {names}")
            
        return dict(clusters)

    async def refine_clusters_with_llm(self, clusters: Dict[str, List[str]]) -> Dict[str, str]:
        """阶段四：对每个聚类出的类别，使用大模型进行精细对齐。"""
        if not clusters:
            logger.info("No clusters to refine.")
            return {}
            
        logger.info(f"--- Stage 4: Refining {len(clusters)} Clusters with LLM ---")
        
        final_alias_map = {}
        failed_clusters_count = 0

        # --- NEW: Process clusters one by one for clarity and robustness ---
        for cluster_id, names in clusters.items():
            logger.info(f"  - Processing cluster '{cluster_id}': {names}")
            
            # 调用LLM处理单个簇
            # _refine_single_cluster 现在返回一个类似 {'别名': '首选名'} 的字典
            alias_map_for_cluster = await self._refine_single_cluster(names)
            
            if alias_map_for_cluster:
                logger.info(f"    - LLM Result: {alias_map_for_cluster}")
                # 直接将这个小字典合并到最终的大字典中
                final_alias_map.update(alias_map_for_cluster)
            else:
                logger.warning(f"    - Failed to get alignment for cluster '{cluster_id}'. Skipping.")
                failed_clusters_count += 1
        
        logger.info("--- Stage 4 Summary ---")
        logger.info(f"  - Successfully refined {len(clusters) - failed_clusters_count} clusters.")
        if failed_clusters_count > 0:
            logger.warning(f"  - Failed to refine {failed_clusters_count} clusters. Please check logs.")
        logger.info(f"  - Total new alias mappings created: {len(final_alias_map)}")
        
        return final_alias_map

    async def _refine_single_cluster(self, cluster_names: List[str], max_attempts: int = 2) -> Dict[str, str]:
        """对单个聚类调用LLM，带有重试机制。返回一个 {'别名': '首选名'} 字典。"""
        candidate_names_str = "\n".join([f"- {name}" for name in cluster_names])
        base_prompt = ALIGNMENT_PROMPT.format(candidate_names_str=candidate_names_str)
        
        for attempt in range(max_attempts):
            current_prompt = base_prompt
            if attempt > 0:
                current_prompt += "\n\n[重要提醒] 你的上一次输出未能成功解析为JSON。请严格遵循指令，只返回一个完整的JSON对象。"
            
            messages = [[{"role": "user", "content": current_prompt}]]
            json_outputs = await self.llm.generate_json_batch(messages, max_tokens=1024)
            
            if json_outputs and isinstance(json_outputs[0], dict):
                llm_cluster_result = json_outputs[0]
                # --- REFINED PARSING LOGIC ---
                # 这个函数现在只负责从LLM的输出中构建并返回一个干净的别名映射
                alias_map = {}
                try:
                    for canonical, aliases in llm_cluster_result.items():
                        if not isinstance(aliases, list):
                            logger.warning(f"    - LLM returned non-list aliases for cluster {cluster_names}: {aliases}")
                            continue # 跳过这个错误的条目
                        for alias in aliases:
                            if alias != canonical:
                                alias_map[alias] = canonical
                    return alias_map # 成功解析并构建了映射
                except Exception as e:
                    logger.error(f"    - Error parsing LLM JSON structure for cluster {cluster_names}: {e}")
                    # 继续下一次重试
            
        logger.error(f"  - Failed to refine cluster after {max_attempts} attempts: {cluster_names}")
        return {} # 所有尝试都失败了，返回空字典

    def save_alias_map(self, alias_map: Dict[str, str], output_file: str):
        """保存别名映射文件。"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(alias_map, f, ensure_ascii=False, indent=4)
            logger.info(f"Successfully saved final alias map with {len(alias_map)} entries to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save alias map: {e}")


async def main(args: argparse.Namespace):
    """主执行函数。"""
    api_url = f"http://{settings.servers.host}:{settings.servers.retrieval_api_port}"
    api_client = RetrievalAPIClient(base_url=api_url)
    
    provider_config = get_provider_config(args.llm_model)
    llm_provider = get_llm_provider(provider_config)
    
    aligner = KnowledgeAligner(api_client, llm_provider)
    
    # 严格按照四步流程执行
    aligner.load_knowledge_names(args.input_file)
    aligner.encode_names()
    clusters = aligner.cluster_names_with_dbscan(eps=args.dbscan_eps, min_samples=args.dbscan_min_samples)
    
    if clusters:
        final_alias_map = await aligner.refine_clusters_with_llm(clusters)
        aligner.save_alias_map(final_alias_map, args.output_file)
    else:
        logger.info("No clusters were found. No alias map will be generated.")

    logger.info("Knowledge alignment process complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Refine the knowledge base using clustering and LLM refinement.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--input-file", 
        type=str, 
        default="knowledge_base.json", 
        help="Path to the input knowledge_base.json file."
    )
    parser.add_argument(
        "--output-file", 
        type=str, 
        default="alias_map.json", 
        help="Path to save the output alias map JSON file."
    )
    parser.add_argument(
        "--llm-model", 
        type=str, 
        default="qwen3_local_aligner", 
        help="The LLM provider name for the refinement step."
    )
    
    parser.add_argument(
        "--dbscan-eps",
        type=float,
        default=0.3,
        help="DBSCAN 'eps' parameter. The maximum distance between two samples for one to be considered as in the neighborhood of the other. (Try values between 0.1 and 0.5)"
    )
    parser.add_argument(
        "--dbscan-min-samples",
        type=int,
        default=2,
        help="DBSCAN 'min_samples' parameter. The number of samples in a neighborhood for a point to be considered as a core point."
    )
    
    args = parser.parse_args()
    
    logger.info("Please ensure the retrieval API server is running for embedding tasks.")
    asyncio.run(main(args))