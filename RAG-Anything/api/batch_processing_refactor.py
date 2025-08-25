#!/usr/bin/env python3
"""
批量处理重构模块 - 第一阶段实现
解决架构问题，提供清晰的职责分离
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingState(Enum):
    """处理状态枚举"""
    CREATED = "created"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CacheMetrics:
    """缓存指标数据类 - 始终有默认值"""
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_ratio: float = 0.0
    total_time_saved: float = 0.0
    efficiency_improvement: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": self.cache_hit_ratio,
            "total_time_saved": self.total_time_saved,
            "efficiency_improvement": self.efficiency_improvement
        }
    
    def update_from(self, other_metrics: Optional[Dict[str, Any]]) -> None:
        """从字典更新指标"""
        if not other_metrics:
            return
        
        self.cache_hits = other_metrics.get("cache_hits", self.cache_hits)
        self.cache_misses = other_metrics.get("cache_misses", self.cache_misses)
        self.cache_hit_ratio = other_metrics.get("cache_hit_ratio", self.cache_hit_ratio)
        self.total_time_saved = other_metrics.get("total_time_saved", self.total_time_saved)
        self.efficiency_improvement = other_metrics.get("efficiency_improvement", self.efficiency_improvement)
    
    def calculate_ratio(self) -> None:
        """计算缓存命中率"""
        total = self.cache_hits + self.cache_misses
        if total > 0:
            self.cache_hit_ratio = (self.cache_hits / total) * 100


@dataclass
class BatchContext:
    """批处理上下文 - 管理批处理的所有状态"""
    batch_id: str
    document_ids: List[str]
    cache_metrics: CacheMetrics = field(default_factory=CacheMetrics)
    state: ProcessingState = ProcessingState.CREATED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    results: Dict[str, Any] = field(default_factory=dict)
    
    def transition_to(self, new_state: ProcessingState) -> bool:
        """状态转换"""
        # 定义允许的状态转换
        allowed_transitions = {
            ProcessingState.CREATED: [ProcessingState.VALIDATING, ProcessingState.CANCELLED],
            ProcessingState.VALIDATING: [ProcessingState.PROCESSING, ProcessingState.FAILED],
            ProcessingState.PROCESSING: [ProcessingState.COMPLETED, ProcessingState.FAILED, ProcessingState.CANCELLED],
            ProcessingState.COMPLETED: [],
            ProcessingState.FAILED: [],
            ProcessingState.CANCELLED: []
        }
        
        if new_state in allowed_transitions.get(self.state, []):
            self.state = new_state
            if new_state in [ProcessingState.COMPLETED, ProcessingState.FAILED, ProcessingState.CANCELLED]:
                self.completed_at = datetime.now().isoformat()
            return True
        
        logger.warning(f"Invalid state transition from {self.state} to {new_state}")
        return False


class DocumentValidator:
    """文档验证器 - 单一职责：验证文档"""
    
    def __init__(self, documents_store: Dict[str, Any]):
        self.documents = documents_store
    
    async def validate_document(self, document_id: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        验证单个文档
        返回: (是否有效, 错误消息, 文档信息)
        """
        # 检查文档是否存在
        if document_id not in self.documents:
            return False, "文档不存在", None
        
        document = self.documents[document_id]
        
        # 检查文档状态
        if document["status"] != "uploaded":
            return False, f"文档状态不允许处理: {document['status']}", document
        
        # 检查文件路径
        import os
        if not os.path.exists(document["file_path"]):
            return False, f"文件不存在: {document['file_path']}", document
        
        return True, None, document
    
    async def validate_batch(self, document_ids: List[str]) -> Dict[str, Any]:
        """批量验证文档"""
        validation_results = {
            "valid_documents": [],
            "invalid_documents": [],
            "total": len(document_ids)
        }
        
        for doc_id in document_ids:
            is_valid, error_msg, doc_info = await self.validate_document(doc_id)
            
            if is_valid:
                validation_results["valid_documents"].append({
                    "document_id": doc_id,
                    "document": doc_info
                })
            else:
                validation_results["invalid_documents"].append({
                    "document_id": doc_id,
                    "error": error_msg
                })
        
        return validation_results


class CacheManager:
    """缓存管理器 - 单一职责：管理缓存操作和指标"""
    
    def __init__(self):
        self.metrics = CacheMetrics()
    
    def record_hit(self, time_saved: float = 0.0) -> None:
        """记录缓存命中"""
        self.metrics.cache_hits += 1
        self.metrics.total_time_saved += time_saved
        self.metrics.calculate_ratio()
    
    def record_miss(self) -> None:
        """记录缓存未命中"""
        self.metrics.cache_misses += 1
        self.metrics.calculate_ratio()
    
    def get_metrics(self) -> CacheMetrics:
        """获取当前指标的副本"""
        return CacheMetrics(
            cache_hits=self.metrics.cache_hits,
            cache_misses=self.metrics.cache_misses,
            cache_hit_ratio=self.metrics.cache_hit_ratio,
            total_time_saved=self.metrics.total_time_saved,
            efficiency_improvement=self.metrics.efficiency_improvement
        )
    
    def merge_metrics(self, other_metrics: Optional[Dict[str, Any]]) -> None:
        """合并其他指标"""
        if not other_metrics:
            return
        
        self.metrics.update_from(other_metrics)
        self.metrics.calculate_ratio()


