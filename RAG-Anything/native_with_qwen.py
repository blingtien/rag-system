#!/usr/bin/env python
"""
基于原生raganything_example.py的最小修改版本
只替换embedding函数，其他保持原生代码不变
使用DeepSeek LLM + 本地Qwen embedding
"""

import os
import argparse
import asyncio
import logging
import logging.config
from pathlib import Path

# Add project root directory to Python path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug
from raganything import RAGAnything, RAGAnythingConfig

# 导入我们的简单Qwen嵌入函数
from simple_qwen_embed import qwen_embed

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=False)


def configure_logging():
    """Configure logging for the application"""
    # Get log directory path from environment variable or use current directory
    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(os.path.join(log_dir, "native_with_qwen.log"))

    print(f"\nNative RAGAnything with Qwen log file: {log_file_path}\n")
    os.makedirs(os.path.dirname(log_dir), exist_ok=True)

    # Get log file max size and backup count from environment variables
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", 10485760))  # Default 10MB
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", 5))  # Default 5 backups

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s: %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "formatter": "detailed",
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file_path,
                    "maxBytes": log_max_bytes,
                    "backupCount": log_backup_count,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "lightrag": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )

    # Set the logger level to INFO
    logger.setLevel(logging.INFO)
    # Enable verbose debug if needed
    set_verbose_debug(os.getenv("VERBOSE", "false").lower() == "true")


async def process_with_rag(
    file_path: str,
    output_dir: str,
    api_key: str,
    base_url: str = None,
    working_dir: str = None,
    parser: str = None,
):
    """
    Process document with RAGAnything using DeepSeek LLM + Qwen embedding

    Args:
        file_path: Path to the document
        output_dir: Output directory for RAG results
        api_key: DeepSeek API key
        base_url: DeepSeek API base URL
        working_dir: Working directory for RAG storage
        parser: Parser to use (mineru or docling)
    """
    try:
        # Create RAGAnything configuration
        config = RAGAnythingConfig(
            working_dir=working_dir or "./rag_storage",
            parser=parser or "mineru",  # Parser selection: mineru or docling
            parse_method="auto",  # Parse method: auto, ocr, or txt
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )

        # Define LLM model function using DeepSeek
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                "deepseek-chat",  # 使用deepseek-chat模型
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )

        # Define vision model function for image processing using DeepSeek
        def vision_model_func(
            prompt,
            system_prompt=None,
            history_messages=[],
            image_data=None,
            messages=None,
            **kwargs,
        ):
            # If messages format is provided (for multimodal VLM enhanced query), use it directly
            if messages:
                return openai_complete_if_cache(
                    "deepseek-vl",  # 使用deepseek-vl模型
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=messages,
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            # Traditional single image format
            elif image_data:
                return openai_complete_if_cache(
                    "deepseek-vl",
                    "",
                    system_prompt=None,
                    history_messages=[],
                    messages=[
                        {"role": "system", "content": system_prompt}
                        if system_prompt
                        else None,
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    },
                                },
                            ],
                        }
                        if image_data
                        else {"role": "user", "content": prompt},
                    ],
                    api_key=api_key,
                    base_url=base_url,
                    **kwargs,
                )
            # Pure text format
            else:
                return llm_model_func(prompt, system_prompt, history_messages, **kwargs)

        # Define embedding function using local Qwen model
        # 关键修改：使用本地Qwen模型替代OpenAI embedding
        embedding_func = EmbeddingFunc(
            embedding_dim=1024,  # Qwen3-Embedding-0.6B的维度
            max_token_size=512,   # Qwen模型的最大token长度
            func=qwen_embed,      # 使用我们的本地Qwen嵌入函数
        )

        logger.info("Configuration:")
        logger.info(f"  LLM: DeepSeek API at {base_url}")
        logger.info(f"  Embedding: Local Qwen3-Embedding-0.6B (1024 dim)")
        logger.info(f"  Parser: {parser or 'mineru'}")

        # Initialize RAGAnything with new dataclass structure
        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
        )

        # Process document
        await rag.process_document_complete(
            file_path=file_path, output_dir=output_dir, parse_method="auto"
        )

        # Example queries - demonstrating different query approaches
        logger.info("\nQuerying processed document:")

        # 1. Pure text queries using aquery()
        text_queries = [
            "What is the main content of the document?",
            "What are the key topics discussed?",
        ]

        for query in text_queries:
            logger.info(f"\n[Text Query]: {query}")
            # 禁用VLM增强查询，避免DeepSeek视觉API格式问题
            result = await rag.aquery(query, mode="hybrid", vlm_enhanced=False)
            logger.info(f"Answer: {result}")

        # 2. Multimodal query with specific multimodal content using aquery_with_multimodal()
        logger.info(
            "\n[Multimodal Query]: Analyzing performance data in context of document"
        )
        multimodal_result = await rag.aquery_with_multimodal(
            "Compare this performance data with any similar results mentioned in the document",
            multimodal_content=[
                {
                    "type": "table",
                    "table_data": """Method,Accuracy,Processing_Time
                                RAGAnything_DeepSeek,95.2%,120ms
                                Traditional_RAG,87.3%,180ms
                                Baseline,82.1%,200ms""",
                    "table_caption": "Performance comparison with DeepSeek + Qwen",
                }
            ],
            mode="hybrid",
        )
        logger.info(f"Answer: {multimodal_result}")

        logger.info("\n✅ Processing completed successfully!")

    except Exception as e:
        logger.error(f"Error processing with RAG: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def main():
    """Main function to run the example"""
    parser = argparse.ArgumentParser(description="Native RAGAnything with DeepSeek + Qwen")
    parser.add_argument("file_path", help="Path to the document to process")
    parser.add_argument(
        "--working_dir", "-w", default="./rag_storage", help="Working directory path"
    )
    parser.add_argument(
        "--output", "-o", default="./output", help="Output directory path"
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("LLM_BINDING_API_KEY", os.getenv("DEEPSEEK_API_KEY")),
        help="DeepSeek API key",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1"),
        help="DeepSeek API base URL",
    )
    parser.add_argument(
        "--parser",
        default=os.getenv("PARSER", "mineru"),
        help="Parser to use (mineru or docling)",
    )

    args = parser.parse_args()

    # Check if API key is provided
    if not args.api_key:
        logger.error("Error: DeepSeek API key is required")
        logger.error("Set DEEPSEEK_API_KEY environment variable or use --api-key option")
        return

    # Create output directory if specified
    if args.output:
        os.makedirs(args.output, exist_ok=True)

    print("Native RAGAnything with DeepSeek + Qwen")
    print("=" * 45)
    print("Configuration:")
    print(f"  LLM: DeepSeek API")
    print(f"  Embedding: Local Qwen3-Embedding-0.6B")
    print(f"  Document: {args.file_path}")
    print("=" * 45)

    # Process with RAG
    asyncio.run(
        process_with_rag(
            args.file_path,
            args.output,
            args.api_key,
            args.base_url,
            args.working_dir,
            args.parser,
        )
    )


if __name__ == "__main__":
    # Configure logging first
    configure_logging()
    main()