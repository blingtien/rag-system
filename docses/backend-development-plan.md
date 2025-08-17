# 后端开发计划

## 🎯 项目概述

RAG-Anything后端开发主要围绕web-api服务的完善，实现RAG-Anything核心功能与LightRAG WebUI的无缝集成。

### 技术架构
- **核心系统**: RAG-Anything v1.2.7 (基于LightRAG)
- **API框架**: FastAPI 0.104+
- **文档解析**: MinerU 2.0
- **向量存储**: 本地JSON存储
- **嵌入模型**: Qwen3-Embedding-0.6B
- **LLM**: DeepSeek API

## 📋 详细开发任务

### Phase 1: API标准化与兼容性 (🔥高优先级)

#### 1.1 LightRAG API兼容性完善
**预估时间**: 3天
**负责模块**: `web-api/main.py`

**核心接口标准化**:
```python
# 需要完善的核心接口
1. GET /health - 系统健康检查
   当前状态: ✅ 基础实现完成
   需要完善: 
   - 添加详细的系统组件状态检查
   - 包含RAG-Anything特有的配置信息
   - 添加pipeline_busy状态指示

2. POST /documents/upload - 文档上传处理
   当前状态: ✅ 基础功能可用
   需要完善:
   - 多文件批量上传支持
   - 文件上传状态反馈
   - 文件类型验证和错误处理

3. GET /documents - 文档状态列表
   当前状态: 🔄 已修复基础数据返回
   需要完善:
   - 文档解析过程的实时状态展示（解析耗时较长）
   - WebSocket实时状态推送机制
   - 解析进度详细信息（页面数、处理阶段等）
   - 分页和排序功能
   - 状态筛选功能

4. POST /query - 智能查询接口
   当前状态: ✅ 基础查询功能可用
   需要完善:
   - 流式响应支持
   - 多模态查询处理
   - 查询历史管理

5. GET /graph - 知识图谱数据
   当前状态: ❌ 需要实现
   需要实现:
   - 图谱数据格式转换
   - 节点和边的过滤
   - 大型图谱的分页加载
```

**具体实现任务**:

```python
# 1. 完善健康检查接口
@app.get("/health")
async def get_health():
    """
    返回LightRAG兼容的系统状态
    需要包含: 配置信息、pipeline状态、版本信息
    """
    return LightragStatus(
        status="healthy",
        working_directory=str(rag_storage_path),
        configuration={...},  # 详细配置信息
        pipeline_busy=is_processing,  # 实时处理状态
        core_version="1.2.7",
        api_version="1.0.0"
    )

# 2. 实现知识图谱接口
@app.get("/graph")
async def get_graph(limit: int = 1000):
    """
    返回LightRAG兼容的图谱数据格式
    包含节点、边、属性信息
    """
    # 读取RAG-Anything的图谱数据
    # 转换为LightRAG格式
    # 返回标准化的图谱结构

# 3. 优化文档接口
@app.get("/documents")
async def get_documents_paginated(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    sort_field: str = "updated_at",
    sort_direction: str = "desc"
):
    """
    支持分页、排序、筛选的文档列表
    兼容LightRAG WebUI的调用格式
    """
```

**验收标准**:
- [ ] 所有接口响应格式与LightRAG WebUI兼容
- [ ] API文档完整，包含Schema定义
- [ ] 错误响应格式统一标准化

#### 1.2 数据格式标准化
**预估时间**: 2天
**负责模块**: Response Models

**统一响应格式**:
```python
# 1. 文档状态格式标准化
class DocStatusResponse(BaseModel):
    id: str
    content_summary: str
    content_length: int
    status: Literal["processed", "processing", "pending", "failed"]
    created_at: str
    updated_at: str
    track_id: str
    chunks_count: int
    file_path: str
    error_msg: Optional[str] = None
    multimodal_processed: bool = False

# 2. 查询响应格式标准化
class QueryResponse(BaseModel):
    response: str
    query_id: str
    mode: str
    conversation_history: List[Dict[str, str]]
    sources: List[Dict[str, Any]]  # 新增：源文档引用
    confidence_score: float  # 新增：置信度评分
    processing_time: float

# 3. 知识图谱格式标准化
class GraphNode(BaseModel):
    id: str
    labels: List[str]
    properties: Dict[str, Any]

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any]

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int
```

