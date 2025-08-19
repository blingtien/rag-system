# RAG-Anything架构分析与API设计方案 (WebUI集成版)

> **设计目标**：使LightRAG WebUI完美接入RAG-Anything多模态处理系统，实现实时进度监控和优质用户体验。

## 1. LightRAG WebUI前端页面架构分析

### 1.1 前端技术栈
- **框架**: React + TypeScript
- **构建工具**: Vite
- **路由**: React Router
- **UI库**: Antd (Ant Design)
- **状态管理**: React Hooks + Context API
- **HTTP客户端**: Axios

### 1.2 核心功能模块

#### 主要页面结构
```
/webui
├── DocumentManager.tsx    # 文档管理页面
├── GraphViewer.tsx       # 知识图谱可视化
├── RetrievalTesting.tsx  # 检索测试页面
└── AppRouter.tsx         # 路由配置
```

#### DocumentManager (文档管理)
**核心功能**:
- 文档上传与管理
- 文档状态监控 (PENDING/PROCESSING/PROCESSED/FAILED)
- 批量文档处理
- 文档删除与清理
- 扫描本地目录
- 实时处理进度显示

**关键特性**:
- 支持多种文件格式 (PDF, DOCX, PPTX, XLSX, TXT, MD等)
- 文件大小验证和类型检查
- 拖拽上传界面
- 分页显示文档列表
- 状态过滤和排序功能

#### GraphViewer (知识图谱可视化)
**核心功能**:
- 实体和关系可视化
- 交互式图谱浏览
- 节点和边的详细信息展示
- 图谱搜索和筛选

#### RetrievalTesting (检索测试)
**核心功能**:
- 多模式查询测试 (local/global/hybrid/naive)
- 实时查询结果展示
- 查询历史记录
- 参数调优界面

### 1.3 前端与后端交互模式

#### API调用模式
- **REST API**: 标准HTTP请求/响应
- **流式响应**: 支持实时查询结果流
- **WebSocket**: 实时状态更新
- **文件上传**: FormData格式

#### 认证机制
- **Token认证**: JWT Bearer token
- **会话管理**: 自动token刷新
- **权限控制**: 基于角色的访问控制

## 2. LightRAG API接口设计分析

### 2.1 API架构

#### 核心服务器文件
```
lightrag/api/
├── lightrag_server.py           # 主服务器文件
├── routers/
│   ├── document_routes.py       # 文档管理路由
│   ├── query_routes.py         # 查询路由
│   └── graph_routes.py         # 图谱路由
```

#### API框架
- **FastAPI**: 现代Python Web框架
- **异步支持**: 全异步API设计
- **自动文档**: OpenAPI/Swagger集成
- **数据验证**: Pydantic模型验证

### 2.2 文档管理API (/documents)

#### 核心端点
```python
POST   /documents/upload          # 文件上传
POST   /documents/text           # 文本插入
POST   /documents/texts          # 批量文本插入
POST   /documents/scan           # 扫描本地文件
GET    /documents                # 获取文档状态
POST   /documents/paginated      # 分页查询文档
GET    /documents/status_counts  # 状态统计
DELETE /documents                # 清空所有文档
DELETE /documents/delete_document # 删除指定文档
POST   /documents/clear_cache    # 清理缓存
```

#### 关键特性
- **后台处理**: 异步文档处理
- **进度跟踪**: track_id追踪处理状态
- **批量操作**: 支持批量文档处理
- **安全验证**: 文件类型和路径安全检查
- **错误处理**: 详细的错误信息和恢复机制

#### 数据模型
```python
class DocStatusResponse(BaseModel):
    id: str                      # 文档ID
    content_summary: str         # 内容摘要
    content_length: int          # 内容长度
    status: DocStatus           # 处理状态
    created_at: str             # 创建时间
    updated_at: str             # 更新时间
    track_id: Optional[str]     # 跟踪ID
    chunks_count: Optional[int] # 分块数量
    error_msg: Optional[str]    # 错误信息
    file_path: str              # 文件路径
```

### 2.3 查询API (/query)

#### 核心端点
```python
POST /query         # 标准查询
POST /query/stream  # 流式查询
```

#### 查询模式
- **local**: 局部知识查询
- **global**: 全局知识图谱查询  
- **hybrid**: 混合模式查询
- **naive**: 简单向量搜索
- **mix**: 智能混合模式
- **bypass**: 绕过RAG直接查询

#### 查询参数
```python
class QueryRequest(BaseModel):
    query: str                           # 查询文本
    mode: str                           # 查询模式
    top_k: Optional[int]                # 检索数量
    response_type: Optional[str]        # 响应格式
    conversation_history: Optional[List] # 对话历史
    enable_rerank: Optional[bool]       # 启用重排序
```

## 3. RAG-Anything核心组件分析

### 3.1 架构设计

#### 核心类结构
```python
@dataclass
class RAGAnything(QueryMixin, ProcessorMixin, BatchMixin):
    # 核心组件
    lightrag: Optional[LightRAG]           # LightRAG实例
    llm_model_func: Optional[Callable]     # LLM模型函数
    vision_model_func: Optional[Callable]  # 视觉模型函数
    embedding_func: Optional[Callable]     # 嵌入函数
    config: Optional[RAGAnythingConfig]    # 配置对象
    
    # 多模态处理器
    modal_processors: Dict[str, Any]       # 模态处理器字典
    context_extractor: ContextExtractor    # 上下文提取器
```

#### Mixin架构
- **QueryMixin**: 查询功能 (文本查询、多模态查询、VLM增强查询)
- **ProcessorMixin**: 文档处理功能 (解析、内容插入、多模态处理)
- **BatchMixin**: 批量处理功能 (文件夹批量处理、并发控制)

### 3.2 配置系统

#### 环境变量支持
```python
@dataclass
class RAGAnythingConfig:
    # 目录配置
    working_dir: str = get_env_value("WORKING_DIR", "./rag_storage")
    parser_output_dir: str = get_env_value("OUTPUT_DIR", "./output")
    
    # 解析配置
    parser: str = get_env_value("PARSER", "mineru")  # mineru/docling
    parse_method: str = get_env_value("PARSE_METHOD", "auto")
    
    # 多模态处理配置
    enable_image_processing: bool = get_env_value("ENABLE_IMAGE_PROCESSING", True)
    enable_table_processing: bool = get_env_value("ENABLE_TABLE_PROCESSING", True)
    enable_equation_processing: bool = get_env_value("ENABLE_EQUATION_PROCESSING", True)
    
    # DeepSeek配置
    deepseek_api_key: str = get_env_value("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = get_env_value("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    
    # Qwen本地嵌入配置
    qwen_model_name: str = get_env_value("QWEN_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
    embedding_device: str = get_env_value("EMBEDDING_DEVICE", "auto")
```

### 3.3 多模态处理系统

#### 专用处理器
```python
# 图像处理器
ImageModalProcessor: 
    - 图像内容分析
    - 视觉描述生成
    - 上下文增强

# 表格处理器  
TableModalProcessor:
    - 表格数据分析
    - 统计模式识别
    - 结构化数据处理

# 公式处理器
EquationModalProcessor:
    - LaTeX公式解析
    - 数学表达式理解
    - 符号计算支持

# 通用处理器
GenericModalProcessor:
    - 自定义内容类型
    - 可扩展处理逻辑
```

