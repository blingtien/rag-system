#!/usr/bin/env python3
"""
Enhanced Error Handler for RAG-Anything API
Provides comprehensive error categorization, recovery mechanisms, and user-friendly error reporting
"""

import os
import time
import asyncio
import logging
import psutil
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for better handling and user feedback"""
    TRANSIENT = "transient"           # Temporary issues that can be retried
    PERMANENT = "permanent"           # Issues that won't resolve with retry
    SYSTEM = "system"                 # System resource or environment issues
    TIMEOUT = "timeout"               # Operations that exceed time limits
    GPU_MEMORY = "gpu_memory"         # GPU out of memory issues
    NETWORK = "network"               # Network connectivity issues
    VALIDATION = "validation"         # Input validation errors
    UNKNOWN = "unknown"               # Unclassified errors


@dataclass
class ErrorInfo:
    """Comprehensive error information"""
    category: ErrorCategory
    original_error: Exception
    message: str
    user_message: str
    suggested_solution: str
    is_recoverable: bool
    retry_delay: float = 1.0
    max_retries: int = 3
    context: Dict[str, Any] = None
    occurred_at: datetime = None
    
    def __post_init__(self):
        if self.occurred_at is None:
            self.occurred_at = datetime.now()
        if self.context is None:
            self.context = {}


class EnhancedErrorHandler:
    """
    Enhanced error handler with categorization, recovery mechanisms, and user feedback
    """
    
    def __init__(self):
        self.error_patterns = self._initialize_error_patterns()
        self.retry_attempts = {}
        self.gpu_fallback_enabled = True
        self.system_health_warnings = []
        
    def _initialize_error_patterns(self) -> Dict[str, Tuple[ErrorCategory, str, str, bool, int]]:
        """
        Initialize error patterns for categorization
        Format: pattern -> (category, user_message, solution, recoverable, max_retries)
        """
        return {
            # GPU Memory Issues
            "out of memory": (
                ErrorCategory.GPU_MEMORY,
                "GPU内存不足",
                "尝试使用CPU处理或减小批处理大小",
                True, 2
            ),
            "cuda out of memory": (
                ErrorCategory.GPU_MEMORY,
                "CUDA显存不足",
                "将自动切换到CPU处理或减小文档批次",
                True, 2
            ),
            "allocate memory": (
                ErrorCategory.GPU_MEMORY,
                "内存分配失败",
                "释放内存后重试或使用更小的批次大小",
                True, 2
            ),
            
            # Network Issues
            "connection timeout": (
                ErrorCategory.NETWORK,
                "网络连接超时",
                "检查网络连接，稍后重试",
                True, 3
            ),
            "connection refused": (
                ErrorCategory.NETWORK,
                "连接被拒绝",
                "检查服务状态和网络配置",
                True, 3
            ),
            "network is unreachable": (
                ErrorCategory.NETWORK,
                "网络不可达",
                "检查网络连接和防火墙设置",
                True, 2
            ),
            
            # File and System Issues
            "no such file": (
                ErrorCategory.PERMANENT,
                "文件不存在",
                "确认文件路径正确且文件存在",
                False, 0
            ),
            "permission denied": (
                ErrorCategory.SYSTEM,
                "权限不足",
                "检查文件权限或运行权限",
                False, 0
            ),
            "disk space": (
                ErrorCategory.SYSTEM,
                "磁盘空间不足",
                "清理磁盘空间后重试",
                True, 1
            ),
            "no space left": (
                ErrorCategory.SYSTEM,
                "存储空间已满",
                "清理存储空间或选择其他存储位置",
                True, 1
            ),
            
            # Parsing and Processing Issues
            "parse error": (
                ErrorCategory.PERMANENT,
                "文档解析失败",
                "文件可能损坏或格式不受支持",
                False, 0
            ),
            "unsupported format": (
                ErrorCategory.VALIDATION,
                "不支持的文件格式",
                "请使用支持的文件格式",
                False, 0
            ),
            "corrupted": (
                ErrorCategory.PERMANENT,
                "文件损坏",
                "文件已损坏，无法处理",
                False, 0
            ),
            
            # Timeout Issues
            "timeout": (
                ErrorCategory.TIMEOUT,
                "操作超时",
                "增加超时时间或减小文档大小",
                True, 2
            ),
            "timed out": (
                ErrorCategory.TIMEOUT,
                "处理超时",
                "文档太大或系统负载过高，稍后重试",
                True, 2
            ),
            
            # API and Service Issues
            "rate limit": (
                ErrorCategory.TRANSIENT,
                "API调用频率限制",
                "等待一段时间后重试",
                True, 3
            ),
            "service unavailable": (
                ErrorCategory.TRANSIENT,
                "服务暂时不可用",
                "稍后重试",
                True, 3
            ),
            "internal server error": (
                ErrorCategory.TRANSIENT,
                "服务器内部错误",
                "稍后重试，如持续出现请联系管理员",
                True, 2
            ),
        }
    
    def categorize_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Categorize an error and generate comprehensive error information
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for specific error patterns
        for pattern, (category, user_msg, solution, recoverable, max_retries) in self.error_patterns.items():
            if pattern in error_str or pattern in error_type:
                return ErrorInfo(
                    category=category,
                    original_error=error,
                    message=str(error),
                    user_message=user_msg,
                    suggested_solution=solution,
                    is_recoverable=recoverable,
                    max_retries=max_retries,
                    context=context or {}
                )
        
        # Default categorization based on exception type
        if isinstance(error, (FileNotFoundError, IsADirectoryError, NotADirectoryError)):
            return ErrorInfo(
                category=ErrorCategory.PERMANENT,
                original_error=error,
                message=str(error),
                user_message="文件系统错误",
                suggested_solution="检查文件路径和权限",
                is_recoverable=False,
                context=context or {}
            )
        elif isinstance(error, (PermissionError, OSError)):
            return ErrorInfo(
                category=ErrorCategory.SYSTEM,
                original_error=error,
                message=str(error),
                user_message="系统权限或资源错误",
                suggested_solution="检查系统权限和可用资源",
                is_recoverable=True,
                max_retries=1,
                context=context or {}
            )
        elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return ErrorInfo(
                category=ErrorCategory.TIMEOUT,
                original_error=error,
                message=str(error),
                user_message="操作超时",
                suggested_solution="增加超时时间或优化处理参数",
                is_recoverable=True,
                max_retries=2,
                context=context or {}
            )
        else:
            # Unknown error
            return ErrorInfo(
                category=ErrorCategory.UNKNOWN,
                original_error=error,
                message=str(error),
                user_message="未知错误",
                suggested_solution="请查看详细日志或联系技术支持",
                is_recoverable=True,
                max_retries=1,
                context=context or {}
            )
    
    async def handle_error_with_recovery(
        self,
        error: Exception,
        operation_func: Callable,
        operation_id: str,
        context: Dict[str, Any] = None,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[bool, Any, ErrorInfo]:
        """
        Handle error with automatic recovery mechanisms
        
        Returns:
            (success, result, error_info)
        """
        error_info = self.categorize_error(error, context)
        
        # Check if error is recoverable
        if not error_info.is_recoverable:
            logger.error(f"Permanent error in {operation_id}: {error_info.user_message}")
            return False, None, error_info
        
        # Check retry count
        retry_key = f"{operation_id}_{error_info.category.value}"
        current_retries = self.retry_attempts.get(retry_key, 0)
        
        if current_retries >= error_info.max_retries:
            logger.error(f"Max retries exceeded for {operation_id}: {error_info.user_message}")
            error_info.user_message += f" (已重试{current_retries}次)"
            error_info.suggested_solution += "，请检查系统状态或联系技术支持"
            return False, None, error_info
        
        # Implement specific recovery strategies
        recovery_success = await self._apply_recovery_strategy(error_info, context)
        
        if not recovery_success:
            logger.warning(f"Recovery strategy failed for {operation_id}")
            return False, None, error_info
        
        # Retry the operation
        self.retry_attempts[retry_key] = current_retries + 1
        retry_delay = self._calculate_retry_delay(current_retries, error_info.category)
        
        if progress_callback:
            await progress_callback(
                f"遇到{error_info.user_message}，{retry_delay:.1f}秒后重试 (第{current_retries + 1}次)",
                "warning"
            )
        
        logger.info(f"Retrying {operation_id} after {retry_delay}s delay (attempt {current_retries + 1})")
        await asyncio.sleep(retry_delay)
        
        try:
            result = await operation_func()
            # Clear retry count on success
            self.retry_attempts.pop(retry_key, None)
            
            if progress_callback:
                await progress_callback("重试成功，继续处理", "success")
            
            return True, result, error_info
            
        except Exception as retry_error:
            # Recursive call for nested error handling
            return await self.handle_error_with_recovery(
                retry_error, operation_func, operation_id, context, progress_callback
            )
    
    async def _apply_recovery_strategy(self, error_info: ErrorInfo, context: Dict[str, Any]) -> bool:
        """
        Apply specific recovery strategies based on error category
        """
        try:
            if error_info.category == ErrorCategory.GPU_MEMORY:
                return await self._handle_gpu_memory_error(context)
            elif error_info.category == ErrorCategory.SYSTEM:
                return await self._handle_system_error(context)
            elif error_info.category == ErrorCategory.NETWORK:
                return await self._handle_network_error(context)
            elif error_info.category in [ErrorCategory.TRANSIENT, ErrorCategory.TIMEOUT]:
                return True  # Simple retry
            else:
                return False
        except Exception as e:
            logger.error(f"Recovery strategy failed: {e}")
            return False
    
    async def _handle_gpu_memory_error(self, context: Dict[str, Any]) -> bool:
        """Handle GPU memory errors with device fallback"""
        if not self.gpu_fallback_enabled:
            return False
        
        logger.info("Attempting GPU memory recovery...")
        
        # Clear GPU cache if available
        if TORCH_AVAILABLE:
            try:
                torch.cuda.empty_cache()
                logger.info("GPU cache cleared")
            except Exception as e:
                logger.warning(f"Failed to clear GPU cache: {e}")
        
        # Switch to CPU processing
        if context and "device" in context:
            original_device = context.get("device", "cuda")
            if original_device != "cpu":
                context["device"] = "cpu"
                logger.info("Switched processing device from GPU to CPU")
                return True
        
        # Reduce batch size if applicable
        if context and "max_workers" in context:
            current_workers = context.get("max_workers", 3)
            if current_workers > 1:
                context["max_workers"] = max(1, current_workers // 2)
                logger.info(f"Reduced batch workers from {current_workers} to {context['max_workers']}")
                return True
        
        return False
    
    async def _handle_system_error(self, context: Dict[str, Any]) -> bool:
        """Handle system resource errors"""
        logger.info("Attempting system error recovery...")
        
        # Check disk space
        try:
            working_dir = context.get("working_dir", "/tmp")
            disk_usage = psutil.disk_usage(working_dir)
            free_gb = disk_usage.free / (1024**3)
            
            if free_gb < 1.0:  # Less than 1GB free
                self.system_health_warnings.append(f"磁盘空间不足: 剩余 {free_gb:.1f}GB")
                return False
            
        except Exception as e:
            logger.warning(f"Failed to check disk space: {e}")
        
        # Check memory usage
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self.system_health_warnings.append(f"内存使用率过高: {memory.percent:.1f}%")
                return False
        except Exception as e:
            logger.warning(f"Failed to check memory usage: {e}")
        
        # Wait a bit for system resources to recover
        await asyncio.sleep(2.0)
        return True
    
    async def _handle_network_error(self, context: Dict[str, Any]) -> bool:
        """Handle network connectivity errors"""
        logger.info("Attempting network error recovery...")
        
        # Simple wait for network recovery
        await asyncio.sleep(5.0)
        return True
    
    def _calculate_retry_delay(self, attempt: int, category: ErrorCategory) -> float:
        """Calculate exponential backoff delay"""
        base_delays = {
            ErrorCategory.TRANSIENT: 1.0,
            ErrorCategory.NETWORK: 2.0,
            ErrorCategory.GPU_MEMORY: 3.0,
            ErrorCategory.SYSTEM: 5.0,
            ErrorCategory.TIMEOUT: 10.0,
        }
        
        base_delay = base_delays.get(category, 1.0)
        return min(base_delay * (2 ** attempt), 30.0)  # Max 30 seconds
    
    def get_system_health_warnings(self) -> List[str]:
        """Get current system health warnings"""
        warnings = self.system_health_warnings.copy()
        self.system_health_warnings.clear()  # Clear after reading
        return warnings
    
    def get_user_friendly_error_message(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """
        Generate user-friendly error message with context and suggestions
        """
        return {
            "title": self._get_error_title(error_info.category),
            "message": error_info.user_message,
            "category": error_info.category.value,
            "suggested_solution": error_info.suggested_solution,
            "is_recoverable": error_info.is_recoverable,
            "severity": self._get_error_severity(error_info.category),
            "icon": self._get_error_icon(error_info.category),
            "timestamp": error_info.occurred_at.isoformat(),
            "context": error_info.context,
            "technical_details": str(error_info.original_error) if logger.level <= logging.DEBUG else None
        }
    
    def _get_error_title(self, category: ErrorCategory) -> str:
        """Get user-friendly error title"""
        titles = {
            ErrorCategory.GPU_MEMORY: "显存不足",
            ErrorCategory.NETWORK: "网络连接问题",
            ErrorCategory.SYSTEM: "系统资源问题",
            ErrorCategory.PERMANENT: "文件处理错误",
            ErrorCategory.TIMEOUT: "处理超时",
            ErrorCategory.TRANSIENT: "临时错误",
            ErrorCategory.VALIDATION: "输入验证错误",
            ErrorCategory.UNKNOWN: "未知错误"
        }
        return titles.get(category, "系统错误")
    
    def _get_error_severity(self, category: ErrorCategory) -> str:
        """Get error severity level"""
        if category in [ErrorCategory.PERMANENT, ErrorCategory.VALIDATION]:
            return "high"
        elif category in [ErrorCategory.SYSTEM, ErrorCategory.GPU_MEMORY]:
            return "medium"
        else:
            return "low"
    
    def _get_error_icon(self, category: ErrorCategory) -> str:
        """Get error icon for UI"""
        icons = {
            ErrorCategory.GPU_MEMORY: "memory",
            ErrorCategory.NETWORK: "wifi_off",
            ErrorCategory.SYSTEM: "warning",
            ErrorCategory.PERMANENT: "error",
            ErrorCategory.TIMEOUT: "schedule",
            ErrorCategory.TRANSIENT: "refresh",
            ErrorCategory.VALIDATION: "info",
            ErrorCategory.UNKNOWN: "help"
        }
        return icons.get(category, "error")
    
    def clear_retry_attempts(self):
        """Clear retry attempt counters"""
        self.retry_attempts.clear()


# Global error handler instance
enhanced_error_handler = EnhancedErrorHandler()