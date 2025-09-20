"""
状态管理器
集中管理应用状态，替代全局变量，提供线程安全的状态操作
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from threading import RLock
from fastapi import WebSocket
import asyncpg
import logging

from config.settings import settings


def parse_datetime(dt_str: str) -> datetime:
    """解析ISO格式的日期时间字符串为 datetime 对象"""
    if isinstance(dt_str, datetime):
        return dt_str
    if isinstance(dt_str, str):
        # 处理ISO格式的日期时间字符串
        if 'T' in dt_str:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(dt_str)
    return dt_str


@dataclass
class Document:
    """文档状态数据类"""
    document_id: str
    file_name: str
    file_path: str
    file_size: int
    status: str  # "uploaded", "processing", "completed", "failed"
    created_at: str
    updated_at: str
    task_id: Optional[str] = None
    processing_time: Optional[float] = None
    content_length: Optional[int] = None
    chunks_count: Optional[int] = None
    rag_doc_id: Optional[str] = None
    content_summary: Optional[str] = None
    error_message: Optional[str] = None
    batch_operation_id: Optional[str] = None
    parser_used: Optional[str] = None
    parser_reason: Optional[str] = None
    content_hash: Optional[str] = None  # SHA-256哈希值，用于重复检测


@dataclass 
class Task:
    """任务状态数据类"""
    task_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    stage: str
    progress: int
    file_path: str
    file_name: str
    file_size: int
    created_at: str
    updated_at: str
    document_id: str
    total_stages: int
    stage_details: Dict[str, Any]
    multimodal_stats: Dict[str, Any]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    batch_operation_id: Optional[str] = None
    parser_info: Optional[Dict[str, Any]] = None


@dataclass
class BatchOperation:
    """批量操作状态数据类"""
    batch_operation_id: str
    operation_type: str  # "upload", "process"
    status: str  # "running", "completed", "failed", "cancelled"
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    started_at: str
    results: List[Dict[str, Any]]
    completed_at: Optional[str] = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    system_warnings: Optional[List[str]] = None


class StateManager:
    """
    状态管理器 - 线程安全的应用状态管理
    替代原来的全局变量，提供集中化的状态管理
    """
    
    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._tasks: Dict[str, Task] = {}
        self._batch_operations: Dict[str, BatchOperation] = {}
        self._active_websockets: Dict[str, WebSocket] = {}
        self._processing_log_websockets: List[WebSocket] = []
        
        # 线程安全锁
        self._documents_lock = RLock()
        self._tasks_lock = RLock()
        self._batch_lock = RLock()
        self._ws_lock = RLock()
        
        # 数据库连接池
        self._db_pool: Optional[asyncpg.Pool] = None
        self._db_initialized = False
        
        # 从环境变量构建数据库连接字符串
        postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        postgres_port = os.getenv('POSTGRES_PORT', '5432')
        postgres_db = os.getenv('POSTGRES_DB', 'raganything')
        postgres_user = os.getenv('POSTGRES_USER', 'ragsvr')
        postgres_password = os.getenv('POSTGRES_PASSWORD', '')
        
        if postgres_host.startswith('/'):  # Unix socket
            self._db_dsn = f"postgresql://{postgres_user}@/{postgres_db}?host={postgres_host}"
        else:
            self._db_dsn = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    
    async def _ensure_db_connection(self):
        """确保数据库连接池已初始化"""
        if not self._db_initialized:
            try:
                self._db_pool = await asyncpg.create_pool(
                    self._db_dsn,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                self._db_initialized = True
                logging.info(f"数据库连接池初始化成功: {self._db_dsn}")
            except Exception as e:
                logging.error(f"数据库连接失败: {e}")
                raise
    
    async def close_db_connection(self):
        """关闭数据库连接池"""
        if self._db_pool:
            await self._db_pool.close()
            self._db_pool = None
            self._db_initialized = False
    
    # 文档状态管理
    async def add_document(self, document: Document) -> None:
        """添加文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO documents (
                    id, workspace, file_name, file_path, file_size, status, created_at, updated_at,
                    task_id, processing_time, content_length, chunks_count, rag_doc_id,
                    content_summary, error_message, batch_operation_id, parser_used, parser_reason, content_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (id, workspace) DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    file_path = EXCLUDED.file_path,
                    file_size = EXCLUDED.file_size,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at,
                    task_id = EXCLUDED.task_id,
                    processing_time = EXCLUDED.processing_time,
                    content_length = EXCLUDED.content_length,
                    chunks_count = EXCLUDED.chunks_count,
                    rag_doc_id = EXCLUDED.rag_doc_id,
                    content_summary = EXCLUDED.content_summary,
                    error_message = EXCLUDED.error_message,
                    batch_operation_id = EXCLUDED.batch_operation_id,
                    parser_used = EXCLUDED.parser_used,
                    parser_reason = EXCLUDED.parser_reason,
                    content_hash = EXCLUDED.content_hash
            """, document.document_id, 'default', document.file_name, document.file_path, 
                 document.file_size, document.status, parse_datetime(document.created_at), 
                 parse_datetime(document.updated_at), document.task_id, document.processing_time,
                 document.content_length, document.chunks_count, document.rag_doc_id,
                 document.content_summary, document.error_message, document.batch_operation_id,
                 document.parser_used, document.parser_reason, document.content_hash)
        
        with self._documents_lock:
            self._documents[document.document_id] = document
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """获取文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, file_name, file_path, file_size, status, created_at, updated_at,
                       task_id, processing_time, content_length, chunks_count, rag_doc_id,
                       content_summary, error_message, batch_operation_id, parser_used, parser_reason, content_hash
                FROM documents WHERE id = $1 AND workspace = 'default'
            """, document_id)
            
            if row:
                doc = Document(
                    document_id=row['id'],
                    file_name=row['file_name'],
                    file_path=row['file_path'],
                    file_size=row['file_size'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    task_id=row['task_id'],
                    processing_time=row['processing_time'],
                    content_length=row['content_length'],
                    chunks_count=row['chunks_count'],
                    rag_doc_id=row['rag_doc_id'],
                    content_summary=row['content_summary'],
                    error_message=row['error_message'],
                    batch_operation_id=row['batch_operation_id'],
                    parser_used=row['parser_used'],
                    parser_reason=row['parser_reason'],
                    content_hash=row['content_hash']
                )
                
                with self._documents_lock:
                    self._documents[document_id] = doc
                
                return doc
            
            return None
    
    async def update_document_status(self, document_id: str, status: str, **kwargs) -> None:
        """更新文档状态"""
        await self._ensure_db_connection()
        
        # 构建更新字段
        update_fields = ["status = $2", "updated_at = $3"]
        values = [document_id, status, datetime.now()]
        param_idx = 4
        
        for key, value in kwargs.items():
            if key in ['task_id', 'processing_time', 'content_length', 'chunks_count', 
                      'rag_doc_id', 'content_summary', 'error_message', 
                      'batch_operation_id', 'parser_used', 'parser_reason', 'content_hash']:
                update_fields.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1
        
        query = f"UPDATE documents SET {', '.join(update_fields)} WHERE id = $1 AND workspace = 'default'"
        
        async with self._db_pool.acquire() as conn:
            await conn.execute(query, *values)
        
        # 更新内存缓存
        with self._documents_lock:
            if document_id in self._documents:
                doc = self._documents[document_id]
                doc.status = status
                doc.updated_at = datetime.now().isoformat()
                for key, value in kwargs.items():
                    if hasattr(doc, key):
                        setattr(doc, key, value)
    
    async def get_all_documents(self) -> List[Document]:
        """获取所有文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, file_name, file_path, file_size, status, created_at, updated_at,
                       task_id, processing_time, content_length, chunks_count, rag_doc_id,
                       content_summary, error_message, batch_operation_id, parser_used, parser_reason, content_hash
                FROM documents WHERE workspace = 'default' ORDER BY created_at DESC
            """)
            
            documents = []
            for row in rows:
                doc = Document(
                    document_id=row['id'],
                    file_name=row['file_name'],
                    file_path=row['file_path'],
                    file_size=row['file_size'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    task_id=row['task_id'],
                    processing_time=row['processing_time'],
                    content_length=row['content_length'],
                    chunks_count=row['chunks_count'],
                    rag_doc_id=row['rag_doc_id'],
                    content_summary=row['content_summary'],
                    error_message=row['error_message'],
                    batch_operation_id=row['batch_operation_id'],
                    parser_used=row['parser_used'],
                    parser_reason=row['parser_reason'],
                    content_hash=row['content_hash']
                )
                documents.append(doc)
            
            # 更新内存缓存
            with self._documents_lock:
                self._documents.clear()
                for doc in documents:
                    self._documents[doc.document_id] = doc
            
            return documents
    
    async def remove_document(self, document_id: str) -> bool:
        """删除文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM documents WHERE id = $1 AND workspace = 'default'", document_id)
            deleted = result.split()[-1] != '0'  # 检查是否删除了行
            
            if deleted:
                with self._documents_lock:
                    self._documents.pop(document_id, None)
            
            return deleted
    
    async def clear_documents(self) -> int:
        """清空所有文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            # 获取当前文档数量
            count_result = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE workspace = 'default'")
            count = int(count_result)
            
            # 删除所有文档
            await conn.execute("DELETE FROM documents WHERE workspace = 'default'")
            
            with self._documents_lock:
                self._documents.clear()
        
        return count
    
    # 任务状态管理
    async def add_task(self, task: Task) -> None:
        """添加任务"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tasks (
                    task_id, status, stage, progress, file_path, file_name, file_size,
                    created_at, updated_at, document_id, total_stages, stage_details,
                    multimodal_stats, started_at, completed_at, error_message,
                    batch_operation_id, parser_info
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (task_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    stage = EXCLUDED.stage,
                    progress = EXCLUDED.progress,
                    updated_at = EXCLUDED.updated_at,
                    total_stages = EXCLUDED.total_stages,
                    stage_details = EXCLUDED.stage_details,
                    multimodal_stats = EXCLUDED.multimodal_stats,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    error_message = EXCLUDED.error_message,
                    batch_operation_id = EXCLUDED.batch_operation_id,
                    parser_info = EXCLUDED.parser_info
            """, task.task_id, task.status, task.stage, task.progress,
                 task.file_path, task.file_name, task.file_size,
                 parse_datetime(task.created_at), parse_datetime(task.updated_at), task.document_id,
                 task.total_stages, json.dumps(task.stage_details),
                 json.dumps(task.multimodal_stats), 
                 parse_datetime(task.started_at) if task.started_at else None,
                 parse_datetime(task.completed_at) if task.completed_at else None,
                 task.error_message, task.batch_operation_id,
                 json.dumps(task.parser_info) if task.parser_info else None)
        
        with self._tasks_lock:
            self._tasks[task.task_id] = task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT task_id, status, stage, progress, file_path, file_name, file_size,
                       created_at, updated_at, document_id, total_stages, stage_details,
                       multimodal_stats, started_at, completed_at, error_message,
                       batch_operation_id, parser_info
                FROM tasks WHERE task_id = $1
            """, task_id)
            
            if row:
                task = Task(
                    task_id=row['task_id'],
                    status=row['status'],
                    stage=row['stage'],
                    progress=row['progress'],
                    file_path=row['file_path'],
                    file_name=row['file_name'],
                    file_size=row['file_size'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    document_id=row['document_id'],
                    total_stages=row['total_stages'],
                    stage_details=json.loads(row['stage_details']) if row['stage_details'] else {},
                    multimodal_stats=json.loads(row['multimodal_stats']) if row['multimodal_stats'] else {},
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    error_message=row['error_message'],
                    batch_operation_id=row['batch_operation_id'],
                    parser_info=json.loads(row['parser_info']) if row['parser_info'] else None
                )
                
                with self._tasks_lock:
                    self._tasks[task_id] = task
                
                return task
            
            return None
    
    async def update_task(self, task_id: str, **kwargs) -> None:
        """更新任务状态"""
        with self._tasks_lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.updated_at = datetime.now().isoformat()
                
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
        
        await self._save_state()
    
    async def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT task_id, status, stage, progress, file_path, file_name, file_size,
                       created_at, updated_at, document_id, total_stages, stage_details,
                       multimodal_stats, started_at, completed_at, error_message,
                       batch_operation_id, parser_info
                FROM tasks ORDER BY created_at DESC
            """)
            
            tasks = []
            for row in rows:
                task = Task(
                    task_id=row['task_id'],
                    status=row['status'],
                    stage=row['stage'],
                    progress=row['progress'],
                    file_path=row['file_path'],
                    file_name=row['file_name'],
                    file_size=row['file_size'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    document_id=row['document_id'],
                    total_stages=row['total_stages'],
                    stage_details=json.loads(row['stage_details']) if row['stage_details'] else {},
                    multimodal_stats=json.loads(row['multimodal_stats']) if row['multimodal_stats'] else {},
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    error_message=row['error_message'],
                    batch_operation_id=row['batch_operation_id'],
                    parser_info=json.loads(row['parser_info']) if row['parser_info'] else None
                )
                tasks.append(task)
            
            # 更新内存缓存
            with self._tasks_lock:
                self._tasks.clear()
                for task in tasks:
                    self._tasks[task.task_id] = task
            
            return tasks
    
    async def get_active_tasks(self) -> List[Task]:
        """获取活跃任务"""
        with self._tasks_lock:
            return [task for task in self._tasks.values() if task.status == "running"]
    
    async def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._tasks_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                await self._save_state()
                return True
            return False
    
    async def clear_tasks(self) -> int:
        """清空所有任务"""
        with self._tasks_lock:
            count = len(self._tasks)
            self._tasks.clear()
        await self._save_state()
        return count
    
    # 批量操作管理
    async def add_batch_operation(self, batch_op: BatchOperation) -> None:
        """添加批量操作"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO batch_operations (
                    batch_operation_id, operation_type, status, total_items,
                    completed_items, failed_items, progress, started_at, results,
                    completed_at, error, error_details, system_warnings
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (batch_operation_id) DO UPDATE SET
                    operation_type = EXCLUDED.operation_type,
                    status = EXCLUDED.status,
                    total_items = EXCLUDED.total_items,
                    completed_items = EXCLUDED.completed_items,
                    failed_items = EXCLUDED.failed_items,
                    progress = EXCLUDED.progress,
                    results = EXCLUDED.results,
                    completed_at = EXCLUDED.completed_at,
                    error = EXCLUDED.error,
                    error_details = EXCLUDED.error_details,
                    system_warnings = EXCLUDED.system_warnings
            """, batch_op.batch_operation_id, batch_op.operation_type, batch_op.status,
                 batch_op.total_items, batch_op.completed_items, batch_op.failed_items,
                 batch_op.progress, parse_datetime(batch_op.started_at), json.dumps(batch_op.results),
                 parse_datetime(batch_op.completed_at) if batch_op.completed_at else None, batch_op.error, 
                 json.dumps(batch_op.error_details) if batch_op.error_details else None,
                 json.dumps(batch_op.system_warnings) if batch_op.system_warnings else None)
        
        with self._batch_lock:
            self._batch_operations[batch_op.batch_operation_id] = batch_op
    
    async def get_batch_operation(self, batch_id: str) -> Optional[BatchOperation]:
        """获取批量操作"""
        with self._batch_lock:
            return self._batch_operations.get(batch_id)
    
    async def update_batch_operation(self, batch_id: str, **kwargs) -> None:
        """更新批量操作"""
        with self._batch_lock:
            if batch_id in self._batch_operations:
                batch_op = self._batch_operations[batch_id]
                for key, value in kwargs.items():
                    if hasattr(batch_op, key):
                        setattr(batch_op, key, value)
        
        await self._save_state()
    
    async def get_all_batch_operations(self) -> List[BatchOperation]:
        """获取所有批量操作"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT batch_operation_id, operation_type, status, total_items, 
                       completed_items, failed_items, progress, started_at, results,
                       completed_at, error, error_details, system_warnings
                FROM batch_operations ORDER BY started_at DESC
            """)
            
            batch_operations = []
            for row in rows:
                batch_op = BatchOperation(
                    batch_operation_id=row['batch_operation_id'],
                    operation_type=row['operation_type'],
                    status=row['status'],
                    total_items=row['total_items'],
                    completed_items=row['completed_items'],
                    failed_items=row['failed_items'],
                    progress=row['progress'],
                    started_at=row['started_at'],
                    results=json.loads(row['results']) if row['results'] else [],
                    completed_at=row['completed_at'],
                    error=row['error'],
                    error_details=json.loads(row['error_details']) if row['error_details'] else None,
                    system_warnings=json.loads(row['system_warnings']) if row['system_warnings'] else None
                )
                batch_operations.append(batch_op)
            
            # 更新内存缓存
            with self._batch_lock:
                self._batch_operations.clear()
                for batch_op in batch_operations:
                    self._batch_operations[batch_op.batch_operation_id] = batch_op
            
            return batch_operations
    
    # WebSocket连接管理
    async def add_websocket(self, task_id: str, websocket: WebSocket) -> None:
        """添加WebSocket连接"""
        with self._ws_lock:
            self._active_websockets[task_id] = websocket
    
    async def remove_websocket(self, task_id: str) -> None:
        """移除WebSocket连接"""
        with self._ws_lock:
            self._active_websockets.pop(task_id, None)
    
    async def get_websocket(self, task_id: str) -> Optional[WebSocket]:
        """获取WebSocket连接"""
        with self._ws_lock:
            return self._active_websockets.get(task_id)
    
    async def add_processing_websocket(self, websocket: WebSocket) -> None:
        """添加处理日志WebSocket"""
        with self._ws_lock:
            if websocket not in self._processing_log_websockets:
                self._processing_log_websockets.append(websocket)
    
    async def remove_processing_websocket(self, websocket: WebSocket) -> None:
        """移除处理日志WebSocket"""
        with self._ws_lock:
            if websocket in self._processing_log_websockets:
                self._processing_log_websockets.remove(websocket)
    
    async def get_processing_websockets(self) -> List[WebSocket]:
        """获取所有处理日志WebSocket"""
        with self._ws_lock:
            return self._processing_log_websockets.copy()
    
    async def clear_websockets(self) -> None:
        """清空所有WebSocket连接"""
        with self._ws_lock:
            # 尝试关闭所有连接
            for ws in self._active_websockets.values():
                try:
                    await ws.close()
                except:
                    pass
            
            for ws in self._processing_log_websockets:
                try:
                    await ws.close()
                except:
                    pass
            
            self._active_websockets.clear()
            self._processing_log_websockets.clear()
    
    # 状态持久化（已改为数据库存储，保留方法以兼容现有代码）
    async def _save_state(self) -> None:
        """保存状态到数据库（替代原文件保存）"""
        # 这个方法现在是空的，因为数据已经在各个操作中直接保存到数据库
        # 保留此方法是为了兼容现有调用此方法的代码
        pass
    
    async def load_state(self) -> None:
        """从数据库加载状态"""
        try:
            await self._ensure_db_connection()
            
            # 加载所有文档到内存缓存
            documents = await self.get_all_documents()
            
            # 加载所有任务到内存缓存
            tasks = await self.get_all_tasks()
            
            # 加载所有批量操作到内存缓存
            batch_operations = await self.get_all_batch_operations()
            
            logging.info(f"从数据库加载状态: {len(documents)} 个文档, {len(tasks)} 个任务, {len(batch_operations)} 个批量操作")
            
        except Exception as e:
            logging.error(f"从数据库加载状态失败: {str(e)}")
    
    # 统计信息
    async def get_statistics(self) -> Dict[str, Any]:
        """获取状态统计信息"""
        with self._documents_lock, self._tasks_lock, self._batch_lock:
            return {
                "documents": {
                    "total": len(self._documents),
                    "uploaded": len([d for d in self._documents.values() if d.status == "uploaded"]),
                    "processing": len([d for d in self._documents.values() if d.status == "processing"]),
                    "completed": len([d for d in self._documents.values() if d.status == "completed"]),
                    "failed": len([d for d in self._documents.values() if d.status == "failed"])
                },
                "tasks": {
                    "total": len(self._tasks),
                    "active": len([t for t in self._tasks.values() if t.status == "running"]),
                    "completed": len([t for t in self._tasks.values() if t.status == "completed"]),
                    "failed": len([t for t in self._tasks.values() if t.status == "failed"])
                },
                "batch_operations": {
                    "total": len(self._batch_operations),
                    "running": len([b for b in self._batch_operations.values() if b.status == "running"]),
                    "completed": len([b for b in self._batch_operations.values() if b.status == "completed"])
                },
                "websockets": {
                    "active_tasks": len(self._active_websockets),
                    "processing_logs": len(self._processing_log_websockets)
                }
            }
    
    # 哈希重复检查
    async def check_duplicate_by_hash(self, content_hash: str) -> Optional[str]:
        """检查是否存在相同哈希的文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id FROM documents 
                WHERE content_hash = $1 AND workspace = 'default'
                LIMIT 1
            """, content_hash)
            
            return row['id'] if row else None
    
    async def find_documents_by_hash(self, content_hash: str) -> List[Document]:
        """查找所有具有相同哈希的文档"""
        await self._ensure_db_connection()
        
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, file_name, file_path, file_size, status, created_at, updated_at,
                       task_id, processing_time, content_length, chunks_count, rag_doc_id,
                       content_summary, error_message, batch_operation_id, parser_used, parser_reason, content_hash
                FROM documents WHERE content_hash = $1 AND workspace = 'default'
            """, content_hash)
            
            documents = []
            for row in rows:
                doc = Document(
                    document_id=row['id'],
                    file_name=row['file_name'],
                    file_path=row['file_path'],
                    file_size=row['file_size'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    task_id=row['task_id'],
                    processing_time=row['processing_time'],
                    content_length=row['content_length'],
                    chunks_count=row['chunks_count'],
                    rag_doc_id=row['rag_doc_id'],
                    content_summary=row['content_summary'],
                    error_message=row['error_message'],
                    batch_operation_id=row['batch_operation_id'],
                    parser_used=row['parser_used'],
                    parser_reason=row['parser_reason'],
                    content_hash=row['content_hash']
                )
                documents.append(doc)
            
            return documents


# 创建全局状态管理器实例（单例）
_state_manager_instance = None

def get_state_manager() -> StateManager:
    """获取状态管理器实例（单例模式）"""
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager()
    return _state_manager_instance