#### 上下文提取系统
```python
@dataclass
class ContextConfig:
    context_window: int = 1              # 上下文窗口大小
    context_mode: str = "page"           # 上下文模式 (page/chunk)
    max_context_tokens: int = 2000       # 最大上下文token数
    include_headers: bool = True         # 包含标题
    include_captions: bool = True        # 包含标注
```

### 3.4 查询功能

#### 查询类型
```python
# 纯文本查询
async def aquery(query: str, mode: str = "mix", **kwargs) -> str

# 多模态查询  
async def aquery_with_multimodal(
    query: str, 
    multimodal_content: List[Dict[str, Any]] = None,
    mode: str = "mix",
    **kwargs
) -> str

# VLM增强查询
async def aquery_vlm_enhanced(query: str, mode: str = "mix", **kwargs) -> str
```

#### 使用示例
```python
# simple_query.py - 简单查询工具
rag = RAGAnything(config=config, llm_model_func=llm_func, embedding_func=embed_func)
result = await rag.aquery("问题", mode="hybrid", vlm_enhanced=False)

# native_with_qwen.py - 完整处理流程
await rag.process_document_complete(file_path="document.pdf", output_dir="./output")
result = await rag.aquery("问题", mode="hybrid", vlm_enhanced=False)
```

## 4. RAG-Anything API设计方案

### 4.1 设计目标

#### 核心设计理念
- **RAG-Anything为核心**: 完全基于RAG-Anything构建API系统
- **WebUI完美接入**: LightRAG WebUI作为纯前端界面接入RAG-Anything
- **实时进度监控**: 解决多模态处理耗时的用户体验问题
- **零兼容性负担**: 不考虑LightRAG原有功能的兼容性

#### 功能增强
- **多模态文档处理**: 支持PDF中的图像、表格、公式
- **增强查询能力**: VLM增强查询和多模态内容查询
- **可配置解析器**: 支持MinerU 2.0和Docling
- **批量处理**: 支持文件夹批量处理

### 4.2 实时进度监控系统设计

#### 4.2.1 多模态处理阶段分析

RAG-Anything文档处理包含以下主要阶段：

```python
class ProcessingStage(Enum):
    PARSING = "parsing"           # 文档解析 (10-20%)
    SEPARATION = "separation"     # 内容分离 (5%)  
    TEXT_INSERT = "text_insert"   # 文本插入 (20-30%)
    IMAGE_PROCESS = "image_process"    # 图像处理 (15-25%)
    TABLE_PROCESS = "table_process"    # 表格处理 (10-20%)
    EQUATION_PROCESS = "equation_process"  # 公式处理 (5-10%)
    GRAPH_BUILD = "graph_build"   # 知识图谱构建 (20-30%)
    INDEXING = "indexing"         # 向量索引 (5-10%)
    COMPLETED = "completed"       # 处理完成 (100%)
```

#### 4.2.2 任务状态管理器

```python
@dataclass
class ProcessingTask:
    """文档处理任务状态"""
    task_id: str                          # 任务唯一ID
    file_path: str                        # 文件路径
    status: ProcessingStatus              # 任务状态
    current_stage: ProcessingStage        # 当前阶段
    progress_percent: float               # 总进度百分比
    stage_progress: float                 # 当前阶段进度
    start_time: datetime                  # 开始时间
    estimated_total_time: Optional[float] # 预估总时间
    stage_details: Dict[str, Any]         # 阶段详细信息
    multimodal_stats: Dict[str, int]      # 多模态统计
    error_message: Optional[str]          # 错误信息

class ProcessingStatus(Enum):
    PENDING = "pending"           # 等待处理
    RUNNING = "running"           # 正在处理
    PAUSED = "paused"            # 暂停处理
    COMPLETED = "completed"       # 处理完成
    FAILED = "failed"            # 处理失败
    CANCELLED = "cancelled"       # 已取消

class TaskManager:
    """任务状态管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, ProcessingTask] = {}
        self.progress_callbacks: Dict[str, List[Callable]] = {}
    
    async def create_task(self, file_path: str, **options) -> str:
        """创建新的处理任务"""
        task_id = str(uuid.uuid4())
        task = ProcessingTask(
            task_id=task_id,
            file_path=file_path,
            status=ProcessingStatus.PENDING,
            current_stage=ProcessingStage.PARSING,
            progress_percent=0.0,
            stage_progress=0.0,
            start_time=datetime.now(),
            estimated_total_time=None,
            stage_details={},
            multimodal_stats={},
            error_message=None
        )
        self.tasks[task_id] = task
        return task_id
    
    async def update_progress(
        self, 
        task_id: str, 
        stage: ProcessingStage,
        stage_progress: float,
        **details
    ):
        """更新任务进度"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        task.current_stage = stage
        task.stage_progress = stage_progress
        task.progress_percent = self._calculate_total_progress(stage, stage_progress)
        task.stage_details.update(details)
        
        # 触发进度回调
        await self._notify_progress_callbacks(task_id, task)
    
    def _calculate_total_progress(self, stage: ProcessingStage, stage_progress: float) -> float:
        """计算总进度百分比"""
        stage_weights = {
            ProcessingStage.PARSING: (0, 15),
            ProcessingStage.SEPARATION: (15, 20),
            ProcessingStage.TEXT_INSERT: (20, 40),
            ProcessingStage.IMAGE_PROCESS: (40, 65),
            ProcessingStage.TABLE_PROCESS: (65, 80),
            ProcessingStage.EQUATION_PROCESS: (80, 85),
            ProcessingStage.GRAPH_BUILD: (85, 95),
            ProcessingStage.INDEXING: (95, 100)
        }
        
        start_weight, end_weight = stage_weights.get(stage, (0, 100))
        stage_range = end_weight - start_weight
        return start_weight + (stage_range * stage_progress / 100)
```

#### 4.2.3 WebSocket实时通信

```python
class ProgressWebSocketManager:
    """WebSocket进度推送管理器"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.task_subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """客户端连接"""
        await websocket.accept()
        self.connections[client_id] = websocket
        self.logger.info(f"WebSocket客户端连接: {client_id}")
    
    async def disconnect(self, client_id: str):
        """客户端断开"""
        if client_id in self.connections:
            del self.connections[client_id]
        # 清理订阅
        for task_id in list(self.task_subscriptions.keys()):
            self.task_subscriptions[task_id].discard(client_id)
    
    async def subscribe_task(self, client_id: str, task_id: str):
        """订阅任务进度"""
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        self.task_subscriptions[task_id].add(client_id)
    
    async def broadcast_progress(self, task_id: str, progress_data: Dict):
        """广播进度更新"""
        if task_id in self.task_subscriptions:
            message = {
                "type": "progress_update",
                "task_id": task_id,
                "data": progress_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # 向所有订阅的客户端发送消息
            disconnected_clients = []
            for client_id in self.task_subscriptions[task_id]:
                if client_id in self.connections:
                    try:
                        await self.connections[client_id].send_json(message)
                    except Exception as e:
                        self.logger.warning(f"发送消息失败: {client_id}, {e}")
                        disconnected_clients.append(client_id)
                        
            # 清理断开的连接
            for client_id in disconnected_clients:
                await self.disconnect(client_id)
```

#### 4.2.4 增强的RAG-Anything处理器

