# RAG-Anything API 性能测试方案

## 测试目标

1. **基准性能测试**: 建立当前系统性能基线
2. **负载测试**: 确定系统最大处理能力
3. **压力测试**: 找出系统崩溃点
4. **并发测试**: 验证并发处理能力
5. **持久性测试**: 检测内存泄漏和性能退化

## 1. 测试环境准备

### 1.1 硬件要求
```yaml
测试服务器:
  CPU: 8核心以上
  内存: 16GB以上
  GPU: NVIDIA GPU (可选，用于GPU测试)
  存储: SSD，100GB可用空间

负载生成器:
  CPU: 4核心
  内存: 8GB
  网络: 与测试服务器同一局域网
```

### 1.2 软件环境
```bash
# 安装性能测试工具
pip install locust pytest-benchmark pytest-asyncio memory_profiler
pip install gputil psutil aiohttp

# 安装监控工具
sudo apt-get install htop iotop nethogs
pip install prometheus-client grafana-api

# GPU监控（如果有GPU）
pip install nvidia-ml-py3
```

### 1.3 测试数据准备
```python
# 生成不同大小的测试文档
测试文档集:
  - 小文档: 100个 x 100KB (PDF/DOCX/TXT)
  - 中文档: 50个 x 1MB
  - 大文档: 20个 x 10MB
  - 混合类型: PDF(40%), DOCX(30%), TXT(20%), 其他(10%)
```

## 2. 性能测试脚本

### 2.1 基准性能测试脚本

创建文件 `performance_tests/benchmark_test.py`:

