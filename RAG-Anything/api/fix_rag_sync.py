#!/usr/bin/env python3
"""
修复RAG系统同步问题
清理孤儿文档数据并同步统计信息
"""

import asyncio
import requests
import json
import os

API_BASE = "http://127.0.0.1:8001"

async def fix_rag_sync():
    """修复RAG同步问题"""
    print("🔧 修复RAG系统同步问题")
    
    # 1. 获取当前文档管理列表
    print("\n📋 获取当前文档管理状态...")
    response = requests.get(f"{API_BASE}/api/v1/documents")
    if response.status_code == 200:
        docs_data = response.json()
        current_docs = docs_data["documents"]
        print(f"   文档管理界面显示: {len(current_docs)} 个文档")
        
        # 显示文档详情
        for doc in current_docs:
            rag_id = doc.get("rag_doc_id") or "None"
            print(f"   📄 {doc['file_name']} - RAG ID: {rag_id}")
    else:
        print(f"❌ 无法获取文档列表: {response.status_code}")
        return
    
    # 2. 获取当前统计信息
    print("\n📊 获取当前统计信息...")
    response = requests.get(f"{API_BASE}/api/system/status")
    if response.status_code == 200:
        system_data = response.json()
        stats = system_data["processing_stats"]
        print(f"   文档数量: {stats['documents_processed']}")
        print(f"   实体数量: {stats['entities_count']}")
        print(f"   关系数量: {stats['relationships_count']}")
        print(f"   chunks数量: {stats['chunks_count']}")
    else:
        print(f"❌ 无法获取统计信息: {response.status_code}")
        return
    
    # 3. 检查RAG存储文件
    print("\n🔍 检查RAG存储状态...")
    rag_storage_dir = "/home/ragsvr/projects/ragsystem/RAG-Anything/rag_storage"
    
    # 读取RAG系统中的文档状态
    doc_status_file = os.path.join(rag_storage_dir, "kv_store_doc_status.json")
    if os.path.exists(doc_status_file):
        with open(doc_status_file, 'r', encoding='utf-8') as f:
            rag_docs = json.load(f)
        print(f"   RAG系统中的文档: {len(rag_docs)} 个")
        print("   RAG文档列表:")
        for doc_id in rag_docs.keys():
            print(f"     - {doc_id}")
    else:
        print("   ❌ 找不到RAG文档状态文件")
        return
    
    # 4. 分析不一致性
    print("\n⚠️  发现的问题:")
    current_rag_ids = {doc.get("rag_doc_id") for doc in current_docs if doc.get("rag_doc_id")}
    rag_system_ids = set(rag_docs.keys())
    
    # 找出孤儿文档（在RAG中但不在管理界面中）
    orphan_docs = rag_system_ids - current_rag_ids
    if orphan_docs:
        print(f"   🗂️  孤儿文档 ({len(orphan_docs)}个): 在RAG系统中但不在管理界面")
        for doc_id in orphan_docs:
            print(f"      - {doc_id}")
    
    # 找出丢失的文档（在管理界面但不在RAG中）
    missing_docs = current_rag_ids - rag_system_ids
    if missing_docs:
        print(f"   💥 丢失文档 ({len(missing_docs)}个): 在管理界面但不在RAG系统")
        for doc_id in missing_docs:
            print(f"      - {doc_id}")
    
    # 找出rag_doc_id为None的文档
    none_rag_docs = [doc for doc in current_docs if not doc.get("rag_doc_id")]
    if none_rag_docs:
        print(f"   🔍 rag_doc_id缺失 ({len(none_rag_docs)}个):")
        for doc in none_rag_docs:
            print(f"      - {doc['file_name']}")
    
    # 5. 提供修复选项
    print(f"\n🔧 修复选项:")
    print(f"   1. 清理 {len(orphan_docs)} 个孤儿文档")
    print(f"   2. 修复 {len(none_rag_docs)} 个缺失rag_doc_id的文档")
    print(f"   3. 清空所有文档重新开始")
    
    try:
        choice = input("请选择修复选项 (1/2/3/q退出): ").strip()
        
        if choice == "1":
            await cleanup_orphan_docs(orphan_docs)
        elif choice == "2":
            await fix_missing_rag_ids(none_rag_docs, rag_docs)
        elif choice == "3":
            await clear_all_docs()
        elif choice.lower() == "q":
            print("🚪 退出修复程序")
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n🚪 用户取消操作")

async def cleanup_orphan_docs(orphan_docs):
    """清理孤儿文档"""
    print(f"\n🧹 清理 {len(orphan_docs)} 个孤儿文档...")
    
    # 这里我们需要直接调用RAG系统的删除方法
    # 由于我们在API外部，我们建议用户使用clear all然后重新上传活跃文档
    print("💡 建议方案：")
    print("   1. 备份重要文档")
    print("   2. 使用清空所有文档功能")
    print("   3. 重新上传需要的文档")
    
    confirm = input("是否继续清空所有文档？(y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        await clear_all_docs()

async def fix_missing_rag_ids(none_rag_docs, rag_docs):
    """尝试修复缺失的rag_doc_id"""
    print(f"\n🔧 尝试修复 {len(none_rag_docs)} 个缺失rag_doc_id的文档...")
    
    # 这个修复比较复杂，因为我们需要猜测哪个RAG文档对应哪个管理界面文档
    # 建议用户重新处理这些文档
    print("💡 建议方案：")
    print("   由于rag_doc_id丢失，建议重新处理这些文档")
    for doc in none_rag_docs:
        print(f"   📄 {doc['file_name']} - 建议重新上传")

async def clear_all_docs():
    """清空所有文档"""
    print("\n🗑️  清空所有文档...")
    
    response = requests.delete(f"{API_BASE}/api/v1/documents/clear")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 清空完成: {result['message']}")
        
        # 验证清空结果
        await asyncio.sleep(2)
        response = requests.get(f"{API_BASE}/api/system/status")
        if response.status_code == 200:
            stats = response.json()["processing_stats"]
            print("\n📊 清空后统计信息:")
            print(f"   文档数量: {stats['documents_processed']}")
            print(f"   实体数量: {stats['entities_count']}")
            print(f"   关系数量: {stats['relationships_count']}")
            print(f"   chunks数量: {stats['chunks_count']}")
            
            if (stats['documents_processed'] == 0 and 
                stats['entities_count'] == 0 and 
                stats['relationships_count'] == 0 and 
                stats['chunks_count'] == 0):
                print("✅ 清空成功，所有统计信息已重置")
            else:
                print("⚠️  统计信息未完全重置，可能需要重启服务器")
    else:
        print(f"❌ 清空失败: {response.status_code}")
        print(response.text)

def main():
    """主函数"""
    print("🔧 RAG系统同步修复工具")
    print("=" * 50)
    
    # 检查API服务器
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code != 200:
            print("❌ API服务器未运行，请先启动 rag_api_server.py")
            return
    except Exception:
        print("❌ 无法连接到API服务器，请先启动 rag_api_server.py")
        return
    
    print("✅ API服务器连接正常")
    
    # 运行修复程序
    asyncio.run(fix_rag_sync())

if __name__ == "__main__":
    main()