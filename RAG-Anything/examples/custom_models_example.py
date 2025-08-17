#!/usr/bin/env python
"""
Example script demonstrating custom model integration with RAGAnything

This example shows how to:
1. Use local Qwen embedding model for text vectorization
2. Use DeepSeek API for LLM text generation and vision processing
3. Configure the complete RAGAnything pipeline with custom models
4. Process documents and perform queries with the custom setup
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

from lightrag.utils import logger, set_verbose_debug
from raganything import RAGAnything
from raganything.custom_models import (
    get_qwen_embedding_func,
    deepseek_complete_if_cache,
    deepseek_vision_complete,
    validate_custom_models
)

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=False)


def configure_logging():
    """Configure logging for the application"""
    # Get log directory path from environment variable or use current directory
    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(os.path.join(log_dir, "custom_models_example.log"))

    print(f"\nCustom Models RAGAnything example log file: {log_file_path}\n")
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


async def process_with_custom_models(
    file_path: str,
    output_dir: str,
    working_dir: str = None,
    parser: str = None,
):
    """
    Process document with RAGAnything using custom models

    Args:
        file_path: Path to the document
        output_dir: Output directory for RAG results
        working_dir: Working directory for RAG storage
        parser: Parser to use (mineru or docling)
    """
    try:
        # Validate custom models setup
        logger.info("Validating custom models configuration...")
        validation_results = validate_custom_models()
        
        for check, result in validation_results.items():
            status = "✓" if result else "✗"
            logger.info(f"  {status} {check}: {result}")
        
        if not validation_results["deepseek_api_configured"]:
            raise ValueError("DeepSeek API not configured. Please set DEEPSEEK_API_KEY environment variable.")
        
        if not validation_results["torch_available"]:
            raise ValueError("PyTorch not available. Please install torch>=2.0.0")
        
        if not validation_results["transformers_available"]:
            raise ValueError("Transformers not available. Please install transformers>=4.30.0")

        # Get environment variables for configuration
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        deepseek_vision_model = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl-chat")
        
        logger.info(f"Using DeepSeek model: {deepseek_model}")
        logger.info(f"Using DeepSeek vision model: {deepseek_vision_model}")

        # Define LLM model function using DeepSeek
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return deepseek_complete_if_cache(
                model=deepseek_model,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=deepseek_api_key,
                base_url=deepseek_base_url,
                temperature=float(os.getenv("TEMPERATURE", "0.0")),
                max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
                **kwargs,
            )

        # Define vision model function using DeepSeek vision model
        def vision_model_func(
            prompt,
            system_prompt=None,
            history_messages=[],
            image_data=None,
            messages=None,
            **kwargs,
        ):
            return deepseek_vision_complete(
                model=deepseek_vision_model,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                image_data=image_data,
                messages=messages,
                api_key=deepseek_api_key,
                base_url=deepseek_base_url,
                **kwargs,
            )

        # Create Qwen embedding function
        logger.info("Initializing Qwen embedding model...")
        embedding_func, embedding_dim = get_qwen_embedding_func(
            model_name=os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"),
            device=os.getenv("EMBEDDING_DEVICE", "auto"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            max_length=int(os.getenv("EMBEDDING_MAX_LENGTH", "512")),
            cache_dir=os.getenv("MODEL_CACHE_DIR", "./models"),
        )
        logger.info(f"Qwen embedding model initialized with dimension: {embedding_dim}")

        # Create LightRAG EmbeddingFunc object
        from lightrag.utils import EmbeddingFunc
        embedding_func_obj = EmbeddingFunc(
            embedding_dim=embedding_dim,
            max_token_size=int(os.getenv("EMBEDDING_MAX_LENGTH", "512")),
            func=embedding_func
        )
        
        # Initialize RAGAnything with custom models following the documented pattern
        rag = RAGAnything(
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func_obj,
            lightrag_kwargs={
                "working_dir": working_dir or "./rag_storage"
            }
        )

        # Process document with specified parser
        logger.info(f"Processing document: {file_path}")
        await rag.process_document_complete(
            file_path=file_path, 
            output_dir=output_dir, 
            parse_method="auto"  # MinerU支持的方法: auto, txt, ocr
        )

        # Example queries - demonstrating different query approaches
        logger.info("\nQuerying processed document with custom models:")

        # 1. Pure text queries using aquery()
        text_queries = [
            "What is the main content of the document?",
            "What are the key topics discussed?", 
            "Summarize the most important findings.",
        ]

        for query in text_queries:
            logger.info(f"\n[Text Query]: {query}")
            result = await rag.aquery(query, mode="hybrid")
            logger.info(f"Answer: {result}")

        # 2. Multimodal query with specific multimodal content
        logger.info("\n[Multimodal Query]: Analyzing performance data with custom models")
        multimodal_result = await rag.aquery_with_multimodal(
            "Compare this performance data with any similar results mentioned in the document",
            multimodal_content=[
                {
                    "type": "table",
                    "table_data": """Model,Accuracy,Inference_Time,Memory_Usage
                                Custom_RAG_Qwen,96.8%,85ms,2.1GB
                                OpenAI_RAG,94.2%,150ms,N/A
                                Local_RAG,91.5%,120ms,1.8GB""",
                    "table_caption": "Performance comparison with custom models",
                }
            ],
            mode="hybrid",
        )
        logger.info(f"Answer: {multimodal_result}")

        # 3. Test VLM enhanced query if vision model is available
        logger.info("\n[VLM Enhanced Query]: Testing vision capabilities")
        vlm_result = await rag.aquery(
            "Describe any visual elements, charts, or diagrams in the document",
            mode="hybrid",
            vlm_enhanced=True
        )
        logger.info(f"Answer: {vlm_result}")

        # 4. Different retrieval modes comparison
        logger.info("\n[Retrieval Mode Comparison]: Testing different modes")
        test_query = "What are the main conclusions?"
        
        modes = ["naive", "local", "global", "hybrid"]
        for mode in modes:
            logger.info(f"\n  Mode '{mode}':")
            result = await rag.aquery(test_query, mode=mode)
            logger.info(f"  Result: {result[:200]}..." if len(result) > 200 else f"  Result: {result}")

    except Exception as e:
        logger.error(f"Error processing with custom models: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def main():
    """Main function to run the example"""
    parser = argparse.ArgumentParser(description="Custom Models RAG Example")
    parser.add_argument("file_path", help="Path to the document to process")
    parser.add_argument(
        "--working_dir", "-w", default="./rag_storage", help="Working directory path"
    )
    parser.add_argument(
        "--output", "-o", default="./output", help="Output directory path"
    )
    parser.add_argument(
        "--parser",
        default=os.getenv("PARSER", "mineru"),
        help="Parser to use (mineru or docling)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate configuration without processing document"
    )

    args = parser.parse_args()

    # Validate configuration
    print("Custom Models Configuration Validation")
    print("=" * 50)
    
    validation_results = validate_custom_models()
    all_valid = True
    
    for check, result in validation_results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} {check}")
        if not result:
            all_valid = False
    
    print("=" * 50)
    
    if not all_valid:
        print("\nConfiguration issues detected:")
        if not validation_results["deepseek_api_configured"]:
            print("- Set DEEPSEEK_API_KEY environment variable")
        if not validation_results["torch_available"]:
            print("- Install PyTorch: pip install torch>=2.0.0")
        if not validation_results["transformers_available"]:
            print("- Install Transformers: pip install transformers>=4.30.0")
        if not validation_results["qwen_model_available"]:
            print("- Qwen model will be downloaded on first use")
    
    if args.validate_only:
        print(f"\nValidation complete. Overall status: {'PASS' if all_valid else 'ISSUES DETECTED'}")
        return

    if not validation_results["deepseek_api_configured"]:
        logger.error("Error: DeepSeek API key is required")
        logger.error("Set DEEPSEEK_API_KEY environment variable")
        return

    # Create output directory if specified
    if args.output:
        os.makedirs(args.output, exist_ok=True)

    # Process with custom models
    asyncio.run(
        process_with_custom_models(
            args.file_path,
            args.output,
            args.working_dir,
            args.parser,
        )
    )


if __name__ == "__main__":
    # Configure logging first
    configure_logging()

    print("RAGAnything Custom Models Example")
    print("=" * 40)
    print("Using:")
    print("- Local Qwen embedding model for text vectorization")
    print("- DeepSeek API for LLM text generation and vision")
    print("=" * 40)

    main()