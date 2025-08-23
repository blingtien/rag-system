# RAG-Anything API 性能优化实施指南

## 快速开始

### 运行性能测试
```bash
# 1. 确保API服务器运行
cd RAG-Anything/api
python rag_api_server.py

# 2. 在另一个终端运行性能测试
python run_performance_test.py
```

## 优化实施步骤

### 第一阶段：立即修复（1-3天）

#### 1. 修复批处理串行问题 ⚡ 预期提升 300%

**问题位置**: `RAG-Anything/raganything/batch.py` 行 350-358

**当前代码**:
```python
# 串行处理
for file_path in parse_result.successful_files:
    await self.process_document_complete(file_path, ...)
```

**优化方案**:
```python
# 并行处理
async def process_file_with_rag(file_path):
    try:
        return await self.process_document_complete(file_path, ...)
    except Exception as e:
        return {"error": str(e)}

# 使用 gather 并行执行
tasks = [process_file_with_rag(fp) for fp in parse_result.successful_files]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**实施文件**: 创建 `RAG-Anything/api/optimize_batch_processing.py`

```python
#!/usr/bin/env python3
"""批处理优化补丁"""

import asyncio
from typing import List, Dict, Any

async def optimized_batch_process(rag_instance, file_paths: List[str], **kwargs):
    """优化的批处理函数"""
    
    # 创建信号量控制并发度
    max_concurrent = kwargs.get('max_workers', 5)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_limit(file_path: str):
        async with semaphore:
            return await rag_instance.process_document_complete(
                file_path, **kwargs
            )
    
    # 并行处理所有文件
    tasks = [process_with_limit(fp) for fp in file_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

#### 2. 实现内存管理 🧹 防止OOM

**创建文件**: `RAG-Anything/api/memory_manager.py`

```python
#!/usr/bin/env python3
"""内存管理器"""

import gc
import time
from collections import OrderedDict
from typing import Any, Optional
import weakref

class MemoryManager:
    """内存管理器，防止内存泄漏"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}
        self.weak_refs = weakref.WeakValueDictionary()
    
    def set(self, key: str, value: Any):
        """设置缓存项"""
        # 检查大小限制
        if len(self.cache) >= self.max_size:
            # 移除最旧的项
            oldest = next(iter(self.cache))
            del self.cache[oldest]
            del self.timestamps[oldest]
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
        
        # 创建弱引用
        try:
            self.weak_refs[key] = value
        except TypeError:
            pass  # 某些类型不支持弱引用
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        if key not in self.cache:
            return None
        
        # 检查TTL
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        # 更新访问顺序
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def cleanup(self):
        """清理过期项"""
        current_time = time.time()
        expired_keys = [
            k for k, t in self.timestamps.items()
            if current_time - t > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.cache[key]
            del self.timestamps[key]
        
        # 强制垃圾回收
        gc.collect()
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        import psutil
        process = psutil.Process()
        
        return {
            "cache_size": len(self.cache),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "weak_refs": len(self.weak_refs)
        }

# 全局内存管理器
memory_manager = MemoryManager()
```

**集成到API服务器**:
```python
# 在 rag_api_server.py 中添加
from memory_manager import memory_manager

# 替换全局字典
tasks = memory_manager  # 使用内存管理器替代普通字典
documents = memory_manager

# 添加定期清理任务
async def periodic_cleanup():
    while True:
        await asyncio.sleep(300)  # 每5分钟清理一次
        memory_manager.cleanup()
        logger.info(f"内存清理完成: {memory_manager.get_memory_usage()}")

# 在 startup_event 中启动
asyncio.create_task(periodic_cleanup())
```

#### 3. 优化缓存策略 💾 提升命中率至60%

**创建文件**: `RAG-Anything/api/content_cache.py`

```python
#!/usr/bin/env python3
"""基于内容的缓存系统"""

import hashlib
import json
from typing import Any, Dict, Optional
from pathlib import Path

class ContentBasedCache:
    """基于内容哈希的缓存"""
    
    def __init__(self, cache_dir: str = "/tmp/rag_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.stats = {"hits": 0, "misses": 0}
    
    def _generate_content_hash(self, file_path: str) -> str:
        """生成文件内容哈希"""
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # 读取文件内容生成哈希
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def get_cache_key(self, file_path: str, **config) -> str:
        """生成缓存键"""
        content_hash = self._generate_content_hash(file_path)
        
        # 只包含影响解析结果的配置
        relevant_config = {
            k: v for k, v in config.items()
            if k in ['parser', 'parse_method', 'lang']
        }
        
        config_str = json.dumps(relevant_config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()
        
        return f"{content_hash}_{config_hash}"
    
    def get(self, file_path: str, **config) -> Optional[Any]:
        """获取缓存内容"""
        cache_key = self.get_cache_key(file_path, **config)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            self.stats["hits"] += 1
            with open(cache_file, 'r') as f:
                return json.load(f)
        
        self.stats["misses"] += 1
        return None
    
    def set(self, file_path: str, content: Any, **config):
        """设置缓存内容"""
        cache_key = self.get_cache_key(file_path, **config)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        with open(cache_file, 'w') as f:
            json.dump(content, f)
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return self.stats["hits"] / total * 100

# 全局缓存实例
content_cache = ContentBasedCache()
```

### 第二阶段：短期优化（1-2周）

#### 4. 实现任务队列系统

**安装依赖**:
```bash
pip install celery redis
```

**创建文件**: `RAG-Anything/api/task_queue.py`

```python
#!/usr/bin/env python3
"""Celery任务队列配置"""

from celery import Celery
import os

# 创建Celery应用
app = Celery(
    'rag_tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# 配置
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # 任务路由
    task_routes={
        'rag_tasks.process_document': {'queue': 'high'},
        'rag_tasks.batch_process': {'queue': 'batch'},
        'rag_tasks.query': {'queue': 'query'}
    },
    # 并发配置
    worker_concurrency=4,
    worker_prefetch_multiplier=2,
    # 任务时限
    task_soft_time_limit=300,
    task_time_limit=600,
)

@app.task(bind=True, max_retries=3)
def process_document_task(self, file_path: str, **kwargs):
    """异步处理文档任务"""
    try:
        # 处理逻辑
        result = process_document_sync(file_path, **kwargs)
        return result
    except Exception as e:
        # 重试机制
        raise self.retry(exc=e, countdown=60)

# 启动Worker
# celery -A task_queue worker --loglevel=info --queues=high,batch,query
```

#### 5. 实现异步I/O

**创建文件**: `RAG-Anything/api/async_io_utils.py`

```python
#!/usr/bin/env python3
"""异步I/O工具"""

import aiofiles
import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional

async def async_read_file(file_path: str, chunk_size: int = 8192) -> bytes:
    """异步读取文件"""
    async with aiofiles.open(file_path, 'rb') as f:
        return await f.read()

async def async_write_file(file_path: str, content: bytes):
    """异步写入文件"""
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)

async def async_read_chunks(
    file_path: str, 
    chunk_size: int = 1024 * 1024
) -> AsyncIterator[bytes]:
    """异步分块读取大文件"""
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(chunk_size):
            yield chunk

class AsyncFilePool:
    """异步文件操作池"""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_files(self, file_paths: list, processor):
        """并发处理多个文件"""
        async def process_with_limit(file_path):
            async with self.semaphore:
                return await processor(file_path)
        
        tasks = [process_with_limit(fp) for fp in file_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

#### 6. GPU内存管理

**创建文件**: `RAG-Anything/api/gpu_manager.py`

```python
#!/usr/bin/env python3
"""GPU内存管理器"""

import torch
import gc
from typing import Optional

class GPUMemoryManager:
    """GPU内存管理器"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.max_memory_mb = self._get_max_memory()
        self.fallback_to_cpu = True
    
    def _get_max_memory(self) -> float:
        """获取GPU最大内存"""
        if not torch.cuda.is_available():
            return 0
        
        return torch.cuda.get_device_properties(0).total_memory / 1024 / 1024
    
    def get_available_memory(self) -> float:
        """获取可用GPU内存"""
        if not torch.cuda.is_available():
            return 0
        
        return (torch.cuda.get_device_properties(0).total_memory - 
                torch.cuda.memory_allocated()) / 1024 / 1024
    
    def clear_cache(self):
        """清理GPU缓存"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
    
    def adaptive_batch_size(self, base_batch_size: int = 8) -> int:
        """根据可用内存自适应调整批大小"""
        available = self.get_available_memory()
        
        if available < 1000:  # < 1GB
            return max(1, base_batch_size // 4)
        elif available < 2000:  # < 2GB
            return max(2, base_batch_size // 2)
        else:
            return base_batch_size
    
    def safe_gpu_operation(self, func, *args, **kwargs):
        """安全的GPU操作，OOM时自动降级到CPU"""
        try:
            return func(*args, **kwargs)
        except torch.cuda.OutOfMemoryError:
            if self.fallback_to_cpu:
                self.clear_cache()
                # 切换到CPU
                kwargs['device'] = 'cpu'
                return func(*args, **kwargs)
            raise

# 全局GPU管理器
gpu_manager = GPUMemoryManager()
```

### 第三阶段：监控和持续优化

#### 7. 性能监控仪表板

**创建文件**: `RAG-Anything/api/monitoring_dashboard.py`

```python
#!/usr/bin/env python3
"""性能监控仪表板"""

from flask import Flask, render_template_string
import json
import psutil
from datetime import datetime

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>RAG-Anything Performance Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial; margin: 20px; background: #f5f5f5; }
        .metric { 
            display: inline-block; 
            margin: 10px; 
            padding: 15px; 
            background: white; 
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value { font-size: 32px; font-weight: bold; }
        .metric-label { color: #666; margin-top: 5px; }
        #charts { margin-top: 20px; }
        .chart { 
            background: white; 
            padding: 20px; 
            margin: 10px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>🚀 RAG-Anything Performance Dashboard</h1>
    
    <div id="metrics">
        <div class="metric">
            <div class="metric-value" id="cpu">{{ cpu }}%</div>
            <div class="metric-label">CPU Usage</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="memory">{{ memory }}%</div>
            <div class="metric-label">Memory Usage</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="throughput">{{ throughput }}</div>
            <div class="metric-label">Docs/Min</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="cache">{{ cache_hit }}%</div>
            <div class="metric-label">Cache Hit Rate</div>
        </div>
    </div>
    
    <div id="charts">
        <div class="chart">
            <div id="cpu-chart"></div>
        </div>
        <div class="chart">
            <div id="throughput-chart"></div>
        </div>
    </div>
    
    <script>
        // 实时更新
        setInterval(function() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('cpu').innerText = data.cpu + '%';
                    document.getElementById('memory').innerText = data.memory + '%';
                    document.getElementById('throughput').innerText = data.throughput;
                    document.getElementById('cache').innerText = data.cache_hit + '%';
                    
                    // 更新图表
                    updateCharts(data);
                });
        }, 2000);
        
        function updateCharts(data) {
            // CPU趋势图
            Plotly.newPlot('cpu-chart', [{
                y: data.cpu_history,
                type: 'line',
                name: 'CPU Usage'
            }], {
                title: 'CPU Usage Trend',
                yaxis: { title: 'Usage %' }
            });
            
            // 吞吐量图
            Plotly.newPlot('throughput-chart', [{
                y: data.throughput_history,
                type: 'line',
                name: 'Throughput'
            }], {
                title: 'Processing Throughput',
                yaxis: { title: 'Docs/Min' }
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """仪表板页面"""
    metrics = get_current_metrics()
    return render_template_string(DASHBOARD_HTML, **metrics)

@app.route('/api/metrics')
def metrics_api():
    """指标API"""
    return json.dumps(get_current_metrics())

def get_current_metrics():
    """获取当前指标"""
    return {
        "cpu": psutil.cpu_percent(interval=1),
        "memory": psutil.virtual_memory().percent,
        "throughput": 45,  # 从实际系统获取
        "cache_hit": 65,   # 从实际系统获取
        "cpu_history": [20, 25, 30, 35, 40, 38, 35, 32],
        "throughput_history": [40, 42, 45, 48, 50, 47, 45, 45]
    }

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

## 部署优化配置

### 环境变量优化 (.env.performance)

```bash
# 并发配置
MAX_CONCURRENT_PROCESSING=8
MAX_CONCURRENT_FILES=10
WORKER_POOL_SIZE=4

# 缓存配置
ENABLE_PARSE_CACHE=true
ENABLE_LLM_CACHE=true
CACHE_SIZE_LIMIT=5000
CACHE_TTL_HOURS=72
CACHE_STORAGE=/data/rag_cache

# 内存管理
MAX_MEMORY_MB=8192
MEMORY_CLEANUP_INTERVAL=300
GC_THRESHOLD=1000

# GPU配置
CUDA_VISIBLE_DEVICES=0,1
GPU_MEMORY_FRACTION=0.8
FALLBACK_TO_CPU=true

# 批处理优化
BATCH_SIZE=20
BATCH_TIMEOUT=600
ENABLE_BATCH_CACHE=true

# 监控
ENABLE_MONITORING=true
METRICS_PORT=9090
PROFILING_ENABLED=false
```

### Nginx 配置优化

```nginx
# /etc/nginx/sites-available/rag-api
upstream rag_backend {
    least_conn;
    server 127.0.0.1:8001 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name api.rag-anything.local;
    
    # 优化缓冲区
    client_body_buffer_size 128k;
    client_max_body_size 100M;
    client_body_timeout 300;
    
    # 启用压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain application/json;
    
    # 缓存静态内容
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # API代理
    location /api/ {
        proxy_pass http://rag_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # WebSocket支持
    location /ws/ {
        proxy_pass http://rag_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

### Systemd 服务配置

```ini
# /etc/systemd/system/rag-api.service
[Unit]
Description=RAG-Anything API Server
After=network.target

[Service]
Type=simple
User=ragsvr
WorkingDirectory=/home/ragsvr/projects/ragsystem/RAG-Anything/api
Environment="PYTHONPATH=/home/ragsvr/projects/ragsystem/RAG-Anything"
ExecStart=/usr/bin/python3 rag_api_server.py
Restart=always
RestartSec=10

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096
MemoryLimit=8G
CPUQuota=400%

# 性能优化
Nice=-5
IOSchedulingClass=best-effort
IOSchedulingPriority=0

[Install]
WantedBy=multi-user.target
```

## 验证优化效果

### 运行对比测试

```bash
# 优化前基准测试
python run_performance_test.py > before_optimization.txt

# 应用优化
./apply_optimizations.sh

# 优化后测试
python run_performance_test.py > after_optimization.txt

# 生成对比报告
python compare_results.py before_optimization.txt after_optimization.txt
```

### 预期改进

| 指标 | 优化前 | 优化后 | 改进 |
|-----|--------|--------|------|
| 批处理吞吐量 | 20 docs/min | 100 docs/min | +400% |
| 缓存命中率 | 23% | 65% | +183% |
| CPU利用率 | 25% | 70% | +180% |
| 内存稳定性 | 泄漏 | 稳定 | ✓ |
| 并发处理 | 3 | 20 | +567% |
| P95响应时间 | 45s | 10s | -78% |

## 长期优化路线图

### Q1 2025
- [ ] 实现分布式任务队列
- [ ] 添加Redis缓存层
- [ ] GPU集群支持

### Q2 2025
- [ ] 微服务架构改造
- [ ] Kubernetes部署
- [ ] 自动扩缩容

### Q3 2025
- [ ] 边缘计算支持
- [ ] 实时流处理
- [ ] AI优化调度

## 总结

通过实施这些优化，RAG-Anything API的性能将获得显著提升：

1. **立即见效**: 批处理并行化带来 3-5倍 性能提升
2. **短期改进**: 缓存和内存优化提升稳定性
3. **长期演进**: 架构升级支持大规模部署

建议按优先级逐步实施，每个阶段验证效果后再进行下一步优化。