```python
#!/usr/bin/env python3
"""
基准性能测试脚本
测试单文档处理性能和批处理性能
"""

import asyncio
import time
import statistics
import json
from pathlib import Path
from typing import List, Dict, Any
import aiohttp
import psutil
import GPUtil

class BenchmarkTest:
    def __init__(self, api_url: str = "http://127.0.0.1:8001"):
        self.api_url = api_url
        self.results = {
            "single_document": [],
            "batch_processing": [],
            "cache_performance": [],
            "resource_usage": []
        }
    
    async def test_single_document(self, file_path: str) -> Dict[str, Any]:
        """测试单文档处理性能"""
        start_time = time.time()
        
        # 记录初始资源使用
        initial_cpu = psutil.cpu_percent(interval=1)
        initial_memory = psutil.virtual_memory().percent
        
        async with aiohttp.ClientSession() as session:
            # 上传文档
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=Path(file_path).name)
                
                upload_start = time.time()
                async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                    upload_result = await resp.json()
                upload_time = time.time() - upload_start
            
            document_id = upload_result.get('document_id')
            
            # 触发处理
            process_start = time.time()
            async with session.post(f"{self.api_url}/api/v1/documents/{document_id}/process") as resp:
                process_result = await resp.json()
            
            task_id = process_result.get('task_id')
            
            # 等待处理完成
            processing_complete = False
            poll_count = 0
            while not processing_complete and poll_count < 300:  # 最多等待5分钟
                await asyncio.sleep(1)
                async with session.get(f"{self.api_url}/api/v1/tasks/{task_id}") as resp:
                    task_status = await resp.json()
                    if task_status['task']['status'] in ['completed', 'failed']:
                        processing_complete = True
                poll_count += 1
            
            process_time = time.time() - process_start
        
        # 记录资源使用
        final_cpu = psutil.cpu_percent(interval=1)
        final_memory = psutil.virtual_memory().percent
        
        total_time = time.time() - start_time
        
        result = {
            "file_path": file_path,
            "file_size": Path(file_path).stat().st_size,
            "upload_time": upload_time,
            "process_time": process_time,
            "total_time": total_time,
            "cpu_usage": final_cpu - initial_cpu,
            "memory_usage": final_memory - initial_memory,
            "success": task_status['task']['status'] == 'completed'
        }
        
        self.results["single_document"].append(result)
        return result
    
    async def test_batch_processing(self, file_paths: List[str], batch_size: int = 10) -> Dict[str, Any]:
        """测试批量处理性能"""
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # 批量上传
            upload_start = time.time()
            document_ids = []
            
            for file_path in file_paths[:batch_size]:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=Path(file_path).name)
                    
                    async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                        result = await resp.json()
                        document_ids.append(result['document_id'])
            
            upload_time = time.time() - upload_start
            
            # 批量处理
            process_start = time.time()
            batch_data = {
                "document_ids": document_ids,
                "parser": "auto",
                "parse_method": "auto"
            }
            
            async with session.post(
                f"{self.api_url}/api/v1/documents/process/batch",
                json=batch_data
            ) as resp:
                batch_result = await resp.json()
            
            batch_operation_id = batch_result.get('batch_operation_id')
            
            # 等待批处理完成
            processing_complete = False
            poll_count = 0
            while not processing_complete and poll_count < 600:  # 最多等待10分钟
                await asyncio.sleep(2)
                async with session.get(f"{self.api_url}/api/v1/batch-operations/{batch_operation_id}") as resp:
                    batch_status = await resp.json()
                    if batch_status['status'] == 'completed':
                        processing_complete = True
                poll_count += 1
            
            process_time = time.time() - process_start
        
        total_time = time.time() - start_time
        
        result = {
            "batch_size": batch_size,
            "upload_time": upload_time,
            "process_time": process_time,
            "total_time": total_time,
            "throughput": batch_size / total_time * 60,  # docs/min
            "avg_time_per_doc": total_time / batch_size,
            "cache_performance": batch_result.get('cache_performance', {})
        }
        
        self.results["batch_processing"].append(result)
        return result
    
    async def test_cache_performance(self, file_path: str, iterations: int = 3) -> Dict[str, Any]:
        """测试缓存性能"""
        results = []
        
        for i in range(iterations):
            result = await self.test_single_document(file_path)
            results.append(result['process_time'])
            
            # 清理文档以便重新测试
            await self._cleanup_document(result.get('document_id'))
        
        cache_result = {
            "file_path": file_path,
            "iterations": iterations,
            "first_process_time": results[0],
            "cached_process_times": results[1:],
            "cache_speedup": results[0] / statistics.mean(results[1:]) if len(results) > 1 else 1.0
        }
        
        self.results["cache_performance"].append(cache_result)
        return cache_result
    
    async def run_benchmark_suite(self, test_files: List[str]):
        """运行完整的基准测试套件"""
        print("🚀 开始基准性能测试...")
        
        # 1. 单文档测试
        print("\n📄 测试单文档处理性能...")
        for file_path in test_files[:5]:  # 测试前5个文件
            result = await self.test_single_document(file_path)
            print(f"  ✓ {Path(file_path).name}: {result['total_time']:.2f}s")
        
        # 2. 批处理测试
        print("\n📦 测试批量处理性能...")
        for batch_size in [5, 10, 20]:
            result = await self.test_batch_processing(test_files, batch_size)
            print(f"  ✓ Batch {batch_size}: {result['throughput']:.1f} docs/min")
        
        # 3. 缓存测试
        print("\n💾 测试缓存性能...")
        cache_result = await self.test_cache_performance(test_files[0])
        print(f"  ✓ Cache speedup: {cache_result['cache_speedup']:.2f}x")
        
        # 生成报告
        self._generate_report()
    
    def _generate_report(self):
        """生成性能测试报告"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "single_document_stats": self._calculate_stats(self.results["single_document"], "total_time"),
            "batch_processing_stats": self._calculate_stats(self.results["batch_processing"], "throughput"),
            "cache_performance": self.results["cache_performance"],
            "detailed_results": self.results
        }
        
        with open("benchmark_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("\n📊 性能测试报告已生成: benchmark_report.json")
        self._print_summary(report)
    
    def _calculate_stats(self, data: List[Dict], key: str) -> Dict[str, float]:
        """计算统计数据"""
        if not data:
            return {}
        
        values = [d[key] for d in data if key in d]
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0
        }
    
    def _print_summary(self, report: Dict):
        """打印测试摘要"""
        print("\n" + "="*50)
        print("性能测试摘要")
        print("="*50)
        
        if "single_document_stats" in report:
            stats = report["single_document_stats"]
            print(f"\n单文档处理时间:")
            print(f"  平均: {stats.get('mean', 0):.2f}s")
            print(f"  最快: {stats.get('min', 0):.2f}s")
            print(f"  最慢: {stats.get('max', 0):.2f}s")
        
        if "batch_processing_stats" in report:
            stats = report["batch_processing_stats"]
            print(f"\n批处理吞吐量:")
            print(f"  平均: {stats.get('mean', 0):.1f} docs/min")
            print(f"  最高: {stats.get('max', 0):.1f} docs/min")
            print(f"  最低: {stats.get('min', 0):.1f} docs/min")
    
    async def _cleanup_document(self, document_id: str):
        """清理测试文档"""
        if not document_id:
            return
        
        async with aiohttp.ClientSession() as session:
            await session.delete(f"{self.api_url}/api/v1/documents", 
                                json={"document_ids": [document_id]})


async def main():
    # 准备测试文件
    test_files = list(Path("test_documents").glob("*.pdf"))[:20]
    
    if not test_files:
        print("❌ 未找到测试文件，请在 test_documents 目录下准备测试文档")
        return
    
    # 运行基准测试
    benchmark = BenchmarkTest()
    await benchmark.run_benchmark_suite(test_files)


if __name__ == "__main__":
    asyncio.run(main())
```

