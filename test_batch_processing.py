#!/usr/bin/env python3
"""
批量处理测试脚本
测试批量解析功能的修复效果
"""

import asyncio
import aiohttp
import json
import os
import time
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API基础URL
API_BASE = "http://localhost:8002"

class BatchProcessingTester:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def upload_test_files(self, num_files=10):
        """创建并上传测试文件"""
        test_files_dir = Path("test_batch_files")
        test_files_dir.mkdir(exist_ok=True)
        
        uploaded_docs = []
        
        # 创建测试文件
        for i in range(1, num_files + 1):
            file_path = test_files_dir / f"test_doc{i}.txt"
            content = f"""测试文档 {i}
            
这是第{i}个测试文档，用于验证批量处理功能。
文档内容包含：
- 文档标题：测试文档{i}
- 创建时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
- 测试目的：验证RAG系统批量处理能力

{'=' * 50}
内容段落1：这是一个测试段落，包含一些基本信息。
内容段落2：这里是更多的测试内容，用于RAG解析。
内容段落3：最后一个段落，完成文档内容。
{'=' * 50}

文档结束标记。
"""
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 上传文件
            logger.info(f"正在上传文件: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=file_path.name)
                
                async with self.session.post(f"{API_BASE}/api/v1/documents/upload", data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        uploaded_docs.append(result["document_id"])
                        logger.info(f"✅ 文件上传成功: {file_path.name} -> {result['document_id']}")
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ 文件上传失败: {file_path.name} - {error_text}")
                        
        return uploaded_docs
    
    async def start_batch_processing(self, document_ids):
        """启动批量处理"""
        logger.info(f"🚀 启动批量处理，文档数量: {len(document_ids)}")
        
        payload = {
            "document_ids": document_ids
        }
        
        async with self.session.post(
            f"{API_BASE}/api/v1/documents/process/batch", 
            json=payload
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                logger.info(f"✅ 批量处理启动成功")
                logger.info(f"批量操作ID: {result.get('batch_operation_id')}")
                logger.info(f"处理结果统计: {result.get('summary')}")
                return result
            else:
                error_text = await resp.text()
                logger.error(f"❌ 批量处理启动失败: {error_text}")
                return None
    
    async def monitor_processing_status(self, document_ids, timeout=300):
        """监控处理状态"""
        logger.info("📊 开始监控处理状态...")
        
        start_time = time.time()
        check_interval = 5  # 5秒检查一次
        
        while time.time() - start_time < timeout:
            # 获取所有文档状态
            status_counts = {
                "uploaded": 0,
                "queued": 0, 
                "processing": 0,
                "completed": 0,
                "failed": 0
            }
            
            for doc_id in document_ids:
                async with self.session.get(f"{API_BASE}/api/v1/documents/{doc_id}") as resp:
                    if resp.status == 200:
                        doc = await resp.json()
                        status = doc.get("status", "unknown")
                        if status in status_counts:
                            status_counts[status] += 1
                        else:
                            status_counts["unknown"] = status_counts.get("unknown", 0) + 1
            
            logger.info(f"📈 状态统计: {status_counts}")
            
            # 检查是否全部完成
            total_finished = status_counts["completed"] + status_counts["failed"]
            if total_finished == len(document_ids):
                logger.info("🎉 所有文档处理完成！")
                return status_counts
                
            await asyncio.sleep(check_interval)
        
        logger.warning("⏰ 监控超时，仍有文档未完成处理")
        return status_counts
    
    async def get_batch_operation_status(self):
        """获取批量操作状态"""
        async with self.session.get(f"{API_BASE}/api/v1/batch-operations") as resp:
            if resp.status == 200:
                operations = await resp.json()
                logger.info(f"📋 批量操作列表: {len(operations)} 个操作")
                for op in operations:
                    logger.info(f"  - {op.get('id')}: {op.get('status')} ({op.get('completed_count', 0)}/{op.get('total_count', 0)})")
                return operations
            else:
                logger.error("❌ 获取批量操作状态失败")
                return []

async def main():
    """主测试函数"""
    logger.info("🧪 开始批量处理测试")
    
    async with BatchProcessingTester() as tester:
        try:
            # 1. 上传测试文件
            logger.info("📁 步骤1: 上传测试文件")
            document_ids = await tester.upload_test_files(10)  # 上传10个文件
            
            if len(document_ids) < 5:
                logger.error("❌ 上传的文件数量不足，无法进行批量测试")
                return
                
            logger.info(f"✅ 成功上传 {len(document_ids)} 个文件")
            
            # 2. 启动批量处理
            logger.info("⚙️ 步骤2: 启动批量处理")
            batch_result = await tester.start_batch_processing(document_ids)
            
            if not batch_result:
                logger.error("❌ 批量处理启动失败")
                return
                
            # 3. 监控处理状态
            logger.info("👀 步骤3: 监控处理状态")
            final_status = await tester.monitor_processing_status(document_ids, timeout=600)
            
            # 4. 获取批量操作状态
            logger.info("📊 步骤4: 获取批量操作状态")
            await tester.get_batch_operation_status()
            
            # 5. 分析结果
            logger.info("📋 步骤5: 分析测试结果")
            logger.info("=" * 60)
            logger.info("🏁 测试结果总结:")
            logger.info(f"总文档数: {len(document_ids)}")
            logger.info(f"成功处理: {final_status.get('completed', 0)}")
            logger.info(f"处理失败: {final_status.get('failed', 0)}")
            logger.info(f"仍在队列: {final_status.get('queued', 0)}")
            logger.info(f"正在处理: {final_status.get('processing', 0)}")
            
            # 判断测试是否成功
            success_rate = final_status.get('completed', 0) / len(document_ids) * 100
            if success_rate >= 80:
                logger.info(f"✅ 测试通过! 成功率: {success_rate:.1f}%")
            else:
                logger.warning(f"⚠️ 测试存在问题，成功率: {success_rate:.1f}%")
                
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 测试过程中发生错误: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(main())