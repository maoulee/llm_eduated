# llm_providers_new/glm_batch_client.py

import json
import logging
import time
import os
from typing import List, Dict, Any
from zai import ZhipuAiClient

try:
    from zhipuai import ZhipuAI
except ImportError:
    raise ImportError("ZhipuAI SDK not installed. Please run 'pip install zhipuai'.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GLMBatchClient:
    """
    一个封装了智谱AI Batch API完整流程的客户端。
    """
    def __init__(self, api_key: str):
        self.client = ZhipuAiClient(api_key=api_key)

    def create_batch_input_file(self, requests: List[Dict], filename: str = "batch_input.jsonl"):
        """根据请求列表创建符合Batch API格式的 .jsonl 文件。"""
        with open(filename, 'w', encoding='utf-8') as f:
            for req in requests:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
        logger.info(f"Successfully created batch input file: {filename}")
        return filename

    def upload_file(self, filepath: str) -> str:
        """上传文件并返回文件ID。"""
        logger.info(f"Uploading file: {filepath}...")
        try:
            file_object = self.client.files.create(file=open(filepath, "rb"), purpose="batch")
            logger.info(f"File uploaded successfully. File ID: {file_object.id}")
            return file_object.id
        except Exception as e:
            logger.error(f"File upload failed: {e}", exc_info=True)
            raise

    def create_batch_job(self, file_id: str, endpoint: str = "/v4/chat/completions", metadata: Dict = None) -> str:
        """创建批处理任务并返回任务ID。"""
        logger.info(f"Creating batch job for file_id: {file_id}...")
        try:
            batch_job = self.client.batches.create(
                input_file_id=file_id,
                endpoint=endpoint,
                metadata=metadata or {}
            )
            logger.info(f"Batch job created successfully. Batch ID: {batch_job.id}")
            return batch_job.id
        except Exception as e:
            logger.error(f"Batch job creation failed: {e}", exc_info=True)
            raise

    def monitor_job_status(self, batch_id: str, interval: int = 30) -> bool:
        """监控任务状态，直到完成或失败。"""
        logger.info(f"Monitoring status for batch_id: {batch_id}...")
        while True:
            try:
                status = self.client.batches.retrieve(batch_id)
                logger.info(f"  - Current status: {status.status}")
                if status.status == "completed":
                    logger.info("Batch job completed successfully!")
                    return True
                elif status.status in ["failed", "expired", "cancelled"]:
                    logger.error(f"Batch job ended with status: {status.status}")
                    return False
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Failed to retrieve batch status: {e}", exc_info=True)
                # In case of API error during monitoring, wait and retry
                time.sleep(interval * 2)


    def download_and_parse_results(self, batch_id: str, output_dir: str = ".") -> List[Dict]:
        """下载并解析成功的结果文件。"""
        logger.info("Downloading and parsing results...")
        try:
            batch_info = self.client.batches.retrieve(batch_id)
            if batch_info.output_file_id:
                output_filepath = os.path.join(output_dir, f"{batch_id}_results.jsonl")
                content = self.client.files.content(batch_info.output_file_id)
                content.write_to_file(output_filepath)
                logger.info(f"Results downloaded to: {output_filepath}")
                
                # 解析结果文件
                results = []
                with open(output_filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        results.append(json.loads(line))
                return results
            else:
                logger.warning("No output file ID found for this batch job.")
                return []
        except Exception as e:
            logger.error(f"Failed to download or parse results: {e}", exc_info=True)
            return []

    def run_full_batch_process(self, requests: List[Dict], job_description: str) -> List[Dict]:
        """执行完整的批处理流程：创建文件 -> 上传 -> 创建任务 -> 监控 -> 下载结果。"""
        input_file = self.create_batch_input_file(requests)
        file_id = self.upload_file(input_file)
        batch_id = self.create_batch_job(file_id, metadata={"description": job_description})
        
        if self.monitor_job_status(batch_id):
            return self.download_and_parse_results(batch_id)
        else:
            logger.error("Batch process failed. No results will be returned.")
            return []