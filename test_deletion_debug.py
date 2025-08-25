#!/usr/bin/env python3
"""
测试脚本：专门调试文档删除功能
分析删除请求的整个流程，检查每一步的执行情况
"""

import os
import json
import asyncio
import aiohttp
import sys
from pathlib import Path

# API配置
API_BASE_URL = "http://127.0.0.1:8001"
UPLOAD_DIR = "/home/ragsvr/projects/ragsystem/uploads"
TEST_FILE_NAME = "deletion_test_file.txt"
TEST_FILE_PATH = os.path.join(UPLOAD_DIR, TEST_FILE_NAME)

async def test_deletion_flow():
    """测试完整的删除流程"""
    print("🔍 开始测试文档删除功能...")
    
    async with aiohttp.ClientSession() as session:
        # 步骤1: 创建测试文件
        print(f"\n📝 步骤1: 创建测试文件 {TEST_FILE_NAME}")
        test_content = f"这是一个用于测试删除功能的文件\n创建时间: {os.popen('date').read().strip()}"
        with open(TEST_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(test_content)
        print(f"✅ 测试文件已创建: {TEST_FILE_PATH}")
        print(f"   文件存在: {os.path.exists(TEST_FILE_PATH)}")
        print(f"   文件大小: {os.path.getsize(TEST_FILE_PATH)} bytes")
        
        # 步骤2: 上传文件到API
        print(f"\n📤 步骤2: 上传文件到API")
        try:
            with open(TEST_FILE_PATH, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=TEST_FILE_NAME)
                
                async with session.post(f"{API_BASE_URL}/api/v1/documents/upload", data=data) as resp:
                    if resp.status == 200:
                        upload_result = await resp.json()
                        print(f"✅ 文件上传成功")
                        print(f"   Document ID: {upload_result.get('document_id')}")
                        print(f"   Task ID: {upload_result.get('task_id')}")
                        document_id = upload_result.get('document_id')
                    else:
                        print(f"❌ 文件上传失败: {resp.status}")
                        error_text = await resp.text()
                        print(f"   错误信息: {error_text}")
                        return
        except Exception as e:
            print(f"❌ 上传文件时发生异常: {str(e)}")
            return
        
        # 步骤3: 验证文件在uploads目录中
        print(f"\n🔍 步骤3: 验证文件状态")
        print(f"   上传后文件仍存在: {os.path.exists(TEST_FILE_PATH)}")
        
        # 步骤4: 获取文档列表，确认文档已添加
        print(f"\n📋 步骤4: 验证文档在API中的记录")
        try:
            async with session.get(f"{API_BASE_URL}/api/v1/documents") as resp:
                if resp.status == 200:
                    docs_result = await resp.json()
                    if docs_result.get('success'):
                        documents = docs_result.get('documents', [])
                        test_doc = None
                        for doc in documents:
                            if doc.get('document_id') == document_id:
                                test_doc = doc
                                break
                        
                        if test_doc:
                            print(f"✅ 找到文档记录:")
                            print(f"   文档ID: {test_doc.get('document_id')}")
                            print(f"   文件名: {test_doc.get('file_name')}")
                            print(f"   文件大小: {test_doc.get('file_size')}")
                            print(f"   状态: {test_doc.get('status_code')}")
                        else:
                            print(f"❌ 未找到对应的文档记录")
                            return
                    else:
                        print(f"❌ 获取文档列表失败")
                        return
                else:
                    print(f"❌ 获取文档列表请求失败: {resp.status}")
                    return
        except Exception as e:
            print(f"❌ 获取文档列表时发生异常: {str(e)}")
            return
        
        # 步骤5: 执行删除操作
        print(f"\n🗑️ 步骤5: 执行删除操作")
        try:
            delete_payload = {"document_ids": [document_id]}
            async with session.delete(f"{API_BASE_URL}/api/v1/documents", json=delete_payload) as resp:
                if resp.status == 200:
                    delete_result = await resp.json()
                    print(f"✅ 删除请求响应成功")
                    print(f"   响应内容: {json.dumps(delete_result, indent=2, ensure_ascii=False)}")
                    
                    # 检查删除结果
                    if delete_result.get('success'):
                        deleted_count = delete_result.get('deleted_count', 0)
                        deletion_results = delete_result.get('deletion_results', [])
                        print(f"   已删除数量: {deleted_count}")
                        
                        if deletion_results:
                            for result in deletion_results:
                                print(f"   - 文档 {result.get('file_name')}: {result.get('status')} - {result.get('message')}")
                                if result.get('details'):
                                    details = result.get('details')
                                    print(f"     RAG删除: {details.get('rag_deletion', {})}")
                                    print(f"     文件删除: {details.get('file_deletion', 'N/A')}")
                    else:
                        print(f"❌ 删除操作失败: {delete_result.get('message')}")
                else:
                    print(f"❌ 删除请求失败: {resp.status}")
                    error_text = await resp.text()
                    print(f"   错误信息: {error_text}")
                    return
        except Exception as e:
            print(f"❌ 删除操作时发生异常: {str(e)}")
            return
        
        # 步骤6: 验证文件是否真的被删除
        print(f"\n🔍 步骤6: 验证删除结果")
        file_exists_after = os.path.exists(TEST_FILE_PATH)
        print(f"   删除后文件仍存在: {file_exists_after}")
        
        if file_exists_after:
            print(f"❌ 发现问题：文件应该被删除但仍然存在！")
            print(f"   文件路径: {TEST_FILE_PATH}")
            print(f"   文件权限: {oct(os.stat(TEST_FILE_PATH).st_mode)}")
            print(f"   文件所有者: {os.stat(TEST_FILE_PATH).st_uid}")
            print(f"   当前用户UID: {os.getuid()}")
        else:
            print(f"✅ 文件已成功删除")
        
        # 步骤7: 验证文档记录是否被删除
        print(f"\n📋 步骤7: 验证文档记录删除状态")
        try:
            async with session.get(f"{API_BASE_URL}/api/v1/documents") as resp:
                if resp.status == 200:
                    docs_result = await resp.json()
                    if docs_result.get('success'):
                        documents = docs_result.get('documents', [])
                        test_doc_exists = any(doc.get('document_id') == document_id for doc in documents)
                        
                        if test_doc_exists:
                            print(f"❌ 发现问题：文档记录应该被删除但仍然存在！")
                        else:
                            print(f"✅ 文档记录已成功删除")
                    else:
                        print(f"❌ 获取文档列表失败")
                else:
                    print(f"❌ 获取文档列表请求失败: {resp.status}")
        except Exception as e:
            print(f"❌ 验证文档记录时发生异常: {str(e)}")

async def check_api_status():
    """检查API服务是否运行"""
    print("🔍 检查API服务状态...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health") as resp:
                if resp.status == 200:
                    health_data = await resp.json()
                    print(f"✅ API服务正常运行")
                    print(f"   服务状态: {health_data.get('status')}")
                    return True
                else:
                    print(f"❌ API服务响应异常: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ 无法连接到API服务: {str(e)}")
        print(f"   请确保API服务正在运行: python RAG-Anything/api/rag_api_server.py")
        return False

async def main():
    """主函数"""
    print("=" * 60)
    print("🧪 文档删除功能调试测试")
    print("=" * 60)
    
    # 检查API服务状态
    if not await check_api_status():
        return
    
    # 检查uploads目录
    print(f"\n📁 检查uploads目录: {UPLOAD_DIR}")
    if not os.path.exists(UPLOAD_DIR):
        print(f"❌ uploads目录不存在: {UPLOAD_DIR}")
        return
    else:
        print(f"✅ uploads目录存在")
        files_count = len(os.listdir(UPLOAD_DIR))
        print(f"   目录中当前文件数量: {files_count}")
    
    # 执行删除测试
    await test_deletion_flow()
    
    # 清理测试文件（如果仍存在）
    print(f"\n🧹 清理测试文件")
    if os.path.exists(TEST_FILE_PATH):
        try:
            os.remove(TEST_FILE_PATH)
            print(f"✅ 手动删除了测试文件")
        except Exception as e:
            print(f"❌ 手动删除测试文件失败: {str(e)}")
    
    print("\n" + "=" * 60)
    print("🧪 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())