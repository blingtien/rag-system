#!/usr/bin/env python3
"""
修复文档路径匹配问题
"""

import requests
import json
import os
import re
from pathlib import Path

API_BASE = "http://127.0.0.1:8001"
UPLOADS_DIR = "/home/ragsvr/projects/ragsystem/uploads"

def normalize_filename(filename):
    """标准化文件名，移除重复编号等"""
    # 移除 (1), (2) 等重复标记
    filename = re.sub(r'\(\d+\)', '', filename)
    return filename.strip()

def find_matching_file(target_filename, upload_files):
    """在上传目录中找到匹配的文件"""
    target_norm = normalize_filename(target_filename)
    target_base = Path(target_norm).stem.lower()
    
    # 直接匹配
    if target_filename in upload_files:
        return target_filename
    
    # 标准化后匹配
    if target_norm in upload_files:
        return target_norm
    
    # 模糊匹配 - 基于文件名的主要部分
    for upload_file in upload_files:
        upload_base = Path(upload_file).stem.lower()
        
        # 检查是否包含主要关键词
        target_words = target_base.split('_')[0:3]  # 取前3个主要词
        upload_words = upload_base.split('_')[0:3]
        
        if len(target_words) >= 2:
            match_score = sum(1 for word in target_words if word in upload_base)
            if match_score >= 2:  # 至少匹配2个关键词
                return upload_file
    
    return None

def update_document_path(document_id, correct_path):
    """更新文档路径（这需要直接修改API数据或添加API端点）"""
    # 这里我们创建一个修复映射，稍后可以用于修正API
    return {
        "document_id": document_id,
        "correct_path": correct_path,
        "status": "ready_to_process"
    }

def main():
    print("=== 修复文件路径匹配问题 ===")
    print()
    
    # 获取uploads目录中的所有文件
    if not os.path.exists(UPLOADS_DIR):
        print(f"❌ uploads目录不存在: {UPLOADS_DIR}")
        return
    
    upload_files = os.listdir(UPLOADS_DIR)
    print(f"uploads目录包含 {len(upload_files)} 个文件")
    print()
    
    # 获取失败的文档
    try:
        response = requests.get(f"{API_BASE}/api/v1/documents")
        response.raise_for_status()
        data = response.json()
        
        failed_docs = [doc for doc in data['documents'] if doc['status_code'] == 'failed']
        print(f"找到 {len(failed_docs)} 个失败的文档")
        print()
        
        fixes = []
        for doc in failed_docs:
            target_file = doc['file_name']
            print(f"处理: {target_file}")
            
            matching_file = find_matching_file(target_file, upload_files)
            if matching_file:
                correct_path = os.path.join(UPLOADS_DIR, matching_file)
                print(f"  ✅ 找到匹配文件: {matching_file}")
                print(f"  完整路径: {correct_path}")
                
                # 验证文件可读
                if os.access(correct_path, os.R_OK):
                    print(f"  ✅ 文件可读")
                    fix_info = update_document_path(doc['document_id'], correct_path)
                    fixes.append({
                        'document_id': doc['document_id'],
                        'original_name': target_file,
                        'matched_file': matching_file,
                        'full_path': correct_path
                    })
                else:
                    print(f"  ❌ 文件不可读")
            else:
                print(f"  ❌ 未找到匹配文件")
            print()
        
        # 保存修复信息到JSON文件，供手动修复使用
        if fixes:
            fix_file = "/home/ragsvr/projects/ragsystem/path_fixes.json"
            with open(fix_file, 'w', encoding='utf-8') as f:
                json.dump(fixes, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 生成了 {len(fixes)} 个修复建议")
            print(f"修复信息已保存到: {fix_file}")
            print()
            print("建议的修复操作:")
            for fix in fixes:
                print(f"- 文档ID {fix['document_id']}:")
                print(f"  原文件名: {fix['original_name']}")
                print(f"  匹配文件: {fix['matched_file']}")
        else:
            print("❌ 没有找到可修复的文档")
            
    except Exception as e:
        print(f"修复失败: {e}")

if __name__ == "__main__":
    main()