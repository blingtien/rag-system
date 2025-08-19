#!/usr/bin/env python3
"""
强制清空RAG系统
彻底清理所有RAG数据
"""

import os
import json
import shutil
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path="../.env", override=False)

async def force_clear_rag():
    """强制清空RAG系统"""
    print("🔥 强制清空RAG系统")
    
    WORKING_DIR = os.getenv("WORKING_DIR", "./rag_storage")
    
    try:
        # 1. 初始化RAG系统
        print("🔧 初始化RAG系统...")
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_BINDING_API_KEY")
        if not api_key:
            print("❌ 未找到API密钥")
            return
        
        base_url = os.getenv("LLM_BINDING_HOST", "https://api.deepseek.com/v1")
        
        # 创建配置
        config = RAGAnythingConfig(
            working_dir=WORKING_DIR,
            parser="mineru",
        )
        
        # 定义LLM函数
        def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return openai_complete_if_cache(
                "deepseek-chat",
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=api_key,
                base_url=base_url,
                **kwargs,
            )
        
        # 定义嵌入函数
        embedding_func = EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=512,
            func=qwen_embed,
        )
        
        # 初始化RAGAnything
        rag = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
        )
        
        await rag._ensure_lightrag_initialized()
        print("✅ RAG系统初始化成功")
        
        # 2. 读取所有RAG文档
        doc_status_file = os.path.join(WORKING_DIR, "kv_store_doc_status.json")
        if os.path.exists(doc_status_file):
            with open(doc_status_file, 'r', encoding='utf-8') as f:
                rag_docs = json.load(f)
            print(f"📋 发现 {len(rag_docs)} 个RAG文档")
            
            # 3. 逐个删除所有文档
            success_count = 0
            failed_count = 0
            
            for i, doc_id in enumerate(rag_docs.keys(), 1):
                print(f"🗑️  删除文档 {i}/{len(rag_docs)}: {doc_id}")
                try:
                    deletion_result = await rag.lightrag.adelete_by_doc_id(doc_id)
                    if deletion_result.status == "success":
                        success_count += 1
                        print(f"   ✅ 删除成功: {deletion_result.message}")
                    else:
                        failed_count += 1
                        print(f"   ❌ 删除失败: {deletion_result.message}")
                except Exception as e:
                    failed_count += 1
                    print(f"   ❌ 删除异常: {str(e)}")
            
            print(f"\n📊 删除结果: 成功 {success_count}, 失败 {failed_count}")
        else:
            print("📋 没有找到RAG文档状态文件")
        
        # 4. 强制删除存储文件（如果删除失败）
        if failed_count > 0:
            print("\n🔥 强制删除存储文件...")
            storage_files = [
                "kv_store_doc_status.json",
                "kv_store_full_docs.json",
                "kv_store_full_entities.json",
                "kv_store_full_relations.json",
                "kv_store_text_chunks.json",
                "vdb_chunks.json",
                "vdb_entities.json",
                "vdb_relationships.json",
                "graph_chunk_entity_relation.graphml"
            ]
            
            for file_name in storage_files:
                file_path = os.path.join(WORKING_DIR, file_name)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"   🗑️  删除文件: {file_name}")
                    except Exception as e:
                        print(f"   ❌ 删除失败 {file_name}: {str(e)}")
        
        # 5. 清理存储对象
        try:
            await rag.finalize_storages()
            print("✅ 存储对象已清理")
        except Exception as e:
            print(f"⚠️  存储清理警告: {str(e)}")
            
    except Exception as e:
        print(f"❌ 清空失败: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🔥 RAG系统强制清空工具")
    print("⚠️  警告: 这将删除所有RAG数据，无法恢复！")
    print("=" * 50)
    
    try:
        confirm = input("确认继续？输入 'DELETE ALL' 来确认: ").strip()
        if confirm == "DELETE ALL":
            asyncio.run(force_clear_rag())
            print("\n🎉 RAG系统强制清空完成")
        else:
            print("🚪 操作已取消")
    except KeyboardInterrupt:
        print("\n🚪 用户取消操作")

if __name__ == "__main__":
    main()