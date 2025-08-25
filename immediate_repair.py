#!/usr/bin/env python3
# 立即修复RAG系统数据一致性问题

import asyncio
import sys
import os
import json
import shutil
from pathlib import Path

# 添加项目路径
sys.path.append('/home/ragsvr/projects/ragsystem/RAG-Anything')

from raganything import RAGAnything, RAGAnythingConfig
from simple_qwen_embed import qwen_embed
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path="/home/ragsvr/projects/ragsystem/.env")

async def immediate_repair():
    """立即修复数据一致性问题"""
    print("🚨 开始立即修复RAG系统数据一致性问题...")
    
    # 目标文档
    target_file = "国家电网有限公司企业年金管理办法_1644559838997.pdf"
    target_doc_id = "doc-e3839963a33571bb53650c50411ea7b1"
    
    print(f"🎯 目标文档: {target_file}")
    print(f"🔍 问题doc_id: {target_doc_id}")
    
    # 第一步：完全清理问题doc_id的所有存储记录
    print("\n📋 第一步：清理所有存储记录...")
    
    storage_files = [
        "/home/ragsvr/projects/ragsystem/rag_storage/kv_store_doc_status.json",
        "/home/ragsvr/projects/ragsystem/rag_storage/kv_store_full_docs.json",
        "/home/ragsvr/projects/ragsystem/rag_storage/kv_store_text_chunks.json",
    ]
    
    for storage_file in storage_files:
        if os.path.exists(storage_file):
            print(f"  清理 {os.path.basename(storage_file)}...")
            with open(storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 删除目标doc_id的记录
            if target_doc_id in data:
                del data[target_doc_id]
                print(f"    ✅ 删除了doc_id: {target_doc_id}")
                
            # 同时清理任何包含目标文件名的记录
            keys_to_remove = []
            for key, value in data.items():
                if isinstance(value, dict):
                    file_path = value.get('file_path', '') or value.get('file_name', '')
                    if target_file in file_path:
                        keys_to_remove.append(key)
                        
            for key in keys_to_remove:
                del data[key]
                print(f"    ✅ 删除了相关记录: {key}")
            
            # 保存清理后的数据
            with open(storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 清理vdb_chunks.json
    vdb_chunks_file = "/home/ragsvr/projects/ragsystem/rag_storage/vdb_chunks.json"
    if os.path.exists(vdb_chunks_file):
        print(f"  清理 {os.path.basename(vdb_chunks_file)}...")
        with open(vdb_chunks_file, 'r', encoding='utf-8') as f:
            vdb_data = json.load(f)
        
        if 'data' in vdb_data and isinstance(vdb_data['data'], list):
            original_count = len(vdb_data['data'])
            vdb_data['data'] = [
                chunk for chunk in vdb_data['data'] 
                if chunk.get('full_doc_id') != target_doc_id
            ]
            removed_count = original_count - len(vdb_data['data'])
            if removed_count > 0:
                print(f"    ✅ 删除了 {removed_count} 个chunk记录")
                
                with open(vdb_chunks_file, 'w', encoding='utf-8') as f:
                    json.dump(vdb_data, f, ensure_ascii=False, indent=2)
    
    # 第二步：查找解析输出文件
    print("\n📄 第二步：查找解析输出...")
    
    base_name = target_file.replace('.pdf', '')
    content_list_path = None
    
    # 搜索所有可能的路径
    search_paths = [
        f"/home/ragsvr/projects/ragsystem/output/{base_name}/auto/{base_name}_content_list.json",
        f"/home/ragsvr/projects/ragsystem/output/{base_name}/{base_name}/auto/{base_name}_content_list.json",
        f"/home/ragsvr/projects/ragsystem/output/{base_name}/content_list.json",
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            content_list_path = path
            break
    
    if not content_list_path:
        print("❌ 未找到解析输出文件")
        return False
    
    print(f"✅ 找到解析输出: {content_list_path}")
    
    # 第三步：重新初始化RAG系统并导入文档
    print("\n🔄 第三步：重新导入文档...")
    
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
    
    # 加载content_list
    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_list = json.load(f)
    
    print(f"📊 内容块数量: {len(content_list)}")
    
    # 重新插入文档
    print("🔄 正在重新插入文档...")
    try:
        await rag.insert_content_list(content_list, target_file)
        print("✅ 文档重新插入成功！")
    except Exception as e:
        print(f"❌ 重新插入失败: {e}")
        return False
    
    # 第四步：验证修复结果
    print("\n🔍 第四步：验证修复结果...")
    
    # 检查新的doc状态
    with open("/home/ragsvr/projects/ragsystem/rag_storage/kv_store_doc_status.json", 'r', encoding='utf-8') as f:
        doc_status = json.load(f)
    
    # 查找新的成功记录
    success_count = 0
    new_doc_id = None
    for doc_id, status_info in doc_status.items():
        if isinstance(status_info, dict):
            file_path = status_info.get('file_path', '')
            if target_file in file_path and status_info.get('status') == 'processed':
                success_count += 1
                new_doc_id = doc_id
                print(f"✅ 找到成功记录: {doc_id}")
                print(f"   状态: {status_info.get('status')}")
                print(f"   chunks数量: {status_info.get('chunks_count', 0)}")
    
    if success_count > 0:
        print(f"🎉 修复成功！找到 {success_count} 个新的成功记录")
        
        # 测试查询
        print("\n🔍 测试查询功能...")
        try:
            result = await rag.aquery("企业年金管理办法的主要内容是什么？", mode="hybrid")
            if result and "企业年金" in result:
                print("✅ 查询测试成功！可以找到企业年金相关内容")
                print(f"查询结果预览: {result[:200]}...")
            else:
                print("⚠️ 查询测试：仍然没有找到相关内容")
        except Exception as e:
            print(f"❌ 查询测试失败: {e}")
        
        return True
    else:
        print("❌ 修复失败：没有找到成功的新记录")
        return False

if __name__ == "__main__":
    success = asyncio.run(immediate_repair())
    if success:
        print("\n🎊 立即修复完成！")
        print("现在可以通过API查询企业年金管理办法的相关内容了。")
    else:
        print("\n💥 修复失败，请检查错误信息并手动处理。")