#!/usr/bin/env python
"""
Environment Configuration Validation Script for RAG-Anything

This script validates that environment variables are correctly configured
according to RAG-Anything's requirements and custom models integration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def validate_environment():
    """Validate environment configuration"""
    
    # Load .env file
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from: {env_path}")
    else:
        print(f"✗ No .env file found at: {env_path}")
        return False
    
    print("\n" + "="*60)
    print("RAG-ANYTHING ENVIRONMENT VALIDATION")
    print("="*60)
    
    validation_results = {}
    
    # Core RAG-Anything Configuration
    print("\n📁 CORE CONFIGURATION:")
    core_vars = {
        "WORKING_DIR": "./rag_storage",
        "OUTPUT_DIR": "./output", 
        "PARSER": "mineru",
        "PARSE_METHOD": "auto"
    }
    
    for var, default in core_vars.items():
        value = os.getenv(var, default)
        print(f"  {var}: {value}")
        validation_results[var] = value is not None
    
    # LLM Configuration
    print("\n🤖 LLM CONFIGURATION:")
    llm_vars = {
        "LLM_BINDING": "openai",
        "LLM_MODEL": "gpt-4o", 
        "LLM_BINDING_API_KEY": "REQUIRED",
        "TEMPERATURE": "0",
        "MAX_TOKENS": "32768"
    }
    
    for var, expected in llm_vars.items():
        value = os.getenv(var)
        if var == "LLM_BINDING_API_KEY":
            status = "✓ SET" if value else "✗ MISSING (REQUIRED)"
            print(f"  {var}: {status}")
        else:
            print(f"  {var}: {value or 'NOT SET'}")
        validation_results[var] = value is not None
    
    # Embedding Configuration  
    print("\n🔗 EMBEDDING CONFIGURATION:")
    embed_vars = {
        "EMBEDDING_BINDING": "ollama",
        "EMBEDDING_MODEL": "bge-m3:latest",
        "EMBEDDING_DIM": "1024",
        "EMBEDDING_BINDING_HOST": "http://localhost:11434"
    }
    
    for var, expected in embed_vars.items():
        value = os.getenv(var)
        print(f"  {var}: {value or 'NOT SET'}")
        validation_results[var] = value is not None
    
    # Custom Models Configuration
    print("\n🎯 CUSTOM MODELS CONFIGURATION:")
    custom_vars = {
        "DEEPSEEK_API_KEY": "REQUIRED FOR CUSTOM MODELS",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "DEEPSEEK_VISION_MODEL": "deepseek-vl",
        "QWEN_MODEL_NAME": "Qwen/Qwen3-Embedding-0.6B",
        "EMBEDDING_DEVICE": "auto",
        "MODEL_CACHE_DIR": "./models"
    }
    
    for var, note in custom_vars.items():
        value = os.getenv(var)
        if "REQUIRED" in note:
            status = "✓ SET" if value else "✗ MISSING (for custom models)"
            print(f"  {var}: {status}")
        else:
            print(f"  {var}: {value or 'NOT SET'}")
        validation_results[var] = value is not None
    
    # Multimodal Processing
    print("\n🖼️ MULTIMODAL PROCESSING:")
    multimodal_vars = {
        "ENABLE_IMAGE_PROCESSING": "true",
        "ENABLE_TABLE_PROCESSING": "true", 
        "ENABLE_EQUATION_PROCESSING": "true",
        "CONTEXT_WINDOW": "1",
        "MAX_CONTEXT_TOKENS": "2000"
    }
    
    for var, expected in multimodal_vars.items():
        value = os.getenv(var)
        print(f"  {var}: {value or 'NOT SET'}")
        validation_results[var] = value is not None
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    required_for_basic = ["LLM_BINDING_API_KEY"]
    required_for_custom = ["DEEPSEEK_API_KEY"]
    
    basic_ready = all(validation_results.get(var, False) for var in required_for_basic)
    custom_ready = all(validation_results.get(var, False) for var in required_for_custom)
    
    print(f"✓ Basic RAG-Anything: {'READY' if basic_ready else 'MISSING REQUIRED VARS'}")
    print(f"✓ Custom Models: {'READY' if custom_ready else 'MISSING REQUIRED VARS'}")
    
    if not basic_ready:
        print(f"\n⚠️  To use basic RAG-Anything, set: {', '.join(required_for_basic)}")
    
    if not custom_ready:
        print(f"\n⚠️  To use custom models, set: {', '.join(required_for_custom)}")
    
    print(f"\n📄 Environment file: {env_path}")
    print("💡 Edit the .env file to update configuration")
    
    return basic_ready or custom_ready


if __name__ == "__main__":
    validate_environment()