**验收标准**:
- [ ] 数据格式完全兼容LightRAG WebUI
- [ ] 包含必要的元数据信息
- [ ] 支持扩展字段，保持向后兼容

#### 1.3 配置系统优化
**预估时间**: 1天
**负责模块**: Configuration Management

**统一配置管理**:
```python
# 1. 环境变量标准化
WORKING_DIR = os.getenv("WORKING_DIR", "./rag_storage")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
PARSER = os.getenv("PARSER", "mineru")
PARSE_METHOD = os.getenv("PARSE_METHOD", "auto")

# 2. RAG-Anything配置适配
config = RAGAnythingConfig(
    working_dir=WORKING_DIR,
    enable_image_processing=True,
    enable_table_processing=True,
    enable_equation_processing=True,
    max_concurrent_files=4
)

# 3. 配置接口实现
@app.get("/config")
async def get_config():
    """返回当前系统配置"""
    
@app.post("/config")
async def update_config(config_update: ConfigUpdate):
    """更新系统配置"""
```

**验收标准**:
- [ ] 配置变更立即生效
- [ ] 配置持久化存储
- [ ] 支持配置验证和回滚

### Phase 2: 错误处理与稳定性 (🔥高优先级)

#### 2.1 异常处理增强
**预估时间**: 2天
**负责模块**: Error Handling

**文件上传错误处理**:
```python
# 1. 文件验证和错误处理
async def validate_upload_file(file: UploadFile):
    """
    文件上传前验证
    - 文件大小限制 (100MB)
    - 文件类型检查
    - 文件名安全性检查
    """
    if file.size > 100 * 1024 * 1024:
        raise HTTPException(400, "文件大小超过100MB限制")
    
    if not is_supported_file_type(file.filename):
        raise HTTPException(400, f"不支持的文件类型: {file.filename}")

# 2. 解析失败恢复机制
async def handle_parsing_failure(file_path: str, error: Exception):
    """
    解析失败时的恢复策略
    - 记录详细错误信息
    - 尝试备用解析方法
    - 保存部分成功的结果
    """
    logger.error(f"文档解析失败: {file_path}, 错误: {error}")
    
    # 尝试备用解析方法
    if isinstance(error, MinerUError):
        return await try_docling_parser(file_path)
    
    # 标记为失败状态
    await update_doc_status(file_path, "failed", str(error))

# 3. 查询超时和重试
async def query_with_retry(query_params: QueryRequest, max_retries: int = 3):
    """
    查询重试机制
    - 超时检测和处理
    - 自动重试逻辑
    - 降级处理策略
    """
    for attempt in range(max_retries):
        try:
            return await execute_query(query_params)
        except TimeoutError:
            if attempt == max_retries - 1:
                raise HTTPException(408, "查询超时，请稍后重试")
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

**系统资源保护**:
```python
# 1. 内存使用监控
async def check_memory_usage():
    """监控内存使用，防止OOM"""
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 85:
        raise HTTPException(503, "系统内存不足，请稍后重试")

# 2. 并发控制
semaphore = asyncio.Semaphore(10)  # 最大并发处理数

async def process_with_semaphore(func, *args):
    async with semaphore:
        return await func(*args)

# 3. 请求频率限制
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/query")
@limiter.limit("60/minute")  # 每分钟最多60次查询
async def query_endpoint(request: Request, query: QueryRequest):
    """带频率限制的查询接口"""
```

**验收标准**:
- [ ] 所有可能的异常都有适当处理
- [ ] 错误信息友好且具体
- [ ] 系统在高负载下稳定运行

#### 2.2 数据验证和安全
**预估时间**: 2天
**负责模块**: Security & Validation

**输入验证强化**:
```python
# 1. 查询输入清理
def sanitize_query_input(query: str) -> str:
    """
    清理查询输入，防止注入攻击
    - 过滤特殊字符
    - 长度限制
    - 编码检查
    """
    if len(query) > 10000:
        raise HTTPException(400, "查询内容过长")
    
    # 移除潜在危险字符
    sanitized = re.sub(r'[<>"\']', '', query)
    return sanitized.strip()

# 2. 文件路径安全检查
def validate_file_path(file_path: str) -> str:
    """
    验证文件路径安全性，防止目录遍历
    """
    # 规范化路径
    normalized = os.path.normpath(file_path)
    
    # 检查是否在允许的目录内
    if not normalized.startswith(ALLOWED_UPLOAD_DIR):
        raise HTTPException(400, "非法文件路径")
    
    return normalized

