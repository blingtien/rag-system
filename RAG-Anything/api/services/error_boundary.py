"""
错误边界和恢复机制
统一的错误处理，确保系统状态一致性
"""
import logging
import traceback
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from models.batch_models import BatchContext, BatchStatus, CacheMetrics

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误分类"""
    VALIDATION = "validation"
    PROCESSING = "processing"
    SYSTEM = "system"
    NETWORK = "network"
    STORAGE = "storage"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """错误信息封装"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    technical_details: str
    suggested_solution: str
    is_recoverable: bool
    context: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "technical_details": self.technical_details,
            "suggested_solution": self.suggested_solution,
            "is_recoverable": self.is_recoverable,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class ErrorBoundary:
    """错误边界
    
    提供统一的错误处理和状态恢复机制
    """
    
    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        初始化错误边界
        
        Args:
            log_callback: 日志回调函数，用于发送实时日志
        """
        self.log_callback = log_callback
        self.error_history: List[ErrorInfo] = []
    
    async def handle_batch_error(
        self, 
        error: Exception,
        context: BatchContext,
        documents_store: Dict[str, Any],
        tasks_store: Dict[str, Any],
        batch_operations: Dict[str, Any]
    ) -> ErrorInfo:
        """
        处理批量操作错误
        
        Args:
            error: 异常对象
            context: 批处理上下文
            documents_store: 文档存储
            tasks_store: 任务存储
            batch_operations: 批量操作存储
            
        Returns:
            ErrorInfo: 错误信息
        """
        # 1. 分析错误
        error_info = self._categorize_error(error, context)
        
        # 2. 记录错误
        self.error_history.append(error_info)
        await self._log_error(error_info)
        
        # 3. 尝试状态恢复
        await self._recover_state(error_info, context, documents_store, tasks_store, batch_operations)
        
        # 4. 提供恢复建议
        if error_info.is_recoverable:
            await self._log_message(f"💡 恢复建议: {error_info.suggested_solution}", "warning")
        
        return error_info
    
    def _categorize_error(self, error: Exception, context: BatchContext) -> ErrorInfo:
        """
        分类和分析错误
        
        Args:
            error: 异常对象
            context: 批处理上下文
            
        Returns:
            ErrorInfo: 分析后的错误信息
        """
        error_message = str(error)
        technical_details = traceback.format_exc()
        
        # 根据错误类型和消息进行分类
        if "cache_metrics" in error_message:
            return ErrorInfo(
                category=ErrorCategory.PROCESSING,
                severity=ErrorSeverity.MEDIUM,
                message="缓存指标初始化错误",
                technical_details=technical_details,
                suggested_solution="检查批处理流程中的变量初始化逻辑",
                is_recoverable=True,
                context={"batch_id": context.batch_id, "error_type": "variable_initialization"},
                timestamp=datetime.now()
            )
        
        elif "FileNotFoundError" in str(type(error)):
            return ErrorInfo(
                category=ErrorCategory.STORAGE,
                severity=ErrorSeverity.HIGH,
                message="文件不存在",
                technical_details=technical_details,
                suggested_solution="检查文件路径是否正确，文件是否被移动或删除",
                is_recoverable=False,
                context={"batch_id": context.batch_id, "document_count": len(context.document_ids)},
                timestamp=datetime.now()
            )
        
        elif "ConnectionError" in str(type(error)) or "TimeoutError" in str(type(error)):
            return ErrorInfo(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.HIGH,
                message="网络连接错误",
                technical_details=technical_details,
                suggested_solution="检查网络连接，稍后重试",
                is_recoverable=True,
                context={"batch_id": context.batch_id},
                timestamp=datetime.now()
            )
        
        elif "MemoryError" in str(type(error)):
            return ErrorInfo(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                message="系统内存不足",
                technical_details=technical_details,
                suggested_solution="减少并发处理数量，清理系统内存",
                is_recoverable=True,
                context={"batch_id": context.batch_id, "document_count": len(context.document_ids)},
                timestamp=datetime.now()
            )
        
        else:
            return ErrorInfo(
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.MEDIUM,
                message="未知错误",
                technical_details=technical_details,
                suggested_solution="请查看详细日志或联系技术支持",
                is_recoverable=True,
                context={"batch_id": context.batch_id, "error_message": error_message},
                timestamp=datetime.now()
            )
    
    async def _recover_state(
        self,
        error_info: ErrorInfo,
        context: BatchContext,
        documents_store: Dict[str, Any],
        tasks_store: Dict[str, Any],
        batch_operations: Dict[str, Any]
    ) -> None:
        """
        尝试恢复系统状态
        
        Args:
            error_info: 错误信息
            context: 批处理上下文
            documents_store: 文档存储
            tasks_store: 任务存储
            batch_operations: 批量操作存储
        """
        try:
            # 1. 确保缓存指标始终有效
            if not isinstance(context.cache_metrics, CacheMetrics):
                context.cache_metrics = CacheMetrics()
                await self._log_message("🔧 重置缓存指标为默认值", "info")
            
            # 2. 更新文档状态为失败
            for document_id in context.document_ids:
                if document_id in documents_store:
                    document = documents_store[document_id]
                    document["status"] = "failed"
                    document["error_category"] = error_info.category.value
                    document["error_severity"] = error_info.severity.value
                    document["suggested_solution"] = error_info.suggested_solution
                    document["updated_at"] = datetime.now().isoformat()
                    
                    # 更新对应的任务
                    task_id = document.get("task_id")
                    if task_id and task_id in tasks_store:
                        tasks_store[task_id]["status"] = "failed"
                        tasks_store[task_id]["error"] = error_info.message
                        tasks_store[task_id]["error_category"] = error_info.category.value
                        tasks_store[task_id]["error_details"] = error_info.to_dict()
                        tasks_store[task_id]["updated_at"] = datetime.now().isoformat()
            
            # 3. 更新批量操作状态
            if context.batch_id in batch_operations:
                batch_op = batch_operations[context.batch_id]
                batch_op["status"] = "failed"
                batch_op["failed_items"] = len(context.document_ids)
                batch_op["completed_at"] = datetime.now().isoformat()
                batch_op["error"] = error_info.message
                batch_op["error_details"] = error_info.to_dict()
                batch_op["progress"] = 100.0
            
            # 4. 更新上下文状态
            context.status = BatchStatus.FAILED
            context.error_message = error_info.message
            context.mark_completed()
            
            await self._log_message("✅ 系统状态恢复完成", "info")
            
        except Exception as recovery_error:
            logger.error(f"状态恢复失败: {str(recovery_error)}")
            await self._log_message(f"❌ 状态恢复失败: {str(recovery_error)}", "error")
    
    async def _log_error(self, error_info: ErrorInfo) -> None:
        """记录错误日志"""
        logger.error(f"错误边界捕获异常: {error_info.message}")
        logger.error(f"错误详情: {error_info.technical_details}")
        
        if self.log_callback:
            await self.log_callback(f"❌ 批量处理失败: {error_info.message}", "error")
    
    async def _log_message(self, message: str, level: str = "info") -> None:
        """发送日志消息"""
        if self.log_callback:
            await self.log_callback(message, level)
    
    def get_system_health_warnings(self) -> List[str]:
        """获取系统健康警告"""
        warnings = []
        
        # 统计最近的错误
        recent_errors = [e for e in self.error_history if 
                        (datetime.now() - e.timestamp).total_seconds() < 3600]  # 最近1小时
        
        if len(recent_errors) > 5:
            warnings.append("系统在过去1小时内发生了多次错误，建议检查系统状态")
        
        # 检查严重错误
        critical_errors = [e for e in recent_errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            warnings.append(f"发现 {len(critical_errors)} 个严重错误，需要立即处理")
        
        # 检查不可恢复错误
        unrecoverable_errors = [e for e in recent_errors if not e.is_recoverable]
        if unrecoverable_errors:
            warnings.append(f"发现 {len(unrecoverable_errors)} 个不可恢复错误，需要人工干预")
        
        return warnings
    
    def clear_error_history(self) -> None:
        """清理错误历史"""
        self.error_history.clear()