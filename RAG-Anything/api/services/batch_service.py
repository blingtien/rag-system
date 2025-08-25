"""
BatchService - 批量操作服务
实现批量操作的协调和进度管理，应用观察者模式和异步并发控制
"""
import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from core.state_manager import StateManager, BatchOperation, Document
from core.rag_manager import RAGManager
from services.processing_service import ProcessingService, ProcessingConfig
from services.exceptions import ServiceException, BatchProcessingError


class BatchOperationType(Enum):
    """批量操作类型"""
    UPLOAD = "upload"
    PROCESS = "process"
    DELETE = "delete"


class BatchStatus(Enum):
    """批量操作状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchProgressInfo(BaseModel):
    """批量操作进度信息"""
    batch_id: str
    operation_type: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    started_at: str
    estimated_remaining_seconds: Optional[float] = None
    processing_speed: Optional[float] = None
    current_phase: str
    active_tasks: int = 0
    error_summary: Optional[Dict[str, Any]] = None


class BatchProcessingRequest(BaseModel):
    """批量处理请求"""
    document_ids: List[str]
    processing_config: Optional[ProcessingConfig] = None
    concurrency_limit: int = 3
    retry_failed: bool = True


class BatchProcessingResult(BaseModel):
    """批量处理结果"""
    batch_id: str
    success: bool
    started_count: int
    failed_count: int
    total_requested: int
    results: List[Dict[str, Any]]
    message: str


# 批量操作观察者接口
class BatchObserver(ABC):
    """批量操作观察者接口 - 实现Observer Pattern"""
    
    @abstractmethod
    async def on_batch_started(self, batch_id: str):
        """批量操作开始"""
        pass
    
    @abstractmethod
    async def on_item_completed(self, batch_id: str, item_result: Dict[str, Any]):
        """单个项目完成"""
        pass
    
    @abstractmethod
    async def on_batch_completed(self, batch_id: str, final_result: Dict[str, Any]):
        """批量操作完成"""
        pass
    
    @abstractmethod
    async def on_batch_failed(self, batch_id: str, error: str):
        """批量操作失败"""
        pass


class WebSocketBatchObserver(BatchObserver):
    """WebSocket批量操作观察者"""
    
    def __init__(self, websocket_manager):
        self.websocket_manager = websocket_manager
    
    async def on_batch_started(self, batch_id: str):
        """通过WebSocket发送开始消息"""
        await self.websocket_manager.broadcast({
            "type": "batch_started",
            "batch_id": batch_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_item_completed(self, batch_id: str, item_result: Dict[str, Any]):
        """通过WebSocket发送项目完成消息"""
        await self.websocket_manager.broadcast({
            "type": "batch_item_completed",
            "batch_id": batch_id,
            "item_result": item_result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_batch_completed(self, batch_id: str, final_result: Dict[str, Any]):
        """通过WebSocket发送批量完成消息"""
        await self.websocket_manager.broadcast({
            "type": "batch_completed",
            "batch_id": batch_id,
            "result": final_result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def on_batch_failed(self, batch_id: str, error: str):
        """通过WebSocket发送失败消息"""
        await self.websocket_manager.broadcast({
            "type": "batch_failed",
            "batch_id": batch_id,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })


class ConcurrencyController:
    """并发控制器 - 控制同时运行的任务数量"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: Set[str] = set()
    
    async def acquire(self, task_id: str):
        """获取执行许可"""
        await self.semaphore.acquire()
        self.active_tasks.add(task_id)
    
    def release(self, task_id: str):
        """释放执行许可"""
        if task_id in self.active_tasks:
            self.active_tasks.remove(task_id)
        self.semaphore.release()
    
    def get_active_count(self) -> int:
        """获取当前活跃任务数"""
        return len(self.active_tasks)