# 3. API调用认证 (可选)
def verify_api_key(api_key: str = Header(None)):
    """
    API密钥验证 (如果需要)
    """
    if REQUIRE_AUTH and api_key != VALID_API_KEY:
        raise HTTPException(401, "无效的API密钥")
```

**日志和审计**:
```python
# 1. 结构化日志
import structlog

logger = structlog.get_logger()

async def log_api_request(request: Request, response: Response):
    """记录API请求和响应"""
    logger.info(
        "api_request",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        user_agent=request.headers.get("user-agent"),
        timestamp=datetime.utcnow().isoformat()
    )

# 2. 操作审计日志
async def log_document_operation(operation: str, file_path: str, user_id: str = None):
    """记录文档操作日志"""
    logger.info(
        "document_operation",
        operation=operation,
        file_path=file_path,
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat()
    )

# 3. 性能监控日志
async def log_performance_metrics(endpoint: str, duration: float, memory_usage: float):
    """记录性能指标"""
    logger.info(
        "performance_metrics",
        endpoint=endpoint,
        duration_ms=duration * 1000,
        memory_mb=memory_usage / 1024 / 1024,
        timestamp=datetime.utcnow().isoformat()
    )
```

**验收标准**:
- [ ] 所有输入都经过验证和清理
- [ ] 安全漏洞扫描通过
- [ ] 日志记录完整且结构化

### Phase 3: 性能优化与扩展性 (🔶中优先级)

#### 3.1 并发处理优化
**预估时间**: 3天
**负责模块**: Concurrency & Queue Management

**异步文档处理队列**:
```python
# 1. 处理队列实现
from asyncio import Queue
from dataclasses import dataclass

@dataclass
class ProcessingTask:
    file_path: str
    task_id: str
    priority: int
    created_at: datetime

class DocumentProcessor:
    def __init__(self, max_workers: int = 4):
        self.queue = Queue()
        self.workers = []
        self.max_workers = max_workers
        self.processing_tasks = {}
    
    async def start_workers(self):
        """启动处理工作线程"""
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
    
    async def _worker(self, worker_name: str):
        """处理工作线程"""
        while True:
            task = await self.queue.get()
            try:
                await self._process_document(task)
            except Exception as e:
                logger.error(f"处理任务失败: {task.task_id}, 错误: {e}")
            finally:
                self.queue.task_done()
    
    async def add_task(self, file_path: str, priority: int = 0):
        """添加处理任务"""
        task = ProcessingTask(
            file_path=file_path,
            task_id=str(uuid.uuid4()),
            priority=priority,
            created_at=datetime.utcnow()
        )
        await self.queue.put(task)
        return task.task_id

# 2. 并发查询优化
class QueryProcessor:
    def __init__(self, max_concurrent_queries: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent_queries)
        self.active_queries = {}
    
    async def execute_query(self, query_params: QueryRequest):
        """并发安全的查询执行"""
        async with self.semaphore:
            query_id = str(uuid.uuid4())
            self.active_queries[query_id] = datetime.utcnow()
            
            try:
                result = await rag_instance.aquery(
                    query_params.query,
                    mode=query_params.mode
                )
                return result
            finally:
                del self.active_queries[query_id]

# 3. 资源池管理
class ResourcePool:
    def __init__(self):
        self.rag_instances = []
        self.lock = asyncio.Lock()
    
    async def get_rag_instance(self):
        """获取可用的RAG实例"""
        async with self.lock:
            if self.rag_instances:
                return self.rag_instances.pop()
            else:
                return await self._create_new_instance()
    
    async def return_rag_instance(self, instance):
        """归还RAG实例到池中"""
        async with self.lock:
            self.rag_instances.append(instance)
```

**验收标准**:
- [ ] 支持多文档并发处理
- [ ] 查询响应时间在高并发下稳定
- [ ] 资源使用效率提升50%以上

#### 3.2 缓存策略实现
**预估时间**: 3天
**负责模块**: Caching System

**多层缓存架构**:
```python
# 1. 查询结果缓存
import hashlib
from typing import Dict, Any, Optional

