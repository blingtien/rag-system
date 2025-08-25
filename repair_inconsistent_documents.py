#!/usr/bin/env python3
# RAG系统数据一致性修复脚本

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/home/ragsvr/projects/ragsystem/RAG-Anything')

from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc
from dotenv import load_dotenv
from data_consistency_checker import RAGDataConsistencyChecker

# 加载环境变量
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env")

async def repair_documents():
    """修复数据不一致的文档"""
    print("🔧 开始RAG系统数据一致性修复...")
    
    # 初始化RAG系统
    config = RAGAnythingConfig(
        working_dir="/home/ragsvr/projects/ragsystem/rag_storage",
        parser_output_dir="/home/ragsvr/projects/ragsystem/output"
    )

    # LLM函数
    def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        return openai_complete_if_cache(
            "deepseek-chat",
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1"),
            **kwargs,
        )

    # 嵌入函数
    embedding_func = EmbeddingFunc(
        embedding_dim=1024,
        max_token_size=512,
        func=qwen_embed,
    )

    # 创建RAG实例
    rag = RAGAnything(
        config=config,
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
    )

    await rag._ensure_lightrag_initialized()

    # 创建检查器
    checker = RAGDataConsistencyChecker("/home/ragsvr/projects/ragsystem/rag_storage", "/home/ragsvr/projects/ragsystem/output")

    # 查找可恢复的文档
    print("📊 检查数据一致性...")
    failed_docs, recoverable_docs = checker.find_inconsistent_documents()
    
    print(f"发现 {len(recoverable_docs)} 个可恢复的文档")
    print(f"发现 {len(failed_docs)} 个需要重新解析的文档")

    if not recoverable_docs:
        print("✅ 没有需要修复的文档")
        return

    # 修复可恢复的文档
    print("\n🔧 开始修复文档...")
    success_count = 0
    
    for i, doc in enumerate(recoverable_docs, 1):
        doc_id = doc["doc_id"]
        filename = doc['file_name']
        print(f"[{i}/{len(recoverable_docs)}] 修复文档: {filename}")
        
        try:
            success = await checker.repair_document(doc_id, rag)
            if success:
                print(f"  ✅ 修复成功: {doc_id}")
                success_count += 1
            else:
                print(f"  ❌ 修复失败: {doc_id}")
        except Exception as e:
            print(f"  ❌ 修复出错: {e}")
    
    print(f"\n📈 修复完成统计:")
    print(f"  成功修复: {success_count}/{len(recoverable_docs)} 个文档")
    
    if failed_docs:
        print(f"\n⚠️ 以下 {len(failed_docs)} 个文档需要重新解析：")
        for doc in failed_docs:
            print(f"  - {doc['file_name']}")

if __name__ == "__main__":
    asyncio.run(repair_documents())