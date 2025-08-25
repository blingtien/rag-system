#!/usr/bin/env python3
"""
调试批量处理失败的具体原因
"""

import requests
import json
import os
from pathlib import Path

API_BASE = "http://127.0.0.1:8001"

def check_file_exists(file_path):
    """检查文件是否存在"""
    return os.path.exists(file_path)

def get_file_info(file_path):
    """获取文件信息"""
    if not os.path.exists(file_path):
        return None
    
    stat = os.stat(file_path)
    return {
        "size": stat.st_size,
        "readable": os.access(file_path, os.R_OK),
        "extension": Path(file_path).suffix.lower()
    }

def main():
    print("=== 批量处理失败原因调试 ===")
    print()
    
    # 获取失败文档信息
    try:
        response = requests.get(f"{API_BASE}/api/v1/documents")
        response.raise_for_status()
        data = response.json()
        
        failed_docs = [doc for doc in data['documents'] if doc['status_code'] == 'failed']
        print(f"分析 {len(failed_docs)} 个失败的文档:")
        print()
        
        for i, doc in enumerate(failed_docs[:5], 1):  # 分析前5个
            print(f"{i}. {doc['file_name']}")
            print(f"   文档ID: {doc['document_id']}")
            print(f"   状态: {doc['status_display']}")
            print(f"   上传时间: {doc['uploaded_at']}")
            
            # 检查文件路径(从uploads目录推断)
            file_name = doc['file_name']
            possible_paths = [
                f"/home/ragsvr/projects/ragsystem/uploads/{file_name}",
                f"/home/ragsvr/projects/ragsystem/uploads/{file_name.replace('(1)', '').replace('(2)', '')}",
            ]
            
            file_found = False
            for path in possible_paths:
                if check_file_exists(path):
                    file_info = get_file_info(path)
                    print(f"   文件路径: {path} ✅")
                    print(f"   文件大小: {file_info['size']:,} bytes")
                    print(f"   可读性: {'是' if file_info['readable'] else '否'}")
                    print(f"   文件类型: {file_info['extension']}")
                    file_found = True
                    break
            
            if not file_found:
                print(f"   文件路径: 未找到 ❌")
                # 列出uploads目录中类似的文件
                uploads_dir = "/home/ragsvr/projects/ragsystem/uploads"
                if os.path.exists(uploads_dir):
                    similar_files = [f for f in os.listdir(uploads_dir) 
                                   if file_name[:20] in f or f[:20] in file_name]
                    if similar_files:
                        print(f"   可能的匹配文件: {similar_files[:3]}")
            
            print()
        
        # 检查uploads目录状态
        uploads_dir = "/home/ragsvr/projects/ragsystem/uploads"
        if os.path.exists(uploads_dir):
            upload_files = os.listdir(uploads_dir)
            print(f"uploads目录包含 {len(upload_files)} 个文件")
            recent_files = sorted(upload_files)[-10:]
            print("最近的10个文件:")
            for f in recent_files:
                print(f"  - {f}")
        else:
            print("❌ uploads目录不存在!")
            
    except Exception as e:
        print(f"调试失败: {e}")

if __name__ == "__main__":
    main()