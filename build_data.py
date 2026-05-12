# main_build_metadata_new.py

"""
数据准备脚本：
1. 从源文件加载问题和答案。
2. 使用LLM提取元数据（知识点、实体等）。
3. 使用嵌入模型构建并保存FAISS向量索引。
此脚本为整个系统的检索功能提供数据基础。
"""
import asyncio
import logging
from rich.console import Console

# --- 从重构后的模块导入 ---
from config import settings, get_provider_config
from core_new.metadata_extractor import MetadataExtractor
from core_new.retriever import Retriever
from llm_providers_new import get_llm_provider

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """
    异步主函数，执行元数据提取和索引构建的完整流程。
    """
    console = Console()
    console.rule("[bold cyan]Data Preparation: Metadata and FAISS Index[/bold cyan]")

    # 1. 初始化服务
    # 元数据提取是一次性批量任务，通常使用本地模型更具成本效益
    console.print("--> Initializing LLM Service for metadata extraction (local mode recommended)...")
    try:
        # 强制使用'local' provider进行数据准备
        provider_config = get_provider_config("local")
        llm_provider = get_llm_provider(provider_config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM Provider: {e}[/bold red]")
        logger.error("Failed to initialize LLM provider.", exc_info=True)
        return

    # 2. 提取元数据
    console.print(f"\n--> Step 1: Extracting metadata from [green]{settings.paths.seed_questions}[/green]")
    extractor = MetadataExtractor(llm_provider)
    try:
        # 调用重构后的异步方法
        await extractor.build_database_from_file(
            questions_file_path=settings.paths.seed_questions,
            output_db_path=settings.paths.metadata_db
        )
        console.print(f"--> Metadata database saved to [green]{settings.paths.metadata_db}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error during metadata extraction: {e}[/bold red]")
        logger.error("Metadata extraction process failed.", exc_info=True)
        return

    # 3. 构建FAISS索引
    console.print(f"\n--> Step 2: Building FAISS index from [green]{settings.paths.metadata_db}[/green]")
    try:
        # Retriever的初始化和build_index是同步的，因为它们是计算密集型任务
        retriever = Retriever(model_name=settings.embedding_model_path)
        retriever.build_index(
            metadata_db_path=settings.paths.metadata_db,
            output_index_path=settings.paths.faiss_index
        )
        console.print(f"--> FAISS index saved to [green]{settings.paths.faiss_index}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error during FAISS index building: {e}[/bold red]")
        logger.error("FAISS index building process failed.", exc_info=True)
        return

    console.print("\n[bold bright_green]✅ Data preparation process completed successfully![/bold bright_green]")


if __name__ == "__main__":
    # 因为main是异步函数，所以使用asyncio.run()来启动
    asyncio.run(main())