class QueryCache:
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def _generate_key(self, query: str, mode: str, params: Dict) -> str:
        """生成缓存键"""
        content = f"{query}:{mode}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def get(self, query: str, mode: str, params: Dict) -> Optional[str]:
        """获取缓存结果"""
        key = self._generate_key(query, mode, params)
        
        if key in self.cache:
            entry = self.cache[key]
            if datetime.utcnow().timestamp() - entry['timestamp'] < self.ttl:
                return entry['result']
            else:
                del self.cache[key]
        
        return None
    
    async def set(self, query: str, mode: str, params: Dict, result: str):
        """设置缓存结果"""
        if len(self.cache) >= self.max_size:
            # LRU清理策略
            oldest_key = min(self.cache.keys(), 
                           key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        key = self._generate_key(query, mode, params)
        self.cache[key] = {
            'result': result,
            'timestamp': datetime.utcnow().timestamp()
        }

# 2. 文档解析缓存
class DocumentCache:
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    async def get_parsed_content(self, file_path: str, file_hash: str) -> Optional[Dict]:
        """获取已解析的文档内容"""
        cache_file = self.cache_dir / f"{file_hash}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"缓存文件读取失败: {e}")
        
        return None
    
    async def set_parsed_content(self, file_hash: str, content: Dict):
        """缓存解析结果"""
        cache_file = self.cache_dir / f"{file_hash}.json"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"缓存写入失败: {e}")

# 3. 知识图谱缓存
class GraphCache:
    def __init__(self):
        self.graph_cache = None
        self.last_update = None
        self.cache_ttl = 300  # 5分钟
    
    async def get_graph_data(self) -> Optional[Dict]:
        """获取缓存的图谱数据"""
        if (self.graph_cache and self.last_update and 
            datetime.utcnow().timestamp() - self.last_update < self.cache_ttl):
            return self.graph_cache
        
        return None
    
    async def update_graph_cache(self, graph_data: Dict):
        """更新图谱缓存"""
        self.graph_cache = graph_data
        self.last_update = datetime.utcnow().timestamp()
```

**验收标准**:
- [ ] 缓存命中率达到70%以上
- [ ] 查询响应时间提升60%以上
- [ ] 缓存失效机制准确可靠

#### 3.3 数据库优化
**预估时间**: 2天
**负责模块**: Data Storage Optimization

**存储结构优化**:
```python
# 1. 索引策略优化
class DocumentIndex:
    def __init__(self, index_file: str = "document_index.json"):
        self.index_file = index_file
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """加载文档索引"""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "documents": {},
            "by_status": {"processed": [], "processing": [], "pending": [], "failed": []},
            "by_date": {},
            "by_type": {}
        }
    
    def add_document(self, doc_id: str, doc_info: Dict):
        """添加文档到索引"""
        self.index["documents"][doc_id] = doc_info
        
        # 按状态索引
        status = doc_info.get("status", "pending")
        if doc_id not in self.index["by_status"][status]:
            self.index["by_status"][status].append(doc_id)
        
        # 按日期索引
        date_key = doc_info.get("created_at", "")[:10]  # YYYY-MM-DD
        if date_key not in self.index["by_date"]:
            self.index["by_date"][date_key] = []
        self.index["by_date"][date_key].append(doc_id)
        
        self._save_index()
    
    def query_documents(self, status: str = None, date_range: tuple = None, 
                       file_type: str = None, page: int = 1, page_size: int = 20):
        """高效查询文档"""
        doc_ids = list(self.index["documents"].keys())
        
        # 状态筛选
        if status and status != "all":
            doc_ids = [doc_id for doc_id in doc_ids 
                      if doc_id in self.index["by_status"].get(status, [])]
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        
        result_docs = []
        for doc_id in doc_ids[start:end]:
            if doc_id in self.index["documents"]:
                result_docs.append(self.index["documents"][doc_id])
        
        return {
            "documents": result_docs,
            "total_count": len(doc_ids),
            "page": page,
            "page_size": page_size
        }

# 2. 数据压缩策略
import gzip
import pickle

