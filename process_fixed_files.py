#!/usr/bin/env python3
"""
使用正确的文件路径重新处理失败的文档
"""

import requests
import json
import os
import time

API_BASE = "http://127.0.0.1:8001"

def main():
    print("=== 重新处理修复后的文档 ===")
    print()
    
    # 读取修复信息
    fix_file = "/home/ragsvr/projects/ragsystem/path_fixes.json"
    if not os.path.exists(fix_file):
        print("❌ 修复信息文件不存在，请先运行 fix_file_paths.py")
        return
    
    with open(fix_file, 'r', encoding='utf-8') as f:
        fixes = json.load(f)
    
    print(f"准备重新处理 {len(fixes)} 个文档")
    print()
    
    success_count = 0
    for i, fix in enumerate(fixes, 1):
        document_id = fix['document_id']
        original_name = fix['original_name']
        matched_file = fix['matched_file']
        full_path = fix['full_path']
        
        print(f"{i}. 处理文档: {original_name}")
        print(f"   使用文件: {matched_file}")
        
        # 验证文件存在且可读
        if not os.path.exists(full_path):
            print(f"   ❌ 文件不存在: {full_path}")
            continue
        
        if not os.access(full_path, os.R_OK):
            print(f"   ❌ 文件不可读: {full_path}")
            continue
        
        try:
            # 这里我们需要创建一个新的处理请求，绕过状态检查
            # 由于API限制，我们使用文件重新上传的方式
            print(f"   📤 重新上传文件...")
            
            # 重新上传文件
            with open(full_path, 'rb') as file_data:
                files = {'file': (matched_file, file_data, 'application/pdf')}
                data = {'auto_process': 'true'}  # 自动处理
                
                response = requests.post(f"{API_BASE}/api/v1/documents/upload", 
                                       files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    new_document_id = result.get('document_id')
                    print(f"   ✅ 重新上传成功，新文档ID: {new_document_id}")
                    success_count += 1
                    
                    # 等待处理完成
                    print(f"   ⏳ 等待处理完成...")
                    time.sleep(3)
                    
                else:
                    print(f"   ❌ 重新上传失败: {response.status_code}")
                    if response.headers.get('content-type', '').startswith('application/json'):
                        error_detail = response.json()
                        print(f"      错误详情: {error_detail}")
                    
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
        
        print()
    
    print(f"重新处理完成: {success_count}/{len(fixes)} 个文档成功")
    
    if success_count > 0:
        print()
        print("✅ 建议操作:")
        print("1. 通过前端界面查看新上传文档的处理状态")
        print("2. 如果处理成功，可以考虑删除原来失败的文档记录")
        print("3. 监控系统日志确保没有其他问题")

if __name__ == "__main__":
    main()