"""
批量处理协调器
统一协调批量处理的各个阶段，确保职责清晰分离
"""
import os
import logging
import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime

from models.batch_models import (
    BatchContext, BatchStatus, BatchResult, DocumentInfo, 
    CacheMetrics, ProcessingCounters, BatchOperation
)
from services.document_validator import DocumentValidator
from services.error_boundary import ErrorBoundary

logger = logging.getLogger(__name__)


class BatchProcessingCoordinator:
    """批量处理协调器
    
    负责协调整个批量处理流程：
    1. 文档验证
    2. 批量处理执行
    3. 状态更新
    4. 错误处理
    
    每个职责都委托给专门的服务类
    """
    
    def __init__(
        self,
        documents_store: Dict[str, Any],
        tasks_store: Dict[str, Any], 
        batch_operations: Dict[str, Any],
        cache_enhanced_processor: Any,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        初始化协调器
        
        Args:
            documents_store: 文档存储
            tasks_store: 任务存储
            batch_operations: 批量操作存储
            cache_enhanced_processor: 缓存增强处理器
            log_callback: 日志回调函数
        """
        self.documents = documents_store
        self.tasks = tasks_store
        self.batch_operations = batch_operations
        self.cache_processor = cache_enhanced_processor
        self.log_callback = log_callback
        
        # 初始化服务组件
        self.document_validator = DocumentValidator(documents_store, tasks_store)
        self.error_boundary = ErrorBoundary(log_callback)
    
    async def process_batch(
        self,
        document_ids: List[str],
        parser: str = "mineru",
        parse_method: str = "auto",
        max_workers: Optional[int] = None
    ) -> BatchContext:
        """
        执行完整的批量处理流程
        
        Args:
            document_ids: 要处理的文档ID列表
            parser: 解析器类型
            parse_method: 解析方法
            max_workers: 最大工作线程数
            
        Returns:
            BatchContext: 处理结果上下文
        """
        # 创建处理上下文，确保所有变量都正确初始化
        context = BatchContext(
            document_ids=document_ids,
            cache_metrics=CacheMetrics(),  # 始终初始化
            counters=ProcessingCounters(total_requested=len(document_ids))
        )
        
        try:
            await self._log_message(f"🚀 开始批量处理 {len(document_ids)} 个文档", "info")
            context.status = BatchStatus.RUNNING
            
            # 步骤1: 文档验证
            valid_docs, failed_results = await self._validate_documents(context)
            
            # 将失败结果添加到上下文
            for result in failed_results:
                context.add_result(result)
            
            # 步骤2: 如果有有效文档，执行批量处理
            if valid_docs:
                await self._execute_batch_processing(context, valid_docs, parser, parse_method, max_workers)
            else:
                await self._log_message("⚠️ 没有有效文档可以处理", "warning")
            
            # 步骤3: 完成处理
            await self._finalize_processing(context)
            
            return context
            
        except Exception as e:
            logger.error(f"批量处理异常: {str(e)}")
            
            # 使用错误边界处理异常
            error_info = await self.error_boundary.handle_batch_error(
                e, context, self.documents, self.tasks, self.batch_operations
            )
            
            # 确保上下文有正确的错误状态
            context.status = BatchStatus.FAILED
            context.error_message = error_info.message
            context.mark_completed()
            
            return context
    
    async def _validate_documents(self, context: BatchContext) -> tuple[List[DocumentInfo], List[BatchResult]]:
        """验证文档阶段"""
        await self._log_message("📋 开始文档验证", "info")
        
        try:
            valid_docs, failed_results = self.document_validator.validate_batch_documents(context.document_ids)
            
            # 更新上下文
            context.valid_documents = valid_docs
            context.file_paths = [doc.file_path for doc in valid_docs]
            
            # 记录验证摘要
            summary = self.document_validator.get_validation_summary(valid_docs, failed_results)
            await self._log_message(f"✅ {summary}", "info")
            
            return valid_docs, failed_results
            
        except Exception as e:
            await self._log_message(f"❌ 文档验证失败: {str(e)}", "error")
            raise
    
    async def _execute_batch_processing(
        self,
        context: BatchContext,
        valid_docs: List[DocumentInfo],
        parser: str,
        parse_method: str, 
        max_workers: Optional[int]
    ) -> None:
        """执行批量处理阶段"""
        await self._log_message(f"🔄 开始批量处理 {len(valid_docs)} 个文档", "info")
        
        try:
            # 创建进度回调
            async def progress_callback(progress_data):
                if self.log_callback:
                    await self.log_callback(f"📊 处理进度: {progress_data.get('message', '处理中...')}", "info")
            
            # 获取系统配置
            if max_workers is None:
                max_workers = self._get_optimal_worker_count()
            
            output_dir = os.getenv("OUTPUT_DIR", "./rag_storage")
            device_type = self._get_device_type()
            
            await self._log_message(f"⚙️ 处理配置: {parser}/{parse_method}, {max_workers}线程, {device_type}", "info")
            
            # 执行批量处理
            batch_result = await self.cache_processor.batch_process_with_cache_tracking(
                file_paths=context.file_paths,
                progress_callback=progress_callback,
                output_dir=output_dir,
                parse_method=parse_method,
                max_workers=max_workers,
                recursive=False,
                show_progress=True,
                lang="en",
                device=device_type
            )
            
            # 安全更新缓存指标
            if batch_result and isinstance(batch_result, dict):
                context.cache_metrics.update_from_batch_result(batch_result)
                
                # 处理批量结果
                await self._process_batch_results(context, batch_result, valid_docs)
            else:
                await self._log_message("⚠️ 批量处理返回了无效结果", "warning")
            
            await self._log_message("✅ 批量处理完成", "info")
            
        except Exception as e:
            await self._log_message(f"❌ 批量处理执行失败: {str(e)}", "error")
            raise
    
    async def _process_batch_results(
        self,
        context: BatchContext, 
        batch_result: Dict[str, Any],
        valid_docs: List[DocumentInfo]
    ) -> None:
        """处理批量结果"""
        rag_results = batch_result.get("rag_results", {})
        
        # 为每个有效文档处理结果
        path_to_doc = {doc.file_path: doc for doc in valid_docs}
        
        for file_path in context.file_paths:
            if file_path not in path_to_doc:
                continue
                
            doc_info = path_to_doc[file_path]
            rag_result = rag_results.get(file_path, {})
            
            if rag_result.get("processed", False):
                # 处理成功
                await self._handle_document_success(context, doc_info)
            else:
                # 处理失败
                error_msg = rag_result.get("error", "RAG处理失败")
                await self._handle_document_failure(context, doc_info, error_msg)
    
    async def _handle_document_success(self, context: BatchContext, doc_info: DocumentInfo) -> None:
        """处理文档成功"""
        # 更新文档状态
        if doc_info.document_id in self.documents:
            document = self.documents[doc_info.document_id]
            document["status"] = "completed"
            document["updated_at"] = datetime.now().isoformat()
        
        # 更新任务状态
        if doc_info.task_id and doc_info.task_id in self.tasks:
            task = self.tasks[doc_info.task_id]
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
        
        # 添加成功结果
        context.add_result(BatchResult(
            document_id=doc_info.document_id,
            file_name=doc_info.file_name,
            status="success",
            message="文档批量处理成功",
            task_id=doc_info.task_id
        ))
    
    async def _handle_document_failure(
        self, 
        context: BatchContext, 
        doc_info: DocumentInfo,
        error_msg: str
    ) -> None:
        """处理文档失败"""
        # 更新文档状态
        if doc_info.document_id in self.documents:
            document = self.documents[doc_info.document_id]
            document["status"] = "failed"
            document["updated_at"] = datetime.now().isoformat()
        
        # 更新任务状态
        if doc_info.task_id and doc_info.task_id in self.tasks:
            task = self.tasks[doc_info.task_id]
            task["status"] = "failed"
            task["error"] = error_msg
            task["updated_at"] = datetime.now().isoformat()
        
        # 添加失败结果
        context.add_result(BatchResult(
            document_id=doc_info.document_id,
            file_name=doc_info.file_name,
            status="failed",
            message=f"RAG处理失败: {error_msg}",
            task_id=doc_info.task_id
        ))
    
    async def _finalize_processing(self, context: BatchContext) -> None:
        """完成处理阶段"""
        context.mark_completed()
        
        # 记录缓存性能统计
        cache_metrics = context.cache_metrics
        cache_metrics.calculate_metrics()
        
        await self._log_message(
            f"📈 处理完成: {context.counters.completed} 成功, {context.counters.failed} 失败", 
            "info"
        )
        
        if cache_metrics.cache_hits > 0:
            await self._log_message(
                f"🚀 缓存性能: {cache_metrics.cache_hits} 命中, {cache_metrics.cache_hit_ratio:.1f}% 命中率",
                "info"
            )
        
        if cache_metrics.total_time_saved > 0:
            await self._log_message(
                f"⚡ 效率提升: 节省 {cache_metrics.total_time_saved:.1f}s, 提升 {cache_metrics.efficiency_improvement:.1f}%",
                "info"
            )
    
    def _get_optimal_worker_count(self) -> int:
        """获取最优工作线程数"""
        try:
            import psutil
            env_workers = os.getenv("MAX_CONCURRENT_PROCESSING")
            if env_workers:
                workers = min(max(int(env_workers), 1), psutil.cpu_count() * 2)
            else:
                workers = min(psutil.cpu_count(), 4)
            
            # 根据内存调整
            memory_gb = psutil.virtual_memory().total / (1024**3)
            if memory_gb < 8:
                workers = min(workers, 2)
            
            return workers
        except Exception:
            return int(os.getenv("MAX_CONCURRENT_PROCESSING", "3"))
    
    def _get_device_type(self) -> str:
        """获取设备类型"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
    
    async def _log_message(self, message: str, level: str = "info") -> None:
        """发送日志消息"""
        if self.log_callback:
            await self.log_callback(message, level)
        
        # 同时记录到标准日志
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)