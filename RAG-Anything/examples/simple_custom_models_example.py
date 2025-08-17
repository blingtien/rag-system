#!/usr/bin/env python
"""
Simple example demonstrating custom model integration with RAGAnything

This example shows the correct patterns for:
1. Local Qwen embedding model integration
2. DeepSeek API for LLM and vision
3. Proper RAGAnything initialization
"""

import os
import asyncio
import logging
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from raganything import RAGAnything
from raganything.custom_models import (
    get_qwen_embedding_func,
    deepseek_complete_if_cache,
    deepseek_vision_complete,
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Simple example following RAGAnything documentation patterns
    Environment variables are read within lambda functions, not through RAGAnything config
    """
    
    # Check required environment variables
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        logger.error("DEEPSEEK_API_KEY environment variable is required")
        return
    
    try:
        # Initialize Qwen embedding function using environment variables
        logger.info("Initializing Qwen embedding model...")
        embedding_func, embedding_dim = get_qwen_embedding_func(
            model_name=os.getenv("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"),
            device=os.getenv("EMBEDDING_DEVICE", "auto"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            max_length=int(os.getenv("EMBEDDING_MAX_LENGTH", "512")),
            cache_dir=os.getenv("MODEL_CACHE_DIR", "./models")
        )
        logger.info(f"Embedding dimension: {embedding_dim}")
        
        # Define LLM function that reads environment variables within the lambda
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return deepseek_complete_if_cache(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                temperature=float(os.getenv("TEMPERATURE", "0.0")),
                max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
                **kwargs,
            )
        
        # Define vision function that reads environment variables within the lambda
        def vision_model_func(prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs):
            return deepseek_vision_complete(
                model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl"),
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                image_data=image_data,
                messages=messages,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                **kwargs,
            )
        
        # Initialize RAGAnything following documented pattern
        rag = RAGAnything(
            working_dir=os.getenv("WORKING_DIR", "./rag_storage"),
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
            embedding_dim=embedding_dim,
            max_token_size=int(os.getenv("EMBEDDING_MAX_LENGTH", "512"))
        )
        
        logger.info("RAGAnything initialized successfully with custom models!")
        
        # Example: Process a document (you would replace with your document path)
        # await rag.process_document_complete(
        #     file_path="path/to/your/document.pdf",
        #     output_dir="./output",
        #     parse_method="auto"
        # )
        
        # Example: Query the processed content
        # result = await rag.aquery("What is this document about?", mode="hybrid")
        # logger.info(f"Query result: {result}")
        
        logger.info("Custom models integration completed successfully!")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("RAGAnything Custom Models Integration Example")
    print("=" * 50)
    print("Requirements:")
    print("1. Set DEEPSEEK_API_KEY environment variable")
    print("2. Install: pip install torch transformers")
    print("3. Qwen model will be downloaded automatically")
    print("=" * 50)
    
    asyncio.run(main())