class ErrorBoundary:
    """错误边界 - 统一的错误处理"""
    
    async def execute_with_boundary(self, operation, context: BatchContext) -> Tuple[bool, Any]:
        """
        在错误边界内执行操作
        返回: (是否成功, 结果或错误信息)
        """
        try:
            result = await operation()
            return True, result
        except FileNotFoundError as e:
            context.error_message = f"文件未找到: {str(e)}"
            logger.error(f"FileNotFoundError in batch {context.batch_id}: {e}")
            return False, str(e)
        except PermissionError as e:
            context.error_message = f"权限错误: {str(e)}"
            logger.error(f"PermissionError in batch {context.batch_id}: {e}")
            return False, str(e)
        except asyncio.TimeoutError as e:
            context.error_message = f"处理超时: {str(e)}"
            logger.error(f"TimeoutError in batch {context.batch_id}: {e}")
            return False, str(e)
        except Exception as e:
            context.error_message = f"未知错误: {str(e)}"
            logger.error(f"Unexpected error in batch {context.batch_id}: {e}")
            return False, str(e)


class BatchProcessingCoordinator:
    """
    批处理协调器 - 编排各个组件
    解决原始代码的问题：
    1. 清晰的职责分离
    2. 始终初始化的cache_metrics
    3. 统一的错误处理
    4. 明确的状态管理
    """
    
    def __init__(self, 
                 documents_store: Dict[str, Any],
                 tasks_store: Dict[str, Any],
                 rag_instance: Any = None,
                 cache_processor: Any = None):
        self.documents = documents_store
        self.tasks = tasks_store
        self.rag_instance = rag_instance
        self.cache_processor = cache_processor
        
        # 初始化组件
        self.validator = DocumentValidator(documents_store)
        self.cache_manager = CacheManager()
        self.error_boundary = ErrorBoundary()
    
    async def process_batch(self, 
                           batch_id: str,
                           document_ids: List[str],
                           options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理批量文档
        返回处理结果，包含cache_metrics
        """
        # 1. 创建批处理上下文 - cache_metrics始终被初始化
        context = BatchContext(
            batch_id=batch_id,
            document_ids=document_ids,
            cache_metrics=CacheMetrics()  # 始终初始化
        )
        
        # 2. 验证阶段
        context.transition_to(ProcessingState.VALIDATING)
        
        success, validation_result = await self.error_boundary.execute_with_boundary(
            lambda: self.validator.validate_batch(document_ids),
            context
        )
        
        if not success:
            context.transition_to(ProcessingState.FAILED)
            return self._create_failure_response(context, validation_result)
        
        valid_docs = validation_result["valid_documents"]
        invalid_docs = validation_result["invalid_documents"]
        
        if not valid_docs:
            context.transition_to(ProcessingState.FAILED)
            context.error_message = "没有有效的文档可处理"
            return self._create_failure_response(context, "No valid documents")
        
        # 3. 处理阶段
        context.transition_to(ProcessingState.PROCESSING)
        
        # 准备文件路径列表
        file_paths = [doc["document"]["file_path"] for doc in valid_docs]
        
        # 如果有缓存处理器，使用它
        if self.cache_processor:
            success, processing_result = await self.error_boundary.execute_with_boundary(
                lambda: self._process_with_cache(file_paths, options or {}),
                context
            )
            
            if success and isinstance(processing_result, dict):
                # 更新缓存指标
                batch_cache_metrics = processing_result.get("cache_metrics")
                if batch_cache_metrics:
                    context.cache_metrics.update_from(batch_cache_metrics)
                
                # 保存处理结果
                context.results = processing_result
        else:
            # 没有缓存处理器时的后备处理
            context.results = {"message": "No cache processor available"}
        
        # 4. 完成阶段
        if success:
            context.transition_to(ProcessingState.COMPLETED)
        else:
            context.transition_to(ProcessingState.FAILED)
        
        # 5. 返回结果 - 保证cache_metrics始终存在
        return self._create_response(context, valid_docs, invalid_docs)
    
    async def _process_with_cache(self, file_paths: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """使用缓存处理器处理文件"""
        if not self.cache_processor:
            raise ValueError("Cache processor not available")
        
        # 调用缓存增强处理器
        result = await self.cache_processor.batch_process_with_cache_tracking(
            file_paths=file_paths,
            output_dir=options.get("output_dir", "./output"),
            parse_method=options.get("parse_method", "auto"),
            max_workers=options.get("max_workers", 3),
            recursive=False,
            show_progress=True
        )
        
        return result
    
    def _create_response(self, 
                        context: BatchContext, 
                        valid_docs: List[Dict],
                        invalid_docs: List[Dict]) -> Dict[str, Any]:
        """创建响应 - 确保所有必要字段都存在"""
        return {
            "success": context.state == ProcessingState.COMPLETED,
            "batch_id": context.batch_id,
            "state": context.state.value,
            "started_at": context.created_at,
            "completed_at": context.completed_at,
            "total_requested": len(context.document_ids),
            "valid_count": len(valid_docs),
            "invalid_count": len(invalid_docs),
            "cache_performance": context.cache_metrics.to_dict(),  # 始终有值
            "results": context.results,
            "error_message": context.error_message
        }
    
    def _create_failure_response(self, context: BatchContext, error_detail: str) -> Dict[str, Any]:
        """创建失败响应 - 确保cache_metrics存在"""
        return {
            "success": False,
            "batch_id": context.batch_id,
            "state": context.state.value,
            "error_message": context.error_message or error_detail,
            "cache_performance": context.cache_metrics.to_dict(),  # 即使失败也有值
            "results": {}
        }


# 导出重构的批处理协调器
__all__ = [
    'BatchProcessingCoordinator',
    'BatchContext',
    'CacheMetrics',
    'ProcessingState',
    'DocumentValidator',
    'CacheManager',
    'ErrorBoundary'
]