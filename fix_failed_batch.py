#!/usr/bin/env python3
"""
批量解析失败文档修复脚本
重置失败文档状态并重新处理
"""

import requests
import json
import time
import sys

API_BASE = "http://127.0.0.1:8001"

def get_failed_documents():
    """获取失败的文档列表"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/documents")
        response.raise_for_status()
        data = response.json()
        
        failed_docs = [doc for doc in data['documents'] if doc['status_code'] == 'failed']
        print(f"找到 {len(failed_docs)} 个失败的文档")
        
        for doc in failed_docs:
            print(f"- {doc['file_name']} (ID: {doc['document_id']})")
        
        return failed_docs
    except Exception as e:
        print(f"获取文档列表失败: {e}")
        return []

def reset_document_status(document_id):
    """重置文档状态为uploaded，允许重新处理"""
    try:
        # 这里我们需要直接修改API或创建一个重置端点
        # 暂时通过API调用尝试
        response = requests.post(f"{API_BASE}/api/v1/documents/{document_id}/reset")
        if response.status_code == 404:
            print(f"  重置端点不存在，尝试直接处理...")
            return False
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"  重置状态失败: {e}")
        return False

def process_document(document_id, file_name):
    """处理单个文档"""
    try:
        print(f"正在处理: {file_name}")
        
        # 首先尝试重置状态
        if not reset_document_status(document_id):
            print(f"  无法重置状态，跳过")
            return False
            
        # 等待一秒钟
        time.sleep(1)
        
        # 尝试处理
        response = requests.post(f"{API_BASE}/api/v1/documents/{document_id}/process")
        response.raise_for_status()
        
        print(f"  ✅ 成功启动处理")
        return True
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return False

def main():
    print("=== RAG-Anything 批量解析修复工具 ===")
    print()
    
    # 获取失败的文档
    failed_docs = get_failed_documents()
    if not failed_docs:
        print("没有找到失败的文档")
        return
    
    print()
    print("开始修复失败的文档...")
    print()
    
    success_count = 0
    for doc in failed_docs:
        if process_document(doc['document_id'], doc['file_name']):
            success_count += 1
        time.sleep(2)  # 避免过于频繁的请求
    
    print()
    print(f"修复完成: {success_count}/{len(failed_docs)} 个文档成功重新开始处理")
    
    if success_count > 0:
        print()
        print("请通过前端界面或API监控处理进度")
        print("处理可能需要几分钟时间，请耐心等待")

if __name__ == "__main__":
    main()