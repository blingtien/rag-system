#!/usr/bin/env python3
"""
性能测试和诊断脚本
用于测试批量文档处理的并发性能
"""

import asyncio
import time
import json
import requests
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any
import statistics
import sys
import os

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))

class PerformanceTest:
    def __init__(self, api_base_url: str = "http://localhost:8002"):
        self.api_base_url = api_base_url
        self.results = []
        
    def test_serial_processing(self, document_ids: List[str]) -> Dict[str, Any]:
        """测试串行处理性能"""
        print("\n=== 测试串行处理 ===")
        start_time = time.time()
        success_count = 0
        fail_count = 0
        
        for i, doc_id in enumerate(document_ids, 1):
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/v1/documents/{doc_id}/process"
                )
                if response.json().get("success"):
                    success_count += 1
                    print(f"✓ 文档 {i}/{len(document_ids)} 处理成功")
                else:
                    fail_count += 1
                    print(f"✗ 文档 {i}/{len(document_ids)} 处理失败")
            except Exception as e:
                fail_count += 1
                print(f"✗ 文档 {i}/{len(document_ids)} 请求失败: {e}")
                
        total_time = time.time() - start_time
        
        return {
            "method": "串行处理",
            "total_documents": len(document_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "total_time": total_time,
            "avg_time_per_doc": total_time / len(document_ids) if document_ids else 0,
            "documents_per_second": len(document_ids) / total_time if total_time > 0 else 0
        }
    
    def test_parallel_processing(self, document_ids: List[str], max_workers: int = 3) -> Dict[str, Any]:
        """测试并行处理性能"""
        print(f"\n=== 测试并行处理 (workers={max_workers}) ===")
        start_time = time.time()
        success_count = 0
        fail_count = 0
        
        def process_document(doc_info):
            doc_id, index, total = doc_info
            try:
                response = requests.post(
                    f"{self.api_base_url}/api/v1/documents/{doc_id}/process"
                )
                if response.json().get("success"):
                    print(f"✓ 文档 {index}/{total} 处理成功")
                    return True
                else:
                    print(f"✗ 文档 {index}/{total} 处理失败")
                    return False
            except Exception as e:
                print(f"✗ 文档 {index}/{total} 请求失败: {e}")
                return False
        
        # 准备任务列表
        tasks = [(doc_id, i, len(document_ids)) for i, doc_id in enumerate(document_ids, 1)]
        
        # 使用线程池并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_document, tasks))
            
        success_count = sum(1 for r in results if r)
        fail_count = sum(1 for r in results if not r)
        total_time = time.time() - start_time
        
        return {
            "method": f"并行处理 (workers={max_workers})",
            "total_documents": len(document_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "total_time": total_time,
            "avg_time_per_doc": total_time / len(document_ids) if document_ids else 0,
            "documents_per_second": len(document_ids) / total_time if total_time > 0 else 0
        }
    
    async def test_async_processing(self, document_ids: List[str], max_concurrent: int = 3) -> Dict[str, Any]:
        """测试异步处理性能"""
        print(f"\n=== 测试异步处理 (concurrent={max_concurrent}) ===")
        import aiohttp
        
        start_time = time.time()
        success_count = 0
        fail_count = 0
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_document(session, doc_id, index, total):
            async with semaphore:
                try:
                    async with session.post(
                        f"{self.api_base_url}/api/v1/documents/{doc_id}/process"
                    ) as response:
                        data = await response.json()
                        if data.get("success"):
                            print(f"✓ 文档 {index}/{total} 处理成功")
                            return True
                        else:
                            print(f"✗ 文档 {index}/{total} 处理失败")
                            return False
                except Exception as e:
                    print(f"✗ 文档 {index}/{total} 请求失败: {e}")
                    return False
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                process_document(session, doc_id, i, len(document_ids))
                for i, doc_id in enumerate(document_ids, 1)
            ]
            results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r)
        fail_count = sum(1 for r in results if not r)
        total_time = time.time() - start_time
        
        return {
            "method": f"异步处理 (concurrent={max_concurrent})",
            "total_documents": len(document_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "total_time": total_time,
            "avg_time_per_doc": total_time / len(document_ids) if document_ids else 0,
            "documents_per_second": len(document_ids) / total_time if total_time > 0 else 0
        }
    
    def get_test_documents(self, count: int = 10) -> List[str]:
        """获取测试文档ID"""
        try:
            response = requests.get(f"{self.api_base_url}/api/v1/documents")
            data = response.json()
            if data.get("success") and data.get("documents"):
                # 筛选可处理的文档
                available_docs = [
                    doc["document_id"] 
                    for doc in data["documents"] 
                    if doc.get("can_process", False)
                ][:count]
                
                if len(available_docs) < count:
                    print(f"⚠️  只找到 {len(available_docs)} 个可处理的文档")
                
                return available_docs
        except Exception as e:
            print(f"获取文档列表失败: {e}")
        
        return []
    
    def print_results(self, results: List[Dict[str, Any]]):
        """打印测试结果对比"""
        print("\n" + "="*60)
        print("性能测试结果对比")
        print("="*60)
        
        # 打印表头
        print(f"{'方法':<25} {'文档数':<8} {'成功':<6} {'失败':<6} {'总耗时(秒)':<12} {'平均耗时':<12} {'吞吐量(doc/s)':<15}")
        print("-"*60)
        
        # 打印每个结果
        for result in results:
            print(f"{result['method']:<25} "
                  f"{result['total_documents']:<8} "
                  f"{result['success_count']:<6} "
                  f"{result['fail_count']:<6} "
                  f"{result['total_time']:<12.2f} "
                  f"{result['avg_time_per_doc']:<12.2f} "
                  f"{result['documents_per_second']:<15.2f}")
        
        print("="*60)
        
        # 计算性能提升
        if len(results) >= 2:
            serial_time = results[0]["total_time"]
            print("\n性能提升分析:")
            for i in range(1, len(results)):
                speedup = serial_time / results[i]["total_time"] if results[i]["total_time"] > 0 else 0
                improvement = ((serial_time - results[i]["total_time"]) / serial_time * 100) if serial_time > 0 else 0
                print(f"  {results[i]['method']}: {speedup:.2f}x 加速, 节省 {improvement:.1f}% 时间")
    
    def run_comprehensive_test(self, document_count: int = 10):
        """运行综合性能测试"""
        print("\n" + "="*60)
        print(f"开始综合性能测试 (文档数: {document_count})")
        print("="*60)
        
        # 获取测试文档
        document_ids = self.get_test_documents(document_count)
        if not document_ids:
            print("❌ 无法获取测试文档")
            return
        
        print(f"\n准备测试 {len(document_ids)} 个文档")
        
        results = []
        
        # 1. 测试串行处理
        result = self.test_serial_processing(document_ids)
        results.append(result)
        time.sleep(2)  # 给服务器一点休息时间
        
        # 2. 测试不同并发度的并行处理
        for workers in [3, 5, 8]:
            result = self.test_parallel_processing(document_ids, workers)
            results.append(result)
            time.sleep(2)
        
        # 3. 测试异步处理
        loop = asyncio.get_event_loop()
        for concurrent in [3, 5, 8]:
            result = loop.run_until_complete(
                self.test_async_processing(document_ids, concurrent)
            )
            results.append(result)
            time.sleep(2)
        
        # 打印结果
        self.print_results(results)
        
        # 保存结果到文件
        output_file = Path("performance_test_results.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n测试结果已保存到: {output_file}")
        
        return results

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG系统性能测试工具")
    parser.add_argument("--api-url", default="http://localhost:8002", help="API服务器URL")
    parser.add_argument("--count", type=int, default=10, help="测试文档数量")
    parser.add_argument("--method", choices=["all", "serial", "parallel", "async"], 
                       default="all", help="测试方法")
    
    args = parser.parse_args()
    
    tester = PerformanceTest(args.api_url)
    
    if args.method == "all":
        tester.run_comprehensive_test(args.count)
    else:
        document_ids = tester.get_test_documents(args.count)
        if not document_ids:
            print("无法获取测试文档")
            return
        
        if args.method == "serial":
            result = tester.test_serial_processing(document_ids)
        elif args.method == "parallel":
            result = tester.test_parallel_processing(document_ids, 5)
        elif args.method == "async":
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                tester.test_async_processing(document_ids, 5)
            )
        
        tester.print_results([result])

if __name__ == "__main__":
    main()