#!/usr/bin/env python3
# 手动修复RAG系统数据不一致文档

import asyncio
import sys
import os
import json

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

async def manual_repair_documents():
    """手动修复数据不一致的文档"""
    print("🔧 开始手动修复RAG系统数据不一致...")
    
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
    
    # 重点修复目标文档
    target_filename = "国家电网有限公司企业年金管理办法_1644559838997.pdf"
    target_doc = None
    for doc in recoverable_docs:
        if target_filename in doc['file_name']:
            target_doc = doc
            break
    
    if not target_doc:
        print(f"❌ 未找到目标文档: {target_filename}")
        return
    
    print(f"\n🎯 开始修复目标文档: {target_filename}")
    
    # 手动清理存储中的旧记录
    doc_id = target_doc['doc_id']
    print(f"清理旧记录: {doc_id}")
    
    # 清理doc_status
    doc_status_path = "/home/ragsvr/projects/ragsystem/rag_storage/kv_store_doc_status.json"
    with open(doc_status_path, 'r', encoding='utf-8') as f:
        doc_status = json.load(f)
    
    if doc_id in doc_status:
        del doc_status[doc_id]
        with open(doc_status_path, 'w', encoding='utf-8') as f:
            json.dump(doc_status, f, ensure_ascii=False, indent=2)
        print("✅ 已清理doc_status记录")
    
    # 清理full_docs（如果存在）
    full_docs_path = "/home/ragsvr/projects/ragsystem/rag_storage/kv_store_full_docs.json"
    with open(full_docs_path, 'r', encoding='utf-8') as f:
        full_docs = json.load(f)
    
    if doc_id in full_docs:
        del full_docs[doc_id]
        with open(full_docs_path, 'w', encoding='utf-8') as f:
            json.dump(full_docs, f, ensure_ascii=False, indent=2)
        print("✅ 已清理full_docs记录")
    
    # 查找content_list文件
    base_name = target_filename.replace('.pdf', '')
    folder_paths = [
        os.path.join("/home/ragsvr/projects/ragsystem/output", base_name),
        os.path.join("/home/ragsvr/projects/ragsystem/output", base_name, 'auto'),
        os.path.join("/home/ragsvr/projects/ragsystem/output", base_name, base_name, 'auto'),
    ]
    
    content_list_files = [
        'content_list.json',
        f'{base_name}_content_list.json'
    ]
    
    content_list_path = None
    for folder_path in folder_paths:
        for filename_pattern in content_list_files:
            potential_path = os.path.join(folder_path, filename_pattern)
            if os.path.exists(potential_path):
                content_list_path = potential_path
                break
        if content_list_path:
            break
    
    if not content_list_path:
        print("❌ 未找到content_list文件")
        return
    
    # 加载content_list
    print(f"📄 加载解析内容: {content_list_path}")
    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_list = json.load(f)
    
    print(f"内容块数量: {len(content_list)}")
    
    # 重新插入文档（这会生成新的doc_id）
    print("🔄 重新插入文档...")
    try:
        await rag.insert_content_list(content_list, target_filename)
        print(f"✅ 成功修复文档: {target_filename}")
        
        # 检查修复结果
        print("\n📊 检查修复结果...")
        failed_docs_after, recoverable_docs_after = checker.find_inconsistent_documents()
        
        # 查看是否还有这个文件名的问题
        still_has_issue = False
        for doc in recoverable_docs_after + failed_docs_after:
            if target_filename in doc['file_name']:
                still_has_issue = True
                break
        
        if still_has_issue:
            print("⚠️ 文档仍存在问题")
        else:
            print("🎉 文档修复成功！")
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")

if __name__ == "__main__":
    asyncio.run(manual_repair_documents())