### 2.2 负载测试脚本（使用Locust）

创建文件 `performance_tests/locustfile.py`:

```python
from locust import HttpUser, task, between, events
import random
import time
from pathlib import Path
import json

class RAGAPIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """初始化测试数据"""
        self.test_files = list(Path("test_documents").glob("*"))
        self.uploaded_documents = []
    
    @task(3)
    def upload_document(self):
        """上传文档任务"""
        if not self.test_files:
            return
        
        file_path = random.choice(self.test_files)
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            
            with self.client.post("/api/v1/documents/upload", 
                                 files=files, 
                                 catch_response=True) as response:
                if response.status_code == 200:
                    data = response.json()
                    self.uploaded_documents.append(data['document_id'])
                    response.success()
                else:
                    response.failure(f"Upload failed: {response.status_code}")
    
    @task(2)
    def process_document(self):
        """处理文档任务"""
        if not self.uploaded_documents:
            self.upload_document()
            return
        
        document_id = random.choice(self.uploaded_documents)
        
        with self.client.post(f"/api/v1/documents/{document_id}/process",
                             catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Process failed: {response.status_code}")
    
    @task(5)
    def query_documents(self):
        """查询文档任务"""
        queries = [
            "What is the main topic?",
            "Summarize the key points",
            "Find information about technology",
            "What are the conclusions?",
            "Explain the methodology"
        ]
        
        query_data = {
            "query": random.choice(queries),
            "mode": random.choice(["hybrid", "local", "global"]),
            "vlm_enhanced": False
        }
        
        with self.client.post("/api/v1/query",
                             json=query_data,
                             catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Query failed: {response.status_code}")
    
    @task(1)
    def batch_process(self):
        """批量处理任务"""
        if len(self.uploaded_documents) < 5:
            return
        
        batch_size = random.randint(3, 10)
        document_ids = random.sample(self.uploaded_documents, min(batch_size, len(self.uploaded_documents)))
        
        batch_data = {
            "document_ids": document_ids,
            "parser": "auto",
            "parse_method": "auto"
        }
        
        with self.client.post("/api/v1/documents/process/batch",
                             json=batch_data,
                             catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Batch process failed: {response.status_code}")

# 自定义统计收集
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """收集详细的性能指标"""
    if exception:
        print(f"Request failed: {name} - {exception}")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时生成报告"""
    stats = environment.stats
    
    report = {
        "total_requests": stats.total.num_requests,
        "failure_rate": stats.total.failure_ratio,
        "avg_response_time": stats.total.avg_response_time,
        "median_response_time": stats.total.median_response_time,
        "p95_response_time": stats.total.get_response_time_percentile(0.95),
        "p99_response_time": stats.total.get_response_time_percentile(0.99),
        "rps": stats.total.current_rps
    }
    
    with open("load_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n负载测试完成:")
    print(f"  总请求数: {report['total_requests']}")
    print(f"  失败率: {report['failure_rate']:.2%}")
    print(f"  平均响应时间: {report['avg_response_time']:.2f}ms")
    print(f"  P95响应时间: {report['p95_response_time']:.2f}ms")
    print(f"  RPS: {report['rps']:.2f}")
```

