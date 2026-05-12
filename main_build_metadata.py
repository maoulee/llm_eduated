# main_build_metadata.py
from core.llm_service import LLMService
from core.metadata_extractor import MetadataExtractor
from core.retriever import Retriever
import os
import json

# --- 配置 ---
LLM_MODEL_PATH = "/zhaoshu/llm/qwen3-32b/" # 换成你的模型路径
EMBEDDING_MODEL_PATH = "/zhaoshu/llm/BAAI/bge-m3/"
SEED_QUESTIONS_FILE = "/zhaoshu/mcts_reason/data/full_question.json"
METADATA_DB_FILE = "/zhaoshu/mcts_reason/artifacts/metadata_db_full.json"
FAISS_INDEX_FILE = "/zhaoshu/mcts_reason/artifacts/faiss_index_full.bin"

def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("artifacts", exist_ok=True)
    
    if not os.path.exists(SEED_QUESTIONS_FILE):
        sample_data = [
            {"prompt": "[2014年考研真题第15题]某容量为256MB的存储器由若干4M×8位的DRAM芯片构成，该DRAM芯片的地址引脚和数据引脚总数是。", "answer": "DRAM芯片容量为4M×8位 = 2^22×8位，存储单元数为2^22，地址线数为22。由于DRAM芯片采用地址复用技术，地址分两次传输，故地址引脚为22/2=11。数据引脚为8。总引脚数为11+8=19。"}
        ]
        with open(SEED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        print(f"Created a sample seed file at {SEED_QUESTIONS_FILE}. Please populate it with your data.")
        return

    print("Initializing LLM Service...")
    llm_service = LLMService(model_name=LLM_MODEL_PATH)

    print("\nBuilding Metadata Database...")
    extractor = MetadataExtractor(llm_service)
    extractor.build_metadata_database(SEED_QUESTIONS_FILE, METADATA_DB_FILE)

    print("\nBuilding FAISS Index...")
    retriever = Retriever(model_name=EMBEDDING_MODEL_PATH)
    retriever.build_index(METADATA_DB_FILE, FAISS_INDEX_FILE)

    print("\n--- Metadata and Index build process completed! ---")

if __name__ == "__main__":
    main()