class BatchService:
    """
    批量操作服务
    
    负责协调批量操作，包括并发控制、进度跟踪、错误处理
    应用Observer Pattern实现进度通知
    """
    
    def __init__(
        self,
        state_manager: StateManager,
        rag_manager: RAGManager,
        processing_service: ProcessingService
    ):
        self.state_manager = state_manager
        self.rag_manager = rag_manager
        self.processing_service = processing_service
        
        # 观察者列表
        self.observers: List[BatchObserver] = []
        
        # 活跃的批量操作
        self.active_batches: Dict[str, asyncio.Task] = {}
        
        # 并发控制器映射
        self.concurrency_controllers: Dict[str, ConcurrencyController] = {}
    
    def add_observer(self, observer: BatchObserver):
        """添加观察者"""
        self.observers.append(observer)
    
    def remove_observer(self, observer: BatchObserver):
        """移除观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    async def process_documents_batch(
        self,
        request: BatchProcessingRequest
    ) -> BatchProcessingResult:
        """
        批量处理文档
        
        Args:
            request: 批量处理请求
            
        Returns:
            BatchProcessingResult: 处理结果
        """
        batch_id = str(uuid.uuid4())
        
        try:
            # 创建批量操作记录
            batch_operation = await self._create_batch_operation(
                batch_id,
                BatchOperationType.PROCESS,
                len(request.document_ids)
            )
            
            # 验证文档和准备处理列表
            valid_documents, validation_results = await self._validate_documents_for_processing(
                request.document_ids
            )
            
            if not valid_documents:
                # 没有有效文档，直接完成
                await self._complete_batch_operation(
                    batch_id,
                    0,
                    len(request.document_ids),
                    validation_results
                )
                
                return BatchProcessingResult(
                    batch_id=batch_id,
                    success=False,
                    started_count=0,
                    failed_count=len(request.document_ids),
                    total_requested=len(request.document_ids),
                    results=validation_results,
                    message="没有有效的文档可以处理"
                )
            
            # 启动后台批量处理任务
            processing_task = asyncio.create_task(
                self._execute_batch_processing(
                    batch_id,
                    valid_documents,
                    request.processing_config,
                    request.concurrency_limit,
                    validation_results
                )
            )
            
            # 存储任务引用
            self.active_batches[batch_id] = processing_task
            
            # 设置任务完成回调
            processing_task.add_done_callback(
                lambda t: self._cleanup_batch_task(batch_id)
            )
            
            # 通知观察者批量操作开始
            await self._notify_observers("batch_started", batch_id)
            
            return BatchProcessingResult(
                batch_id=batch_id,
                success=True,
                started_count=len(valid_documents),
                failed_count=len(validation_results),
                total_requested=len(request.document_ids),
                results=validation_results,
                message=f"批量处理已启动: {len(valid_documents)} 个文档"
            )
            
        except Exception as e:
            # 更新批量操作为失败状态
            await self.state_manager.update_batch_operation(
                batch_id,
                status="failed",
                completed_at=datetime.now().isoformat(),
                error=str(e)
            )
            
            raise ServiceException(f"启动批量处理失败: {str(e)}") from e
    
    async def get_batch_progress(self, batch_id: str) -> BatchProgressInfo:
        """
        获取批量操作进度
        
        Args:
            batch_id: 批量操作ID
            
        Returns:
            BatchProgressInfo: 进度信息
        """
        batch_operation = await self.state_manager.get_batch_operation(batch_id)
        
        if not batch_operation:
            raise ServiceException("批量操作不存在")
        
        # 基本进度信息
        progress_info = BatchProgressInfo(
            batch_id=batch_id,
            operation_type=batch_operation.operation_type,
            status=batch_operation.status,
            total_items=batch_operation.total_items,
            completed_items=batch_operation.completed_items,
            failed_items=batch_operation.failed_items,
            progress=batch_operation.progress,
            started_at=batch_operation.started_at,
            current_phase="processing" if batch_operation.status == "running" else batch_operation.status
        )
        
        # 计算处理速度和预估时间
        if batch_operation.status == "running":
            progress_info = await self._calculate_processing_metrics(progress_info, batch_operation)
        
        # 获取活跃任务数
        if batch_id in self.concurrency_controllers:
            progress_info.active_tasks = self.concurrency_controllers[batch_id].get_active_count()
        
        return progress_info
    
    async def cancel_batch_operation(self, batch_id: str) -> bool:
        """
        取消批量操作
        
        Args:
            batch_id: 批量操作ID
            
        Returns:
            bool: 是否成功取消
        """
        batch_operation = await self.state_manager.get_batch_operation(batch_id)
        
        if not batch_operation:
            return False
        
        if batch_operation.status != "running":
            return False
        
        try:
            # 取消后台任务
            if batch_id in self.active_batches:
                task = self.active_batches[batch_id]
                if not task.done():
                    task.cancel()
            
            # 更新状态
            await self.state_manager.update_batch_operation(
                batch_id,
                status="cancelled",
                completed_at=datetime.now().isoformat()
            )
            
            # 通知观察者
            await self._notify_observers("batch_failed", batch_id, "用户取消操作")
            
            return True
            
        except Exception as e:
            raise ServiceException(f"取消批量操作失败: {str(e)}") from e
    
    async def get_all_batch_progress(self) -> Dict[str, Any]:
        """获取所有批量操作的进度"""
        all_operations = await self.state_manager.get_all_batch_operations()
        
        active_batches = []
        recent_history = []
        
        for op in all_operations:
            batch_info = {
                "batch_id": op.batch_operation_id,
                "operation_type": op.operation_type,
                "status": op.status,
                "progress": op.progress,
                "started_at": op.started_at,
                "completed_at": op.completed_at,
                "total_items": op.total_items,
                "completed_items": op.completed_items,
                "failed_items": op.failed_items
            }
            
            if op.status == "running":
                # 添加实时信息
                if op.batch_operation_id in self.concurrency_controllers:
                    batch_info["active_tasks"] = self.concurrency_controllers[op.batch_operation_id].get_active_count()
                active_batches.append(batch_info)
            else:
                recent_history.append(batch_info)
        
        # 限制历史记录数量
        recent_history.sort(key=lambda x: x["started_at"], reverse=True)
        recent_history = recent_history[:20]
        
        return {
            "success": True,
            "active_batches": active_batches,
            "recent_history": recent_history,
            "timestamp": datetime.now().isoformat()
        }
    
    async def cleanup_old_batch_operations(self, keep_days: int = 30) -> int:
        """清理旧的批量操作记录"""
        all_operations = await self.state_manager.get_all_batch_operations()
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        cleaned_count = 0
        for operation in all_operations:
            try:
                op_date = datetime.fromisoformat(operation.started_at)
                if (op_date < cutoff_date and 
                    operation.status in ["completed", "failed", "cancelled"]):
                    # TODO: 实现删除批量操作的方法
                    # await self.state_manager.remove_batch_operation(operation.batch_operation_id)
                    cleaned_count += 1
            except Exception:
                continue
        
        return cleaned_count
    
    async def get_batch_statistics(self) -> Dict[str, Any]:
        """获取批量操作统计信息"""
        all_operations = await self.state_manager.get_all_batch_operations()
        
        # 统计指标
        status_counts = {}
        operation_type_counts = {}
        total_items = 0
        total_completed = 0
        total_failed = 0
        
        for op in all_operations:
            status_counts[op.status] = status_counts.get(op.status, 0) + 1
            operation_type_counts[op.operation_type] = operation_type_counts.get(op.operation_type, 0) + 1
            
            total_items += op.total_items
            total_completed += op.completed_items
            total_failed += op.failed_items
        
        success_rate = (total_completed / total_items * 100) if total_items > 0 else 0
        
        return {
            "success": True,
            "statistics": {
                "total_batch_operations": len(all_operations),
                "status_distribution": status_counts,
                "operation_type_distribution": operation_type_counts,
                "processing_metrics": {
                    "total_items_processed": total_items,
                    "total_completed": total_completed,
                    "total_failed": total_failed,
                    "success_rate_percent": round(success_rate, 2)
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    
    # === 私有方法 ===
    
    async def _create_batch_operation(
        self,
        batch_id: str,
        operation_type: BatchOperationType,
        total_items: int
    ) -> BatchOperation:
        """创建批量操作记录"""
        batch_operation = BatchOperation(
            batch_operation_id=batch_id,
            operation_type=operation_type.value,
            status="running",
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            progress=0.0,
            started_at=datetime.now().isoformat(),
            results=[]
        )
        
        await self.state_manager.add_batch_operation(batch_operation)
        return batch_operation
    
    async def _validate_documents_for_processing(
        self,
        document_ids: List[str]
    ) -> tuple[List[Document], List[Dict[str, Any]]]:
        """验证文档是否可以处理"""
        valid_documents = []
        validation_results = []
        
        for document_id in document_ids:
            document = await self.state_manager.get_document(document_id)
            
            if not document:
                validation_results.append({
                    "document_id": document_id,
                    "file_name": "unknown",
                    "status": "failed",
                    "message": "文档不存在",
                    "task_id": None
                })
                continue
            
            if document.status != "uploaded":
                validation_results.append({
                    "document_id": document_id,
                    "file_name": document.file_name,
                    "status": "failed",
                    "message": f"文档状态不允许处理: {document.status}",
                    "task_id": document.task_id
                })
                continue
            
            # 验证文件存在
            if not os.path.exists(document.file_path):
                validation_results.append({
                    "document_id": document_id,
                    "file_name": document.file_name,
                    "status": "failed",
                    "message": f"文件不存在: {document.file_path}",
                    "task_id": document.task_id
                })
                continue
            
            valid_documents.append(document)
        
        return valid_documents, validation_results
    
    async def _execute_batch_processing(
        self,
        batch_id: str,
        documents: List[Document],
        processing_config: Optional[ProcessingConfig],
        concurrency_limit: int,
        initial_results: List[Dict[str, Any]]
    ):
        """执行批量处理"""
        try:
            # 创建并发控制器
            controller = ConcurrencyController(concurrency_limit)
            self.concurrency_controllers[batch_id] = controller
            
            # 创建处理任务
            tasks = []
            for document in documents:
                task = asyncio.create_task(
                    self._process_single_document_with_control(
                        batch_id,
                        document,
                        processing_config,
                        controller
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            completed_count = 0
            failed_count = 0
            processing_results = initial_results.copy()
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processing_results.append({
                        "document_id": documents[i].document_id,
                        "file_name": documents[i].file_name,
                        "status": "failed",
                        "message": f"处理异常: {str(result)}",
                        "task_id": documents[i].task_id
                    })
                    failed_count += 1
                else:
                    processing_results.append(result)
                    if result.get("status") == "success":
                        completed_count += 1
                    else:
                        failed_count += 1
            
            # 更新批量操作状态
            await self._complete_batch_operation(
                batch_id,
                completed_count,
                failed_count + len(initial_results),
                processing_results
            )
            
            # 通知观察者完成
            final_result = {
                "completed_count": completed_count,
                "failed_count": failed_count + len(initial_results),
                "total_count": len(documents) + len(initial_results)
            }
            await self._notify_observers("batch_completed", batch_id, final_result)
            
        except asyncio.CancelledError:
            # 批量操作被取消
            await self.state_manager.update_batch_operation(
                batch_id,
                status="cancelled",
                completed_at=datetime.now().isoformat()
            )
        except Exception as e:
            # 批量操作失败
            await self.state_manager.update_batch_operation(
                batch_id,
                status="failed",
                completed_at=datetime.now().isoformat(),
                error=str(e)
            )
            await self._notify_observers("batch_failed", batch_id, str(e))
        finally:
            # 清理并发控制器
            if batch_id in self.concurrency_controllers:
                del self.concurrency_controllers[batch_id]
    
    async def _process_single_document_with_control(
        self,
        batch_id: str,
        document: Document,
        processing_config: Optional[ProcessingConfig],
        controller: ConcurrencyController
    ) -> Dict[str, Any]:
        """使用并发控制处理单个文档"""
        task_id = f"{batch_id}_{document.document_id}"
        
        try:
            # 获取执行许可
            await controller.acquire(task_id)
            
            # 更新文档状态
            await self.state_manager.update_document_status(
                document.document_id,
                "processing",
                batch_operation_id=batch_id
            )
            
            # 执行处理
            result = await self.processing_service.process_document(
                document.document_id,
                processing_config
            )
            
            # 构造结果
            item_result = {
                "document_id": document.document_id,
                "file_name": document.file_name,
                "status": "success" if result.success else "failed",
                "message": result.message,
                "task_id": document.task_id,
                "processing_time": result.processing_time_seconds,
                "chunks_count": result.chunks_count
            }
            
            # 通知观察者单个项目完成
            await self._notify_observers("item_completed", batch_id, item_result)
            
            return item_result
            
        except Exception as e:
            error_result = {
                "document_id": document.document_id,
                "file_name": document.file_name,
                "status": "failed",
                "message": f"处理失败: {str(e)}",
                "task_id": document.task_id
            }
            
            await self._notify_observers("item_completed", batch_id, error_result)
            return error_result
            
        finally:
            # 释放执行许可
            controller.release(task_id)
    
    async def _complete_batch_operation(
        self,
        batch_id: str,
        completed_count: int,
        failed_count: int,
        results: List[Dict[str, Any]]
    ):
        """完成批量操作"""
        total_items = completed_count + failed_count
        progress = 100.0 if total_items > 0 else 0.0
        
        await self.state_manager.update_batch_operation(
            batch_id,
            completed_items=completed_count,
            failed_items=failed_count,
            progress=progress,
            status="completed",
            completed_at=datetime.now().isoformat(),
            results=results
        )
    
    async def _calculate_processing_metrics(
        self,
        progress_info: BatchProgressInfo,
        batch_operation: BatchOperation
    ) -> BatchProgressInfo:
        """计算处理指标"""
        try:
            start_time = datetime.fromisoformat(batch_operation.started_at)
            current_time = datetime.now()
            elapsed_seconds = (current_time - start_time).total_seconds()
            
            if elapsed_seconds > 0 and batch_operation.completed_items > 0:
                items_per_second = batch_operation.completed_items / elapsed_seconds
                remaining_items = batch_operation.total_items - batch_operation.completed_items
                
                if items_per_second > 0:
                    progress_info.estimated_remaining_seconds = remaining_items / items_per_second
                    progress_info.processing_speed = items_per_second
        except Exception:
            pass  # 忽略计算错误
        
        return progress_info
    
    async def _notify_observers(self, event_type: str, batch_id: str, data: Any = None):
        """通知所有观察者"""
        for observer in self.observers:
            try:
                if event_type == "batch_started":
                    await observer.on_batch_started(batch_id)
                elif event_type == "item_completed":
                    await observer.on_item_completed(batch_id, data)
                elif event_type == "batch_completed":
                    await observer.on_batch_completed(batch_id, data)
                elif event_type == "batch_failed":
                    await observer.on_batch_failed(batch_id, data)
            except Exception:
                pass  # 忽略观察者通知错误，不影响主流程
    
    def _cleanup_batch_task(self, batch_id: str):
        """清理批量任务"""
        if batch_id in self.active_batches:
            del self.active_batches[batch_id]