### 2.3 并发测试脚本

创建文件 `performance_tests/concurrency_test.py`:

```python
#!/usr/bin/env python3
"""
并发处理能力测试
测试系统在不同并发级别下的表现
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Any
import statistics
import json

class ConcurrencyTest:
    def __init__(self, api_url: str = "http://127.0.0.1:8001"):
        self.api_url = api_url
        self.results = []
    
    async def concurrent_upload_and_process(self, file_paths: List[str], concurrency: int):
        """并发上传和处理文档"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_single_file(file_path: str) -> Dict[str, Any]:
            async with semaphore:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    # 上传
                    with open(file_path, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename=Path(file_path).name)
                        
                        async with session.post(f"{self.api_url}/api/v1/documents/upload", data=data) as resp:
                            upload_result = await resp.json()
                    
                    document_id = upload_result['document_id']
                    
                    # 处理
                    async with session.post(f"{self.api_url}/api/v1/documents/{document_id}/process") as resp:
                        process_result = await resp.json()
                    
                    task_id = process_result['task_id']
                    
                    # 轮询状态
                    completed = False
                    polls = 0
                    while not completed and polls < 300:
                        await asyncio.sleep(1)
                        async with session.get(f"{self.api_url}/api/v1/tasks/{task_id}") as resp:
                            task_status = await resp.json()
                            if task_status['task']['status'] in ['completed', 'failed']:
                                completed = True
                        polls += 1
                
                total_time = time.time() - start_time
                
                return {
                    "file_path": file_path,
                    "time": total_time,
                    "success": task_status['task']['status'] == 'completed'
                }
        
        # 创建所有任务
        tasks = [process_single_file(fp) for fp in file_paths]
        
        # 执行并收集结果
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # 分析结果
        successful = [r for r in results if isinstance(r, dict) and r.get('success')]
        failed = len(results) - len(successful)
        times = [r['time'] for r in successful]
        
        return {
            "concurrency": concurrency,
            "total_files": len(file_paths),
            "successful": len(successful),
            "failed": failed,
            "total_time": total_time,
            "throughput": len(successful) / total_time * 60,  # docs/min
            "avg_time": statistics.mean(times) if times else 0,
            "median_time": statistics.median(times) if times else 0,
            "min_time": min(times) if times else 0,
            "max_time": max(times) if times else 0
        }
    
    async def run_concurrency_tests(self, file_paths: List[str]):
        """运行不同并发级别的测试"""
        concurrency_levels = [1, 2, 5, 10, 20, 50]
        
        for level in concurrency_levels:
            print(f"\n测试并发级别: {level}")
            
            # 使用部分文件进行测试
            test_files = file_paths[:min(level * 2, len(file_paths))]
            
            result = await self.concurrent_upload_and_process(test_files, level)
            self.results.append(result)
            
            print(f"  ✓ 吞吐量: {result['throughput']:.1f} docs/min")
            print(f"  ✓ 平均时间: {result['avg_time']:.2f}s")
            print(f"  ✓ 成功率: {result['successful']}/{result['total_files']}")
        
        self._generate_report()
    
    def _generate_report(self):
        """生成并发测试报告"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": self.results,
            "optimal_concurrency": self._find_optimal_concurrency()
        }
        
        with open("concurrency_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("\n📊 并发测试报告已生成: concurrency_test_report.json")
        self._plot_results()
    
    def _find_optimal_concurrency(self) -> int:
        """找出最优并发级别"""
        if not self.results:
            return 1
        
        # 基于吞吐量找出最优并发
        best = max(self.results, key=lambda x: x['throughput'])
        return best['concurrency']
    
    def _plot_results(self):
        """绘制结果图表（如果matplotlib可用）"""
        try:
            import matplotlib.pyplot as plt
            
            concurrency = [r['concurrency'] for r in self.results]
            throughput = [r['throughput'] for r in self.results]
            avg_time = [r['avg_time'] for r in self.results]
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            
            # 吞吐量图
            ax1.plot(concurrency, throughput, 'b-o')
            ax1.set_xlabel('并发级别')
            ax1.set_ylabel('吞吐量 (docs/min)')
            ax1.set_title('并发级别 vs 吞吐量')
            ax1.grid(True)
            
            # 响应时间图
            ax2.plot(concurrency, avg_time, 'r-o')
            ax2.set_xlabel('并发级别')
            ax2.set_ylabel('平均响应时间 (s)')
            ax2.set_title('并发级别 vs 响应时间')
            ax2.grid(True)
            
            plt.tight_layout()
            plt.savefig('concurrency_test_results.png')
            print("  ✓ 图表已保存: concurrency_test_results.png")
        except ImportError:
            pass
```