```python
class ProgressAwareRAGAnything(RAGAnything):
    """带进度监控的RAG-Anything处理器"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_manager = TaskManager()
        self.ws_manager = ProgressWebSocketManager()
    
    async def process_document_with_progress(
        self,
        file_path: str,
        task_id: str = None,
        **kwargs
    ) -> str:
        """带进度监控的文档处理"""
        
        # 创建任务
        if task_id is None:
            task_id = await self.task_manager.create_task(file_path, **kwargs)
        
        try:
            await self.task_manager.update_task_status(task_id, ProcessingStatus.RUNNING)
            
            # 阶段1: 文档解析
            await self._progress_update(task_id, ProcessingStage.PARSING, 0, 
                                      message="开始解析文档...")
            
            content_list, doc_id = await self._parse_with_progress(
                file_path, task_id, **kwargs
            )
            
            await self._progress_update(task_id, ProcessingStage.PARSING, 100,
                                      message="文档解析完成")
            
            # 阶段2: 内容分离
            await self._progress_update(task_id, ProcessingStage.SEPARATION, 0,
                                      message="分离文本和多模态内容...")
            
            text_content, multimodal_items = separate_content(content_list)
            
            # 统计多模态内容
            multimodal_stats = self._count_multimodal_content(multimodal_items)
            await self.task_manager.update_multimodal_stats(task_id, multimodal_stats)
            
            await self._progress_update(task_id, ProcessingStage.SEPARATION, 100,
                                      message="内容分离完成", 
                                      multimodal_stats=multimodal_stats)
            
            # 阶段3: 文本内容插入
            await self._progress_update(task_id, ProcessingStage.TEXT_INSERT, 0,
                                      message="插入文本内容到知识图谱...")
            
            await self._insert_text_with_progress(text_content, doc_id, task_id)
            
            await self._progress_update(task_id, ProcessingStage.TEXT_INSERT, 100,
                                      message="文本内容插入完成")
            
            # 阶段4-6: 多模态处理
            await self._process_multimodal_with_progress(multimodal_items, task_id)
            
            # 阶段7: 知识图谱构建
            await self._progress_update(task_id, ProcessingStage.GRAPH_BUILD, 0,
                                      message="构建知识图谱...")
            # 实际的图谱构建在文本插入时已完成，这里主要是最终优化
            await self._progress_update(task_id, ProcessingStage.GRAPH_BUILD, 100,
                                      message="知识图谱构建完成")
            
            # 阶段8: 索引完成
            await self._progress_update(task_id, ProcessingStage.INDEXING, 0,
                                      message="完成索引优化...")
            await asyncio.sleep(0.5)  # 模拟索引优化时间
            await self._progress_update(task_id, ProcessingStage.INDEXING, 100,
                                      message="索引优化完成")
            
            # 完成
            await self.task_manager.update_task_status(task_id, ProcessingStatus.COMPLETED)
            await self._progress_update(task_id, ProcessingStage.COMPLETED, 100,
                                      message="文档处理完成！")
            
            return task_id
            
        except Exception as e:
            await self.task_manager.update_task_status(task_id, ProcessingStatus.FAILED, str(e))
            await self._progress_update(task_id, self.task_manager.tasks[task_id].current_stage, 
                                      0, error=str(e), message="处理失败")
            raise
    
    async def _progress_update(self, task_id: str, stage: ProcessingStage, 
                             stage_progress: float, **details):
        """更新并广播进度"""
        await self.task_manager.update_progress(task_id, stage, stage_progress, **details)
        
        # 广播给WebSocket客户端
        task = self.task_manager.tasks[task_id]
        progress_data = {
            "task_id": task_id,
            "status": task.status.value,
            "current_stage": stage.value,
            "progress_percent": task.progress_percent,
            "stage_progress": stage_progress,
            "estimated_remaining": self._estimate_remaining_time(task),
            "details": details
        }
        
        await self.ws_manager.broadcast_progress(task_id, progress_data)
```

### 4.3 RAG-Anything原生API设计

#### 4.3.1 文档处理API

##### 核心端点
```python
# 文档上传与处理 (带实时进度)
POST /documents/process
    Request:
    {
        "file": MultipartFile,              # 文件数据
        "parser": "mineru",                 # 解析器选择
        "parse_method": "auto",             # 解析方法
        "enable_image_processing": true,    # 图像处理
        "enable_table_processing": true,    # 表格处理  
        "enable_equation_processing": true, # 公式处理
        "lang": "en",                       # 文档语言
        "device": "auto"                    # 计算设备
    }
    Response:
    {
        "task_id": "uuid-string",           # 任务ID
        "status": "running",                # 任务状态
        "message": "文档处理已开始",
        "websocket_url": "/ws/progress/{task_id}"  # WebSocket地址
    }

# 任务状态查询
GET /documents/tasks/{task_id}
    Response:
    {
        "task_id": "uuid-string",
        "status": "running",                # pending/running/completed/failed
        "current_stage": "image_process",   # 当前处理阶段
        "progress_percent": 67.5,           # 总进度百分比
        "stage_progress": 45.0,             # 当前阶段进度
        "estimated_remaining": 120,         # 预估剩余时间(秒)
        "multimodal_stats": {               # 多模态统计
            "images_count": 12,
            "tables_count": 5,
            "equations_count": 3
        },
        "start_time": "2024-01-01T10:00:00Z",
        "error_message": null
    }

# 获取所有任务状态
GET /documents/tasks
    Query: ?status=running&limit=50&offset=0
    Response:
    {
        "tasks": [...],                     # 任务列表
        "total": 100,                       # 总数量
        "has_more": true                    # 是否有更多
    }

# 取消任务
DELETE /documents/tasks/{task_id}
    Response:
    {
        "task_id": "uuid-string",
        "status": "cancelled",
        "message": "任务已取消"
    }

# 批量文件夹处理
POST /documents/batch_process
    Request:
    {
        "folder_path": "/path/to/folder",
        "recursive": true,                  # 递归处理子文件夹
        "file_patterns": ["*.pdf", "*.docx"], # 文件模式匹配
        "max_concurrent": 3,                # 最大并发数
        "processing_options": {             # 处理选项
            "parser": "mineru",
            "enable_image_processing": true
        }
    }
    Response:
    {
        "batch_id": "batch-uuid",           # 批处理ID
        "total_files": 25,                  # 文件总数
        "task_ids": ["task1", "task2"],     # 任务ID列表
        "websocket_url": "/ws/batch/{batch_id}"
    }

# 文档删除
DELETE /documents/{doc_id}
    Response:
    {
        "deleted": true,
        "doc_id": "doc-uuid",
        "message": "文档已删除"
    }

# 获取文档列表
GET /documents
    Query: ?status=processed&parser=mineru&limit=20
    Response:
    {
        "documents": [
            {
                "doc_id": "doc-uuid",
                "file_name": "report.pdf",
                "status": "processed",
                "created_at": "2024-01-01T10:00:00Z",
                "multimodal_stats": {...},
                "parser_info": {
                    "parser": "mineru",
                    "version": "2.0.0"
                }
            }
        ],
        "total": 100,
        "has_more": true
    }
```

#### 4.3.2 查询API

