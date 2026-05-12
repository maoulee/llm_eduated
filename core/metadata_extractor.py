from .prompts import METADATA_EXTRACTION_PROMPT
from .llm_service import LLMService
import json
from tqdm import tqdm

class MetadataExtractor:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def build_metadata_database(self, questions_file_path, output_db_path):
        with open(questions_file_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        # 1. 一次性构建所有请求
        messages_batch = []
        for question in questions:
            content = METADATA_EXTRACTION_PROMPT.format(
                prompt=question["prompt"],
                answer=question["answer"]
            )
            messages_batch.append([{"role": "user", "content": content}])

        print(f"Sending a batch of {len(questions)} requests for metadata extraction...")
        # 2. 批量调用LLM
        metadata_results = self.llm.generate_json_batch(messages_batch)
        
        # 3. 处理结果
        metadata_db = {}
        for i, metadata in enumerate(tqdm(metadata_results, desc="Processing Metadata Results")):
            if metadata:
                question = questions[i]
                metadata['original_prompt'] = question['prompt']
                metadata['original_answer'] = question['answer']
                metadata_db[f"q_{i}"] = metadata
        
        with open(output_db_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_db, f, ensure_ascii=False, indent=2)
        
        print(f"Metadata database built and saved to {output_db_path}")
        return metadata_db