## 3. 执行测试计划

### 3.1 测试执行步骤

```bash
# 1. 准备测试环境
mkdir -p performance_tests test_documents
cd performance_tests

# 2. 准备测试数据
python generate_test_documents.py

# 3. 启动监控
python system_monitor.py &

# 4. 执行基准测试
python benchmark_test.py

# 5. 执行负载测试
locust -f locustfile.py --host=http://127.0.0.1:8001 \
       --users=50 --spawn-rate=2 --time=10m \
       --html=load_test_report.html

# 6. 执行并发测试
python concurrency_test.py

# 7. 执行压力测试
locust -f locustfile.py --host=http://127.0.0.1:8001 \
       --users=200 --spawn-rate=10 --time=5m \
       --html=stress_test_report.html

# 8. 执行持久性测试
python endurance_test.py --duration=3600  # 1小时
```

### 3.2 监控脚本

创建文件 `performance_tests/system_monitor.py`:

```python
#!/usr/bin/env python3
"""
系统资源监控脚本
实时监控CPU、内存、GPU和磁盘使用情况
"""

import psutil
import GPUtil
import time
import json
from datetime import datetime
import threading

class SystemMonitor:
    def __init__(self, interval: int = 5):
        self.interval = interval
        self.monitoring = False
        self.data = []
    
    def start(self):
        """开始监控"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop)
        thread.daemon = True
        thread.start()
        print(f"📊 系统监控已启动 (间隔: {self.interval}秒)")
    
    def stop(self):
        """停止监控"""
        self.monitoring = False
        self._save_data()
        print("📊 系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            metrics = self._collect_metrics()
            self.data.append(metrics)
            
            # 实时显示关键指标
            print(f"\r[{metrics['timestamp']}] "
                  f"CPU: {metrics['cpu_percent']:.1f}% | "
                  f"MEM: {metrics['memory_percent']:.1f}% | "
                  f"DISK I/O: R={metrics['disk_read_mb']:.1f}MB/s W={metrics['disk_write_mb']:.1f}MB/s",
                  end="")
            
            time.sleep(self.interval)
    
    def _collect_metrics(self) -> dict:
        """收集系统指标"""
        # CPU指标
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        
        # 内存指标
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # 磁盘I/O
        disk_io = psutil.disk_io_counters()
        disk_usage = psutil.disk_usage('/')
        
        # 网络I/O
        net_io = psutil.net_io_counters()
        
        # GPU指标（如果可用）
        gpu_metrics = {}
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_metrics = {
                    "gpu_load": gpu.load * 100,
                    "gpu_memory_used": gpu.memoryUsed,
                    "gpu_memory_total": gpu.memoryTotal,
                    "gpu_temperature": gpu.temperature
                }
        except:
            pass
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "cpu_per_core": cpu_per_core,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "memory_used_gb": memory.used / (1024**3),
            "swap_percent": swap.percent,
            "disk_usage_percent": disk_usage.percent,
            "disk_read_mb": disk_io.read_bytes / (1024**2) / self.interval,
            "disk_write_mb": disk_io.write_bytes / (1024**2) / self.interval,
            "network_sent_mb": net_io.bytes_sent / (1024**2) / self.interval,
            "network_recv_mb": net_io.bytes_recv / (1024**2) / self.interval,
            **gpu_metrics
        }
    
    def _save_data(self):
        """保存监控数据"""
        with open(f"system_metrics_{int(time.time())}.json", "w") as f:
            json.dump(self.data, f, indent=2)
        
        # 生成摘要
        self._generate_summary()
    
    def _generate_summary(self):
        """生成监控摘要"""
        if not self.data:
            return
        
        summary = {
            "duration_seconds": len(self.data) * self.interval,
            "cpu_avg": sum(d['cpu_percent'] for d in self.data) / len(self.data),
            "cpu_max": max(d['cpu_percent'] for d in self.data),
            "memory_avg": sum(d['memory_percent'] for d in self.data) / len(self.data),
            "memory_max": max(d['memory_percent'] for d in self.data)
        }
        
        with open("monitoring_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 监控摘要:")
        print(f"  平均CPU: {summary['cpu_avg']:.1f}%")
        print(f"  峰值CPU: {summary['cpu_max']:.1f}%")
        print(f"  平均内存: {summary['memory_avg']:.1f}%")
        print(f"  峰值内存: {summary['memory_max']:.1f}%")

if __name__ == "__main__":
    monitor = SystemMonitor(interval=5)
    monitor.start()
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
```

