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

from config.settings import settings


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
        
        # 状态持久化文件路径
        self._state_file = os.path.join(settings.working_dir, "api_documents_state.json")
    
    # 文档状态管理
    async def add_document(self, document: Document) -> None:
        """添加文档"""
        with self._documents_lock:
            self._documents[document.document_id] = document
        await self._save_state()
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """获取文档"""
        with self._documents_lock:
            return self._documents.get(document_id)
    
    async def update_document_status(self, document_id: str, status: str, **kwargs) -> None:
        """更新文档状态"""
        with self._documents_lock:
            if document_id in self._documents:
                doc = self._documents[document_id]
                doc.status = status
                doc.updated_at = datetime.now().isoformat()
                
                # 更新其他字段
                for key, value in kwargs.items():
                    if hasattr(doc, key):
                        setattr(doc, key, value)
        
        await self._save_state()
    
    async def get_all_documents(self) -> List[Document]:
        """获取所有文档"""
        with self._documents_lock:
            return list(self._documents.values())
    
    async def remove_document(self, document_id: str) -> bool:
        """删除文档"""
        with self._documents_lock:
            if document_id in self._documents:
                del self._documents[document_id]
                await self._save_state()
                return True
            return False
    
    async def clear_documents(self) -> int:
        """清空所有文档"""
        with self._documents_lock:
            count = len(self._documents)
            self._documents.clear()
        await self._save_state()
        return count
    
    # 任务状态管理
    async def add_task(self, task: Task) -> None:
        """添加任务"""
        with self._tasks_lock:
            self._tasks[task.task_id] = task
        await self._save_state()
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._tasks_lock:
            return self._tasks.get(task_id)
    
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
        with self._tasks_lock:
            return list(self._tasks.values())
    
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
        with self._batch_lock:
            self._batch_operations[batch_op.batch_operation_id] = batch_op
        await self._save_state()
    
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
        with self._batch_lock:
            return list(self._batch_operations.values())
    
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
    
    # 状态持久化
    async def _save_state(self) -> None:
        """保存状态到磁盘"""
        try:
            state_data = {
                "documents": {doc_id: asdict(doc) for doc_id, doc in self._documents.items()},
                "tasks": {task_id: asdict(task) for task_id, task in self._tasks.items()},
                "batch_operations": {batch_id: asdict(batch_op) for batch_id, batch_op in self._batch_operations.items()},
                "saved_at": datetime.now().isoformat()
            }
            
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            # 记录错误但不抛出异常，避免影响主流程
            import logging
            logging.error(f"保存状态失败: {str(e)}")
    
    async def load_state(self) -> None:
        """从磁盘加载状态"""
        try:
            if not os.path.exists(self._state_file):
                return
                
            with open(self._state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 恢复文档状态
            documents_data = state_data.get("documents", {})
            for doc_id, doc_dict in documents_data.items():
                self._documents[doc_id] = Document(**doc_dict)
            
            # 恢复任务状态
            tasks_data = state_data.get("tasks", {})
            for task_id, task_dict in tasks_data.items():
                self._tasks[task_id] = Task(**task_dict)
            
            # 恢复批量操作状态
            batch_data = state_data.get("batch_operations", {})
            for batch_id, batch_dict in batch_data.items():
                self._batch_operations[batch_id] = BatchOperation(**batch_dict)
                
            import logging
            logging.info(f"从状态文件恢复: {len(self._documents)} 个文档, {len(self._tasks)} 个任务")
            
        except Exception as e:
            import logging
            logging.error(f"加载状态失败: {str(e)}")
    
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


# 创建全局状态管理器实例（单例）
_state_manager_instance = None

def get_state_manager() -> StateManager:
    """获取状态管理器实例（单例模式）"""
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager()
    return _state_manager_instance