# llm_providers_new/glm_batch_client.py

"""
GLM Batch API client using OpenAI-compatible interface.

The GLM API (https://open.bigmodel.cn/api/paas/v4) is fully OpenAI-compatible,
so we use the standard openai SDK directly — no need for a separate zhipuai SDK.
"""

import json
import logging
import os
import time
from typing import Dict, List

from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class GLMBatchClient:
    """GLM Batch API client via OpenAI-compatible interface."""

    def __init__(self, api_key: str, base_url: str = GLM_BASE_URL):
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def create_batch_input_file(self, requests: List[Dict], filename: str = "batch_input.jsonl") -> str:
        with open(filename, "w", encoding="utf-8") as f:
            for req in requests:
                f.write(json.dumps(req, ensure_ascii=False) + "\n")
        logger.info("Created batch input file: %s", filename)
        return filename

    def upload_file(self, filepath: str) -> str:
        logger.info("Uploading file: %s ...", filepath)
        file_object = self.client.files.create(file=open(filepath, "rb"), purpose="batch")
        logger.info("File uploaded. ID: %s", file_object.id)
        return file_object.id

    def create_batch_job(self, file_id: str, endpoint: str = "/v4/chat/completions",
                         metadata: Dict = None) -> str:
        logger.info("Creating batch job for file_id: %s ...", file_id)
        batch_job = self.client.batches.create(
            input_file_id=file_id, endpoint=endpoint, metadata=metadata or {},
        )
        logger.info("Batch job created. ID: %s", batch_job.id)
        return batch_job.id

    def monitor_job_status(self, batch_id: str, interval: int = 30) -> bool:
        logger.info("Monitoring batch_id: %s ...", batch_id)
        while True:
            status = self.client.batches.retrieve(batch_id)
            logger.info("  Status: %s", status.status)
            if status.status == "completed":
                logger.info("Batch job completed!")
                return True
            if status.status in ("failed", "expired", "cancelled"):
                logger.error("Batch job ended: %s", status.status)
                return False
            time.sleep(interval)

    def download_and_parse_results(self, batch_id: str, output_dir: str = ".") -> List[Dict]:
        logger.info("Downloading results ...")
        batch_info = self.client.batches.retrieve(batch_id)
        if not batch_info.output_file_id:
            logger.warning("No output file ID for this batch job.")
            return []

        output_filepath = os.path.join(output_dir, f"{batch_id}_results.jsonl")
        content = self.client.files.content(batch_info.output_file_id)
        content.write_to_file(output_filepath)
        logger.info("Results saved to: %s", output_filepath)

        results = []
        with open(output_filepath, encoding="utf-8") as f:
            for line in f:
                results.append(json.loads(line))
        return results

    def run_full_batch_process(self, requests: List[Dict], job_description: str) -> List[Dict]:
        input_file = self.create_batch_input_file(requests)
        file_id = self.upload_file(input_file)
        batch_id = self.create_batch_job(file_id, metadata={"description": job_description})

        if self.monitor_job_status(batch_id):
            return self.download_and_parse_results(batch_id)

        logger.error("Batch process failed.")
        return []