##### 核心端点
```python
# 标准查询 (兼容LightRAG WebUI)
POST /query
    Request:
    {
        "query": "问题文本",
        "mode": "hybrid",                   # local/global/hybrid/naive/mix
        "vlm_enhanced": false,              # VLM增强查询
        "top_k": 60,                        # 检索数量
        "response_type": "详细回答",         # 响应类型
        "conversation_history": []          # 对话历史
    }
    Response:
    {
        "response": "查询结果文本",
        "query_id": "query-uuid",           # 查询ID
        "mode": "hybrid",
        "processing_time": 1.25,            # 处理时间(秒)
        "retrieved_chunks": 12,             # 检索到的文本块数量
        "vlm_enhanced": false
    }

# 流式查询
POST /query/stream
    Request: 同上
    Response: Server-Sent Events流
    {
        "event": "chunk",
        "data": {"response": "部分回答", "chunk_id": 1}
    }
    {
        "event": "complete", 
        "data": {"query_id": "uuid", "total_chunks": 15}
    }

# 多模态查询
POST /query/multimodal
    Request:
    {
        "query": "分析这个图表的趋势",
        "multimodal_content": [
            {
                "type": "image",
                "img_path": "/absolute/path/to/image.jpg",
                "img_caption": "销售趋势图表"
            },
            {
                "type": "table", 
                "table_data": "月份,销售额\n1月,100\n2月,150",
                "table_caption": "月度销售数据"
            }
        ],
        "mode": "hybrid"
    }
    Response:
    {
        "response": "基于图表和数据的分析结果",
        "query_id": "query-uuid",
        "multimodal_processing": {
            "images_processed": 1,
            "tables_processed": 1,
            "processing_time": 3.5
        }
    }

# VLM增强查询
POST /query/vlm
    Request:
    {
        "query": "图片中显示了什么内容？",
        "mode": "hybrid",
        "vlm_enhanced": true
    }
    Response:
    {
        "response": "基于图像内容的回答",
        "query_id": "query-uuid", 
        "vlm_processing": {
            "images_found": 3,
            "images_processed": 3,
            "vision_model": "deepseek-vl"
        }
    }

# 查询历史
GET /query/history
    Query: ?limit=50&offset=0&user_id=uuid
    Response:
    {
        "queries": [
            {
                "query_id": "uuid",
                "query_text": "问题",
                "response": "回答", 
                "mode": "hybrid",
                "created_at": "2024-01-01T10:00:00Z",
                "processing_time": 1.25
            }
        ],
        "total": 100,
        "has_more": true
    }

# 系统能力查询
GET /query/capabilities
    Response:
    {
        "support_multimodal": true,
        "support_vlm": true,
        "available_modes": ["local", "global", "hybrid", "naive", "mix"],
        "modal_processors": ["image", "table", "equation", "generic"],
        "models": {
            "llm": {"provider": "deepseek", "model": "deepseek-chat"},
            "vision": {"provider": "deepseek", "model": "deepseek-vl"},
            "embedding": {"provider": "local", "model": "Qwen3-Embedding-0.6B"}
        }
    }
```

#### 4.3.3 WebSocket实时通信API

##### WebSocket端点
```python
# 任务进度推送
WS /ws/progress/{task_id}
    连接参数:
    {
        "client_id": "client-uuid",         # 客户端ID
        "task_id": "task-uuid"              # 订阅的任务ID
    }
    
    推送消息格式:
    {
        "type": "progress_update",
        "task_id": "task-uuid", 
        "data": {
            "status": "running",
            "current_stage": "image_process",
            "progress_percent": 67.5,
            "stage_progress": 45.0,
            "message": "正在处理第5张图像...",
            "estimated_remaining": 120,
            "details": {
                "current_item": "image_005.jpg",
                "items_completed": 4,
                "items_total": 9
            }
        },
        "timestamp": "2024-01-01T10:30:00Z"
    }

# 批量任务进度推送
WS /ws/batch/{batch_id}
    推送消息格式:
    {
        "type": "batch_progress",
        "batch_id": "batch-uuid",
        "data": {
            "completed_tasks": 15,
            "total_tasks": 25,
            "active_tasks": 3,
            "failed_tasks": 1,
            "overall_progress": 60.0,
            "active_task_details": [
                {
                    "task_id": "task1",
                    "file_name": "report1.pdf", 
                    "progress": 45.0,
                    "stage": "image_process"
                }
            ]
        },
        "timestamp": "2024-01-01T10:30:00Z"
    }

# 系统状态推送
WS /ws/system
    推送消息格式:
    {
        "type": "system_status",
        "data": {
            "active_tasks": 5,
            "queue_length": 3,
            "cpu_usage": 65.5,
            "memory_usage": 78.2,
            "gpu_usage": 45.0,
            "disk_usage": 82.1
        },
        "timestamp": "2024-01-01T10:30:00Z"
    }

# 错误通知推送
WS /ws/errors
    推送消息格式:
    {
        "type": "error_notification",
        "data": {
            "task_id": "task-uuid",
            "error_type": "parsing_failed",
            "error_message": "文档格式不支持",
            "severity": "error",           # info/warning/error/critical
            "retry_possible": true
        },
        "timestamp": "2024-01-01T10:30:00Z"
    }
```

#### 4.3.4 系统配置与状态API

##### 核心端点
```python
# 系统配置
GET /config
    Response:
    {
        "parser": "mineru",
        "parse_method": "auto",
        "enable_image_processing": true,
        "enable_table_processing": true,
        "enable_equation_processing": true,
        "deepseek_model": "deepseek-chat",
        "deepseek_vision_model": "deepseek-vl",
        "embedding_model": "Qwen/Qwen3-Embedding-0.6B",
        "max_concurrent_tasks": 3,
        "context_window": 1,
        "max_context_tokens": 2000
    }

POST /config
    Request:
    {
        "parser": "mineru",                 # 可选: mineru/docling
        "enable_image_processing": true,
        "max_concurrent_tasks": 5
    }
    Response:
    {
        "updated": true,
        "config": {...},                    # 更新后的完整配置
        "restart_required": false           # 是否需要重启服务
    }

# 系统状态
GET /status
    Response:
    {
        "version": {
            "raganything": "1.0.0",
            "lightrag": "0.9.0",
            "mineru": "2.0.0"
        },
        "system": {
            "cpu_usage": 65.5,
            "memory_usage": 78.2,
            "gpu_usage": 45.0,
            "disk_usage": 82.1,
            "uptime": 86400
        },
        "tasks": {
            "active": 5,
            "queued": 3,
            "completed_today": 125,
            "failed_today": 2
        },
        "parsers": {
            "mineru": {
                "installed": true,
                "version": "2.0.0",
                "status": "healthy"
            },
            "docling": {
                "installed": false,
                "version": null,
                "status": "not_available"
            }
        },
        "models": {
            "llm": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "status": "healthy",
                "last_response_time": 1.25
            },
            "vision": {
                "provider": "deepseek", 
                "model": "deepseek-vl",
                "status": "healthy",
                "last_response_time": 3.5
            },
            "embedding": {
                "provider": "local",
                "model": "Qwen3-Embedding-0.6B",
                "status": "healthy",
                "device": "cuda:0"
            }
        }
    }

# 健康检查
GET /health
    Response:
    {
        "status": "healthy",                # healthy/degraded/unhealthy
        "checks": {
            "database": "healthy",
            "llm_service": "healthy", 
            "embedding_service": "healthy",
            "file_system": "healthy",
            "gpu_available": true
        },
        "timestamp": "2024-01-01T10:30:00Z"
    }
```

#### 4.2.2 查询API扩展

##### 新增端点
```python
# 多模态查询
POST /query/multimodal
    {
        "query": "分析这个图表的趋势",
        "multimodal_content": [
            {
                "type": "image", 
                "img_path": "chart.jpg"
            },
            {
                "type": "table",
                "table_data": "A,B\n1,2\n3,4"
            }
        ],
        "mode": "hybrid"
    }

# VLM增强查询
POST /query/vlm_enhanced
    {
        "query": "图像中显示了什么内容？",
        "mode": "hybrid",
        "vlm_enhanced": true
    }

# 查询能力信息
GET /query/capabilities
    {
        "support_multimodal": true,
        "support_vlm": true,
        "available_modes": ["local", "global", "hybrid", "naive", "mix"],
        "modal_processors": ["image", "table", "equation", "generic"]
    }
```