class CompressedStorage:
    @staticmethod
    def save_compressed(data: Any, file_path: str):
        """压缩保存数据"""
        with gzip.open(file_path, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def load_compressed(file_path: str) -> Any:
        """加载压缩数据"""
        with gzip.open(file_path, 'rb') as f:
            return pickle.load(f)
```

**验收标准**:
- [ ] 大规模数据查询性能提升3倍以上
- [ ] 存储空间使用优化50%以上
- [ ] 数据一致性保持100%

### Phase 4: 企业级功能 (🔷低优先级)

#### 4.1 监控和可观测性
**预估时间**: 4天
**负责模块**: Monitoring & Observability

**指标收集系统**:
```python
# 1. Prometheus指标集成
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# 定义指标
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Request duration')
PROCESSING_QUEUE_SIZE = Gauge('document_processing_queue_size', 'Documents in processing queue')
ACTIVE_QUERIES = Gauge('active_queries_count', 'Number of active queries')

# 2. 性能监控中间件
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()
    
    response = await call_next(request)
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response

# 3. 系统资源监控
import psutil

class SystemMonitor:
    def __init__(self):
        self.cpu_usage = Gauge('system_cpu_usage_percent', 'CPU usage percentage')
        self.memory_usage = Gauge('system_memory_usage_percent', 'Memory usage percentage')
        self.disk_usage = Gauge('system_disk_usage_percent', 'Disk usage percentage')
    
    async def update_metrics(self):
        """更新系统指标"""
        self.cpu_usage.set(psutil.cpu_percent())
        self.memory_usage.set(psutil.virtual_memory().percent)
        self.disk_usage.set(psutil.disk_usage('/').percent)

# 4. 应用指标监控
class ApplicationMonitor:
    def __init__(self):
        self.documents_processed = Counter('documents_processed_total', 'Total processed documents')
        self.queries_executed = Counter('queries_executed_total', 'Total executed queries', ['mode'])
        self.processing_errors = Counter('processing_errors_total', 'Total processing errors', ['type'])
    
    def record_document_processed(self):
        self.documents_processed.inc()
    
    def record_query_executed(self, mode: str):
        self.queries_executed.labels(mode=mode).inc()
    
    def record_processing_error(self, error_type: str):
        self.processing_errors.labels(type=error_type).inc()
```

#### 4.2 高可用性支持
**预估时间**: 3天
**负责模块**: High Availability

**健康检查机制**:
```python
# 1. 深度健康检查
class HealthChecker:
    async def check_rag_system(self) -> Dict[str, Any]:
        """检查RAG系统健康状态"""
        try:
            # 测试简单查询
            test_result = await rag_instance.aquery("test", mode="naive")
            return {"status": "healthy", "test_query": "passed"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_storage_system(self) -> Dict[str, Any]:
        """检查存储系统健康状态"""
        try:
            # 检查关键文件是否可访问
            storage_path = Path(WORKING_DIR)
            if storage_path.exists() and storage_path.is_dir():
                return {"status": "healthy", "storage_path": str(storage_path)}
            else:
                return {"status": "unhealthy", "error": "Storage path not accessible"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_model_availability(self) -> Dict[str, Any]:
        """检查模型可用性"""
        try:
            # 测试嵌入模型
            test_embedding = await embed_func(["test"])
            if test_embedding and len(test_embedding) > 0:
                return {"status": "healthy", "embedding_model": "available"}
            else:
                return {"status": "unhealthy", "error": "Embedding model not responding"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

# 2. 自动故障恢复
class AutoRecovery:
    def __init__(self):
        self.max_retry_attempts = 3
        self.recovery_strategies = {
            "rag_system_failure": self._recover_rag_system,
            "storage_failure": self._recover_storage_system,
            "model_failure": self._recover_model_system
        }
    
    async def _recover_rag_system(self):
        """RAG系统故障恢复"""
        logger.info("尝试恢复RAG系统...")
        try:
            global rag_instance
            rag_instance = await initialize_rag_system()
            return True
        except Exception as e:
            logger.error(f"RAG系统恢复失败: {e}")
            return False
    
    async def _recover_storage_system(self):
        """存储系统故障恢复"""
        logger.info("尝试恢复存储系统...")
        try:
            # 重新创建必要的目录
            Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)
            Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"存储系统恢复失败: {e}")
            return False

# 3. 数据备份机制
class BackupManager:
    def __init__(self, backup_dir: str = "./backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    async def create_backup(self):
        """创建数据备份"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"rag_backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        try:
            # 压缩RAG存储目录
            shutil.make_archive(str(backup_path), 'zip', WORKING_DIR)
            logger.info(f"备份创建成功: {backup_path}.zip")
            
            # 清理旧备份 (保留最近10个)
            await self._cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"备份创建失败: {e}")
    
    async def _cleanup_old_backups(self):
        """清理旧备份"""
        backup_files = list(self.backup_dir.glob("rag_backup_*.zip"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # 删除多余的备份文件
        for old_backup in backup_files[10:]:
            old_backup.unlink()
            logger.info(f"已删除旧备份: {old_backup}")
```

**验收标准**:
- [ ] 系统自动故障检测和恢复
- [ ] 数据备份和恢复机制完整
- [ ] 监控指标覆盖所有关键组件

## 🛠️ 开发环境设置

### 本地开发环境
```bash
# 1. 创建虚拟环境
cd /home/ragsvr/projects/ragsystem/web-api
python -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑.env文件，设置必要的配置

# 4. 启动开发服务器
python main.py

# 5. API文档访问
http://localhost:8001/docs
```

### 调试和测试
```bash
# 1. 运行单元测试
pytest tests/

# 2. API测试
curl -X GET http://localhost:8001/health
curl -X POST http://localhost:8001/query -H "Content-Type: application/json" -d '{"query": "test"}'

# 3. 性能测试
ab -n 100 -c 10 http://localhost:8001/health
```

## 📊 质量标准

### 性能指标
- **API响应时间**: 95%请求<500ms
- **查询处理时间**: 平均<3秒
- **文档处理并发**: 支持4个文档同时处理
- **系统吞吐量**: >100 QPS

### 稳定性指标
- **系统可用性**: 99.5%以上
- **错误率**: <0.1%
- **内存泄漏**: 长期运行内存稳定
- **故障恢复时间**: <30秒

### 安全标准
- **输入验证**: 100%覆盖
- **SQL注入防护**: 完全防护
- **文件上传安全**: 完整验证
- **API频率限制**: 合理设置

## 🚀 部署配置

### 开发环境部署
```bash
# 1. 启动开发服务器
export ENVIRONMENT=development
python main.py --host 0.0.0.0 --port 8001

# 2. 启用调试模式
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### 生产环境部署
```bash
# 1. 使用Gunicorn部署
pip install gunicorn uvicorn[standard]
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001

# 2. 使用Docker部署
docker build -t rag-anything-api .
docker run -d -p 8001:8001 --name rag-api rag-anything-api

# 3. 使用systemd服务
sudo cp rag-anything-api.service /etc/systemd/system/
sudo systemctl enable rag-anything-api
sudo systemctl start rag-anything-api
```

### 监控部署
```bash
# 1. Prometheus配置
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'rag-anything-api'
    static_configs:
      - targets: ['localhost:8001']

# 2. 启动监控
docker run -d -p 9090:9090 -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
```

## 📝 测试计划

### 单元测试
```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_query_endpoint():
    response = client.post("/query", json={"query": "test", "mode": "hybrid"})
    assert response.status_code == 200
    assert "result" in response.json()

def test_document_upload():
    with open("test_file.pdf", "rb") as f:
        response = client.post("/documents/upload", files={"file": f})
    assert response.status_code == 200
```

### 集成测试
```python
# tests/test_integration.py
@pytest.mark.asyncio
async def test_full_pipeline():
    """测试完整的文档处理流程"""
    # 1. 上传文档
    upload_response = await upload_test_document()
    assert upload_response["status"] == "success"
    
    # 2. 等待处理完成
    await wait_for_processing_complete(upload_response["task_id"])
    
    # 3. 查询文档内容
    query_response = await query_document_content()
    assert query_response["confidence_score"] > 0.8
```

### 压力测试
```python
# tests/test_load.py
import asyncio
import aiohttp

async def test_concurrent_queries():
    """测试并发查询性能"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(100):
            task = session.post("/query", json={"query": f"test query {i}"})
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        success_count = sum(1 for r in responses if r.status == 200)
        assert success_count >= 95  # 95%成功率
```

## 📋 验收清单

### Phase 1验收
- [ ] 所有API接口返回正确格式
- [ ] 与LightRAG WebUI完全兼容
- [ ] 基础CRUD功能正常
- [ ] 错误处理机制完善

### Phase 2验收
- [ ] 异常情况处理完整
- [ ] 输入验证和安全防护到位
- [ ] 日志记录详细准确
- [ ] 性能在负载下稳定

### Phase 3验收
- [ ] 并发处理能力提升明显
- [ ] 缓存命中率达到预期
- [ ] 存储性能优化有效
- [ ] 资源使用效率提升

### 最终验收
- [ ] 所有功能稳定可靠
- [ ] 性能指标达到要求
- [ ] 监控和告警完整
- [ ] 生产部署就绪

---

**文档版本**: v1.0
**最后更新**: 2025-08-17
**负责人**: 后端开发团队