## 4. 性能指标收集

### 4.1 关键性能指标 (KPIs)

| 指标类别 | 具体指标 | 目标值 | 告警阈值 |
|---------|---------|--------|---------|
| **响应时间** | | | |
| P50 响应时间 | 中位数响应时间 | < 2s | > 5s |
| P95 响应时间 | 95分位响应时间 | < 10s | > 30s |
| P99 响应时间 | 99分位响应时间 | < 30s | > 60s |
| **吞吐量** | | | |
| 文档处理速率 | docs/min | > 60 | < 20 |
| 并发处理能力 | 并发数 | > 20 | < 5 |
| 批处理效率 | 相对串行提升 | > 5x | < 2x |
| **资源使用** | | | |
| CPU利用率 | 百分比 | 60-80% | > 90% |
| 内存使用率 | 百分比 | < 70% | > 85% |
| GPU利用率 | 百分比 | 70-90% | < 30% |
| **可靠性** | | | |
| 成功率 | 百分比 | > 99% | < 95% |
| 错误率 | 百分比 | < 1% | > 5% |
| 缓存命中率 | 百分比 | > 60% | < 30% |

### 4.2 测试结果分析模板

```python
# performance_tests/analyze_results.py

def analyze_test_results():
    """分析所有测试结果并生成综合报告"""
    
    # 加载各项测试结果
    benchmark = json.load(open("benchmark_report.json"))
    load_test = json.load(open("load_test_report.json"))
    concurrency = json.load(open("concurrency_test_report.json"))
    monitoring = json.load(open("monitoring_summary.json"))
    
    # 综合分析
    analysis = {
        "performance_score": calculate_performance_score(benchmark, load_test),
        "bottlenecks": identify_bottlenecks(monitoring),
        "optimization_recommendations": generate_recommendations(all_results),
        "comparison_with_baseline": compare_with_baseline(current, baseline)
    }
    
    # 生成HTML报告
    generate_html_report(analysis)
```

## 5. 持续性能监控

### 5.1 Prometheus + Grafana 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'rag-api'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/metrics'
```

### 5.2 自定义指标导出

```python
# performance_tests/metrics_exporter.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# 定义指标
document_processed = Counter('documents_processed_total', 'Total processed documents')
processing_time = Histogram('document_processing_seconds', 'Document processing time')
active_tasks = Gauge('active_tasks', 'Number of active tasks')
cache_hit_rate = Gauge('cache_hit_rate', 'Cache hit rate percentage')

def export_metrics():
    """导出自定义指标到Prometheus"""
    start_http_server(9090)
    
    while True:
        # 更新指标
        update_metrics_from_api()
        time.sleep(10)
```

## 6. 测试报告模板

### 6.1 执行摘要
- 测试日期和环境
- 主要发现
- 性能评分
- 关键建议

### 6.2 详细结果
- 各项测试数据
- 图表和趋势
- 与基线对比
- 异常和问题

### 6.3 优化建议
- 立即行动项
- 短期改进
- 长期规划

### 6.4 附录
- 原始数据
- 测试脚本
- 系统配置

## 结论

本测试方案提供了全面的性能测试框架，包括：
- **5种测试类型**覆盖不同性能方面
- **自动化测试脚本**减少人工操作
- **实时监控**捕获系统行为
- **详细报告**支持决策

建议每次重大更新后执行完整测试套件，日常进行基准测试监控性能退化。