##### 增强现有端点
```python
# 扩展标准查询
POST /query
    # 新增参数
    {
        "query": "问题",
        "mode": "hybrid",
        "vlm_enhanced": false,              # VLM增强开关
        "multimodal_enhanced": false,       # 多模态增强开关
        "context_config": {                 # 上下文配置
            "context_window": 1,
            "include_images": true,
            "include_tables": true
        }
    }
```

#### 4.2.3 系统配置API

##### 新增端点
```python
# 系统配置
GET  /config
POST /config  
    {
        "parser": "mineru",
        "enable_image_processing": true,
        "enable_table_processing": true,
        "enable_equation_processing": true,
        "deepseek_model": "deepseek-chat",
        "embedding_model": "Qwen/Qwen3-Embedding-0.6B"
    }

# 系统状态
GET /status/system
    {
        "raganything_version": "1.0.0",
        "lightrag_version": "0.9.0", 
        "parsers": {
            "mineru": {"installed": true, "version": "2.0.0"},
            "docling": {"installed": false, "version": null}
        },
        "models": {
            "llm": {"provider": "deepseek", "model": "deepseek-chat"},
            "embedding": {"provider": "local", "model": "Qwen3-Embedding-0.6B"},
            "vision": {"provider": "deepseek", "model": "deepseek-vl"}
        }
    }

# 处理器状态
GET /status/processors
    {
        "image_processor": {"enabled": true, "model": "deepseek-vl"},
        "table_processor": {"enabled": true, "model": "deepseek-chat"},
        "equation_processor": {"enabled": true, "model": "deepseek-chat"},
        "generic_processor": {"enabled": true, "model": "deepseek-chat"}
    }
```

### 4.3 实现架构

#### 4.3.1 适配器模式

```python
class RAGAnythingAPIAdapter:
    """RAG-Anything到LightRAG API的适配器"""
    
    def __init__(self, rag_anything: RAGAnything):
        self.rag_anything = rag_anything
        self.lightrag = rag_anything.lightrag
    
    async def process_upload(self, file: UploadFile, **kwargs):
        """适配文件上传到RAG-Anything处理流程"""
        # 使用RAG-Anything的多模态处理能力
        return await self.rag_anything.process_file(file.filename, **kwargs)
    
    async def process_query(self, request: QueryRequest):
        """适配查询请求到RAG-Anything查询方法"""
        if request.vlm_enhanced:
            return await self.rag_anything.aquery_vlm_enhanced(
                request.query, mode=request.mode
            )
        else:
            return await self.rag_anything.aquery(
                request.query, mode=request.mode
            )
```

#### 4.3.2 服务器集成

```python
def create_raganything_app(rag_anything: RAGAnything):
    """创建集成RAG-Anything的FastAPI应用"""
    
    # 创建适配器
    adapter = RAGAnythingAPIAdapter(rag_anything)
    
    # 复用LightRAG的路由创建函数，但使用适配器
    app.include_router(
        create_document_routes_enhanced(adapter, doc_manager, api_key)
    )
    app.include_router(
        create_query_routes_enhanced(adapter, api_key)
    )
    
    # 添加RAG-Anything特有的路由
    app.include_router(create_multimodal_routes(adapter, api_key))
    app.include_router(create_config_routes(adapter, api_key))
    
    return app
```

#### 4.3.3 配置管理

```python
class RAGAnythingServerConfig:
    """RAG-Anything服务器配置"""
    
    def __init__(self):
        # 继承LightRAG的所有配置
        self.lightrag_config = global_args
        
        # 添加RAG-Anything特有配置
        self.raganything_config = RAGAnythingConfig()
        
        # 模型配置
        self.llm_model_func = self._create_llm_func()
        self.vision_model_func = self._create_vision_func() 
        self.embedding_func = self._create_embedding_func()
    
    def _create_llm_func(self):
        """创建LLM函数"""
        return lambda prompt, **kwargs: openai_complete_if_cache(
            self.raganything_config.deepseek_model,
            prompt,
            api_key=self.raganything_config.deepseek_api_key,
            base_url=self.raganything_config.deepseek_base_url,
            **kwargs
        )
    
    def _create_embedding_func(self):
        """创建嵌入函数"""
        from simple_qwen_embed import qwen_embed
        return EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=512, 
            func=qwen_embed
        )
```

### 4.4 部署方案

#### 4.4.1 Docker容器化

```dockerfile
# Dockerfile
FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制代码
COPY . /app
WORKDIR /app

# 环境配置
ENV WORKING_DIR=/data/rag_storage
ENV OUTPUT_DIR=/data/output
ENV MODEL_CACHE_DIR=/data/models

# 启动脚本
CMD ["python", "raganything_server.py"]
```

#### 4.4.2 环境配置

```bash
# .env配置示例
# RAG-Anything配置
WORKING_DIR=./rag_storage
OUTPUT_DIR=./output
PARSER=mineru
PARSE_METHOD=auto

# 多模态处理
ENABLE_IMAGE_PROCESSING=true
ENABLE_TABLE_PROCESSING=true  
ENABLE_EQUATION_PROCESSING=true

# DeepSeek配置
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_VISION_MODEL=deepseek-vl

# Qwen本地嵌入
QWEN_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_DEVICE=auto
MODEL_CACHE_DIR=./models

# 上下文配置
CONTEXT_WINDOW=1
CONTEXT_MODE=page
MAX_CONTEXT_TOKENS=2000
INCLUDE_HEADERS=true
INCLUDE_CAPTIONS=true
```

## 5. LightRAG WebUI增强集成方案

### 5.1 实时进度显示前端设计

#### 5.1.1 WebSocket进度监控客户端

```typescript
// services/ProgressWebSocket.ts
export interface ProgressUpdate {
    task_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    current_stage: string;
    progress_percent: number;
    stage_progress: number;
    message: string;
    estimated_remaining?: number;
    details?: Record<string, any>;
}

export class ProgressWebSocketClient {
    private ws: WebSocket | null = null;
    private callbacks: Map<string, (progress: ProgressUpdate) => void> = new Map();
    private reconnectTimer: NodeJS.Timeout | null = null;
    private clientId: string;

    constructor() {
        this.clientId = `client-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    async connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/progress`;
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket连接已建立');
                // 发送客户端ID
                this.ws?.send(JSON.stringify({
                    type: 'client_register',
                    client_id: this.clientId
                }));
                resolve();
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    if (message.type === 'progress_update') {
                        const taskId = message.task_id;
                        const callback = this.callbacks.get(taskId);
                        if (callback) {
                            callback(message.data);
                        }
                    }
                } catch (error) {
                    console.error('WebSocket消息解析错误:', error);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket连接已关闭');
                this.scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                reject(error);
            };
        });
    }

    subscribeTask(taskId: string, callback: (progress: ProgressUpdate) => void): void {
        this.callbacks.set(taskId, callback);
        
        // 发送订阅消息
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'subscribe_task',
                task_id: taskId,
                client_id: this.clientId
            }));
        }
    }

    unsubscribeTask(taskId: string): void {
        this.callbacks.delete(taskId);
        
        // 发送取消订阅消息
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'unsubscribe_task',
                task_id: taskId,
                client_id: this.clientId
            }));
        }
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        this.reconnectTimer = setTimeout(() => {
            console.log('尝试重新连接WebSocket...');
            this.connect().catch(console.error);
        }, 3000);
    }

    disconnect(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.callbacks.clear();
    }
}

// 全局单例
export const progressWS = new ProgressWebSocketClient();
```

