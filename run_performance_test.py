#!/usr/bin/env python3
"""
RAG-Anything API 快速性能测试脚本
用于验证性能分析报告中识别的主要问题
"""

import asyncio
import aiohttp
import time
import psutil
import json
import statistics
from pathlib import Path
from typing import List, Dict, Any
import sys
import os

# 添加项目路径
sys.path.append(str(Path(__file__).parent / "RAG-Anything"))


class QuickPerformanceTest:
    """快速性能测试类"""
    
    def __init__(self, api_url: str = "http://127.0.0.1:8001"):
        self.api_url = api_url
        self.results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests": {},
            "issues_found": [],
            "recommendations": []
        }
    
    async def check_api_health(self) -> bool:
        """检查API健康状态"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/health", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ API健康检查通过: {data['status']}")
                        return True
        except Exception as e:
            print(f"❌ API健康检查失败: {e}")
            return False
        return False
    
    async def test_serial_batch_processing(self, num_files: int = 5) -> Dict[str, Any]:
        """测试批处理是否真的并行"""
        print(f"\n🔍 测试批处理并发性 ({num_files} 个文件)...")
        
        # 创建测试文件
        test_files = []
        for i in range(num_files):
            file_path = f"/tmp/test_doc_{i}.txt"
            with open(file_path, 'w') as f:
                f.write(f"This is test document {i}\n" * 100)
            test_files.append(file_path)
        
        try:
            async with aiohttp.ClientSession() as session:
                # 上传文件
                document_ids = []
                upload_start = time.time()
                
                for file_path in test_files:
                    with open(file_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename=Path(file_path).name)
                        
                        async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                document_ids.append(result['document_id'])
                
                upload_time = time.time() - upload_start
                
                # 批量处理
                batch_start = time.time()
                batch_data = {
                    "document_ids": document_ids,
                    "parser": "direct_text",  # 使用最快的解析器
                    "parse_method": "auto"
                }
                
                async with session.post(
                    f"{self.api_url}/api/v1/documents/process/batch",
                    json=batch_data,
                    timeout=300
                ) as resp:
                    batch_result = await resp.json()
                
                batch_time = time.time() - batch_start
                
                # 分析结果
                expected_parallel_time = batch_time / num_files  # 如果真正并行的预期时间
                efficiency = (expected_parallel_time * num_files) / batch_time * 100
                
                result = {
                    "num_files": num_files,
                    "upload_time": upload_time,
                    "batch_processing_time": batch_time,
                    "avg_time_per_file": batch_time / num_files,
                    "parallel_efficiency": efficiency,
                    "is_truly_parallel": efficiency > 150  # 如果效率>150%说明有并行
                }
                
                if not result["is_truly_parallel"]:
                    self.results["issues_found"].append(
                        "批处理实际是串行执行，未实现真正的并行处理"
                    )
                    self.results["recommendations"].append(
                        "使用 asyncio.gather() 或 concurrent.futures 实现真正的并行处理"
                    )
                
                print(f"  批处理时间: {batch_time:.2f}s")
                print(f"  平均每文件: {result['avg_time_per_file']:.2f}s")
                print(f"  并行效率: {efficiency:.1f}%")
                print(f"  是否并行: {'✅ 是' if result['is_truly_parallel'] else '❌ 否'}")
                
                return result
                
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            return {"error": str(e)}
        finally:
            # 清理测试文件
            for file_path in test_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    async def test_memory_leak(self, iterations: int = 10) -> Dict[str, Any]:
        """测试内存泄漏"""
        print(f"\n🔍 测试内存泄漏 ({iterations} 次迭代)...")
        
        memory_usage = []
        process = psutil.Process()
        
        # 初始内存
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_usage.append(initial_memory)
        
        try:
            async with aiohttp.ClientSession() as session:
                for i in range(iterations):
                    # 创建并上传小文件
                    file_path = f"/tmp/mem_test_{i}.txt"
                    with open(file_path, 'w') as f:
                        f.write(f"Memory test {i}\n" * 10)
                    
                    # 上传
                    with open(file_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename=f"mem_test_{i}.txt")
                        
                        async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                            await resp.json()
                    
                    # 清理文件
                    os.remove(file_path)
                    
                    # 记录内存
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_usage.append(current_memory)
                    
                    if i % 3 == 0:
                        print(f"  迭代 {i+1}/{iterations}: 内存 {current_memory:.1f}MB (+{current_memory - initial_memory:.1f}MB)")
        
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
        
        # 分析内存增长
        memory_growth = memory_usage[-1] - memory_usage[0]
        avg_growth_per_iteration = memory_growth / iterations
        
        result = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": memory_usage[-1],
            "total_growth_mb": memory_growth,
            "avg_growth_per_iteration_mb": avg_growth_per_iteration,
            "has_memory_leak": avg_growth_per_iteration > 0.5  # 每次迭代增长>0.5MB视为泄漏
        }
        
        if result["has_memory_leak"]:
            self.results["issues_found"].append(
                f"检测到内存泄漏：每次操作增长 {avg_growth_per_iteration:.2f}MB"
            )
            self.results["recommendations"].append(
                "实现定期清理机制，限制全局变量大小，使用弱引用"
            )
        
        print(f"  内存增长: {memory_growth:.1f}MB")
        print(f"  每次迭代: {avg_growth_per_iteration:.2f}MB")
        print(f"  内存泄漏: {'⚠️ 是' if result['has_memory_leak'] else '✅ 否'}")
        
        return result
    
    async def test_cache_efficiency(self) -> Dict[str, Any]:
        """测试缓存效率"""
        print(f"\n🔍 测试缓存效率...")
        
        # 创建相同内容的文件
        content = "This is a test document for cache testing.\n" * 100
        file1 = "/tmp/cache_test_1.txt"
        file2 = "/tmp/cache_test_2.txt"
        
        with open(file1, 'w') as f:
            f.write(content)
        
        # 等待以确保不同的时间戳
        await asyncio.sleep(1)
        
        with open(file2, 'w') as f:
            f.write(content)
        
        try:
            async with aiohttp.ClientSession() as session:
                results = []
                
                for file_path in [file1, file2]:
                    # 上传并处理
                    start_time = time.time()
                    
                    with open(file_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename=Path(file_path).name)
                        
                        async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                            upload_result = await resp.json()
                    
                    document_id = upload_result['document_id']
                    
                    async with session.post(f"{self.api_url}/api/v1/documents/{document_id}/process") as resp:
                        process_result = await resp.json()
                    
                    # 等待处理完成
                    task_id = process_result['task_id']
                    completed = False
                    polls = 0
                    
                    while not completed and polls < 60:
                        await asyncio.sleep(1)
                        async with session.get(f"{self.api_url}/api/v1/tasks/{task_id}") as resp:
                            task_status = await resp.json()
                            if task_status['task']['status'] in ['completed', 'failed']:
                                completed = True
                        polls += 1
                    
                    process_time = time.time() - start_time
                    results.append(process_time)
                
                # 分析缓存效果
                cache_speedup = results[0] / results[1] if results[1] > 0 else 1.0
                
                result = {
                    "first_process_time": results[0],
                    "second_process_time": results[1],
                    "cache_speedup": cache_speedup,
                    "cache_working": cache_speedup > 1.5
                }
                
                if not result["cache_working"]:
                    self.results["issues_found"].append(
                        "缓存未生效：相同内容的文件处理时间相近"
                    )
                    self.results["recommendations"].append(
                        "使用内容哈希而非文件修改时间作为缓存键"
                    )
                
                print(f"  首次处理: {results[0]:.2f}s")
                print(f"  二次处理: {results[1]:.2f}s")
                print(f"  缓存加速: {cache_speedup:.2f}x")
                print(f"  缓存生效: {'✅ 是' if result['cache_working'] else '❌ 否'}")
                
                return result
                
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            return {"error": str(e)}
        finally:
            # 清理测试文件
            for file_path in [file1, file2]:
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    async def test_concurrent_requests(self, num_concurrent: int = 10) -> Dict[str, Any]:
        """测试并发请求处理能力"""
        print(f"\n🔍 测试并发请求处理 ({num_concurrent} 个并发)...")
        
        async def single_request(index: int) -> float:
            """单个请求"""
            start_time = time.time()
            
            try:
                async with aiohttp.ClientSession() as session:
                    # 健康检查请求（轻量级）
                    async with session.get(f"{self.api_url}/health", timeout=10) as resp:
                        await resp.json()
                
                return time.time() - start_time
            except Exception:
                return -1
        
        # 串行执行
        serial_start = time.time()
        serial_times = []
        for i in range(num_concurrent):
            t = await single_request(i)
            if t > 0:
                serial_times.append(t)
        serial_total = time.time() - serial_start
        
        # 并发执行
        concurrent_start = time.time()
        tasks = [single_request(i) for i in range(num_concurrent)]
        concurrent_times = await asyncio.gather(*tasks)
        concurrent_total = time.time() - concurrent_start
        
        # 过滤有效结果
        concurrent_times = [t for t in concurrent_times if t > 0]
        
        result = {
            "num_concurrent": num_concurrent,
            "serial_total_time": serial_total,
            "concurrent_total_time": concurrent_total,
            "speedup": serial_total / concurrent_total if concurrent_total > 0 else 1.0,
            "avg_response_time": statistics.mean(concurrent_times) if concurrent_times else 0,
            "success_rate": len(concurrent_times) / num_concurrent * 100
        }
        
        if result["speedup"] < 2.0:
            self.results["issues_found"].append(
                f"并发处理能力差：{num_concurrent}个并发请求仅获得 {result['speedup']:.1f}x 加速"
            )
            self.results["recommendations"].append(
                "优化事件循环，避免阻塞操作，使用异步I/O"
            )
        
        print(f"  串行时间: {serial_total:.2f}s")
        print(f"  并发时间: {concurrent_total:.2f}s")
        print(f"  加速比: {result['speedup']:.2f}x")
        print(f"  成功率: {result['success_rate']:.1f}%")
        
        return result
    
    async def test_resource_usage(self) -> Dict[str, Any]:
        """测试资源使用情况"""
        print(f"\n🔍 测试资源使用...")
        
        # 获取系统资源
        cpu_percent = psutil.cpu_percent(interval=2)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 检查进程数
        rag_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'rag_api_server' in cmdline or 'RAG-Anything' in cmdline:
                    rag_processes.append(proc)
            except:
                pass
        
        result = {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "disk_usage_percent": disk.percent,
            "disk_free_gb": disk.free / (1024**3),
            "num_rag_processes": len(rag_processes),
            "cpu_underutilized": cpu_percent < 30,
            "memory_pressure": memory.percent > 80,
            "disk_pressure": disk.percent > 90
        }
        
        if result["cpu_underutilized"]:
            self.results["issues_found"].append(
                f"CPU利用率低：仅 {cpu_percent:.1f}%"
            )
            self.results["recommendations"].append(
                "增加并发处理，使用多进程处理CPU密集型任务"
            )
        
        if result["memory_pressure"]:
            self.results["issues_found"].append(
                f"内存压力高：使用率 {memory.percent:.1f}%"
            )
            self.results["recommendations"].append(
                "实现内存限制，定期清理缓存，优化数据结构"
            )
        
        print(f"  CPU使用: {cpu_percent:.1f}%")
        print(f"  内存使用: {memory.percent:.1f}%")
        print(f"  磁盘使用: {disk.percent:.1f}%")
        print(f"  RAG进程数: {len(rag_processes)}")
        
        return result
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("RAG-Anything API 快速性能测试")
        print("=" * 60)
        
        # 检查API健康
        if not await self.check_api_health():
            print("\n❌ API不可用，请先启动API服务器:")
            print("   cd RAG-Anything/api")
            print("   python rag_api_server.py")
            return
        
        # 运行各项测试
        self.results["tests"]["batch_processing"] = await self.test_serial_batch_processing()
        self.results["tests"]["memory_leak"] = await self.test_memory_leak()
        self.results["tests"]["cache_efficiency"] = await self.test_cache_efficiency()
        self.results["tests"]["concurrent_requests"] = await self.test_concurrent_requests()
        self.results["tests"]["resource_usage"] = await self.test_resource_usage()
        
        # 生成报告
        self._generate_report()
    
    def _generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("测试结果总结")
        print("=" * 60)
        
        # 问题总结
        if self.results["issues_found"]:
            print("\n🔴 发现的问题:")
            for i, issue in enumerate(self.results["issues_found"], 1):
                print(f"  {i}. {issue}")
        else:
            print("\n✅ 未发现明显性能问题")
        
        # 优化建议
        if self.results["recommendations"]:
            print("\n💡 优化建议:")
            for i, rec in enumerate(self.results["recommendations"], 1):
                print(f"  {i}. {rec}")
        
        # 性能评分
        score = self._calculate_performance_score()
        print(f"\n📊 总体性能评分: {score}/100")
        
        if score < 40:
            print("   评级: 🔴 差 - 需要立即优化")
        elif score < 60:
            print("   评级: 🟡 中等 - 建议优化")
        elif score < 80:
            print("   评级: 🟢 良好 - 可以优化")
        else:
            print("   评级: 🎯 优秀 - 性能良好")
        
        # 保存报告
        report_file = f"performance_test_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 详细报告已保存: {report_file}")
    
    def _calculate_performance_score(self) -> int:
        """计算性能评分"""
        score = 100
        
        # 根据问题扣分
        score -= len(self.results["issues_found"]) * 15
        
        # 根据测试结果调整
        tests = self.results["tests"]
        
        # 批处理并行性
        if "batch_processing" in tests and not tests["batch_processing"].get("is_truly_parallel", True):
            score -= 20
        
        # 内存泄漏
        if "memory_leak" in tests and tests["memory_leak"].get("has_memory_leak", False):
            score -= 15
        
        # 缓存效率
        if "cache_efficiency" in tests and not tests["cache_efficiency"].get("cache_working", True):
            score -= 10
        
        # 资源使用
        if "resource_usage" in tests:
            resource = tests["resource_usage"]
            if resource.get("cpu_underutilized", False):
                score -= 10
            if resource.get("memory_pressure", False):
                score -= 15
        
        return max(0, min(100, score))


async def main():
    """主函数"""
    tester = QuickPerformanceTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    print("🚀 启动RAG-Anything API性能测试...")
    print("   确保API服务器运行在 http://127.0.0.1:8001")
    print()
    
    asyncio.run(main())