#### 5.1.2 增强的API客户端

```typescript
// api/ragAnythingAPI.ts
export interface ProcessingOptions {
    parser: 'mineru' | 'docling';
    parse_method: 'auto' | 'ocr' | 'txt';
    enable_image_processing: boolean;
    enable_table_processing: boolean;
    enable_equation_processing: boolean;
    lang?: string;
    device?: string;
}

export interface TaskStatus {
    task_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
    current_stage: string;
    progress_percent: number;
    stage_progress: number;
    estimated_remaining?: number;
    multimodal_stats?: {
        images_count: number;
        tables_count: number;
        equations_count: number;
    };
    start_time: string;
    error_message?: string;
}

export interface MultimodalContent {
    type: 'image' | 'table' | 'equation' | 'generic';
    img_path?: string;
    table_data?: string;
    latex?: string;
    [key: string]: any;
}

export class RAGAnythingAPI {
    private baseURL: string;

    constructor(baseURL: string = '') {
        this.baseURL = baseURL;
    }

    // 文档处理API
    async processDocument(file: File, options: ProcessingOptions): Promise<{task_id: string}> {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('options', JSON.stringify(options));

        const response = await fetch(`${this.baseURL}/documents/process`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`文档处理失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 获取任务状态
    async getTaskStatus(taskId: string): Promise<TaskStatus> {
        const response = await fetch(`${this.baseURL}/documents/tasks/${taskId}`);
        
        if (!response.ok) {
            throw new Error(`获取任务状态失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 取消任务
    async cancelTask(taskId: string): Promise<void> {
        const response = await fetch(`${this.baseURL}/documents/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`取消任务失败: ${response.statusText}`);
        }
    }

    // 获取所有任务
    async getTasks(status?: string, limit = 50, offset = 0): Promise<{tasks: TaskStatus[], total: number}> {
        const params = new URLSearchParams({
            limit: limit.toString(),
            offset: offset.toString()
        });
        
        if (status) {
            params.append('status', status);
        }

        const response = await fetch(`${this.baseURL}/documents/tasks?${params}`);
        
        if (!response.ok) {
            throw new Error(`获取任务列表失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 标准查询 (兼容LightRAG WebUI)
    async query(query: string, options: {
        mode?: string;
        vlm_enhanced?: boolean;
        top_k?: number;
        response_type?: string;
        conversation_history?: any[];
    } = {}): Promise<{response: string, query_id: string}> {
        const response = await fetch(`${this.baseURL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query,
                mode: options.mode || 'hybrid',
                vlm_enhanced: options.vlm_enhanced || false,
                top_k: options.top_k || 60,
                response_type: options.response_type,
                conversation_history: options.conversation_history || []
            })
        });

        if (!response.ok) {
            throw new Error(`查询失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 多模态查询
    async queryMultimodal(
        query: string, 
        multimodalContent: MultimodalContent[], 
        mode = 'hybrid'
    ): Promise<{response: string, query_id: string}> {
        const response = await fetch(`${this.baseURL}/query/multimodal`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query,
                multimodal_content: multimodalContent,
                mode
            })
        });

        if (!response.ok) {
            throw new Error(`多模态查询失败: ${response.statusText}`);
        }

        return await response.json();
    }

    // 获取系统能力
    async getCapabilities(): Promise<any> {
        const response = await fetch(`${this.baseURL}/query/capabilities`);
        
        if (!response.ok) {
            throw new Error(`获取系统能力失败: ${response.statusText}`);
        }

        return await response.json();
    }
}

// 全局API实例
export const ragAPI = new RAGAnythingAPI();
```

#### 5.1.3 实时进度显示UI组件

```tsx
// components/ProgressTracker.tsx
import React, { useState, useEffect } from 'react';
import { Progress, Card, Tag, Typography, Space, Button, Alert } from 'antd';
import { ClockCircleOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { progressWS, type ProgressUpdate } from '../services/ProgressWebSocket';

const { Text, Title } = Typography;

interface ProgressTrackerProps {
    taskId: string;
    onComplete?: (taskId: string) => void;
    onError?: (taskId: string, error: string) => void;
}

const stageNames: Record<string, string> = {
    parsing: '文档解析',
    separation: '内容分离',
    text_insert: '文本处理',
    image_process: '图像处理',
    table_process: '表格处理',
    equation_process: '公式处理',
    graph_build: '知识图谱构建',
    indexing: '索引优化',
    completed: '处理完成'
};

const stageColors: Record<string, string> = {
    parsing: '#1890ff',
    separation: '#52c41a',
    text_insert: '#13c2c2',
    image_process: '#eb2f96',
    table_process: '#f5222d',
    equation_process: '#fa8c16',
    graph_build: '#722ed1',
    indexing: '#faad14',
    completed: '#52c41a'
};

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({ 
    taskId, 
    onComplete, 
    onError 
}) => {
    const [progress, setProgress] = useState<ProgressUpdate | null>(null);
    const [connected, setConnected] = useState(false);

    useEffect(() => {
        // 连接WebSocket
        const connectAndSubscribe = async () => {
            try {
                await progressWS.connect();
                setConnected(true);
                
                // 订阅任务进度
                progressWS.subscribeTask(taskId, (update: ProgressUpdate) => {
                    setProgress(update);
                    
                    // 处理完成回调
                    if (update.status === 'completed' && onComplete) {
                        onComplete(taskId);
                    }
                    
                    // 处理错误回调
                    if (update.status === 'failed' && onError) {
                        onError(taskId, update.details?.error || '处理失败');
                    }
                });
            } catch (error) {
                console.error('WebSocket连接失败:', error);
                setConnected(false);
            }
        };

        connectAndSubscribe();

        // 清理函数
        return () => {
            progressWS.unsubscribeTask(taskId);
        };
    }, [taskId, onComplete, onError]);

    const formatTime = (seconds?: number): string => {
        if (!seconds) return '--';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed':
                return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
            case 'failed':
                return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
            case 'running':
                return <ClockCircleOutlined style={{ color: '#1890ff' }} />;
            default:
                return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />;
        }
    };

    const getProgressColor = (status: string): string => {
        switch (status) {
            case 'completed':
                return '#52c41a';
            case 'failed':
                return '#ff4d4f';
            case 'running':
                return '#1890ff';
            default:
                return '#d9d9d9';
        }
    };

    if (!connected) {
        return (
            <Alert
                message="连接状态"
                description="正在连接进度监控服务..."
                type="info"
                showIcon
            />
        );
    }

    if (!progress) {
        return (
            <Alert
                message="等待任务信息"
                description="正在获取任务进度信息..."
                type="info"
                showIcon
            />
        );
    }

    return (
        <Card 
            title={
                <Space>
                    {getStatusIcon(progress.status)}
                    <Title level={5} style={{ margin: 0 }}>
                        文档处理进度
                    </Title>
                </Space>
            }
            extra={
                <Tag color={stageColors[progress.current_stage] || '#default'}>
                    {stageNames[progress.current_stage] || progress.current_stage}
                </Tag>
            }
        >
            {/* 总进度条 */}
            <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Text strong>总进度</Text>
                    <Text>{Math.round(progress.progress_percent)}%</Text>
                </div>
                <Progress 
                    percent={Math.round(progress.progress_percent)}
                    strokeColor={getProgressColor(progress.status)}
                    status={progress.status === 'failed' ? 'exception' : 'active'}
                />
            </div>

            {/* 当前阶段进度 */}
            {progress.status === 'running' && (
                <div style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <Text>当前阶段: {stageNames[progress.current_stage]}</Text>
                        <Text>{Math.round(progress.stage_progress)}%</Text>
                    </div>
                    <Progress 
                        percent={Math.round(progress.stage_progress)}
                        size="small"
                        strokeColor={stageColors[progress.current_stage]}
                    />
                </div>
            )}

            {/* 状态信息 */}
            <Space direction="vertical" style={{ width: '100%' }}>
                {progress.message && (
                    <Text type="secondary">{progress.message}</Text>
                )}
                
                {progress.estimated_remaining && (
                    <Space>
                        <ClockCircleOutlined />
                        <Text>预计剩余时间: {formatTime(progress.estimated_remaining)}</Text>
                    </Space>
                )}

                {/* 多模态统计信息 */}
                {progress.details?.multimodal_stats && (
                    <div>
                        <Text strong>内容统计: </Text>
                        <Space>
                            {progress.details.multimodal_stats.images_count > 0 && (
                                <Tag color="magenta">
                                    图像 {progress.details.multimodal_stats.images_count}
                                </Tag>
                            )}
                            {progress.details.multimodal_stats.tables_count > 0 && (
                                <Tag color="red">
                                    表格 {progress.details.multimodal_stats.tables_count}
                                </Tag>
                            )}
                            {progress.details.multimodal_stats.equations_count > 0 && (
                                <Tag color="orange">
                                    公式 {progress.details.multimodal_stats.equations_count}
                                </Tag>
                            )}
                        </Space>
                    </div>
                )}

                {/* 详细进度信息 */}
                {progress.details?.current_item && (
                    <Text type="secondary">
                        正在处理: {progress.details.current_item}
                        {progress.details.items_completed && progress.details.items_total && (
                            ` (${progress.details.items_completed}/${progress.details.items_total})`
                        )}
                    </Text>
                )}
            </Space>

            {/* 错误信息 */}
            {progress.status === 'failed' && progress.details?.error && (
                <Alert
                    message="处理失败"
                    description={progress.details.error}
                    type="error"
                    style={{ marginTop: 16 }}
                />
            )}
        </Card>
    );
};

// components/EnhancedDocumentUpload.tsx
import React, { useState } from 'react';
import { Upload, Card, Form, Select, Checkbox, Space, Button, message } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { ragAPI, type ProcessingOptions } from '../api/ragAnythingAPI';
import { ProgressTracker } from './ProgressTracker';

const { Dragger } = Upload;
const { Option } = Select;

export const EnhancedDocumentUpload: React.FC = () => {
    const [form] = Form.useForm();
    const [uploading, setUploading] = useState(false);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);

    const defaultOptions: ProcessingOptions = {
        parser: 'mineru',
        parse_method: 'auto',
        enable_image_processing: true,
        enable_table_processing: true,
        enable_equation_processing: true,
        lang: 'en',
        device: 'auto'
    };

    const handleUpload = async () => {
        if (!uploadedFile) {
            message.error('请先选择文件');
            return;
        }

        try {
            setUploading(true);
            const options = form.getFieldsValue() as ProcessingOptions;
            
            // 开始文档处理
            const result = await ragAPI.processDocument(uploadedFile, options);
            
            setCurrentTaskId(result.task_id);
            message.success('文档上传成功，开始处理...');
            
        } catch (error) {
            console.error('上传失败:', error);
            message.error('文档处理失败');
        } finally {
            setUploading(false);
        }
    };

    const handleTaskComplete = (taskId: string) => {
        message.success('文档处理完成！');
        setCurrentTaskId(null);
        setUploadedFile(null);
        form.resetFields();
    };

    const handleTaskError = (taskId: string, error: string) => {
        message.error(`文档处理失败: ${error}`);
        setCurrentTaskId(null);
    };

    const uploadProps = {
        name: 'file',
        multiple: false,
        showUploadList: false,
        beforeUpload: (file: File) => {
            setUploadedFile(file);
            return false; // 阻止自动上传
        },
        accept: '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md',
    };

    return (
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
            {/* 文档上传区域 */}
            <Card title="多模态文档处理" style={{ marginBottom: 16 }}>
                <Dragger {...uploadProps} disabled={uploading || !!currentTaskId}>
                    <p className="ant-upload-drag-icon">
                        <InboxOutlined />
                    </p>
                    <p className="ant-upload-text">
                        点击或拖拽文件到此区域上传
                    </p>
                    <p className="ant-upload-hint">
                        支持PDF、Office文档、文本文件等格式<br/>
                        自动识别和处理图像、表格、公式等多模态内容
                    </p>
                </Dragger>

                {uploadedFile && (
                    <div style={{ marginTop: 16, padding: 12, backgroundColor: '#f6f8fa', borderRadius: 6 }}>
                        <Text>已选择文件: {uploadedFile.name}</Text>
                        <br />
                        <Text type="secondary">大小: {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB</Text>
                    </div>
                )}
            </Card>

            {/* 处理选项 */}
            <Card title="处理选项" style={{ marginBottom: 16 }}>
                <Form
                    form={form}
                    layout="vertical"
                    initialValues={defaultOptions}
                >
                    <Form.Item label="解析器" name="parser">
                        <Select>
                            <Option value="mineru">MinerU 2.0 (推荐)</Option>
                            <Option value="docling">Docling</Option>
                        </Select>
                    </Form.Item>

                    <Form.Item label="解析方法" name="parse_method">
                        <Select>
                            <Option value="auto">自动选择</Option>
                            <Option value="ocr">OCR模式</Option>
                            <Option value="txt">文本模式</Option>
                        </Select>
                    </Form.Item>

                    <Form.Item label="多模态处理">
                        <Space direction="vertical">
                            <Form.Item name="enable_image_processing" valuePropName="checked" noStyle>
                                <Checkbox>图像处理 (使用视觉模型分析图像内容)</Checkbox>
                            </Form.Item>
                            <Form.Item name="enable_table_processing" valuePropName="checked" noStyle>
                                <Checkbox>表格处理 (提取和分析表格数据)</Checkbox>
                            </Form.Item>
                            <Form.Item name="enable_equation_processing" valuePropName="checked" noStyle>
                                <Checkbox>公式处理 (识别和解析数学公式)</Checkbox>
                            </Form.Item>
                        </Space>
                    </Form.Item>

                    <Form.Item label="文档语言" name="lang">
                        <Select>
                            <Option value="en">English</Option>
                            <Option value="zh">中文</Option>
                            <Option value="auto">自动检测</Option>
                        </Select>
                    </Form.Item>

                    <Form.Item label="计算设备" name="device">
                        <Select>
                            <Option value="auto">自动选择</Option>
                            <Option value="cuda">GPU加速</Option>
                            <Option value="cpu">CPU处理</Option>
                        </Select>
                    </Form.Item>
                </Form>

                <Button 
                    type="primary" 
                    size="large"
                    loading={uploading}
                    disabled={!uploadedFile || !!currentTaskId}
                    onClick={handleUpload}
                    style={{ width: '100%' }}
                >
                    {uploading ? '正在上传...' : '开始处理文档'}
                </Button>
            </Card>

            {/* 实时进度显示 */}
            {currentTaskId && (
                <ProgressTracker
                    taskId={currentTaskId}
                    onComplete={handleTaskComplete}
                    onError={handleTaskError}
                />
            )}
        </div>
    );
};
```

#### 5.1.3 文档管理扩展

```tsx
// components/DocumentUpload.tsx  
export const EnhancedDocumentUpload: React.FC = () => {
    const [uploadOptions, setUploadOptions] = useState({
        enable_multimodal: true,
        parser: 'mineru',
        parse_method: 'auto',
        enable_image_processing: true,
        enable_table_processing: true,
        enable_equation_processing: true
    });
    
    return (
        <Card title="增强文档上传">
            <Upload.Dragger {...uploadProps}>
                <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p className="ant-upload-hint">
                    支持多模态文档处理，包括图像、表格、公式识别
                </p>
            </Upload.Dragger>
            
            <Divider>处理选项</Divider>
            
            <Form layout="vertical">
                <Form.Item label="解析器">
                    <Select 
                        value={uploadOptions.parser}
                        onChange={(value) => setUploadOptions(prev => ({...prev, parser: value}))}
                    >
                        <Option value="mineru">MinerU 2.0</Option>
                        <Option value="docling">Docling</Option>
                    </Select>
                </Form.Item>
                
                <Form.Item label="多模态处理">
                    <Space direction="vertical">
                        <Checkbox 
                            checked={uploadOptions.enable_image_processing}
                            onChange={(e) => setUploadOptions(prev => ({
                                ...prev, 
                                enable_image_processing: e.target.checked
                            }))}
                        >
                            图像处理
                        </Checkbox>
                        <Checkbox 
                            checked={uploadOptions.enable_table_processing}
                            onChange={(e) => setUploadOptions(prev => ({
                                ...prev, 
                                enable_table_processing: e.target.checked
                            }))}
                        >
                            表格处理
                        </Checkbox>
                        <Checkbox 
                            checked={uploadOptions.enable_equation_processing}
                            onChange={(e) => setUploadOptions(prev => ({
                                ...prev, 
                                enable_equation_processing: e.target.checked
                            }))}
                        >
                            公式处理
                        </Checkbox>
                    </Space>
                </Form.Item>
            </Form>
        </Card>
    );
};
```

### 5.2 状态管理扩展

```tsx
// contexts/RAGAnythingContext.tsx
interface RAGAnythingState {
    capabilities: SystemCapabilities | null;
    processorStatus: ProcessorStatus | null;
    systemConfig: SystemConfig | null;
}

export const RAGAnythingProvider: React.FC<{children: ReactNode}> = ({children}) => {
    const [state, setState] = useState<RAGAnythingState>({
        capabilities: null,
        processorStatus: null,
        systemConfig: null
    });
    
    useEffect(() => {
        // 初始化时获取系统能力
        ragAnythingAPI.getCapabilities().then(capabilities => {
            setState(prev => ({...prev, capabilities}));
        });
    }, []);
    
    return (
        <RAGAnythingContext.Provider value={{state, setState}}>
            {children}
        </RAGAnythingContext.Provider>
    );
};
```

## 6. 总结与建议

### 6.1 架构优势

#### RAG-Anything的核心优势
1. **多模态处理能力**: 原生支持图像、表格、公式等复杂内容
2. **灵活的解析器系统**: 支持MinerU 2.0和Docling双引擎  
3. **模块化设计**: Mixin架构支持功能组合和扩展
4. **完整的配置系统**: 环境变量驱动的配置管理
5. **VLM集成**: 原生视觉语言模型支持

#### WebUI集成方案优势
1. **实时进度监控**: 解决多模态处理耗时的用户体验问题
2. **零兼容性负担**: 专为RAG-Anything优化，无历史包袱
3. **现代化架构**: WebSocket实时通信，分阶段进度跟踪
4. **原生多模态支持**: UI组件原生支持多模态内容展示

### 6.2 实施建议

#### 第一阶段：核心API开发 (2-3周)
1. **RAG-Anything服务器架构**: 实现ProgressAwareRAGAnything核心处理器
2. **任务管理系统**: 构建TaskManager和处理状态追踪
3. **基础API端点**: 文档处理、任务查询、系统状态API
4. **WebSocket服务**: 实时进度推送基础架构

#### 第二阶段：前端集成开发 (2-3周)  
1. **WebSocket客户端**: 实现ProgressWebSocketClient
2. **UI组件开发**: ProgressTracker和EnhancedDocumentUpload
3. **API客户端**: RAGAnythingAPI类和接口封装
4. **LightRAG WebUI改造**: 集成新组件到现有界面

#### 第三阶段：功能完善 (1-2周)
1. **多模态查询界面**: 图像、表格、公式查询组件
2. **批量处理功能**: 文件夹批量处理界面
3. **错误处理优化**: 完善错误提示和恢复机制
4. **性能优化**: 缓存策略和并发控制

#### 第四阶段：测试与部署 (1周)
1. **端到端测试**: 完整的文档处理流程测试
2. **性能压力测试**: 大文件和批量处理测试
3. **用户界面测试**: 多浏览器兼容性测试
4. **生产环境部署**: Docker容器化和配置优化

### 6.3 技术栈总结

#### 后端技术栈
- **核心框架**: FastAPI + RAG-Anything (基于LightRAG)
- **实时通信**: WebSocket + Server-Sent Events
- **任务管理**: 异步任务队列 + 状态管理
- **文档解析**: MinerU 2.0 / Docling
- **模型集成**: DeepSeek API + 本地Qwen Embedding
- **存储系统**: LightRAG统一存储抽象

#### 前端技术栈
- **核心框架**: React + TypeScript + Vite (复用LightRAG WebUI)
- **UI组件库**: Ant Design
- **实时通信**: WebSocket客户端 + 自动重连
- **状态管理**: React Hooks + Context API
- **进度显示**: 多阶段进度条 + 实时更新

#### 关键创新点
1. **分阶段进度监控**: 8个处理阶段的详细进度追踪
2. **WebSocket实时推送**: 毫秒级的进度更新响应
3. **智能任务管理**: 任务状态持久化和恢复机制
4. **多模态内容可视化**: 实时显示图像、表格、公式处理进度
5. **用户体验优化**: 预估时间、错误恢复、批量处理支持

#### 部署方案
- **容器化**: Docker + Docker Compose
- **配置管理**: 环境变量 + .env文件
- **模型管理**: HuggingFace Hub + 本地缓存
- **监控日志**: 结构化日志 + WebSocket连接监控

### 6.4 项目价值

这个设计方案成功解决了多模态RAG系统的关键用户体验问题：

1. **解决进度可视化痛点**: 多模态处理从"黑盒"变为透明的分阶段可视化过程
2. **提升用户体验**: 从被动等待到主动了解处理进展，显著降低用户焦虑
3. **实现技术升级**: LightRAG WebUI无缝接入RAG-Anything的强大多模态能力
4. **保持架构简洁**: 基于现有技术栈，无需大规模重构

**最终效果**: 用户可以通过熟悉的LightRAG WebUI界面，实时观看文档的多模态处理过程，从文档解析、图像分析、表格提取到知识图谱构建的每个步骤都清晰可见，创造了业界领先的多模态RAG用户体验。